"""J.0 — Platform layer scaffold: smoke-import tests.

These tests must be RED before `src/armance/platform/__init__.py` exists
and GREEN after. They verify the scaffold contract described in
issues/features/web-j-platform-abstractions.md § J.0.
"""
from __future__ import annotations

import inspect
import typing


def test_platform_package_is_importable() -> None:
    """armance.platform must import without error."""
    import armance.platform  # noqa: F401


def test_platform_exposes_storage_protocol() -> None:
    """armance.platform must export a 'Storage' name."""
    from armance.platform import Storage

    # It must be a class (Protocol or ABC)
    assert inspect.isclass(Storage), "Storage must be a class"


def test_platform_exposes_session_registry_protocol() -> None:
    """armance.platform must export a 'SessionRegistry' name."""
    from armance.platform import SessionRegistry

    assert inspect.isclass(SessionRegistry), "SessionRegistry must be a class"


def test_platform_exposes_event_bus_protocol() -> None:
    """armance.platform must export an 'EventBus' name."""
    from armance.platform import EventBus

    assert inspect.isclass(EventBus), "EventBus must be a class"


def test_platform_exposes_workflow_executor_protocol() -> None:
    """armance.platform must export a 'WorkflowExecutor' name."""
    from armance.platform import WorkflowExecutor

    assert inspect.isclass(WorkflowExecutor), "WorkflowExecutor must be a class"


def test_platform_exposes_get_current_user() -> None:
    """armance.platform must export 'get_current_user' as a callable."""
    from armance.platform import get_current_user

    assert callable(get_current_user), "get_current_user must be callable"


def test_get_current_user_is_async() -> None:
    """get_current_user() must be an async function (a FastAPI dependency)."""
    from armance.platform import get_current_user

    assert inspect.iscoroutinefunction(
        get_current_user
    ), "get_current_user must be async"


def _import_lines(filepath: str) -> list[str]:
    """Return only the actual import lines from a Python source file."""
    import pathlib

    lines = pathlib.Path(filepath).read_text(encoding="utf-8").splitlines()
    return [
        ln.strip()
        for ln in lines
        if ln.strip().startswith(("import ", "from "))
    ]


def test_platform_does_not_import_service() -> None:
    """armance.platform must not import from armance.service (layer contract)."""
    import armance.platform as plat_pkg

    plat_file = getattr(plat_pkg, "__file__", "") or ""
    if plat_file:
        import_lines = _import_lines(plat_file)
        bad = [ln for ln in import_lines if "armance.service" in ln]
        assert bad == [], (
            f"armance/platform/__init__.py imports from armance.service: {bad}"
        )


def test_platform_does_not_import_client() -> None:
    """armance.platform must not import from armance.client (layer contract)."""
    import armance.platform as plat_pkg

    plat_file = getattr(plat_pkg, "__file__", "") or ""
    if plat_file:
        import_lines = _import_lines(plat_file)
        bad = [ln for ln in import_lines if "armance.client" in ln]
        assert bad == [], (
            f"armance/platform/__init__.py imports from armance.client: {bad}"
        )
