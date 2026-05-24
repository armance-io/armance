"""Session routes.

POST /projects/{pid}/sessions      — create a new session
GET  /projects/{pid}/sessions/{sid} — get session state + agents

All data routes declare Depends(get_current_user) per the non-negotiable rules.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from armance.config import load_config, ensure_armance_tree
from armance.nls import set_language
from armance.platform.events import LocalEventBus
from armance.platform.user import get_current_user
from armance.service.llm_service import TokenLedger, set_ledger
from armance.service.session import start_or_resume, Session
from armance.service.tui_bridge import make_loop_context, META_AGENTS

from backend.checkpoint import WebCheckpointHandler
from backend.deps import get_app_state
from backend.state import AppState, WebSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}", tags=["sessions"])


def _check_initialised(armance_root: Path, pid: str) -> None:
    """Raise 409 if the project is not yet initialised."""
    config_path = armance_root.parent / "config.yaml"
    if not config_path.exists():
        raise HTTPException(
            status_code=409,
            detail={"error": "not_initialised", "redirect": "/setup"},
        )


@router.post("/sessions", status_code=201)
async def create_session(
    pid: str,
    request: Request,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Create a new Armance session for project *pid*.

    V2: pid is always "default".  V3 wires real project isolation.
    """
    armance_root = app_state.armance_root
    _check_initialised(armance_root, pid)

    # Build a fresh session (same as CLI cmd_run, minus the TUI).
    try:
        cfg = load_config(armance_root.parent)
    except Exception as exc:
        raise HTTPException(status_code=409, detail={"error": "not_initialised", "redirect": "/setup"}) from exc

    ensure_armance_tree(armance_root.parent, cfg)
    set_language(cfg.language)

    state = start_or_resume(armance_root, resume=False)
    session = Session(state, armance_root)

    ledger_path = Path(state.ledger_path) if state.ledger_path else None
    ledger = TokenLedger(persist_path=ledger_path) if ledger_path else TokenLedger()
    set_ledger(ledger)

    # Event bus: JSONL log + asyncio.Queue for SSE.
    log_path = armance_root / "sessions" / state.id / "events.log"
    bus = LocalEventBus(log_path=log_path)

    handler = WebCheckpointHandler(bus)
    ctx = make_loop_context(armance_root, cfg, state, session, ledger,
                            checkpoint_handler=handler)

    # Register in the platform SessionRegistry.
    sid = await app_state.registry.create(pid)
    # Override the registry sid with the actual session id from start_or_resume.
    # (The registry entry exists for tracking; the real id comes from session.state.)
    sid = state.id

    # Determine driver_client_id from the request cookie (for read-along guard).
    client_id = request.cookies.get("armance_client_id", user)

    web_session = WebSession(
        sid=sid,
        project_id=pid,
        session=session,
        ctx=ctx,
        bus=bus,
        handler=handler,
        driver_client_id=client_id,
    )
    app_state.put(web_session)

    logger.info("session created sid=%s pid=%s user=%s", sid, pid, user)
    return {"id": sid, "project_id": pid}


@router.get("/sessions/{sid}")
async def get_session(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return session state, agent list, and language."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    state = ws.session.state
    agents_info = [
        {"name": name, "first_name": first_name, "title": title}
        for name, first_name, title in META_AGENTS
    ]
    # Append user-defined agents from the context.
    for agent in ws.ctx.agents:
        agents_info.append({
            "name": agent.name,
            "first_name": agent.name,
            "title": getattr(agent, "role", "") or getattr(agent, "domain", ""),
        })

    return {
        "state": state.model_dump(),
        "agents": agents_info,
        "language": ws.ctx.cfg.language,
    }
