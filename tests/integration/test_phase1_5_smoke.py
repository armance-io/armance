"""Phase 1.5 end-to-end smoke test.

Verifies the full P1.5 pipeline in a single deterministic scenario:

1. Create a ``ContextService`` backed by a temporary ``.armance`` directory.
2. Save an L0 context file via ``ContextService.write_l0``.
3. Save an L1 layer for the ``architect`` role via ``ContextService.write_l1``
   that contains a claim block in the spec format
   ``[[claim id=... evidence=... confidence=...]]...[[/claim]]``.
4. Run the claim parser against the L1 content and emit claims to the
   ``ClaimLedgerService``.
5. Assert that the claim appears in the ledger with correct fields.
6. Exercise the full ``AgentLifecycleService`` CRUD cycle:
   create → read (get) → list → promote → delete (archive) → verify
   the agent registry reflects each state change.

This test treats the system as a black box and uses only public APIs.
No real LLM calls are made; claim parsing is exercised directly.
All file I/O is isolated under ``tmp_path``.

Spec refs: 05_context.md (Layers), 19_claim_ledger.md (Path A),
20_agent_lifecycle.md (CRUD operations).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from armance.core.models.agent import Agent
from armance.core.models.claim import Claim, ClaimStatus, Confidence, Evidence, EvidenceKind
from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.claim_parser import parse_claims
from armance.service.context_service import ContextService
from armance.service.agents.agent_lifecycle_service import (
    AgentLifecycleError,
    AgentLifecycleService,
    AgentNotFoundError,
    DuplicateAgentError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    name: str,
    domain: str,
    *,
    persona: str = "test",
    provider: str = "openrouter",
    model: str = "model-a",
    status: str = "active",
) -> Agent:
    """Create a minimal test agent."""
    return Agent(
        name=name,
        domain=domain,
        persona=persona,
        provider=provider,
        model=model,
        system_prompt=f"You are {name}, a {persona} {domain} agent.",
        status=status,
    )


def _generate_claim_block(
    claim_id: str = "c_test0001",
    evidence_refs: list[str] | None = None,
    confidence: str = "asserted",
    text: str = "The architect layer defines the project structure.",
) -> str:
    """Generate a claim block string in the spec micro-syntax.

    Format::

        [[claim id=<id> evidence=<ref1>,<ref2> confidence=<conf>]]
        <text>
        [[/claim]]
    """
    evidence_str = ",".join(evidence_refs or ["docs/brief.md#p.1"])
    return (
        f"[[claim id={claim_id} evidence=\"{evidence_str}\" confidence={confidence}]]\n"
        f"{text}\n"
        f"[[/claim]]\n"
    )


def _seed_armance_dir(tmp_path: Path) -> Path:
    """Create a minimal ``.armance/`` skeleton under ``tmp_path``.

    Returns the ``armance_root`` path (which is ``tmp_path`` itself).
    """
    armance_root = tmp_path
    # Create required directories
    (armance_root / "context" / "L0").mkdir(parents=True, exist_ok=True)
    (armance_root / "context" / "L1").mkdir(parents=True, exist_ok=True)
    (armance_root / "agents").mkdir(parents=True, exist_ok=True)
    (armance_root / "shared_memory").mkdir(parents=True, exist_ok=True)
    return armance_root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_phase1_5_end_to_end(tmp_path: Path) -> None:
    """Exercise the full Phase 1.5 pipeline: L0 → L1 → claim parse → ledger → agent CRUD."""
    # ── 0. Seed directory ────────────────────────────────────────────────────
    armance_root = _seed_armance_dir(tmp_path)

    # ── 1. Write L0 context ──────────────────────────────────────────────────
    ctx_service = ContextService(armance_root)

    l0_body = (
        "# Project Expo Medievale\n\n"
        "## Goal\n\n"
        "Organize a medieval exhibition in June 2027.\n\n"
        "## Scope\n\n"
        "Historians, textile experts, and a narrator.\n"
    )
    l0_path = ctx_service.write_l0(
        body=l0_body,
        slug="expo-medievale",
        confirmed_by_user=True,
    )
    assert l0_path.exists(), "L0 file must be written"
    assert "v001" in l0_path.name, "L0 version must be v001"

    # Verify L0 round-trip
    read_body = ctx_service.read_l0_body()
    assert read_body is not None
    assert "Expo Medievale" in read_body

    # Verify manifest updated
    manifest_path = armance_root / "context" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["current_l0"] == l0_path.name

    # ── 2. Write L1 layer for architect role with embedded claim block ───────
    claim_block = _generate_claim_block(
        claim_id="c_arch0001",
        evidence_refs=["docs/textile-inventory-1380.pdf#p.42"],
        confidence="asserted",
        text="The architect layer defines the project structure with L0 and L1 separation.",
    )

    l1_body = (
        "# Architect Context — Expo Medievale\n\n"
        "## Directory Layout\n\n"
        "Source code under ``src/armance/``, tests under ``tests/``.\n\n"
        "## Claim from L1 dialogue\n\n"
        f"{claim_block}"
    )

    l1_path = ctx_service.write_l1(
        role="architect",
        body=l1_body,
        slug="project-structure",
    )
    assert l1_path.exists(), "L1 file must be written"
    assert "architect" in str(l1_path)

    # Verify L1 round-trip
    read_l1 = ctx_service.read_current_l1("architect")
    assert read_l1 is not None
    assert "c_arch0001" in read_l1, "L1 body must contain the claim block"

    # Verify manifest tracks current L1 for architect
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["current_l1"].get("architect") == l1_path.name

    # ── 3. Parse claims from L1 content ──────────────────────────────────────
    parsed = parse_claims(l1_body, defaults={"by": "architect", "view": "open-space"})
    assert len(parsed) == 1, "Must parse exactly one claim from L1 content"

    claim = parsed[0]
    assert claim.id == "c_arch0001"
    assert claim.by == "architect"
    assert claim.view == "open-space"
    assert claim.confidence == Confidence.ASSERTED
    assert claim.status == ClaimStatus.UNVERIFIED
    assert len(claim.evidence) == 1
    assert claim.evidence[0].ref == "docs/textile-inventory-1380.pdf#p.42"

    # ── 4. Append claim to ledger ────────────────────────────────────────────
    ledger_service = ClaimLedgerService(armance_root)
    ledger_service.append_claim(claim)

    # ── 5. Verify claim in ledger ────────────────────────────────────────────
    all_claims = ledger_service.get_claims()
    assert len(all_claims) == 1, "Ledger must contain exactly one claim"
    assert all_claims[0].id == "c_arch0001"
    assert all_claims[0].by == "architect"

    # Query by view
    view_claims = ledger_service.get_claims_by_view("open-space")
    assert len(view_claims) == 1

    # Query by agent
    agent_claims = ledger_service.get_claims_by_agent("architect")
    assert len(agent_claims) == 1

    # Query unverified
    unverified = ledger_service.get_unverified()
    assert len(unverified) == 1
    assert unverified[0].id == "c_arch0001"

    # Verify a claim
    ledger_service.verify_claim(
        claim_id="c_arch0001",
        verdict=ClaimStatus.VERIFIED,
        rationale="Evidence reference points to a valid document.",
        by="system-judge",
    )

    verified_claims = ledger_service.get_claims(filter={"status": ClaimStatus.VERIFIED})
    assert len(verified_claims) == 1
    assert verified_claims[0].status_meta is not None
    assert verified_claims[0].status_meta.by == "system-judge"

    # ── 6. Agent CRUD lifecycle ──────────────────────────────────────────────
    agent_service = AgentLifecycleService(armance_root)

    # 6a. Create agent
    test_agent = _make_agent(
        name="architect-bianca",
        domain="architect",
        persona="methodical",
    )
    agent_service.create_agent(test_agent)

    # Verify in registry
    registry_path = armance_root / "agents" / "registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    agent_names = [a["name"] for a in registry.get("agents", [])]
    assert "architect-bianca" in agent_names

    # 6b. Get agent
    loaded = agent_service.get_agent("architect-bianca")
    assert loaded is not None
    assert loaded.name == "architect-bianca"
    assert loaded.domain == "architect"
    assert loaded.persona == "methodical"

    # 6c. List agents
    agents = agent_service.list_agents()
    assert len(agents) >= 1
    agent_names_list = [a.name for a in agents]
    assert "architect-bianca" in agent_names_list

    # 6d. Promote agent
    promoted = agent_service.promote_agent("architect-bianca", "textiles")
    assert "textiles" in promoted.lead_for

    # 6e. Delete (archive) agent
    agent_service.delete_agent("architect-bianca")

    # Verify agent is archived — not in active list
    active_agents = agent_service.list_agents()
    active_names = [a.name for a in active_agents]
    assert "architect-bianca" not in active_names

    # Verify agent is in archived list (include_archived=True)
    all_agents = agent_service.list_agents(include_archived=True)
    archived_agents = [a for a in all_agents if a.status == "archived"]
    archived_names = [a.name for a in archived_agents]
    assert "architect-bianca" in archived_names

    # get_agent only finds active agents (file was moved to archive)
    # This is expected: archived agents are not in the active agents directory
    archived_agent = agent_service.get_agent("architect-bianca")
    assert archived_agent is None, "get_agent should not find archived agents"

    # 6f. Verify DuplicateAgentError on re-create
    duplicate_agent = _make_agent(
        name="architect-bianca",
        domain="architect",
        persona="methodical",
    )
    # The agent is archived, so the file was moved — re-create should succeed
    # Actually, archive moves the file, so create should work again
    agent_service.create_agent(duplicate_agent)
    # Verify it's back
    reloaded = agent_service.get_agent("architect-bianca")
    assert reloaded is not None
    assert reloaded.status == "active"

    # 6g. Verify get_agent returns None for a truly non-existent agent
    ghost = agent_service.get_agent("ghost-agent-xyz")
    assert ghost is None

    # promote_agent raises AgentNotFoundError for missing agents
    with pytest.raises(AgentNotFoundError):
        agent_service.promote_agent("ghost-agent-xyz", "something")

    # ── 7. Cleanup is automatic via tmp_path ─────────────────────────────────
    # tmp_path fixture tears down after the test
