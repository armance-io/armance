"""armance.service.events — shim (J.3).

EventBus protocol and LocalEventBus implementation moved to
armance.platform.events.  This module re-exports them for back-compat.
"""
# Re-export for back-compat — do not add new code here.
from armance.core.models.event import Event  # noqa: F401  # architecture test checks evmod.Event
from armance.platform.events import EventBus, LocalEventBus  # noqa: F401

__all__ = ["Event", "EventBus", "LocalEventBus"]
