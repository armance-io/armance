"""A.12 — Coverage gate: backend ≥ 85%.

This file exists as documentation of the coverage requirement.
The actual gate is enforced by:
  cd web && .venv/bin/pytest --cov=backend --cov-fail-under=85

See web/pyproject.toml [tool.pytest.ini_options] addopts.
"""
from __future__ import annotations

# No runtime tests needed — coverage is measured by pytest-cov across
# all backend/tests/*.py files.
