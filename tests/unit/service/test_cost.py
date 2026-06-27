"""Tests for armance.service.cost and TokenLedger budget cap.

Hard-coded model prices were removed from service.cost — all prices now
flow from `cfg.prices` (user override) or live OpenRouter discovery.
These tests use explicit overrides so they stay deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest


_SONNET = {"input_per_mtok": 3.0, "output_per_mtok": 15.0}
_OPUS = {"input_per_mtok": 15.0, "output_per_mtok": 75.0}
_OVERRIDE = {
    "anthropic/claude-sonnet-4-6": _SONNET,
    "claude-opus-4-7": _OPUS,
    "my-model": {"input_per_mtok": 1.0, "output_per_mtok": 2.0},
}


@dataclass
class _FakeAgent:
    name: str
    model: str = "anthropic/claude-sonnet-4-6"
    provider: str = "openrouter"


def _make_workflow(steps_spec: list[dict]):
    from armance.core.models.workflow import Workflow, WorkflowStep

    steps = [
        WorkflowStep(
            id=s["id"],
            kind=s.get("kind", "meeting"),
            role=s.get("role", "default"),
            mode=s.get("mode", "full"),
            agents=s.get("agents", []),
            prompt_template=s.get("prompt_template", "{{user_prompt}}"),
        )
        for s in steps_spec
    ]
    return Workflow(name="test", steps=steps)


# ---------------------------------------------------------------------------
# lookup_price
# ---------------------------------------------------------------------------

def test_lookup_price_override_exact():
    from armance.service.cost import lookup_price
    p = lookup_price("anthropic/claude-sonnet-4-6", prices_override=_OVERRIDE)
    assert p == _SONNET


def test_lookup_price_override_short_form():
    from armance.service.cost import lookup_price
    p = lookup_price("claude-opus-4-7", prices_override=_OVERRIDE)
    assert p == _OPUS


def test_lookup_price_free_suffix_zero(monkeypatch):
    # Force live discovery off so we exercise the :free heuristic only.
    from armance.service import cost as _cost
    monkeypatch.setattr(_cost, "_live_openrouter_prices", lambda: {})
    p = _cost.lookup_price("foo/bar:free")
    assert p == {"input_per_mtok": 0.0, "output_per_mtok": 0.0}


def test_lookup_price_unknown_returns_none(monkeypatch):
    from armance.service import cost as _cost
    monkeypatch.setattr(_cost, "_live_openrouter_prices", lambda: {})
    assert _cost.lookup_price("totally-unknown-model-xyz") is None


def test_token_cost_usd_math():
    from armance.service.cost import token_cost_usd
    # 1M input + 1M output at $3/$15 per MTok = $18
    cost = token_cost_usd(1_000_000, 1_000_000, "anthropic/claude-sonnet-4-6", prices_override=_OVERRIDE)
    assert cost is not None
    assert abs(cost - 18.0) < 1e-6


def test_token_cost_usd_unknown_model_returns_none(monkeypatch):
    from armance.service import cost as _cost
    monkeypatch.setattr(_cost, "_live_openrouter_prices", lambda: {})
    assert _cost.token_cost_usd(1000, 1000, "no-such-model") is None


# ---------------------------------------------------------------------------
# estimate_workflow
# ---------------------------------------------------------------------------

def test_estimate_workflow_skips_checkpoint_and_deliverable():
    from armance.service.cost import estimate_workflow

    wf = _make_workflow([
        {"id": "step_a", "kind": "meeting", "mode": "light"},
        {"id": "checkpoint", "kind": "human_checkpoint"},
        {"id": "out", "kind": "deliverable"},
    ])
    agents = [_FakeAgent("worker")]
    result = estimate_workflow(wf, agents, "hello world", prices_override=_OVERRIDE)

    cp = next(e for e in result["steps"] if e["id"] == "checkpoint")
    out = next(e for e in result["steps"] if e["id"] == "out")
    assert cp["cost_usd"] == 0.0
    assert out["cost_usd"] == 0.0


def test_estimate_workflow_total_sums_steps():
    from armance.service.cost import estimate_workflow

    wf = _make_workflow([
        {"id": "s1", "kind": "meeting", "mode": "light"},
        {"id": "s2", "kind": "task", "mode": "light"},
    ])
    agents = [_FakeAgent("worker")]
    result = estimate_workflow(wf, agents, "test prompt", prices_override=_OVERRIDE)

    expected = sum(e["cost_usd"] for e in result["steps"] if e["cost_usd"] is not None)
    assert abs(result["total_usd"] - expected) < 1e-9


def test_estimate_workflow_by_provider_sums():
    from armance.service.cost import estimate_workflow

    wf = _make_workflow([
        {"id": "s1", "kind": "meeting", "mode": "light"},
        {"id": "s2", "kind": "task", "mode": "light"},
    ])
    agents = [_FakeAgent("worker", provider="openrouter")]
    result = estimate_workflow(wf, agents, "prompt", prices_override=_OVERRIDE)
    assert abs(sum(result["by_provider"].values()) - result["total_usd"]) < 1e-9


def test_estimate_workflow_zero_priced_model():
    from armance.service.cost import estimate_workflow

    wf = _make_workflow([{"id": "s1", "kind": "meeting", "mode": "light"}])
    agents = [_FakeAgent("worker", model="my-model")]
    override = {"my-model": {"input_per_mtok": 0.0, "output_per_mtok": 0.0}}
    result = estimate_workflow(wf, agents, "prompt", prices_override=override)
    assert result["total_usd"] == 0.0


def test_estimate_workflow_unknown_model_contributes_zero(monkeypatch):
    """Unknown model → cost_usd is None per step; total stays 0."""
    from armance.service import cost as _cost
    monkeypatch.setattr(_cost, "_live_openrouter_prices", lambda: {})

    wf = _make_workflow([{"id": "s1", "kind": "meeting", "mode": "light"}])
    agents = [_FakeAgent("worker", model="no-such-model")]
    result = _cost.estimate_workflow(wf, agents, "prompt")
    assert result["total_usd"] == 0.0
    assert any(e["cost_usd"] is None for e in result["steps"])


# ---------------------------------------------------------------------------
# BudgetExceeded / TokenLedger.check_budget
# ---------------------------------------------------------------------------

def test_check_budget_no_cap_never_raises():
    from armance.service.llm_service import TokenLedger
    ledger = TokenLedger()
    ledger.record("agent", 1_000_000, 1_000_000, cost_usd=999.0)
    ledger.check_budget()


def test_check_budget_under_cap_ok():
    from armance.service.llm_service import TokenLedger
    ledger = TokenLedger(budget_cap_usd=1.0)
    ledger.record("agent", 100, 100, cost_usd=0.50)
    ledger.check_budget()


def test_check_budget_at_cap_raises():
    from armance.service.llm_service import BudgetExceeded, TokenLedger
    ledger = TokenLedger(budget_cap_usd=1.0)
    ledger.record("agent", 100, 100, cost_usd=1.0)
    with pytest.raises(BudgetExceeded, match="budget cap"):
        ledger.check_budget()


def test_check_budget_over_cap_raises():
    from armance.service.llm_service import BudgetExceeded, TokenLedger
    ledger = TokenLedger(budget_cap_usd=0.01)
    ledger.record("agent", 100, 100, cost_usd=0.02)
    with pytest.raises(BudgetExceeded):
        ledger.check_budget()


@pytest.mark.asyncio
async def test_call_with_ledger_raises_budget_exceeded_before_call():
    from armance.service.llm_service import BudgetExceeded, TokenLedger, call_with_ledger

    ledger = TokenLedger(budget_cap_usd=0.001)
    ledger.record("prior", 100, 100, cost_usd=0.002)

    client = MagicMock()
    client.complete = AsyncMock()

    with pytest.raises(BudgetExceeded):
        await call_with_ledger(client, "agent", [], "model", ledger=ledger)
    client.complete.assert_not_called()


# ---------------------------------------------------------------------------
# Config plumbing
# ---------------------------------------------------------------------------

def test_config_budget_cap_default_none():
    from armance.config import Config
    assert Config().budget_cap_usd is None


def test_config_budget_cap_set():
    from armance.config import Config
    assert Config(budget_cap_usd=5.0).budget_cap_usd == 5.0


def test_config_prices_default_empty():
    from armance.config import Config
    assert Config().prices == {}


def test_config_prices_override():
    from armance.config import Config
    cfg = Config(prices={"my-model": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}})
    assert cfg.prices["my-model"]["input_per_mtok"] == 1.0
