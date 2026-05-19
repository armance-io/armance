"""Path builders for Armance storage layout.

This module provides functions to build paths for all Armance artifacts
under .armance/ directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def armance_root(repo_root: Path) -> Path:
    """Get the .armance root directory."""
    return repo_root / ".armance"


def agents_dir(armance_root: Path) -> Path:
    """Get the agents directory."""
    return armance_root / "agents"


def agent_path(armance_root: Path, name: str) -> Path:
    """Get path for an agent file."""
    return agents_dir(armance_root) / f"{name}.md"


def agent_card_path(armance_root: Path, name: str) -> Path:
    """Get path for an agent card sidecar JSON file."""
    return agents_dir(armance_root) / f"{name}.agent_card.json"




def workflows_dir(armance_root: Path) -> Path:
    """Get the workflows directory."""
    return armance_root / "workflows"


def workflow_path(armance_root: Path, name: str) -> Path:
    """Get path for a workflow file."""
    return workflows_dir(armance_root) / f"{name}.yaml"


def reports_dir(armance_root: Path) -> Path:
    """Get the reports directory."""
    return armance_root / "reports"


def report_path(armance_root: Path, domain: str, agent: str, version: int) -> Path:
    """Get path for a report file."""
    domain_dir = reports_dir(armance_root) / domain
    return domain_dir / f"{agent}_v{version:03d}.md"


def context_dir(armance_root: Path) -> Path:
    """Get the context directory."""
    return armance_root / "context"


def context_l0_path(armance_root: Path, version: int, date: str, slug: str) -> Path:
    """Get path for an L0 context version file.

    Format: context/L0/v<NNN>_<date>_<slug>.md

    Examples:
        context/L0/v001_2026-05-02_table-basse-chene.md
    """
    return context_dir(armance_root) / "L0" / f"v{version:03d}_{date}_{slug}.md"


def context_l1_path(armance_root: Path, role: str, version: int, date: str, slug: str) -> Path:
    """Get path for an L1 context version file.

    Format: context/L1/<role>/v<NNN>_<date>_<slug>.md

    Examples:
        context/L1/woodworking/v001_2026-05-02_table-basse-chene.md
    """
    return context_dir(armance_root) / "L1" / role / f"v{version:03d}_{date}_{slug}.md"


def context_l2_path(armance_root: Path, role: str, topic: str, version: int, date: str, slug: str) -> Path:
    """Get path for an L2 context version file.

    Format: context/L2/<role>/<topic>/v<NNN>_<date>_<slug>.md

    Examples:
        context/L2/woodworking/joinery/v001_2026-05-02_table-basse-chene.md
    """
    return context_dir(armance_root) / "L2" / role / topic / f"v{version:03d}_{date}_{slug}.md"


def context_version_path(armance_root: Path, layer: str, theme: str, version: int) -> Path:
    """Get path for a context version file (legacy, deprecated).

    Use context_l0_path, context_l1_path, or context_l2_path instead.
    """
    prefix = f"{layer}_{theme}" if theme else layer
    return context_dir(armance_root) / f"{prefix}_v{version:03d}.md"


def judge_dir(armance_root: Path) -> Path:
    """Get the judge directory."""
    return armance_root / "judge"


def judge_path(armance_root: Path, version: int) -> Path:
    """Get path for a judge report."""
    return judge_dir(armance_root) / f"judge_v{version:03d}.md"


def sessions_dir(armance_root: Path) -> Path:
    """Get the sessions directory."""
    return armance_root / "sessions"


def session_dir(armance_root: Path, session_id: str) -> Path:
    """Get a specific session directory."""
    return sessions_dir(armance_root) / session_id


def session_state_path(armance_root: Path, session_id: str) -> Path:
    """Get path for session state.json."""
    return session_dir(armance_root, session_id) / "state.json"


def session_ledger_path(armance_root: Path, session_id: str) -> Path:
    """Get path for session ledger.json."""
    return session_dir(armance_root, session_id) / "ledger.json"


def session_transcript_path(armance_root: Path, session_id: str) -> Path:
    """Get path for session transcript.md."""
    return session_dir(armance_root, session_id) / "transcript.md"


def docs_dir(armance_root: Path) -> Path:
    """Get the docs directory."""
    return armance_root / "docs"


def rag_index_db_path(armance_root: Path) -> Path:
    """Get the path for the RAG sqlite-vec database."""
    return armance_root / "rag" / "index.db"


def archive_dir(armance_root: Path) -> Path:
    """Get the archive directory."""
    return armance_root / ".archive"


def archive_agent_path(armance_root: Path, name: str) -> Path:
    """Get path for an archived agent file."""
    return archive_dir(armance_root) / f"{name}.md"


def exports_dir(armance_root: Path) -> Path:
    """Get the exports directory."""
    return armance_root / "exports"


def config_path(armance_root: Path) -> Path:
    """Get path for config.yaml."""
    return armance_root / "config.yaml"


def env_path(armance_root: Path) -> Path:
    """Get path for .env."""
    return armance_root / ".env"


def gitignore_path(armance_root: Path) -> Path:
    """Get path for .gitignore."""
    return armance_root / ".gitignore"


# ============================================================================
# Shared memory / claim ledger paths
# ============================================================================


def shared_memory_dir(armance_root: Path) -> Path:
    """Get the shared_memory directory."""
    return armance_root / "shared_memory"


def claims_jsonl_path(armance_root: Path) -> Path:
    """Get path for the claim ledger JSONL file.

    Path: shared_memory/claims.jsonl
    """
    return shared_memory_dir(armance_root) / "claims.jsonl"


def claims_index_path(armance_root: Path) -> Path:
    """Get path for the claim ledger secondary index.

    Path: shared_memory/claims.idx.json
    """
    return shared_memory_dir(armance_root) / "claims.idx.json"


def ensure_shared_memory_dir(armance_root: Path) -> Path:
    """Create the shared_memory directory if it does not exist.

    Returns:
        The shared_memory directory path.
    """
    sm_dir = shared_memory_dir(armance_root)
    sm_dir.mkdir(parents=True, exist_ok=True)
    return sm_dir


# ============================================================================
# Agent lifecycle storage paths
# ============================================================================


def agents_registry_path(armance_root: Path) -> Path:
    """Get path for the agent registry JSON file.

    Path: .armance/agents/registry.json
    """
    return agents_dir(armance_root) / "registry.json"


def ensure_agents_dir(armance_root: Path) -> Path:
    """Create the agents directory (and .armance root) if it does not exist.

    Returns:
        The agents directory path.
    """
    agents = agents_dir(armance_root)
    agents.mkdir(parents=True, exist_ok=True)
    return agents


def ensure_agents_registry(armance_root: Path) -> dict[str, list[dict[str, Any]]]:
    """Load or create the agent registry JSON.

    Returns:
        The registry dict (list of agent dicts under 'agents' key).
    """
    agents_dir_path = ensure_agents_dir(armance_root)
    registry_file = agents_dir_path / "registry.json"
    if registry_file.exists():
        data: dict[str, list[dict[str, Any]]] = json.loads(
            registry_file.read_text(encoding="utf-8")
        )
        return data
    # Create empty registry
    registry: dict[str, list[dict[str, Any]]] = {"agents": []}
    registry_file.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return registry


def write_agents_registry(armance_root: Path, registry: dict[str, list[dict[str, Any]]]) -> None:
    """Write the agent registry atomically (temp + rename).

    Path: .armance/agents/registry.json
    """
    registry_file = agents_registry_path(armance_root)
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix="registry_", dir=registry_file.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, registry_file)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def agent_version_path(armance_root: Path, name: str, version: int) -> Path:
    """Get path for a specific agent version file.

    Path: .armance/agents/<name>-v<N>.md
    """
    return agents_dir(armance_root) / f"{name}-v{version}.md"


def agent_archive_path(armance_root: Path, name: str, version: int | None = None) -> Path:
    """Get path for an archived agent file.

    Path: .armance/.archive/<name>-v<N>_<date>.md
    """
    return archive_dir(armance_root) / f"{name}"
