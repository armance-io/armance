"""Armance V2 web backend — FastAPI app.

Entrypoint: `uvicorn armance.web.backend.main:app` (or `armance web`).

The FastAPI lifespan builds an AppState (SessionRegistry + Storage +
EventBus factory) and attaches it to `app.state.app_state`. Routes
resolve it via `Depends(get_app_state)`.

Architectural invariants (web-layer.md §5):
  - No service code in this package. Transport adapter only.
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

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from armance.web.backend.state import AppState
from armance.web.backend.routes import health, whoami, sessions, turn, events, checkpoint, docs, library, library_docs, library_delete, library_action, exports, runs, agents, providers, embedding_models, hypotheses, workflows, active_workflow, sidecars, admin, admin_config, admin_secrets, admin_logs, admin_stats, admin_agents, deliverables, setup, auth

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


def _resolve_static_dir() -> Path | None:
    """Locate the bundled static frontend build (``out/`` export).

    Resolution order:
      1. ``ARMANCE_WEB_DIST`` env var (explicit override).
      2. ``armance/web_dist`` inside the installed package (ships in the
         wheel — pip users hit this path).
      3. ``web/frontend/out`` in a repo checkout (dev convenience after
         ``ARMANCE_STATIC_EXPORT=1 pnpm build``).

    Returns ``None`` when no build is present; the app then runs API-only
    and the frontend must be served separately (``pnpm dev``).
    """
    override = os.environ.get("ARMANCE_WEB_DIST")
    if override:
        p = Path(override)
        return p if (p / "index.html").exists() else None

    import armance

    pkg_dist = Path(armance.__file__).parent / "web_dist"
    if (pkg_dist / "index.html").exists():
        return pkg_dist

    # Repo layout: <root>/src/armance/web/backend/main.py and
    # <root>/web/frontend/out — walk up to the repo root.
    repo_root = Path(__file__).resolve().parents[4]
    repo_out = repo_root / "web" / "frontend" / "out"
    if (repo_out / "index.html").exists():
        return repo_out
    return None


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

    # Epic S · security gate. Fail-closed auth over every data route (mounted
    # under both "" and "/api") except the public liveness + auth endpoints.
    # Runs after the SPA middleware, so static HTML navigations (the login
    # shell included) are served before the gate and stay reachable.
    _install_auth_gate(app)

    # SPA page URLs share the /projects/{pid}/... shape with the API. The
    # browser asks for pages with `Accept: text/html` and for data via
    # fetch/EventSource (Accept: */* or application/json). A pre-routing
    # middleware serves the static shell for the former; everything else
    # falls through to the API routers below. Tests (Accept: */*) are never
    # intercepted, so they keep hitting the API unchanged.
    _install_spa(app)

    # API routes are reachable both at the root (used by the offline test
    # suite) and under /api (used by the browser, where /api/* is the only
    # path the SPA middleware lets through to the API).
    for prefix in ("", "/api"):
        api = APIRouter(prefix=prefix)
        for r in (
            health.router, whoami.router, sessions.router, turn.router,
            events.router, checkpoint.router, docs.router, library.router,
            library_docs.router, library_delete.router, library_action.router,
            exports.router,
            runs.router, agents.router, providers.router,
            embedding_models.router, hypotheses.router,
            workflows.router, active_workflow.router, sidecars.router,
            admin.router, admin_config.router, admin_secrets.router,
            admin_logs.router, admin_stats.router, admin_agents.router,
            deliverables.router, setup.router, auth.router,
        ):
            api.include_router(r)
        app.include_router(api)

    return app


# Paths that bypass the security gate: liveness + the auth flow itself (so
# the login page can authenticate before any cookie exists). Listed for both
# the root and /api mounts — the API routers are mounted under both.
_PUBLIC_PREFIXES = (
    "/healthz", "/api/healthz",
    "/auth/", "/api/auth/",
)


def _install_auth_gate(app: FastAPI) -> None:
    """Require a valid web secret on protected /api/* requests."""
    from fastapi.responses import JSONResponse

    from armance.config import load_config
    from armance.service import security
    from armance.web.backend.routes.auth import COOKIE_NAME

    def _candidate(request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        qp = request.query_params.get("token")
        if qp:
            return qp
        return request.cookies.get(COOKIE_NAME)

    @app.middleware("http")
    async def _auth_gate(request, call_next):
        # The SPA middleware runs before this one and already returns the
        # static HTML shell for text/html navigations, so anything reaching
        # here is a data/fetch call (root- or /api-mounted). Gate them all
        # except the public liveness + auth endpoints. This closes the
        # root-mount bypass: data routes exist at both "" and "/api".
        path = request.url.path
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)
        state = getattr(request.app.state, "app_state", None)
        if state is None:  # lifespan not yet run (shouldn't happen in serving)
            return await call_next(request)
        try:
            cfg = load_config(state.armance_root.parent)
        except Exception:  # noqa: BLE001 — config unreadable; env secret still applies
            from armance.config import Config as _Cfg
            cfg = _Cfg()
        if not security.check_web_secret(cfg, _candidate(request)):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


# Segments whose *following* path component is a dynamic id. The static
# export emits one shell per route template with these ids fixed to "_";
# a real URL maps onto that shell by substituting each id back to "_".
_DYNAMIC_AFTER = {"projects", "sessions", "workflows", "runs"}


def _sentinel_path(segments: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        out.append(seg)
        if seg in _DYNAMIC_AFTER and i + 1 < len(segments):
            out.append("_")
            i += 2
            continue
        i += 1
    return "/".join(out)


def _resolve_shell(static_dir: Path, path: str) -> Path:
    """Map a browser navigation path to its exported HTML shell."""
    path = path.strip("/")
    if not path:
        return static_dir / "index.html"
    direct = static_dir / f"{path}.html"
    if direct.is_file():
        return direct
    if (static_dir / path / "index.html").is_file():
        return static_dir / path / "index.html"
    template = _sentinel_path(path.split("/"))
    tmpl = static_dir / f"{template}.html"
    if tmpl.is_file():
        return tmpl
    if (static_dir / template / "index.html").is_file():
        return static_dir / template / "index.html"
    return static_dir / "index.html"


def _install_spa(app: FastAPI) -> None:
    """Serve the bundled static SPA for browser navigations.

    No build present → API-only (serve the UI separately with `pnpm dev`).
    """
    static_dir = _resolve_static_dir()
    if static_dir is None:
        logger.info("No bundled frontend found; running API-only "
                    "(serve the UI with `pnpm dev`, or `pnpm build` to bundle).")
        return

    @app.middleware("http")
    async def spa_middleware(request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        accept = request.headers.get("accept", "")
        is_nav = request.method == "GET" and "text/html" in accept
        is_api = path.startswith("/api")
        if is_nav and not is_api:
            # Static asset on disk (e.g. /favicon.ico, /_next/...) → file.
            asset = static_dir / path.lstrip("/")
            if path != "/" and asset.is_file():
                return FileResponse(asset)
            return FileResponse(_resolve_shell(static_dir, path))
        return await call_next(request)

    # Hashed build assets are fetched by the browser with Accept: */*, so
    # they bypass the nav middleware — mount them explicitly.
    app.mount("/_next", StaticFiles(directory=static_dir / "_next"), name="next-assets")

    logger.info("Serving bundled frontend from %s", static_dir)


app = create_app()
