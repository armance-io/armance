"""Service-layer LLM glue: client factory delegation, exchange logging,
and the retry-with-backoff wrapper used by every agent call site.

The actual `LLMClient` factory + registry live in
`core.protocols.llm`. This module re-exports `get_client` so older code
in `armance.service.*` and `armance.client.*` keeps working unchanged.
"""
from __future__ import annotations

import datetime
import json
import logging
import threading
from pathlib import Path
from typing import Any

from armance.config import Config
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


def set_current_config(config: Config) -> None:
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = config


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
    ) -> None:
        self.agent = agent
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd


class TokenLedger:
    def __init__(
        self,
        persist_path: Path | None = None,
        budget_cap_usd: float | None = None,
    ) -> None:
        self.entries: list[LedgerEntry] = []
        self.persist_path = persist_path
        self.budget_cap_usd = budget_cap_usd
        self._lock = threading.RLock()

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
    ) -> None:
        with self._lock:
            self.entries.append(LedgerEntry(agent, ti, to, cost_usd))
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
            total = {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "calls": 0}
            for e in self.entries:
                b = per_agent.setdefault(
                    e.agent,
                    {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "calls": 0},
                )
                for d in (b, total):
                    d["tokens_in"] += e.tokens_in
                    d["tokens_out"] += e.tokens_out
                    d["cost_usd"] += e.cost_usd or 0.0
                    d["calls"] += 1
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
        log_dir = Path.cwd() / ".armance" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
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


def log_response(agent_name: str, model: str, response: LLMResponse) -> None:
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
    **params: Any,
) -> LLMResponse:
    """Run a single LLM call with budget check, structured logging, retry,
    and ledger accounting."""
    target = ledger or _GLOBAL_LEDGER
    target.check_budget()

    log_request(agent_name, model, messages)

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            if on_token:
                response = await client.stream_complete(
                    messages, model, on_token=on_token, **params
                )
            else:
                response = await complete_with_continuation(
                    client, messages, model, **params
                )
            log_response(agent_name, model, response)
            target.record(
                agent_name,
                response.tokens_in,
                response.tokens_out,
                response.cost_usd,
            )
            return response

        except Exception as exc:
            log_failure(agent_name, model, exc, attempt, max_retries)
            if attempt == max_retries:
                raise

            if on_token:
                try:
                    on_token(
                        f"\n[⚠️ {agent_name} : Error {exc!s}. "
                        f"Retrying in {backoff}s... "
                        f"(Attempt {attempt}/{max_retries})]\n"
                    )
                except Exception:
                    logger.debug("on_token notify failed", exc_info=True)

            import asyncio

            await asyncio.sleep(backoff)
            backoff *= 1.5
    # Unreachable — the loop either returns or raises.
    raise RuntimeError("call_with_ledger exhausted retries without returning")
