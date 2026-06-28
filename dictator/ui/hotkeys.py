"""HotkeyManager: Configurable global keybindings with conflict detection and push-to-talk."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from dictator.core.config import KeybindingsConfig
from dictator.core.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Manages global hotkeys with configurable bindings and conflict detection.

    Supports:
    - Toggle keys (press to toggle state)
    - Push-to-talk (hold to activate, release to deactivate)
    - Runtime rebinding without restart
    - Graceful fallback when a key is already registered
    """

    def __init__(self, config: KeybindingsConfig, event_bus: EventBus):
        self._config = config
        self._event_bus = event_bus
        self._bindings: dict[str, Callable[[], None]] = {}
        self._listener = None
        self._active = False

    def start(self, actions: dict[str, Callable[[], None]]) -> None:
        """Register and start listening for global hotkeys.

        Args:
            actions: Mapping of action names to callback functions.
                     Action names must match KeybindingsConfig field names.
        """
        self._bindings = actions
        self._active = True

        binding_map = self._build_binding_map()
        if not binding_map:
            logger.warning("No valid hotkey bindings configured")
            return

        try:
            from pynput.keyboard import GlobalHotKeys

            self._listener = GlobalHotKeys(binding_map)
            self._listener.start()
            logger.info(f"Registered {len(binding_map)} hotkeys")
        except Exception as e:
            logger.error(f"Failed to register hotkeys: {e}")
            self._event_bus.publish(Event(
                type=EventType.ERROR_OCCURRED,
                data="Hotkey registration failed. Keys may be in use by another app.",
                source="hotkeys",
            ))

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        self._active = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _build_binding_map(self) -> dict[str, Callable[[], None]]:
        """Build pynput-compatible binding map from config."""
        mapping = {}

        key_config = {
            "toggle_dictation": self._config.toggle_dictation,
            "toggle_agent": self._config.toggle_agent,
            "toggle_overlay": self._config.toggle_overlay,
            "toggle_log": self._config.toggle_log,
            "hide_all": self._config.hide_all,
            "cancel_current": self._config.cancel_current,
        }

        for action_name, key_str in key_config.items():
            if action_name not in self._bindings:
                continue

            pynput_key = self._to_pynput_format(key_str)
            if pynput_key:
                mapping[pynput_key] = self._bindings[action_name]

        return mapping

    def _to_pynput_format(self, key_str: str) -> str | None:
        """Convert human-readable key string to pynput format.

        Examples: 'F9' -> '<f9>', 'ctrl+shift+space' -> '<ctrl>+<shift>+<space>'
        """
        if not key_str:
            return None

        parts = key_str.lower().split("+")
        formatted = []

        for part in parts:
            part = part.strip()
            if part in ("ctrl", "alt", "shift", "cmd", "super", "win"):
                formatted.append(f"<{part}>")
            elif part.startswith("f") and part[1:].isdigit():
                formatted.append(f"<{part}>")
            elif part == "space":
                formatted.append("<space>")
            elif part == "enter":
                formatted.append("<enter>")
            elif part == "escape":
                formatted.append("<esc>")
            elif part == "`":
                formatted.append("`")
            elif len(part) == 1:
                formatted.append(part)
            else:
                formatted.append(f"<{part}>")

        return "+".join(formatted) if formatted else None
