"""OverlayUI: Thread-safe overlay manager subscribing to EventBus. Never steals focus."""

from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from typing import Any

from dictator.core.events import Event, EventBus, EventType
from dictator.ui.panels import LogPanel, MainPanel

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "idle": "gray",
    "listening": "#00ff00",
    "processing": "yellow",
    "agent": "#00ccff",
    "sleep": "#202020",
    "error": "#ff4444",
}


class OverlayUI:
    """Crash-isolated overlay UI running in its own daemon thread.

    - Subscribes to EventBus for updates
    - Auto-hides after inactivity
    - Never steals keyboard focus
    - If the Tkinter thread crashes, the main app continues
    """

    def __init__(self, event_bus: EventBus, auto_hide_seconds: float = 3.0):
        self._event_bus = event_bus
        self._auto_hide_seconds = auto_hide_seconds
        self._root: tk.Tk | None = None
        self._main_panel: MainPanel | None = None
        self._log_panel: LogPanel | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_activity: float = 0
        self._pending_calls: list[tuple[str, Any]] = []
        self._bg_color = "#202020"

    def start(self) -> None:
        """Start the overlay UI in a background daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="OverlayUI")
        self._thread.start()
        self._subscribe_events()

    def stop(self) -> None:
        """Stop the overlay."""
        self._stop_event.set()
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _subscribe_events(self) -> None:
        self._event_bus.subscribe(EventType.TEXT_UPDATED, self._on_text_updated)
        self._event_bus.subscribe(EventType.STATUS_CHANGED, self._on_status_changed)
        self._event_bus.subscribe(EventType.AGENT_RESPONSE, self._on_agent_response)
        self._event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        self._event_bus.subscribe(EventType.OVERLAY_TOGGLE, self._on_toggle)

    def _on_text_updated(self, event: Event) -> None:
        self._schedule("set_text", event.data)

    def _on_status_changed(self, event: Event) -> None:
        self._schedule("set_status", event.data)

    def _on_agent_response(self, event: Event) -> None:
        self._schedule("agent_response", event.data)

    def _on_log_message(self, event: Event) -> None:
        self._schedule("log", event.data)

    def _on_toggle(self, event: Event) -> None:
        action = event.data or "toggle_main"
        self._schedule(action, None)

    def _schedule(self, action: str, data: Any) -> None:
        """Thread-safe: schedule a UI update on the Tkinter thread."""
        self._pending_calls.append((action, data))
        self._last_activity = time.time()

    def _run(self) -> None:
        """Main UI thread loop."""
        try:
            self._root = tk.Tk()
            self._root.withdraw()

            self._main_panel = MainPanel(self._root, self._bg_color)
            self._log_panel = LogPanel(self._root, self._bg_color)

            self._poll()
            self._root.mainloop()
        except Exception as e:
            logger.error(f"Overlay UI thread crashed: {e}")

    def _poll(self) -> None:
        """Process pending UI calls and handle auto-hide."""
        try:
            while self._pending_calls:
                action, data = self._pending_calls.pop(0)
                self._dispatch(action, data)

            # Auto-hide logic
            if self._auto_hide_seconds > 0 and self._main_panel and self._main_panel.visible:
                elapsed = time.time() - self._last_activity
                if elapsed > self._auto_hide_seconds and self._last_activity > 0:
                    self._main_panel.hide()

        except Exception as e:
            logger.debug(f"Overlay poll error: {e}")

        if not self._stop_event.is_set():
            self._root.after(50, self._poll)  # type: ignore[union-attr]

    def _dispatch(self, action: str, data: Any) -> None:
        if action == "set_text" and self._main_panel:
            self._main_panel.show()
            self._main_panel.set_text(data or "", "white")
        elif action == "set_status" and self._main_panel:
            color = STATUS_COLORS.get(data, "gray")
            self._main_panel.set_status(color)
        elif action == "agent_response" and self._main_panel:
            self._main_panel.show()
            self._main_panel.set_text(data or "", "#00ccff")
            if self._log_panel:
                self._log_panel.write(f"Agent: {data}")
        elif action == "log" and self._log_panel:
            self._log_panel.write(data or "")
        elif action == "toggle_main" and self._main_panel:
            self._main_panel.toggle()
        elif action == "toggle_log" and self._log_panel:
            self._log_panel.toggle()
        elif action == "hide_all":
            if self._main_panel:
                self._main_panel.hide()
            if self._log_panel:
                self._log_panel.hide()
