"""filter_for_budget keeps effectively-free models regardless of tier.

Regression: Claude Haiku (tier=low, effectively_free=True) was being
filtered out under budget=free-first, leaving Malik to report "no models
discovered" for the `claude-code` provider even when subscription was
configured.
"""
from __future__ import annotations

from armance.providers.base import ModelSpec
from armance.providers.discovery import filter_for_budget


def test_effectively_free_low_kept_under_free_first() -> None:
    """Claude Haiku is tier=low but the user pays nothing (subscription)."""
    haiku = ModelSpec(
        id="claude-haiku-4-5", provider="claude-code",
        tier="low", effectively_free=True,
    )
    out = filter_for_budget([haiku], "free-first")
    assert out == [haiku]


def test_effectively_free_high_also_kept() -> None:
    """Even Claude Opus (tier=high) should survive free-first because
    a subscription user already pays for it."""
    opus = ModelSpec(
        id="claude-opus-4-7", provider="claude-code",
        tier="high", effectively_free=True,
    )
    out = filter_for_budget([opus], "free-first")
    assert out == [opus]


def test_non_free_low_still_excluded_under_free_first() -> None:
    """A paid Gemini Flash (tier=low, effectively_free=False) stays out."""
    flash = ModelSpec(
        id="gemini-2.5-flash", provider="gemini",
        tier="low", effectively_free=False,
    )
    out = filter_for_budget([flash], "free-first")
    assert out == []


def test_or_free_kept_under_free_first() -> None:
    """OpenRouter `:free` ids (tier=free, effectively_free=True) stay in."""
    gemma = ModelSpec(
        id="google/gemma-2-9b-it:free", provider="openrouter",
        tier="free", effectively_free=True,
    )
    out = filter_for_budget([gemma], "free-first")
    assert out == [gemma]


def test_mixed_catalogue_under_free_first() -> None:
    haiku = ModelSpec(
        id="claude-haiku-4-5", provider="claude-code",
        tier="low", effectively_free=True,
    )
    flash = ModelSpec(
        id="gemini-2.5-flash", provider="gemini",
        tier="low", effectively_free=False,
    )
    gemma = ModelSpec(
        id="google/gemma:free", provider="openrouter",
        tier="free", effectively_free=True,
    )
    out = filter_for_budget([haiku, flash, gemma], "free-first")
    ids = {m.id for m in out}
    assert "claude-haiku-4-5" in ids
    assert "google/gemma:free" in ids
    assert "gemini-2.5-flash" not in ids
