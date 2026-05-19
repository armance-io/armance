"""Tests for ChallengerAgent (Serge) — T-25a.

Validates:
- critique() returns a Critique with 4 blocks
- Serge can downgrade a verified claim to disputed
- Cross-family check refuses single-family configs
- serge_inconclusive flagged when zero objections
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.claim import Claim, Confidence, ClaimStatus
from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.agents.challenger_agent import (
    ChallengerAgent,
    CrossFamilyConfigError,
    Critique,
)


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_memory").mkdir()
    return root


@pytest.fixture()
def multi_family_cfg() -> Config:
    """Config with two provider families — cross-family check passes."""
    return Config(
        providers=[
            ProviderConfig(name="openrouter", api_key="sk-or-test"),
            ProviderConfig(name="gemini", api_key="AIza-test"),
        ],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
    )


@pytest.fixture()
def single_family_cfg() -> Config:
    """Config with single provider family — Serge must raise."""
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="sk-or-test")],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
    )


SYNTHESIS_TEXT = """\
## Consensus
La garance était rouge. (c_v01)

## Recommendation
Approfondir l'analyse. (c_v01)
"""

CRITIQUE_TEXT = """\
## Assumptions
1. La garance était universellement disponible.
2. Les sources primaires sont représentatives.

## Counter-samples
- Le nord de la France utilisait principalement l'indigotier (c_e01 — evidence manquante).

## Groupthink risks
Le panel partage un biais vers les sources françaises centrales. Risque d'angle mort régional.

## Decisive question
Quelle proportion de sources du panel provient des régions septentrionales?
"""

ZERO_OBJECTION_TEXT = """\
## Assumptions
None identified.

## Counter-samples
No counter-samples.

## Groupthink risks
Minimal risk.

## Decisive question
Are there other angles to explore?
"""


@pytest.mark.asyncio
async def test_critique_returns_four_block_artifact(
    tmp_armance: Path, multi_family_cfg: Config
) -> None:
    """critique() must return a Critique with content."""
    agent = ChallengerAgent(
        tmp_armance, multi_family_cfg,
        executor_families=["openai"],
        mona_family="openai",
        serge_family="google",
    )

    with patch("armance.service.agents.challenger_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.challenger_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=CRITIQUE_TEXT, finish_reason="stop")), \
         patch("armance.service.agents.challenger_agent.ChallengerAgent._init_rag") as m_rag:
        
        m_rag.return_value.conn.cursor.return_value.execute.return_value.fetchone.return_value = (0,)
        result = await agent.critique(
            view="wf:r_abc",
            target=SYNTHESIS_TEXT,
        )

    assert isinstance(result, Critique)
    assert "Assumptions" in result.content
    assert "Decisive question" in result.content


@pytest.mark.asyncio
async def test_serge_downgrades_verified_claim(
    tmp_armance: Path, multi_family_cfg: Config
) -> None:
    """Serge can downgrade a verified claim to disputed via the ledger."""
    from armance.core.models.claim import Evidence, EvidenceKind

    ledger = ClaimLedgerService(tmp_armance)
    claim = Claim(
        id="c_v01", text="Garance rouge",
        evidence=[Evidence(kind=EvidenceKind.DOC, ref="ms_42")],
        confidence=Confidence.ASSERTED, by="historian-aisha", view="wf:r_abc"
    )
    ledger.append_claim(claim)
    # Mark it verified first
    ledger.verify_claim("c_v01", verdict=ClaimStatus.VERIFIED, by="system-judge", rationale="Confirmed.")

    agent = ChallengerAgent(
        tmp_armance, multi_family_cfg,
        executor_families=["openai"],
        mona_family="openai",
        serge_family="google",
    )

    with patch("armance.service.agents.challenger_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.challenger_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=CRITIQUE_TEXT, finish_reason="stop")), \
         patch("armance.service.agents.challenger_agent.ChallengerAgent._init_rag") as m_rag:

        m_rag.return_value.conn.cursor.return_value.execute.return_value.fetchone.return_value = (0,)
        await agent.critique(view="wf:r_abc", target=SYNTHESIS_TEXT, dispute_ids=["c_v01"])

    # Reload ledger from disk to get the updated status
    fresh_ledger = ClaimLedgerService(tmp_armance)
    updated = fresh_ledger.get_claims(filter={"view": "wf:r_abc"})[0]
    assert updated.status == ClaimStatus.DISPUTED, (
        f"Expected DISPUTED, got {updated.status}"
    )


def test_cross_family_hard_refusal_single_provider(
    tmp_armance: Path, single_family_cfg: Config
) -> None:
    """ChallengerAgent must raise CrossFamilyConfigError when only one family configured."""
    with pytest.raises(CrossFamilyConfigError) as exc_info:
        ChallengerAgent(
            tmp_armance, single_family_cfg,
            executor_families=["openai"],
            mona_family="openai",
            serge_family="openai",  # same family as executors + Mona
        )
    assert "openai" in str(exc_info.value).lower()


def test_cross_family_ok_different_providers(
    tmp_armance: Path, multi_family_cfg: Config
) -> None:
    """ChallengerAgent must not raise when Serge is on a different family."""
    # Should not raise
    agent = ChallengerAgent(
        tmp_armance, multi_family_cfg,
        executor_families=["openai"],
        mona_family="openai",
        serge_family="google",
    )
    assert agent is not None


@pytest.mark.asyncio
async def test_zero_objections_marks_serge_inconclusive(
    tmp_armance: Path, multi_family_cfg: Config
) -> None:
    """When Serge output has no objections, result.serge_inconclusive must be True."""
    agent = ChallengerAgent(
        tmp_armance, multi_family_cfg,
        executor_families=["openai"],
        mona_family="openai",
        serge_family="google",
    )

    with patch("armance.service.agents.challenger_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.challenger_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=ZERO_OBJECTION_TEXT, finish_reason="stop")), \
         patch("armance.service.agents.challenger_agent.ChallengerAgent._init_rag") as m_rag:
        
        # Mock RAG count to 0 to skip query
        m_rag.return_value.conn.cursor.return_value.execute.return_value.fetchone.return_value = (0,)
        
        result = await agent.critique(view="wf:r_empty", target="No synthesis.")

    assert result.serge_inconclusive is True
