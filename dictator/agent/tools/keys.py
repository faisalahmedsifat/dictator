"""SimulateKeysCommand: Simulates keyboard input with dangerous combo blocking."""

from __future__ import annotations

import logging
import time
from typing import Any

from dictator.agent.commands import Command

logger = logging.getLogger(__name__)

BLOCKED_COMBOS = frozenset({
    "alt+f4",
    "ctrl+alt+del",
    "ctrl+alt+delete",
    "win+l",
    "super+l",
    "ctrl+shift+del",
    "ctrl+shift+delete",
})


class SimulateKeysCommand(Command):
    @property
    def name(self) -> str:
        return "simulate_keys"

    @property
    def description(self) -> str:
        return "Simulate keyboard key presses or text typing"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "string",
                    "description": "Key combo (e.g. 'ctrl+c', 'alt+enter') or text to type",
                },
            },
            "required": ["keys"],
        }

    def validate(self, args: dict[str, Any]) -> str | None:
        base = super().validate(args)
        if base:
            return base

        keys_str = args.get("keys", "").lower().strip()
        if keys_str in BLOCKED_COMBOS:
            return f"Blocked dangerous key combination: {keys_str}"
        return None

    def execute(self, args: dict[str, Any]) -> str:
        from pynput.keyboard import Controller, Key

        keys_str = args.get("keys", "").strip()
        if not keys_str:
            return "No keys provided."

        keyboard = Controller()
        normalized = keys_str.lower().replace("'", "").replace('"', "").strip()

        try:
            if "+" in normalized:
                parts = [k.strip() for k in normalized.split("+")]
                py_keys = []
                for k in parts:
                    if hasattr(Key, k):
                        py_keys.append(getattr(Key, k))
                    else:
                        py_keys.append(k)

                for k in py_keys:
                    keyboard.press(k)
                time.sleep(0.05)
                for k in reversed(py_keys):
                    keyboard.release(k)

                return f"Pressed combo: {keys_str}"
            else:
                if hasattr(Key, normalized):
                    k = getattr(Key, normalized)
                    keyboard.press(k)
                    keyboard.release(k)
                    return f"Pressed key: {keys_str}"
                else:
                    keyboard.type(keys_str)
                    return f"Typed: {keys_str}"
        except Exception as e:
            return f"Failed to simulate keys: {e}"
