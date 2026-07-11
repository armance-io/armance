"""Lot H — Creuset quality report generator.

Covers: per-criterion scores + verdict + weighted mean, iteration count,
paired draft divergences ↔ resolution, families-per-stage, degraded-flag
disambiguation (G3 in-flight vs G4 mono-family), and the non-crucible no-op.
"""
from __future__ import annotations

import json
from pathlib import Path

from armance.service.workflow_quality_report import (
    build_crucible_report,
    render_crucible_report_md,
)


def _write(run_dir: Path, step_id: str, content: str) -> None:
    (run_dir / f"step-{step_id}.md").write_text(content, encoding="utf-8")


def _crucible_manifest(steps: list[dict], **extra) -> dict:
    base = {"workflow": "wf", "run_id": "run-1", "status": "completed", "steps": steps}
    base.update(extra)
    return base


def _full_crucible_run(tmp_path: Path, *, gate_verdict: str = "ACCEPT") -> tuple[dict, Path]:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    _write(run_dir, "draft_a", "Draft A body")
    _write(run_dir, "draft_b", "Draft B body")
    _write(
        run_dir, "critique",
        "## Draft A — forces\nstrong\n\n"
        "## Divergences entre drafts\n"
        "A dit X sur le pricing ; B dit Y sur le pricing.\n",
    )
    _write(
        run_dir, "synthesis",
        "Le livrable final.\n\n"
        "## Divergences résolues\n"
        "Le pricing a été tranché en faveur de X parce que la marge le permet.\n",
    )
    _write(
        run_dir, "gate",
        "| Criterion | Score |\n|---|---|\n"
        "| Couverture | 8/10 |\n"
        "| Différenciation | 7.5/10 |\n"
        "| Clarté | 9/10 |\n\n"
        f"[GATE:{gate_verdict}]\n"
        "Raisons : couverture solide, différenciation limite.\n",
    )
    steps = [
        {"id": "draft_a", "stage": "draft", "family": "anthropic", "status": "completed",
         "output_path": "step-draft_a.md"},
        {"id": "draft_b", "stage": "draft", "family": "google", "status": "completed",
         "output_path": "step-draft_b.md"},
        {"id": "critique", "stage": "critique", "family": "openai", "status": "completed",
         "output_path": "step-critique.md"},
        {"id": "synthesis", "stage": "synthesis", "family": "anthropic", "status": "completed",
         "output_path": "step-synthesis.md"},
        {"id": "gate", "stage": "gate", "family": "google", "status": "completed",
         "output_path": "step-gate.md", "gate_threshold": 7.5},
    ]
    return _crucible_manifest(steps), run_dir


def test_report_scores_verdict_and_families(tmp_path: Path) -> None:
    manifest, run_dir = _full_crucible_run(tmp_path)
    report = build_crucible_report(manifest, run_dir)
    assert report is not None
    assert report.families_by_stage["draft_a"] == "anthropic"
    assert report.families_by_stage["draft_b"] == "google"
    assert report.families_by_stage["critique"] == "openai"
    assert report.families_by_stage["synthesis"] == "anthropic"
    assert report.families_by_stage["gate"] == "google"
    assert len(report.gates) == 1
    ev = report.gates[0]
    assert ev.verdict == "ACCEPT"
    assert ev.scores == {"Couverture": 8.0, "Différenciation": 7.5, "Clarté": 9.0}
    assert ev.weighted_mean == round((8.0 + 7.5 + 9.0) / 3, 2)
    assert report.iterations == 0
    assert report.threshold_met is True


def test_report_paired_divergences(tmp_path: Path) -> None:
    manifest, run_dir = _full_crucible_run(tmp_path)
    report = build_crucible_report(manifest, run_dir)
    assert report is not None
    assert "pricing" in report.draft_divergences
    assert "tranché" in report.resolved_divergences
    md = render_crucible_report_md(report)
    assert "Désaccords entre drafts" in md
    assert "pricing" in md
    assert "tranché" in md
    # Scores + verdict + families all appear in the rendered markdown.
    assert "Couverture" in md
    assert "8/10" in md
    assert "ACCEPT" in md
    assert "anthropic" in md and "google" in md and "openai" in md


def test_report_iteration_count_after_one_revision(tmp_path: Path) -> None:
    """A fired second gate → 1 revision; a below-threshold last verdict flags."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    _write(run_dir, "gate_1", "| Criterion | Score |\n|---|---|\n| X | 5/10 |\n\n[GATE:REVISE]\ntrop faible")
    _write(run_dir, "gate_2", "| Criterion | Score |\n|---|---|\n| X | 6/10 |\n\n[GATE:REVISE]\nencore faible")
    steps = [
        {"id": "draft_a", "stage": "draft", "family": "anthropic", "status": "completed"},
        {"id": "draft_b", "stage": "draft", "family": "google", "status": "completed"},
        {"id": "gate_1", "stage": "gate", "family": "google", "status": "completed",
         "output_path": "step-gate_1.md"},
        {"id": "gate_2", "stage": "gate", "family": "google", "status": "completed",
         "output_path": "step-gate_2.md"},
    ]
    report = build_crucible_report(_crucible_manifest(steps), run_dir)
    assert report is not None
    assert report.iterations == 1
    assert report.threshold_met is False
    md = render_crucible_report_md(report)
    assert "Seuil non atteint" in md


def test_degraded_g4_mono_family(tmp_path: Path) -> None:
    """Both drafts on the same family from the start → G4 named degradation."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    steps = [
        {"id": "draft_a", "stage": "draft", "family": "anthropic", "status": "completed"},
        {"id": "draft_b", "stage": "draft", "family": "anthropic", "status": "completed"},
        {"id": "synthesis", "stage": "synthesis", "family": "anthropic", "status": "completed"},
    ]
    report = build_crucible_report(_crucible_manifest(steps, available_families=1), run_dir)
    assert report is not None
    assert report.degraded is True
    assert "§G4" in report.degraded_reason
    assert "dès le départ" in report.degraded_reason


def test_degraded_g3_in_flight(tmp_path: Path) -> None:
    """A draft failed mid-run → G3 in-flight degradation, distinct from G4."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    steps = [
        {"id": "draft_a", "stage": "draft", "family": "anthropic", "status": "completed"},
        {"id": "draft_b", "stage": "draft", "family": "google", "status": "failed"},
        {"id": "synthesis", "stage": "synthesis", "family": "anthropic", "status": "completed"},
    ]
    report = build_crucible_report(_crucible_manifest(steps), run_dir)
    assert report is not None
    assert report.degraded is True
    assert "§G3" in report.degraded_reason
    assert "en vol" in report.degraded_reason


def test_non_crucible_run_returns_none(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    steps = [
        {"id": "analyse", "stage": "standard", "status": "completed"},
        {"id": "format", "status": "completed"},  # no stage key at all
    ]
    report = build_crucible_report(_crucible_manifest(steps), run_dir)
    assert report is None
    assert render_crucible_report_md(report) == ""


def test_manifest_json_roundtrip(tmp_path: Path) -> None:
    """The report reads a real on-disk finalized manifest.json."""
    manifest, run_dir = _full_crucible_run(tmp_path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    loaded = json.loads((run_dir / "manifest.json").read_text())
    report = build_crucible_report(loaded, run_dir)
    assert report is not None
    assert report.gates[0].verdict == "ACCEPT"
