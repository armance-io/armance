"""Tests for SharedMemoryService — T-06.

Validation use case: roster with 3 specialists; pending_addressed={"malik":[entry]}.
Call digest_for_agent("malik") → digest contains project brief, roster lines, 1 pending entry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.service.shared_memory_service import (
    SharedMemoryService,
    RosterService,
)


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_memory").mkdir()
    (root / "context").mkdir()
    # Write a simple L0 for project brief
    l0_dir = root / "context" / "L0"
    l0_dir.mkdir(parents=True)
    l0_file = l0_dir / "v001_2026-01-01_textiles.md"
    l0_file.write_text(
        "---\nversion: 1\nproject_slug: textiles\ncontext_layer: L0\n"
        "created_at: '2026-01-01T00:00:00+00:00'\n---\n"
        "## Brief\n\nExpo médiévale textiles.",
        encoding="utf-8",
    )
    (root / "context" / "manifest.json").write_text(
        json.dumps({
            "current_l0": "v001_2026-01-01_textiles.md",
            "current_l1": {},
            "updated_at": "2026-01-01T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    return root


def _write_roster(armance_root: Path) -> None:
    """Write a roster with 3 historians."""
    import yaml  # type: ignore[import-untyped]

    roster = {
        "specialists": [
            {
                "canonical": "historian-aisha",
                "role": "historian",
                "persona": "positivist",
                "provider": "openrouter",
                "model": "openai/gpt-4o",
                "recruited_at": "2026-01-01T00:00:00Z",
            },
            {
                "canonical": "historian-lars",
                "role": "historian",
                "persona": "revisionist",
                "provider": "anthropic",
                "model": "anthropic/claude-3.5-sonnet",
                "recruited_at": "2026-01-01T00:00:00Z",
            },
            {
                "canonical": "historian-mei",
                "role": "historian",
                "persona": "cultural",
                "provider": "google",
                "model": "google/gemini-1.5-pro",
                "recruited_at": "2026-01-01T00:00:00Z",
            },
        ]
    }
    roster_path = armance_root / "shared_memory" / "roster.yaml"
    roster_path.write_text(yaml.safe_dump(roster, allow_unicode=True), encoding="utf-8")


def _write_pending_addressed(armance_root: Path) -> None:
    """Write a pending_addressed.json with one entry for malik."""
    entry = {
        "from_": "armance",
        "to": "system-hr",
        "view": "open-space",
        "snippet": "recrute des historiens",
        "ts": "2026-01-01T10:00:00Z",
        "picked_up": False,
    }
    pending = {"system-hr": [entry]}
    path = armance_root / "shared_memory" / "pending_addressed.json"
    path.write_text(json.dumps(pending), encoding="utf-8")


# ---------------------------------------------------------------------------
# SharedMemoryService
# ---------------------------------------------------------------------------

def test_digest_contains_project_brief(tmp_armance: Path) -> None:
    """digest_for_agent must include L0 project brief."""
    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("system-context")
    assert "Expo médiévale textiles" in digest, f"Brief not in digest:\n{digest[:400]}"


def test_digest_contains_roster(tmp_armance: Path) -> None:
    """digest_for_agent must include roster when non-empty."""
    _write_roster(tmp_armance)
    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("system-hr")
    assert "historian-aisha" in digest, f"Roster not in digest:\n{digest[:400]}"
    assert "historian-lars" in digest
    assert "historian-mei" in digest


def test_digest_contains_pending_addressed(tmp_armance: Path) -> None:
    """digest_for_agent must include pending @-mentions for that agent."""
    _write_pending_addressed(tmp_armance)
    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("system-hr")
    assert "recrute des historiens" in digest, (
        f"Pending entry not in digest:\n{digest[:400]}"
    )


def test_digest_no_pending_for_other_agent(tmp_armance: Path) -> None:
    """Pending entries for malik must NOT appear in Aisha's digest."""
    _write_pending_addressed(tmp_armance)
    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("historian-aisha")
    assert "recrute des historiens" not in digest, (
        "Malik's pending entries leaked into Aisha's digest"
    )


def test_digest_empty_shared_memory_no_crash(tmp_armance: Path) -> None:
    """digest_for_agent must not crash when shared_memory is empty."""
    svc = SharedMemoryService(tmp_armance)
    digest = svc.digest_for_agent("historian-aisha")
    assert isinstance(digest, str)


# ---------------------------------------------------------------------------
# RosterService
# ---------------------------------------------------------------------------

def test_roster_refresh_loads_agents_dir(tmp_armance: Path) -> None:
    """RosterService.refresh() rewrites roster.yaml from agents/ directory."""
    from armance.core.models.agent import Agent

    agents_dir = tmp_armance / "agents"
    agents_dir.mkdir()
    aisha = Agent(
        name="historian-aisha",
        domain="historian",
        character="positivist",
        provider="openrouter",
        model="openai/gpt-4o",
    )
    aisha.save(agents_dir / "historian-aisha.md")

    svc = RosterService(tmp_armance)
    svc.refresh()

    roster_path = tmp_armance / "shared_memory" / "roster.yaml"
    assert roster_path.exists(), "roster.yaml not written after refresh()"
    content = roster_path.read_text(encoding="utf-8")
    assert "historian-aisha" in content


def test_roster_refresh_excludes_archived(tmp_armance: Path) -> None:
    """RosterService.refresh() excludes archived agents."""
    from armance.core.models.agent import Agent

    agents_dir = tmp_armance / "agents"
    agents_dir.mkdir()
    aisha = Agent(
        name="historian-aisha",
        domain="historian",
        character="positivist",
        provider="openrouter",
        model="openai/gpt-4o",
        status="archived",
    )
    aisha.save(agents_dir / "historian-aisha.md")

    svc = RosterService(tmp_armance)
    svc.refresh()

    roster_path = tmp_armance / "shared_memory" / "roster.yaml"
    if roster_path.exists():
        content = roster_path.read_text(encoding="utf-8")
        assert "historian-aisha" not in content, (
            "Archived agent must not appear in roster"
        )
