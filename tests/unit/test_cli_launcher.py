"""Bare `armance` → launcher / first-run wizard (grandma launcher, SF5)."""
from __future__ import annotations

import os
from pathlib import Path

from armance import cli, paths


def test_bare_armance_routes_to_launcher(monkeypatch) -> None:
    """`armance` with no args invokes the launcher command."""
    called = {}

    def _stub() -> int:
        called["hit"] = True
        return 0

    monkeypatch.setattr(cli, "cmd_launcher", _stub)
    rc = cli.main([])
    assert rc == 0
    assert called.get("hit") is True


def test_help_still_prints_usage(monkeypatch, capsys) -> None:
    """`-h` / `help` keep printing usage (not the launcher)."""
    monkeypatch.setattr(cli, "cmd_launcher", lambda: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = cli.main(["--help"])
    assert rc == 0
    assert "usage" in capsys.readouterr().err.lower()


def test_launcher_first_run_opens_setup(monkeypatch, isolate_global_config: Path) -> None:
    """No global config → launcher boots in setup mode (browser → /setup)."""
    opened = {}

    def _fake_cmd_web(root=None, remaining=None, *, data_dir=None, launch_url_suffix="") -> int:
        opened["root"] = root
        opened["remaining"] = remaining
        opened["data_dir"] = data_dir
        opened["path"] = launch_url_suffix
        return 0

    # A fixed password → no token in the URL (a configured secret never travels
    # in the query string).
    monkeypatch.setenv("ARMANCE_WEB_PASSWORD", "fixed-secret")
    monkeypatch.setattr(cli, "cmd_web", _fake_cmd_web)

    # No global config.yaml exists (isolate_global_config is empty).
    assert not paths.global_config_path().exists()
    rc = cli.cmd_launcher()
    assert rc == 0
    # The browser is pointed at the setup wizard (no token — password is fixed).
    assert opened.get("path") == "/setup"
    # The launcher server is homed in the global config dir — both as the root
    # and as the data dir (no nested .armance under ~/.config/armance).
    assert opened["root"] == paths.global_config_dir()
    assert opened["data_dir"] == paths.global_config_dir()


def test_launcher_auto_token_in_url(monkeypatch, isolate_global_config: Path) -> None:
    """First run with no password → the auto-generated token is in the URL.

    Without it, the page's first (gated) API call 401s and the grandma hits a
    login wall (the token lives only in the terminal). SEC5 then exchanges the
    ?token for a cookie. The same secret is pinned for the child server.
    """
    from armance.service import security

    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    security.reset_web_secret_cache()
    opened = {}
    def _fake_cmd_web(root=None, remaining=None, *, data_dir=None, launch_url_suffix="") -> int:
        opened["path"] = launch_url_suffix
        return 0
    monkeypatch.setattr(cli, "cmd_web", _fake_cmd_web)

    rc = cli.cmd_launcher()
    assert rc == 0
    assert opened["path"].startswith("/setup?token=")
    # The child server inherits the same secret (parent + gate agree).
    token = opened["path"].split("token=", 1)[1]
    assert os.environ["ARMANCE_WEB_PASSWORD"] == token


def test_bare_stop_routes_to_launcher_stop(monkeypatch) -> None:
    """`armance --stop` stops the global-homed launcher from any cwd."""
    captured = {}

    def _stub(stop: bool = False) -> int:
        captured["stop"] = stop
        return 0

    monkeypatch.setattr(cli, "cmd_launcher", _stub)
    rc = cli.main(["--stop"])
    assert rc == 0
    assert captured.get("stop") is True


def test_launcher_stop_targets_global_home(monkeypatch, isolate_global_config: Path) -> None:
    """cmd_launcher(stop=True) stops the server at the global config dir."""
    seen = {}

    def _fake_stop(data_dir):
        seen["data_dir"] = data_dir
        return True, "stopped"

    monkeypatch.setattr("armance.web.server_lock.stop_server", _fake_stop)
    rc = cli.cmd_launcher(stop=True)
    assert rc == 0
    assert seen["data_dir"] == paths.global_config_dir()


def test_launcher_configured_opens_launcher(monkeypatch, isolate_global_config: Path) -> None:
    """Global config present → browser opens the launcher window."""
    opened = {}
    def _fake_cmd_web(root=None, remaining=None, *, data_dir=None, launch_url_suffix="") -> int:
        opened["path"] = launch_url_suffix
        return 0
    monkeypatch.setattr(cli, "cmd_web", _fake_cmd_web)

    paths.global_config_path().write_text("language: en\n", encoding="utf-8")
    rc = cli.cmd_launcher()
    assert rc == 0
    assert opened.get("path") == "/launcher"
