"""System tray integration using pystray. Provides state-colored icon and context menu."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

from dictator.core.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)


class SystemTray:
    """System tray icon with state-aware coloring and context menu.

    Tray icon colors:
    - Gray: idle
    - Green: actively listening/dictating
    - Blue: agent mode
    - Red: error state
    """

    def __init__(
        self,
        event_bus: EventBus,
        on_toggle_dictation: Callable[[], None],
        on_toggle_agent: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._event_bus = event_bus
        self._on_toggle_dictation = on_toggle_dictation
        self._on_toggle_agent = on_toggle_agent
        self._on_quit = on_quit
        self._icon = None
        self._current_status = "idle"
        self._thread: threading.Thread | None = None

        self._event_bus.subscribe(EventType.STATUS_CHANGED, self._on_status_changed)

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        if sys.platform != "win32":
            logger.debug("System tray only supported on Windows")
            return

        self._thread = threading.Thread(target=self._run, daemon=True, name="SystemTray")
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw

            icon_image = self._create_icon("gray")
            menu = pystray.Menu(
                pystray.MenuItem("Start Dictation (F9)", lambda: self._on_toggle_dictation()),
                pystray.MenuItem("Start Agent (F10)", lambda: self._on_toggle_agent()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda: self._on_quit()),
            )

            self._icon = pystray.Icon("Dictator", icon_image, "Dictator - Voice Assistant", menu)
            self._icon.run()
        except ImportError:
            logger.warning("pystray or Pillow not installed, tray icon disabled")
        except Exception as e:
            logger.error(f"System tray failed: {e}")

    def _on_status_changed(self, event: Event) -> None:
        self._current_status = event.data or "idle"
        self._update_icon()

    def _update_icon(self) -> None:
        if not self._icon:
            return
        color_map = {
            "idle": "gray",
            "listening": "#00ff00",
            "processing": "yellow",
            "agent": "#00ccff",
            "error": "#ff4444",
        }
        color = color_map.get(self._current_status, "gray")
        try:
            self._icon.icon = self._create_icon(color)
        except Exception:
            pass

    @staticmethod
    def _create_icon(color: str):
        """Create a simple colored circle icon."""
        from PIL import Image, ImageDraw

        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, size - 8, size - 8], fill=color)
        return image
