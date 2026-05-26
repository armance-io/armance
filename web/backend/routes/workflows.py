"""Workflow routes (D.1–D.5).

GET    /workflows                                    list workflows
GET    /workflows/{name}                              YAML + graph layout
POST   /workflows/{name}/run                          launch (body: mode, depth)
POST   /workflows/{name}/stop                         interrupt (body: confirm)

Spec: web-d-pipeline.md
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user

from backend.deps import get_app_state
from backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["workflows"])


def _load_workflow_safe(path) -> Any | None:
    """Best-effort load — broken YAML returns None instead of raising."""
    try:
        from armance.core.models.workflow import load_workflow
        return load_workflow(path)
    except Exception as exc:
        logger.debug("workflow %s failed to parse: %s", path.name, exc)
        return None


@router.get("/workflows")
async def list_workflows(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """List every workflow YAML in .armance/workflows/."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    wf_dir = ws.ctx.armance_root / "workflows"
    if not wf_dir.exists():
        return {"workflows": []}

    items: list[dict[str, Any]] = []
    for p in sorted(wf_dir.glob("*.yaml")):
        wf = _load_workflow_safe(p)
        if wf is None:
            continue
        items.append({
            "name": wf.name,
            "scope": getattr(wf, "scope", "") or "",
            "step_count": len(getattr(wf, "steps", []) or []),
        })
    return {"workflows": items}
