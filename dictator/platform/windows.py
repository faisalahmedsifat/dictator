"""Windows platform implementations: text injection, volume, notifications, window context, app launching.

Each method is wrapped in error isolation — failures are logged but never propagate.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import shutil
import subprocess
import time
from typing import Any

from dictator.platform.factory import PlatformFactory
from dictator.platform.interfaces import (
    AppLauncher,
    Notifier,
    TextInjector,
    VolumeController,
    WindowContext,
)

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32  # type: ignore[attr-defined]
kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]


class WindowsTextInjector(TextInjector):
    """Injects text via pynput keyboard controller with 1ms inter-key delay."""

    def __init__(self) -> None:
        from pynput.keyboard import Controller
        self._keyboard = Controller()

    def type_text(self, text: str) -> bool:
        try:
            for char in text:
                self._keyboard.type(char)
                time.sleep(0.001)
            return True
        except Exception as e:
            logger.error(f"Text injection failed: {e}")
            return False

    def backspace(self, count: int) -> bool:
        try:
            from pynput.keyboard import Key
            for _ in range(count):
                self._keyboard.press(Key.backspace)
                self._keyboard.release(Key.backspace)
                time.sleep(0.001)
            return True
        except Exception as e:
            logger.error(f"Backspace injection failed: {e}")
            return False


class WindowsVolumeController(VolumeController):
    """Controls Windows system volume via pycaw (Windows Core Audio API)."""

    def __init__(self) -> None:
        self._interface: Any = None
        self._initialize()

    def _initialize(self) -> None:
        try:
            from pycaw.pycaw import AudioUtilities

            device = AudioUtilities.GetSpeakers()
            # pycaw >= 2024: AudioDevice wraps endpoint volume directly
            if hasattr(device, "EndpointVolume"):
                self._interface = device.EndpointVolume
            else:
                # Legacy pycaw: use COM Activate
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import IAudioEndpointVolume
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._interface = interface.QueryInterface(IAudioEndpointVolume)
        except Exception as e:
            logger.warning(f"Failed to initialize volume control: {e}")
            self._interface = None

    def get_volume(self) -> float:
        if not self._interface:
            return 0.5
        try:
            return self._interface.GetMasterVolumeLevelScalar()
        except Exception as e:
            logger.error(f"Failed to get volume: {e}")
            return 0.5

    def set_volume(self, level: float) -> bool:
        if not self._interface:
            return False
        try:
            level = max(0.0, min(1.0, level))
            self._interface.SetMasterVolumeLevelScalar(level, None)
            return True
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False

    def toggle_mute(self) -> bool:
        if not self._interface:
            return False
        try:
            current = self._interface.GetMute()
            self._interface.SetMute(not current, None)
            return True
        except Exception as e:
            logger.error(f"Failed to toggle mute: {e}")
            return False


class WindowsNotifier(Notifier):
    """Windows toast notifications via winotify."""

    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        try:
            from winotify import Notification, audio

            toast = Notification(
                app_id="Dictator",
                title=title,
                msg=message,
                duration="short" if urgency != "critical" else "long",
            )
            toast.set_audio(audio.Silent, loop=False)
            toast.show()
        except Exception as e:
            logger.debug(f"Toast notification failed: {e}")


class WindowsWindowContext(WindowContext):
    """Windows window context using Win32 API via ctypes."""

    def get_active_window_title(self) -> str:
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception as e:
            logger.debug(f"Failed to get window title: {e}")
            return ""

    def get_active_window_pid(self) -> int | None:
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value if pid.value else None
        except Exception as e:
            logger.debug(f"Failed to get window PID: {e}")
            return None

    def get_shell_cwd(self, pid: int) -> str | None:
        try:
            import psutil
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)

            shell_names = ("powershell.exe", "pwsh.exe", "cmd.exe", "bash.exe", "wsl.exe")
            for child in children:
                if child.name().lower() in shell_names:
                    return child.cwd()
            return proc.cwd()
        except Exception as e:
            logger.debug(f"Failed to get shell CWD: {e}")
            return None

    def is_fullscreen(self) -> bool:
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            from ctypes import Structure, sizeof

            class MONITORINFO(Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD),
                ]

            mi = MONITORINFO()
            mi.cbSize = sizeof(MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

            return (
                rect.left <= mi.rcMonitor.left
                and rect.top <= mi.rcMonitor.top
                and rect.right >= mi.rcMonitor.right
                and rect.bottom >= mi.rcMonitor.bottom
            )
        except Exception as e:
            logger.debug(f"Failed to check fullscreen: {e}")
            return False


class WindowsAppLauncher(AppLauncher):
    """Launches Windows applications with alias resolution."""

    APP_ALIASES: dict[str, str] = {
        "code": "code",
        "vscode": "code",
        "vs code": "code",
        "chrome": "chrome",
        "google chrome": "chrome",
        "terminal": "wt",
        "windows terminal": "wt",
        "cmd": "cmd",
        "powershell": "powershell",
        "spotify": "spotify",
        "firefox": "firefox",
        "files": "explorer",
        "file manager": "explorer",
        "explorer": "explorer",
        "notepad": "notepad",
        "calculator": "calc",
    }

    def launch(self, app_name: str) -> str:
        if not app_name:
            return "No app name provided."

        app_key = app_name.lower().strip()
        cmd = self.APP_ALIASES.get(app_key, app_key)

        # Verify the command exists before executing
        resolved = shutil.which(cmd)
        if not resolved:
            # Try with os.startfile for registered apps
            try:
                os.startfile(cmd)  # type: ignore[attr-defined]
                return f"Launched {cmd}"
            except OSError:
                return f"App '{app_name}' not found."

        try:
            subprocess.Popen(
                [resolved],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS,
            )
            return f"Launched {cmd}"
        except Exception as e:
            return f"Failed to launch {cmd}: {e}"

    def get_known_apps(self) -> dict[str, str]:
        return dict(self.APP_ALIASES)


class WindowsFactory(PlatformFactory):
    """Creates Windows-specific platform implementations with fallback on failure."""

    def create_injector(self) -> TextInjector:
        try:
            return WindowsTextInjector()
        except Exception as e:
            logger.error(f"Failed to create WindowsTextInjector: {e}")
            from dictator.platform.null import NullTextInjector
            return NullTextInjector()

    def create_volume_controller(self) -> VolumeController:
        try:
            return WindowsVolumeController()
        except Exception as e:
            logger.error(f"Failed to create WindowsVolumeController: {e}")
            from dictator.platform.null import NullVolumeController
            return NullVolumeController()

    def create_notifier(self) -> Notifier:
        try:
            return WindowsNotifier()
        except Exception as e:
            logger.error(f"Failed to create WindowsNotifier: {e}")
            from dictator.platform.null import NullNotifier
            return NullNotifier()

    def create_window_context(self) -> WindowContext:
        try:
            return WindowsWindowContext()
        except Exception as e:
            logger.error(f"Failed to create WindowsWindowContext: {e}")
            from dictator.platform.null import NullWindowContext
            return NullWindowContext()

    def create_app_launcher(self) -> AppLauncher:
        try:
            return WindowsAppLauncher()
        except Exception as e:
            logger.error(f"Failed to create WindowsAppLauncher: {e}")
            from dictator.platform.null import NullAppLauncher
            return NullAppLauncher()
