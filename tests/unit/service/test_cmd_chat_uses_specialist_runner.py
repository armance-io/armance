"""Regression: _cmd_chat for specialist agents must use SpecialistRunner
(for L0+L1 injection and claim emission), not run_meeting.

T-15d spec: specialist prompt = caveman + system_prompt + L0 + L1[role]
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from armance.client.tui.types import LoopContext, AgentStatus
from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.session import SessionState


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    (root / "shared_memory").mkdir()
    (root / "sessions").mkdir()
    (root / "reports").mkdir()
    # Write L1 for historian role
    l1_dir = root / "context" / "L1" / "historian"
    l1_dir.mkdir(parents=True)
    l1_file = l1_dir / "v001_2026-01-01_textiles.md"
    l1_file.write_text(
        "---\nversion: 1\nproject_slug: textiles\ncontext_layer: L1\nrole: historian\n"
        "created_at: '2026-01-01T00:00:00+00:00'\nconfirmed_by_user: true\n---\n"
        "## Textile dyes\n\nGarance was the main red dye in the 14th century.",
        encoding="utf-8",
    )
    # Write manifest pointing to L1
    (root / "context" / "manifest.json").write_text(
        json.dumps({
            "current_l0": None,
            "current_l1": {"historian": "v001_2026-01-01_textiles.md"},
            "updated_at": "2026-01-01T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def aisha(tmp_armance: Path) -> Agent:
    a = Agent(
        name="Aisha",
        domain="historian",
        character="positivist",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are Aisha.",
    )
    (tmp_armance / "agents" / "Aisha-positivist.md").write_text(
        "---\nname: Aisha\ndomain: historian\ncharacter: positivist\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nreasoning: medium\n---\n"
        "You are Aisha.",
        encoding="utf-8",
    )
    return a


@pytest.fixture()
def cfg() -> Config:
    return Config()


def _make_ctx(
    armance_root: Path, cfg: Config, current_agent: str, agents: list[Agent]
) -> LoopContext:
    from armance.service.session import Session
    state = SessionState.new()
    state.current_agent = current_agent
    session = Session(state, armance_root)
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=MagicMock(),
        statuses=[AgentStatus(name=a.name) for a in agents],
        agents=agents,
    )


@pytest.mark.asyncio
async def test_specialist_dm_injects_l1_in_system_prompt(
    tmp_armance: Path, cfg: Config, aisha: Agent
) -> None:
    """DM with specialist must include L1[role] in the system prompt."""
    from armance.service.handlers import _cmd_chat

    ctx = _make_ctx(tmp_armance, cfg, "Aisha", [aisha])

    captured: list[dict] = []

    async def fake_call(*args, **kwargs):
        # Capture messages arg
        messages_arg = args[2] if len(args) > 2 else kwargs.get("messages", [])
        captured.extend(messages_arg)
        return MagicMock(text="La garance était rouge.", finish_reason="stop")

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call):
        reply = await _cmd_chat("Quelles teintures au XIVe ?", ctx)

    sys_msgs = [m for m in captured if m.get("role") == "system"]
    assert sys_msgs, "No system message captured"
    sys_content = sys_msgs[0]["content"]
    assert "Garance" in sys_content, (
        f"L1 body (Garance...) not in system prompt. Got:\n{sys_content[:300]}"
    )


@pytest.mark.asyncio
async def test_specialist_dm_caveman_explicit(
    tmp_armance: Path, cfg: Config, aisha: Agent
) -> None:
    """A2H invariant: DM with a specialist never uses a compression
    protocol — not even when the user asks for it by name. Compression
    is A2A-only (workflow steps)."""
    from armance.service.handlers import _cmd_chat

    # Test default: no caveman requested
    ctx = _make_ctx(tmp_armance, cfg, "Aisha", [aisha])
    captured_default: list[dict] = []

    async def fake_call_default(*args, **kwargs):
        messages_arg = args[2] if len(args) > 2 else kwargs.get("messages", [])
        captured_default.extend(messages_arg)
        return MagicMock(text="Response", finish_reason="stop")

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call_default):
        await _cmd_chat("Teintures ?", ctx)

    sys_content_default = captured_default[0]["content"]
    assert "Response protocol — caveman" not in sys_content_default

    # Even an explicit request must NOT switch the human-facing register.
    ctx = _make_ctx(tmp_armance, cfg, "Aisha", [aisha])
    captured_caveman: list[dict] = []

    async def fake_call_caveman(*args, **kwargs):
        messages_arg = args[2] if len(args) > 2 else kwargs.get("messages", [])
        captured_caveman.extend(messages_arg)
        return MagicMock(text="Response", finish_reason="stop")

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call_caveman):
        await _cmd_chat("Teintures ? Parle en mode caveman ultra.", ctx)

    sys_content_caveman = captured_caveman[0]["content"]
    assert "Response protocol — caveman" not in sys_content_caveman
    assert "Direct Human Dialogue" in sys_content_caveman


@pytest.mark.asyncio
async def test_specialist_dm_excludes_other_agents_user_turns(
    tmp_armance: Path, cfg: Config, aisha: Agent
) -> None:
    """Regression (P1 leak): a user turn directed at Malik (system-hr) must
    NOT appear in a specialist's LLM history. Before the agent_visibility
    fix, every user turn leaked into every agent's history, so a specialist
    would see (and regurgitate) recruitment chatter."""
    from armance.service.handlers import _cmd_chat

    ctx = _make_ctx(tmp_armance, cfg, "Aisha", [aisha])
    # Seed history: a framing turn (Armance) + a recruitment turn (Malik).
    ctx.session.conversation.append(
        "user", "Conference sur le climat, focus vegetation.", agent="system-context"
    )
    ctx.session.conversation.append(
        "user", "Change le modele de Aisha en gpt-oss.", agent="system-hr"
    )

    captured: list[dict] = []

    async def fake_call(*args, **kwargs):
        messages_arg = args[2] if len(args) > 2 else kwargs.get("messages", [])
        captured.extend(messages_arg)
        return MagicMock(text="Bonjour.", finish_reason="stop")

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, side_effect=fake_call):
        await _cmd_chat("Presente-toi.", ctx)

    user_contents = [m["content"] for m in captured if m.get("role") == "user"]
    # Recruitment turn directed at Malik must be filtered out.
    assert "Change le modele de Aisha en gpt-oss." not in user_contents
    # Framing turn (Armance) is inherited.
    assert any("Conference sur le climat" in c for c in user_contents)

