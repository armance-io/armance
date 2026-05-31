"""Admin agents routes — agent list + model/reasoning update.

GET  /projects/{pid}/sessions/{sid}/agents
PATCH /projects/{pid}/sessions/{sid}/agents/{name}

Persona edits are rejected — only Malik chat can edit persona.
Model + reasoning can be updated; the file is written via Agent.save().
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from armance.core.models.agent import Agent
from armance.platform.user import get_current_user
from armance.service.tui_bridge import META_AGENTS
from armance.storage.paths import agent_path
from armance.web.backend.deps import get_app_state, get_web_session
from armance.web.backend.state import AppState, WebSession

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

router = APIRouter()

_PERSONA_ERROR = {"error": "persona_via_malik_only"}
_WRITABLE_FIELDS = {"model", "reasoning"}


def _persona_text(agent: Agent) -> str:
    """Best-effort human-readable persona for display (read-only in the web)."""
    p = agent.persona
    if p is None:
        return ""
    for attr in ("summary", "description", "text", "bio"):
        val = getattr(p, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Persona may be a plain string in older definitions.
    if isinstance(p, str):
        return p.strip()
    return ""


def _agent_row(
    agent: Agent,
    *,
    staff: bool,
    default_provider: str,
    default_model: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    # Staff files often leave provider/model blank to inherit the project
    # defaults at runtime; surface the effective values, never a blank "-".
    return {
        "name": display_name or agent.name,
        "slug": agent.name,
        "domain": agent.domain,
        "role": agent.role or agent.domain or "",
        "provider": agent.provider or default_provider,
        "model": agent.model or default_model,
        "reasoning": agent.reasoning,
        "persona": _persona_text(agent),
        "staff": staff,
    }


@router.get("/projects/{pid}/sessions/{sid}/agents")
async def list_agents(
    pid: str,
    sid: str,
    _user: str = Depends(get_current_user),
    ws: WebSession = Depends(get_web_session),
) -> list[dict[str, Any]]:
    # The 5 permanent staff (Armance/Malik/Kim/Mona/Serge) live as
    # system-*.md files and are NOT in ctx.agents (which holds only the
    # specialists Malik recruits). Surface staff first, then specialists.
    cfg = ws.ctx.cfg
    dp = getattr(cfg, "default_provider", "") or ""
    dm = getattr(cfg, "default_model", "") or ""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slug, first_name, _role in META_AGENTS:
        path = agent_path(ws.ctx.armance_root, slug)
        if not path.exists():
            continue
        try:
            agent = Agent.load(path)
        except Exception:  # noqa: BLE001 — skip an unreadable staff file
            continue
        result.append(_agent_row(agent, staff=True, default_provider=dp, default_model=dm, display_name=first_name))
        seen.add(agent.name)
    for agent in ws.ctx.agents:
        if agent.name in seen:
            continue
        result.append(_agent_row(agent, staff=False, default_provider=dp, default_model=dm))
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
    if not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid_agent_name")

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
