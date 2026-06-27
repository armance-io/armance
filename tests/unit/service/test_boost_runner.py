from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.core.models.agent import Agent
from armance.core.models.task import Task
from armance.service.agents.specialist_runner import SpecialistRunner


@pytest.mark.asyncio
async def test_specialist_runner_uses_boosted_model(tmp_path: Path) -> None:
    agent = Agent(
        name="Alice",
        role="analyst",
        provider="openrouter",
        model="base-model",
        boost_provider="anthropic",
        boost_model="opus-model",
    )
    task = Task(prompt="hello", role="analyst")

    config = MagicMock()
    runner = SpecialistRunner(tmp_path, config)

    # Mock get_client and call_with_ledger
    with patch(
        "armance.service.agents.specialist_runner.get_client"
    ) as mock_get_client, patch(
        "armance.service.agents.specialist_runner.call_with_ledger",
        new_callable=AsyncMock,
    ) as mock_call_with_ledger:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_call_with_ledger.return_value = MagicMock(
            text="response text",
            tokens_in=10,
            tokens_out=20,
            cost_usd=0.01,
            finish_reason="stop",
        )

        await runner.run(agent, task, boosted_agents={"Alice"})

        # Assert get_client was called with the boost provider
        mock_get_client.assert_called_once_with("anthropic", config)

        # Assert call_with_ledger was called with the boost model and provider
        args, kwargs = mock_call_with_ledger.call_args
        assert kwargs["provider"] == "anthropic"
        assert args[3] == "opus-model"
