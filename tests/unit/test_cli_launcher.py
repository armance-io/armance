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

    def _fake_cmd_web(root=None, remaining=None) -> int:
        opened["root"] = root
        opened["remaining"] = remaining
        return 0

    # A fixed password → no token in the URL (a configured secret never travels
    # in the query string).
    monkeypatch.setenv("ARMANCE_WEB_PASSWORD", "fixed-secret")
    monkeypatch.setattr(cli, "cmd_web", _fake_cmd_web)
    monkeypatch.setattr(cli, "_open_launcher_browser", lambda path: opened.setdefault("path", path))

    # No global config.yaml exists (isolate_global_config is empty).
    assert not paths.global_config_path().exists()
    rc = cli.cmd_launcher()
    assert rc == 0
    # The browser is pointed at the setup wizard (no token — password is fixed).
    assert opened.get("path") == "/setup"
    # The launcher server is homed in the global config dir, not cwd.
    assert opened["root"] == paths.global_config_dir()


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
    monkeypatch.setattr(cli, "cmd_web", lambda root=None, remaining=None: 0)
    monkeypatch.setattr(cli, "_open_launcher_browser", lambda path: opened.setdefault("path", path))

    rc = cli.cmd_launcher()
    assert rc == 0
    assert opened["path"].startswith("/setup?token=")
    # The child server inherits the same secret (parent + gate agree).
    token = opened["path"].split("token=", 1)[1]
    assert os.environ["ARMANCE_WEB_PASSWORD"] == token


def test_launcher_configured_opens_launcher(monkeypatch, isolate_global_config: Path) -> None:
    """Global config present → browser opens the launcher window."""
    opened = {}
    monkeypatch.setattr(cli, "cmd_web", lambda root=None, remaining=None: 0)
    monkeypatch.setattr(cli, "_open_launcher_browser", lambda path: opened.setdefault("path", path))

    paths.global_config_path().write_text("language: en\n", encoding="utf-8")
    rc = cli.cmd_launcher()
    assert rc == 0
    assert opened.get("path") == "/launcher"
