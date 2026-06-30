"""Regression: SpecialistRunner must tag claims with the correct view (DM vs open-space)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.core.models.task import Task
from armance.service.agents.specialist_runner import SpecialistRunner


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "context").mkdir()
    (root / "shared_memory").mkdir()
    return root


@pytest.fixture()
def aisha() -> Agent:
    return Agent(
        name="Aisha",
        role="historian",
        persona="positivist",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are Aisha.",
    )


@pytest.fixture()
def task() -> Task:
    return Task(prompt="Question ?", role="historian", mode="light")


@pytest.mark.asyncio
async def test_claim_view_is_dm_when_view_provided(
    tmp_armance: Path, aisha: Agent, task: Task
) -> None:
    """Claims emitted in a DM must have view='dm:Aisha', not 'open-space'."""
    cfg = Config()
    response_text = (
        "Réponse. "
        "[[claim id=c_dm01 evidence=src]]"
        "La garance était rouge."
        "[[/claim]]"
    )

    runner = SpecialistRunner(tmp_armance, cfg)

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=response_text, finish_reason="stop")):
        await runner.run(aisha, task, view="dm:Aisha")

    claims_file = tmp_armance / "shared_memory" / "claims.jsonl"
    claim = json.loads(claims_file.read_text().strip())
    assert claim["view"] == "dm:Aisha", (
        f"Claim view should be 'dm:Aisha', got {claim['view']}"
    )


@pytest.mark.asyncio
async def test_claim_view_defaults_to_open_space(
    tmp_armance: Path, aisha: Agent, task: Task
) -> None:
    """Without view arg, claims default to 'open-space'."""
    cfg = Config()
    response_text = (
        "[[claim id=c_os01 evidence=src]]La teinture.[[/claim]]"
    )

    runner = SpecialistRunner(tmp_armance, cfg)

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=response_text, finish_reason="stop")):
        await runner.run(aisha, task)

    claims_file = tmp_armance / "shared_memory" / "claims.jsonl"
    claim = json.loads(claims_file.read_text().strip())
    assert claim["view"] == "open-space"
