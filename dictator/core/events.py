"""Observer pattern: Thread-safe event bus with typed events and dead-letter handling."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(Enum):
    TEXT_UPDATED = auto()
    STATUS_CHANGED = auto()
    AGENT_RESPONSE = auto()
    STATE_CHANGED = auto()
    LOG_MESSAGE = auto()
    HEALTH_CHECK = auto()
    ERROR_OCCURRED = auto()
    MODEL_PROGRESS = auto()
    HOTKEY_TRIGGERED = auto()
    OVERLAY_TOGGLE = auto()
    SHUTDOWN_REQUESTED = auto()


@dataclass(frozen=True)
class Event:
    type: EventType
    data: Any = None
    source: str = ""


@dataclass
class DeadLetter:
    event: Event
    error: Exception
    subscriber: str


class EventBus:
    """Thread-safe publish/subscribe event bus with dead-letter queue for failed deliveries."""

    def __init__(self, max_dead_letters: int = 100):
        self._subscribers: dict[EventType, list[tuple[str, Callable[[Event], None]]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._dead_letters: list[DeadLetter] = []
        self._max_dead_letters = max_dead_letters

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None], name: str = "") -> Callable[[], None]:
        """Subscribe to an event type. Returns an unsubscribe function."""
        subscriber_name = name or callback.__qualname__

        with self._lock:
            self._subscribers[event_type].append((subscriber_name, callback))

        def unsubscribe() -> None:
            with self._lock:
                self._subscribers[event_type] = [
                    (n, cb) for n, cb in self._subscribers[event_type]
                    if cb is not callback
                ]

        return unsubscribe

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers. Failures are isolated per subscriber."""
        with self._lock:
            subscribers = list(self._subscribers.get(event.type, []))

        for subscriber_name, callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event delivery failed for '{subscriber_name}' on {event.type.name}: {e}")
                self._record_dead_letter(event, e, subscriber_name)

    def publish_async(self, event: Event) -> None:
        """Publish an event on a background thread (non-blocking)."""
        thread = threading.Thread(target=self.publish, args=(event,), daemon=True)
        thread.start()

    def get_dead_letters(self) -> list[DeadLetter]:
        """Retrieve failed event deliveries for diagnostics."""
        with self._lock:
            return list(self._dead_letters)

    def clear_dead_letters(self) -> None:
        with self._lock:
            self._dead_letters.clear()

    def _record_dead_letter(self, event: Event, error: Exception, subscriber: str) -> None:
        with self._lock:
            self._dead_letters.append(DeadLetter(event=event, error=error, subscriber=subscriber))
            if len(self._dead_letters) > self._max_dead_letters:
                self._dead_letters = self._dead_letters[-self._max_dead_letters:]
