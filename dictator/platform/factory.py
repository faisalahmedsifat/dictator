"""Abstract Factory pattern: Creates platform-specific strategy implementations.

Falls back to Null Object implementations if platform initialization fails,
ensuring the application always boots regardless of environment issues.
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod

from dictator.platform.interfaces import (
    AppLauncher,
    Notifier,
    TextInjector,
    VolumeController,
    WindowContext,
)
from dictator.platform.null import (
    NullAppLauncher,
    NullNotifier,
    NullTextInjector,
    NullVolumeController,
    NullWindowContext,
)

logger = logging.getLogger(__name__)


class PlatformFactory(ABC):
    """Abstract factory for creating all platform-specific components."""

    @abstractmethod
    def create_injector(self) -> TextInjector:
        """Create a text injector for the current platform."""

    @abstractmethod
    def create_volume_controller(self) -> VolumeController:
        """Create a volume controller for the current platform."""

    @abstractmethod
    def create_notifier(self) -> Notifier:
        """Create a notification sender for the current platform."""

    @abstractmethod
    def create_window_context(self) -> WindowContext:
        """Create a window context provider for the current platform."""

    @abstractmethod
    def create_app_launcher(self) -> AppLauncher:
        """Create an application launcher for the current platform."""


class NullPlatformFactory(PlatformFactory):
    """Fallback factory returning Null Object implementations for everything."""

    def create_injector(self) -> TextInjector:
        return NullTextInjector()

    def create_volume_controller(self) -> VolumeController:
        return NullVolumeController()

    def create_notifier(self) -> Notifier:
        return NullNotifier()

    def create_window_context(self) -> WindowContext:
        return NullWindowContext()

    def create_app_launcher(self) -> AppLauncher:
        return NullAppLauncher()


def get_platform_factory() -> PlatformFactory:
    """Detect the platform and return the appropriate factory.

    Falls back to NullPlatformFactory if the platform module fails to load.
    """
    if sys.platform == "win32":
        try:
            from dictator.platform.windows import WindowsFactory
            return WindowsFactory()
        except Exception as e:
            logger.error(f"Failed to initialize Windows platform: {e}")
            return NullPlatformFactory()
    elif sys.platform == "linux":
        try:
            from dictator.platform.linux import LinuxFactory
            return LinuxFactory()
        except Exception as e:
            logger.error(f"Failed to initialize Linux platform: {e}")
            return NullPlatformFactory()
    else:
        logger.warning(f"Unsupported platform: {sys.platform}, using null implementations")
        return NullPlatformFactory()
