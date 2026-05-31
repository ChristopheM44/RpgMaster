from __future__ import annotations

import asyncio
import contextvars
import inspect
import logging
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar

ResultT = TypeVar("ResultT")
AsyncCallable = Callable[..., Awaitable[ResultT]]
ErrorFactory = Callable[[BaseException | None, int], Exception]
JitterFactory = Callable[[], float]
RetryObserver = Callable[[dict[str, Any]], Any]

logger = logging.getLogger(__name__)
_retry_observer: contextvars.ContextVar[RetryObserver | None] = contextvars.ContextVar(
    "llm_retry_observer",
    default=None,
)


@contextmanager
def observe_llm_retries(observer: RetryObserver | None):
    """Register a task-local observer for low-level LLM retry attempts."""
    token = _retry_observer.set(observer)
    try:
        yield
    finally:
        _retry_observer.reset(token)


async def _notify_retry_observer(event: dict[str, Any]) -> None:
    observer = _retry_observer.get()
    if observer is None:
        return
    try:
        result = observer(event)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.debug("LLM retry observer failed", exc_info=True)


def with_llm_retry(
    *,
    retry_exceptions: tuple[type[BaseException], ...],
    error_factory: ErrorFactory,
    provider_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    jitter: JitterFactory | None = None,
    log: logging.Logger | None = None,
) -> Callable[[AsyncCallable[ResultT]], AsyncCallable[ResultT]]:
    """Retry an async LLM call with exponential backoff."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    def decorator(func: AsyncCallable[ResultT]) -> AsyncCallable[ResultT]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> ResultT:
            delay = base_delay
            last_exc: BaseException | None = None
            retry_logger = log or logger

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        break

                    err_msg = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                    retry_logger.warning(
                        "%s tentative %d/%d échouée : %s — retry dans %.1fs",
                        provider_name,
                        attempt,
                        max_retries,
                        err_msg,
                        delay,
                    )
                    await _notify_retry_observer(
                        {
                            "provider": provider_name,
                            "attempt": attempt,
                            "max_attempts": max_retries,
                            "delay": delay,
                            "error": str(exc),
                        }
                    )
                    sleep_delay = delay + (jitter() if jitter is not None else 0.0)
                    await asyncio.sleep(sleep_delay)
                    delay *= 2

            raise error_factory(last_exc, max_retries) from last_exc

        return wrapper

    return decorator
