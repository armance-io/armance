"""Coverage backfill for backend/routes/workflows.py.

Exercises the error branches and the two dispatch seams
(`_dispatch_run` / `_dispatch_stop`) that the happy-path D.1–D.6
tests skip. Closes the 84.80% → ≥85% gate gap (workflows.py was 77%).

Spec: web-d-pipeline.md § D.1–D.6
"""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient
from pathlib import Path
from unittest.mock import AsyncMock, patch


def _seed_workflow(armance_root: Path, name: str = "wf") -> None:
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{name}.yaml").write_text(
        "name: wf\nscope: x\nsteps:\n  - id: a\n    kind: task\n    role: r\n",
        encoding="utf-8",
    )


# --- list_workflows error / empty branches (lines 53, 57) ----------------

@pytest.mark.asyncio
async def test_list_workflows_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions/ghost/workflows")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


@pytest.mark.asyncio
async def test_list_workflows_no_dir_returns_empty(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    # No workflows/ dir seeded → empty list, not error.
    resp = await client.get(f"/projects/default/sessions/{sid}/workflows")
    assert resp.status_code == 200
    assert resp.json() == {"workflows": []}


# --- get_workflow error branches (lines 139, 146) ------------------------

@pytest.mark.asyncio
async def test_get_workflow_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions/ghost/workflows/wf")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


@pytest.mark.asyncio
async def test_get_workflow_invalid_yaml_422(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    # Broken YAML — _load_workflow_safe returns None → 422.
    (wf_dir / "broken.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/broken")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "workflow_invalid_yaml"


# --- _dispatch_run real body (lines 185-202) -----------------------------

@pytest.mark.asyncio
async def test_run_dispatch_seam_derives_run_id_from_index(
    client: AsyncClient, armance_root: Path, app_state
) -> None:
    """Exercise the real _dispatch_run directly: it reads runs.json for run_id.

    (The route now runs this in the background and returns immediately, so we
    call the seam directly to assert run_id derivation + reply_preview.)
    """
    from armance.web.backend.routes.workflows import _dispatch_run

    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    ws = app_state.get(sid)
    # Seed a runs.json so _dispatch_run can derive the last run_id.
    exports = armance_root / "exports" / "wf"
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "runs.json").write_text(
        json.dumps([{"run_id": "run-latest", "status": "completed"}]),
        encoding="utf-8",
    )
    with patch(
        "armance.service.handlers._cmd_workflow_run",
        new=AsyncMock(return_value="Lancé."),
    ):
        body = await _dispatch_run(ws, "wf", "interactive")
    assert body["ack"] is True
    assert body["run_id"] == "run-latest"
    assert body["reply_preview"] == "Lancé."


@pytest.mark.asyncio
async def test_run_dispatch_seam_no_index_blank_run_id(
    client: AsyncClient, armance_root: Path, app_state
) -> None:
    """No runs.json → run_id falls back to empty string."""
    from armance.web.backend.routes.workflows import _dispatch_run

    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    ws = app_state.get(sid)
    with patch(
        "armance.service.handlers._cmd_workflow_run",
        new=AsyncMock(return_value="ok"),
    ):
        body = await _dispatch_run(ws, "wf", "autonomous")
    assert body["run_id"] == ""


@pytest.mark.asyncio
async def test_run_unknown_session_404(
    client: AsyncClient, armance_root: Path
) -> None:
    resp = await client.post(
        "/projects/default/sessions/ghost/workflows/wf/run",
        json={"mode": "interactive"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


# --- stop: honest 409 when nothing is running -----------------------------
# (The old `_dispatch_stop` chat seam is gone — stop now cancels the
#  session's run task directly; the happy path lives in
#  test_d4_d6_workflow_actions.test_stop_cancels_the_active_run_task.)

@pytest.mark.asyncio
async def test_stop_idle_session_is_409(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    resp = await client.post(
        f"/projects/default/sessions/{sid}/workflows/wf/stop",
        json={"confirm": True},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == {"error": "no_active_run"}


@pytest.mark.asyncio
async def test_stop_unknown_session_404(
    client: AsyncClient, armance_root: Path
) -> None:
    resp = await client.post(
        "/projects/default/sessions/ghost/workflows/wf/stop",
        json={"confirm": True},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


# --- delete_run error branches (lines 276, 278, 285-286, 294-304) --------

@pytest.mark.asyncio
async def test_delete_run_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.request(
        "DELETE",
        "/projects/default/sessions/ghost/workflows/wf/runs/run-1",
        json={"confirm": True},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


@pytest.mark.asyncio
async def test_delete_run_invalid_run_id_400(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/bad%20id%21",
        json={"confirm": True},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_run_id"


# Note: the invalid_path branch (lines 285-286) guards a resolved path that
# escapes exports_root. A "run_id" capable of escaping (e.g. "..") is rejected
# by HTTP path normalisation (405) before reaching the handler, so the branch
# is unreachable over the wire — left uncovered deliberately.


@pytest.mark.asyncio
async def test_delete_active_run_blocked_409(
    client: AsyncClient, armance_root: Path
) -> None:
    """Most-recent run of the current_workflow is protected (lines 294-304)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    run_dir = armance_root / "exports" / "wf" / "run-active"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (armance_root / "exports" / "wf" / "runs.json").write_text(
        json.dumps([{"run_id": "run-active", "status": "running"}]),
        encoding="utf-8",
    )
    # Mark the workflow as the session's current one.
    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.session.state.current_workflow = "wf"
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-active",
        json={"confirm": True},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "run_is_active"
    assert run_dir.exists()  # not removed


@pytest.mark.asyncio
async def test_delete_run_tolerates_corrupt_runs_index(
    client: AsyncClient, armance_root: Path
) -> None:
    """Corrupt runs.json on rewrite is logged, not fatal (lines 315-316)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_workflow(armance_root)
    run_dir = armance_root / "exports" / "wf" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    # Corrupt index — delete still succeeds (dir removed), rewrite swallowed.
    (armance_root / "exports" / "wf" / "runs.json").write_text(
        "{not json", encoding="utf-8"
    )
    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1",
        json={"confirm": True},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert not run_dir.exists()
