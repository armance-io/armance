"""D.3 — GET /active-workflow — null when idle, payload when a run is active.

Spec: web-d-pipeline.md § D.3
"""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.mark.asyncio
async def test_active_workflow_null_when_idle(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/active-workflow")
    assert resp.status_code == 200
    assert resp.json() == {"active": None}


@pytest.mark.asyncio
async def test_active_workflow_returns_payload_for_current_workflow(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.session.state.current_workflow = "dossier-vapp"

    wf_dir = armance_root / "exports" / "dossier-vapp"
    wf_dir.mkdir(parents=True, exist_ok=True)
    run_dir = wf_dir / "run-20260526-235959"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "run-20260526-235959", "status": "running"}),
        encoding="utf-8",
    )
    (wf_dir / "runs.json").write_text(
        json.dumps([{"run_id": "run-20260526-235959", "status": "running"}]),
        encoding="utf-8",
    )

    resp = await client.get(f"/projects/default/sessions/{sid}/active-workflow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is not None
    assert data["active"]["workflow"] == "dossier-vapp"
    assert data["active"]["run_id"] == "run-20260526-235959"
    assert "manifest_path" in data["active"]
