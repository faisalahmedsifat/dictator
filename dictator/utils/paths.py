"""Cross-platform application data directory resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Get the application data directory, creating it if needed.

    Windows: %APPDATA%/Dictator
    Linux:   ~/.local/share/dictator
    macOS:   ~/Library/Application Support/Dictator
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        app_dir = base / "Dictator"
    elif sys.platform == "darwin":
        app_dir = Path.home() / "Library" / "Application Support" / "Dictator"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        app_dir = base / "dictator"

    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_models_dir() -> Path:
    """Get the models directory."""
    models_dir = get_app_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_logs_dir() -> Path:
    """Get the logs directory."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = get_app_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
