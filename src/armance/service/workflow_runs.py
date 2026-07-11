"""Workflow run artefacts: versioned export tree + trace metadata.

Every `/workflow run <name>` produces a new directory:

    .armance/exports/<workflow-name>/run-<YYYYMMDD-HHMMSS>/
        manifest.json         run id, started/ended_at, workflow, step ids
        step-<id>.md          raw output of each step (one file per step)
        trace.md              human-readable agent trace (kept args, dropped,
                              adopted from peer, Serge objections addressed)
        synthesis.md          Mona's final synthesis (if a judge step ran)

A workflow-level `runs.json` lists every run for quick lookup by Mona /
specialists. Previous runs are NEVER overwritten.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """Per-step run metadata. Tokens/cost are nullable — only filled when
    the LLM call returned hard numbers. We DO NOT estimate; an "N/A" is
    preferred to a hallucinated cost."""

    id: str
    status: str = "queued"   # queued | working | completed | failed | skipped
    agent: str | None = None  # who actually spoke (set on completion; failover-aware)
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    output_path: str | None = None
    error: str | None = None
    prompt_file: str | None = None
    template_used: bool | None = None
    # Creuset (Lot H): a step's crucible function (`draft`/`critique`/
    # `synthesis`/`gate`/`standard`) and the provider *family* that actually
    # spoke — carried into the manifest so the quality report can reconstruct
    # families-per-stage and gate scores at report time (no re-resolution).
    stage: str | None = None
    family: str | None = None
    # Lot E.1: non-fatal warnings recorded even when the step ultimately
    # succeeds — e.g. a contradictory second-regard candidate that errored
    # before a same-role peer took over. Keeps the run auditable instead of
    # silently swallowing the lost binôme.
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "agent": self.agent,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "output_path": self.output_path,
            "error": self.error,
            "prompt_file": self.prompt_file,
            "template_used": self.template_used,
            "stage": self.stage,
            "family": self.family,
            "warnings": list(self.warnings),
        }


@dataclass
class RunArtefact:
    """Where a single workflow run lives on disk + its quick metadata."""

    workflow_name: str
    run_id: str
    run_dir: Path
    started_at: str
    ended_at: str = ""
    step_ids: list[str] = field(default_factory=list)
    steps: dict[str, StepRecord] = field(default_factory=dict)
    # Lot I: partial re-run provenance. Each entry references the parent run
    # and the per-step human overrides fed into this run, e.g.
    # {"run_id": <parent>, "overrides": [{"step": "B", "source": "b.md"}]}.
    # A run NEVER overwrites its parent — this makes the derivation auditable.
    derived_from: list[dict[str, Any]] = field(default_factory=list)

    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    def record(self, step_id: str) -> StepRecord:
        """Get-or-create a StepRecord for ``step_id``."""
        if step_id not in self.steps:
            self.steps[step_id] = StepRecord(id=step_id)
        return self.steps[step_id]

    def step_path(self, step_id: str) -> Path:
        safe = re.sub(r"[^\w-]", "_", step_id)[:64]
        return self.run_dir / f"step-{safe}.md"

    def step_prompt_path(self, step_id: str) -> Path:
        safe = re.sub(r"[^\w-]", "_", step_id)[:64]
        return self.run_dir / f"step-{safe}.prompt.md"

    def trace_path(self) -> Path:
        return self.run_dir / "trace.md"

    def synthesis_path(self) -> Path:
        return self.run_dir / "synthesis.md"

    def assumptions_path(self) -> Path:
        return self.run_dir / "assumptions.md"



def create_run(
    armance_root: Path,
    workflow_name: str,
    step_ids: list[str] | None = None,
) -> RunArtefact:
    """Mint a new versioned run directory.

    ``step_ids`` pre-registers every workflow step as `queued` so the
    manifest shows the full DAG from the first snapshot — without it,
    steps never reached (abort, checkpoint timeout) simply don't exist in
    the manifest and the UI can't tell "never ran" from "unknown".
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"run-{ts}"
    safe_wf = re.sub(r"[^\w-]", "_", workflow_name)[:64]
    run_dir = armance_root / "exports" / safe_wf / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    artefact = RunArtefact(
        workflow_name=workflow_name,
        run_id=run_id,
        run_dir=run_dir,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    for sid in step_ids or []:
        artefact.record(sid)
        if sid not in artefact.step_ids:
            artefact.step_ids.append(sid)
    # Register the run as in-flight up-front: an initial manifest + a runs.json
    # entry so /active-workflow reports it immediately and the web UI can switch
    # to the live view before the first step completes.
    write_running_manifest(artefact)
    _append_runs_index(run_dir.parent, _build_manifest(artefact, status="working", finalising=False))
    return artefact


def write_step_output(artefact: RunArtefact, step_id: str, content: str) -> Path:
    """Persist a step's raw output + register its path on the StepRecord."""
    path = artefact.step_path(step_id)
    path.write_text(content, encoding="utf-8")
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    rec = artefact.record(step_id)
    rec.output_path = str(path.relative_to(artefact.run_dir))
    return path


def write_step_prompt(
    artefact: RunArtefact, step_id: str, prompt: str, *, template_used: bool,
) -> Path:
    """Persist the effective prompt rendered for a step (Lot C — auditability).

    Written alongside `step-<id>.md`; referenced in the manifest via
    `prompt_file` + `template_used` so a run is fully rejouable/auditable
    and the future UI (Lot D) has a data source to read from.
    """
    path = artefact.step_prompt_path(step_id)
    path.write_text(prompt, encoding="utf-8")
    rec = artefact.record(step_id)
    rec.prompt_file = str(path.relative_to(artefact.run_dir))
    rec.template_used = template_used
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    return path


def mark_step_started(artefact: RunArtefact, step_id: str) -> None:
    rec = artefact.record(step_id)
    rec.status = "working"
    rec.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    write_running_manifest(artefact)


def mark_step_completed(
    artefact: RunArtefact,
    step_id: str,
    *,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
    agent: str | None = None,
    stage: str | None = None,
    family: str | None = None,
) -> None:
    rec = artefact.record(step_id)
    rec.status = "completed"
    rec.agent = agent or rec.agent
    if stage is not None:
        rec.stage = stage
    if family is not None:
        rec.family = family
    rec.ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec.duration_ms = _ms_between(rec.started_at, rec.ended_at)
    rec.tokens_in = tokens_in
    rec.tokens_out = tokens_out
    rec.cost_usd = cost_usd
    write_running_manifest(artefact)


def mark_step_failed(artefact: RunArtefact, step_id: str, error: str) -> None:
    rec = artefact.record(step_id)
    rec.status = "failed"
    rec.ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec.duration_ms = _ms_between(rec.started_at, rec.ended_at)
    rec.error = error[:500]
    write_running_manifest(artefact)


def mark_step_skipped(artefact: RunArtefact, step_id: str, reason: str) -> None:
    rec = artefact.record(step_id)
    rec.status = "skipped"
    rec.error = reason[:200]
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    write_running_manifest(artefact)


def mark_step_provided(
    artefact: RunArtefact, step_id: str, source: str, *, stage: str | None = None,
) -> None:
    """Mark a step whose output was supplied by a human override (Lot I).

    A `provided` step is NOT re-executed: its output came from a human-edited
    file (partial re-run with override) or was carried verbatim from the parent
    run. Distinct from `skipped` (F5 pass-through) so the report can tell
    "human replaced this" from "run_if said don't run". `source` records the
    override file (or `<parent>` when carried) for auditability.
    """
    rec = artefact.record(step_id)
    rec.status = "provided"
    rec.error = f"override: {source}"[:200]
    if stage is not None:
        rec.stage = stage
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    write_running_manifest(artefact)


def add_step_warning(artefact: RunArtefact, step_id: str, warning: str) -> None:
    """Append a non-fatal warning to a step's manifest record (Lot E.1).

    Used to keep a record of a contradictory candidate that failed even when
    a same-role peer later took over — so the lost second regard is auditable
    instead of vanishing silently.
    """
    rec = artefact.record(step_id)
    rec.warnings.append(warning[:300])
    if step_id not in artefact.step_ids:
        artefact.step_ids.append(step_id)
    write_running_manifest(artefact)


def _ms_between(started_iso: str | None, ended_iso: str | None) -> int | None:
    if not started_iso or not ended_iso:
        return None
    try:
        s = datetime.fromisoformat(started_iso)
        e = datetime.fromisoformat(ended_iso)
        return int((e - s).total_seconds() * 1000)
    except Exception:
        return None


def write_synthesis(artefact: RunArtefact, content: str) -> Path:
    path = artefact.synthesis_path()
    path.write_text(content, encoding="utf-8")
    # D.8 — extract Mona's structured sidecars (arguments.json + sources.json)
    # alongside the synthesis. No-op when the synthesis carries no fenced
    # ```json argument-ledger / source-ledger blocks.
    try:
        from armance.service.argument_ledger import persist_sidecars
        persist_sidecars(content, artefact.run_dir)
    except Exception:
        logger.exception("argument_ledger persist failed for run %s", artefact.run_dir)
    return path


def write_trace(artefact: RunArtefact, content: str) -> Path:
    path = artefact.trace_path()
    path.write_text(content, encoding="utf-8")
    return path


def write_assumptions(artefact: RunArtefact, content: str) -> Path:
    path = artefact.assumptions_path()
    path.write_text(content, encoding="utf-8")
    return path



def _build_manifest(artefact: RunArtefact, *, status: str, finalising: bool) -> dict[str, Any]:
    """Assemble the manifest dict for *artefact* at the current state.

    When *finalising*, a queued step with an output path is upgraded to
    completed (defensive backfill for steps that bypassed mark_step_*);
    a queued step without output never ran — mark it skipped so the UI
    doesn't show it as forever-pending.
    """
    step_records: list[dict[str, Any]] = []
    for sid in artefact.step_ids:
        rec = artefact.record(sid)
        if finalising and rec.status == "queued":
            if rec.output_path:
                rec.status = "completed"
            else:
                rec.status = "skipped"
                rec.error = rec.error or "run ended before this step"
        step_records.append(rec.to_dict())

    return {
        "workflow": artefact.workflow_name,
        "run_id": artefact.run_id,
        "status": status,
        "started_at": artefact.started_at,
        "ended_at": artefact.ended_at,
        "duration_ms": _ms_between(artefact.started_at, artefact.ended_at),
        "steps": step_records,
        "totals": _aggregate(artefact),
        "assumptions_present": artefact.assumptions_path().exists(),
        "synthesis_present": artefact.synthesis_path().exists(),
        "trace_present": artefact.trace_path().exists(),
        "quality_present": (artefact.run_dir / "quality.md").exists(),
        "derived_from": list(artefact.derived_from),
    }


def write_running_manifest(artefact: RunArtefact) -> None:
    """Persist a live snapshot of the manifest (status='working').

    Called after every step transition so the web UI (which polls
    manifest.json) sees steps go queued → working → completed in real time.
    Does NOT touch runs.json — that index is bumped once, by finalise().
    """
    manifest = _build_manifest(artefact, status="working", finalising=False)
    try:
        artefact.manifest_path().write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        logger.warning("could not write running manifest for %s", artefact.run_id, exc_info=True)


def finalise(artefact: RunArtefact, *, status: str = "completed") -> None:
    """Write the per-run manifest + bump the workflow-level runs.json.

    The manifest now records per-step metadata (status, duration, tokens,
    output path, error) and aggregates totals. Cost is never estimated —
    it stays None if the provider didn't return hard pricing numbers.
    """
    artefact.ended_at = datetime.now(timezone.utc).isoformat()
    manifest = _build_manifest(artefact, status=status, finalising=True)
    artefact.manifest_path().write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    _append_runs_index(artefact.run_dir.parent, manifest)


def _aggregate(artefact: RunArtefact) -> dict[str, Any]:
    """Aggregate per-step counts. Cost stays None unless every step has
    a measured cost — partial sums would mislead the user.
    """
    t_in = sum((r.tokens_in or 0) for r in artefact.steps.values())
    t_out = sum((r.tokens_out or 0) for r in artefact.steps.values())
    costs = [r.cost_usd for r in artefact.steps.values()]
    total_cost: float | None = None
    if costs and all(c is not None for c in costs):
        total_cost = round(sum(c for c in costs if c is not None), 6)
    return {
        "steps_total": len(artefact.step_ids),
        "steps_completed": sum(
            1 for r in artefact.steps.values() if r.status == "completed"
        ),
        "steps_failed": sum(
            1 for r in artefact.steps.values() if r.status == "failed"
        ),
        "steps_skipped": sum(
            1 for r in artefact.steps.values() if r.status == "skipped"
        ),
        "steps_provided": sum(
            1 for r in artefact.steps.values() if r.status == "provided"
        ),
        "tokens_in": t_in or None,
        "tokens_out": t_out or None,
        "cost_usd": total_cost,  # None when unknown
    }


def _append_runs_index(workflow_dir: Path, manifest: dict[str, Any]) -> None:
    """Upsert `<workflow>/runs.json` with a compact entry for this run.

    Upsert (not blind append) so a run can be registered as in-flight when it
    starts and updated in place to 'completed'/'failed' when it finishes —
    without creating duplicate entries.
    """
    runs_path = workflow_dir / "runs.json"
    entries: list[dict[str, Any]] = []
    if runs_path.exists():
        try:
            entries = json.loads(runs_path.read_text(encoding="utf-8")) or []
        except Exception:
            entries = []
    entry = {
        "run_id": manifest["run_id"],
        "started_at": manifest["started_at"],
        "ended_at": manifest["ended_at"],
        "duration_ms": manifest.get("duration_ms"),
        "status": manifest["status"],
        "totals": manifest.get("totals", {}),
    }
    for i, e in enumerate(entries):
        if e.get("run_id") == entry["run_id"]:
            entries[i] = entry
            break
    else:
        entries.append(entry)
    runs_path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")


def list_runs(armance_root: Path, workflow_name: str) -> list[dict[str, Any]]:
    """Return every run manifest for a workflow, oldest first."""
    safe_wf = re.sub(r"[^\w-]", "_", workflow_name)[:64]
    runs_path = armance_root / "exports" / safe_wf / "runs.json"
    if not runs_path.exists():
        return []
    try:
        return json.loads(runs_path.read_text(encoding="utf-8")) or []
    except Exception:
        return []


def load_run(armance_root: Path, workflow_name: str, run_id: str) -> dict[str, str]:
    """Load every artefact of a past run into a dict {filename: content}."""
    safe_wf = re.sub(r"[^\w-]", "_", workflow_name)[:64]
    run_dir = armance_root / "exports" / safe_wf / run_id
    if not run_dir.exists():
        return {}
    out: dict[str, str] = {}
    for p in sorted(run_dir.iterdir()):
        if not p.is_file():
            continue
        try:
            out[p.name] = p.read_text(encoding="utf-8")
        except Exception:
            continue
    return out
