"""AppLaunchCommand: Launches applications with platform-aware alias resolution."""

from __future__ import annotations

import logging
from typing import Any

from dictator.agent.commands import Command
from dictator.platform.interfaces import AppLauncher

logger = logging.getLogger(__name__)


class AppLaunchCommand(Command):
    def __init__(self, launcher: AppLauncher):
        self._launcher = launcher

    @property
    def name(self) -> str:
        return "app_launcher"

    @property
    def description(self) -> str:
        return "Launch a desktop application"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application (e.g. code, spotify, terminal)",
                },
            },
            "required": ["app_name"],
        }

    def execute(self, args: dict[str, Any]) -> str:
        app_name = args.get("app_name", "").strip()
        if not app_name:
            return "No app name provided."
        return self._launcher.launch(app_name)
