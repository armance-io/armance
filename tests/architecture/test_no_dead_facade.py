"""Guard: ArmanceService stub + LocalTransport must remain dropped.

These modules existed as placeholders that pretended to be the public
service-layer API but contained only `pass`/placeholder bodies. The
real entry point is `service.tui_bridge.dispatch_input`. Reintroducing
the stubs would close doors for the web/SaaS layer rather than open them.
"""
from __future__ import annotations

from pathlib import Path

import armance


def _src_root() -> Path:
    return Path(armance.__file__).parent


def test_armance_service_stub_is_removed():
    assert not (_src_root() / "service" / "armance_service.py").exists(), (
        "ArmanceService stub must stay removed — use dispatch_input"
    )


def test_local_transport_stub_is_removed():
    assert not (_src_root() / "transport" / "local.py").exists(), (
        "LocalTransport stub must stay removed"
    )


def test_dispatch_input_is_the_public_entry_point():
    from armance.service.tui_bridge import dispatch_input

    assert callable(dispatch_input)


def test_no_consumer_imports_the_dead_stubs():
    forbidden = (
        "from armance.service.armance_service",
        "from armance.transport.local",
        "import armance.service.armance_service",
        "import armance.transport.local",
    )
    root = Path(armance.__file__).parent
    hits: list[str] = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden:
            if needle in text:
                hits.append(f"{py}: {needle}")
    assert not hits, f"Dead stub imports found: {hits}"
