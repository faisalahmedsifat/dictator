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

WAKE_WORD_FILENAME = "hey_jarvis_v0.1.onnx"

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
        results["wake_word"] = wake_path.exists() and wake_path.stat().st_size > 10_000
        return results

    def models_available(self) -> bool:
        """Quick check if essential models are present."""
        integrity = self.verify_integrity()
        return all(integrity.values())

    def _extract_wake_word_model(self, dest: Path) -> bool:
        """Extract the wake word ONNX model from the openwakeword package."""
        try:
            import openwakeword

            oww_dir = Path(openwakeword.__file__).parent / "resources" / "models"
            source = oww_dir / WAKE_WORD_FILENAME

            if source.exists():
                shutil.copy2(source, dest)
                logger.info(f"Extracted wake word model to {dest}")
                return True

            for onnx_file in oww_dir.glob("*.onnx"):
                if "jarvis" in onnx_file.name.lower():
                    shutil.copy2(onnx_file, dest)
                    logger.info(f"Extracted wake word model from {onnx_file.name}")
                    return True

            logger.warning("Could not find wake word model in openwakeword package")
            return False

        except ImportError:
            logger.warning("openwakeword not installed, wake word model unavailable")
            return False
        except Exception as e:
            logger.error(f"Failed to extract wake word model: {e}")
            return False

    def _report_progress(self, description: str, fraction: float) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(description, fraction)
            except Exception:
                pass
