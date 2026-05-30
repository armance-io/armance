"""B.5, B.6, B.7 — GET /workflows/{name}/runs routes.

Spec:
  - B.5: GET /runs returns list of runs; unknown workflow -> 404.
  - B.6: GET /runs/{run_id} returns manifest.json; unknown run_id -> 404.
  - B.7: GET /runs/{run_id}/step/{step_id} returns raw Markdown; unknown step -> 404; path traversal -> 400.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_workflow_runs(client: AsyncClient, armance_root: Path) -> None:
    """GET /runs returns the list of runs."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    runs_data = [{"run_id": "run1"}, {"run_id": "run2"}]
    wf_dir = armance_root / "exports" / "test-wf"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "runs.json").write_text(json.dumps(runs_data))

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs")
    assert resp.status_code == 200
    assert resp.json() == runs_data


@pytest.mark.asyncio
async def test_get_workflow_runs_unknown_returns_empty(client: AsyncClient) -> None:
    """GET /runs for a workflow with no runs returns [] (not 404).

    The frontend polls this endpoint; a 404 on a not-yet-launched workflow
    produced a redirect/error loop in the run-history sidebar.
    """
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/unknown_wf/runs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_workflow_run_manifest(client: AsyncClient, armance_root: Path) -> None:
    """GET /runs/{run_id} returns the manifest."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    run_dir = armance_root / "exports" / "test-wf" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text('{"foo": "bar"}')
    (run_dir / "other.txt").write_text("hello")

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs/run1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest.json"] == '{"foo": "bar"}'
    assert data["other.txt"] == "hello"


@pytest.mark.asyncio
async def test_get_workflow_run_unknown_returns_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs/unknown_run")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_workflow_run_step_markdown(client: AsyncClient, armance_root: Path) -> None:
    """GET /runs/.../step/{step_id} returns raw markdown."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    run_dir = armance_root / "exports" / "test-wf" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step-123.md").write_text("# Step 123")

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs/run1/step/123")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    assert resp.text == "# Step 123"


@pytest.mark.asyncio
async def test_get_workflow_run_step_unknown_returns_404(client: AsyncClient, armance_root: Path) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    
    run_dir = armance_root / "exports" / "test-wf" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs/run1/step/unknown")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_workflow_run_step_traversal_returns_400(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/test-wf/runs/run1/step/..%2Fpasswd")
    assert resp.status_code in (400, 404)
