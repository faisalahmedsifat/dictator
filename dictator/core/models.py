"""Singleton pattern: Model lifecycle management with lazy init and integrity verification."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from dictator.utils.paths import get_models_dir

logger = logging.getLogger(__name__)

QWEN_MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)
QWEN_MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
WAKE_WORD_FILENAME = "hey_jarvis_v0.1.onnx"

MAX_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_BASE = 5.0


class ModelManager:
    """Singleton managing AI model lifecycle: loading, downloading, and verification."""

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
        self._llm: Any = None
        self._whisper_lock = threading.Lock()
        self._llm_lock = threading.Lock()
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

    def get_llm(self) -> Any | None:
        """Lazily load and return the LLM (thread-safe). Returns None on failure."""
        with self._llm_lock:
            if self._llm is None:
                model_path = self._models_dir / QWEN_MODEL_FILENAME
                if not model_path.exists():
                    logger.warning("LLM model file not found. Agent unavailable.")
                    return None

                try:
                    from llama_cpp import Llama

                    logger.info("Loading Qwen LLM model...")
                    self._llm = Llama(
                        model_path=str(model_path),
                        n_gpu_layers=-1,
                        n_ctx=4096,
                        verbose=False,
                    )
                    logger.info("LLM model loaded.")
                except Exception as e:
                    logger.error(f"Failed to load LLM: {e}")
                    return None
            return self._llm

    def unload_llm(self) -> None:
        """Release LLM memory."""
        with self._llm_lock:
            self._llm = None
            logger.info("LLM unloaded.")

    def unload_whisper(self) -> None:
        """Release Whisper memory."""
        with self._whisper_lock:
            self._whisper_model = None
            logger.info("Whisper model unloaded.")

    def download_if_missing(self) -> bool:
        """Download models that are missing. Returns True if all models are available."""
        all_ok = True

        qwen_path = self._models_dir / QWEN_MODEL_FILENAME
        if not qwen_path.exists():
            success = self._download_with_retry(
                url=QWEN_MODEL_URL,
                dest=qwen_path,
                description="Qwen 2.5 LLM",
            )
            if not success:
                all_ok = False

        wake_path = self._models_dir / WAKE_WORD_FILENAME
        if not wake_path.exists():
            success = self._extract_wake_word_model(wake_path)
            if not success:
                all_ok = False

        return all_ok

    def verify_integrity(self) -> dict[str, bool]:
        """Check model files exist and are non-trivially sized."""
        results = {}

        qwen_path = self._models_dir / QWEN_MODEL_FILENAME
        results["qwen_llm"] = qwen_path.exists() and qwen_path.stat().st_size > 100_000_000

        wake_path = self._models_dir / WAKE_WORD_FILENAME
        results["wake_word"] = wake_path.exists() and wake_path.stat().st_size > 10_000

        return results

    def models_available(self) -> bool:
        """Quick check if essential models are present."""
        integrity = self.verify_integrity()
        return all(integrity.values())

    def _download_with_retry(self, url: str, dest: Path, description: str) -> bool:
        """Download a file with retry logic and progress reporting."""
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            try:
                logger.info(f"Downloading {description} (attempt {attempt}/{MAX_DOWNLOAD_RETRIES})...")
                self._report_progress(f"Downloading {description}...", 0.0)

                temp_path = dest.with_suffix(".tmp")
                self._download_file(url, temp_path)

                temp_path.rename(dest)
                self._report_progress(f"{description} complete", 1.0)
                logger.info(f"Downloaded {description} to {dest}")
                return True

            except Exception as e:
                logger.warning(f"Download attempt {attempt} failed: {e}")
                if attempt < MAX_DOWNLOAD_RETRIES:
                    wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)

        logger.error(f"Failed to download {description} after {MAX_DOWNLOAD_RETRIES} attempts")
        return False

    def _download_file(self, url: str, dest: Path) -> None:
        """Download a file with progress reporting."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(url, headers={"User-Agent": "Dictator/2.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self._report_progress(
                            f"Downloading... {downloaded / 1024 / 1024:.0f}MB / {total / 1024 / 1024:.0f}MB",
                            downloaded / total,
                        )

    def _extract_wake_word_model(self, dest: Path) -> bool:
        """Extract the wake word ONNX model from the openwakeword package."""
        try:
            import openwakeword

            oww_dir = Path(openwakeword.__file__).parent / "resources" / "models"
            source = oww_dir / WAKE_WORD_FILENAME

            if source.exists():
                import shutil
                shutil.copy2(source, dest)
                logger.info(f"Extracted wake word model to {dest}")
                return True

            for onnx_file in oww_dir.glob("*.onnx"):
                if "jarvis" in onnx_file.name.lower():
                    import shutil
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
