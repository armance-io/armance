"""GET /projects/{pid}/sessions/{sid}/agents/{name} — agent details.

Returns the agent's runtime metadata for the chat tooltip (C.7):
name, role, persona one-liner, provider, model, reasoning,
cumulative tokens_in / tokens_out / cost from the session ledger.

Spec: web-c-deliberation.md § C.7
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["agents"])


@router.get("/agents/{name}")
async def get_agent_details(
    pid: str,
    sid: str,
    name: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return agent metadata + cumulative token usage for this session."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    agent = next((a for a in ws.ctx.agents if a.name == name), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")

    # Ledger snapshot — per-agent usage. Defaults to zero when the
    # agent hasn't been called this session.
    snap = ws.ctx.ledger.snapshot()
    per_agent = snap.get("per_agent", {}).get(name, {})
    tokens_in = per_agent.get("tokens_in", 0)
    tokens_out = per_agent.get("tokens_out", 0)
    cost_usd = per_agent.get("cost_usd", 0.0) if per_agent else None

    persona_label = ""
    persona = getattr(agent, "persona", None)
    if persona is not None:
        persona_label = getattr(persona, "label", "") or ""

    boosted = (name in ws.session.state.boosted_agents) and agent.is_boostable
    eff_mod = agent.model
    if boosted:
        from armance.service.boost_ops import boosted_model_for
        _, eff_mod = boosted_model_for(agent, ws.session.state.boosted_agents)

    return {
        "name": agent.name,
        "role": agent.role or agent.domain or "",
        "persona": persona_label,
        "description": getattr(agent, "description", "") or "",
        "provider": agent.provider,
        "model": agent.model,
        "reasoning": agent.reasoning,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "boosted": boosted,
        "effective_model": eff_mod,
    }
