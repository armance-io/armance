"""Workflow run routes (B.5–B.7).

GET  /projects/{pid}/sessions/{sid}/workflows/{name}/runs
GET  /projects/{pid}/sessions/{sid}/workflows/{name}/runs/{run_id}
GET  /projects/{pid}/sessions/{sid}/workflows/{name}/runs/{run_id}/step/{step_id}

Delegates to armance.service.workflow_runs.{list_runs, load_run}.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from armance.platform.user import get_current_user
from armance.service.workflow_runs import list_runs, load_run

from backend.deps import get_app_state
from backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{pid}/sessions/{sid}/workflows/{name}",
    tags=["runs"],
)


@router.get("/runs")
async def get_workflow_runs(
    pid: str,
    sid: str,
    name: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> list:
    """List all runs for a workflow, oldest first."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    runs = list_runs(ws.ctx.armance_root, name)
    return runs


@router.get("/runs/{run_id}")
async def get_workflow_run(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return all artefacts of a past run as {filename: content}."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    run_data = load_run(ws.ctx.armance_root, name, run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="run_not_found")
    return run_data


@router.get("/runs/{run_id}/step/{step_id}")
async def get_workflow_run_step(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    step_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> PlainTextResponse:
    """Return raw Markdown of a step file as text/markdown."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    import re
    safe_wf = re.sub(r"[^\w-]", "_", name)[:64]
    # Validate step_id — no path traversal.
    if not re.fullmatch(r"[\w-]+", step_id):
        raise HTTPException(status_code=400, detail="invalid_step_id")

    step_file = ws.ctx.armance_root / "exports" / safe_wf / run_id / f"step-{step_id}.md"

    # Security: verify the path doesn't escape the exports directory.
    exports_root = ws.ctx.armance_root / "exports"
    try:
        step_file.resolve().relative_to(exports_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_path")

    if not step_file.exists():
        raise HTTPException(status_code=404, detail="step_not_found")

    content = step_file.read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")
