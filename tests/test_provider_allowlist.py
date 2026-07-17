"""LOT B — declarative model allowlist per instance (ADR 0003, §3.2).

`ProviderConfig.models` COMPLETES discovery: `known_model_ids` = discovered ∪
allowlist. An allowlisted id absent from `/models` is accepted by Malik's
validator; when discovery fails entirely, the allowlist is the effective
catalogue. The allowlist NEVER masks a discovered id (union, not intersection).
"""
from __future__ import annotations

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.providers import discovery
from armance.providers.base import ModelSpec


@pytest.fixture(autouse=True)
def _clear_cache():
    discovery.reset_cache()
    yield
    discovery.reset_cache()


def _seed_cache(instance: str, ids: list[str]) -> None:
    discovery._CACHE[instance] = [
        ModelSpec(id=i, provider=instance, tier="low", effectively_free=False) for i in ids
    ]


# ---- known_model_ids union ---------------------------------------------------

def test_known_ids_union_discovered_and_allowlist():
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab", models=["declared-x"])])
    _seed_cache("custom-openai:lab", ["found-a"])
    ids = discovery.known_model_ids("custom-openai:lab", cfg)
    assert ids == {"found-a", "declared-x"}


def test_allowlist_never_masks_discovered():
    # /models lists a model NOT in the allowlist → it stays visible.
    cfg = Config(providers=[ProviderConfig(name="custom-openai", models=["only-declared"])])
    _seed_cache("custom-openai", ["surprise-new-model"])
    ids = discovery.known_model_ids("custom-openai", cfg)
    assert "surprise-new-model" in ids  # union, not intersection
    assert "only-declared" in ids


def test_full_discovery_failure_allowlist_is_catalogue():
    # Endpoint 400 → empty cache; allowlist becomes the effective catalogue.
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab", models=["m1", "m2"])])
    _seed_cache("custom-openai:lab", [])
    assert discovery.known_model_ids("custom-openai:lab", cfg) == {"m1", "m2"}


def test_no_cfg_keeps_legacy_discovery_only():
    _seed_cache("custom-openai", ["found-a"])
    assert discovery.known_model_ids("custom-openai") == {"found-a"}


# ---- recruiter validator accepts an allowlisted id ---------------------------

def _recruiter(cfg, tmp_path):
    from armance.service.agents.recruiter_agent import RecruiterAgentService

    hr = Agent(
        name="system-hr", role="recruiter", provider="openrouter",
        model="x/y", description="hr", persona=None,
    )
    return RecruiterAgentService(agent=hr, armance_root=tmp_path, config=cfg)


_YAML = """agents:
  - name: Nadia
    persona: rigorous
    domain: research
    description: analyst
    provider: custom-openai:lab
    model: declared-model
    role: researcher
"""


def test_recruit_accepts_allowlisted_absent_from_discovery(tmp_path):
    # /models lists something else; the declared model must NOT be rejected.
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab", models=["declared-model"])])
    _seed_cache("custom-openai:lab", ["other-discovered"])
    hr = _recruiter(cfg, tmp_path)
    created, _ = hr.recruit_agents(_YAML, "specialist", tmp_path / "agents")
    assert any(a.name == "Nadia" for a in created)
    assert not hr.last_rejected_models


def test_recruit_rejects_model_neither_discovered_nor_declared(tmp_path):
    # Honest rejection preserved: the id is neither found nor declared.
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab", models=["declared-model"])])
    _seed_cache("custom-openai:lab", ["other-discovered"])
    hr = _recruiter(cfg, tmp_path)
    bad_yaml = _YAML.replace("model: declared-model", "model: ghost-model")
    created, _ = hr.recruit_agents(bad_yaml, "specialist", tmp_path / "agents")
    assert not any(a.name == "Nadia" for a in created)
    assert hr.last_rejected_models
