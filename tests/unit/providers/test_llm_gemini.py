"""Tests for armance.providers.gemini via respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from armance.config import ProviderConfig
from armance.service.llm_service import complete_with_continuation
from armance.providers.gemini import (
    GeminiHTTPError,
    GeminiClient,
    _messages_to_contents,
    _parse_generate_content,
    _normalize_gemini_finish,
)


def _provider() -> ProviderConfig:
    return ProviderConfig(
        name="gemini", api_key="sk-test", base_url="https://api.test/v1beta"
    )


def _gemini_payload(
    text: str = "hello",
    finish: str = "STOP",
    prompt_tokens: int = 7,
    candidates_tokens: int = 11,
) -> dict:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finish_reason": finish,
            }
        ],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": candidates_tokens,
        },
    }


# --- _messages_to_contents ---


def test_messages_to_contents_maps_system_to_user() -> None:
    msgs = [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "hi"},
    ]
    contents = _messages_to_contents(msgs)
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "be helpful"
    assert contents[1]["role"] == "user"
    assert contents[1]["parts"][0]["text"] == "hi"


def test_messages_to_contents_maps_assistant_to_model() -> None:
    msgs = [{"role": "assistant", "content": "reply"}]
    contents = _messages_to_contents(msgs)
    assert contents[0]["role"] == "model"


def test_messages_to_contents_skips_empty_content() -> None:
    msgs = [{"role": "user", "content": ""}, {"role": "user", "content": "hi"}]
    contents = _messages_to_contents(msgs)
    assert len(contents) == 1


# --- _parse_generate_content ---


def test_parse_generate_content_success() -> None:
    data = _gemini_payload(text="world", finish="STOP", prompt_tokens=5, candidates_tokens=3)
    resp = _parse_generate_content(data)
    assert resp.text == "world"
    assert resp.finish_reason == "stop"
    assert resp.tokens_in == 5
    assert resp.tokens_out == 3
    assert resp.cost_usd is None


def test_parse_generate_content_empty_candidates() -> None:
    resp = _parse_generate_content({"candidates": []})
    assert resp.text == ""
    assert resp.finish_reason == "other"
    assert resp.tokens_in == 0


def test_parse_generate_content_max_tokens() -> None:
    data = _gemini_payload(finish="MAX_TOKENS")
    resp = _parse_generate_content(data)
    assert resp.finish_reason == "length"


def test_parse_generate_content_multiple_parts() -> None:
    data = {
        "candidates": [
            {
                "content": {"parts": [{"text": "a"}, {"text": "b"}], "role": "model"},
                "finish_reason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 2},
    }
    resp = _parse_generate_content(data)
    assert resp.text == "a\nb"


# --- _normalize_gemini_finish ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("STOP", "stop"),
        ("MAX_TOKENS", "length"),
        ("OVER_TOKEN_LIMIT", "length"),
        ("SAFETY", "other"),
        ("RECITATION", "other"),
        ("LANGUAGE", "other"),
        ("OTHER", "other"),
        ("FINISH_REASON_UNSPECIFIED", "other"),
        ("UNKNOWN_REASON", "other"),
    ],
)
def test_normalize_gemini_finish(raw: str, expected: str) -> None:
    assert _normalize_gemini_finish(raw) == expected


# --- GeminiClient.complete ---


@pytest.mark.asyncio
async def test_gemini_success() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=True) as router:
        router.post("https://api.test/v1beta/models/gemini-1.5:generateContent").mock(
            return_value=httpx.Response(200, json=_gemini_payload("ok", "STOP", 3, 4))
        )
        client = GeminiClient(_provider(), client=http_client)
        resp = await client.complete([{"role": "user", "content": "hi"}], "gemini-1.5")

    assert resp.text == "ok"
    assert resp.finish_reason == "stop"
    assert resp.tokens_in == 3
    assert resp.tokens_out == 4
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_error_status() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock() as router:
        router.post("https://api.test/v1beta/models/gemini-1.5:generateContent").mock(
            return_value=httpx.Response(500, text="server boom")
        )
        client = GeminiClient(_provider(), client=http_client)
        with pytest.raises(GeminiHTTPError):
            await client.complete([{"role": "user", "content": "hi"}], "gemini-1.5")
        await client.aclose()


@pytest.mark.asyncio
async def test_gemini_api_key_passed_in_payload() -> None:
    import json as json_mod

    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=True) as router:
        route = router.post("https://api.test/v1beta/models/gemini-1.5:generateContent").mock(
            return_value=httpx.Response(200, json=_gemini_payload())
        )
        client = GeminiClient(_provider(), client=http_client)
        await client.complete([{"role": "user", "content": "hi"}], "gemini-1.5")

    # API key is passed in the JSON payload as "key"
    request = route.calls[0].request
    body = json_mod.loads(request.content)
    assert body["key"] == "sk-test"
    await client.aclose()


@pytest.mark.asyncio
async def test_continuation_handles_length_finish() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=True) as router:
        route = router.post("https://api.test/v1beta/models/gemini-1.5:generateContent")
        route.side_effect = [
            httpx.Response(200, json=_gemini_payload("first fragment long enough", "MAX_TOKENS", 5, 7)),
            httpx.Response(200, json=_gemini_payload(" and the rest", "STOP", 6, 4)),
        ]
        client = GeminiClient(_provider(), client=http_client)
        resp = await complete_with_continuation(
            client, [{"role": "user", "content": "hi"}], "gemini-1.5"
        )

    assert resp.text == "first fragment long enough and the rest"
    assert resp.finish_reason == "stop"
    assert resp.tokens_in == 11
    assert resp.tokens_out == 11
    assert route.call_count == 2
    await client.aclose()
