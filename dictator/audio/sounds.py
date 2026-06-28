"""Non-blocking sound feedback player. Fire-and-forget audio cues."""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100


class SoundPlayer:
    """Plays short synthesized feedback sounds without blocking the main loop."""

    def play(self, style: str = "wake") -> None:
        """Play a feedback sound asynchronously. Never blocks, never raises."""
        thread = threading.Thread(target=self._play_sync, args=(style,), daemon=True)
        thread.start()

    def _play_sync(self, style: str) -> None:
        try:
            wave = self._synthesize(style)
            if wave is not None:
                sd.play(wave, samplerate=SAMPLE_RATE)
                sd.wait()
        except Exception as e:
            logger.debug(f"Sound playback failed: {e}")

    def _synthesize(self, style: str) -> np.ndarray | None:
        if style == "wake":
            return self._make_wake()
        elif style == "success":
            return self._make_success()
        elif style == "exit":
            return self._make_exit()
        elif style == "error":
            return self._make_error()
        return None

    def _make_wake(self) -> np.ndarray:
        duration = 0.2
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        envelope = np.concatenate([
            np.linspace(0, 1, int(SAMPLE_RATE * 0.05)),
            np.ones(int(SAMPLE_RATE * 0.1)),
            np.linspace(1, 0, int(SAMPLE_RATE * 0.05)),
        ])
        return (0.5 * np.sin(2 * np.pi * 880.0 * t) * envelope).astype(np.float32)

    def _make_success(self) -> np.ndarray:
        duration = 0.3
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        len_note = len(t) // 2
        t1, t2 = t[:len_note], t[len_note:]

        wave1 = 0.5 * np.sin(2 * np.pi * 880.0 * t1)
        wave2 = 0.5 * np.sin(2 * np.pi * 1108.0 * t2)

        env1 = np.concatenate([
            np.linspace(0, 1, int(SAMPLE_RATE * 0.02)),
            np.linspace(1, 0, len_note - int(SAMPLE_RATE * 0.02)),
        ])
        env2 = np.concatenate([
            np.linspace(0, 1, int(SAMPLE_RATE * 0.02)),
            np.linspace(1, 0, len(t2) - int(SAMPLE_RATE * 0.02)),
        ])

        return np.concatenate([wave1 * env1, wave2 * env2]).astype(np.float32)

    def _make_exit(self) -> np.ndarray:
        duration = 0.3
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        f_start, f_end = 600, 300
        phase = 2 * np.pi * (f_start * t + (f_end - f_start) * t**2 / (2 * duration))
        envelope = np.concatenate([
            np.linspace(0, 1, int(SAMPLE_RATE * 0.05)),
            np.ones(int(SAMPLE_RATE * 0.15)),
            np.linspace(1, 0, int(SAMPLE_RATE * 0.1)),
        ])
        return (0.5 * np.sin(phase) * envelope).astype(np.float32)

    def _make_error(self) -> np.ndarray:
        duration = 0.4
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        wave = 0.4 * np.sin(2 * np.pi * 200.0 * t)
        envelope = np.concatenate([
            np.linspace(0, 1, int(SAMPLE_RATE * 0.02)),
            np.ones(int(SAMPLE_RATE * 0.2)),
            np.linspace(1, 0, int(SAMPLE_RATE * 0.18)),
        ])
        return (wave * envelope).astype(np.float32)
