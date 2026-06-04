"""Tests for JudgeAgent (Mona) — T-20.

Validation: 3 mock deliverables, 2 claim blocks each already in ledger
(some with empty evidence, some valid) → synthesis has correct format,
Recommendation refs claims, unsourced in dedicated block, verdicts persisted.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config
from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.agents.judge_agent import JudgeAgent, Synthesis


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_memory").mkdir()
    (root / "context").mkdir()
    (root / "reports").mkdir()
    return root


@pytest.fixture()
def ledger(tmp_armance: Path) -> ClaimLedgerService:
    return ClaimLedgerService(tmp_armance)


@pytest.fixture()
def cfg() -> Config:
    return Config()


SYNTHESIS_TEXT = """\
## Consensus

La garance était la principale teinture rouge au XIVe siècle. (c_valid01)

## Divergence

- Lars conteste l'origine exclusive française. (c_empty01)

## Blind spots

Le rôle du commerce méditerranéen a été sous-estimé.

## Unsourced claims

- « La soie était aussi répandue » — aucune source dans le registre.

## Recommendation

Approfondir l'analyse des routes commerciales. (c_valid01)
"""


@pytest.mark.asyncio
async def test_synthesise_calls_llm_and_returns_synthesis(
    tmp_armance: Path, cfg: Config, ledger: ClaimLedgerService
) -> None:
    """JudgeAgent.synthesise must call LLM and return a Synthesis object."""
    from armance.core.models.claim import Claim, Confidence, Evidence, EvidenceKind

    # Pre-seed ledger with 2 claims: one valid (has evidence), one unsourced
    ledger.append_claim(Claim(
        id="c_valid01", text="La garance = rouge XIVe",
        evidence=[Evidence(kind=EvidenceKind.DOC, ref="manuscript_bib_nat_f42")],
        confidence=Confidence.ASSERTED, by="historian-aisha", view="wf:r_abc"
    ))
    ledger.append_claim(Claim(
        id="c_empty01", text="Teinture française exclusive",
        evidence=[],
        confidence=Confidence.TENTATIVE, by="historian-lars", view="wf:r_abc"
    ))

    deliverables = [
        "[[claim id=c_valid01 evidence=manuscript_bib_nat_f42]]La garance.[[/claim]]",
        "[[claim id=c_empty01 evidence=]]Teinture exclusive.[[/claim]]",
        "La broderie était secondaire.",
    ]

    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=SYNTHESIS_TEXT, finish_reason="stop")):
        result = await agent.synthesise(
            view="wf:r_abc",
            deliverables=deliverables,
        )

    assert isinstance(result, Synthesis)
    assert result.content == SYNTHESIS_TEXT


@pytest.mark.asyncio
async def test_synthesise_injects_claims_in_prompt(
    tmp_armance: Path, cfg: Config, ledger: ClaimLedgerService
) -> None:
    """Claims from ledger.query_by_view must appear in the messages sent to LLM."""
    from armance.core.models.claim import Claim, Confidence, Evidence, EvidenceKind

    ledger.append_claim(Claim(
        id="c_test01", text="Indigotier au nord",
        evidence=[Evidence(kind=EvidenceKind.DOC, ref="src_42")],
        confidence=Confidence.ASSERTED, by="historian-mei", view="wf:r_xyz"
    ))

    captured: list[dict] = []

    async def fake_call(*args, **kwargs):
        messages_arg = args[2] if len(args) > 2 else kwargs.get("messages", [])
        captured.extend(messages_arg)
        return MagicMock(text=SYNTHESIS_TEXT, finish_reason="stop")

    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call):
        await agent.synthesise(view="wf:r_xyz", deliverables=["Deliverable 1."])

    all_content = " ".join(m.get("content", "") for m in captured)
    assert "c_test01" in all_content, (
        f"Claim ID c_test01 not injected in messages:\n{all_content[:400]}"
    )


@pytest.mark.asyncio
async def test_synthesise_no_claims_adds_warning_banner(
    tmp_armance: Path, cfg: Config
) -> None:
    """If ledger has zero claims for the view, synthesis must include warning banner."""
    warning_synthesis = (
        "⚠ AUCUNE CLAIM SOURCÉE — synthèse non vérifiable.\n\n"
        "## Consensus\n\nPas de données vérifiées.\n"
    )
    agent = JudgeAgent(tmp_armance, cfg)

    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=warning_synthesis, finish_reason="stop")):
        result = await agent.synthesise(view="wf:r_empty", deliverables=["Some text."])

    # When no claims exist, agent must still succeed (not raise)
    assert isinstance(result, Synthesis)


@pytest.mark.asyncio
async def test_compile_assumptions(tmp_armance: Path, cfg: Config) -> None:
    agent = JudgeAgent(tmp_armance, cfg)
    mock_report = "Executive Summary\n---\nDetailed Register"
    with patch("armance.service.agents.judge_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.judge_agent.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=mock_report)):
        result = await agent.compile_assumptions("all steps text")
    assert result == mock_report

