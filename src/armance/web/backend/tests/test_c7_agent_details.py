"""C.7 — GET /projects/{pid}/sessions/{sid}/agents/{name} route.

Returns the agent's runtime metadata for the chat tooltip:
  - name, role, persona one-liner
  - provider, model, reasoning
  - cumulative tokens_in / tokens_out / cost (from the session ledger)

Spec: web-c-deliberation.md § C.7
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.mark.asyncio
async def test_get_agent_details_returns_payload(
    client: AsyncClient, armance_root: Path
) -> None:
    """GET /agents/{name} returns the contract fields."""
    # Seed: ensure a session exists.
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Seed a specialist agent in .armance/agents/ so the route can find it.
    agents_dir = armance_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / "Aisha.md").write_text(
        "---\n"
        "name: Aisha\n"
        "domain: historian\n"
        "role: historian\n"
        "provider: openrouter\n"
        "model: google/gemma-2-9b-it:free\n"
        "reasoning: medium\n"
        "description: sticks to primary sources\n"
        "---\n"
        "You are Aisha, a positivist historian.\n",
        encoding="utf-8",
    )

    # Append a ledger entry for Aisha so tokens_in/out > 0.
    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.ctx.ledger.record("Aisha", 120, 350, 0.0021)
    ws.ctx.agents.clear()
    from armance.core.models.agent import Agent
    ws.ctx.agents.append(Agent.load(agents_dir / "Aisha.md"))

    resp = await client.get(f"/projects/default/sessions/{sid}/agents/Aisha")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Aisha"
    assert data["role"] == "historian"
    assert data["provider"] == "openrouter"
    assert data["model"] == "google/gemma-2-9b-it:free"
    assert data["reasoning"] == "medium"
    assert data["tokens_in"] == 120
    assert data["tokens_out"] == 350
    # cost may be None or a float — both contract-valid.
    assert "cost_usd" in data
    assert "persona" in data


@pytest.mark.asyncio
async def test_augment_toggle_flips_boosted_state(
    client: AsyncClient, armance_root: Path
) -> None:
    """POST /agents/{name}/augment toggles the augmented state deterministically."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    agents_dir = armance_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / "Lea.md").write_text(
        "---\n"
        "name: Lea\n"
        "domain: historian\n"
        "role: historian\n"
        "provider: claude-code\n"
        "model: claude-haiku-4-5\n"
        "boost_provider: claude-code\n"
        "boost_model: claude-sonnet-4-6\n"
        "---\n"
        "You are Lea.\n",
        encoding="utf-8",
    )
    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.ctx.agents.clear()
    from armance.core.models.agent import Agent
    ws.ctx.agents.append(Agent.load(agents_dir / "Lea.md"))

    on = await client.post(
        f"/projects/default/sessions/{sid}/agents/Lea/augment",
        json={"enabled": True},
    )
    assert on.status_code == 200
    assert on.json()["boosted"] is True
    assert on.json()["effective_model"] == "claude-sonnet-4-6"
    assert "Lea" in ws.session.state.boosted_agents

    off = await client.post(
        f"/projects/default/sessions/{sid}/agents/Lea/augment",
        json={"enabled": False},
    )
    assert off.status_code == 200
    assert off.json()["boosted"] is False
    assert "Lea" not in ws.session.state.boosted_agents


@pytest.mark.asyncio
async def test_augment_non_boostable_stays_false(
    client: AsyncClient, armance_root: Path
) -> None:
    """Enabling augment on an agent with no boost_model is a no-op."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    agents_dir = armance_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / "Flat.md").write_text(
        "---\nname: Flat\ndomain: critic\nrole: critic\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\n---\nYou are Flat.\n",
        encoding="utf-8",
    )
    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.ctx.agents.clear()
    from armance.core.models.agent import Agent
    ws.ctx.agents.append(Agent.load(agents_dir / "Flat.md"))

    r = await client.post(
        f"/projects/default/sessions/{sid}/agents/Flat/augment",
        json={"enabled": True},
    )
    assert r.status_code == 200
    assert r.json()["boosted"] is False


@pytest.mark.asyncio
async def test_get_agent_unknown_returns_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/agents/Nobody")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_returns_zero_tokens_when_no_calls(
    client: AsyncClient, armance_root: Path
) -> None:
    """An agent that hasn't been called yet returns tokens_in/out == 0."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    agents_dir = armance_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / "Mute.md").write_text(
        "---\n"
        "name: Mute\n"
        "domain: critic\n"
        "role: critic\n"
        "provider: openrouter\n"
        "model: openai/gpt-4o-mini\n"
        "---\n"
        "You are Mute.\n",
        encoding="utf-8",
    )

    ws = client._transport.app.state.app_state.get(sid)  # type: ignore[attr-defined]
    ws.ctx.agents.clear()
    from armance.core.models.agent import Agent
    ws.ctx.agents.append(Agent.load(agents_dir / "Mute.md"))

    resp = await client.get(f"/projects/default/sessions/{sid}/agents/Mute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tokens_in"] == 0
    assert data["tokens_out"] == 0
