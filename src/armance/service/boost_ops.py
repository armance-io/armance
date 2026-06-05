"""Agent boost resolution helpers.

A boosted agent runs on its (boost_provider, boost_model) instead of its base
pair. Boost state is ephemeral session state (``SessionState.boosted_agents``),
never persisted to L0. Transitions are user-validated via a Checkpoint (a later
task) or applied deterministically in intense-mode workflows.

Layer rule: imports ``armance.core`` and internal ``service`` only.
"""
from __future__ import annotations

from armance.core.models.agent import Agent
from armance.service.checkpoint import Checkpoint

_REQ = "[EXECUTE:/boost-request]"
_REL = "[EXECUTE:/boost-release]"


def boosted_model_for(agent: Agent, boosted_names: set[str]) -> tuple[str, str]:
    """Return the (provider, model) to use for this agent given the boost set."""
    if agent.name in boosted_names and agent.is_boostable:
        pair = agent.effective_boost()
        if pair is not None:
            return pair
    return (agent.provider, agent.model)


def set_boost(agent: Agent, boosted_names: set[str], *, enabled: bool) -> bool:
    """Manually toggle an agent's augmented state, mutating ``boosted_names``.

    Deterministic counterpart to the NL ``/boost-request`` flow: the user drives
    the transition directly (sidebar toggle / settings) with no checkpoint.
    Enabling only takes effect when the agent is boostable; disabling always
    clears the name (defensive against a stale entry). Returns the resulting
    boosted state for this agent.
    """
    if enabled and agent.is_boostable:
        boosted_names.add(agent.name)
        return True
    boosted_names.discard(agent.name)
    return False


async def intercept_boost_tags(
    reply: str,
    agent: Agent,
    boosted_names: set[str],
    checkpoint_handler,
    t,
) -> str:
    """Detect boost tags, confirm via checkpoint, mutate boosted_names in place.

    Returns the reply with the tags stripped. A request from a non-boostable
    agent is a no-op (tag stripped, no checkpoint). t is the nls translator.
    """
    if _REQ in reply:
        reply = reply.replace(_REQ, "").strip()
        if agent.is_boostable:
            pair = agent.effective_boost()
            if pair is not None:
                ans = await checkpoint_handler.prompt(Checkpoint(
                    id=f"boost.upgrade.{agent.name}",
                    prompt=t("boost.confirm_upgrade", agent=agent.name,
                             base=agent.model, boost=pair[1]),
                    kind="confirm",
                ))
                if ans.content == "yes":
                    boosted_names.add(agent.name)
    if _REL in reply:
        reply = reply.replace(_REL, "").strip()
        if agent.name in boosted_names:
            ans = await checkpoint_handler.prompt(Checkpoint(
                id=f"boost.downgrade.{agent.name}",
                prompt=t("boost.confirm_downgrade", agent=agent.name, base=agent.model),
                kind="confirm",
            ))
            if ans.content == "yes":
                boosted_names.discard(agent.name)
    return reply
