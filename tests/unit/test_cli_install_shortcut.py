"""`armance install-shortcut` dispatch (grandma launcher, sub-feature 4)."""
from __future__ import annotations

from pathlib import Path

from armance import cli
from armance.service import shortcuts


def test_cmd_install_shortcut_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "cmd_install_shortcut", cli.cmd_install_shortcut
    )  # keep real
    monkeypatch.setattr(
        shortcuts,
        "install_shortcut",
        lambda *a, **k: shortcuts.ShortcutResult(ok=True, message="created at X"),
    )
    rc = cli.cmd_install_shortcut()
    assert rc == 0
    assert "created at X" in capsys.readouterr().out


def test_cmd_install_shortcut_failure_returns_1(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        shortcuts,
        "install_shortcut",
        lambda *a, **k: shortcuts.ShortcutResult(ok=False, message="run armance manually"),
    )
    rc = cli.cmd_install_shortcut()
    assert rc == 1
    assert "manually" in capsys.readouterr().out


def test_main_routes_install_shortcut(monkeypatch) -> None:
    called = {}

    def _stub() -> int:
        called["hit"] = True
        return 0

    monkeypatch.setattr(cli, "cmd_install_shortcut", _stub)
    rc = cli.main(["install-shortcut"])
    assert rc == 0
    assert called.get("hit") is True
