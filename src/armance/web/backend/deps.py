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


def resolve_root_or_404(app_state: AppState, pid: str):
    """Resolve project *pid*'s data root, raising 404 on an unknown pid.

    Plain helper for route bodies (multi-project, grandma launcher).
    ``pid=default`` keeps the boot root; a registry pid resolves to its folder;
    an unknown pid is a 404 — a raw pid never addresses an arbitrary folder.
    """
    root = app_state.resolve_root(pid)
    if root is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return root


def get_project_root(pid: str, app_state: AppState = Depends(get_app_state)):
    """Depends() form of :func:`resolve_root_or_404`."""
    return resolve_root_or_404(app_state, pid)


def get_web_session(
    sid: str,
    app_state: AppState = Depends(get_app_state),
) -> WebSession:
    """Resolve a session by sid; raise 404 if not found."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ws
