"""Tests for L1 per-role save (T-15d).

Covers:
- L1Frontmatter from_yaml / to_yaml / to_file round-trip
- ContextService.write_l1 / read_current_l1 round-trip
- manifest update with current_l1 per role
- SetL1Skill run with role extraction
- Atomic write (temp file + rename)
- Version increment
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.core.models.context import L1Frontmatter
from armance.service.context_service import ContextService
from armance.service.skills.set_l1 import SetL1Skill


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    """Create a minimal .armance-like directory structure."""
    armance_root = tmp_path / "project"
    armance_root.mkdir()
    (armance_root / "context").mkdir()
    return armance_root


# ---------------------------------------------------------------------------
# L1Frontmatter
# ---------------------------------------------------------------------------


class TestL1Frontmatter:
    """Tests for L1Frontmatter dataclass."""

    def test_from_yaml_parses_fields(self) -> None:
        text = """---
version: 2
project_slug: table-basse-chene
context_layer: L1
created_at: 2026-05-02T15:10:00Z
parent_version: 1
role: woodworking
derived_from:
  - workflows/runs/r_x9f4k2pq/final/judge_v001.md
confirmed_by_user: true
confirmed_at: 2026-05-09T17:05:30Z
evidence:
  - {kind: claim, ref: c_a4f9k2pq}
---

# L1: Woodworking

