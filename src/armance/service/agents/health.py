"""Agent health-check — ping the configured (provider, model) with a
1-token call to validate the pair works before letting the user rely on it.

Used in two places:
  1. After Malik recruits — surfaces unreachable models immediately so
     the user can pick another one (rate limits, auth, typos, ...).
  2. Pre-run by Kim — refuses to launch a workflow whose agents are
     known-unhealthy.

Result is cached on the Agent's frontmatter under `last_health`:
  - "ok"            → ping succeeded
  - "error:<code>"  → ping failed (e.g. "error:429", "error:auth")
  - missing/empty   → never checked yet
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from armance.core.models.agent import Agent

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HealthResult:
    agent: str
    status: str  # "ok" or "error:<code>"
    detail: str = ""
    boost_status: str | None = None  # probe of the boost pair, when set

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def boost_ok(self) -> bool:
        return self.boost_status in (None, "ok")


_PROBE_MESSAGES = [{"role": "user", "content": "hi"}]
_PROBE_TIMEOUT_SECONDS = 15.0
# Opus and other 'high' tier models can take 7s+ to cold-start through the
# Claude Agent SDK subprocess; under parallel fan-out (recruit of 8+ agents)
# they thrash and time out at 15s. Give the heavy tier more headroom.
_PROBE_TIMEOUT_HIGH_SECONDS = 60.0


async def _probe(provider: str, model: str, cfg, timeout: float) -> tuple[str, str]:
    """1-token probe of a (provider, model) pair → (status, detail)."""
    from armance.core.protocols.llm import register_client  # noqa: F401  (side-effect)
    from armance.service.llm_service import get_client

    try:
        client = get_client(provider, cfg)
    except Exception as exc:
        return "error:client", str(exc)
    try:
        import asyncio
        await asyncio.wait_for(
            client.complete(
                messages=_PROBE_MESSAGES,
                model=model,
                max_tokens=1,
            ),
            timeout=timeout,
        )
        return "ok", ""
    except asyncio.TimeoutError:
        return "error:timeout", f"no reply within {timeout}s"
    except Exception as exc:
        msg = str(exc)
        code = _extract_http_code(msg)
        return f"error:{code or 'unknown'}", msg[:200]


async def check_agent_health(agent: Agent, cfg) -> HealthResult:
    """Probe the agent's base (provider, model), and its boost pair if any.

    A broken boost never fails the agent (base still works); it is
    reported separately via ``boost_status`` so Malik can surface it.
    """
    timeout = _timeout_for(agent)
    status, detail = await _probe(agent.provider, agent.model, cfg, timeout)

    boost_status: str | None = None
    boost_pair = agent.effective_boost() if hasattr(agent, "effective_boost") else None
    if boost_pair is not None:
        b_provider, b_model = boost_pair
        boost_status, _b_detail = await _probe(b_provider, b_model, cfg, timeout)

    return HealthResult(
        agent=agent.name, status=status, detail=detail, boost_status=boost_status,
    )


def _extract_http_code(msg: str) -> str:
    """Pull an HTTP code out of a provider error message (e.g. '429', '401').
    Defensive parsing — providers format errors differently."""
    import re
    m = re.search(r"\b([45]\d{2})\b", msg)
    return m.group(1) if m else ""


def _timeout_for(agent: Agent) -> float:
    """High-tier Claude models (opus) need extra time when many agents
    are probed in parallel through the SDK subprocess."""
    mid = (agent.model or "").lower()
    if agent.provider == "claude-code" and "opus" in mid:
        return _PROBE_TIMEOUT_HIGH_SECONDS
    return _PROBE_TIMEOUT_SECONDS


async def check_many(agents: list[Agent], cfg) -> list[HealthResult]:
    """Fan out health checks in parallel, with a per-provider concurrency
    cap so the claude-code SDK isn't asked to spawn N subprocesses at once
    (causes spurious timeouts on opus models)."""
    if not agents:
        return []
    import asyncio
    cc_limit = asyncio.Semaphore(2)

    async def _guarded(a: Agent) -> HealthResult:
        if a.provider == "claude-code":
            async with cc_limit:
                return await check_agent_health(a, cfg)
        return await check_agent_health(a, cfg)

    return await asyncio.gather(
        *(_guarded(a) for a in agents),
        return_exceptions=False,
    )


def persist_health(result: HealthResult, agents_dir: Path) -> None:
    """Update the agent's `.md` frontmatter with the health probe result."""
    path = agents_dir / f"{result.agent}.md"
    if not path.exists():
        return
    try:
        a = Agent.load(path)
    except Exception:
        logger.exception("persist_health: failed to load %s", path)
        return
    a.last_health = result.status
    a.last_health_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    a.last_boost_health = result.boost_status
    a.save(path)
