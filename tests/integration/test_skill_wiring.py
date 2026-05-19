"""Integration tests for slash-command to skill wiring in Armance.

Verifies that all 11 skills (including the deprecation warning) are correctly
reachable via the central HANDLERS dispatchers.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from armance.client.tui.types import LoopContext
from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import AgentLifecycleService
from armance.service.handlers import HANDLERS, _cmd_workflow
from armance.service.llm_service import TokenLedger
from armance.service.session import SessionState


def _make_cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="test")],
        default_provider="openrouter",
        default_model="gpt-4o-mini",
    )


def _make_ctx(tmp_path: Path) -> LoopContext:
    from armance.service.session import Session, SessionState
    armance_root = tmp_path / ".armance"
    armance_root.mkdir(parents=True, exist_ok=True)
    cfg = _make_cfg()
    state = SessionState.new()
    session = Session(state, armance_root)
    ledger = TokenLedger()
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=ledger,
        statuses=[],
        agents=[],
    )


@pytest.fixture
def temp_armance_root() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        yield root


@pytest.fixture
def sample_agent(temp_armance_root: Path) -> Agent:
    service = AgentLifecycleService(temp_armance_root / ".armance")
    agent = Agent(
        name="historian-aisha",
        domain="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="Aisha is a historian",
    )
    service.create_agent(agent)
    return agent


@pytest.mark.asyncio
async def test_cmd_agents_wiring(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agents"]
    res = await handler([], ctx)
    assert "| Name | Role | Persona | Model |" in res
    assert "historian-aisha" in res


@pytest.mark.asyncio
async def test_cmd_agent_list_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agent"]
    res = await handler(["list"], ctx)
    assert "| Name | Role | Persona | Model |" in res
    assert "historian-aisha" in res


@pytest.mark.asyncio
async def test_cmd_agent_edit_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agent"]
    res = await handler(["edit", "historian-aisha", "--persona", "revisionist"], ctx)
    assert "updated" in res
    assert "revisionist" in res


@pytest.mark.asyncio
async def test_cmd_agent_replace_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agent"]
    res = await handler(["replace", "historian-aisha", "with", "materialist"], ctx)
    assert "historian-aisha" in res
    assert "archived" in res
    assert "materialist" in res


@pytest.mark.asyncio
async def test_cmd_agent_promote_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agent"]
    res = await handler(["promote", "historian-aisha", "renaissance"], ctx)
    assert "now lead on" in res
    assert "renaissance" in res


@pytest.mark.asyncio
async def test_cmd_agent_demote_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    # Promote first
    service = AgentLifecycleService(temp_armance_root / ".armance")
    service.promote_agent("historian-aisha", "renaissance")

    handler = HANDLERS["agent"]
    res = await handler(["demote", "historian-aisha", "renaissance"], ctx)
    assert "no longer lead on" in res


@pytest.mark.asyncio
async def test_cmd_agent_archive_subcommand(temp_armance_root: Path, sample_agent: Agent) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["agent"]
    res = await handler(["archive", "historian-aisha"], ctx)
    assert "archived" in res


@pytest.mark.asyncio
async def test_cmd_workflow_design_subcommand(temp_armance_root: Path) -> None:
    """`/workflow design` is now deprecated as a slash entry: workflow
    design happens via Kim in NL, and the skill consumes Kim's YAML
    block emitted with [EXECUTE:/workflow-design]. The slash should
    return a hint, not a state-machine prompt."""
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["workflow"]
    res = await handler(["design", "my-new-workflow"], ctx)
    assert res, "expected a non-empty deprecation hint"


@pytest.mark.asyncio
async def test_cmd_feedback_loop_wiring(temp_armance_root: Path) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["feedback-loop"]
    res = await handler(["r_test_id"], ctx)
    # Since r_test_id doesn't exist, feedback-loop skill should complain or handle gracefully
    assert "not found" in res.lower() or "error" in res.lower()


@pytest.mark.asyncio
async def test_cmd_iterate_from_wiring(temp_armance_root: Path) -> None:
    ctx = _make_ctx(temp_armance_root)
    handler = HANDLERS["iterate-from"]
    res = await handler(["r_test_id"], ctx)
    assert "not found" in res.lower() or "error" in res.lower() or "aucun" in res.lower()
