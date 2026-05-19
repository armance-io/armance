"""Regression tests for /save buffer injection (Bug #2).

_cmd_save must inject ctx.state.context_buffer into the
HostAgentService before freezing, so the saved L0 contains
the facts Armance accumulated during dialogue.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.client.tui.types import LoopContext, AgentStatus
from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.session import SessionState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    (root / "sessions").mkdir()
    # Write a minimal system-context agent so Agent.load works
    agent_md = root / "agents" / "system-context.md"
    agent_md.write_text(
        "---\nname: system-context\ndomain: meta\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nreasoning: medium\n---\n"
        "You are Armance, the host.",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


def _make_ctx(armance_root: Path, cfg: Config, buffer: list[str]) -> LoopContext:
    from armance.service.session import Session, SessionState
    state = SessionState.new()
    session = Session(state, armance_root)
    session.metadata["host_buffer"] = buffer
    ledger = MagicMock()
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=ledger,
        statuses=[],
        agents=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_save_injects_buffer_into_l0(tmp_armance: Path, cfg: Config) -> None:
    """/save must write the context_buffer content into the L0 file."""
    from armance.service.handlers import _cmd_save

    user_facts = ["On prépare une expo médiévale pour juin 2026. L'objectif est d'attirer 5000 visiteurs."]
    ctx = _make_ctx(tmp_armance, cfg, buffer=user_facts)

    with patch("armance.service.agents.host_agent.get_client") as mock_gc, \
         patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
        
        mock_response = MagicMock()
        mock_response.text = "## Goal\nOn prépare une expo médiévale pour juin 2026."
        mock_call.return_value = mock_response

        result = await _cmd_save([], ctx)

    l0_dir = tmp_armance / "context" / "L0"
    l0_files = list(l0_dir.glob("v*.md"))
    assert len(l0_files) == 1, f"Expected 1 L0 file, got {l0_files}"

    content = l0_files[0].read_text(encoding="utf-8")
    assert "expo" in content, (
        "L0 body must contain buffer content, got:\n" + content
    )


@pytest.mark.asyncio
async def test_cmd_save_clears_buffer_from_state(tmp_armance: Path, cfg: Config) -> None:
    """/save must succeed when the buffer content is sufficiently long."""
    from armance.service.handlers import _cmd_save

    ctx = _make_ctx(tmp_armance, cfg, buffer=["We are building a highly advanced, ultra-secure financial auditing platform for international corporations."])
    
    with patch("armance.service.agents.host_agent.get_client") as mock_gc, \
         patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
        
        mock_response = MagicMock()
        mock_response.text = "## Goal\nWe are building a highly advanced, ultra-secure financial auditing platform."
        mock_call.return_value = mock_response

        result = await _cmd_save([], ctx)
        
    assert "error" not in result.lower(), f"save returned error: {result}"


@pytest.mark.asyncio
async def test_cmd_save_empty_or_trivial_buffer_is_rejected(tmp_armance: Path, cfg: Config) -> None:
    """/save with empty or trivial buffer must be rejected."""
    from armance.service.handlers import _cmd_save

    # Empty buffer
    ctx = _make_ctx(tmp_armance, cfg, buffer=[])
    result = await _cmd_save([], ctx)
    assert "error: context is too brief" in result

    # Bare greeting
    ctx2 = _make_ctx(tmp_armance, cfg, buffer=["Salut, bonjour, hello!"])
    result2 = await _cmd_save([], ctx2)
    assert "error: context is too brief" in result2
