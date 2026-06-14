from __future__ import annotations

import subprocess


def type_text(text: str) -> None:
    """Inject text into the active window via xdotool."""
    subprocess.run(
        ["xdotool", "type", "--delay", "1", "--clearmodifiers", text],
        check=False,
    )


def backspace(n: int) -> None:
    """Send n backspace key presses via xdotool."""
    if n <= 0:
        return
    cmd = ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * n
    subprocess.run(cmd, check=False)
