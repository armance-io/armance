import pytest
from unittest.mock import MagicMock
import tiktoken

@pytest.fixture(autouse=True)
def mock_tiktoken(monkeypatch):
    """Mock tiktoken to avoid network calls during tests."""
    mock_enc = MagicMock()
    # Simple length-based token estimation, handles empty text
    mock_enc.encode.side_effect = lambda text: [0] * (len(text) // 4 + 1) if text else []
    mock_enc.decode.side_effect = lambda tokens: " " * (len(tokens) * 4)
    
    monkeypatch.setattr(tiktoken, "get_encoding", MagicMock(return_value=mock_enc))
    monkeypatch.setattr(tiktoken, "encoding_for_model", MagicMock(return_value=mock_enc))
    return mock_enc
