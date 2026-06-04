"""D.4 + D.5 + D.6 — workflow run / stop / delete-run routes.

D.4: POST /workflows/{name}/run  body {mode}            → 202 {run_id}
D.5: POST /workflows/{name}/stop body {confirm}         → 200 {cancelled} / 409
D.6: DELETE /workflows/{name}/runs/{run_id} body {confirm} → 200 {deleted} / 409

Spec: web-d-pipeline.md § D.4, D.5, D.6
"""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient
from pathlib import Path
from unittest.mock import AsyncMock, patch


def _seed_workflow(armance_root: Path) -> None:
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "wf.yaml").write_text(
        "name: wf\nscope: x\nsteps:\n  - id: a\n    kind: task\n    role: r\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_run_accepts_mode_and_returns_run_id(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    with patch(
        "armance.web.backend.routes.workflows._dispatch_run",
        new=AsyncMock(return_value={"ack": True, "run_id": "run-X"}),
    ):
        resp = await client.post(
            f"/projects/default/sessions/{sid}/workflows/wf/run",
            json={"mode": "interactive"},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] == "run-X"


@pytest.mark.asyncio
async def test_run_invalid_mode_400(client: AsyncClient, armance_root: Path) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    resp = await client.post(
        f"/projects/default/sessions/{sid}/workflows/wf/run",
        json={"mode": "bogus"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_run_unknown_workflow_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.post(
        f"/projects/default/sessions/{sid}/workflows/nope/run",
        json={"mode": "interactive"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stop_requires_confirm(client: AsyncClient, armance_root: Path) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    resp = await client.post(
        f"/projects/default/sessions/{sid}/workflows/wf/stop",
        json={"confirm": False},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_stop_with_confirm_dispatches(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    with patch(
        "armance.web.backend.routes.workflows._dispatch_stop",
        new=AsyncMock(return_value={"cancelled": True}),
    ):
        resp = await client.post(
            f"/projects/default/sessions/{sid}/workflows/wf/stop",
            json={"confirm": True},
        )
    assert resp.status_code == 200
    assert resp.json() == {"cancelled": True}


@pytest.mark.asyncio
async def test_delete_run_requires_confirm(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    run_dir = armance_root / "exports" / "wf" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}")
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1",
        json={"confirm": False},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_run_with_confirm_removes(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    run_dir = armance_root / "exports" / "wf" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}")
    (armance_root / "exports" / "wf" / "runs.json").write_text(
        json.dumps([{"run_id": "run-1", "status": "completed"}]),
    )
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1",
        json={"confirm": True},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert not run_dir.exists()


@pytest.mark.asyncio
async def test_delete_run_unknown_404(client: AsyncClient, armance_root: Path) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/nope",
        json={"confirm": True},
    )
    assert resp.status_code == 404
