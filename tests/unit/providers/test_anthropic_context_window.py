"""Live context-window discovery for the claude-code provider.

The list endpoint carries no capability data; the per-model retrieve endpoint
does. `_fetch` reads `max_input_tokens` live and only falls back to the
written-in-stone constant when the lookup fails or omits the field.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from armance.providers.anthropic_provider import (
    ClaudeCodeProvider,
    _FALLBACK_CONTEXT_WINDOW,
)

_LIST = "https://api.anthropic.com/v1/models"


@respx.mock
@pytest.mark.asyncio
async def test_context_window_read_live_from_capability_endpoint() -> None:
    respx.get(_LIST).mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "claude-opus-4-8", "display_name": "Claude Opus 4.8"}]},
        )
    )
    respx.get(f"{_LIST}/claude-opus-4-8").mock(
        return_value=httpx.Response(200, json={"max_input_tokens": 1_000_000})
    )

    p = ClaudeCodeProvider(api_key="sk-test")
    models = await p.list_models()

    assert len(models) == 1
    assert models[0].context_window == 1_000_000  # live, not the fallback


@respx.mock
@pytest.mark.asyncio
async def test_context_window_falls_back_when_lookup_fails() -> None:
    respx.get(_LIST).mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "claude-opus-4-8", "display_name": "Claude Opus 4.8"}]},
        )
    )
    # Capability endpoint 500s — fall back to the constant, don't sink the catalogue.
    respx.get(f"{_LIST}/claude-opus-4-8").mock(return_value=httpx.Response(500))

    p = ClaudeCodeProvider(api_key="sk-test")
    models = await p.list_models()

    assert len(models) == 1
    assert models[0].context_window == _FALLBACK_CONTEXT_WINDOW
