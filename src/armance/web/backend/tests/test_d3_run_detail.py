"""D3 / ADR 0003 — structured run-detail route.

GET /projects/{pid}/sessions/{sid}/workflows/{name}/runs/{run_id}/detail

Shapes the run's on-disk manifest.json into the fixed detail contract
(stage/family/quality/derived_from/per-step cost). Read-only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient


def _seed_workflow(armance_root: Path, name: str = "wf") -> None:
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{name}.yaml").write_text(
        "name: wf\nscope: x\nsteps:\n  - id: a\n    kind: task\n    role: r\n",
        encoding="utf-8",
    )


def _write_manifest(
    armance_root: Path, run_id: str, manifest: dict, *, wf: str = "wf"
) -> Path:
    run_dir = armance_root / "exports" / wf / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


@pytest.mark.asyncio
async def test_detail_nominal_creuset(client: AsyncClient, armance_root: Path) -> None:
    """Full Creuset manifest: stage + family + quality.md → shaped contract."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)

    manifest = {
        "workflow": "wf",
        "run_id": "run-1",
        "status": "completed",
        "started_at": "2026-07-13T10:00:00+00:00",
        "ended_at": "2026-07-13T10:05:00+00:00",
        "quality_present": True,
        "derived_from": [
            {"run_id": "run-0", "overrides": [{"step": "a", "source": "a.md"}]}
        ],
        "steps": [
            {
                "id": "a",
                "status": "completed",
                "stage": "draft",
                "family": "anthropic",
                "agent": "Claire",
                "duration_ms": 1234,
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_usd": 0.0042,
                "error": None,
            }
        ],
    }
    run_dir = _write_manifest(armance_root, "run-1", manifest)
    (run_dir / "quality.md").write_text("# Quality\nGate passed.", encoding="utf-8")

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/detail"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-1"
    assert body["workflow"] == "wf"
    assert body["status"] == "completed"
    assert body["started_at"] == "2026-07-13T10:00:00+00:00"
    assert body["ended_at"] == "2026-07-13T10:05:00+00:00"
    assert body["derived_from"] == [
        {"run_id": "run-0", "overrides": [{"step": "a", "source": "a.md"}]}
    ]
    assert body["quality"] == {"present": True, "markdown": "# Quality\nGate passed."}
    assert len(body["steps"]) == 1
    step = body["steps"][0]
    assert step["id"] == "a"
    assert step["status"] == "completed"
    assert step["stage"] == "draft"
    assert step["family"] == "anthropic"
    assert step["agent"] == "Claire"
    assert step["duration_ms"] == 1234
    assert step["tokens_in"] == 100
    assert step["tokens_out"] == 200
    assert step["cost_usd"] == 0.0042
    assert step["provided"] is False
    assert step["error"] is None


@pytest.mark.asyncio
async def test_detail_legacy_manifest_nulls(
    client: AsyncClient, armance_root: Path
) -> None:
    """Pre-Creuset manifest without stage/family/quality → nulls, no crash."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)

    manifest = {
        "workflow": "wf",
        "run_id": "run-old",
        "status": "completed",
        "started_at": "2026-01-01T00:00:00+00:00",
        "ended_at": None,
        "steps": [
            {"id": "a", "status": "completed", "duration_ms": 500}
        ],
    }
    _write_manifest(armance_root, "run-old", manifest)

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-old/detail"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ended_at"] is None
    assert body["derived_from"] == []
    assert body["quality"] == {"present": False, "markdown": None}
    step = body["steps"][0]
    assert step["stage"] is None
    assert step["family"] is None
    assert step["agent"] is None
    assert step["cost_usd"] is None
    assert step["tokens_in"] is None
    assert step["provided"] is False
    assert step["error"] is None


@pytest.mark.asyncio
async def test_detail_unknown_run_404(client: AsyncClient, armance_root: Path) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-nope/detail"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_unknown_workflow_404(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    # No workflow YAML seeded.
    _write_manifest(armance_root, "run-1", {"run_id": "run-1", "steps": []})

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/detail"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_provided_step(client: AsyncClient, armance_root: Path) -> None:
    """A human-override step (status='provided') → provided=true."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)

    manifest = {
        "workflow": "wf",
        "run_id": "run-2",
        "status": "completed",
        "started_at": "2026-07-13T10:00:00+00:00",
        "ended_at": "2026-07-13T10:01:00+00:00",
        "steps": [
            {"id": "a", "status": "provided", "error": "override: a.md"}
        ],
    }
    _write_manifest(armance_root, "run-2", manifest)

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-2/detail"
    )
    assert resp.status_code == 200
    step = resp.json()["steps"][0]
    assert step["status"] == "provided"
    assert step["provided"] is True