## Goal
Joinery details for the table legs.
"""
        fm, body = L1Frontmatter.from_yaml(text)
        assert fm.version == 2
        assert fm.project_slug == "table-basse-chene"
        assert fm.context_layer == "L1"
        assert fm.parent_version == 1
        assert fm.role == "woodworking"
        assert len(fm.derived_from) == 1
        assert fm.confirmed_by_user is True
        assert len(fm.evidence) == 1
        assert "## Goal" in body

    def test_from_yaml_raises_on_missing_frontmatter(self) -> None:
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            L1Frontmatter.from_yaml("no frontmatter here")

    def test_from_yaml_raises_on_missing_closing_delimiter(self) -> None:
        with pytest.raises(ValueError, match="missing closing --- delimiter"):
            L1Frontmatter.from_yaml("---\nversion: 1\nrole: test")

    def test_to_yaml_round_trip(self) -> None:
        fm = L1Frontmatter(
            version=1,
            project_slug="test-project",
            role="design",
            created_at="2026-05-10T08:00:00Z",
            confirmed_by_user=True,
            confirmed_at="2026-05-10T08:00:00Z",
        )
        yaml_str = fm.to_yaml()
        fm2, _ = L1Frontmatter.from_yaml(f"---\n{yaml_str}\n---\n\nbody")
        assert fm2.version == fm.version
        assert fm2.project_slug == fm.project_slug
        assert fm2.role == fm.role
        assert fm2.confirmed_by_user is True

    def test_to_file_includes_body(self) -> None:
        fm = L1Frontmatter(
            version=1,
            project_slug="test",
            role="woodworking",
            created_at="2026-05-10T08:00:00Z",
        )
        full = fm.to_file("# Hello\n\nBody text.")
        assert "---" in full
        assert "# Hello" in full
        assert "Body text." in full
        assert "role: woodworking" in full


# ---------------------------------------------------------------------------
# ContextService L1 methods
# ---------------------------------------------------------------------------


class TestContextServiceL1:
    """Tests for ContextService L1 write/read."""

    def test_write_l1_creates_file(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking\n\n## Goal\nJoinery details."
        path = svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=True)
        assert path.exists()
        assert path.name.startswith("v001_")
        assert "test" in path.name
        # Verify frontmatter
        text = path.read_text(encoding="utf-8")
        fm, b = L1Frontmatter.from_yaml(text)
        assert fm.role == "woodworking"
        assert fm.version == 1
        assert "## Goal" in b

    def test_write_l1_updates_manifest(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking"
        svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=True)
        manifest_path = tmp_armance / "context" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["current_l1"]["woodworking"] is not None
        assert manifest["current_l1"]["woodworking"].startswith("v001_")

    def test_write_l1_multiple_roles(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        svc.write_l1(role="woodworking", body="wood stuff", slug="wood-test", confirmed_by_user=True)
        svc.write_l1(role="design", body="design stuff", slug="design-test", confirmed_by_user=True)
        manifest_path = tmp_armance / "context" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "woodworking" in manifest["current_l1"]
        assert "design" in manifest["current_l1"]
        assert manifest["current_l1"]["woodworking"] != manifest["current_l1"]["design"]

    def test_read_current_l1_returns_body(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking\n\n## Goal\nJoinery details."
        svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=True)
        result = svc.read_current_l1("woodworking")
        assert result is not None
        assert "## Goal" in result

    def test_read_current_l1_returns_none_when_missing(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        assert svc.read_current_l1("woodworking") is None

    def test_write_l1_version_increment(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        svc.write_l1(role="woodworking", body="v1", slug="test", confirmed_by_user=True)
        svc.write_l1(role="woodworking", body="v2", slug="test", confirmed_by_user=True)
        path2 = svc.write_l1(role="woodworking", body="v3", slug="test", confirmed_by_user=True)
        assert "v003_" in path2.name

    def test_write_l1_atomic_write(self, tmp_armance: Path) -> None:
        """Verify no .tmp_ files remain after write."""
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking"
        svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=True)
        l1_dir = tmp_armance / "context" / "L1" / "woodworking"
        tmp_files = list(l1_dir.glob(".tmp_*"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"

    def test_write_l1_confirmed_by_user_flag(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking"
        path = svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=True)
        text = path.read_text(encoding="utf-8")
        fm, _ = L1Frontmatter.from_yaml(text)
        assert fm.confirmed_by_user is True

    def test_write_l1_unconfirmed(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# L1: Woodworking"
        path = svc.write_l1(role="woodworking", body=body, slug="test", confirmed_by_user=False)
        text = path.read_text(encoding="utf-8")
        fm, _ = L1Frontmatter.from_yaml(text)
        assert fm.confirmed_by_user is False

    def test_write_l1_parent_version(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        svc.write_l1(role="woodworking", body="v1", slug="test", confirmed_by_user=True)
        path2 = svc.write_l1(role="woodworking", body="v2", slug="test", confirmed_by_user=True)
        text = path2.read_text(encoding="utf-8")
        fm, _ = L1Frontmatter.from_yaml(text)
        assert fm.parent_version == 1


# ---------------------------------------------------------------------------
# SetL1Skill
# ---------------------------------------------------------------------------


class TestSetL1Skill:
    """Tests for SetL1Skill."""

    def test_run_without_role_returns_error(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        result = svc.run(args="", ctx={})
        assert "no role specified" in result

    def test_run_with_role_saves_l1(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        svc.set_role("woodworking")
        svc.add_to_buffer("Use mortise-and-tenon joints.")
        result = svc.run(args="", ctx={})
        assert "L1 context saved" in result
        # Verify file exists
        l1_dir = tmp_armance / "context" / "L1" / "woodworking"
        assert any(p.name.startswith("v001_") for p in l1_dir.iterdir())

    def test_run_with_explicit_role_arg(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        svc.add_to_buffer("Use dovetail joints.")
        result = svc.run(args="--role=design", ctx={})
        assert "L1 context saved" in result
        l1_dir = tmp_armance / "context" / "L1" / "design"
        assert any(p.name.startswith("v001_") for p in l1_dir.iterdir())

    def test_run_with_role_in_ctx(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        svc.add_to_buffer("Use Scandinavian finish.")
        result = svc.run(args="", ctx={"role": "woodworking"})
        assert "L1 context saved" in result

    def test_run_clears_buffer(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        svc.set_role("woodworking")
        svc.add_to_buffer("fact 1")
        svc.add_to_buffer("fact 2")
        svc.run(args="", ctx={})
        assert svc._buffer == []

    def test_run_includes_prior_l1_body(self, tmp_armance: Path) -> None:
        svc = SetL1Skill(tmp_armance, None)
        svc.set_role("woodworking")
        # First save
        svc.add_to_buffer("initial fact")
        svc.run(args="", ctx={})
        # Second save
        svc.add_to_buffer("updated fact")
        result = svc.run(args="", ctx={})
        assert "L1 context saved" in result
        # Verify the new file contains the prior body marker
        l1_dir = tmp_armance / "context" / "L1" / "woodworking"
        latest = sorted(l1_dir.glob("v*.md"))[-1]
        text = latest.read_text(encoding="utf-8")
        assert "Previous L1" in text or "initial fact" in text
