from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user
from armance.service.deliverable_index import list_deliverables, set_starred_id

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["deliverables"])


class StarPayload(BaseModel):
    starred: bool


@router.get("/deliverables")
async def get_deliverables(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
):
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    items = await list_deliverables(ws.ctx.armance_root, storage)
    return items


@router.patch("/deliverables/{id:path}/star")
async def patch_star_deliverable(
    pid: str,
    sid: str,
    id: str,
    body: StarPayload,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
):
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    
    # List all deliverables to check if the requested id exists
    items = await list_deliverables(ws.ctx.armance_root, storage)
    target = None
    for item in items:
        if item["id"] == id:
            target = item
            break
            
    if target is None:
        raise HTTPException(status_code=404, detail="deliverable_not_found")

    # Update starred status
    await set_starred_id(storage, id, body.starred)
    
    # Return the updated entry
    target["starred"] = body.starred
    return target
