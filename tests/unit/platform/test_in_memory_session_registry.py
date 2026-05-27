"""J.2 — InMemorySessionRegistry tests.

Written RED before implementation exists. Spec:
issues/features/web-j-platform-abstractions.md § J.2

Acceptance criteria from the spec:
- create("default") returns a sid.
- get("default", sid) returns the entry.
- list("default") includes the sid.
- delete removes it.
- get on unknown sid returns None.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry():
    from armance.platform.sessions import InMemorySessionRegistry
    return InMemorySessionRegistry()


# ---------------------------------------------------------------------------
# create / get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_returns_a_sid(registry) -> None:
    sid = await registry.create("default")
    assert isinstance(sid, str)
    assert len(sid) > 0


@pytest.mark.asyncio
async def test_create_returns_unique_sids(registry) -> None:
    sid1 = await registry.create("default")
    sid2 = await registry.create("default")
    assert sid1 != sid2


@pytest.mark.asyncio
async def test_get_returns_entry_after_create(registry) -> None:
    sid = await registry.create("default")
    entry = await registry.get("default", sid)
    assert entry is not None


@pytest.mark.asyncio
async def test_get_unknown_sid_returns_none(registry) -> None:
    entry = await registry.get("default", "nonexistent-sid")
    assert entry is None


@pytest.mark.asyncio
async def test_get_wrong_project_returns_none(registry) -> None:
    sid = await registry.create("project-a")
    entry = await registry.get("project-b", sid)
    assert entry is None


# ---------------------------------------------------------------------------
# SessionEntry carries sid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_entry_has_sid(registry) -> None:
    sid = await registry.create("default")
    entry = await registry.get("default", sid)
    assert entry is not None
    assert entry.sid == sid


@pytest.mark.asyncio
async def test_session_entry_has_project_id(registry) -> None:
    sid = await registry.create("my-project")
    entry = await registry.get("my-project", sid)
    assert entry is not None
    assert entry.project_id == "my-project"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_includes_created_sid(registry) -> None:
    sid = await registry.create("default")
    sids = await registry.list("default")
    assert sid in sids


@pytest.mark.asyncio
async def test_list_multiple_sessions(registry) -> None:
    sid1 = await registry.create("default")
    sid2 = await registry.create("default")
    sids = await registry.list("default")
    assert sid1 in sids
    assert sid2 in sids


@pytest.mark.asyncio
async def test_list_empty_project(registry) -> None:
    sids = await registry.list("no-such-project")
    assert sids == []


@pytest.mark.asyncio
async def test_list_isolates_projects(registry) -> None:
    sid_a = await registry.create("project-a")
    await registry.create("project-b")
    sids_a = await registry.list("project-a")
    assert sid_a in sids_a
    assert len(sids_a) == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_removes_sid(registry) -> None:
    sid = await registry.create("default")
    await registry.delete("default", sid)
    entry = await registry.get("default", sid)
    assert entry is None


@pytest.mark.asyncio
async def test_delete_removes_from_list(registry) -> None:
    sid = await registry.create("default")
    await registry.delete("default", sid)
    sids = await registry.list("default")
    assert sid not in sids


@pytest.mark.asyncio
async def test_delete_missing_is_silent(registry) -> None:
    """Deleting a non-existent (project, sid) must not raise."""
    await registry.delete("default", "nonexistent-sid")


@pytest.mark.asyncio
async def test_delete_does_not_affect_other_sessions(registry) -> None:
    sid1 = await registry.create("default")
    sid2 = await registry.create("default")
    await registry.delete("default", sid1)
    entry2 = await registry.get("default", sid2)
    assert entry2 is not None
