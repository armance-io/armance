from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.core.models.workflow import load_workflow
from armance.service.checkpoint import CheckpointResponse
from armance.service.cost import estimate_workflow
from armance.service.handlers import _cmd_workflow_run
from armance.service.llm_service import TokenLedger
from armance.service.loop_context import LoopContext
from armance.service.session import Session, SessionState


@pytest.fixture
def cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="t")],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
        prices={
            "anthropic/claude-3.5-sonnet": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
            "anthropic/claude-opus-4-5": {"input_per_mtok": 15.0, "output_per_mtok": 75.0},
        }
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir(parents=True)
    (tmp_path / ".armance" / "workflows").mkdir(parents=True)
    (tmp_path / "context" / "L0").mkdir(parents=True)
    return tmp_path


def _write_wf(root: Path, name: str, body: str) -> Path:
    wf_path = root / ".armance" / "workflows" / f"{name}.yaml"
    wf_path.write_text(body)
    return wf_path


@pytest.mark.asyncio
async def test_workflow_estimate_and_run_boost(root: Path, cfg: Config):
    _write_wf(
        root,
        "boost_wf",
        "name: boost_wf\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: step_a\n"
        "    kind: task\n"
        "    role: helper\n"
        "    agents: [Sara]\n",
    )

    # Agent with boost model configured
    agent = Agent(
        name="Sara",
        provider="openrouter",
        model="anthropic/claude-3.5-sonnet",
        role="helper",
        boost_provider="openrouter",
        boost_model="anthropic/claude-opus-4-5",
    )

    # Let's verify estimate_workflow has boosted_count = 0 in standard mode
    wf = load_workflow(root / ".armance" / "workflows" / "boost_wf.yaml")
    est_normal = estimate_workflow(wf, [agent], "test prompt", prices_override=cfg.prices, intense=False)
    assert est_normal["boosted_count"] == 0

    # Let's verify estimate_workflow has boosted_count = 1 in intense mode
    est_intense = estimate_workflow(wf, [agent], "test prompt", prices_override=cfg.prices, intense=True)
    assert est_intense["boosted_count"] == 1
    # Cost should reflect the boost model (Opus vs Sonnet)
    assert est_intense["total_usd"] > est_normal["total_usd"]

    state = SessionState.new()
    session = Session(state, root)
    ctx = LoopContext(
        armance_root=root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=TokenLedger(),
        statuses=[],
        agents=[agent],
    )

    # We mock specialist execution and run_specialist to avoid calling real APIs
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="yes", is_abort=False)
    ctx.checkpoint_handler = mock_ch

    # Run in quick mode: agent should NOT be auto-boosted
    assert "Sara" not in ctx.state.boosted_agents
    await _cmd_workflow_run(
        "boost_wf",
        enrich_sid=None,
        ctx=ctx,
        skip_preflight=True,
        user_prompt_override="test",
        run_mode="interactive",
        depth="quick",
    )
    assert "Sara" not in ctx.state.boosted_agents

    # Run in deep mode: agent SHOULD be auto-boosted
    await _cmd_workflow_run(
        "boost_wf",
        enrich_sid=None,
        ctx=ctx,
        skip_preflight=True,
        user_prompt_override="test",
        run_mode="interactive",
        depth="deep",
    )
    assert "Sara" in ctx.state.boosted_agents
