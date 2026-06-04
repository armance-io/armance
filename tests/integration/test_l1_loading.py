"""Integration tests for L1 loading flow (T-15d).

Covers:
- End-to-end: write L0, write L1, specialist runner injects L1 into prompt
- Version bump on L1 re-save
- Manifest tracks current L1 per role
- SpecialistRunner._build_layered_context includes L0 + L1[role]
"""

from __future__ import annotations

from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.core.models.context import ContextManifest
from armance.service.agents.specialist_runner import SpecialistRunner
from armance.service.context_service import ContextService


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    """Create a minimal .armance-like directory structure."""
    armance_root = tmp_path / "project"
    armance_root.mkdir()
    (armance_root / "context").mkdir()
    (armance_root / "reports").mkdir()
    return armance_root


def _make_agent(role: str = "woodworking") -> Agent:
    """Create a minimal test agent with the given role."""
    return Agent(
        name=f"{role}-agent",
        domain=role,
        character="balanced",
        provider="openai",
        model="gpt-4",
        system_prompt=f"You are a {role} specialist.",
    )


# ---------------------------------------------------------------------------
# SpecialistRunner layered context
# ---------------------------------------------------------------------------


class TestSpecialistRunnerContext:
    """Tests for SpecialistRunner L0+L1 context injection."""

    def test_build_layered_context_includes_l0(self, tmp_armance: Path) -> None:
        """SpecialistRunner includes L0 body in layered context."""
        ctx_svc = ContextService(tmp_armance)
        ctx_svc.write_l0(
            body="# Project: Test\n\n## Goal\nBuild something.",
            slug="test",
            confirmed_by_user=True,
        )
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent()
        context = runner._build_layered_context(agent)
        assert "## L0" in context
        assert "## Goal" in context

    def test_build_layered_context_includes_l1(self, tmp_armance: Path) -> None:
        """SpecialistRunner includes L1[role] body in layered context."""
        ctx_svc = ContextService(tmp_armance)
        ctx_svc.write_l0(
            body="# Project: Test\n\n## Goal\nBuild something.",
            slug="test",
            confirmed_by_user=True,
        )
        ctx_svc.write_l1(
            role="woodworking",
            body="# L1: Woodworking\n\n## Goal\nUse mortise-and-tenon joints.",
            slug="test",
            confirmed_by_user=True,
        )
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent(role="woodworking")
        context = runner._build_layered_context(agent)
        assert "## L0" in context
        assert "## L1" in context
        assert "woodworking" in context.lower()
        assert "mortise-and-tenon" in context.lower()

    def test_build_layered_context_no_l1_when_missing(self, tmp_armance: Path) -> None:
        """SpecialistRunner does not include L1 when it doesn't exist."""
        ctx_svc = ContextService(tmp_armance)
        ctx_svc.write_l0(
            body="# Project: Test",
            slug="test",
            confirmed_by_user=True,
        )
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent(role="woodworking")
        context = runner._build_layered_context(agent)
        assert "## L0" in context
        assert "## L1" not in context

    def test_build_layered_context_role_mismatch(self, tmp_armance: Path) -> None:
        """SpecialistRunner only loads L1 matching agent role."""
        ctx_svc = ContextService(tmp_armance)
        ctx_svc.write_l0(
            body="# Project: Test",
            slug="test",
            confirmed_by_user=True,
        )
        ctx_svc.write_l1(
            role="design",
            body="# L1: Design\n\n## Goal\nMinimalist style.",
            slug="test",
            confirmed_by_user=True,
        )
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent(role="woodworking")
        context = runner._build_layered_context(agent)
        assert "## L0" in context
        # L1 for "design" should NOT appear for woodworking agent
        assert "Minimalist" not in context


# ---------------------------------------------------------------------------
# End-to-end: L0 + L1 write + manifest + prompt injection
# ---------------------------------------------------------------------------


