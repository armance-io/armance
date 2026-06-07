#!/usr/bin/env sh
# Armance installer — installs or upgrades from GitHub
# Usage: curl -sSL https://raw.githubusercontent.com/armance-io/armance/main/install.sh | sh
set -e

REPO="https://github.com/armance-io/armance.git"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
_green() { printf '\033[32m%s\033[0m\n' "$*"; }
_dim()   { printf '\033[2m%s\033[0m\n'  "$*"; }

# ── Python version check ──────────────────────────────────────────────────────
_python=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        _ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        _major=$(echo "$_ver" | cut -d. -f1)
        _minor=$(echo "$_ver" | cut -d. -f2)
        if [ "$_major" -ge "$MIN_PYTHON_MAJOR" ] && [ "$_minor" -ge "$MIN_PYTHON_MINOR" ]; then
            _python="$candidate"
            break
        fi
    fi
done

if [ -z "$_python" ]; then
    _red "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found."
    _dim "Install it from https://www.python.org/downloads/ and re-run."
    exit 1
fi
_dim "Using $($_python --version)"

# ── Clean up any stale binary not managed by uv/pipx ─────────────────────────
_stale_bin=""
for _bindir in "$HOME/.local/bin" "/usr/local/bin"; do
    if [ -f "$_bindir/armance" ]; then
        _stale_bin="$_bindir/armance"
        break
    fi
done

# ── Install or upgrade (uv > pipx > pip) ─────────────────────────────────────
if command -v uv >/dev/null 2>&1; then
    _dim "Installer: uv tool"
    uv tool uninstall armance 2>/dev/null || true
    [ -n "$_stale_bin" ] && rm -f "$_stale_bin"
    uv tool install "git+https://github.com/armance-io/armance.git"

elif command -v pipx >/dev/null 2>&1; then
    _dim "Installer: pipx"
    pipx uninstall armance 2>/dev/null || true
    [ -n "$_stale_bin" ] && rm -f "$_stale_bin"
    pipx install "git+${REPO}"

else
    _dim "pipx not found — installing pipx first via pip"
    "$_python" -m pip install --quiet --user pipx
    "$_python" -m pipx ensurepath --quiet
    "$_python" -m pipx install "git+${REPO}"
    _dim "Restart your shell (or run: source ~/.bashrc) so PATH includes ~/.local/bin"
fi

# ── Verify ────────────────────────────────────────────────────────────────────
if command -v armance >/dev/null 2>&1; then
    _green "armance installed successfully."
    _dim "Run: armance init"
else
    _dim "armance installed but not yet on PATH."
    _dim "Restart your shell, then run: armance init"
fi
