from __future__ import annotations

import time
from typing import Generator

import numpy as np
import webrtcvad
from faster_whisper import WhisperModel

from .audio import audio_queue, fetch_audio

model: WhisperModel | None = None
vad = webrtcvad.Vad(2)

audio_buffer = np.zeros(0, dtype=np.float32)
last_text = ""
should_reset_flag = False
last_partial_time: float = 0
last_partial_text = ""

STABILITY_TIMEOUT = 2.0
MIN_AUDIO_SAMPLES = 16000


def force_reset() -> None:
    global should_reset_flag
    should_reset_flag = True


def load_model(model_size: str = "base.en") -> None:
    global model
    print(f"[STT] Loading Whisper model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("[STT] Model loaded.")


def transcribe_loop(
    stream: Generator | None = None,
) -> Generator[tuple[str | None, bool], None, None]:
    """
    Yields (text, is_final) tuples from the audio stream.
    text=None means no speech detected this cycle.
    """
    global audio_buffer, last_text, should_reset_flag
    global last_partial_time, last_partial_text

    if stream is None:
        stream = fetch_audio()

    while True:
        try:
            chunk = next(stream)
        except StopIteration:
            break

        if should_reset_flag:
            audio_buffer = np.zeros(0, dtype=np.float32)
            last_text = ""
            last_partial_text = ""
            should_reset_flag = False

        # Auto-commit stable partial text after timeout
        current_time = time.time()
        if last_partial_text and (current_time - last_partial_time > STABILITY_TIMEOUT):
            yield (last_partial_text, True)
            audio_buffer = np.zeros(0, dtype=np.float32)
            last_text = ""
            last_partial_text = ""
            last_partial_time = current_time

        # Drain all available audio from queue
        new_data = [chunk.flatten()]
        while not audio_queue.empty():
            new_data.append(next(stream).flatten())

        audio_buffer = np.concatenate([audio_buffer, *new_data])

        if len(audio_buffer) < MIN_AUDIO_SAMPLES:
            continue

        segments_gen, _ = model.transcribe(
            audio_buffer, language="en", vad_filter=True, beam_size=1
        )
        segments = list(segments_gen)

        if not segments:
            yield (None, False)
            continue

        final_text = ""
        partial_text = ""

        if len(segments) > 1:
            final_segments = segments[:-1]
            partial_segment = segments[-1]

            final_text = " ".join(s.text.strip() for s in final_segments)
            partial_text = partial_segment.text.strip()

            cut_samples = int(final_segments[-1].end * 16000)
            if cut_samples < len(audio_buffer):
                audio_buffer = audio_buffer[cut_samples:]
            else:
                audio_buffer = np.zeros(0, dtype=np.float32)

            if final_text:
                yield (final_text, True)
        else:
            partial_text = segments[0].text.strip()

        if partial_text != last_text:
            yield (partial_text, False)
            last_text = partial_text
            last_partial_text = partial_text
            last_partial_time = time.time()
        elif not partial_text:
            yield ("", False)
            last_text = ""
            last_partial_text = ""
