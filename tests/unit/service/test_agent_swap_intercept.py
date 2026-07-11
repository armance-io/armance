"""Malik's `/agent-swap` tag: parse, intercept, role-scoping, roster health."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agent_sandbox import scrub_reply
from armance.service.agents._team_roster import build_team_roster
from armance.service.agents.agent_swap import _AGENT_SWAP_RE, handle_agent_swap


def _save(root: Path, name: str, **kw) -> Agent:
    a = Agent(name=name, role="expert", provider="openrouter", model="m",
              system_prompt="persona", **kw)
    a.save(root / "agents" / f"{name}.md")
    return a


def test_tag_regex_parses_name_and_models() -> None:
    m = _AGENT_SWAP_RE.search(
        "[EXECUTE:/agent-swap:Elena custom-openai/qwen3:free openrouter/o3]"
    )
    assert m
    assert m.group(1).split() == ["Elena", "custom-openai/qwen3:free", "openrouter/o3"]


def test_specialist_cannot_emit_agent_swap() -> None:
    """The tag is Malik-only — a specialist's reply is scrubbed of it."""
    raw = "Sure. [EXECUTE:/agent-swap:Elena openrouter/x]"
    assert "agent-swap" not in scrub_reply(raw, agent_role="specialist")
    # Malik keeps it.
    assert "agent-swap" in scrub_reply(raw, agent_role="malik")


@pytest.mark.asyncio
async def test_handle_agent_swap_applies_and_strips_tag(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "agents").mkdir(parents=True)
    _save(root, "Elena")
    ctx = SimpleNamespace(armance_root=root, cfg=Config(), agents=[Agent.load(root / "agents" / "Elena.md")])

    reply = "Je répare le modèle.\n[EXECUTE:/agent-swap:Elena custom-openai/gpt-5]"
    with patch("armance.service.agents.health.check_agent_health",
               new=AsyncMock(return_value=type("H", (), {"status": "ok"})())), \
         patch("armance.service.agents.health.persist_health"):
        out = await handle_agent_swap(reply, ctx)

    assert "[EXECUTE:/agent-swap" not in out  # tag stripped
    assert "gpt-5" in out  # status line appended
    # In-memory roster refreshed.
    assert ctx.agents[0].model == "gpt-5"
    # Persisted.
    assert Agent.load(root / "agents" / "Elena.md").model == "gpt-5"


@pytest.mark.asyncio
async def test_handle_agent_swap_unknown_name(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "agents").mkdir(parents=True)
    ctx = SimpleNamespace(armance_root=root, cfg=Config(), agents=[])
    out = await handle_agent_swap("[EXECUTE:/agent-swap:Ghost openrouter/x]", ctx)
    assert "[EXECUTE:/agent-swap" not in out
    assert "Ghost" in out  # unknown note surfaced


def test_roster_shows_health_for_malik_only(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "agents").mkdir(parents=True)
    _save(root, "Elena", last_health="error:400")
    _save(root, "Marc", last_health="ok")

    malik_view = build_team_roster(root, "system-hr", show_health=True)
    # Malik's view carries the family tag (§G2) then the health marker.
    assert "Elena" in malik_view and "⚠ (error:400)" in malik_view
    assert "Marc ⚠" not in malik_view  # healthy → no marker

    specialist_view = build_team_roster(root, "Luc", show_health=False)
    assert "⚠" not in specialist_view  # lean view, no health
