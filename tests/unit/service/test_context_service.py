"""Tests for ContextService (T-15c).

Covers:
- write_l0 / read_l0_body round-trip
- manifest update
- slug derivation
- confirmed_by_user flag
- legacy project_brief.md migration
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.core.models.context import L0Frontmatter, ContextManifest
from armance.service.context_service import ContextService


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    """Create a minimal .armance-like directory structure."""
    armance_root = tmp_path / "project"
    armance_root.mkdir()
    (armance_root / "context").mkdir()
    (armance_root / "shared_memory").mkdir()
    return armance_root


class TestL0Frontmatter:
    """Tests for L0Frontmatter dataclass."""

    def test_from_yaml_parses_fields(self) -> None:
        text = """---
version: 3
project_slug: table-basse-chene
context_layer: L0
created_at: 2026-05-02T15:10:00Z
parent_version: 2
roles: [woodworking, design]
summary_token_estimate: 350
derived_from:
  - workflows/runs/r_w8c4k1mn/final/judge_v001.md
confirmed_by_user: true
confirmed_at: 2026-05-02T15:10:30Z
evidence:
  - {kind: claim, ref: c_d8e1f2gh}
---

# Project: Table basse en chêne

## Goal
Build a custom solid-oak coffee table.
"""
        fm, body = L0Frontmatter.from_yaml(text)
        assert fm.version == 3
        assert fm.project_slug == "table-basse-chene"
        assert fm.context_layer == "L0"
        assert fm.parent_version == 2
        assert fm.roles == ["woodworking", "design"]
        assert fm.summary_token_estimate == 350
        assert len(fm.derived_from) == 1
        assert fm.confirmed_by_user is True
        assert len(fm.evidence) == 1
        assert "## Goal" in body

    def test_from_yaml_raises_on_missing_frontmatter(self) -> None:
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            L0Frontmatter.from_yaml("no frontmatter here")

    def test_to_yaml_round_trip(self) -> None:
        fm = L0Frontmatter(
            version=1,
            project_slug="test-project",
            created_at="2026-05-10T08:00:00Z",
            confirmed_by_user=True,
            confirmed_at="2026-05-10T08:00:00Z",
        )
        yaml_str = fm.to_yaml()
        fm2, _ = L0Frontmatter.from_yaml(f"---\n{yaml_str}\n---\n\nbody")
        assert fm2.version == fm.version
        assert fm2.project_slug == fm.project_slug
        assert fm2.confirmed_by_user is True

    def test_to_file_includes_body(self) -> None:
        fm = L0Frontmatter(
            version=1,
            project_slug="test",
            created_at="2026-05-10T08:00:00Z",
        )
        full = fm.to_file("# Hello\n\nBody text.")
        assert "---" in full
        assert "# Hello" in full
        assert "Body text." in full


class TestContextManifest:
    """Tests for ContextManifest dataclass."""

    def test_from_path_empty_file(self, tmp_armance: Path) -> None:
        manifest_path = tmp_armance / "context" / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")
        manifest = ContextManifest.from_path(manifest_path)
        assert manifest.current_l0 is None
        assert manifest.current_l1 == {}

    def test_from_path_populated(self, tmp_armance: Path) -> None:
        manifest_path = tmp_armance / "context" / "manifest.json"
        data = {
            "current_l0": "v001_2026-05-10_test.md",
            "current_l1": {"woodworking": "v001_2026-05-10_wood.md"},
            "active_session": "s_abc123",
            "updated_at": "2026-05-10T08:00:00Z",
        }
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        manifest = ContextManifest.from_path(manifest_path)
        assert manifest.current_l0 == "v001_2026-05-10_test.md"
        assert manifest.current_l1["woodworking"] == "v001_2026-05-10_wood.md"
        assert manifest.active_session == "s_abc123"

    def test_to_path_round_trip(self, tmp_armance: Path) -> None:
        manifest_path = tmp_armance / "context" / "manifest.json"
        manifest = ContextManifest(
            current_l0="v002_2026-05-10_updated.md",
            active_session="s_xyz789",
            updated_at="2026-05-10T09:00:00Z",
        )
        manifest.to_path(manifest_path)
        loaded = ContextManifest.from_path(manifest_path)
        assert loaded.current_l0 == "v002_2026-05-10_updated.md"
        assert loaded.active_session == "s_xyz789"


class TestContextService:
    """Tests for ContextService."""

    def test_write_l0_creates_file(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# Project: Test\n\n## Goal\nBuild something."
        path = svc.write_l0(body=body, slug="test-project", confirmed_by_user=True)
        assert path.exists()
        assert path.name.startswith("v001_")
        assert "test-project" in path.name

    def test_write_l0_updates_manifest(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# Project: Test"
        svc.write_l0(body=body, slug="test", confirmed_by_user=True)
        manifest_path = tmp_armance / "context" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["current_l0"] is not None
        assert manifest["current_l0"].startswith("v001_")

    def test_read_current_l0_returns_none_when_missing(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        assert svc.read_current_l0() is None

    def test_read_l0_body_returns_body(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# Project: Test\n\n## Goal\nBuild something."
        svc.write_l0(body=body, slug="test", confirmed_by_user=True)
        result = svc.read_l0_body()
        assert result is not None
        assert "## Goal" in result

    def test_write_l0_version_increment(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        svc.write_l0(body="v1", slug="test", confirmed_by_user=True)
        svc.write_l0(body="v2", slug="test", confirmed_by_user=True)
        path2 = svc.write_l0(body="v3", slug="test", confirmed_by_user=True)
        assert "v003_" in path2.name

    def test_migrate_legacy_project_brief(self, tmp_armance: Path) -> None:
        legacy = tmp_armance / "shared_memory" / "project_brief.md"
        legacy.write_text("# Legacy Brief\n\nOld content.", encoding="utf-8")
        svc = ContextService(tmp_armance)
        result = svc.migrate_legacy_project_brief()
        assert result is not None
        assert result.exists()
        # Legacy file should be archived
        archive = tmp_armance / "shared_memory" / ".archive" / "project_brief.md"
        assert archive.exists()

    def test_migrate_legacy_project_brief_no_file(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        assert svc.migrate_legacy_project_brief() is None

    def test_write_l0_confirmed_by_user_flag(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# Project: Test"
        path = svc.write_l0(body=body, slug="test", confirmed_by_user=True)
        text = path.read_text(encoding="utf-8")
        fm, _ = L0Frontmatter.from_yaml(text)
        assert fm.confirmed_by_user is True

    def test_write_l0_unconfirmed(self, tmp_armance: Path) -> None:
        svc = ContextService(tmp_armance)
        body = "# Project: Test"
        path = svc.write_l0(body=body, slug="test", confirmed_by_user=False)
        text = path.read_text(encoding="utf-8")
        fm, _ = L0Frontmatter.from_yaml(text)
        assert fm.confirmed_by_user is False


class TestSlugify:
    """Tests for _slugify helper."""

    def test_simple_slug(self) -> None:
        from armance.core.models.context import _slugify
        assert _slugify("Hello World") == "hello-world"

    def test_slug_truncation(self) -> None:
        from armance.core.models.context import _slugify
        long = "a" * 100
        slug = _slugify(long, max_len=20)
        assert len(slug) <= 20

    def test_slug_keeps_accents(self) -> None:
        from armance.core.models.context import _slugify
        slug = _slugify("Exposé médiéval")
        assert "expose" in slug or "exposé" in slug
