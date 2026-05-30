"""G8 — GET /sessions/{sid}/agents + PATCH .../agents/{name}.

Tests:
  - GET returns agents list with model + provider + reasoning.
  - PATCH {"model": "..."} writes the agent file (no new write surface).
  - PATCH on staff agent (system-*) updates system-*.md.
  - PATCH on specialist updates agents/<name>.md.
  - PATCH persona field → 422 {"error": "persona_via_malik_only"}.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import MagicMock

from armance.core.models.agent import Agent


def _make_agent(name: str, model: str = "gpt-4o-mini", provider: str = "openrouter",
                is_staff: bool = False) -> Agent:
    domain = "staff" if is_staff else "analyst"
    return Agent(name=name, domain=domain, model=model, provider=provider, reasoning=None)


def _write_agent_file(agents_dir: Path, agent: Agent) -> None:
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{agent.name}.md").write_text(agent.to_markdown(), encoding="utf-8")


@pytest.fixture()
def session_with_agents(armance_root: Path, client: AsyncClient):
    """Fixture that creates a fake WebSession with two agents."""
    from backend.state import WebSession

    agents_dir = armance_root / "agents"
    alice = _make_agent("Alice", model="gpt-4o-mini")
    bob = _make_agent("system-context", model="claude-3-haiku", is_staff=True)
    _write_agent_file(agents_dir, alice)
    _write_agent_file(agents_dir, bob)

    mock_ctx = MagicMock()
    mock_ctx.armance_root = armance_root
    mock_ctx.agents = [alice, bob]

    mock_ledger = MagicMock()
    mock_ledger.snapshot.return_value = {}
    mock_ctx.ledger = mock_ledger

    ws = WebSession(
        sid="test-sid",
        project_id="default",
        session=MagicMock(),
        ctx=mock_ctx,
        bus=MagicMock(),
        handler=MagicMock(),
    )
    from backend.state import AppState
    import os
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from backend.main import create_app
    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    app.state.app_state.put(ws)
    return app, ws


@pytest.mark.asyncio
async def test_get_agents_list(session_with_agents, armance_root: Path) -> None:
    app, ws = session_with_agents
    from httpx import AsyncClient as AC, ASGITransport
    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/projects/default/sessions/{ws.sid}/agents")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    names = {a["name"] for a in body}
    assert "Alice" in names
    assert "system-context" in names
    alice = next(a for a in body if a["name"] == "Alice")
    assert alice["model"] == "gpt-4o-mini"
    assert alice["provider"] == "openrouter"


@pytest.mark.asyncio
async def test_patch_agent_model_specialist(session_with_agents, armance_root: Path) -> None:
    app, ws = session_with_agents
    from httpx import AsyncClient as AC, ASGITransport
    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/Alice",
            json={"model": "claude-3-5-haiku"},
        )

    assert resp.status_code == 200
    agent_path = armance_root / "agents" / "Alice.md"
    saved = Agent.load(agent_path)
    assert saved.model == "claude-3-5-haiku"


@pytest.mark.asyncio
async def test_patch_agent_model_staff(session_with_agents, armance_root: Path) -> None:
    app, ws = session_with_agents
    from httpx import AsyncClient as AC, ASGITransport
    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/system-context",
            json={"model": "gemini-2.0-flash"},
        )

    assert resp.status_code == 200
    agent_path = armance_root / "agents" / "system-context.md"
    saved = Agent.load(agent_path)
    assert saved.model == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_patch_persona_rejected(session_with_agents, armance_root: Path) -> None:
    app, ws = session_with_agents
    from httpx import AsyncClient as AC, ASGITransport
    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/Alice",
            json={"persona": "new persona text"},
        )

    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "persona_via_malik_only"
