"""ContextService — L0/L1/L2 management with manifest tracking.

Implements the unified project brief path (T-15c):
- read_current_l0() → Path | None
- write_l0(body, slug, derived_from, confirmed_by_user) → Path
- migrate_legacy_project_brief(armance_root) → Path | None

Spec refs: 05_context.md (Layers, Loading flow, Freezing flow, Manifest)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from armance.core.models.context import (
    ContextManifest,
    L0Frontmatter,
    L1Frontmatter,
    L2Frontmatter,
    _slugify,
    next_layer_version,
    read_current_l0,
)

logger = logging.getLogger(__name__)


class ContextService:
    """Manages L0/L1/L2 context layers and manifest."""

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self.context_dir = armance_root / "context"
        self.manifest_path = self.context_dir / "manifest.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_current_l0(self) -> Path | None:
        """Return the current L0 file path, or None if none exists."""
        return read_current_l0(self.armance_root)

    CACHE_FULL_CHARS = 1500  # cache proposes a freeze past this size

    def _cache_path(self) -> Path:
        from armance.storage.paths import context_cache_path
        return context_cache_path(self.armance_root)

    def read_cache(self) -> str:
        """Return the pending cache body, or '' if missing/unreadable."""
        path = self._cache_path()
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            logger.debug("cache read failed", exc_info=True)
            return ""

    def cache_append(self, note: str) -> None:
        """Append a worth-saving note to the cache (Armance only)."""
        note = (note or "").strip()
        if not note:
            return
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.read_cache()
        body = f"{existing}\n\n{note}".strip() if existing else note
        try:
            path.write_text(body + "\n", encoding="utf-8")
        except Exception:
            logger.exception("cache append failed")

    def clear_cache(self) -> None:
        """Delete the pending cache file (no-op if absent)."""
        path = self._cache_path()
        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.debug("cache clear failed", exc_info=True)

    def cache_is_full(self) -> bool:
        """True once the cache reaches the freeze-proposal threshold."""
        return len(self.read_cache()) >= self.CACHE_FULL_CHARS

    def append_quick_freeze(self, text: str, slug: str = "quit-quick-save") -> Path:
        """Quick non-LLM save used by the Ctrl+C×2 quit modal.

        Writes the raw buffer as a new L0 version, prefixed with a date and
        a marker so the user can identify it later. No LLM call, no schema
        beyond write_l0's safety net."""
        body = (
            f"## L0 — Quick save ({datetime.now(timezone.utc).isoformat()})\n\n"
            "Saved without LLM compilation on user quit. Raw buffer below.\n\n"
            f"{text.strip()}\n"
        )
        return self.write_l0(body, slug=slug, confirmed_by_user=True)

    def read_l0_body(self) -> str | None:
        """Return the body (without frontmatter) of the current L0, or None."""
        path = self.read_current_l0()
        if path is None:
            return None
        try:
            _, body = L0Frontmatter.from_yaml(path.read_text(encoding="utf-8"))
            return body
        except ValueError:
            return path.read_text(encoding="utf-8")

    def write_l0(
        self,
        body: str,
        slug: str | None = None,
        derived_from: list[str] | None = None,
        confirmed_by_user: bool = False,
    ) -> Path:
        """Write a new L0 version.

        Path format: context/L0/v<NNN>_<date>_<slug>.md
        Updates manifest.json to point to the new version.

        Defensive: ensures body is never empty to prevent frontmatter-only files.
        """
        # Safety net: ensure body is never empty (prevents frontmatter-only files)
        if not body.strip():
            body = "## L0\n\n### Goal\nProject context to be defined."
        l0_dir = self.context_dir / "L0"
        l0_dir.mkdir(parents=True, exist_ok=True)

        version = next_layer_version(l0_dir, "v")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_slug = slug or _slugify(body[:80])

        # Find previous L0 for parent_version
        prev_path = self.read_current_l0()
        parent_version = None
        if prev_path:
            m = re.match(r"^v(\d+)_", prev_path.name)
            if m:
                parent_version = int(m.group(1))

        fm = L0Frontmatter(
            version=version,
            project_slug=effective_slug,
            context_layer="L0",
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_version=parent_version,
            derived_from=derived_from or [],
            confirmed_by_user=confirmed_by_user,
            confirmed_at=datetime.now(timezone.utc).isoformat() if confirmed_by_user else "",
        )

        filename = f"v{version:03d}_{date_str}_{effective_slug}.md"
        path = l0_dir / filename
        path.write_text(fm.to_file(body), encoding="utf-8")

        # Update manifest
        manifest = self._load_manifest()
        manifest.current_l0 = filename
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        manifest.to_path(self.manifest_path)

        logger.info("wrote L0 v%03d: %s", version, path)
        return path

    def write_l1(
        self,
        role: str,
        body: str,
        slug: str | None = None,
        derived_from: list[str] | None = None,
        confirmed_by_user: bool = False,
    ) -> Path:
        """Write a new L1 version for a role.

        Path format: context/L1/<role>/v<NNN>_<date>_<slug>.md
        Uses atomic write (temp file + rename).
        Updates manifest.json to point to the new version.
        """
        l1_dir = self.context_dir / "L1" / role
        l1_dir.mkdir(parents=True, exist_ok=True)

        version = next_layer_version(l1_dir, "v")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_slug = slug or _slugify(body[:80])

        # Find previous L1 for parent_version
        prev_path = self._read_current_l1_path(role)
        parent_version = None
        if prev_path:
            m = re.match(r"^v(\d+)_", prev_path.name)
            if m:
                parent_version = int(m.group(1))

        fm = L1Frontmatter(
            version=version,
            project_slug=effective_slug,
            context_layer="L1",
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_version=parent_version,
            role=role,
            derived_from=derived_from or [],
            confirmed_by_user=confirmed_by_user,
            confirmed_at=datetime.now(timezone.utc).isoformat() if confirmed_by_user else "",
        )

        filename = f"v{version:03d}_{date_str}_{effective_slug}.md"
        temp_path = l1_dir / f".tmp_{filename}"
        path = l1_dir / filename
        temp_path.write_text(fm.to_file(body), encoding="utf-8")
        temp_path.rename(path)

        # Update manifest
        manifest = self._load_manifest()
        manifest.current_l1[role] = filename
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        manifest.to_path(self.manifest_path)

        logger.info("wrote L1/%s v%03d: %s", role, version, path)
        return path

    def write_l2(
        self,
        theme: str,
        body: str,
        slug: str | None = None,
        derived_from: list[str] | None = None,
        confirmed_by_user: bool = False,
    ) -> Path:
        """Write a new L2 version for a theme.

        Path format: context/L2/<theme>/v<NNN>_<date>_<slug>.md
        Updates manifest.json to point to the new version.
        """
        l2_dir = self.context_dir / "L2" / theme
        l2_dir.mkdir(parents=True, exist_ok=True)

        version = next_layer_version(l2_dir, "v")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_slug = slug or _slugify(body[:80])

        fm = L2Frontmatter(
            version=version,
            project_slug=effective_slug,
            context_layer="L2",
            created_at=datetime.now(timezone.utc).isoformat(),
            theme=theme,
            sub_topic=effective_slug,
            derived_from=derived_from or [],
            confirmed_by_user=confirmed_by_user,
            confirmed_at=datetime.now(timezone.utc).isoformat() if confirmed_by_user else "",
        )

        filename = f"v{version:03d}_{date_str}_{effective_slug}.md"
        path = l2_dir / filename
        path.write_text(fm.to_file(body), encoding="utf-8")

        # Update manifest
        manifest = self._load_manifest()
        if theme not in manifest.current_l2:
            manifest.current_l2[theme] = {}
        manifest.current_l2[theme][effective_slug] = filename
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        manifest.to_path(self.manifest_path)

        logger.info("wrote L2/%s v%03d: %s", theme, version, path)
        return path

    def read_current_l1(self, role: str) -> str | None:
        """Return the body (without frontmatter) of the current L1 for a role, or None."""
        path = self._read_current_l1_path(role)
        if path is None:
            return None
        text = path.read_text(encoding="utf-8")
        try:
            _, body = L1Frontmatter.from_yaml(text)
            return body
        except ValueError:
            return text

    def _read_current_l1_path(self, role: str) -> Path | None:
        """Return the path to the current L1 file for a role, or None."""
        manifest = self._load_manifest()
        filename = manifest.current_l1.get(role)
        if not filename:
            return None
        path = self.context_dir / "L1" / role / filename
        if not path.exists():
            return None
        return path

    def read_current_l2(self, theme: str) -> str | None:
        """Return the concatenated body of the current L2 versions for a theme."""
        manifest = self._load_manifest()
        files = manifest.current_l2.get(theme, {})
        if not files:
            return None
        
        bodies = []
        for filename in sorted(files.values()):
            path = self.context_dir / "L2" / theme / filename
            if path.exists():
                bodies.append(path.read_text(encoding="utf-8"))
        
        return "\n\n".join(bodies) if bodies else None

    async def enrich_for_agent(
        self,
        agent_name: str,
        base_context: str,
        query: str,
        k: int = 5,
        config=None,
    ) -> str:
        """Query RAG and inject top-K chunks into base_context.

        Per T-27: L1 enrichment with retrieved chunks at load time.
        When ``config`` has a rerank model configured, retrieval is two-stage.
        """
        from armance.storage.rag_index import context_with_rag

        # We can pass the root to the helper which handles the async-in-thread logic
        rag_context = context_with_rag(self.armance_root, query, k=k, config=config)
        
        if not rag_context:
            return base_context
            
        header = "## RAG — Retrieved Evidence"
        return f"{header}\n\n{rag_context}\n\n{base_context}"

    def migrate_legacy_project_brief(self) -> Path | None:
        """Migrate shared_memory/project_brief.md → context/L0/v001_*.md.

        Returns the new L0 path if migration happened, None otherwise.
        """
        legacy_path = self.armance_root / "shared_memory" / "project_brief.md"
        if not legacy_path.exists():
            return None

        text = legacy_path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        # Try to parse frontmatter; if it fails, treat whole text as body
        try:
            fm, body = L0Frontmatter.from_yaml(text)
        except ValueError:
            body = text
            fm = None

        # Write as L0 v001
        slug = fm.project_slug if fm and fm.project_slug != "untitled" else "project-brief"
        new_path = self.write_l0(
            body=body,
            slug=slug,
            derived_from=["shared_memory/project_brief.md"],
            confirmed_by_user=fm.confirmed_by_user if fm else False,
        )

        # Archive the legacy file
        archive_dir = self.armance_root / "shared_memory" / ".archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / "project_brief.md"
        legacy_path.rename(archive_path)
        logger.info(
            "migrated legacy project_brief.md → %s (archived to %s)",
            new_path,
            archive_path,
        )
        return new_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> ContextManifest:
        """Load or create a fresh manifest."""
        if self.manifest_path.exists():
            return ContextManifest.from_path(self.manifest_path)
        return ContextManifest(
            updated_at=datetime.now(timezone.utc).isoformat()
        )
