"""Regression: Malik must answer as a specialist when messaged as a recruited agent.

When current_agent is a non-system agent (e.g. recruited designer),
_cmd_chat must call run_specialist() with that agent's system_prompt,
NOT dispatch to _cmd_hr_chat (recruitment flow).

The bug: system-hr was special-cased, but if the user DMs a recruited
specialist that happens to have Malik's role, the routing falls into
the general _cmd_chat which is fine — but if current_agent is literally
"system-hr" and the user types a non-recruit message, the old code
returned a static "tell me who to recruit" response instead of an LLM reply.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    (root / "sessions").mkdir()
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


def _make_specialist(name: str, role: str, system_prompt: str) -> Agent:
    return Agent(
        name=name,
        domain=role,
        character="positivist",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt=system_prompt,
    )


def _make_ctx(
    armance_root: Path,
    cfg: Config,
    current_agent: str,
    agents: list[Agent],
) -> LoopContext:
    from armance.service.session import Session, SessionState
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
async def test_system_hr_non_recruit_message_calls_llm(
    tmp_armance: Path, cfg: Config
) -> None:
    """If current_agent=system-hr and user sends a question (not a recruit request),
    the service must call the LLM with Malik's system prompt, not return static help text.
    """
    from armance.service.handlers import _cmd_hr_chat

    # Minimal Malik agent
    malik_path = tmp_armance / "agents" / "system-hr.md"
    malik_path.write_text(
        "---\nname: system-hr\ndomain: meta\ncharacter: recruiter\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nreasoning: medium\n---\n"
        "You are Malik, the recruiter for Armance.",
        encoding="utf-8",
    )

    ctx = _make_ctx(tmp_armance, cfg, "system-hr", [])
    ctx.state.current_agent = "system-hr"

    # Mock run_specialist to return a realistic LLM reply
    fake_report = MagicMock()
    fake_report.content = "Je suis Malik. Je peux recruter des spécialistes pour vous."

    with patch(
        "armance.service.chat_handlers.malik.run_specialist",
        new_callable=AsyncMock,
        return_value=fake_report,
    ) as mock_specialist:
        from armance.service.handlers import _cmd_chat
        # Send a conversational (non-recruit) message
        reply = await _cmd_chat("Bonjour, tu peux m'expliquer ton rôle ?", ctx)

    # Must have called the LLM, not returned static help text
    assert mock_specialist.called, "LLM (run_specialist) must be called for non-recruit messages"
    assert "Je suis Malik" in reply


@pytest.mark.asyncio
async def test_recruited_specialist_uses_system_prompt(
    tmp_armance: Path, cfg: Config
) -> None:
    """A recruited historian specialist must answer questions using their LLM + system_prompt,
    not the recruitment flow.
    """
    from armance.service.handlers import _cmd_chat

    aisha = _make_specialist(
        "Aisha",
        "historian",
        "You are Aisha, a positivist medieval historian specialising in textile dyes.",
    )
    ctx = _make_ctx(tmp_armance, cfg, "Aisha", [aisha])

    fake_response = MagicMock(
        text="Au XIVe siècle, la garance était la principale teinture rouge.",
        finish_reason="stop",
    )

    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, return_value=fake_response):
        reply = await _cmd_chat("Quelles teintures au XIVe siècle ?", ctx)

    assert "garance" in reply, f"Got: {reply}"
