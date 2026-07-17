"""Run detail route (D3 / ADR 0003).

GET /projects/{pid}/sessions/{sid}/workflows/{name}/runs/{run_id}/detail

Returns the fixed run-detail contract shaped from the run's on-disk
``manifest.json`` (stage/family/quality/derived_from/per-step cost), so the
web UI no longer has to fetch the raw file dump and re-parse the manifest
client-side (losing every Creuset field). The raw ``GET /runs/{run_id}``
(``routes/runs.py``) stays for artefact access; this is the structured view.

Read-only. Delegates shaping to ``service.workflow_runs.run_detail`` — the
route only resolves the session and guards the run_id.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user
from armance.service.workflow_runs import run_detail

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{pid}/sessions/{sid}/workflows/{name}",
    tags=["run-detail"],
)


@router.get("/runs/{run_id}/detail")
async def get_run_detail(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return the structured detail of a past run (D3 contract).

    404 when the session, workflow or run is unknown. No writes.
    """
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if not re.fullmatch(r"[\w.-]+", run_id):
        raise HTTPException(status_code=400, detail="invalid_run_id")

    wf_path = ws.ctx.armance_root / "workflows" / f"{name}.yaml"
    if not wf_path.exists():
        raise HTTPException(status_code=404, detail="workflow_not_found")

    detail = run_detail(ws.ctx.armance_root, name, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    return detail
