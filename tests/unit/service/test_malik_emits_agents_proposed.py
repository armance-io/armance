"""C.6 — Malik emits `agents_proposed` event on `[EXECUTE:/recruit]`.

When the Malik chat handler intercepts a `[EXECUTE:/recruit]` tag, it
parses the YAML, writes the agent files via RecruiterAgentService, and
then — if `ctx.event_bus` is set — emits an `agents_proposed` event so
the web frontend can render a recruitment confirmation panel.

The event carries the structured list of newly-created agents (name,
role, persona label, provider, model). The TUI does not set
`event_bus`; the test that follows confirms the emit is a no-op there.

Spec: web-c-deliberation.md § C.6
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.client.tui.types import LoopContext, AgentStatus
from armance.config import Config
from armance.core.models.agent import Agent


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    (root / "sessions").mkdir()
    return root


def _make_ctx(armance_root: Path, *, bus: object | None) -> LoopContext:
    from armance.service.session import Session, SessionState

    state = SessionState.new()
    state.current_agent = "system-hr"
    session = Session(state, armance_root)
    return LoopContext(
        armance_root=armance_root,
        cfg=Config(),
        state=state,
        session=session,
        ledger=MagicMock(),
        statuses=[],
        agents=[],
        event_bus=bus,
    )


def _recruit_yaml() -> str:
    return (
        "```yaml\n"
        "agents:\n"
        "  - name: Aisha\n"
        "    persona: positivist\n"
        "    role: historian\n"
        "    description: sticks to primary sources\n"
        "    provider: openrouter\n"
        "    model: google/gemma-2-9b-it:free\n"
        "  - name: Lars\n"
        "    persona: revisionist\n"
        "    role: historian\n"
        "    description: challenges established narratives\n"
        "    provider: openrouter\n"
        "    model: meta-llama/llama-3.1-8b-instruct:free\n"
        "```\n"
    )


def _build_created_agents() -> list[Agent]:
    return [
        Agent(
            name="Aisha",
            domain="historian",
            role="historian",
            provider="openrouter",
            model="google/gemma-2-9b-it:free",
            description="sticks to primary sources",
        ),
        Agent(
            name="Lars",
            domain="historian",
            role="historian",
            provider="openrouter",
            model="meta-llama/llama-3.1-8b-instruct:free",
            description="challenges established narratives",
        ),
    ]


@pytest.mark.asyncio
async def test_malik_emits_agents_proposed_when_bus_present(tmp_armance: Path) -> None:
    """When ctx.event_bus is set, `agents_proposed` is emitted with the parsed list."""
    from armance.service.chat_handlers.malik import _handle_recruit

    bus = MagicMock()
    bus.emit = AsyncMock()
    ctx = _make_ctx(tmp_armance, bus=bus)

    hr = MagicMock()
    created = _build_created_agents()
    hr.recruit_agents = MagicMock(return_value=(created, ["Aisha", "Lars"]))
    hr.last_new_names = ["Aisha", "Lars"]
    hr.last_updated_names = []
    hr.last_staff_updates = []
    hr.last_skipped_collisions = []

    reply = f"Voici l'équipe.\n[EXECUTE:/recruit]\n{_recruit_yaml()}"

    with patch(
        "armance.service.agents.persona_writer.write_personas",
        new=AsyncMock(),
    ):
        await _handle_recruit(reply, ctx, hr)

    # The bus.emit was called with the agents_proposed event name.
    assert bus.emit.await_count >= 1
    names_emitted = [c.args[0] for c in bus.emit.await_args_list]
    assert "agents_proposed" in names_emitted

    # Inspect the agents_proposed payload.
    call = next(c for c in bus.emit.await_args_list if c.args[0] == "agents_proposed")
    attrs = call.kwargs.get("attributes") or {}
    agents_payload = attrs.get("agents")
    assert isinstance(agents_payload, list)
    assert len(agents_payload) == 2
    names_in_payload = {a["name"] for a in agents_payload}
    assert names_in_payload == {"Aisha", "Lars"}
    # Each entry carries the contract fields.
    for entry in agents_payload:
        assert "name" in entry
        assert "role" in entry
        assert "provider" in entry
        assert "model" in entry


@pytest.mark.asyncio
async def test_malik_no_emit_when_bus_absent(tmp_armance: Path) -> None:
    """When ctx.event_bus is None (TUI), no emit attempt is made."""
    from armance.service.chat_handlers.malik import _handle_recruit

    ctx = _make_ctx(tmp_armance, bus=None)
    hr = MagicMock()
    created = _build_created_agents()
    hr.recruit_agents = MagicMock(return_value=(created, ["Aisha", "Lars"]))
    hr.last_new_names = ["Aisha", "Lars"]
    hr.last_updated_names = []
    hr.last_staff_updates = []
    hr.last_skipped_collisions = []

    reply = f"Voici l'équipe.\n[EXECUTE:/recruit]\n{_recruit_yaml()}"

    with patch(
        "armance.service.agents.persona_writer.write_personas",
        new=AsyncMock(),
    ):
        out = await _handle_recruit(reply, ctx, hr)
    # No event_bus → handler completes normally.
    assert "Voici l'équipe" in out
