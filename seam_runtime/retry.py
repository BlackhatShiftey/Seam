from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import sqlite3
import time
from typing import Any, Callable, TypeVar

LOGGER = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _compute_delay(
    attempt: int,
    backoff: str,
    base_delay: float,
    max_delay: float,
) -> float:
    if backoff == "exponential":
        delay = base_delay * (2 ** (attempt - 1))
    elif backoff == "linear":
        delay = base_delay * attempt
    elif backoff == "fixed":
        delay = base_delay
    else:
        raise ValueError(f"unknown backoff strategy: {backoff!r}")
    return min(delay, max_delay)


def retry(
    max_attempts: int = 3,
    backoff: str = "exponential",
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    exceptions: tuple[type[BaseException], ...] = (
        sqlite3.OperationalError,
        ConnectionError,
        TimeoutError,
    ),
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    exception_check: Callable[[BaseException], bool] | None = None,
) -> Callable[[F], F]:
    """Decorator that retries a function on transient failures.

    Args:
        max_attempts: Maximum number of attempts before re-raising.
        backoff: Delay strategy — ``'exponential'``, ``'linear'``, or ``'fixed'``.
        base_delay: Initial delay in seconds.
        max_delay: Upper bound on delay in seconds.
        exceptions: Tuple of exception types to catch and retry.
        on_retry: Optional callback invoked before each retry sleep.
            Receives ``(attempt_number, exception, delay_seconds)``.
        exception_check: Optional predicate to filter caught exceptions.
            When provided, only exceptions for which this returns ``True``
            are retried; others propagate immediately.

    Returns:
        A decorator that wraps the target function with retry logic.
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        if exception_check is not None and not exception_check(exc):
                            raise
                        if attempt == max_attempts:
                            raise
                        delay = _compute_delay(attempt, backoff, base_delay, max_delay)
                        LOGGER.warning(
                            "retry %d/%d for %s: %s (delay=%.3fs)",
                            attempt,
                            max_attempts,
                            func.__qualname__,
                            type(exc).__name__,
                            delay,
                        )
                        if on_retry is not None:
                            on_retry(attempt, exc, delay)
                        await asyncio.sleep(delay)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if exception_check is not None and not exception_check(exc):
                        raise
                    if attempt == max_attempts:
                        raise
                    delay = _compute_delay(attempt, backoff, base_delay, max_delay)
                    LOGGER.warning(
                        "retry %d/%d for %s: %s (delay=%.3fs)",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        type(exc).__name__,
                        delay,
                    )
                    if on_retry is not None:
                        on_retry(attempt, exc, delay)
                    time.sleep(delay)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

_DB_TRANSIENT_MESSAGES: tuple[str, ...] = ("database is locked", "cannot commit")


def _is_transient_db_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and any(
        msg in str(exc).lower() for msg in _DB_TRANSIENT_MESSAGES
    )


def retry_db_operation(
    max_attempts: int = 5,
    base_delay: float = 0.05,
    max_delay: float = 2.0,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> Callable[[F], F]:
    """Retry decorator specialised for SQLite transient errors.

    Only retries ``sqlite3.OperationalError`` whose message contains
    *database is locked* or *cannot commit*.  Other operational errors
    propagate immediately.
    """
    return retry(
        max_attempts=max_attempts,
        backoff="exponential",
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=(sqlite3.OperationalError,),
        on_retry=on_retry,
        exception_check=_is_transient_db_error,
    )


def retry_network_operation(
    max_attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> Callable[[F], F]:
    """Retry decorator specialised for network-related transient errors.

    Catches ``ConnectionError``, ``TimeoutError``, and ``OSError``.
    """
    return retry(
        max_attempts=max_attempts,
        backoff="exponential",
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=_NETWORK_EXCEPTIONS,
        on_retry=on_retry,
    )
