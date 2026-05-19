#!/usr/bin/env sh
# Armance uninstaller
# Usage: curl -sSL https://raw.githubusercontent.com/armance-io/armance/main/uninstall.sh | sh
set -e

_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
_green() { printf '\033[32m%s\033[0m\n' "$*"; }
_dim()   { printf '\033[2m%s\033[0m\n'  "$*"; }

if command -v uv >/dev/null 2>&1 && uv tool list 2>/dev/null | grep -q "^armance"; then
    _dim "Removing via uv tool..."
    uv tool uninstall armance
    _green "armance uninstalled."

elif command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q "^armance"; then
    _dim "Removing via pipx..."
    pipx uninstall armance
    _green "armance uninstalled."

else
    _red "armance not found in uv tool or pipx. Nothing to remove."
    _dim "If installed manually via pip, run: pip uninstall armance"
    exit 1
fi

_dim "Your .armance/ project directories are untouched."
