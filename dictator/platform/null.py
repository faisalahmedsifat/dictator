"""Null Object pattern: Safe no-op implementations for all platform interfaces.

Used when a platform capability is unavailable or initialization fails,
ensuring the application always boots without None-checks everywhere.
"""

from __future__ import annotations

import logging

from dictator.platform.interfaces import (
    AppLauncher,
    Notifier,
    TextInjector,
    VolumeController,
    WindowContext,
)

logger = logging.getLogger(__name__)


class NullTextInjector(TextInjector):
    """No-op text injector — logs but does nothing."""

    def type_text(self, text: str) -> bool:
        logger.debug(f"[NullInjector] Would type: {text[:50]}...")
        return False

    def backspace(self, count: int) -> bool:
        logger.debug(f"[NullInjector] Would backspace: {count}")
        return False


class NullVolumeController(VolumeController):
    """No-op volume controller — returns neutral values."""

    def get_volume(self) -> float:
        return 0.5

    def set_volume(self, level: float) -> bool:
        logger.debug(f"[NullVolume] Would set volume to {level:.0%}")
        return False

    def toggle_mute(self) -> bool:
        logger.debug("[NullVolume] Would toggle mute")
        return False


class NullNotifier(Notifier):
    """No-op notifier — logs instead of showing notifications."""

    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        logger.info(f"[Notification] {title}: {message}")


class NullWindowContext(WindowContext):
    """No-op window context — returns empty/None for all queries."""

    def get_active_window_title(self) -> str:
        return ""

    def get_active_window_pid(self) -> int | None:
        return None

    def get_shell_cwd(self, pid: int) -> str | None:
        return None

    def is_fullscreen(self) -> bool:
        return False


class NullAppLauncher(AppLauncher):
    """No-op launcher — reports that launching is not available."""

    def launch(self, app_name: str) -> str:
        return f"App launching unavailable (would launch: {app_name})"

    def get_known_apps(self) -> dict[str, str]:
        return {}
