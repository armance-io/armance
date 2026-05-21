"""Tests for armance.service.llm_service.get_client factory."""
from __future__ import annotations

import pytest

from armance.config import Config, ProviderConfig
from armance.service.llm_service import get_client
from armance.providers.claude_code import ClaudeCodeClient
from armance.providers.gemini import GeminiClient
from armance.providers.openrouter import OpenRouterClient


def _config(*providers: ProviderConfig) -> Config:
    return Config(
        providers=list(providers),
        default_provider=providers[0].name if providers else "openrouter",
        default_model="m",
    )


def test_factory_returns_openrouter_client() -> None:
    cfg = _config(ProviderConfig(name="openrouter", api_key="k"))
    assert isinstance(get_client("openrouter", cfg), OpenRouterClient)


def test_factory_returns_claude_code_client() -> None:
    cfg = _config(ProviderConfig(name="claude-code"))
    assert isinstance(get_client("claude-code", cfg), ClaudeCodeClient)


def test_factory_returns_gemini_client() -> None:
    cfg = _config(ProviderConfig(name="gemini", api_key="k"))
    assert isinstance(get_client("gemini", cfg), GeminiClient)


def test_factory_unknown_provider_raises() -> None:
    cfg = _config(ProviderConfig(name="openrouter"))
    with pytest.raises(KeyError):
        get_client("missing", cfg)


@pytest.mark.asyncio
async def test_llm_service_retries_and_raises(monkeypatch, tmp_path) -> None:
    from unittest.mock import AsyncMock, MagicMock
    from armance.core.protocols.llm import LLMResponse
    from armance.service.llm_service import call_with_ledger, set_current_config
    
    cfg = Config(log_level="INFO")
    set_current_config(cfg)
    
    # Mock LLMClient that fails twice and succeeds on the 3rd attempt
    mock_client = MagicMock()
    mock_client.complete = AsyncMock()
    mock_client.stream_complete = AsyncMock()
    
    # Setup mock file directory for logs
    monkeypatch.setattr("pathlib.Path.cwd", MagicMock(return_value=tmp_path))
    
    # First 2 calls raise, 3rd succeeds
    mock_client.stream_complete.side_effect = [
        RuntimeError("Transient 429 Error"),
        RuntimeError("Transient 500 Error"),
        LLMResponse(text="Success response!", tokens_in=10, tokens_out=20, finish_reason="stop", cost_usd=0.001)
    ]
    
    # Execute call_with_ledger with a mock token stream callback
    tokens_streamed = []
    def mock_on_token(tok: str):
        tokens_streamed.append(tok)
        
    # We patch sleep to avoid waiting during tests
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    
    resp = await call_with_ledger(
        mock_client,
        "test_agent",
        [{"role": "user", "content": "hello"}],
        "gpt-test",
        on_token=mock_on_token
    )
    
    assert resp.text == "Success response!"
    assert mock_client.stream_complete.call_count == 3
    
    # Verify that retry notifications were sent to the stream callback
    assert len(tokens_streamed) == 2
    assert "Transient 429 Error" in tokens_streamed[0]
    assert "Transient 500 Error" in tokens_streamed[1]
    
    # Verify log file got written
    log_file = tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 4  # 1 request, 2 failures, 1 successful response
    
    # Under INFO level, verify the response doesn't have the full text (it only has a preview)
    import json
    response_log = json.loads(lines[-1])
    assert "Success response!" not in response_log
    assert "response_preview" in response_log
    assert response_log["response_preview"] == "Success response!..."


@pytest.mark.asyncio
async def test_llm_service_debug_logging(monkeypatch, tmp_path) -> None:
    from unittest.mock import AsyncMock, MagicMock
    from armance.core.protocols.llm import LLMResponse
    from armance.service.llm_service import call_with_ledger, set_current_config
    
    cfg = Config(log_level="DEBUG")
    set_current_config(cfg)
    
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=LLMResponse(
        text="Full detailed output", tokens_in=5, tokens_out=5, finish_reason="stop", cost_usd=0.0
    ))
    
    monkeypatch.setattr("pathlib.Path.cwd", MagicMock(return_value=tmp_path))
    
    await call_with_ledger(
        mock_client,
        "debug_agent",
        [{"role": "user", "content": "debug query"}],
        "gpt-debug"
    )
    
    log_file = tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    
    # Under DEBUG level, verify full message array and response text are logged!
    import json
    request_log = json.loads(lines[0])
    assert "messages" in request_log
    assert request_log["messages"][0]["content"] == "debug query"
    
    response_log = json.loads(lines[1])
    assert "text" in response_log
    assert response_log["text"] == "Full detailed output"
