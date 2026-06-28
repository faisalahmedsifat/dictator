"""Resilient audio stream with auto-reconnect via circuit breaker."""

from __future__ import annotations

import logging
import queue
import time
from typing import Generator

import numpy as np
import sounddevice as sd
from scipy import signal as scipy_signal

from dictator.core.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

TARGET_RATE = 16000
BLOCK_DURATION = 0.2


class AudioStream:
    """Manages microphone input with automatic reconnection on device loss.

    Uses a circuit breaker to prevent rapid reconnect loops when the device
    is genuinely unavailable.
    """

    def __init__(self, device: str | int | None = None):
        self._device = device
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._native_rate: int = TARGET_RATE
        self._circuit = CircuitBreaker(
            name="audio_stream",
            failure_threshold=5,
            reset_timeout=10.0,
        )
        self._running = False

    @property
    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    def start(self) -> None:
        """Open the audio stream. Raises on unrecoverable device errors."""
        self._running = True
        self._open_stream()

    def stop(self) -> None:
        """Close the audio stream and release the microphone."""
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Error closing stream: {e}")
            self._stream = None
        # Drain the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    def iter_chunks(self) -> Generator[np.ndarray, None, None]:
        """Yield resampled 16kHz audio chunks. Auto-reconnects on failure."""
        while self._running:
            try:
                raw_chunk = self._audio_queue.get(timeout=1.0)
                self._circuit.record_success()
            except queue.Empty:
                if not self.is_active and self._running:
                    self._try_reconnect()
                continue
            except Exception as e:
                logger.warning(f"Audio queue error: {e}")
                self._circuit.record_failure(e)
                self._try_reconnect()
                continue

            # Resample if needed
            if self._native_rate != TARGET_RATE:
                num_samples = int(len(raw_chunk) * TARGET_RATE / self._native_rate)
                chunk = scipy_signal.resample(raw_chunk, num_samples).astype(np.float32)
            else:
                chunk = raw_chunk

            yield chunk

    def _open_stream(self) -> None:
        """Open the sounddevice InputStream."""
        resolved = self._resolve_device()

        if resolved is not None:
            info = sd.query_devices(resolved, "input")
        else:
            info = sd.query_devices(kind="input")

        self._native_rate = int(info["default_samplerate"])
        block_size = int(self._native_rate * BLOCK_DURATION)

        # Clear stale data
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._stream = sd.InputStream(
            device=resolved,
            samplerate=self._native_rate,
            channels=1,
            blocksize=block_size,
            callback=self._audio_callback,
            dtype=np.float32,
        )
        self._stream.start()
        logger.info(f"Audio stream opened: device={resolved}, rate={self._native_rate}Hz")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            logger.debug(f"Audio callback status: {status}")
        self._audio_queue.put(indata.copy())

    def _try_reconnect(self) -> None:
        """Attempt to reopen the stream, respecting the circuit breaker."""
        if not self._circuit.is_available:
            time.sleep(1.0)
            return

        logger.info("Attempting audio stream reconnection...")
        try:
            if self._stream:
                self._stream.close()
                self._stream = None
            self._open_stream()
            logger.info("Audio stream reconnected successfully")
        except Exception as e:
            logger.warning(f"Reconnection failed: {e}")
            self._circuit.record_failure(e)

    def _resolve_device(self) -> int | None:
        """Resolve device name or index to integer index."""
        if self._device is None:
            return None
        if isinstance(self._device, int):
            return self._device
        try:
            return int(self._device)
        except ValueError:
            pass

        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if dev["name"] == self._device and dev["max_input_channels"] > 0:
                return i
        for i, dev in enumerate(devices):
            if self._device in dev["name"] and dev["max_input_channels"] > 0:
                logger.info(f"Resolved device '{self._device}' -> index {i} ({dev['name']})")
                return i

        raise ValueError(f"Could not find input device matching: {self._device}")

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
