"""PresenceManager: Detects when Dictator should suppress itself (fullscreen, gaming, DND)."""

from __future__ import annotations

import logging
import threading
import time

from dictator.core.config import PresenceConfig
from dictator.platform.interfaces import WindowContext

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 2.0  # seconds between presence checks


class PresenceManager:
    """Monitors user context to determine if Dictator should be suppressed.

    Suppression triggers:
    - Fullscreen application detected (games, presentations, video calls)
    - Windows Focus Assist / DND enabled
    - User manually enabled gaming mode
    """

    def __init__(self, config: PresenceConfig, window_context: WindowContext):
        self._config = config
        self._window_ctx = window_context
        self._suppressed = False
        self._manual_gaming_mode = False
        self._check_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_suppressed(self) -> bool:
        """Returns True if Dictator should go silent."""
        return self._suppressed

    def set_gaming_mode(self, enabled: bool) -> None:
        """Manually enable/disable gaming mode."""
        self._manual_gaming_mode = enabled
        self._update_state()

    def start(self) -> None:
        """Start periodic presence checking."""
        self._check_thread = threading.Thread(
            target=self._check_loop, daemon=True, name="PresenceManager"
        )
        self._check_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _check_loop(self) -> None:
        while not self._stop_event.is_set():
            self._update_state()
            self._stop_event.wait(CHECK_INTERVAL)

    def _update_state(self) -> None:
        was_suppressed = self._suppressed

        self._suppressed = (
            self._manual_gaming_mode
            or (self._config.respect_fullscreen and self._is_fullscreen())
            or (self._config.respect_dnd and self._is_dnd_enabled())
        )

        if self._suppressed != was_suppressed:
            state = "suppressed" if self._suppressed else "active"
            logger.info(f"Presence state changed: {state}")

    def _is_fullscreen(self) -> bool:
        try:
            return self._window_ctx.is_fullscreen()
        except Exception:
            return False

    def _is_dnd_enabled(self) -> bool:
        """Check if Windows Focus Assist / DND is enabled."""
        try:
            import sys
            if sys.platform != "win32":
                return False
            # Windows Focus Assist detection via registry (best-effort)
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings",
            )
            value, _ = winreg.QueryValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_ENABLED")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return False
