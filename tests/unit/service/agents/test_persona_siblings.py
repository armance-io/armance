"""Persona writer must make same-role agents distinct and complementary.

Same role → the writer is told who the siblings are so personas don't echo.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agents.persona_writer import write_personas


def _save(root: Path, **kw) -> Agent:
    a = Agent(provider="openrouter", model="x", system_prompt="", **kw)
    a.save(root / "agents" / f"{a.name}.md")
    return a


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    (r / "agents").mkdir(parents=True)
    (r / "reports").mkdir()
    return r


@pytest.mark.asyncio
async def test_same_role_agents_get_sibling_context(root: Path) -> None:
    """Two `expert` agents → each persona prompt names the other as a sibling
    to differentiate from; the lone `communicant` gets no siblings block."""
    elena = _save(root, name="Elena", role="expert",
                  description="security by design")
    marc = _save(root, name="Marc", role="expert",
                 description="flow integration")
    luc = _save(root, name="Luc", role="communicant",
                description="visual designer")

    captured: dict[str, str] = {}

    async def fake_run(writer_agent, task, *a, **k):
        # task.prompt is the assembled persona prompt; key it by the agent
        # name it targets (present in the "Name: <x>" identity line).
        for nm in ("Elena", "Marc", "Luc"):
            if f"Name: {nm}" in task.prompt:
                captured[nm] = task.prompt
        return type("R", (), {"content": "a rich persona body"})()

    with patch("armance.service.agents.persona_writer.run_specialist",
               new=AsyncMock(side_effect=fake_run)):
        await write_personas([elena, marc, luc], "brief", root, Config())

    # Elena's prompt cites Marc as a same-role sibling, and vice-versa.
    assert "distinctness within the role" in captured["Elena"].lower() or \
           "DISTINCTNESS" in captured["Elena"]
    assert "Marc" in captured["Elena"]
    assert "Elena" in captured["Marc"]
    # Luc is the only communicant → no siblings block, no peer named in it.
    assert "share this same role" not in captured["Luc"]


@pytest.mark.asyncio
async def test_personas_persisted_to_disk(root: Path) -> None:
    elena = _save(root, name="Elena", role="expert", description="x")

    async def fake_run(writer_agent, task, *a, **k):
        return type("R", (), {"content": "Tu es Elena, experte..."})()

    with patch("armance.service.agents.persona_writer.run_specialist",
               new=AsyncMock(side_effect=fake_run)):
        await write_personas([elena], "brief", root, Config())

    body = (root / "agents" / "Elena.md").read_text(encoding="utf-8")
    assert "Tu es Elena" in body
