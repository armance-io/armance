"""GET /whoami — current user identity (V2 = "local")."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from armance.platform.user import get_current_user

router = APIRouter(tags=["auth"])


@router.get("/whoami")
async def whoami(user: str = Depends(get_current_user)) -> dict:
    return {"user": user}
