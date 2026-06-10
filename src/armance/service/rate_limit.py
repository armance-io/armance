"""Per-provider concurrency cap + 429-aware backoff.

Background workflow runs removed the natural one-call-at-a-time limit the
TUI used to impose: a run driving several specialists in parallel plus a
live chat can hammer the same provider (free-tier OpenRouter especially)
and trip HTTP 429. This module is the minimal governor:

- ``provider_semaphore(name)`` — an ``asyncio.Semaphore`` per provider,
  capping concurrent in-flight calls (default 2).
- ``backoff_for(exc, attempt, base_backoff)`` — the sleep to apply before
  retrying: honours the provider's ``retry_after`` hint when the failure
  is a rate limit, with a floor that actually lets a free-tier window
  reset, and falls back to the caller's exponential backoff otherwise.

Provider exceptions carry ``status_code`` / ``retry_after`` attributes
(see ``providers/openrouter.py`` / ``providers/gemini.py``); detection is
duck-typed so this module imports nothing from ``providers``.
"""
from __future__ import annotations

import asyncio

# Max concurrent in-flight LLM calls per provider. Low on purpose: a
# single-user tool gains nothing from more parallelism than this on one
# provider, and free tiers punish it.
MAX_CONCURRENT_PER_PROVIDER = 2

# A 429 almost never resets in the 2-3s of the generic backoff; wait at
# least this long (seconds), scaled by attempt.
RATE_LIMIT_BACKOFF_FLOOR = 10.0

_semaphores: dict[str, asyncio.Semaphore] = {}


def provider_semaphore(provider: str | None) -> asyncio.Semaphore:
    """The shared concurrency gate for ``provider`` (``None`` → default)."""
    key = provider or "default"
    sem = _semaphores.get(key)
    if sem is None:
        sem = asyncio.Semaphore(MAX_CONCURRENT_PER_PROVIDER)
        _semaphores[key] = sem
    return sem


def is_rate_limit(exc: BaseException) -> bool:
    """True when the exception is an HTTP 429 from a provider client."""
    return getattr(exc, "status_code", None) == 429


def backoff_for(exc: BaseException, attempt: int, base_backoff: float) -> float:
    """Seconds to sleep before retry ``attempt`` (1-based) after ``exc``.

    Rate limits get the provider's Retry-After hint when present, never
    less than ``RATE_LIMIT_BACKOFF_FLOOR * attempt``. Everything else
    keeps the caller's exponential backoff.
    """
    if is_rate_limit(exc):
        hint = getattr(exc, "retry_after", None) or 0.0
        return max(float(hint), RATE_LIMIT_BACKOFF_FLOOR * attempt)
    return base_backoff


def _reset_for_tests() -> None:
    """Drop all semaphores (test isolation across event loops)."""
    _semaphores.clear()
