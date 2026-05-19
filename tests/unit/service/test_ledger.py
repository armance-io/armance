"""Tests for armance.service.llm_service.TokenLedger and call_with_ledger."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.core.protocols.llm import (
    LLMClient,
    LLMResponse,
    TokenLedger,
    call_with_ledger,
)


class StubClient(LLMClient):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    async def complete(self, messages, model, **params):  # type: ignore[override]
        return self._responses.pop(0)

    async def embed(self, text, model):
        return [0.0] * 1536


def _resp(text: str, t_in: int, t_out: int, finish: str = "stop", cost: float | None = 0.001) -> LLMResponse:
    return LLMResponse(text=text, tokens_in=t_in, tokens_out=t_out, finish_reason=finish, cost_usd=cost)


def test_ledger_record_and_snapshot() -> None:
    ledger = TokenLedger()
    ledger.record("alpha", 10, 20, 0.001)
    ledger.record("alpha", 5, 6, 0.0005)
    ledger.record("beta", 1, 2, None)
    snap = ledger.snapshot()
    assert snap["per_agent"]["alpha"] == {
        "tokens_in": 15, "tokens_out": 26, "cost_usd": pytest.approx(0.0015), "calls": 2,
    }
    assert snap["per_agent"]["beta"]["tokens_in"] == 1
    assert snap["total"]["tokens_in"] == 16
    assert snap["total"]["calls"] == 3


@pytest.mark.asyncio
async def test_call_with_ledger_persists_to_disk(tmp_path: Path) -> None:
    persist = tmp_path / "ledger.json"
    ledger = TokenLedger(persist_path=persist)
    client = StubClient([_resp("hi", 7, 11)])
    resp = await call_with_ledger(
        client, "alpha", [{"role": "user", "content": "x"}], "model-a", ledger=ledger
    )
    assert resp.text == "hi"
    assert persist.exists()
    payload = json.loads(persist.read_text(encoding="utf-8"))
    assert payload["entries"][0] == {
        "agent": "alpha", "tokens_in": 7, "tokens_out": 11, "cost_usd": 0.001,
    }
    assert payload["snapshot_unsafe"]["total"]["tokens_in"] == 7


@pytest.mark.asyncio
async def test_call_with_ledger_handles_continuation_sums(tmp_path: Path) -> None:
    ledger = TokenLedger()
    client = StubClient([_resp("first fragment long enough", 5, 7, finish="length"), _resp("continuation", 6, 4)])
    resp = await call_with_ledger(
        client, "beta", [{"role": "user", "content": "x"}], "model-a", ledger=ledger
    )
    assert resp.text == "first fragment long enoughcontinuation"
    snap = ledger.snapshot()
    assert snap["per_agent"]["beta"]["tokens_in"] == 11
    assert snap["per_agent"]["beta"]["tokens_out"] == 11
    assert snap["per_agent"]["beta"]["calls"] == 1
