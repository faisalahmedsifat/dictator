"""Text utilities: cleaning, sanitization, and safe text processing."""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """Remove repeated consecutive words from transcribed text."""
    return re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)


def sanitize_for_injection(text: str) -> str:
    """Strip control characters that could be dangerous when injected as keystrokes.

    Preserves: printable characters, spaces, newlines, tabs.
    Removes: null bytes, escape sequences, bell, backspace, etc.
    """
    allowed = set("\t\n\r")
    return "".join(
        ch for ch in text
        if ch.isprintable() or ch in allowed
    )


def cap_length(text: str, max_length: int = 5000) -> str:
    """Cap text to a maximum length to prevent runaway injection."""
    if len(text) <= max_length:
        return text
    return text[:max_length]
