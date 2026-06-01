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
from armance.service.session import start_or_resume, Session, load_state, latest_session_id, list_sessions
from armance.service.tui_bridge import make_loop_context, META_AGENTS

from armance.web.backend.checkpoint import WebCheckpointHandler
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState, WebSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}", tags=["sessions"])


def _check_initialised(armance_root: Path, pid: str) -> None:
    """Raise 409 if the project is not yet initialised.

    "Initialised" = `.armance/config.yaml` exists (the same path load_config
    reads). Never write or overwrite config here — a previous version checked
    the wrong path (`<root>/config.yaml`) and silently clobbered the user's
    real config with a Gemini default on every launch.
    """
    config_path = armance_root / "config.yaml"
    if not config_path.exists():
        raise HTTPException(
            status_code=409,
            detail={"error": "not_initialised", "redirect": "/setup"},
        )


def _load_web_session(
    app_state: AppState,
    armance_root: Path,
    pid: str,
    sid: str,
    client_id: str | None = None,
) -> WebSession:
    """Loads a session from memory or disk into AppState."""
    ws = app_state.get(sid)
    if ws is not None:
        return ws

    try:
        cfg = load_config(armance_root.parent)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "not_initialised", "redirect": "/setup"},
        ) from exc

    ensure_armance_tree(armance_root.parent, cfg)
    set_language(cfg.language)

    state = load_state(armance_root, sid)
    session = Session(state, armance_root)

    ledger_path = Path(state.ledger_path) if state.ledger_path else None
    ledger = TokenLedger(persist_path=ledger_path) if ledger_path else TokenLedger()
    set_ledger(ledger)

    log_path = armance_root / "sessions" / state.id / "events.log"
    bus = LocalEventBus(log_path=log_path)

    handler = WebCheckpointHandler(bus)
    ctx = make_loop_context(armance_root, cfg, state, session, ledger,
                            checkpoint_handler=handler,
                            event_bus=bus)

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
    return web_session


@router.post("/sessions", status_code=201)
async def create_session(
    pid: str,
    request: Request,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Create a new Armance session for project *pid*."""
    armance_root = app_state.armance_root
    _check_initialised(armance_root, pid)

    try:
        cfg = load_config(armance_root.parent)
    except Exception as exc:
        raise HTTPException(status_code=409, detail={"error": "not_initialised", "redirect": "/setup"}) from exc

    ensure_armance_tree(armance_root.parent, cfg)
    set_language(cfg.language)

    state = start_or_resume(armance_root, resume=False)
    client_id = request.cookies.get("armance_client_id", user)

    _load_web_session(app_state, armance_root, pid, state.id, client_id=client_id)

    logger.info("session created sid=%s pid=%s user=%s", state.id, pid, user)
    return {"id": state.id, "project_id": pid}


@router.get("/sessions")
async def get_sessions(
    pid: str,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """List persisted sessions (newest first) for the header selector.

    Mirrors the TUI resume picker: id, updated_at, turns, est_tokens.
    """
    try:
        sessions = list_sessions(app_state.armance_root)
    except Exception:
        logger.warning("list_sessions failed pid=%s", pid, exc_info=True)
        sessions = []
    return {"sessions": sessions}


@router.get("/sessions/latest")
async def get_latest_session(
    pid: str,
    request: Request,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return the latest session, auto-creating one if none exists."""
    armance_root = app_state.armance_root
    _check_initialised(armance_root, pid)

    sid = latest_session_id(armance_root)
    if not sid:
        # Create a default session automatically just like POST /sessions
        try:
            cfg = load_config(armance_root.parent)
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"error": "not_initialised", "redirect": "/setup"}) from exc

        ensure_armance_tree(armance_root.parent, cfg)
        set_language(cfg.language)
        state = start_or_resume(armance_root, resume=False)
        sid = state.id
        logger.info("auto-created default session sid=%s for first launch", sid)

    client_id = request.cookies.get("armance_client_id", user)
    _load_web_session(app_state, armance_root, pid, sid, client_id=client_id)

    return {"id": sid, "project_id": pid}


@router.get("/sessions/{sid}")
async def get_session(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return session state, agent list, and language."""
    armance_root = app_state.armance_root
    _check_initialised(armance_root, pid)

    try:
        ws = _load_web_session(app_state, armance_root, pid, sid, client_id=user)
    except Exception:
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


@router.get("/sessions/{sid}/messages")
async def get_messages(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return the session's conversation turns, oldest-first.

    The web chat replays these on mount so an existing session shows its
    dialogue exactly like the TUI.
    """
    armance_root = app_state.armance_root
    _check_initialised(armance_root, pid)

    try:
        ws = _load_web_session(app_state, armance_root, pid, sid, client_id=user)
    except Exception:
        raise HTTPException(status_code=404, detail="session_not_found")

    conv = ws.ctx.session.conversation
    messages = [
        {
            "role": turn.role,
            "content": turn.content,
            "agent": turn.agent,
            "timestamp": turn.timestamp.isoformat() if turn.timestamp else None,
        }
        for turn in conv.turns
    ]
    return {"messages": messages}
