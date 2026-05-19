"""Kim run-intent safety net — when the user says 'lance' but Kim
re-emits the workflow YAML, we force the run tag instead of re-saving.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from armance.service.chat_handlers.kim import (
    _inject_run_tag_if_user_says_launch,
    _latest_workflow_name,
    _user_wants_to_run,
)


def _make_ctx(tmp_path: Path, *, with_workflow: bool = True):
    ctx = MagicMock()
    ctx.armance_root = tmp_path
    wf_dir = tmp_path / ".armance" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    if with_workflow:
        (wf_dir / "dossier-historique.yaml").write_text("name: dossier-historique\nsteps: []\n")
    return ctx


def test_user_wants_to_run_recognises_french_and_english() -> None:
    assert _user_wants_to_run("lance le workflow")
    assert _user_wants_to_run("RUN LE WORKFLOW")
    assert _user_wants_to_run("execute it")
    assert _user_wants_to_run("démarre")
    assert _user_wants_to_run("Bordel run")
    assert not _user_wants_to_run("sauvegarde le workflow")
    assert not _user_wants_to_run("non")


def test_latest_workflow_returned(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    assert _latest_workflow_name(ctx) == "dossier-historique"


def test_inject_run_tag_when_user_launches_and_kim_re_emits_yaml(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    reply = (
        "yaml\n"
        "name: dossier-historique\n"
        "steps:\n"
        "  - id: a\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "```\n"
    )
    out = _inject_run_tag_if_user_says_launch(reply, "lance le workflow", ctx)
    assert "[EXECUTE:/workflow-run:dossier-historique]" in out
    # Raw YAML must be cleaned from the user-visible reply.
    assert "name: dossier-historique\nsteps:" not in out


def test_no_inject_when_user_did_not_ask_to_run(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    reply = "Workflow proposé, ok ?"
    out = _inject_run_tag_if_user_says_launch(reply, "ok parfait", ctx)
    assert "[EXECUTE:/workflow-run:" not in out


def test_no_inject_when_no_workflow_exists(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, with_workflow=False)
    out = _inject_run_tag_if_user_says_launch("yaml...", "lance", ctx)
    assert "[EXECUTE:/workflow-run:" not in out


def test_no_inject_when_run_tag_already_present(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    reply = "[EXECUTE:/workflow-run:dossier-historique:interactive]"
    out = _inject_run_tag_if_user_says_launch(reply, "lance", ctx)
    assert out.count("[EXECUTE:/workflow-run:") == 1


def test_no_inject_when_design_tag_present(tmp_path: Path) -> None:
    """Kim legitimately emits a design tag — don't override with run."""
    ctx = _make_ctx(tmp_path)
    reply = "[EXECUTE:/workflow-design]\n```yaml\nname:x\n```"
    out = _inject_run_tag_if_user_says_launch(reply, "lance", ctx)
    assert "[EXECUTE:/workflow-run:" not in out
