"""Tests for SpecialistRunner — L0/L1 context injection and claim emission."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    (root / "reports").mkdir()
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


@pytest.fixture()
def aisha() -> Agent:
    return Agent(
        name="Aisha",
        role="historian",
        persona="positivist",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are Aisha, a positivist medieval historian.",
    )


@pytest.fixture()
def task() -> Task:
    return Task(
        prompt="Quelles teintures au XIVe siècle ?",
        role="historian",
        mode="light",
    )


# ---------------------------------------------------------------------------
# L0 injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_specialist_runner_injects_l0(
    tmp_armance: Path, cfg: Config, aisha: Agent, task: Task
) -> None:
    """SpecialistRunner must include L0 body in the system prompt."""
    # Write a real L0 file
    l0_dir = tmp_armance / "context" / "L0"
    l0_dir.mkdir(parents=True)
    l0_file = l0_dir / "v001_2026-01-01_expo-mediev.md"
    l0_file.write_text(
        "---\nversion: 1\nproject_slug: expo-mediev\ncontext_layer: L0\n"
        "created_at: '2026-01-01T00:00:00+00:00'\nconfirmed_by_user: true\n---\n"
        "## L0\n\n### Goal\nPréparer une expo médiévale.",
        encoding="utf-8",
    )
    # Point manifest to this file
    import json
    (tmp_armance / "context" / "manifest.json").write_text(
        json.dumps({"current_l0": "v001_2026-01-01_expo-mediev.md", "current_l1": {},
                    "updated_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )

    captured_messages: list = []

    async def fake_call_with_ledger(client, name, messages, model, **kwargs):
        captured_messages.extend(messages)
        return MagicMock(text="La garance était rouge.", finish_reason="stop")

    runner = SpecialistRunner(tmp_armance, cfg)

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call_with_ledger):
        report = await runner.run(aisha, task)

    # System prompt must contain the L0 body
    sys_msg = next(m for m in captured_messages if m["role"] == "system")
    assert "expo médiévale" in sys_msg["content"], (
        f"L0 body not injected. System prompt:\n{sys_msg['content']}"
    )
    assert report.content == "La garance était rouge."


@pytest.mark.asyncio
async def test_specialist_runner_no_l0_still_runs(
    tmp_armance: Path, cfg: Config, aisha: Agent, task: Task
) -> None:
    """SpecialistRunner must not crash when no L0 exists."""
    runner = SpecialistRunner(tmp_armance, cfg)

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text="No L0, but still works.", finish_reason="stop")):
        report = await runner.run(aisha, task)

    assert "still works" in report.content


# ---------------------------------------------------------------------------
# Claim emission (T-15f)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_specialist_runner_emits_claims(
    tmp_armance: Path, cfg: Config, aisha: Agent, task: Task
) -> None:
    """Claims in LLM response must be appended to claims.jsonl."""
    (tmp_armance / "shared_memory").mkdir()

    response_with_claim = (
        "La garance était rouge. "
        "[[claim id=c_abc evidence=period_sources]]"
        "La cochenille vient d'Amérique."
        "[[/claim]]"
    )

    runner = SpecialistRunner(tmp_armance, cfg)

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock,
               return_value=MagicMock(text=response_with_claim, finish_reason="stop")):
        await runner.run(aisha, task)

    claims_file = tmp_armance / "shared_memory" / "claims.jsonl"
    assert claims_file.exists(), "claims.jsonl must be created"
    lines = claims_file.read_text().strip().split("\n")
    assert len(lines) == 1
    import json
    claim = json.loads(lines[0])
    assert claim["by"] == "Aisha"
    assert "cochenille" in claim["text"]
