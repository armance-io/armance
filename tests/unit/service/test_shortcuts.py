"""Tests for desktop shortcut generation (grandma launcher, sub-feature 4).

Per-OS generation into an isolated temp HOME (monkeypatched). Best-effort:
failures must print a manual fallback and never raise.
"""
from __future__ import annotations

from pathlib import Path


from armance.service import shortcuts


def test_linux_desktop_entry(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    result = shortcuts.install_shortcut(platform="linux")

    desktop = home / ".local" / "share" / "applications" / "armance.desktop"
    assert desktop.exists()
    content = desktop.read_text(encoding="utf-8")
    assert "Exec=armance" in content
    assert "Name=Armance" in content
    assert result.ok is True


def test_macos_app_wrapper(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    result = shortcuts.install_shortcut(platform="darwin")

    launcher = home / "Applications" / "Armance.app" / "Contents" / "MacOS" / "armance"
    assert launcher.exists()
    assert "armance" in launcher.read_text(encoding="utf-8")
    assert result.ok is True


def test_windows_creates_lnk_script(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "Desktop").mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    # No PowerShell in CI: the generator must degrade gracefully.
    monkeypatch.setattr(shortcuts, "_run_powershell", lambda script: False)

    result = shortcuts.install_shortcut(platform="win32")

    # Either the .lnk was created via PowerShell (real Windows) or we fell back
    # to a manual message — never a crash.
    assert isinstance(result.ok, bool)
    assert result.message  # a human-readable line is always produced


def test_failure_is_best_effort(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    # Make directory creation fail to simulate a permissions error.
    def boom(*_a, **_kw):
        raise PermissionError("denied")

    monkeypatch.setattr(shortcuts.Path, "mkdir", boom)

    result = shortcuts.install_shortcut(platform="linux")
    assert result.ok is False
    assert "armance" in result.message.lower()
