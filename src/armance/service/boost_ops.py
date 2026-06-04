"""Agent boost resolution helpers.

A boosted agent runs on its (boost_provider, boost_model) instead of its base
pair. Boost state is ephemeral session state (``SessionState.boosted_agents``),
never persisted to L0. Transitions are user-validated via a Checkpoint (a later
task) or applied deterministically in intense-mode workflows.

Layer rule: imports ``armance.core`` only.
"""
from __future__ import annotations

from armance.core.models.agent import Agent


def boosted_model_for(agent: Agent, boosted_names: set[str]) -> tuple[str, str]:
    """Return the (provider, model) to use for this agent given the boost set."""
    if agent.name in boosted_names and agent.is_boostable:
        pair = agent.effective_boost()
        if pair is not None:
            return pair
    return (agent.provider, agent.model)
