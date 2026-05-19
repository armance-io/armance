"""Regression: /save --layer=L1 must route to SetL1Skill, not SetBriefSkill.

T-15d spec: `/save --layer=L1 --role=historian` writes
context/L1/historian/v001_<date>_*.md
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from armance.client.tui.types import LoopContext, AgentStatus
from armance.config import Config
from armance.service.session import SessionState


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    (root / "sessions").mkdir()
    agent_md = root / "agents" / "system-context.md"
    agent_md.write_text(
        "---\nname: system-context\ndomain: meta\ncharacter: balanced\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nreasoning: medium\n---\nArmance.",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


def _make_ctx(
    armance_root: Path, cfg: Config, buffer: list[str], current_agent: str = "system-context"
) -> LoopContext:
    from armance.service.session import Session, SessionState
    state = SessionState.new()
    session = Session(state, armance_root)
    session.metadata["host_buffer"] = buffer
    state.current_agent = current_agent
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=MagicMock(),
        statuses=[],
        agents=[],
    )


@pytest.mark.asyncio
async def test_save_l1_creates_l1_file(tmp_armance: Path, cfg: Config) -> None:
    """/save --layer=L1 --role=historian must create context/L1/historian/v001_*.md."""
    from armance.service.handlers import _cmd_save

    ctx = _make_ctx(tmp_armance, cfg, buffer=["Facts about medieval textiles."])

    result = await _cmd_save(["--layer=L1", "--role=historian"], ctx)

    assert "error" not in result.lower(), f"Got error: {result}"
    l1_dir = tmp_armance / "context" / "L1" / "historian"
    l1_files = list(l1_dir.glob("v*.md"))
    assert len(l1_files) == 1, f"Expected 1 L1 file, got {l1_files}"
    assert "v001_" in l1_files[0].name


@pytest.mark.asyncio
async def test_save_l1_without_layer_flag_writes_l0(tmp_armance: Path, cfg: Config) -> None:
    """/save (no --layer flag) must still write L0, not L1."""
    from armance.service.handlers import _cmd_save
    from unittest.mock import AsyncMock, patch

    ctx = _make_ctx(tmp_armance, cfg, buffer=["We want to study the conjoint history of France and Scotland during medieval times, specifically focusing on the Auld Alliance."])
    
    with patch("armance.service.agents.host_agent.get_client") as mock_gc, \
         patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
        
        mock_response = MagicMock()
        mock_response.text = "## Goal\nWe want to study the conjoint history of France and Scotland."
        mock_call.return_value = mock_response

        result = await _cmd_save([], ctx)

    assert "error" not in result.lower(), f"Got error: {result}"
    l0_dir = tmp_armance / "context" / "L0"
    l0_files = list(l0_dir.glob("v*.md"))
    assert len(l0_files) == 1
    # Must NOT create L1
    l1_dir = tmp_armance / "context" / "L1"
    assert not l1_dir.exists() or not list(l1_dir.glob("**/*.md"))
