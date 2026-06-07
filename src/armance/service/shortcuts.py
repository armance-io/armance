"""Desktop shortcut generation for the grandma launcher (3 platforms).

``armance install-shortcut`` creates a clickable icon that launches ``armance``
(the launcher). Best-effort: if creation fails (permissions, missing shell),
it returns a result carrying a manual fallback message and never raises.

Icon assets ship in the wheel at ``armance/assets/icon.{ico,png,icns}``.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ShortcutResult:
    ok: bool
    message: str
    path: Path | None = None


def _icon_path(suffix: str) -> Path | None:
    """Locate a bundled icon asset, or None if it is not shipped."""
    try:
        asset = resources.files("armance").joinpath(f"assets/icon.{suffix}")
        p = Path(str(asset))
        return p if p.exists() else None
    except (ModuleNotFoundError, AttributeError, OSError):
        return None


def _run_powershell(script: str) -> bool:
    """Run a PowerShell script; return True on success. Isolated for testing."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=30,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _install_linux() -> ShortcutResult:
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    icon = _icon_path("png")
    icon_line = f"Icon={icon}\n" if icon else ""
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Armance\n"
        "Comment=A brain you consult when the choice matters\n"
        "Exec=armance\n"
        f"{icon_line}"
        "Terminal=false\n"
        "Categories=Office;Utility;\n"
    )
    target = apps / "armance.desktop"
    target.write_text(entry, encoding="utf-8")
    target.chmod(0o755)

    # Also drop one on the Desktop if it exists.
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        (desktop / "armance.desktop").write_text(entry, encoding="utf-8")
        (desktop / "armance.desktop").chmod(0o755)

    return ShortcutResult(ok=True, message=f"Desktop entry created at {target}", path=target)


def _install_macos() -> ShortcutResult:
    app = Path.home() / "Applications" / "Armance.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    launcher = macos / "armance"
    launcher.write_text("#!/bin/sh\nexec armance\n", encoding="utf-8")
    launcher.chmod(0o755)

    plist = app / "Contents" / "Info.plist"
    plist.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        "  <key>CFBundleName</key><string>Armance</string>\n"
        "  <key>CFBundleExecutable</key><string>armance</string>\n"
        "  <key>CFBundleIdentifier</key><string>io.armance.launcher</string>\n"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    return ShortcutResult(ok=True, message=f"App wrapper created at {app}", path=launcher)


def _install_windows() -> ShortcutResult:
    desktop = Path.home() / "Desktop"
    lnk = desktop / "Armance.lnk"
    icon = _icon_path("ico")
    icon_line = f"$s.IconLocation = '{icon}';" if icon else ""
    # pythonw -m armance → no console window.
    script = (
        "$w = New-Object -ComObject WScript.Shell; "
        f"$s = $w.CreateShortcut('{lnk}'); "
        "$s.TargetPath = 'pythonw'; "
        "$s.Arguments = '-m armance'; "
        f"{icon_line} "
        "$s.Save()"
    )
    if _run_powershell(script):
        return ShortcutResult(ok=True, message=f"Shortcut created at {lnk}", path=lnk)
    return ShortcutResult(
        ok=False,
        message=(
            "Could not create a Windows shortcut automatically. Create one "
            "manually: target 'pythonw -m armance' (or just run `armance`)."
        ),
    )


def install_shortcut(platform: str | None = None) -> ShortcutResult:
    """Create a desktop shortcut for the current OS. Best-effort, never raises."""
    plat = platform or sys.platform
    try:
        if plat.startswith("linux"):
            return _install_linux()
        if plat == "darwin":
            return _install_macos()
        if plat.startswith("win"):
            return _install_windows()
        return ShortcutResult(
            ok=False, message=f"Unsupported platform {plat!r}; run `armance` directly."
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, surface a manual path
        logger.warning("shortcut creation failed: %s", exc)
        return ShortcutResult(
            ok=False,
            message=(
                f"Could not create an Armance shortcut ({exc}). You can still "
                "launch it by running `armance` in a terminal."
            ),
        )
