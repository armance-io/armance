"""Web-search capability detection across providers."""
from __future__ import annotations

import pytest

from armance.providers.openrouter_provider import _BUILTIN_SEARCH_PATTERNS
from armance.providers.gemini_provider import GeminiProvider, _FALLBACK_SPECS as _GEMINI_FB
from armance.providers.anthropic_provider import ClaudeCodeProvider, _FALLBACK_SPECS as _ANTHROPIC_FB


def test_openrouter_sonar_detected_as_search() -> None:
    assert _BUILTIN_SEARCH_PATTERNS.search("perplexity/sonar")
    assert _BUILTIN_SEARCH_PATTERNS.search("perplexity/sonar-pro")
    assert _BUILTIN_SEARCH_PATTERNS.search("perplexity/sonar-reasoning")


def test_openrouter_online_suffix_detected() -> None:
    assert _BUILTIN_SEARCH_PATTERNS.search("openai/gpt-4o:online")
    assert _BUILTIN_SEARCH_PATTERNS.search("google/gemini-2.5-pro:online")


def test_openrouter_plain_free_not_search() -> None:
    assert not _BUILTIN_SEARCH_PATTERNS.search("meta-llama/llama-3.3-70b-instruct:free")
    assert not _BUILTIN_SEARCH_PATTERNS.search("google/gemma-2-9b-it:free")


@pytest.mark.asyncio
async def test_gemini_fallback_when_no_key() -> None:
    p = GeminiProvider(api_key="")
    models = await p.list_models()
    assert models  # fallback is non-empty
    assert all(m.provider == "gemini" for m in models)
    assert all(m.supports_search for m in models)
    assert all(m.search_mode == "tool" for m in models)


@pytest.mark.asyncio
async def test_anthropic_fallback_when_no_key() -> None:
    p = ClaudeCodeProvider(api_key="")
    models = await p.list_models()
    assert models
    assert all(m.provider == "claude-code" for m in models)
    assert all(m.supports_search for m in models)
    assert all(m.effectively_free for m in models)


def test_gemini_fallback_includes_flash_and_pro() -> None:
    ids = {m.id for m in _GEMINI_FB}
    assert "gemini-2.5-flash" in ids
    assert "gemini-2.5-pro" in ids


def test_anthropic_fallback_includes_three_tiers() -> None:
    ids = {m.id for m in _ANTHROPIC_FB}
    assert "claude-haiku-4-5" in ids
    assert "claude-sonnet-4-6" in ids
    assert "claude-opus-4-7" in ids
