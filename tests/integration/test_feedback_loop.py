"""T-25g: FeedbackLoopSkill — workflow output → L0 v+1.

Spec: docs/spec/22_circular_outputs.md § 2. Skill feedback_loop
"""
from __future__ import annotations


from armance.service.skills.feedback_loop import FeedbackLoopSkill
from armance.service.context_service import ContextService


SYNTHESIS = """\
## Consensus
The project should adopt a light-weight approach.

## Divergence

## Recommendation
Start with a pilot.
"""


def _setup_armance(tmp_path):
    """Create minimal .armance structure with one L0 file."""
    ctx = ContextService(tmp_path)
    ctx.write_l0(
        body="## L0\n\n### Goal\nInitial brief.",
        slug="initial",
        confirmed_by_user=True,
    )
    return ctx


def test_skill_has_expected_attributes() -> None:
    assert FeedbackLoopSkill.slash == "/feedback-loop"
    assert any("intègre" in p for p in FeedbackLoopSkill.nl_patterns)
    assert FeedbackLoopSkill.triggered_by == "user"


def test_propose_presents_diff(tmp_path) -> None:
    """propose() shows a diff-like preview without writing."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    reply = skill.propose(synthesis=SYNTHESIS, run_id="r_test1")
    # Must mention the run and show some proposal
    assert "r_test1" in reply or "contexte" in reply.lower() or "L0" in reply
    # Nothing written yet
    ctx = ContextService(tmp_path)
    v = ctx.read_l0_body()
    assert "pilot" not in v  # synthesis not merged yet


def test_confirm_writes_new_l0(tmp_path) -> None:
    """confirm() writes L0 v+1 with confirmed_by_user=True."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    skill.propose(synthesis=SYNTHESIS, run_id="r_test2")
    skill.confirm()

    ctx = ContextService(tmp_path)
    l0_body = ctx.read_l0_body()
    assert l0_body  # something written

    # Find the new L0 file and check frontmatter
    l0_dir = tmp_path / "context" / "L0"
    files = sorted(l0_dir.glob("*.md"))
    assert len(files) >= 2, f"Expected at least 2 L0 versions, got {files}"
    latest = files[-1].read_text()
    assert "confirmed_by_user: true" in latest


def test_confirm_writes_derived_from(tmp_path) -> None:
    """New L0 frontmatter includes derived_from pointing to the run."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    skill.propose(synthesis=SYNTHESIS, run_id="r_test3")
    skill.confirm()

    l0_dir = tmp_path / "context" / "L0"
    files = sorted(l0_dir.glob("*.md"))
    latest = files[-1].read_text()
    assert "r_test3" in latest or "derived_from" in latest


def test_decline_writes_nothing(tmp_path) -> None:
    """decline() writes no new L0 and returns acknowledgement."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    skill.propose(synthesis=SYNTHESIS, run_id="r_test4")
    reply = skill.decline()

    l0_dir = tmp_path / "context" / "L0"
    files = list(l0_dir.glob("*.md"))
    assert len(files) == 1, "Decline must not write a new version"
    assert "r_test4" in reply or "modifié" in reply.lower() or "feedback-loop" in reply


def test_run_entry_point_confirm(tmp_path) -> None:
    """run() with 'oui' after propose → confirm path."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    skill.propose(synthesis=SYNTHESIS, run_id="r_test5")
    skill.run(args="oui")

    l0_dir = tmp_path / "context" / "L0"
    files = sorted(l0_dir.glob("*.md"))
    assert len(files) >= 2


def test_run_entry_point_decline(tmp_path) -> None:
    """run() with 'non' after propose → decline path."""
    _setup_armance(tmp_path)
    skill = FeedbackLoopSkill(armance_root=tmp_path, config=None)
    skill.propose(synthesis=SYNTHESIS, run_id="r_test6")
    skill.run(args="non")

    l0_dir = tmp_path / "context" / "L0"
    files = list(l0_dir.glob("*.md"))
    assert len(files) == 1
