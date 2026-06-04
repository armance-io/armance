from __future__ import annotations

import pytest


class _YesHandler:
    def __init__(self, answer="yes"):
        self.answer = answer
        self.prompts = []

    async def prompt(self, checkpoint):
        from armance.service.checkpoint import CheckpointResponse
        self.prompts.append(checkpoint)
        return CheckpointResponse(content=self.answer)


@pytest.mark.asyncio
async def test_boost_request_yes_adds_agent() -> None:
    from armance.service.boost_ops import intercept_boost_tags
    from armance.core.models.agent import Agent
    agent = Agent(name="Sara", domain="strategy", provider="openrouter", model="base/m",
                  boost_provider="anthropic", boost_model="claude-opus-4-5")
    boosted: set[str] = set()
    handler = _YesHandler("yes")
    reply = "I need more depth. [EXECUTE:/boost-request]"
    cleaned = await intercept_boost_tags(reply, agent, boosted, handler, t=lambda k, **kw: k)
    assert "Sara" in boosted
    assert "[EXECUTE:/boost-request]" not in cleaned
    assert handler.prompts  # a checkpoint was shown


@pytest.mark.asyncio
async def test_boost_request_no_keeps_base() -> None:
    from armance.service.boost_ops import intercept_boost_tags
    from armance.core.models.agent import Agent
    agent = Agent(name="Sara", domain="strategy", provider="openrouter", model="base/m",
                  boost_provider="anthropic", boost_model="claude-opus-4-5")
    boosted: set[str] = set()
    handler = _YesHandler("no")
    cleaned = await intercept_boost_tags("[EXECUTE:/boost-request]", agent, boosted, handler, t=lambda k, **kw: k)
    assert "Sara" not in boosted
    assert "[EXECUTE:/boost-request]" not in cleaned


@pytest.mark.asyncio
async def test_boost_request_without_boost_model_is_noop() -> None:
    from armance.service.boost_ops import intercept_boost_tags
    from armance.core.models.agent import Agent
    agent = Agent(name="Sara", domain="strategy", provider="openrouter", model="base/m")  # not boostable
    boosted: set[str] = set()
    handler = _YesHandler("yes")
    cleaned = await intercept_boost_tags("[EXECUTE:/boost-request]", agent, boosted, handler, t=lambda k, **kw: k)
    assert "Sara" not in boosted
    assert handler.prompts == []  # no checkpoint when not boostable
    assert "[EXECUTE:/boost-request]" not in cleaned
