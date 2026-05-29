"""Armance V2 web backend — FastAPI app.

Entrypoint: `uvicorn backend.main:app`

The FastAPI lifespan builds an AppState (SessionRegistry + Storage +
EventBus factory) and attaches it to `app.state.app_state`. Routes
resolve it via `Depends(get_app_state)`.

Architectural invariants (web-layer.md §5):
  - No service code under web/backend/. Transport adapter only.
  - No pathlib.Path.write_* in this package. Use Storage ABC.
  - Every data route declares Depends(get_current_user).
  - URLs are /projects/{pid}/sessions/{sid}/... from day one.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.state import AppState
from backend.routes import health, whoami, sessions, turn, events, checkpoint, docs, library, library_docs, library_delete, exports, runs, agents, providers, hypotheses, workflows, active_workflow, sidecars, admin

logger = logging.getLogger(__name__)


def _resolve_armance_root() -> Path:
    """Resolve the .armance directory from the ARMANCE_ROOT env var or cwd."""
    env = os.environ.get("ARMANCE_ROOT")
    if env:
        root = Path(env)
    else:
        root = Path.cwd()
    armance_root = root / ".armance"
    return armance_root


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    armance_root = _resolve_armance_root()
    app_state = AppState(armance_root=armance_root)
    app.state.app_state = app_state
    logger.info("Armance web backend started; armance_root=%s", armance_root)
    yield
    logger.info("Armance web backend shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Armance Web API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(whoami.router)
    app.include_router(sessions.router)
    app.include_router(turn.router)
    app.include_router(events.router)
    app.include_router(checkpoint.router)
    app.include_router(docs.router)
    app.include_router(library.router)
    app.include_router(library_docs.router)
    app.include_router(library_delete.router)
    app.include_router(exports.router)
    app.include_router(runs.router)
    app.include_router(agents.router)
    app.include_router(providers.router)
    app.include_router(hypotheses.router)
    app.include_router(workflows.router)
    app.include_router(active_workflow.router)
    app.include_router(sidecars.router)
    app.include_router(admin.router)

    return app


app = create_app()
