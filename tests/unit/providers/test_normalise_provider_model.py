"""Validator: provider/model normalisation in the recruiter."""
from __future__ import annotations

from armance.service.agents.recruiter_agent import _normalise_provider_model


def test_strips_vendor_prefix_from_provider() -> None:
    """`openrouter/google` should split into `openrouter` + `google/<model>`."""
    p, m = _normalise_provider_model(
        "openrouter/google", "gemma-2-9b-it:free",
        default_provider="openrouter",
    )
    assert p == "openrouter"
    assert m == "google/gemma-2-9b-it:free"


def test_keeps_already_canonical_pair() -> None:
    p, m = _normalise_provider_model(
        "openrouter", "google/gemma-2-9b-it:free",
        default_provider="openrouter",
    )
    assert p == "openrouter"
    assert m == "google/gemma-2-9b-it:free"


def test_unknown_bare_provider_falls_back() -> None:
    p, m = _normalise_provider_model(
        "deepseek", "deepseek-r1",
        default_provider="openrouter",
    )
    assert p == "openrouter"


def test_does_not_double_prefix_model() -> None:
    """`provider: openrouter/qwen`, `model: qwen/qwen-2.5-7b` already has the
    vendor — keep as-is, don't prepend twice."""
    p, m = _normalise_provider_model(
        "openrouter/qwen", "qwen/qwen-2.5-7b-instruct",
        default_provider="openrouter",
    )
    assert p == "openrouter"
    assert m == "qwen/qwen-2.5-7b-instruct"


def test_empty_provider_uses_default() -> None:
    p, m = _normalise_provider_model("", "x", default_provider="gemini")
    assert p == "gemini"
    assert m == "x"


def test_recognises_all_known_providers() -> None:
    for known in ("openrouter", "claude-code", "gemini", "custom-openai"):
        p, _ = _normalise_provider_model(known, "x", default_provider="openrouter")
        assert p == known
