"""Tests for armance.providers.openrouter via respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from armance.config import ProviderConfig
from armance.service.llm_service import complete_with_continuation
from armance.providers.openrouter import LLMHTTPError, OpenRouterClient


def _provider() -> ProviderConfig:
    return ProviderConfig(
        name="openrouter", api_key="sk-test", base_url="https://api.test/v1"
    )


def _completion_payload(text: str, finish: str, prompt: int = 7, completion: int = 11) -> dict:
    return {
        "id": "x",
        "choices": [{"message": {"content": text}, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "cost": 0.001,
        },
    }


@pytest.mark.asyncio
async def test_openrouter_success() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=True) as router:
        router.post("https://api.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion_payload("hello", "stop"))
        )
        client = OpenRouterClient(_provider(), client=http_client)
        resp = await client.complete([{"role": "user", "content": "hi"}], "model-a")

    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.tokens_in == 7
    assert resp.tokens_out == 11
    assert resp.cost_usd == 0.001


@pytest.mark.asyncio
async def test_openrouter_error_status() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock() as router:
        router.post("https://api.test/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="boom")
        )
        client = OpenRouterClient(_provider(), client=http_client)
        with pytest.raises(LLMHTTPError):
            await client.complete([{"role": "user", "content": "hi"}], "model-a")


@pytest.mark.asyncio
async def test_continuation_handles_length_finish() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=True) as router:
        route = router.post("https://api.test/v1/chat/completions")
        route.side_effect = [
            httpx.Response(200, json=_completion_payload("first fragment long enough", "length", 5, 7)),
            httpx.Response(200, json=_completion_payload("and the rest", "stop", 6, 4)),
        ]
        client = OpenRouterClient(_provider(), client=http_client)
        resp = await complete_with_continuation(
            client, [{"role": "user", "content": "hi"}], "model-a"
        )

    assert resp.text == "first fragment long enoughand the rest"
    assert resp.finish_reason == "stop"
    assert resp.tokens_in == 11
    assert resp.tokens_out == 11
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_continuation_propagates_persistent_length() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock() as router:
        route = router.post("https://api.test/v1/chat/completions")
        route.side_effect = [
            httpx.Response(200, json=_completion_payload("first fragment long enough", "length")),
            httpx.Response(200, json=_completion_payload("and still truncated", "length")),
        ]
        client = OpenRouterClient(_provider(), client=http_client)
        resp = await complete_with_continuation(
            client, [{"role": "user", "content": "hi"}], "model-a"
        )

    assert resp.finish_reason == "length"
    assert resp.text == "first fragment long enoughand still truncated"
