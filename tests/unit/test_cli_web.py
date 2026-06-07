"""cmd_web — background launch returns 0 and logs to a file."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from armance.cli import cmd_web
from armance.web import server_lock


def _fake_ready_response() -> MagicMock:
    resp = MagicMock()
    resp.status = 200
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return resp


def test_cmd_web_background_returns_zero_and_writes_log(tmp_path: Path) -> None:
    proc = MagicMock()
    proc.poll.return_value = None  # still running during readiness wait
    proc.pid = 4321

    with patch("subprocess.Popen", return_value=proc) as popen, \
         patch("urllib.request.urlopen", return_value=_fake_ready_response()):
        rc = cmd_web(tmp_path, ["--no-browser"])

    assert rc == 0
    # The server was launched in the background (look for the uvicorn call —
    # unrelated library calls like ldconfig may also go through Popen).
    uvicorn_calls = [
        c for c in popen.call_args_list
        if c.args and isinstance(c.args[0], list) and "uvicorn" in c.args[0]
    ]
    assert len(uvicorn_calls) == 1
    log_path = tmp_path / ".armance" / "logs" / "web-server.log"
    assert log_path.exists()
    # stdout/stderr were redirected to the log file, not the terminal.
    kwargs = uvicorn_calls[0].kwargs
    assert kwargs.get("stdout") is not None
    assert kwargs.get("stderr") is not None
    assert kwargs.get("start_new_session") is True


def test_cmd_web_background_reports_early_exit(tmp_path: Path) -> None:
    proc = MagicMock()
    proc.poll.return_value = 1  # exited immediately
    proc.returncode = 1
    proc.pid = 4322

    with patch("subprocess.Popen", return_value=proc), \
         patch("urllib.request.urlopen", side_effect=OSError("not up")):
        rc = cmd_web(tmp_path, ["--no-browser"])

    assert rc == 1


def test_cmd_web_refuses_second_instance(tmp_path: Path) -> None:
    # A live lock (our own pid) → launching again is refused without spawning.
    server_lock.write_lock(tmp_path, os.getpid(), 8000)
    with patch("subprocess.Popen") as popen:
        rc = cmd_web(tmp_path, ["--no-browser"])
    assert rc == 1
    uvicorn_calls = [
        c for c in popen.call_args_list
        if c.args and isinstance(c.args[0], list) and "uvicorn" in c.args[0]
    ]
    assert uvicorn_calls == []
    server_lock.clear_lock(tmp_path)


def test_cmd_web_stop_terminates_and_returns_zero(tmp_path: Path) -> None:
    server_lock.write_lock(tmp_path, os.getpid(), 8000)
    with patch.object(server_lock, "_signal"), \
         patch.object(server_lock, "_pid_alive", side_effect=[True, False]):
        rc = cmd_web(tmp_path, ["--stop"])
    assert rc == 0
    assert server_lock.read_lock(tmp_path) is None


def test_cmd_web_stop_without_server_returns_one(tmp_path: Path) -> None:
    rc = cmd_web(tmp_path, ["--stop"])
    assert rc == 1


def test_cmd_web_passes_token_to_child_and_prints_security(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """Epic S · S.3 — auto token handed to the child via env + printed."""
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    from armance.service import security
    security.reset_web_secret_cache()

    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 9999

    with patch("subprocess.Popen", return_value=proc) as popen, \
         patch("urllib.request.urlopen", return_value=_fake_ready_response()):
        rc = cmd_web(tmp_path, ["--no-browser"])

    assert rc == 0
    uvicorn_calls = [
        c for c in popen.call_args_list
        if c.args and isinstance(c.args[0], list) and "uvicorn" in c.args[0]
    ]
    child_env = uvicorn_calls[0].kwargs["env"]
    token = child_env["ARMANCE_WEB_PASSWORD"]
    assert len(token) == 32  # auto-generated 32-hex token
    out = capsys.readouterr().out
    assert "[SECURITY]" in out
    assert token in out  # the printed URL/notice carries the token
    security.reset_web_secret_cache()


def test_cmd_web_uses_configured_password_not_in_url(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """A configured password is honoured and never leaked into the URL."""
    monkeypatch.setenv("ARMANCE_WEB_PASSWORD", "hunter2")
    from armance.service import security
    security.reset_web_secret_cache()

    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 9998

    with patch("subprocess.Popen", return_value=proc) as popen, \
         patch("urllib.request.urlopen", return_value=_fake_ready_response()):
        rc = cmd_web(tmp_path, ["--no-browser"])

    assert rc == 0
    uvicorn_calls = [
        c for c in popen.call_args_list
        if c.args and isinstance(c.args[0], list) and "uvicorn" in c.args[0]
    ]
    assert uvicorn_calls[0].kwargs["env"]["ARMANCE_WEB_PASSWORD"] == "hunter2"
    out = capsys.readouterr().out
    assert "hunter2" not in out  # password must not travel in the URL/output
    security.reset_web_secret_cache()
