"""Structured logging setup with rotating file handler and console output."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from dictator.utils.paths import get_logs_dir


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide logging with rotating file + console output."""
    log_dir = get_logs_dir()
    log_file = log_dir / "dictator.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
