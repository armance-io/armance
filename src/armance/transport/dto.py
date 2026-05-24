"""Data Transfer Objects for Armance API.

These DTOs define the contract between the transport layer and the
service layer. They are used for both LocalTransport and gRPC transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal


class AgentKind(str, Enum):
    """Kind of agent."""

    SYSTEM = "system"
    BUSINESS = "business"


class TaskStatus(str, Enum):
    """Task lifecycle status — A2A vocabulary (Invariant 1)."""

    DEFINED = "defined"
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    ARCHIVED = "archived"


class Mode(str, Enum):
    """Execution mode."""

    FULL = "full"
    LIGHT = "light"


# ============================================================================
# Agent-related DTOs
# ============================================================================


@dataclass
class AgentInfo:
    """Information about an agent."""

    name: str
    domain: str
    kind: AgentKind
    persona: str
    provider: str
    model: str
    reasoning: str | None = None
    system_prompt: str = ""
    is_active: bool = False


@dataclass
class RoleInfo:
    """Information about a role (domain group)."""

    name: str
    agents: list[str]
    description: str = ""


# ============================================================================
# Context-related DTOs
# ============================================================================


@dataclass
class ContextVersion:
    """A versioned context layer."""

    level: Literal["L0", "L1", "L2"]
    version: int
    theme: str | None = None
    created_at: datetime | None = None
    source_files: list[str] | None = None


@dataclass
class ContextInfo:
    """Context version info for UI."""

    version: str
    layer: str
    theme: str | None
    created_at: datetime
    summary: str = ""


# ============================================================================
# Task-related DTOs
# ============================================================================


@dataclass
class TaskInfo:
    """Information about a task."""

    id: str
    brief: str
    domain: str
    mode: Mode
    assignees: list[str]
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deliverables: list[str] | None = None


# ============================================================================
# Workflow-related DTOs
# ============================================================================


@dataclass
class WorkflowStepInfo:
    """Information about a workflow step."""

    id: str
    kind: Literal["task", "meeting", "deliverable", "human_checkpoint"]
    domain: str
    mode: Mode
    depends_on: list[str]
    status: Literal["submitted", "working", "input-required", "completed", "failed", "canceled"] = "submitted"
    output: str | None = None


@dataclass
class WorkflowInfo:
    """Information about a workflow."""

    name: str
    path: Path
    steps: list[WorkflowStepInfo]
    created_at: datetime
    last_run: datetime | None = None


# ============================================================================
# Session-related DTOs
# ============================================================================


@dataclass
class SessionState:
    """Current session state.

    Note: tui_state field has been removed (legacy TUIState enum dropped).
    """

    id: str
    created_at: datetime
    current_agent: str | None = None
    current_workflow: str | None = None
    current_step_id: str | None = None
    ledger_path: str | None = None
    current_provider: str | None = None
    current_model: str | None = None


# Event types live in armance.core.models.event. The dataclass shadows
# previously defined here (Event/AgentStateChanged/TaskEvent/...) were never
# emitted anywhere — the production event bus is
# armance.service.events.LocalEventBus, which uses the canonical Pydantic
# model directly.
