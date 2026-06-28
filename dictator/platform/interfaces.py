"""Strategy pattern: Abstract interfaces for all platform-specific operations.

Each interface defines an error contract:
- Methods MUST NOT raise exceptions to callers (all errors are handled internally)
- Methods return a success indicator or safe default on failure
- Implementations log errors but never propagate them
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TextInjector(ABC):
    """Injects text into the currently focused window as if typed by the user.

    Error contract: type_text/backspace must never raise. On failure, they silently
    skip the operation and log a warning.
    """

    @abstractmethod
    def type_text(self, text: str) -> bool:
        """Type text into the active window. Returns True on success."""

    @abstractmethod
    def backspace(self, count: int) -> bool:
        """Send backspace keystrokes. Returns True on success."""


class VolumeController(ABC):
    """Controls system audio volume.

    Error contract: returns safe defaults on failure (0.5 for get_volume).
    """

    @abstractmethod
    def get_volume(self) -> float:
        """Get current volume as 0.0-1.0. Returns 0.5 on failure."""

    @abstractmethod
    def set_volume(self, level: float) -> bool:
        """Set volume (0.0-1.0). Returns True on success."""

    @abstractmethod
    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns True on success."""


class Notifier(ABC):
    """Sends desktop notifications.

    Error contract: notify must never raise. Failures are silently logged.
    """

    @abstractmethod
    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        """Show a desktop notification. urgency: 'low', 'normal', 'critical'."""


class WindowContext(ABC):
    """Provides information about the currently active window.

    Error contract: returns empty string / None on failure, never raises.
    """

    @abstractmethod
    def get_active_window_title(self) -> str:
        """Get the title of the foreground window. Returns '' on failure."""

    @abstractmethod
    def get_active_window_pid(self) -> int | None:
        """Get the PID of the foreground window's process. Returns None on failure."""

    @abstractmethod
    def get_shell_cwd(self, pid: int) -> str | None:
        """Infer the working directory of a shell process. Returns None on failure."""

    @abstractmethod
    def is_fullscreen(self) -> bool:
        """Check if the foreground window is fullscreen."""


class AppLauncher(ABC):
    """Launches desktop applications.

    Error contract: launch returns a human-readable status message, never raises.
    """

    @abstractmethod
    def launch(self, app_name: str) -> str:
        """Launch an application by name. Returns status message."""

    @abstractmethod
    def get_known_apps(self) -> dict[str, str]:
        """Return mapping of friendly names to executable paths/commands."""
