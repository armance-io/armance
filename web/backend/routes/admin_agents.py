"""Admin agents routes — agent list + model/reasoning update.

GET  /projects/{pid}/sessions/{sid}/agents
PATCH /projects/{pid}/sessions/{sid}/agents/{name}

Persona edits are rejected — only Malik chat can edit persona.
Model + reasoning can be updated; the file is written via Agent.save().
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from armance.core.models.agent import Agent
from armance.platform.user import get_current_user
from armance.storage.paths import agent_path
from backend.deps import get_app_state, get_web_session
from backend.state import AppState, WebSession

router = APIRouter()

_PERSONA_ERROR = {"error": "persona_via_malik_only"}
_WRITABLE_FIELDS = {"model", "reasoning"}


@router.get("/projects/{pid}/sessions/{sid}/agents")
async def list_agents(
    pid: str,
    sid: str,
    _user: str = Depends(get_current_user),
    ws: WebSession = Depends(get_web_session),
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for agent in ws.ctx.agents:
        result.append({
            "name": agent.name,
            "domain": agent.domain,
            "role": agent.role or agent.domain or "",
            "provider": agent.provider,
            "model": agent.model,
            "reasoning": agent.reasoning,
        })
    return result


@router.patch("/projects/{pid}/sessions/{sid}/agents/{name}")
async def patch_agent(
    pid: str,
    sid: str,
    name: str,
    patch: dict[str, Any],
    _user: str = Depends(get_current_user),
    ws: WebSession = Depends(get_web_session),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    if "persona" in patch:
        raise HTTPException(status_code=422, detail=_PERSONA_ERROR)

    unknown = set(patch.keys()) - _WRITABLE_FIELDS
    if unknown:
        raise HTTPException(status_code=422, detail={"error": "unknown_fields", "fields": list(unknown)})

    agent = next((a for a in ws.ctx.agents if a.name == name), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")

    path = agent_path(app_state.armance_root, name)
    if path.exists():
        on_disk = Agent.load(path)
    else:
        on_disk = agent

    updated_data = on_disk.model_dump()
    if "model" in patch:
        updated_data["model"] = patch["model"]
    if "reasoning" in patch:
        updated_data["reasoning"] = patch["reasoning"]

    updated = Agent.model_validate(updated_data)
    updated.save(path)

    return {
        "name": updated.name,
        "model": updated.model,
        "reasoning": updated.reasoning,
    }
