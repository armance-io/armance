"""service.rate_limit — per-provider concurrency cap + 429-aware backoff."""
from __future__ import annotations

import asyncio

import pytest

from armance.providers.gemini import GeminiHTTPError
from armance.providers.openrouter import LLMHTTPError
from armance.service import rate_limit
from armance.service.rate_limit import (
    MAX_CONCURRENT_PER_PROVIDER,
    RATE_LIMIT_BACKOFF_FLOOR,
    backoff_for,
    is_rate_limit,
    provider_semaphore,
)


@pytest.fixture(autouse=True)
def _fresh_semaphores():
    rate_limit._reset_for_tests()
    yield
    rate_limit._reset_for_tests()


def test_is_rate_limit_on_429() -> None:
    assert is_rate_limit(LLMHTTPError("x", status_code=429))
    assert is_rate_limit(GeminiHTTPError("x", status_code=429))


def test_is_not_rate_limit_on_other_errors() -> None:
    assert not is_rate_limit(LLMHTTPError("x", status_code=500))
    assert not is_rate_limit(LLMHTTPError("x"))  # no status
    assert not is_rate_limit(RuntimeError("boom"))


def test_backoff_for_429_has_floor() -> None:
    exc = LLMHTTPError("x", status_code=429)
    assert backoff_for(exc, attempt=1, base_backoff=2.0) == RATE_LIMIT_BACKOFF_FLOOR
    assert backoff_for(exc, attempt=2, base_backoff=2.0) == 2 * RATE_LIMIT_BACKOFF_FLOOR


def test_backoff_for_429_honours_retry_after_hint() -> None:
    exc = LLMHTTPError("x", status_code=429, retry_after=42.0)
    assert backoff_for(exc, attempt=1, base_backoff=2.0) == 42.0


def test_backoff_for_other_errors_keeps_base() -> None:
    assert backoff_for(RuntimeError("boom"), attempt=1, base_backoff=2.0) == 2.0


def test_provider_semaphore_is_shared_per_provider() -> None:
    a = provider_semaphore("openrouter")
    b = provider_semaphore("openrouter")
    c = provider_semaphore("gemini")
    assert a is b
    assert a is not c
    assert provider_semaphore(None) is provider_semaphore("default")


@pytest.mark.asyncio
async def test_semaphore_caps_concurrency() -> None:
    sem = provider_semaphore("openrouter")
    in_flight = 0
    peak = 0

    async def call() -> None:
        nonlocal in_flight, peak
        async with sem:
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1

    await asyncio.gather(*(call() for _ in range(6)))
    assert peak <= MAX_CONCURRENT_PER_PROVIDER


@pytest.mark.asyncio
async def test_call_with_ledger_waits_longer_on_429(monkeypatch) -> None:
    """A 429 from the client sleeps with the rate-limit floor, not 2s."""
    from unittest.mock import AsyncMock, MagicMock

    from armance.service import llm_service

    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMHTTPError("429 too many", status_code=429, retry_after=0.0)
        return MagicMock(
            text="ok", tokens_in=1, tokens_out=1, cost_usd=None, finish_reason="stop"
        )

    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(
        llm_service, "complete_with_continuation", AsyncMock(side_effect=flaky)
    )
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    response = await llm_service.call_with_ledger(
        MagicMock(), "tester", [{"role": "user", "content": "hi"}], "m",
        provider="openrouter",
    )
    assert response.text == "ok"
    assert sleeps == [RATE_LIMIT_BACKOFF_FLOOR]
