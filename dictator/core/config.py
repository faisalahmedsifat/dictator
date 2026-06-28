"""Application configuration with validation, safe defaults, and schema versioning."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from dictator.utils.paths import get_config_dir

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
CONFIG_FILENAME = "config.json"
KEYBINDINGS_FILENAME = "keybindings.json"


@dataclass
class OverlayConfig:
    auto_hide_seconds: float = 3.0
    position: str = "bottom_center"
    click_through: bool = True
    opacity_active: float = 0.85
    opacity_fading: float = 0.3
    respect_fullscreen: bool = True
    width: int = 900
    font_size: int = 18


@dataclass
class AudioConfig:
    device: str | None = None
    sample_rate: int = 16000
    buffer_cap_seconds: int = 30
    reconnect_interval: float = 10.0


@dataclass
class AgentConfig:
    model_name: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    max_tokens: int = 512
    timeout_seconds: float = 10.0
    enabled: bool = True


@dataclass
class WhisperConfig:
    model_size: str = "base.en"
    language: str = "en"
    partial_typing: bool = True


@dataclass
class PresenceConfig:
    respect_fullscreen: bool = True
    respect_dnd: bool = True
    gaming_mode_auto: bool = True


@dataclass
class KeybindingsConfig:
    schema_version: int = 1
    toggle_dictation: str = "F9"
    toggle_agent: str = "F10"
    toggle_overlay: str = "ctrl+shift+space"
    toggle_log: str = "ctrl+alt+l"
    hide_all: str = "ctrl+shift+escape"
    push_to_talk: str = "ctrl+`"
    cancel_current: str = "escape"


@dataclass
class AppConfig:
    schema_version: int = SCHEMA_VERSION
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    keybindings: KeybindingsConfig = field(default_factory=KeybindingsConfig)
    run_at_startup: bool = False
    first_run_complete: bool = False
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> AppConfig:
        """Load config from disk, falling back to safe defaults on any error."""
        config_path = get_config_dir() / CONFIG_FILENAME
        try:
            if config_path.exists():
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                return cls._from_dict(raw)
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
        return cls()

    def save(self) -> None:
        """Persist config to disk."""
        config_path = get_config_dir() / CONFIG_FILENAME
        try:
            config_path.write_text(
                json.dumps(self._to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Reconstruct config from dict with forward compatibility."""
        version = data.get("schema_version", 0)
        if version > SCHEMA_VERSION:
            logger.warning(f"Config schema {version} > supported {SCHEMA_VERSION}, using compatible fields only")

        config = cls()

        # Overlay
        if "overlay" in data and isinstance(data["overlay"], dict):
            for k, v in data["overlay"].items():
                if hasattr(config.overlay, k):
                    setattr(config.overlay, k, v)

        # Audio
        if "audio" in data and isinstance(data["audio"], dict):
            for k, v in data["audio"].items():
                if hasattr(config.audio, k):
                    setattr(config.audio, k, v)

        # Agent
        if "agent" in data and isinstance(data["agent"], dict):
            for k, v in data["agent"].items():
                if hasattr(config.agent, k):
                    setattr(config.agent, k, v)

        # Whisper
        if "whisper" in data and isinstance(data["whisper"], dict):
            for k, v in data["whisper"].items():
                if hasattr(config.whisper, k):
                    setattr(config.whisper, k, v)

        # Presence
        if "presence" in data and isinstance(data["presence"], dict):
            for k, v in data["presence"].items():
                if hasattr(config.presence, k):
                    setattr(config.presence, k, v)

        # Keybindings
        if "keybindings" in data and isinstance(data["keybindings"], dict):
            for k, v in data["keybindings"].items():
                if hasattr(config.keybindings, k):
                    setattr(config.keybindings, k, v)

        # Top-level scalars
        for key in ("run_at_startup", "first_run_complete", "log_level"):
            if key in data:
                setattr(config, key, data[key])

        config.schema_version = SCHEMA_VERSION
        return config

    def validate(self) -> list[str]:
        """Validate config values, returning list of issues (empty = valid)."""
        issues: list[str] = []

        if self.overlay.auto_hide_seconds < 0:
            issues.append("overlay.auto_hide_seconds must be >= 0")
        if not (0.0 <= self.overlay.opacity_active <= 1.0):
            issues.append("overlay.opacity_active must be 0.0-1.0")
        if self.audio.buffer_cap_seconds < 5:
            issues.append("audio.buffer_cap_seconds must be >= 5")
        if self.agent.timeout_seconds < 1:
            issues.append("agent.timeout_seconds must be >= 1")
        if self.whisper.model_size not in ("tiny.en", "base.en", "small.en", "medium.en", "large"):
            issues.append(f"whisper.model_size '{self.whisper.model_size}' is not a known size")

        return issues
