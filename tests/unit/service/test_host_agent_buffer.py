"""Regression: Armance must accumulate all user turns in _buffer, not just the first.

The buffer is what /save freezes into L0. If only turn 1 is buffered,
all follow-up project facts are lost.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agents.host_agent import HostAgentService


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


@pytest.fixture()
def armance(tmp_armance: Path, cfg: Config) -> HostAgentService:
    agent = Agent(
        name="system-context",
        role="meta",
        character="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are Armance.",
    )
    svc = HostAgentService(agent=agent, armance_root=tmp_armance, config=cfg)
    return svc


@pytest.mark.asyncio
async def test_buffer_accumulates_multiple_user_turns(
    armance: HostAgentService,
) -> None:
    """After 3 user turns (all non-command), buffer must contain all 3."""
    fake_report = MagicMock()
    fake_report.content = "Compris, je note."
    fake_result = MagicMock()
    fake_result.reports = [fake_report]

    with patch("armance.service.agents.host_agent.get_client", return_value=MagicMock()), \
         patch(
             "armance.service.agents.host_agent.call_with_ledger",
             new_callable=AsyncMock,
             return_value=MagicMock(text="Compris, je note."),
         ):
        await armance.dialogue("On prépare une expo médiévale pour juin 2026.")
        await armance.dialogue("On a besoin d'historiens et de sociologues.")
        await armance.dialogue("Le budget est de 50 000 euros.")

    assert len(armance._buffer) == 3, (
        f"Expected 3 buffer entries, got {armance._buffer}"
    )
    combined = " ".join(armance._buffer)
    assert "expo médiévale" in combined
    assert "historiens" in combined
    assert "budget" in combined


@pytest.mark.asyncio
async def test_buffer_not_duplicated_on_command_turns(
    armance: HostAgentService,
) -> None:
    """/save, /help etc. must NOT be added to the buffer."""
    with patch("armance.service.agents.host_agent.get_client", return_value=MagicMock()), \
         patch(
             "armance.service.agents.host_agent.call_with_ledger",
             new_callable=AsyncMock,
             return_value=MagicMock(text="Compris."),
         ):
        await armance.dialogue("On prépare une expo.")
        await armance.dialogue("/help")

    # Only the first turn (project brief) should be buffered
    combined = " ".join(armance._buffer)
    assert "/help" not in combined
