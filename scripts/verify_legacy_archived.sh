#!/usr/bin/env sh
# verify_legacy_archived.sh — T-15a verification
# Exits 1 if any legacy file/dir still exists at repo root,
# or if README.md still references the old "audacious / prudent" triplet.
set -eu

ERRORS=0

# Check legacy files/dirs at repo root
for pattern in ROADMAP WEB_UI_PLAN "plan\.md" "^plans$" "^scratch$" "^armance-synthesis" "^AGENTS\.md$"; do
    if ls -1 . | grep -qE "$pattern"; then
        echo "FAIL: legacy item '$pattern' still present at repo root"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check README.md for old triplet references
if grep -qiE "audacious.*prudent|prudent.*balanced" README.md 2>/dev/null; then
    echo "FAIL: README.md still contains 'audacious/prudent' triplet reference"
    ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -gt 0 ]; then
    echo "VERIFICATION FAILED: $ERRORS issue(s) found"
    exit 1
fi

echo "VERIFICATION PASSED: all legacy files archived"
exit 0
