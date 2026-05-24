"""armance.platform.user — FastAPI user dependency.

V2 stub: always returns ``"local"`` (single-user, no auth).
V3 swap: replace this function with one that reads a JWT or an
Identity-Aware-Proxy header to resolve the real user id.
See the V3 forward-spec (internal) for the V3 contract.

Usage
-----
Every route that touches project or session data must declare::

    from armance.platform.user import get_current_user

    @router.get("/projects/{pid}/...")
    async def my_route(user: str = Depends(get_current_user)) -> ...:
        ...
"""
from __future__ import annotations


async def get_current_user() -> str:
    """Return the current user identifier.

    V2 stub — always returns ``"local"``.

    V3 swap point: replace this body with JWT / IAP header resolution.
    See the V3 forward-spec (internal).
    """
    return "local"
