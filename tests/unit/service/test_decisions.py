"""T-24: Mona synthesis appends to shared_memory/decisions.md.

After a synthesis, the next agent's digest must contain the decision.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config
from armance.service.agents.judge_agent import JudgeAgent
from armance.service.shared_memory_service import SharedMemoryService


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_memory").mkdir()
    (root / "context").mkdir()
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


SYNTHESIS_TEXT = """\
## Consensus

La garance était rouge. (c_v01)

## Divergence

- Lars conteste. (c_e01)

## Blind spots

Commerce méditerranéen sous-estimé.

## Recommendation

Approfondir les routes commerciales. (c_v01)
"""


@pytest.mark.asyncio
async def test_synthesis_appends_to_decisions_md(
    tmp_armance: Path, cfg: Config
) -> None:
    """After synthesise(), shared_memory/decisions.md must have a new entry."""
    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=SYNTHESIS_TEXT, finish_reason="stop")):
        await agent.synthesise(view="wf:r_abc", deliverables=["Some deliverable."])

    decisions_path = tmp_armance / "shared_memory" / "decisions.md"
    assert decisions_path.exists(), "decisions.md must exist after synthesis"
    content = decisions_path.read_text(encoding="utf-8")
    assert "La garance était rouge" in content, (
        f"Synthesis content not in decisions.md:\n{content[:400]}"
    )


@pytest.mark.asyncio
async def test_decisions_appear_in_next_agent_digest(
    tmp_armance: Path, cfg: Config
) -> None:
    """Decision written to decisions.md must appear in the next digest."""
    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=SYNTHESIS_TEXT, finish_reason="stop")):
        await agent.synthesise(view="wf:r_abc", deliverables=["Some deliverable."])

    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("historian-aisha")
    assert "garance" in digest.lower(), (
        f"Decision not in digest:\n{digest[:400]}"
    )


@pytest.mark.asyncio
async def test_multiple_syntheses_append_not_overwrite(
    tmp_armance: Path, cfg: Config
) -> None:
    """Two syntheses must produce 2 entries in decisions.md."""
    synthesis2 = "## Consensus\n\nL'indigotier était bleu. (c_blue01)\n## Recommendation\n\nVérifier."

    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=SYNTHESIS_TEXT, finish_reason="stop")):
        await agent.synthesise(view="wf:r_abc", deliverables=["D1."])

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=synthesis2, finish_reason="stop")):
        await agent.synthesise(view="wf:r_xyz", deliverables=["D2."])

    decisions_path = tmp_armance / "shared_memory" / "decisions.md"
    content = decisions_path.read_text(encoding="utf-8")
    assert "garance" in content.lower()
    assert "indigotier" in content.lower()
