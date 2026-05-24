"""J.5 — get_current_user() FastAPI dependency tests.

Written to confirm the V2 stub behaviour.  Spec:
issues/features/web-j-platform-abstractions.md § J.5

Acceptance criteria:
- get_current_user() is async.
- get_current_user() returns "local" in V2.
- It is importable from armance.platform.user and armance.platform.
"""
from __future__ import annotations

import inspect
import pytest


def test_get_current_user_importable_from_platform_user() -> None:
    from armance.platform.user import get_current_user  # noqa: F401


def test_get_current_user_importable_from_platform() -> None:
    from armance.platform import get_current_user  # noqa: F401


def test_get_current_user_is_async() -> None:
    from armance.platform.user import get_current_user
    assert inspect.iscoroutinefunction(get_current_user)


@pytest.mark.asyncio
async def test_get_current_user_returns_local() -> None:
    from armance.platform.user import get_current_user
    result = await get_current_user()
    assert result == "local"


@pytest.mark.asyncio
async def test_get_current_user_returns_string() -> None:
    from armance.platform.user import get_current_user
    result = await get_current_user()
    assert isinstance(result, str)
