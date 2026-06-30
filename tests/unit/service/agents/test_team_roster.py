"""Team-roster injection — every agent must know the whole team.

Covers `build_team_roster` and its wiring into the specialist layered context.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agents._team_roster import build_team_roster
from armance.service.agents.specialist_runner import SpecialistRunner


def _save(root: Path, **kw) -> Agent:
    a = Agent(provider="openrouter", model="x", system_prompt="x", **kw)
    a.save(root / "agents" / f"{a.name}.md")
    return a


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    (r / "agents").mkdir(parents=True)
    (r / "context").mkdir()
    (r / "reports").mkdir()
    return r


def test_roster_lists_peers_grouped_by_role_excluding_self(root: Path) -> None:
    _save(root, name="Elena", role="expert",
          description="security by design")
    _save(root, name="Marc", role="expert",
          description="flow integration")
    _save(root, name="Luc", role="communicant",
          description="visual designer")

    roster = build_team_roster(root, current_name="Elena")

    # Self excluded, peers present, grouped by role (compact, names only).
    assert "Elena" not in roster
    assert "Marc" in roster
    assert "Luc" in roster
    assert "**expert**" in roster and "**communicant**" in roster
    # Token discipline: the per-agent angle is NOT inlined — only a pointer.
    assert "flow integration" not in roster
    assert ".armance/agents/<name>.md" in roster


def test_roster_skips_staff_and_helper_files(root: Path) -> None:
    _save(root, name="Marc", role="expert", description="x")
    # Built-in staff + helper files must not appear in the specialist roster.
    (root / "agents" / "system-judge.md").write_text("---\nname: system-judge\n---\n")
    (root / "agents" / "_armance_concepts.md").write_text("notes")

    roster = build_team_roster(root, current_name="Elena")
    assert "system-judge" not in roster
    assert "_armance_concepts" not in roster
    assert "Marc" in roster


def test_roster_empty_when_alone(root: Path) -> None:
    _save(root, name="Solo", role="expert", description="x")
    assert build_team_roster(root, current_name="Solo") == ""


def test_layered_context_includes_roster(root: Path) -> None:
    _save(root, name="Elena", role="expert", description="security")
    peer = _save(root, name="Marc", role="expert", description="flow")

    runner = SpecialistRunner(armance_root=root, config=Config())
    elena = Agent.load(root / "agents" / "Elena.md")
    ctx = runner._build_layered_context(elena)

    assert "## Your team" in ctx
    assert "Marc" in ctx
    assert peer.name in ctx
