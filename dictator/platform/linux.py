"""Linux platform implementations: xdotool, PulseAudio, notify-send, wmctrl.

Migrated from the original src/ modules with error isolation added.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import psutil

from dictator.platform.factory import PlatformFactory
from dictator.platform.interfaces import (
    AppLauncher,
    Notifier,
    TextInjector,
    VolumeController,
    WindowContext,
)

logger = logging.getLogger(__name__)


class LinuxTextInjector(TextInjector):
    """Injects text via xdotool."""

    def type_text(self, text: str) -> bool:
        try:
            subprocess.run(
                ["xdotool", "type", "--delay", "1", "--clearmodifiers", text],
                check=False,
                timeout=30,
            )
            return True
        except Exception as e:
            logger.error(f"xdotool type failed: {e}")
            return False

    def backspace(self, count: int) -> bool:
        if count <= 0:
            return True
        try:
            cmd = ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * count
            subprocess.run(cmd, check=False, timeout=10)
            return True
        except Exception as e:
            logger.error(f"xdotool backspace failed: {e}")
            return False


class LinuxVolumeController(VolumeController):
    """Controls volume via PulseAudio (pulsectl)."""

    def get_volume(self) -> float:
        try:
            import pulsectl
            with pulsectl.Pulse("dictator") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                return sink.volume.value_flat
        except Exception as e:
            logger.error(f"Failed to get volume: {e}")
            return 0.5

    def set_volume(self, level: float) -> bool:
        try:
            import pulsectl
            level = max(0.0, min(1.0, level))
            with pulsectl.Pulse("dictator") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                pulse.volume_set_all_chans(sink, level)
            return True
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False

    def toggle_mute(self) -> bool:
        try:
            import pulsectl
            with pulsectl.Pulse("dictator") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                pulse.mute(sink, not sink.mute)
            return True
        except Exception as e:
            logger.error(f"Failed to toggle mute: {e}")
            return False


class LinuxNotifier(Notifier):
    """Desktop notifications via notify-send."""

    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        try:
            subprocess.run(
                [
                    "notify-send",
                    "-u", urgency,
                    "-i", "audio-input-microphone",
                    title,
                    message,
                ],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            logger.debug("notify-send not available")
        except Exception as e:
            logger.debug(f"Notification failed: {e}")


class LinuxWindowContext(WindowContext):
    """Window context via xdotool."""

    TERMINAL_NAMES = (
        "gnome-terminal", "konsole", "alacritty", "kitty",
        "xterm", "terminator", "wezterm", "foot",
    )

    def get_active_window_title(self) -> str:
        try:
            win_id = self._get_window_id()
            if not win_id:
                return ""
            return subprocess.check_output(
                ["xdotool", "getwindowname", win_id], text=True, timeout=5
            ).strip()
        except Exception:
            return ""

    def get_active_window_pid(self) -> int | None:
        try:
            win_id = self._get_window_id()
            if not win_id:
                return None
            pid_str = subprocess.check_output(
                ["xdotool", "getwindowpid", win_id], text=True, timeout=5
            ).strip()
            return int(pid_str)
        except Exception:
            return None

    def get_shell_cwd(self, pid: int) -> str | None:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                if child.name() in ("bash", "zsh", "fish", "sh"):
                    return child.cwd()
            return parent.cwd()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def is_fullscreen(self) -> bool:
        try:
            result = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True, timeout=5
            )
            win_id = result.strip().split()[-1]
            state = subprocess.check_output(
                ["xprop", "-id", win_id, "_NET_WM_STATE"], text=True, timeout=5
            )
            return "_NET_WM_STATE_FULLSCREEN" in state
        except Exception:
            return False

    def _get_window_id(self) -> str | None:
        try:
            return subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, timeout=5
            ).strip()
        except Exception:
            return None


class LinuxAppLauncher(AppLauncher):
    """Launches Linux desktop applications."""

    APP_ALIASES: dict[str, str] = {
        "code": "code",
        "vscode": "code",
        "vs code": "code",
        "chrome": "google-chrome",
        "google chrome": "google-chrome",
        "terminal": "gnome-terminal",
        "spotify": "spotify",
        "firefox": "firefox",
        "files": "nautilus",
        "file manager": "nautilus",
    }

    def launch(self, app_name: str) -> str:
        if not app_name:
            return "No app name provided."

        app_key = app_name.lower().strip()
        cmd = self.APP_ALIASES.get(app_key, app_key)

        if not shutil.which(cmd):
            return f"App '{cmd}' not found in PATH."

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return f"Launched {cmd}"
        except Exception as e:
            return f"Failed to launch {cmd}: {e}"

    def get_known_apps(self) -> dict[str, str]:
        return dict(self.APP_ALIASES)


class LinuxFactory(PlatformFactory):
    """Creates Linux-specific platform implementations."""

    def create_injector(self) -> TextInjector:
        try:
            return LinuxTextInjector()
        except Exception as e:
            logger.error(f"Failed to create LinuxTextInjector: {e}")
            from dictator.platform.null import NullTextInjector
            return NullTextInjector()

    def create_volume_controller(self) -> VolumeController:
        try:
            return LinuxVolumeController()
        except Exception as e:
            logger.error(f"Failed to create LinuxVolumeController: {e}")
            from dictator.platform.null import NullVolumeController
            return NullVolumeController()

    def create_notifier(self) -> Notifier:
        try:
            return LinuxNotifier()
        except Exception as e:
            logger.error(f"Failed to create LinuxNotifier: {e}")
            from dictator.platform.null import NullNotifier
            return NullNotifier()

    def create_window_context(self) -> WindowContext:
        try:
            return LinuxWindowContext()
        except Exception as e:
            logger.error(f"Failed to create LinuxWindowContext: {e}")
            from dictator.platform.null import NullWindowContext
            return NullWindowContext()

    def create_app_launcher(self) -> AppLauncher:
        try:
            return LinuxAppLauncher()
        except Exception as e:
            logger.error(f"Failed to create LinuxAppLauncher: {e}")
            from dictator.platform.null import NullAppLauncher
            return NullAppLauncher()
