"""`validate_cross_family` resolves single-family via the central `model_family`
(§G2), not a raw provider-name count — two providers can share a family and a
lone provider name can BE its family."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from armance.service.workflow_hooks import validate_cross_family


@dataclass
class _Step:
    id: str
    kind: str


@dataclass
class _WF:
    steps: list[_Step]


@dataclass
class _Provider:
    name: str


@dataclass
class _Config:
    providers: list[_Provider] = field(default_factory=list)
    default_model: str = ""


async def _warnings(cfg: _Config) -> list[str]:
    wf = _WF(steps=[_Step("c", "critique"), _Step("j", "judge")])
    seen: list[str] = []

    async def notify(kind: str, payload: dict) -> None:
        seen.append(payload.get("message", ""))

    await validate_cross_family(wf, cfg, notify)
    return seen


@pytest.mark.asyncio
async def test_two_providers_same_family_still_single_family() -> None:
    # custom-openai + openrouter both resolving to the SAME underlying family
    # (openai) must count as single-family — the old provider-name count would
    # have (wrongly) seen two and stayed silent.
    cfg = _Config(
        providers=[_Provider("custom-openai"), _Provider("openrouter")],
        default_model="openai/gpt-5",
    )
    warns = await _warnings(cfg)
    assert len(warns) == 2  # both critique + judge fire


@pytest.mark.asyncio
async def test_two_distinct_families_no_warning() -> None:
    cfg = _Config(
        providers=[_Provider("claude-code"), _Provider("gemini")],
        default_model="",
    )
    warns = await _warnings(cfg)
    assert warns == []


@pytest.mark.asyncio
async def test_single_provider_warns() -> None:
    cfg = _Config(providers=[_Provider("claude-code")], default_model="")
    warns = await _warnings(cfg)
    assert len(warns) == 2
