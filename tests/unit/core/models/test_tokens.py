"""Tests for src/armance/tokens.py — per-provider tokenizer abstraction."""
from __future__ import annotations


from armance.core.models.tokens import count_tokens, _resolve_encoding


# ── encoding resolution ────────────────────────────────────────────────────

def test_resolve_gpt4o_encoding() -> None:
    assert _resolve_encoding("gpt-4o") == "o200k_base"


def test_resolve_gpt4_encoding() -> None:
    assert _resolve_encoding("gpt-4") == "cl100k_base"


def test_resolve_unknown_fallback() -> None:
    assert _resolve_encoding("some-unknown-model-xyz") == "cl100k_base"


def test_resolve_openrouter_prefix() -> None:
    assert _resolve_encoding("openai/gpt-4o") == "o200k_base"


# ── count_tokens: openrouter (tiktoken) ───────────────────────────────────

def test_openrouter_returns_int() -> None:
    n = count_tokens("Hello, world!", "openrouter", "gpt-4o")
    assert isinstance(n, int)
    assert n > 0


def test_openrouter_longer_text_more_tokens() -> None:
    short = count_tokens("Hi", "openrouter", "gpt-4")
    long = count_tokens("This is a much longer sentence with many more words.", "openrouter", "gpt-4")
    assert long > short


def test_custom_openai_uses_tiktoken() -> None:
    n = count_tokens("Hello there", "custom-openai", "gpt-4")
    assert n > 0


# ── count_tokens: claude-code + gemini (heuristic) ────────────────────────

def test_claude_code_heuristic() -> None:
    text = "A" * 400
    n = count_tokens(text, "claude-code", "claude-opus-4-5")
    assert n == 100  # len(text) // 4


def test_gemini_heuristic() -> None:
    text = "B" * 800
    n = count_tokens(text, "gemini", "gemini-2.0-flash")
    assert n == 200


def test_unknown_provider_heuristic() -> None:
    text = "C" * 200
    n = count_tokens(text, "unknown-provider", "some-model")
    assert n == 50


# ── empty text ────────────────────────────────────────────────────────────

def test_empty_text_returns_zero() -> None:
    for provider in ("openrouter", "claude-code", "gemini", "custom-openai"):
        assert count_tokens("", provider, "m") == 0
