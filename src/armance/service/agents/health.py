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

    @property
    def ok(self) -> bool:
        return self.status == "ok"


_PROBE_MESSAGES = [{"role": "user", "content": "hi"}]
_PROBE_TIMEOUT_SECONDS = 15.0


async def check_agent_health(agent: Agent, cfg) -> HealthResult:
    """Send a 1-token probe to the agent's (provider, model)."""
    from armance.core.protocols.llm import register_client  # noqa: F401  (side-effect)
    from armance.service.llm_service import get_client

    try:
        client = get_client(agent.provider, cfg)
    except Exception as exc:
        return HealthResult(
            agent=agent.name, status="error:client", detail=str(exc),
        )

    try:
        import asyncio
        resp = await asyncio.wait_for(
            client.complete(
                messages=_PROBE_MESSAGES,
                model=agent.model,
                max_tokens=1,
            ),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        _ = resp
        return HealthResult(agent=agent.name, status="ok")
    except asyncio.TimeoutError:
        return HealthResult(
            agent=agent.name, status="error:timeout",
            detail=f"no reply within {_PROBE_TIMEOUT_SECONDS}s",
        )
    except Exception as exc:
        msg = str(exc)
        code = _extract_http_code(msg)
        return HealthResult(
            agent=agent.name,
            status=f"error:{code or 'unknown'}",
            detail=msg[:200],
        )


def _extract_http_code(msg: str) -> str:
    """Pull an HTTP code out of a provider error message (e.g. '429', '401').
    Defensive parsing — providers format errors differently."""
    import re
    m = re.search(r"\b([45]\d{2})\b", msg)
    return m.group(1) if m else ""


async def check_many(agents: list[Agent], cfg) -> list[HealthResult]:
    """Fan out health checks in parallel."""
    if not agents:
        return []
    import asyncio
    return await asyncio.gather(
        *(check_agent_health(a, cfg) for a in agents),
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
    a.save(path)
