from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Optional, TypeVar

ResultT = TypeVar("ResultT")
AsyncCallable = Callable[..., Awaitable[ResultT]]
ErrorFactory = Callable[[Optional[BaseException], int], Exception]
JitterFactory = Callable[[], float]

logger = logging.getLogger(__name__)


def with_llm_retry(
    *,
    retry_exceptions: tuple[type[BaseException], ...],
    error_factory: ErrorFactory,
    provider_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    jitter: Optional[JitterFactory] = None,
    log: Optional[logging.Logger] = None,
) -> Callable[[AsyncCallable[ResultT]], AsyncCallable[ResultT]]:
    """Retry an async LLM call with exponential backoff."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    def decorator(func: AsyncCallable[ResultT]) -> AsyncCallable[ResultT]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> ResultT:
            delay = base_delay
            last_exc: Optional[BaseException] = None
            retry_logger = log or logger

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        break

                    retry_logger.warning(
                        "%s tentative %d/%d échouée : %s — retry dans %.1fs",
                        provider_name,
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    sleep_delay = delay + (jitter() if jitter is not None else 0.0)
                    await asyncio.sleep(sleep_delay)
                    delay *= 2

            raise error_factory(last_exc, max_retries) from last_exc

        return wrapper

    return decorator
