"""Integration tests for L0 save flow (T-15c).

Covers:
- /save writes context/L0/v001_<date>_<slug>.md
- Frontmatter has confirmed_by_user: true
- Body has Goal section
- Legacy project_brief.md migration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from armance.service.skills.set_brief import SetBriefSkill
from armance.config import Config


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    """Create a minimal project directory."""
    armance_root = tmp_path / "project"
    armance_root.mkdir()
    (armance_root / "context").mkdir()
    (armance_root / "shared_memory").mkdir()
    return armance_root


@pytest.fixture()
def config() -> Config:
    return Config()


@pytest.fixture()
def save_skill(tmp_armance: Path, config: Config) -> SetBriefSkill:
    return SetBriefSkill(
        armance_root=tmp_armance,
        config=config,
    )


class TestSaveSkill:
    """Tests for SetBriefSkill.run()."""

    def test_save_creates_l0_file(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        save_skill.add_to_buffer("User wants to build a medieval expo.")
        result = save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_files = list(l0_dir.glob("v*.md"))
        assert len(l0_files) == 1
        assert "v001_" in l0_files[0].name

    def test_save_includes_goal_section(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        save_skill.add_to_buffer("We need historians and sociologists.")
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_file = list(l0_dir.glob("v*.md"))[0]
        content = l0_file.read_text(encoding="utf-8")
        assert "## Goal" in content

    def test_save_sets_confirmed_by_user(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        save_skill.add_to_buffer("Project brief text.")
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_file = list(l0_dir.glob("v*.md"))[0]
        text = l0_file.read_text(encoding="utf-8")
        assert "confirmed_by_user: true" in text

    def test_save_updates_manifest(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        import json
        save_skill.add_to_buffer("Test brief.")
        save_skill.run()
        manifest_path = tmp_armance / "context" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest.get("current_l0") is not None

    def test_save_migrates_legacy_brief(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        legacy = tmp_armance / "shared_memory" / "project_brief.md"
        legacy.write_text("# Old Brief\n\nLegacy content.", encoding="utf-8")
        result = save_skill.run()
        # Should have migrated
        l0_dir = tmp_armance / "context" / "L0"
        l0_files = list(l0_dir.glob("v*.md"))
        assert len(l0_files) >= 1
        # Legacy file should be archived
        archive = tmp_armance / "shared_memory" / ".archive" / "project_brief.md"
        assert archive.exists()

    def test_save_clears_buffer(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        save_skill.add_to_buffer("First fact.")
        save_skill.run()
        # Buffer should be cleared after save
        assert len(save_skill._buffer) == 0

    def test_save_multiple_versions(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        save_skill.add_to_buffer("First version.")
        save_skill.run()
        save_skill.add_to_buffer("Second version update.")
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_files = sorted(l0_dir.glob("v*.md"))
        assert len(l0_files) == 2
        assert "v001_" in l0_files[0].name
        assert "v002_" in l0_files[1].name

    def test_save_empty_body_includes_l0_header_and_goal(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        """Regression: /save with no buffer and no prior L0 must still produce a non-empty body."""
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_file = list(l0_dir.glob("v*.md"))[0]
        content = l0_file.read_text(encoding="utf-8")
        # Must contain ## L0 header
        assert "## L0" in content
        # Must contain Goal section (not frontmatter-only)
        assert "### Goal" in content
        # Must not be frontmatter-only
        assert "Project context to be defined" in content or "Goal" in content

    def test_save_with_buffer_includes_l0_header(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        """Save with buffer must include ## L0 header and Updated facts section."""
        save_skill.add_to_buffer("Build a medieval expo.")
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_file = list(l0_dir.glob("v*.md"))[0]
        content = l0_file.read_text(encoding="utf-8")
        assert "## L0" in content
        assert "### Updated facts" in content
        assert "medieval expo" in content

    def test_save_empty_buffer_and_no_prior_l0_produces_goal_section(self, save_skill: SetBriefSkill, tmp_armance: Path) -> None:
        """Regression: both buffer and prior L0 empty — body must still contain ### Goal."""
        save_skill.run()
        l0_dir = tmp_armance / "context" / "L0"
        l0_file = list(l0_dir.glob("v*.md"))[0]
        content = l0_file.read_text(encoding="utf-8")
        # Must have frontmatter
        assert content.startswith("---")
        # Must have ### Goal section (not frontmatter-only)
        assert "### Goal" in content
        # Must have the placeholder text
        assert "Project context to be defined" in content
        # Body must not be empty (file should have more than just frontmatter)
        lines = content.split("\n")
        # Find body after closing ---
        body_start = None
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 0:
                body_start = i + 1
                break
        assert body_start is not None
        body = "\n".join(lines[body_start:])
        assert body.strip()  # body must not be empty/whitespace