"""Kim run-intent safety net — syntax normalization tests.

Verifies that we normalize malformed tags and retrieve the latest workflow name properly,
without any eager keyword-based intent parsing.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from armance.service.chat_handlers.kim import (
    _latest_workflow_name,
)


def _make_ctx(tmp_path: Path, *, with_workflow: bool = True):
    ctx = MagicMock()
    ctx.armance_root = tmp_path
    wf_dir = tmp_path / ".armance" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    if with_workflow:
        (wf_dir / "dossier-historique.yaml").write_text("name: dossier-historique\nsteps: []\n")
    return ctx


def test_latest_workflow_returned(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    assert _latest_workflow_name(ctx) == "dossier-historique"


def test_normalise_tool_call_run_rewrites_to_canonical() -> None:
    """Weak LLM emits `<tool_call>execute:workflow-run:NAME:MODE` instead of
    the canonical `[EXECUTE:/workflow-run:NAME:MODE]`. Normaliser rewrites
    so the intercept fires the real runner."""
    from armance.service.chat_handlers.kim import _normalise_tool_call_run
    raw = (
        "Quelque chose…\n"
        "<tool_call>execute:workflow-run:dossier-historique:autonome\n"
    )
    out = _normalise_tool_call_run(raw)
    assert "[EXECUTE:/workflow-run:dossier-historique:autonome]" in out
    assert "<tool_call>" not in out


def test_normalise_handles_missing_slash_variant() -> None:
    """`[EXECUTE:workflow-run:X]` (no leading slash) also normalised."""
    from armance.service.chat_handlers.kim import _normalise_tool_call_run
    out = _normalise_tool_call_run("[EXECUTE:workflow-run:foo]")
    assert "[EXECUTE:/workflow-run:foo]" in out


def test_normalise_preserves_canonical_tag() -> None:
    """No-op when the canonical tag is already present."""
    from armance.service.chat_handlers.kim import _normalise_tool_call_run
    canonical = "[EXECUTE:/workflow-run:foo:autonomous]"
    out = _normalise_tool_call_run(canonical + "\nfoo")
    assert out.count("[EXECUTE:/workflow-run:foo") == 1
