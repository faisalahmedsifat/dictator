"""Template Method pattern: Transcription pipeline with overridable steps and error recovery."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generator

import numpy as np

from dictator.core.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

MAX_BUFFER_SECONDS = 30
SAMPLE_RATE = 16000
MAX_BUFFER_SAMPLES = MAX_BUFFER_SECONDS * SAMPLE_RATE
STABILITY_TIMEOUT = 2.0
MIN_AUDIO_SAMPLES = SAMPLE_RATE  # 1 second minimum


@dataclass
class TranscriptionResult:
    text: str
    is_final: bool
    confidence: float = 1.0


class TranscriptionPipeline(ABC):
    """Template Method: defines the transcription algorithm skeleton with overridable steps."""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._audio_buffer = np.zeros(0, dtype=np.float32)
        self._last_partial_text = ""
        self._last_partial_time: float = 0.0
        self._should_reset = False

    def reset(self) -> None:
        """Signal the pipeline to reset its internal state on next iteration."""
        self._should_reset = True

    def run(self, stream: Generator[np.ndarray, None, None]) -> Generator[TranscriptionResult, None, None]:
        """Main pipeline loop. Yields transcription results from the audio stream."""
        for chunk in stream:
            if self._should_reset:
                self._do_reset()

            # Step 1: Preprocess (overridable)
            processed = self.preprocess(chunk)
            if processed is None:
                continue

            # Step 2: Buffer management with safety cap
            self._audio_buffer = np.concatenate([self._audio_buffer, processed.flatten()])
            if len(self._audio_buffer) > MAX_BUFFER_SAMPLES:
                self._audio_buffer = self._audio_buffer[-MAX_BUFFER_SAMPLES:]
                logger.debug("Audio buffer capped at max size")

            # Step 3: Auto-commit stable partials after timeout
            if self._last_partial_text and (time.time() - self._last_partial_time > STABILITY_TIMEOUT):
                yield TranscriptionResult(text=self._last_partial_text, is_final=True)
                self._do_reset()
                continue

            # Step 4: Check minimum audio threshold
            if len(self._audio_buffer) < MIN_AUDIO_SAMPLES:
                continue

            # Step 5: Transcribe (abstract, must implement)
            try:
                results = self.transcribe(self._audio_buffer)
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                yield from self.on_error(e)
                continue

            # Step 6: Postprocess results (overridable)
            for result in self.postprocess(results):
                if result.is_final:
                    self._last_partial_text = ""
                    self._last_partial_time = 0
                else:
                    if result.text != self._last_partial_text:
                        self._last_partial_text = result.text
                        self._last_partial_time = time.time()
                    else:
                        continue
                yield result

    # --- Template methods ---

    def preprocess(self, chunk: np.ndarray) -> np.ndarray | None:
        """Override to add custom preprocessing (VAD, noise reduction, etc.)."""
        return chunk

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> list[Any]:
        """Core transcription step. Must return a list of segment-like objects."""

    def postprocess(self, segments: list[Any]) -> list[TranscriptionResult]:
        """Override to customize how segments become TranscriptionResults."""
        if not segments:
            return []

        results = []
        if len(segments) > 1:
            final_text = " ".join(s.text.strip() for s in segments[:-1])
            if final_text:
                results.append(TranscriptionResult(text=final_text, is_final=True))
            # Trim buffer to after the finalized segments
            cut_time = segments[-2].end if len(segments) > 1 else 0
            cut_samples = int(cut_time * SAMPLE_RATE)
            if cut_samples < len(self._audio_buffer):
                self._audio_buffer = self._audio_buffer[cut_samples:]
            else:
                self._audio_buffer = np.zeros(0, dtype=np.float32)

        partial_text = segments[-1].text.strip() if segments else ""
        if partial_text:
            results.append(TranscriptionResult(text=partial_text, is_final=False))

        return results

    def on_error(self, error: Exception) -> list[TranscriptionResult]:
        """Override to customize error recovery behavior."""
        self._event_bus.publish(Event(
            type=EventType.ERROR_OCCURRED,
            data=f"Transcription error: {error}",
            source="transcription_pipeline",
        ))
        return []

    def _do_reset(self) -> None:
        self._audio_buffer = np.zeros(0, dtype=np.float32)
        self._last_partial_text = ""
        self._last_partial_time = 0
        self._should_reset = False


class WhisperTranscriptionPipeline(TranscriptionPipeline):
    """Concrete pipeline using faster-whisper for transcription."""

    def __init__(self, event_bus: EventBus, model_manager: Any):
        super().__init__(event_bus)
        self._model_manager = model_manager

    def transcribe(self, audio: np.ndarray) -> list[Any]:
        model = self._model_manager.get_whisper()
        segments_gen, _ = model.transcribe(
            audio, language="en", vad_filter=True, beam_size=1
        )
        return list(segments_gen)
