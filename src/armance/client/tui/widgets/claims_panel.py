"""ClaimsPanel — side panel showing claim density for the active workflow run.

Pure data model + header formatting. Textual Widget subclass deferred to
when the full TUI screen is wired (T-27+); this module provides the data
layer that Widget wraps.

Spec: docs/spec/19_claim_ledger.md § TUI surfacing
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from armance.client.tui.widgets.workflow_view import format_claim_density

# Agent kind → warm editorial hex (matches chat._META_AGENT_COLORS)
KIND_COLORS: dict[str, str] = {
    "synthesis":  "#c5aa72",   # Mona — ambre passé
    "critique":   "#e98667",   # Serge — rust, the rare warning hue
    "specialist": "#eeebe4",   # cream foreground
}


@dataclass
class ClaimsPanel:
    """In-memory model of the claims side panel."""

    total: int = 0
    verified: int = 0
    disputed: int = 0
    unsourced: int = 0
    claims: list[dict[str, Any]] = field(default_factory=list)

    @property
    def header_text(self) -> str:
        if self.total == 0:
            return "0 claims"
        return format_claim_density(
            total=self.total,
            verified=self.verified,
            disputed=self.disputed,
            unsourced=self.unsourced,
        )

    def update(self, *, total: int, verified: int, disputed: int, unsourced: int) -> None:
        self.total = total
        self.verified = verified
        self.disputed = disputed
        self.unsourced = unsourced

    def add_claim(self, *, claim_id: str, text: str, status: str = "asserted") -> None:
        self.claims.append({"id": claim_id, "text": text, "status": status})
        self.total = len(self.claims)
        self.verified = sum(1 for c in self.claims if c["status"] == "verified")
        self.disputed = sum(1 for c in self.claims if c["status"] == "disputed")
        self.unsourced = sum(1 for c in self.claims if c["status"] == "unsourced")
