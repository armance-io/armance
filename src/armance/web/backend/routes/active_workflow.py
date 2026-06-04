"""GET /active-workflow — null or {workflow, run_id, manifest_path}.

Reads `session.state.current_workflow` (set when Kim launches a run)
and pairs it with the most recent run id from `.armance/exports/<wf>/
runs.json`. Returns null when no workflow is active or no run exists.

Spec: web-d-pipeline.md § D.3
"""
from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["workflows"])


def _safe_wf(name: str) -> str:
    return re.sub(r"[^\w-]", "_", name)[:64]


@router.get("/active-workflow")
async def get_active_workflow(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    name = getattr(ws.session.state, "current_workflow", None)
    if not name:
        return {"active": None}

    safe = _safe_wf(name)
    runs_index = ws.ctx.armance_root / "exports" / safe / "runs.json"
    if not runs_index.exists():
        return {"active": None}

    try:
        runs = json.loads(runs_index.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("runs.json unreadable for workflow %s", name)
        return {"active": None}

    if not isinstance(runs, list) or not runs:
        return {"active": None}

    last = runs[-1]
    run_id = last.get("run_id") if isinstance(last, dict) else None
    if not run_id:
        return {"active": None}

    return {
        "active": {
            "workflow": name,
            "run_id": run_id,
            "manifest_path": f"exports/{safe}/{run_id}/manifest.json",
        }
    }
