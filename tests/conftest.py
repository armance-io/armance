import pytest
from unittest.mock import MagicMock
import tiktoken


@pytest.fixture(autouse=True)
def isolate_global_config(monkeypatch, tmp_path_factory):
    """Redirect the global Armance config dir to a tmp path for every test.

    Clean-break (grandma launcher) made config / secrets / base-agents live in
    a single GLOBAL directory resolved via ``armance.paths.global_config_dir``.
    Without this, tests calling ``load_config`` / ``save_config`` would read and
    write the developer's real ``~/.config/armance``. Setting
    ``ARMANCE_CONFIG_DIR`` points every resolution at an isolated tmp dir.

    Uses ``tmp_path_factory`` (a *separate* dir) rather than the test's
    ``tmp_path`` so tests that assert on their own ``tmp_path`` contents are not
    polluted. A test that needs to seed global config takes this fixture as a
    parameter and writes into the yielded ``global_dir``.
    """
    global_dir = tmp_path_factory.mktemp("armance_global")
    monkeypatch.setenv("ARMANCE_CONFIG_DIR", str(global_dir))
    return global_dir


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
