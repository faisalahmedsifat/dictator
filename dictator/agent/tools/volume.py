"""SystemVolumeCommand: Controls system volume with bounded inputs."""

from __future__ import annotations

import logging
from typing import Any

from dictator.agent.commands import Command
from dictator.platform.interfaces import VolumeController

logger = logging.getLogger(__name__)


class SystemVolumeCommand(Command):
    def __init__(self, volume_controller: VolumeController):
        self._volume = volume_controller

    @property
    def name(self) -> str:
        return "system_control"

    @property
    def description(self) -> str:
        return "Control system volume (up/down/mute/set)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "setting": {"type": "string", "enum": ["volume"]},
                "action": {"type": "string", "enum": ["up", "down", "mute", "set"]},
                "value": {
                    "type": "integer",
                    "description": "Percentage value (0-100)",
                },
            },
            "required": ["setting", "action"],
        }

    def validate(self, args: dict[str, Any]) -> str | None:
        base = super().validate(args)
        if base:
            return base

        value = args.get("value")
        if value is not None and not (0 <= value <= 100):
            return "Value must be between 0 and 100"
        return None

    def execute(self, args: dict[str, Any]) -> str:
        setting = args.get("setting")
        action = args.get("action")
        value = args.get("value", 10)

        if setting != "volume":
            return f"Setting '{setting}' not supported."

        current = self._volume.get_volume()

        if action == "up":
            new_level = min(1.0, current + (value / 100))
            self._volume.set_volume(new_level)
            return f"Volume set to {int(new_level * 100)}%"
        elif action == "down":
            new_level = max(0.0, current - (value / 100))
            self._volume.set_volume(new_level)
            return f"Volume set to {int(new_level * 100)}%"
        elif action == "mute":
            self._volume.toggle_mute()
            return "Mute toggled."
        elif action == "set":
            new_level = max(0.0, min(1.0, value / 100))
            self._volume.set_volume(new_level)
            return f"Volume set to {int(new_level * 100)}%"
        else:
            return f"Unknown action: {action}"
