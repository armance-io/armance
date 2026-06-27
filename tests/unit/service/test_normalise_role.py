"""Validator: domain normalisation in the recruiter.

Malik's LLM frequently writes French prose like
`historien des temps modernes` as a `domain:` value. Workflow executor
matches steps to agents by exact domain match, so we slugify to short
ASCII identifiers at recruit time.
"""
from __future__ import annotations

from armance.service.agents.recruiter_agent import _normalise_role


def test_keeps_clean_english_slug() -> None:
    assert _normalise_role("historian") == "historian"


def test_strips_french_stopwords_and_accents() -> None:
    out = _normalise_role("Historien des temps modernes")
    # Stop-tokens "des" dropped, accents stripped.
    assert "des" not in out
    assert "é" not in out
    assert out.startswith("historien")


def test_event_organizer_french_normalised() -> None:
    out = _normalise_role("coordinateur événementiel")
    assert out == "coordinateur-evenementiel"


def test_multi_word_kebab_case() -> None:
    assert _normalise_role("Project Manager") == "project-manager"


def test_empty_returns_empty() -> None:
    assert _normalise_role("") == ""
    assert _normalise_role("   ") == ""


def test_punctuation_collapses_to_hyphen() -> None:
    out = _normalise_role("coordinateur (logistique)")
    assert "(" not in out
    assert ")" not in out
    assert out.startswith("coordinateur")


def test_long_phrase_truncated_to_three_tokens() -> None:
    out = _normalise_role("expert en histoire culturelle des relations franco-ecossaises")
    # Three meaningful tokens at most.
    assert out.count("-") <= 2