class TestL1EndToEnd:
    """End-to-end tests for L1 save and load."""

    def test_full_l1_save_load_cycle(self, tmp_armance: Path) -> None:
        """Write L0, write L1, read L1, verify manifest."""
        ctx_svc = ContextService(tmp_armance)

        # Step 1: Write L0
        l0_path = ctx_svc.write_l0(
            body="# Project: Table\n\n## Goal\nBuild a table.",
            slug="table",
            confirmed_by_user=True,
        )
        assert l0_path.exists()
        assert l0_path.name.startswith("v001_")

        # Step 2: Write L1 for woodworking
        l1_path = ctx_svc.write_l1(
            role="woodworking",
            body="# L1: Woodworking\n\n## Goal\nMortise-and-tenon joints.",
            slug="table",
            confirmed_by_user=True,
        )
        assert l1_path.exists()
        assert l1_path.name.startswith("v001_")
        assert "woodworking" in str(l1_path.parent)

        # Step 3: Verify manifest
        manifest = ContextManifest.from_path(ctx_svc.manifest_path)
        assert manifest.current_l0 is not None
        assert manifest.current_l1.get("woodworking") is not None

        # Step 4: Read L1 body (case-insensitive check)
        l1_body = ctx_svc.read_current_l1("woodworking")
        assert l1_body is not None
        assert "mortise-and-tenon" in l1_body.lower()

        # Step 5: SpecialistRunner sees both L0 and L1
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent(role="woodworking")
        context = runner._build_layered_context(agent)
        assert "# Project: Table" in context
        assert "mortise-and-tenon" in context.lower()

    def test_l1_version_bump_on_resave(self, tmp_armance: Path) -> None:
        """Re-saving L1 increments version and updates manifest."""
        ctx_svc = ContextService(tmp_armance)

        ctx_svc.write_l1(
            role="woodworking",
            body="# L1: Woodworking\n\nv1",
            slug="test",
            confirmed_by_user=True,
        )
        # Read the manifest to get the first version filename
        manifest1 = ContextManifest.from_path(ctx_svc.manifest_path)
        file1 = manifest1.current_l1.get("woodworking")
        assert file1 is not None
        assert "v001_" in file1

        ctx_svc.write_l1(
            role="woodworking",
            body="# L1: Woodworking\n\nv2",
            slug="test",
            confirmed_by_user=True,
        )
        manifest2 = ContextManifest.from_path(ctx_svc.manifest_path)
        file2 = manifest2.current_l1.get("woodworking")
        assert file2 is not None
        assert "v002_" in file2

        # Old file still exists (immutable)
        l1_dir = tmp_armance / "context" / "L1" / "woodworking"
        assert (l1_dir / file1).exists()
        assert (l1_dir / file2).exists()

    def test_l1_prompt_injection_order(self, tmp_armance: Path) -> None:
        """L0 appears before L1 in the layered context."""
        ctx_svc = ContextService(tmp_armance)
        ctx_svc.write_l0(
            body="# Project: Test\n\n## Goal\nL0 content.",
            slug="test",
            confirmed_by_user=True,
        )
        ctx_svc.write_l1(
            role="design",
            body="# L1: Design\n\n## Goal\nL1 content.",
            slug="test",
            confirmed_by_user=True,
        )
        runner = SpecialistRunner(tmp_armance, None)
        agent = _make_agent(role="design")
        context = runner._build_layered_context(agent)
        l0_pos = context.find("## L0")
        l1_pos = context.find("## L1")
        assert l0_pos < l1_pos, "L0 should appear before L1 in context"

    def test_multiple_roles_independent(self, tmp_armance: Path) -> None:
        """Different roles have independent L1 versions."""
        ctx_svc = ContextService(tmp_armance)

        ctx_svc.write_l1(
            role="woodworking",
            body="# L1: Woodworking\n\nwood content",
            slug="wood-test",
            confirmed_by_user=True,
        )
        ctx_svc.write_l1(
            role="design",
            body="# L1: Design\n\ndesign content",
            slug="design-test",
            confirmed_by_user=True,
        )

        # Each role reads its own L1
        wood_body = ctx_svc.read_current_l1("woodworking")
        design_body = ctx_svc.read_current_l1("design")
        assert "wood content" in wood_body
        assert "design content" in design_body
        assert "wood content" not in design_body
        assert "design content" not in wood_body
