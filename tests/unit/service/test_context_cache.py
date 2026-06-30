from __future__ import annotations

from pathlib import Path

from armance.service.context_service import ContextService
from armance.storage.paths import context_cache_path


def test_cache_roundtrip(tmp_path: Path):
    root = tmp_path / ".armance"
    svc = ContextService(root)
    assert svc.read_cache() == ""
    svc.cache_append("forest restoration near town")
    svc.cache_append("audience: civil society")
    body = svc.read_cache()
    assert "forest restoration near town" in body
    assert "audience: civil society" in body
    assert context_cache_path(root).exists()
    svc.clear_cache()
    assert svc.read_cache() == ""


def test_cache_full_threshold(tmp_path: Path):
    svc = ContextService(tmp_path / ".armance")
    assert svc.cache_is_full() is False
    svc.cache_append("x" * 1600)  # exceeds CACHE_FULL_CHARS (1500)
    assert svc.cache_is_full() is True


def test_cache_append_ignores_empty(tmp_path: Path):
    svc = ContextService(tmp_path / ".armance")
    svc.cache_append("")
    svc.cache_append("   ")
    assert svc.read_cache() == ""


def test_layered_context_includes_cache(tmp_path: Path):
    from armance.core.models.agent import Agent
    from armance.service.agents.specialist_runner import SpecialistRunner

    root = tmp_path / ".armance"
    ContextService(root).cache_append("forest restoration is the takeaway")

    runner = SpecialistRunner(root, config=None)
    agent = Agent(
        name="Samir",
        role="communication",
        provider="openrouter",
        model="x",
    )
    ctx = runner._build_layered_context(agent)
    assert "forest restoration is the takeaway" in ctx


def test_freeze_consumes_cache(tmp_path, monkeypatch):
    """freeze() must read the cache as its source and clear it after write."""
    import asyncio
    from unittest.mock import MagicMock

    from armance.config import Config
    from armance.core.models.agent import Agent
    from armance.service.agents.host_agent import HostAgentService

    root = tmp_path / ".armance"
    (root / "agents").mkdir(parents=True)
    (root / "context").mkdir(parents=True)

    ContextService(root).cache_append(
        "audience: civil society; topic: forest restoration"
    )

    agent = Agent(
        name="system-context",
        role="meta",
        character="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are Armance.",
    )
    host = HostAgentService(agent=agent, armance_root=root, config=Config())

    captured: dict = {}

    async def fake_call(client, name, messages, model, **kwargs):
        captured["messages"] = messages
        resp = MagicMock()
        resp.text = (
            "## Goal\nRestore forests near the town for civil society audiences "
            "over the coming season as a flagship environmental programme.\n"
        )
        resp.finish_reason = "stop"
        return resp

    monkeypatch.setattr(
        "armance.service.agents.host_agent.call_with_ledger", fake_call
    )
    monkeypatch.setattr(
        "armance.service.agents.host_agent.get_client",
        lambda *a, **k: object(),
    )

    asyncio.run(host.freeze())

    # Edit B: the cache must be folded in as the freeze SOURCE — its content
    # must reach the LLM compilation prompt (not merely be cleared afterwards).
    assert "messages" in captured, "freeze did not call the LLM"
    assert any(
        "forest restoration" in str(m.get("content", ""))
        for m in captured["messages"]
    ), "cache content was not used as the freeze source"
    # Cache must be cleared after a successful freeze.
    assert ContextService(root).read_cache() == ""
    # L0 must have been written.
    assert ContextService(root).read_l0_body()
