"""Decorator pattern: SafeTextInjector wrapping any TextInjector with safety checks."""

from __future__ import annotations

import logging

from dictator.platform.interfaces import TextInjector, WindowContext
from dictator.utils.text import cap_length, sanitize_for_injection

logger = logging.getLogger(__name__)

MAX_INJECTION_LENGTH = 5000
MAX_BACKSPACE_COUNT = 500
KEYSTROKE_DELAY_MS = 1


class SafeTextInjector(TextInjector):
    """Adds safety guarantees around any TextInjector implementation.

    Safety checks:
    - Caps text length at MAX_INJECTION_LENGTH characters
    - Sanitizes control characters
    - Verifies active window hasn't changed mid-injection
    - Caps backspace count to MAX_BACKSPACE_COUNT
    """

    def __init__(self, inner: TextInjector, window_context: WindowContext):
        self._inner = inner
        self._window_ctx = window_context
        self._total_injected = 0

    @property
    def total_injected(self) -> int:
        """Track how many characters have been injected this session."""
        return self._total_injected

    def reset_tracking(self) -> None:
        """Reset the injection tracking counter."""
        self._total_injected = 0

    def type_text(self, text: str) -> bool:
        """Safely inject text with length cap, sanitization, and window validation."""
        if not text:
            return True

        window_before = self._window_ctx.get_active_window_title()

        text = sanitize_for_injection(text)
        text = cap_length(text, MAX_INJECTION_LENGTH)

        if not text:
            return True

        success = self._inner.type_text(text)

        if success:
            self._total_injected += len(text)

        window_after = self._window_ctx.get_active_window_title()
        if window_before and window_after and window_before != window_after:
            logger.warning(
                f"Window changed during injection: '{window_before}' -> '{window_after}'"
            )

        return success

    def backspace(self, count: int) -> bool:
        """Safely send backspaces with count cap."""
        if count <= 0:
            return True

        count = min(count, MAX_BACKSPACE_COUNT)
        count = min(count, self._total_injected)

        if count <= 0:
            return True

        success = self._inner.backspace(count)
        if success:
            self._total_injected = max(0, self._total_injected - count)
        return success
