"""Claim Ledger Service — record, verify, and query agent claims.

Implements the claim ledger operations described in
:doc:`../spec/19_claim_ledger`.  Claims are persisted as
newline-delimited JSON (JSONL) under ``.armance/shared_memory/claims.jsonl``.
Writes are atomic (temp file + rename).  Verification patches use a
full-file rewrite (flock unavailable on Windows; atomic write provides
safety).

Public API
----------
``ClaimLedgerService`` exposes:

* ``append_claim(claim)`` — atomically append a claim.
* ``verify_claim(claim_id, verdict, rationale, by, contradicting_claim)`` —
  patch status + status_meta on a single line.
* ``get_claims(filter)`` — retrieve claims with optional field filtering.
* ``get_claims_by_view(view)`` — claims emitted in a specific view.
* ``get_claims_by_agent(agent)`` — claims by a given agent.
* ``get_unverified(view)`` — unverified claims, optionally scoped to a view.
* ``delete_claim(claim_id)`` — soft-delete by marking status ``unsourced``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from armance.core.models.claim import (
    Claim,
    ClaimStatus,
    StatusMeta,
)
from armance.storage import paths


class ClaimLedgerError(Exception):
    """Base exception for claim ledger operations."""


class ClaimNotFoundError(ClaimLedgerError):
    """Raised when a claim with the given ID does not exist."""


class ClaimLedgerService:
    """Manages the claim ledger file (JSONL) and in-memory index.

    Parameters:
        repo_root:  Path to the project root (where ``.armance/`` lives).
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)
        self._ledger_path = paths.claims_jsonl_path(self._repo_root)
        self._index_path = paths.claims_index_path(self._repo_root)
        # In-memory index: claim_id -> Claim
        self._index: dict[str, Claim] = {}
        self._load_index()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """Build in-memory index from the JSONL file on disk."""
        paths.ensure_shared_memory_dir(self._repo_root)
        self._index = {}
        if not self._ledger_path.exists():
            self._save_index()
            return
        with open(self._ledger_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    claim = Claim.from_dict(json.loads(line))
                    self._index[claim.id] = claim
                except (json.JSONDecodeError, Exception):
                    # Skip corrupt lines but continue loading
                    continue
        self._save_index()

    def _save_index(self) -> None:
        """Persist the in-memory index to claims.idx.json."""
        idx_data: dict[str, Any] = {}
        for cid, claim in self._index.items():
            idx_data[cid] = claim.to_dict()
        tmp = tempfile.NamedTemporaryFile(
            dir=self._index_path.parent, suffix=".tmp", delete=False, mode="w"
        )
        try:
            json.dump(idx_data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            Path(tmp.name).replace(self._index_path)
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Atomic write helper
    # ------------------------------------------------------------------

    def _atomic_write_lines(self, lines: list[str]) -> None:
        """Rewrite the entire ledger file atomically (temp + rename)."""
        paths.ensure_shared_memory_dir(self._repo_root)
        tmp = tempfile.NamedTemporaryFile(
            dir=self._ledger_path.parent, suffix=".tmp", delete=False, mode="w", encoding="utf-8"
        )
        try:
            for line in lines:
                tmp.write(line)
                if not line.endswith("\n"):
                    tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            Path(tmp.name).replace(self._ledger_path)
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_claim(self, claim: Claim) -> None:
        """Atomically append a claim to the ledger file.

        Checks for ID collision against the in-memory index.
        Caller is responsible for filling ``id``, ``ts``, ``by``.

        Args:
            claim: The claim to append.

        Raises:
            ClaimLedgerError: If a claim with the same ID already exists.
        """
        if claim.id in self._index:
            raise ClaimLedgerError(f"Claim ID already exists: {claim.id}")
        # Append-only: read existing lines, add new one, atomic rewrite
        existing: list[str] = []
        if self._ledger_path.exists():
            with open(self._ledger_path, "r", encoding="utf-8") as fh:
                existing = [
                    line if line.endswith("\n") else line + "\n"
                    for line in fh.readlines()
                ]
        new_line = json.dumps(claim.to_dict(), ensure_ascii=False)
        existing.append(new_line + "\n")
        self._atomic_write_lines(existing)
        self._index[claim.id] = claim
        self._save_index()

    def verify_claim(
        self,
        claim_id: str,
        verdict: ClaimStatus,
        rationale: str,
        by: str,
        contradicting_claim: str | None = None,
    ) -> None:
        """Patch the status and status_meta fields on a single claim.

        Implemented as full-file rewrite (atomic via temp+rename).
        Never deletes lines.

        Args:
            claim_id:              ID of the claim to verify.
            verdict:               New verdict (verified/disputed/refuted/unsourced).
            rationale:             One-line explanation.
            by:                    Canonical verifier agent name.
            contradicting_claim:   Optional ID of a contradicting claim.

        Raises:
            ClaimNotFoundError: If the claim ID does not exist.
        """
        if claim_id not in self._index:
            raise ClaimNotFoundError(f"Claim not found: {claim_id}")

        claim = self._index[claim_id]
        claim.status = verdict
        claim.status_meta = StatusMeta(
            by=by,
            ts=datetime.now(timezone.utc),
            rationale=rationale,
            contradicting_claim=contradicting_claim,
        )

        # Read existing lines, replace the matching claim, atomic rewrite
        with open(self._ledger_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        new_lines: list[str] = []
        found = False
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                new_lines.append(line)
                continue
            try:
                parsed = json.loads(line_stripped)
                if parsed.get("id") == claim_id:
                    new_lines.append(json.dumps(claim.to_dict(), ensure_ascii=False) + "\n")
                    found = True
                    continue
            except (json.JSONDecodeError, Exception):
                pass
            new_lines.append(line)

        if not found:
            raise ClaimNotFoundError(f"Claim not found in file: {claim_id}")

        self._atomic_write_lines(new_lines)
        self._save_index()

    def get_claims(self, filter: dict[str, Any] | None = None) -> list[Claim]:
        """Retrieve all claims, optionally filtered by fields.

        Args:
            filter:  Dict of field->value pairs to match.  Supports
                     ``status``, ``by``, ``view``, ``confidence``.

        Returns:
            List of matching claims (most recent first).
        """
        results = list(self._index.values())
        if filter:
            filtered: list[Claim] = []
            for claim in results:
                match = True
                for key, value in filter.items():
                    if key == "status":
                        if claim.status != value:
                            match = False
                            break
                    elif key == "by":
                        if claim.by != value:
                            match = False
                            break
                    elif key == "view":
                        if claim.view != value:
                            match = False
                            break
                    elif key == "confidence":
                        if claim.confidence != value:
                            match = False
                            break
                    elif key == "step":
                        if claim.step != value:
                            match = False
                            break
                if match:
                    filtered.append(claim)
            results = filtered
        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda c: c.ts, reverse=True)
        return results

    def get_claims_by_view(self, view: str) -> list[Claim]:
        """Return all claims emitted in a specific view.

        Args:
            view: View reference (e.g. ``wf:r_x9f4k2pq``).

        Returns:
            List of claims for that view.
        """
        return self.get_claims(filter={"view": view})

    def get_claims_by_agent(self, agent: str) -> list[Claim]:
        """Return all claims by a given agent.

        Args:
            agent: Canonical agent name.

        Returns:
            List of claims by that agent.
        """
        return self.get_claims(filter={"by": agent})

    def get_unverified(self, view: str | None = None) -> list[Claim]:
        """Return unverified claims, optionally scoped to a view.

        Args:
            view:  Optional view reference to scope the query.

        Returns:
            List of unverified claims.
        """
        filt: dict[str, Any] = {"status": ClaimStatus.UNVERIFIED}
        if view:
            filt["view"] = view
        return self.get_claims(filter=filt)

    def delete_claim(self, claim_id: str) -> None:
        """Soft-delete a claim by marking its status as ``unsourced``.

        This preserves the audit trail while removing the claim from
        active queries.

        Args:
            claim_id: ID of the claim to delete.

        Raises:
            ClaimNotFoundError: If the claim ID does not exist.
        """
        self.verify_claim(
            claim_id=claim_id,
            verdict=ClaimStatus.UNSOURCED,
            rationale="Deleted by user request",
            by="system-admin",
        )

    def rebuild_index(self) -> None:
        """Rebuild the in-memory index from the JSONL file on disk.

        Called on service start and by ``armance repair claims``.
        """
        self._load_index()
