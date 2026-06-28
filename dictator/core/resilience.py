"""Circuit Breaker pattern: Resilience primitives for fault-tolerant subsystems."""

from __future__ import annotations

import functools
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from enum import Enum, auto
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    """Wraps a callable to prevent repeated calls to a failing subsystem.

    - CLOSED: normal operation, calls pass through
    - OPEN: calls immediately return fallback (subsystem assumed down)
    - HALF_OPEN: one trial call allowed; success closes, failure reopens
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ):
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._excluded_exceptions = excluded_exceptions
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
            return self._state

    @property
    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    def call(self, func: Callable[..., T], *args: Any, fallback: Callable[[], T] | None = None, **kwargs: Any) -> T | None:
        """Execute func through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.debug(f"Circuit '{self._name}' is OPEN, returning fallback")
            return fallback() if fallback else None

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if isinstance(e, self._excluded_exceptions):
                raise
            self._on_failure(e)
            if fallback:
                return fallback()
            return None

    def record_success(self) -> None:
        """Manually record a success (for async patterns)."""
        self._on_success()

    def record_failure(self, error: Exception | None = None) -> None:
        """Manually record a failure."""
        self._on_failure(error or RuntimeError("manual failure"))

    def reset(self) -> None:
        """Force-reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit '{self._name}' recovered, closing")
            self._state = CircuitState.CLOSED

    def _on_failure(self, error: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self._name}' OPEN after {self._failure_count} failures. "
                    f"Last error: {error}"
                )
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit '{self._name}' half-open trial failed, reopening")

    def _should_attempt_reset(self) -> bool:
        return (time.time() - self._last_failure_time) >= self._reset_timeout


class RetryPolicy:
    """Configurable retry logic with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential: bool = True,
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exponential = exponential

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute with retries. Raises the last exception if all retries fail."""
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Retry {attempt + 1}/{self._max_retries} in {delay:.1f}s: {e}")
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]

    def _calculate_delay(self, attempt: int) -> float:
        if self._exponential:
            delay = self._base_delay * (2 ** attempt)
        else:
            delay = self._base_delay
        return min(delay, self._max_delay)


def timeout(seconds: float) -> Callable:
    """Decorator that enforces a maximum execution time on a function."""

    def decorator(func: Callable[..., T]) -> Callable[..., T | None]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | None:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future: Future[T] = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=seconds)
                except FutureTimeout:
                    logger.warning(f"{func.__qualname__} timed out after {seconds}s")
                    return None
                except Exception as e:
                    logger.error(f"{func.__qualname__} raised: {e}")
                    raise

        return wrapper

    return decorator


class HealthMonitor:
    """Periodically checks subsystem health and tracks status."""

    def __init__(self):
        self._checks: dict[str, Callable[[], bool]] = {}
        self._last_results: dict[str, bool] = {}
        self._lock = threading.Lock()

    def register_check(self, name: str, check: Callable[[], bool]) -> None:
        """Register a health check function that returns True if healthy."""
        with self._lock:
            self._checks[name] = check

    def unregister_check(self, name: str) -> None:
        with self._lock:
            self._checks.pop(name, None)

    def run_checks(self) -> dict[str, bool]:
        """Run all health checks and return results."""
        with self._lock:
            checks = dict(self._checks)

        results = {}
        for name, check in checks.items():
            try:
                results[name] = check()
            except Exception as e:
                logger.debug(f"Health check '{name}' raised: {e}")
                results[name] = False

        with self._lock:
            self._last_results = results
        return results

    @property
    def last_results(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._last_results)

    @property
    def is_healthy(self) -> bool:
        with self._lock:
            return all(self._last_results.values()) if self._last_results else True
