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
        domain="communication",
        provider="openrouter",
        model="x",
    )
    ctx = runner._build_layered_context(agent)
    assert "forest restoration is the takeaway" in ctx
