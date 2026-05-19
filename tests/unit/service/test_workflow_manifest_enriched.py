"""Manifest schema: per-step records + totals + no cost hallucination."""
from __future__ import annotations

import json
from pathlib import Path

from armance.service.workflow_runs import (
    create_run,
    finalise,
    mark_step_completed,
    mark_step_failed,
    mark_step_skipped,
    mark_step_started,
    write_step_output,
)


def test_manifest_records_per_step_status_and_duration(tmp_path: Path) -> None:
    art = create_run(tmp_path, "test-wf")
    mark_step_started(art, "alpha")
    write_step_output(art, "alpha", "alpha output")
    mark_step_completed(art, "alpha", tokens_in=120, tokens_out=80)

    mark_step_started(art, "beta")
    mark_step_failed(art, "beta", "boom")

    mark_step_skipped(art, "gamma", "upstream beta failed")

    finalise(art, status="failed")

    manifest = json.loads(art.manifest_path().read_text())
    by_id = {s["id"]: s for s in manifest["steps"]}
    assert by_id["alpha"]["status"] == "completed"
    assert by_id["alpha"]["tokens_in"] == 120
    assert by_id["alpha"]["tokens_out"] == 80
    assert by_id["beta"]["status"] == "failed"
    assert "boom" in by_id["beta"]["error"]
    assert by_id["gamma"]["status"] == "skipped"


def test_manifest_cost_is_none_when_not_measured(tmp_path: Path) -> None:
    """A step without explicit cost MUST NOT contribute a fake number."""
    art = create_run(tmp_path, "test-wf")
    mark_step_started(art, "alpha")
    mark_step_completed(art, "alpha", tokens_in=10, tokens_out=20)
    finalise(art)

    manifest = json.loads(art.manifest_path().read_text())
    # Totals must show tokens, but cost_usd None (we never estimate).
    assert manifest["totals"]["tokens_in"] == 10
    assert manifest["totals"]["tokens_out"] == 20
    assert manifest["totals"]["cost_usd"] is None


def test_manifest_cost_aggregated_when_all_steps_measured(tmp_path: Path) -> None:
    art = create_run(tmp_path, "test-wf")
    mark_step_started(art, "a")
    mark_step_completed(art, "a", tokens_in=1, tokens_out=1, cost_usd=0.001)
    mark_step_started(art, "b")
    mark_step_completed(art, "b", tokens_in=2, tokens_out=2, cost_usd=0.002)
    finalise(art)

    manifest = json.loads(art.manifest_path().read_text())
    assert manifest["totals"]["cost_usd"] == 0.003


def test_runs_index_carries_totals(tmp_path: Path) -> None:
    art = create_run(tmp_path, "wf2")
    mark_step_started(art, "x")
    mark_step_completed(art, "x", tokens_in=5, tokens_out=5)
    finalise(art)

    runs = json.loads((art.run_dir.parent / "runs.json").read_text())
    assert runs[-1]["totals"]["tokens_in"] == 5
    assert runs[-1]["totals"]["cost_usd"] is None
