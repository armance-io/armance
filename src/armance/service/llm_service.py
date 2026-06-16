"""Service-layer LLM glue: client factory delegation, exchange logging,
and the retry-with-backoff wrapper used by every agent call site.

The actual `LLMClient` factory + registry live in
`core.protocols.llm`. This module re-exports `get_client` so older code
in `armance.service.*` and `armance.client.*` keeps working unchanged.
"""
from __future__ import annotations

import contextvars
import datetime
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from armance.config import Config
from armance.core.models.footprint import Footprint
from armance.core.protocols.llm import (
    LLMClient,
    LLMResponse,
    complete_with_continuation,
    get_client as _core_get_client,
)

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised when cumulative spend would exceed the configured budget cap."""


_CURRENT_CONFIG: Config | None = None
_CURRENT_SESSION_ID: str | None = None


def set_current_config(config: Config) -> None:
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = config


def set_current_session_id(session_id: str | None) -> None:
    """Mark the active session so llm_exchanges logs land in a per-session file."""
    global _CURRENT_SESSION_ID
    _CURRENT_SESSION_ID = session_id


# Per-task (contextvar) overrides for the exchange-log destination. Set by
# call_with_ledger from the ledger's persist_path so concurrent web sessions
# each log to their own file, even when they share the module-level globals.
_ACTIVE_LOG_DIR: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "_ACTIVE_LOG_DIR", default=None
)
_ACTIVE_SESSION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_ACTIVE_SESSION_ID", default=None
)


def get_client(provider_name: str, config: Config) -> LLMClient:
    """Service-side wrapper that also caches the current Config for logging."""
    set_current_config(config)
    return _core_get_client(provider_name, config)


# ---------------------------------------------------------------------------
# TokenLedger
# ---------------------------------------------------------------------------


class LedgerEntry:
    def __init__(
        self,
        agent: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float | None,
        footprint: Footprint | None = None,
    ) -> None:
        self.agent = agent
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.footprint = footprint


class TokenLedger:
    def __init__(
        self,
        persist_path: Path | None = None,
        budget_cap_usd: float | None = None,
        log_dir: Path | None = None,
        session_id: str | None = None,
    ) -> None:
        self.entries: list[LedgerEntry] = []
        self.persist_path = persist_path
        self.budget_cap_usd = budget_cap_usd
        self.log_dir = log_dir
        self.session_id = session_id
        self._lock = threading.RLock()

        if persist_path and persist_path.exists():
            try:
                data = json.loads(persist_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    fp = None
                    gco2e = entry_data.get("gco2e")
                    if gco2e is not None:
                        fp = Footprint(
                            energy_wh=entry_data.get("energy_wh", 0.0) or 0.0,
                            gco2e=gco2e,
                            water_ml=entry_data.get("water_ml", 0.0) or 0.0,
                            embodied_gco2e=entry_data.get("embodied_gco2e", 0.0) or 0.0,
                            estimate=entry_data.get("estimate", False),
                            tier=entry_data.get("tier", "unknown"),
                            proxy_model=entry_data.get("proxy_model"),
                            zone=entry_data.get("zone", "WOR"),
                            gco2e_min=entry_data.get("gco2e_min"),
                            gco2e_max=entry_data.get("gco2e_max"),
                            water_ml_min=entry_data.get("water_ml_min"),
                            water_ml_max=entry_data.get("water_ml_max"),
                            energy_wh_min=entry_data.get("energy_wh_min"),
                            energy_wh_max=entry_data.get("energy_wh_max"),
                        )
                    self.entries.append(
                        LedgerEntry(
                            agent=entry_data["agent"],
                            tokens_in=entry_data["tokens_in"],
                            tokens_out=entry_data["tokens_out"],
                            cost_usd=entry_data.get("cost_usd"),
                            footprint=fp,
                        )
                    )
            except Exception:
                logger.debug("ledger load failed", exc_info=True)

    def check_budget(self) -> None:
        if self.budget_cap_usd is None:
            return
        with self._lock:
            current = sum((e.cost_usd or 0.0) for e in self.entries)
        if current >= self.budget_cap_usd:
            raise BudgetExceeded(f"budget cap reached: ${current:.4f}")

    def record(
        self,
        agent: str,
        ti: int,
        to: int,
        cost_usd: float | None = None,
        footprint: Footprint | None = None,
    ) -> None:
        with self._lock:
            self.entries.append(LedgerEntry(agent, ti, to, cost_usd, footprint))
            if self.persist_path:
                self._flush()

    def _flush(self) -> None:
        if not self.persist_path:
            return
        try:
            payload = {
                "entries": [
                    {
                        "agent": e.agent,
                        "tokens_in": e.tokens_in,
                        "tokens_out": e.tokens_out,
                        "cost_usd": e.cost_usd,
                        "gco2e": e.footprint.gco2e if e.footprint else None,
                        "water_ml": e.footprint.water_ml if e.footprint else None,
                        "energy_wh": e.footprint.energy_wh if e.footprint else None,
                        "embodied_gco2e": e.footprint.embodied_gco2e if e.footprint else None,
                        "tier": e.footprint.tier if e.footprint else None,
                        "proxy_model": e.footprint.proxy_model if e.footprint else None,
                        "estimate": e.footprint.estimate if e.footprint else None,
                        "zone": e.footprint.zone if e.footprint else None,
                        "gco2e_min": e.footprint.gco2e_min if e.footprint else None,
                        "gco2e_max": e.footprint.gco2e_max if e.footprint else None,
                        "water_ml_min": e.footprint.water_ml_min if e.footprint else None,
                        "water_ml_max": e.footprint.water_ml_max if e.footprint else None,
                        "energy_wh_min": e.footprint.energy_wh_min if e.footprint else None,
                        "energy_wh_max": e.footprint.energy_wh_max if e.footprint else None,
                    }
                    for e in self.entries
                ],
                "snapshot_unsafe": self.snapshot(),
            }
            self.persist_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception:
            logger.exception("ledger persist failed")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            per_agent: dict[str, dict[str, Any]] = {}
            total: dict[str, Any] = {
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                "calls": 0, "gco2e": 0.0, "water_ml": 0.0,
                "has_estimate": False, "has_unknown": False,
                "gco2e_min": 0.0, "gco2e_max": 0.0,
                "water_ml_min": 0.0, "water_ml_max": 0.0,
            }
            for e in self.entries:
                b = per_agent.setdefault(
                    e.agent,
                    {
                        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                        "calls": 0, "gco2e": 0.0, "water_ml": 0.0,
                        "has_estimate": False, "has_unknown": False,
                        "gco2e_min": 0.0, "gco2e_max": 0.0,
                        "water_ml_min": 0.0, "water_ml_max": 0.0,
                    },
                )
                fp = e.footprint
                for d in (b, total):
                    d["tokens_in"] += e.tokens_in
                    d["tokens_out"] += e.tokens_out
                    d["cost_usd"] += e.cost_usd or 0.0
                    d["calls"] += 1
                    d["gco2e"] += fp.gco2e if fp else 0.0
                    d["water_ml"] += fp.water_ml if fp else 0.0
                    d["gco2e_min"] += (
                        fp.gco2e_min if fp and fp.gco2e_min is not None
                        else (fp.gco2e if fp else 0.0)
                    )
                    d["gco2e_max"] += (
                        fp.gco2e_max if fp and fp.gco2e_max is not None
                        else (fp.gco2e if fp else 0.0)
                    )
                    d["water_ml_min"] += (
                        fp.water_ml_min if fp and fp.water_ml_min is not None
                        else (fp.water_ml if fp else 0.0)
                    )
                    d["water_ml_max"] += (
                        fp.water_ml_max if fp and fp.water_ml_max is not None
                        else (fp.water_ml if fp else 0.0)
                    )
                    if fp is None:
                        d["has_unknown"] = True
                    elif fp.estimate:
                        d["has_estimate"] = True
            return {"per_agent": per_agent, "total": total}


_GLOBAL_LEDGER = TokenLedger()


def get_ledger() -> TokenLedger:
    return _GLOBAL_LEDGER


def set_ledger(ledger: TokenLedger) -> None:
    global _GLOBAL_LEDGER
    _GLOBAL_LEDGER = ledger


# ---------------------------------------------------------------------------
# Exchange logging
# ---------------------------------------------------------------------------


def log_exchange_details(
    event_type: str,
    agent_name: str,
    model: str,
    data: dict[str, Any],
) -> None:
    try:
        ldir = _ACTIVE_LOG_DIR.get()
        log_dir = ldir if ldir is not None else Path.cwd() / ".armance" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        # One log file per session so a run's exchanges stay isolated and
        # the file can be deleted with the session. Fall back to the legacy
        # single-file name when no session has been registered yet (e.g.
        # tests, doctor, workflow-run outside a TUI).
        sid = _ACTIVE_SESSION_ID.get()
        if sid is not None:
            log_file = log_dir / f"{sid}-llm_exchanges.jsonl"
        elif _CURRENT_SESSION_ID:
            log_file = log_dir / f"{_CURRENT_SESSION_ID}-llm_exchanges.jsonl"
        else:
            log_file = log_dir / "llm_exchanges.jsonl"

        log_level = "INFO"
        if (
            _CURRENT_CONFIG
            and hasattr(_CURRENT_CONFIG, "log_level")
            and _CURRENT_CONFIG.log_level
        ):
            log_level = _CURRENT_CONFIG.log_level.upper()

        entry: dict[str, Any] = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event": event_type,
            "agent": agent_name,
            "model": model,
        }

        if log_level == "DEBUG":
            entry.update(data)
        elif event_type == "request":
            msgs = data.get("messages", [])
            entry["message_count"] = len(msgs)
            if msgs:
                last_msg = msgs[-1]
                entry["last_message_preview"] = (
                    str(last_msg.get("content", ""))[:200] + "..."
                )
        elif event_type == "response":
            entry["tokens_in"] = data.get("tokens_in")
            entry["tokens_out"] = data.get("tokens_out")
            entry["cost_usd"] = data.get("cost_usd")
            entry["finish_reason"] = data.get("finish_reason")
            entry["response_preview"] = str(data.get("text", ""))[:200] + "..."
            entry["gco2e"] = data.get("gco2e")
            entry["water_ml"] = data.get("water_ml")
            entry["energy_wh"] = data.get("energy_wh")
            entry["estimate"] = data.get("estimate")
            entry["tier"] = data.get("tier")
            entry["zone"] = data.get("zone")
            # Carry the carbon/water confidence bounds too — without these the
            # live range collapses to a flat midpoint in footprint_stats.
            entry["gco2e_min"] = data.get("gco2e_min")
            entry["gco2e_max"] = data.get("gco2e_max")
            entry["water_ml_min"] = data.get("water_ml_min")
            entry["water_ml_max"] = data.get("water_ml_max")
            entry["proxy_model"] = data.get("proxy_model")
        elif event_type == "failure":
            entry["error_type"] = data.get("error_type")
            entry["error_message"] = data.get("error_message")
            entry["attempt"] = data.get("attempt")
            entry["max_retries"] = data.get("max_retries")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("exchange log write failed", exc_info=True)


def log_request(
    agent_name: str,
    model: str,
    messages: list[dict[str, str]],
) -> None:
    log_exchange_details("request", agent_name, model, {"messages": messages})


def log_response(
    agent_name: str,
    model: str,
    response: LLMResponse,
    footprint: Footprint | None = None,
) -> None:
    log_exchange_details(
        "response",
        agent_name,
        model,
        {
            "text": response.text,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "finish_reason": response.finish_reason,
            "cost_usd": response.cost_usd,
            "gco2e": footprint.gco2e if footprint else None,
            "water_ml": footprint.water_ml if footprint else None,
            "energy_wh": footprint.energy_wh if footprint else None,
            "estimate": footprint.estimate if footprint else None,
            "tier": footprint.tier if footprint else None,
            "zone": footprint.zone if footprint else None,
            "gco2e_min": footprint.gco2e_min if footprint else None,
            "gco2e_max": footprint.gco2e_max if footprint else None,
            "water_ml_min": footprint.water_ml_min if footprint else None,
            "water_ml_max": footprint.water_ml_max if footprint else None,
            "proxy_model": footprint.proxy_model if footprint else None,
        },
    )


def log_failure(
    agent_name: str,
    model: str,
    exc: Exception,
    attempt: int,
    max_retries: int,
) -> None:
    import traceback
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_exchange_details(
        "failure",
        agent_name,
        model,
        {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": tb,
            "attempt": attempt,
            "max_retries": max_retries,
        },
    )


async def call_with_ledger(
    client: LLMClient,
    agent_name: str,
    messages: list[dict[str, str]],
    model: str,
    *,
    ledger: TokenLedger | None = None,
    on_token: Any = None,
    provider: str | None = None,
    **params: Any,
) -> LLMResponse:
    """Run a single LLM call with budget check, structured logging, retry,
    and ledger accounting.

    ``provider`` is the Armance provider name (e.g. "anthropic", "openrouter").
    When supplied, the environmental footprint is estimated and recorded on the
    ledger entry.  When omitted (existing callers), footprint is None.
    """
    target = ledger or _GLOBAL_LEDGER
    target.check_budget()

    # Bind the exchange-log destination for this task. Prefer the explicit
    # log_dir/session_id the caller set on the ledger; fall back to deriving
    # them from the ledger's persist_path (sessions/<sid>/ledger.json) so
    # older call sites that only pass persist_path still isolate their logs.
    log_dir = getattr(target, "log_dir", None)
    sid = getattr(target, "session_id", None)
    if (log_dir is None or sid is None) and target.persist_path:
        sid = sid or target.persist_path.parent.name
        log_dir = log_dir or target.persist_path.parent.parent.parent / "logs"
    if log_dir is not None:
        _ACTIVE_LOG_DIR.set(log_dir)
    if sid is not None:
        _ACTIVE_SESSION_ID.set(sid)

    log_request(agent_name, model, messages)

    from armance.service.rate_limit import backoff_for, provider_semaphore

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.perf_counter()
            # Per-provider concurrency cap: background workflow steps +
            # live chat must not hammer one (free-tier) provider at once.
            async with provider_semaphore(provider):
                if on_token:
                    response = await client.stream_complete(
                        messages, model, on_token=on_token, **params
                    )
                else:
                    response = await complete_with_continuation(
                        client, messages, model, **params
                    )
            latency_s = time.perf_counter() - t0

            footprint: Footprint | None = None
            if provider is not None:
                try:
                    from armance.service.footprint import estimate_footprint
                    zone = (
                        _CURRENT_CONFIG.footprint.electricity_mix_zone
                        if _CURRENT_CONFIG is not None
                        else "WOR"
                    )
                    footprint = estimate_footprint(
                        provider=provider,
                        model=model,
                        tokens_out=response.tokens_out,
                        latency_s=latency_s,
                        zone=zone,
                    )
                except Exception:
                    logger.exception("footprint estimation failed — recording None")

            log_response(agent_name, model, response, footprint=footprint)
            target.record(
                agent_name,
                response.tokens_in,
                response.tokens_out,
                response.cost_usd,
                footprint=footprint,
            )
            return response

        except Exception as exc:
            log_failure(agent_name, model, exc, attempt, max_retries)
            if attempt == max_retries:
                raise

            wait_s = backoff_for(exc, attempt, backoff)
            if on_token:
                try:
                    on_token(
                        f"\n[⚠️ {agent_name} : Error {exc!s}. "
                        f"Retrying in {wait_s:.0f}s... "
                        f"(Attempt {attempt}/{max_retries})]\n"
                    )
                except Exception:
                    logger.debug("on_token notify failed", exc_info=True)

            import asyncio

            await asyncio.sleep(wait_s)
            backoff *= 1.5
    # Unreachable — the loop either returns or raises.
    raise RuntimeError("call_with_ledger exhausted retries without returning")
