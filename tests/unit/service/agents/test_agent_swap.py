"""Agent model swap — `/agent-swap` repairs a model in place, persona intact."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agents.agent_swap import (
    SwapResult,
    _split_provider_model,
    swap_agent_model,
)


def _save(root: Path, name: str, **kw) -> Agent:
    a = Agent(
        name=name, role="expert", provider="openrouter", model="old-model",
        system_prompt="Tu es un expert distinctif avec une vraie persona.", **kw,
    )
    a.save(root / "agents" / f"{name}.md")
    return a


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    (r / "agents").mkdir(parents=True)
    return r


def test_split_provider_model_keeps_inner_colons_and_slashes() -> None:
    assert _split_provider_model("openrouter/qwen/qwen3:free") == (
        "openrouter", "qwen/qwen3:free",
    )
    assert _split_provider_model("bare-model") == ("", "bare-model")


@pytest.mark.asyncio
async def test_swap_changes_model_preserves_persona(root: Path) -> None:
    _save(root, "Elena")
    with patch("armance.service.agents.health.check_agent_health",
               new=AsyncMock(return_value=type("H", (), {"status": "ok"})())), \
         patch("armance.service.agents.health.persist_health"):
        res = await swap_agent_model(
            "Elena", "custom-openai/gpt-5", None, root / "agents", Config(),
        )
    assert res.status == "ok"
    assert res.provider == "custom-openai" and res.model == "gpt-5"
    reloaded = Agent.load(root / "agents" / "Elena.md")
    assert reloaded.provider == "custom-openai" and reloaded.model == "gpt-5"
    # Persona, role untouched.
    assert "vraie persona" in reloaded.system_prompt
    assert reloaded.role == "expert"


@pytest.mark.asyncio
async def test_swap_sets_boost_when_given(root: Path) -> None:
    _save(root, "Marc")
    with patch("armance.service.agents.health.check_agent_health",
               new=AsyncMock(return_value=type("H", (), {"status": "ok"})())), \
         patch("armance.service.agents.health.persist_health"):
        res = await swap_agent_model(
            "Marc", "openrouter/gpt-4o", "openrouter/o3", root / "agents", Config(),
        )
    assert res.boost_model == "o3"
    reloaded = Agent.load(root / "agents" / "Marc.md")
    assert reloaded.boost_provider == "openrouter" and reloaded.boost_model == "o3"


@pytest.mark.asyncio
async def test_swap_unknown_agent(root: Path) -> None:
    res = await swap_agent_model("Ghost", "openrouter/x", None, root / "agents", Config())
    assert res == SwapResult(status="unknown", name="Ghost")


@pytest.mark.asyncio
async def test_swap_refuses_staff(root: Path) -> None:
    res = await swap_agent_model(
        "system-judge", "openrouter/x", None, root / "agents", Config(),
    )
    assert res.status == "staff"


@pytest.mark.asyncio
async def test_swap_records_unhealthy_status(root: Path) -> None:
    """A bad model leaves last_health as error — surfaced, not hidden."""
    _save(root, "Lars")
    with patch("armance.service.agents.health.check_agent_health",
               new=AsyncMock(return_value=type("H", (), {"status": "error:400"})())), \
         patch("armance.service.agents.health.persist_health"):
        res = await swap_agent_model(
            "Lars", "custom-openai/nonexistent", None, root / "agents", Config(),
        )
    assert res.status == "ok"  # the swap itself succeeded
    assert res.health == "error:400"  # but the new model is unreachable
