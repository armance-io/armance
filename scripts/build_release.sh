#!/usr/bin/env bash
# Build a release wheel with the web UI bundled.
#
# The static frontend (src/armance/web_dist/) is a build artifact, not tracked
# in git. A plain `uv build` or `pip install git+...` therefore ships an
# API-only wheel. This script regenerates the bundle and then builds the
# wheel/sdist that PyPI users get — so `pip install armance && armance web`
# serves the full UI with Python only (no Node at runtime).
#
# Requirements (build machine / CI only): Node + pnpm, uv.
# Usage: scripts/build_release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/web/frontend"
DEST="$ROOT/src/armance/web_dist"

echo "==> Building static frontend bundle"
cd "$FRONTEND"
pnpm install --frozen-lockfile
ARMANCE_STATIC_EXPORT=1 pnpm build

if [ ! -f "$FRONTEND/out/index.html" ]; then
  echo "ERROR: frontend build produced no out/index.html" >&2
  exit 1
fi

echo "==> Copying bundle into the package ($DEST)"
rm -rf "$DEST"
cp -r "$FRONTEND/out" "$DEST"

echo "==> Building wheel + sdist"
cd "$ROOT"
rm -rf dist
uv build

echo "==> Verifying the UI shipped in the wheel"
WHEEL="$(ls dist/*.whl)"
WHEEL_LIST="$(unzip -l "$WHEEL")"
if ! printf '%s\n' "$WHEEL_LIST" | grep -q "armance/web_dist/index.html"; then
  echo "ERROR: web_dist/index.html missing from $WHEEL" >&2
  exit 1
fi
UI_FILES="$(printf '%s\n' "$WHEEL_LIST" | grep -c "armance/web_dist/")"
echo "    OK — $UI_FILES UI files bundled in $WHEEL"
echo "==> Release artifacts ready in dist/"
