"""FastAPI dependency resolvers.

Centralises resolution of: current user, project, session.
Every data route declares these as Depends(); V3 swaps the implementations.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from armance.platform.user import get_current_user  # noqa: F401 (re-export for routers)
from armance.web.backend.state import AppState, WebSession


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_web_session(
    sid: str,
    app_state: AppState = Depends(get_app_state),
) -> WebSession:
    """Resolve a session by sid; raise 404 if not found."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ws
