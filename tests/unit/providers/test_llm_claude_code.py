"""Tests for armance.providers.claude_code via SDK monkeypatching."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

import pytest

from armance.config import ProviderConfig
from armance.providers import claude_code as cc_module


@dataclass
class _StubText:
    text: str


@dataclass
class _StubAssistant:
    content: list[Any]


@dataclass
class _StubResult:
    usage: dict
    total_cost_usd: float | None = None
    is_error: bool = False
    stop_reason: str | None = None


class _StubOptions:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _patch_sdk(monkeypatch: pytest.MonkeyPatch, messages: list[Any]) -> dict:
    captured: dict = {}

    async def fake_query(*, prompt: str, options: Any) -> AsyncIterator[Any]:
        captured["prompt"] = prompt
        captured["options"] = options
        for m in messages:
            yield m

    fake_module = type(
        "FakeSDK",
        (),
        {
            "AssistantMessage": _StubAssistant,
            "ResultMessage": _StubResult,
            "TextBlock": _StubText,
            "ClaudeAgentOptions": _StubOptions,
            "query": fake_query,
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "claude_agent_sdk", fake_module)
    return captured


@pytest.mark.asyncio
async def test_claude_code_collects_text_and_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_sdk(
        monkeypatch,
        [
            _StubAssistant(content=[_StubText(text="foo "), _StubText(text="bar")]),
            _StubResult(usage={"input_tokens": 12, "output_tokens": 5}, total_cost_usd=0.02),
        ],
    )

    client = cc_module.ClaudeCodeClient(ProviderConfig(name="claude-code"))
    resp = await client.complete(
        [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ],
        "claude-sonnet-4-6",
    )

    assert resp.text == "foo bar"
    assert resp.tokens_in == 12
    assert resp.tokens_out == 5
    assert resp.cost_usd == 0.02
    assert resp.finish_reason == "stop"
    assert captured["prompt"] == "hi"
    assert captured["options"].kwargs["system_prompt"] == "be terse"


@pytest.mark.asyncio
async def test_claude_code_falls_back_to_tiktoken_when_telemetry_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sdk(
        monkeypatch,
        [_StubAssistant(content=[_StubText(text="hello world")])],
    )
    client = cc_module.ClaudeCodeClient(ProviderConfig(name="claude-code"))
    resp = await client.complete([{"role": "user", "content": "hi"}], "m")
    assert resp.tokens_in > 0
    assert resp.tokens_out > 0


@pytest.mark.asyncio
async def test_claude_code_propagates_max_tokens_as_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sdk(
        monkeypatch,
        [
            _StubAssistant(content=[_StubText(text="cut")]),
            _StubResult(usage={"input_tokens": 1, "output_tokens": 1}, stop_reason="max_tokens"),
        ],
    )
    client = cc_module.ClaudeCodeClient(ProviderConfig(name="claude-code"))
    resp = await client.complete([{"role": "user", "content": "hi"}], "m")
    assert resp.finish_reason == "length"


def test_content_to_str_coerces_multipart_blocks() -> None:
    """Anthropic-style content arrives as list[{"type":"text","text":...}].
    Coercion must yield plain string for downstream str.join."""
    from armance.providers.claude_code import _content_to_str
    assert _content_to_str("plain") == "plain"
    assert _content_to_str([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert _content_to_str([{"text": "x"}]) == "x"
    assert _content_to_str(None) == ""
    assert _content_to_str(["raw", {"text": "z"}]) == "rawz"


@pytest.mark.asyncio
async def test_claude_code_accepts_multipart_system_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: TypeError 'sequence item 0: expected str instance, dict found'
    on Claude models when system content is multipart."""
    _patch_sdk(
        monkeypatch,
        [
            _StubAssistant(content=[_StubText(text="ok")]),
            _StubResult(usage={"input_tokens": 1, "output_tokens": 1}),
        ],
    )
    client = cc_module.ClaudeCodeClient(ProviderConfig(name="claude-code"))
    resp = await client.complete(
        [
            {"role": "system", "content": [{"type": "text", "text": "sys1"}]},
            {"role": "user", "content": [{"type": "text", "text": "u1"}]},
        ],
        "claude-haiku-4-5",
    )
    assert resp.text == "ok"
