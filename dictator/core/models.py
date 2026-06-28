"""Singleton pattern: Model lifecycle management with lazy init and integrity verification."""

from __future__ import annotations

import logging
import shutil
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from dictator.utils.paths import get_models_dir

logger = logging.getLogger(__name__)

WAKE_WORD_FILENAME = "hey_jarvis_v0.1.tflite"

MAX_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_BASE = 5.0


class ModelManager:
    """Singleton managing AI model lifecycle: loading, downloading, and verification.

    Manages Whisper (speech-to-text) and wake word (ONNX) models.
    Agent intelligence is delegated to external CLI tools (e.g. claude).
    """

    _instance: ModelManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ModelManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._whisper_model: Any = None
        self._whisper_lock = threading.Lock()
        self._models_dir = get_models_dir()
        self._progress_callback: Callable[[str, float], None] | None = None

    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set a callback for download progress: callback(description, fraction_0_to_1)."""
        self._progress_callback = callback

    def get_whisper(self, model_size: str = "base.en") -> Any:
        """Lazily load and return the Whisper model (thread-safe)."""
        with self._whisper_lock:
            if self._whisper_model is None:
                from faster_whisper import WhisperModel

                logger.info(f"Loading Whisper model: {model_size}")
                self._whisper_model = WhisperModel(
                    model_size, device="cpu", compute_type="int8"
                )
                logger.info("Whisper model loaded.")
            return self._whisper_model

    def unload_whisper(self) -> None:
        """Release Whisper memory."""
        with self._whisper_lock:
            self._whisper_model = None
            logger.info("Whisper model unloaded.")

    def download_if_missing(self) -> bool:
        """Ensure wake word model is available. Returns True if all models are ready.

        Whisper models are auto-downloaded by faster-whisper on first use.
        """
        wake_path = self._models_dir / WAKE_WORD_FILENAME
        if not wake_path.exists():
            return self._extract_wake_word_model(wake_path)
        return True

    def verify_integrity(self) -> dict[str, bool]:
        """Check model files exist and are non-trivially sized."""
        results = {}
        wake_path = self._models_dir / WAKE_WORD_FILENAME
        has_wake = wake_path.exists() and wake_path.stat().st_size > 10_000
        if not has_wake:
            has_wake = any(
                f.stat().st_size > 10_000
                for f in self._models_dir.glob("*jarvis*")
            )
        results["wake_word"] = has_wake
        return results

    def models_available(self) -> bool:
        """Quick check if essential models are present."""
        integrity = self.verify_integrity()
        return all(integrity.values())

    def _extract_wake_word_model(self, dest: Path) -> bool:
        """Download the wake word model via openwakeword's download utility."""
        try:
            from openwakeword.utils import download_models

            dest.parent.mkdir(parents=True, exist_ok=True)
            self._report_progress("Downloading wake word model...", 0.2)

            download_models(
                model_names=["hey_jarvis_v0.1"],
                target_directory=str(dest.parent),
            )

            if dest.exists():
                logger.info(f"Wake word model ready at {dest}")
                self._report_progress("Wake word model ready", 1.0)
                return True

            for candidate in dest.parent.glob("*jarvis*"):
                logger.info(f"Wake word model available: {candidate.name}")
                self._report_progress("Wake word model ready", 1.0)
                return True

            logger.warning("Download completed but model file not found")
            return False

        except ImportError:
            logger.warning("openwakeword not installed, wake word model unavailable")
            return False
        except Exception as e:
            logger.error(f"Failed to download wake word model: {e}")
            return False

    def _report_progress(self, description: str, fraction: float) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(description, fraction)
            except Exception:
                pass
