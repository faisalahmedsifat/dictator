"""Resource lifecycle management: graceful shutdown, cleanup registry, signal handling."""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Ensures all resources are cleaned up on shutdown, even on unexpected exit.

    Cleanups are executed in LIFO order (last registered = first cleaned up).
    Each cleanup is isolated — a failure in one does not prevent others from running.
    """

    def __init__(self):
        self._cleanups: list[tuple[str, Callable[[], None]]] = []
        self._running = False
        self._shutdown_lock = threading.Lock()
        self._shutdown_complete = threading.Event()

    def start(self) -> None:
        """Activate lifecycle management. Register signal handlers and atexit."""
        if self._running:
            return
        self._running = True

        atexit.register(self._shutdown)

        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.debug("LifecycleManager started")

    def register_cleanup(self, name: str, cleanup: Callable[[], None]) -> None:
        """Register a cleanup function. Called in LIFO order on shutdown."""
        self._cleanups.append((name, cleanup))
        logger.debug(f"Registered cleanup: {name}")

    def unregister_cleanup(self, name: str) -> None:
        """Remove a cleanup by name."""
        self._cleanups = [(n, c) for n, c in self._cleanups if n != name]

    def request_shutdown(self) -> None:
        """Programmatically request a graceful shutdown."""
        self._shutdown()

    def is_shutting_down(self) -> bool:
        return self._shutdown_complete.is_set() or not self._running

    def _signal_handler(self, signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, shutting down...")
        self._shutdown()
        sys.exit(0)

    def _shutdown(self) -> None:
        with self._shutdown_lock:
            if not self._running:
                return
            self._running = False

        logger.info("Shutting down: running cleanup handlers...")

        for name, cleanup in reversed(self._cleanups):
            try:
                logger.debug(f"Running cleanup: {name}")
                cleanup()
            except Exception as e:
                logger.error(f"Cleanup '{name}' failed: {e}")

        self._shutdown_complete.set()
        logger.info("Shutdown complete.")
