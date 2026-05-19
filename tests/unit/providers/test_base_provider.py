"""ModelSpec + tier derivation + discovery cache helpers."""
from __future__ import annotations

from armance.providers.base import ModelSpec, derive_tier
from armance.providers.discovery import filter_for_budget, reset_cache


def test_derive_tier_free_when_price_zero() -> None:
    assert derive_tier(0.0, 0.0) == "free"


def test_derive_tier_low_below_half_dollar() -> None:
    assert derive_tier(0.1, 0.3) == "low"


def test_derive_tier_medium_below_five() -> None:
    assert derive_tier(1.0, 2.0) == "medium"


def test_derive_tier_high_above_five() -> None:
    assert derive_tier(3.0, 6.0) == "high"


def test_model_spec_is_free_true_when_both_zero() -> None:
    m = ModelSpec(id="x", provider="openrouter")
    assert m.is_free


def test_filter_for_budget_free_first_keeps_only_free() -> None:
    models = [
        ModelSpec(id="a", provider="openrouter", tier="free"),
        ModelSpec(id="b", provider="openrouter", tier="low"),
        ModelSpec(id="c", provider="openrouter", tier="medium"),
    ]
    out = filter_for_budget(models, "free-first")
    assert [m.id for m in out] == ["a"]


def test_filter_for_budget_medium_drops_high() -> None:
    models = [
        ModelSpec(id="a", provider="openrouter", tier="free"),
        ModelSpec(id="b", provider="openrouter", tier="low"),
        ModelSpec(id="c", provider="openrouter", tier="medium"),
        ModelSpec(id="d", provider="openrouter", tier="high"),
    ]
    out = filter_for_budget(models, "medium")
    assert {m.id for m in out} == {"a", "b", "c"}


def test_reset_cache_does_not_raise() -> None:
    reset_cache()
