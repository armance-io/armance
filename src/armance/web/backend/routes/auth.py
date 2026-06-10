"""Epic S · auth routes — token/password verification + cookie login.

These endpoints are public (the gate exempts ``/auth/*``) so the login
flow can run before a session cookie exists.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from armance.config import load_config
from armance.service import security

COOKIE_NAME = "armance_session_token"

router = APIRouter()


class LoginBody(BaseModel):
    token: str


def _present_secret(request: Request) -> str | None:
    """Extract a candidate secret from header, query, or cookie."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    qp = request.query_params.get("token")
    if qp:
        return qp
    return request.cookies.get(COOKIE_NAME)


def _config(request: Request):
    # Config is global (clean break); request is kept for signature stability.
    return load_config()


@router.get("/auth/verify")
async def verify(request: Request, response: Response) -> dict[str, bool]:
    """200 if the presented credential is valid, else 401."""
    cfg = _config(request)
    candidate = _present_secret(request)
    if not security.check_web_secret(cfg, candidate):
        response.status_code = 401
        return {"valid": False}
    return {"valid": True}


@router.post("/auth/login")
async def login(request: Request, response: Response, body: LoginBody) -> dict[str, bool]:
    """Exchange a valid token/password for an HttpOnly session cookie.

    Using an HttpOnly cookie (instead of localStorage) keeps the secret
    out of reach of XSS and means every subsequent /api call is
    authorised automatically via ``credentials: include``.
    """
    cfg = _config(request)
    if not security.check_web_secret(cfg, body.token):
        response.status_code = 401
        return {"ok": False}
    response.set_cookie(
        COOKIE_NAME,
        body.token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True}
