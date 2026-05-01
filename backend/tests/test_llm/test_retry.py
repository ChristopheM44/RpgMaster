from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.retry import with_llm_retry


class TransientError(Exception):
    pass


class FatalError(Exception):
    pass


class WrappedRetryError(Exception):
    pass


def _wrap_retry_error(exc: Optional[BaseException], max_retries: int) -> WrappedRetryError:
    return WrappedRetryError(f"failed after {max_retries}: {exc}")


async def test_with_llm_retry_returns_without_retry() -> None:
    calls = 0

    @with_llm_retry(
        retry_exceptions=(TransientError,),
        error_factory=_wrap_retry_error,
        provider_name="TestLLM",
    )
    async def call_llm() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    sleep = AsyncMock()
    with patch("app.llm.retry.asyncio.sleep", new=sleep):
        result = await call_llm()

    assert result == "ok"
    assert calls == 1
    sleep.assert_not_awaited()


async def test_with_llm_retry_retries_then_returns() -> None:
    calls = 0

    @with_llm_retry(
        retry_exceptions=(TransientError,),
        error_factory=_wrap_retry_error,
        provider_name="TestLLM",
        base_delay=0.5,
    )
    async def call_llm() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("temporary")
        return "recovered"

    sleep = AsyncMock()
    with patch("app.llm.retry.asyncio.sleep", new=sleep):
        result = await call_llm()

    assert result == "recovered"
    assert calls == 3
    assert [call.args[0] for call in sleep.await_args_list] == [0.5, 1.0]


async def test_with_llm_retry_wraps_last_exception_after_max_retries() -> None:
    calls = 0

    @with_llm_retry(
        retry_exceptions=(TransientError,),
        error_factory=_wrap_retry_error,
        provider_name="TestLLM",
        max_retries=3,
    )
    async def call_llm() -> str:
        nonlocal calls
        calls += 1
        raise TransientError(f"temporary-{calls}")

    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(WrappedRetryError, match="failed after 3: temporary-3") as exc:
            await call_llm()

    assert calls == 3
    assert isinstance(exc.value.__cause__, TransientError)


async def test_with_llm_retry_does_not_catch_non_retryable_exception() -> None:
    calls = 0

    @with_llm_retry(
        retry_exceptions=(TransientError,),
        error_factory=_wrap_retry_error,
        provider_name="TestLLM",
    )
    async def call_llm() -> str:
        nonlocal calls
        calls += 1
        raise FatalError("fatal")

    sleep = AsyncMock()
    with patch("app.llm.retry.asyncio.sleep", new=sleep):
        with pytest.raises(FatalError, match="fatal"):
            await call_llm()

    assert calls == 1
    sleep.assert_not_awaited()
