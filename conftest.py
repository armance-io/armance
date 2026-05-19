from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path before any test imports so that `import armance`
# resolves to src/armance regardless of the invocation method (uv run pytest,
# python -m pytest, or direct pytest).
_src = Path(__file__).parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
