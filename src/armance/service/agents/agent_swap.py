"""Agent model swap — change a recruited specialist's model in place.

Distinct from recruitment: `/recruit` brings *new profiles* (persona, axis of
disagreement); swapping is a narrow, no-LLM edit of one agent's (provider,
model) — typically to fix an unreachable model after a health probe failed,
without re-recruiting a new name (which would duplicate the role).

The persona (system_prompt), role, and description are left untouched: the
model is the tool, not the identity.

Scope: recruited specialists only. Staff meta-agents (`system-*`) are swapped
through the recruiter's staff-role redirect, not here.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from armance.core.models.agent import Agent
from armance.nls import t

logger = logging.getLogger(__name__)

# Payload is colon-introduced (so the sandbox tag regex recognises the tag and
# the allow-list passes) but space-separated inside, so model ids keeping `:`
# (e.g. `qwen3:free`) or `/` survive: `[EXECUTE:/agent-swap:<name> <prov/model>
# [<prov/model>]]`.
_AGENT_SWAP_RE = re.compile(r"\[EXECUTE:/agent-swap:([^\]]+)\]")


@dataclass(slots=True, frozen=True)
class SwapResult:
    status: str  # "ok" | "unknown" | "staff" | "load_error" | "bad_model"
    name: str
    provider: str = ""
    model: str = ""
    boost_model: str = ""
    health: str = ""  # the re-probed last_health, when status == "ok"


def _split_provider_model(token: str) -> tuple[str, str]:
    """Split a `provider/model` token. The model id keeps any inner `/` or `:`.

    `openrouter/qwen/qwen3:free` → ("openrouter", "qwen/qwen3:free").
    A bare token with no slash is treated as model-only (provider stays empty,
    the caller keeps the agent's current provider).
    """
    if "/" not in token:
        return "", token
    provider, model = token.split("/", 1)
    return provider, model


async def swap_agent_model(
    name: str,
    base: str,
    boost: str | None,
    agents_dir: Path,
    cfg,
) -> SwapResult:
    """Swap the (provider, model) — and optional boost — of one specialist.

    `base` / `boost` are `provider/model` tokens. Re-probes health after the
    write so `last_health` reflects the new model. Persona is preserved.
    """
    path = agents_dir / f"{name}.md"
    if name.startswith("system-") or name.startswith("_"):
        return SwapResult(status="staff", name=name)
    if not path.exists():
        return SwapResult(status="unknown", name=name)
    try:
        agent = Agent.load(path)
    except Exception:
        logger.exception("agent-swap: failed to load %s", path)
        return SwapResult(status="load_error", name=name)

    provider, model = _split_provider_model(base)

    # Validate against the session discovery cache (same contract as the
    # recruit validator): a provider WITH a catalogue rejects unknown ids;
    # a provider without one passes (validation impossible).
    from armance.providers.discovery import known_model_ids
    ids = known_model_ids(provider or agent.provider, cfg)
    if model and ids and model not in ids:
        logger.warning(
            "agent-swap: rejected %s — model %s/%s not in the discovered catalogue",
            name, provider or agent.provider, model,
        )
        return SwapResult(status="bad_model", name=name, model=model)

    if provider:
        agent.provider = provider
    if model:
        agent.model = model

    if boost:
        b_provider, b_model = _split_provider_model(boost)
        boost_ids = known_model_ids(b_provider or agent.provider, cfg)
        if b_model and boost_ids and b_model not in boost_ids:
            logger.warning(
                "agent-swap: dropped boost of %s — %s/%s not in catalogue",
                name, b_provider or agent.provider, b_model,
            )
        else:
            agent.boost_provider = b_provider or agent.provider
            agent.boost_model = b_model

    agent.updated_at = agent.now_iso()
    agent.save(path)
    logger.info(
        "agent-swap: %s → provider=%s model=%s boost=%s",
        name, agent.provider, agent.model, agent.boost_model,
    )

    # Re-probe health so a freshly-swapped model is not left with the old
    # error:* status (and a good model clears a prior failure immediately).
    health = ""
    try:
        from armance.service.agents.health import check_agent_health, persist_health
        result = await check_agent_health(agent, cfg)
        persist_health(result, agents_dir)
        health = result.status
    except Exception:
        logger.exception("agent-swap: health re-probe failed for %s", name)

    return SwapResult(
        status="ok",
        name=name,
        provider=agent.provider,
        model=agent.model,
        boost_model=agent.boost_model or "",
        health=health,
    )


async def handle_agent_swap(reply: str, ctx: Any) -> str:
    """Intercept `[EXECUTE:/agent-swap:<name> <provider/model> [<provider/model>]]`.

    Swaps a recruited specialist's model in place (persona preserved), re-probes
    health, and refreshes the in-memory roster (`ctx.agents`). Multiple tags are
    processed in order. Returns the reply with the tags stripped + a status line
    appended. Malik-only — the tag is scrubbed from any other role's reply.
    """
    matches = list(_AGENT_SWAP_RE.finditer(reply))
    if not matches:
        return reply

    agents_dir = ctx.armance_root / "agents"
    notes: list[str] = []
    for m in matches:
        args = m.group(1).split()
        if not args:
            continue
        name = args[0]
        base = args[1] if len(args) > 1 else ""
        boost = args[2] if len(args) > 2 else None
        if not base:
            notes.append(t("system_msg.agent_swap_bad_model", name=name))
            continue
        try:
            res = await swap_agent_model(name, base, boost, agents_dir, ctx.cfg)
        except Exception:
            logger.exception("agent-swap failed for %s", name)
            notes.append(t("system_msg.agent_swap_bad_model", name=name))
            continue
        if res.status == "bad_model":
            notes.append(t(
                "system_msg.agent_swap_model_unknown", name=name, model=res.model,
            ))
            continue
        if res.status != "ok":
            notes.append(t("system_msg.agent_swap_unknown", name=name))
            continue
        # Refresh the in-memory agent so the rest of the session uses the swap.
        path = agents_dir / f"{name}.md"
        if path.exists():
            try:
                reloaded = Agent.load(path)
                idx = next((i for i, a in enumerate(ctx.agents) if a.name == name), None)
                if idx is not None:
                    ctx.agents[idx] = reloaded
                else:
                    ctx.agents.append(reloaded)
            except Exception:
                logger.debug("agent-swap: reload failed for %s", name, exc_info=True)
        notes.append(
            t("system_msg.agent_swapped", name=name, model=res.model, health=res.health)
        )

    cleaned = _AGENT_SWAP_RE.sub("", reply).strip()
    if notes:
        cleaned += "\n\n" + "\n".join(notes)
    return cleaned
