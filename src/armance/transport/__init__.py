"""Transport DTOs for Armance.

Wire-format only: shapes the data crossing the service/client boundary.
There is no `Transport` ABC — the in-process entry point is
`armance.service.tui_bridge.dispatch_input(text, ctx) -> (reply, agent)`.

A future web layer (FastAPI + SSE) will consume the same DTOs as
response models without going through a facade class.
"""

from __future__ import annotations
