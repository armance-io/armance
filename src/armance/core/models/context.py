"""Context agent: L0/L1/L2 layered context with manifest diff and chunking.

Sources:
  - .armance/docs/**            user-dropped docs (symlinks followed)
  - .armance/reports/**         versioned reports — only the latest version
                                per (role, agent) pair is considered

Pipeline:
  1. scan_sources()            list candidate files
  2. load_manifest()           read previous manifest (path → hash)
  3. diff_sources()            compute (added, removed, unchanged)
  4. chunk_text()              tiktoken count; split if > chunk_max_tokens
  5. write context layer files L0_v<N>.md, L1_<theme>_v<N>.md,
                                L2_<theme>_<sub>_v<N>.md (caveman-ultra
                                writing produced by an injected writer
                                callable; default writer is a stub used
                                by tests)
  6. write_manifest()          persist new manifest
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field

class ContextVersion(BaseModel):
    """A versioned context layer."""

    level: str  # "L0", "L1", "L2"
    version: int
    theme: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_files: list[str] = Field(default_factory=list)


class ContextLayer(BaseModel):
    """L0/L1/L2 context structure."""

    layer: str
    theme: str | None = None
    content: str = ""
    versions: list[ContextVersion] = Field(default_factory=list)


logger = logging.getLogger(__name__)

DEFAULT_CHUNK_MAX_TOKENS = 4000
_REPORT_VERSION_RE = re.compile(r"^(?P<stem>.+)_v(?P<n>\d+)\.md$")
_LEVEL_VERSION_RE = re.compile(r"_v(\d+)\.md$")
_L0_FILE_RE = re.compile(r"^v(\d+)_(\d{4}-\d{2}-\d{2})_(.+)\.md$")


@dataclass(slots=True)
class L0Frontmatter:
    """Frontmatter for an L0 context version (unified project brief).

    Per spec §05_context.md — Frontmatter section.
    """

    version: int
    project_slug: str
    context_layer: str = "L0"
    created_at: str = ""  # ISO-8601
    parent_version: int | None = None
    roles: list[str] = field(default_factory=list)
    summary_token_estimate: int = 0
    derived_from: list[str] = field(default_factory=list)
    confirmed_by_user: bool = False
    confirmed_at: str = ""
    evidence: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, text: str) -> tuple["L0Frontmatter", str]:
        """Parse frontmatter YAML + body from a markdown file.

        Returns (frontmatter, body) tuple.
        """
        import yaml

        if not text.startswith("---"):
            raise ValueError("missing YAML frontmatter")
        rest = text[3:].lstrip("\n")
        end = rest.find("\n---")
        if end == -1:
            raise ValueError("missing closing --- delimiter")
        fm_text = rest[:end]
        body = rest[end + 4 :].lstrip("\n")
        data = yaml.safe_load(fm_text) or {}
        return cls(
            version=int(data.get("version", 1)),
            project_slug=str(data.get("project_slug", "untitled")),
            context_layer=str(data.get("context_layer", "L0")),
            created_at=str(data.get("created_at", "")),
            parent_version=data.get("parent_version"),
            roles=data.get("roles") or [],
            summary_token_estimate=int(data.get("summary_token_estimate", 0)),
            derived_from=data.get("derived_from") or [],
            confirmed_by_user=bool(data.get("confirmed_by_user", False)),
            confirmed_at=str(data.get("confirmed_at", "")),
            evidence=data.get("evidence") or [],
        ), body

    def to_yaml(self) -> str:
        """Export frontmatter to YAML string."""
        import yaml

        data = {
            "version": self.version,
            "project_slug": self.project_slug,
            "context_layer": self.context_layer,
            "created_at": self.created_at,
        }
        if self.parent_version is not None:
            data["parent_version"] = self.parent_version
        if self.roles:
            data["roles"] = self.roles
        if self.summary_token_estimate:
            data["summary_token_estimate"] = self.summary_token_estimate
        if self.derived_from:
            data["derived_from"] = self.derived_from
        if self.confirmed_by_user:
            data["confirmed_by_user"] = True
            data["confirmed_at"] = self.confirmed_at
        if self.evidence:
            data["evidence"] = self.evidence
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()

    def to_file(self, body: str) -> str:
        """Render full markdown file with frontmatter + body."""
        return f"---\n{self.to_yaml()}\n---\n\n{body}\n"


_L1_FILE_RE = re.compile(r"^v(\d+)_(\d{4}-\d{2}-\d{2})_(.+)\.md$")


@dataclass(slots=True)
class L1Frontmatter:
    """Frontmatter for an L1 context version (per-role detail).

    Per spec §05_context.md — Frontmatter section.
    Mirrors L0Frontmatter but with ``role`` field instead of ``roles``.
    """

    version: int
    project_slug: str
    context_layer: str = "L1"
    created_at: str = ""  # ISO-8601
    parent_version: int | None = None
    role: str = ""
    derived_from: list[str] = field(default_factory=list)
    confirmed_by_user: bool = False
    confirmed_at: str = ""
    evidence: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, text: str) -> tuple["L1Frontmatter", str]:
        """Parse frontmatter YAML + body from a markdown file.

        Returns (frontmatter, body) tuple.
        """
        import yaml

        if not text.startswith("---"):
            raise ValueError("missing YAML frontmatter")
        rest = text[3:].lstrip("\n")
        end = rest.find("\n---")
        if end == -1:
            raise ValueError("missing closing --- delimiter")
        fm_text = rest[:end]
        body = rest[end + 4 :].lstrip("\n")
        data = yaml.safe_load(fm_text) or {}
        return cls(
            version=int(data.get("version", 1)),
            project_slug=str(data.get("project_slug", "untitled")),
            context_layer=str(data.get("context_layer", "L1")),
            created_at=str(data.get("created_at", "")),
            parent_version=data.get("parent_version"),
            role=str(data.get("role", "")),
            derived_from=data.get("derived_from") or [],
            confirmed_by_user=bool(data.get("confirmed_by_user", False)),
            confirmed_at=str(data.get("confirmed_at", "")),
            evidence=data.get("evidence") or [],
        ), body

    def to_yaml(self) -> str:
        """Export frontmatter to YAML string."""
        import yaml

        data = {
            "version": self.version,
            "project_slug": self.project_slug,
            "context_layer": self.context_layer,
            "created_at": self.created_at,
        }
        if self.parent_version is not None:
            data["parent_version"] = self.parent_version
        if self.role:
            data["role"] = self.role
        if self.derived_from:
            data["derived_from"] = self.derived_from
        if self.confirmed_by_user:
            data["confirmed_by_user"] = True
            data["confirmed_at"] = self.confirmed_at
        if self.evidence:
            data["evidence"] = self.evidence
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()

    def to_file(self, body: str) -> str:
        """Render full markdown file with frontmatter + body."""
        return f"---\n{self.to_yaml()}\n---\n\n{body}\n"


@dataclass(slots=True)
class L2Frontmatter:
    """Frontmatter for an L2 context version (topic knowledge).

    Per spec §05_context.md — Frontmatter section.
    """

    version: int
    project_slug: str
    context_layer: str = "L2"
    created_at: str = ""  # ISO-8601
    parent_version: int | None = None
    theme: str = ""
    sub_topic: str = ""
    derived_from: list[str] = field(default_factory=list)
    confirmed_by_user: bool = False
    confirmed_at: str = ""
    evidence: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, text: str) -> tuple["L2Frontmatter", str]:
        """Parse frontmatter YAML + body from a markdown file.

        Returns (frontmatter, body) tuple.
        """
        import yaml

        if not text.startswith("---"):
            raise ValueError("missing YAML frontmatter")
        rest = text[3:].lstrip("\n")
        end = rest.find("\n---")
        if end == -1:
            raise ValueError("missing closing --- delimiter")
        fm_text = rest[:end]
        body = rest[end + 4 :].lstrip("\n")
        data = yaml.safe_load(fm_text) or {}
        return cls(
            version=int(data.get("version", 1)),
            project_slug=str(data.get("project_slug", "untitled")),
            context_layer=str(data.get("context_layer", "L2")),
            created_at=str(data.get("created_at", "")),
            parent_version=data.get("parent_version"),
            theme=str(data.get("theme", "")),
            sub_topic=str(data.get("sub_topic", "")),
            derived_from=data.get("derived_from") or [],
            confirmed_by_user=bool(data.get("confirmed_by_user", False)),
            confirmed_at=str(data.get("confirmed_at", "")),
            evidence=data.get("evidence") or [],
        ), body

    def to_yaml(self) -> str:
        """Export frontmatter to YAML string."""
        import yaml

        data = {
            "version": self.version,
            "project_slug": self.project_slug,
            "context_layer": self.context_layer,
            "created_at": self.created_at,
        }
        if self.parent_version is not None:
            data["parent_version"] = self.parent_version
        if self.theme:
            data["theme"] = self.theme
        if self.sub_topic:
            data["sub_topic"] = self.sub_topic
        if self.derived_from:
            data["derived_from"] = self.derived_from
        if self.confirmed_by_user:
            data["confirmed_by_user"] = True
            data["confirmed_at"] = self.confirmed_at
        if self.evidence:
            data["evidence"] = self.evidence
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()

    def to_file(self, body: str) -> str:
        """Render full markdown file with frontmatter + body."""
        return f"---\n{self.to_yaml()}\n---\n\n{body}\n"


@dataclass(slots=True)
class ContextManifest:
    """context/manifest.json structure.

    Per spec §05_context.md — Manifest section.
    """

    current_l0: str | None = None
    current_l1: dict[str, str] = field(default_factory=dict)
    current_l2: dict[str, dict[str, str]] = field(default_factory=dict)
    active_session: str | None = None
    updated_at: str = ""

    @classmethod
    def from_path(cls, path: Path) -> "ContextManifest":
        """Load manifest from disk."""
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            current_l0=data.get("current_l0"),
            current_l1=data.get("current_l1", {}),
            current_l2=data.get("current_l2", {}),
            active_session=data.get("active_session"),
            updated_at=data.get("updated_at", ""),
        )

    def to_path(self, path: Path) -> None:
        """Write manifest to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_l0": self.current_l0,
            "current_l1": self.current_l1,
            "current_l2": self.current_l2,
            "active_session": self.active_session,
            "updated_at": self.updated_at,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclass(slots=True)
class SourceFile:
    path: Path
    hash: str
    text: str


@dataclass(slots=True)
class ContextDiff:
    added: list[SourceFile]
    removed: list[Path]
    unchanged: list[SourceFile]


@dataclass(slots=True)
class ContextWriteResult:
    l0_path: Path
    l1_paths: list[Path] = field(default_factory=list)
    l2_paths: list[Path] = field(default_factory=list)
    manifest_path: Path | None = None


WriterFn = Callable[[str, list[SourceFile]], Awaitable[str]]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def scan_sources(armance_root: Path) -> list[SourceFile]:
    """Return latest-version reports + every doc under .armance/docs/."""
    out: list[SourceFile] = []

    docs_dir = armance_root / "docs"
    if docs_dir.exists():
        for p in sorted(docs_dir.rglob("*")):
            if p.is_file() or (p.is_symlink() and p.resolve().is_file()):
                try:
                    text = _read_text(p)
                except UnicodeDecodeError:
                    logger.warning("skipping non-text doc: %s", p)
                    continue
                out.append(SourceFile(path=p, hash=_hash_text(text), text=text))

    reports_dir = armance_root / "reports"
    if reports_dir.exists():
        for path in _latest_reports(reports_dir):
            text = _read_text(path)
            out.append(SourceFile(path=path, hash=_hash_text(text), text=text))

    return out


def _latest_reports(reports_root: Path) -> list[Path]:
    latest: dict[tuple[str, str], tuple[int, Path]] = {}
    for role_dir in reports_root.iterdir():
        if not role_dir.is_dir():
            continue
        for path in role_dir.glob("*_v*.md"):
            m = _REPORT_VERSION_RE.match(path.name)
            if not m:
                continue
            key = (role_dir.name, m.group("stem"))
            n = int(m.group("n"))
            existing = latest.get(key)
            if existing is None or n > existing[0]:
                latest[key] = (n, path)
    return [v[1] for v in sorted(latest.values(), key=lambda x: x[1].as_posix())]


def load_manifest(armance_root: Path) -> dict[str, dict]:
    path = armance_root / "context" / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(armance_root: Path, sources: Iterable[SourceFile]) -> Path:
    context_dir = armance_root / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        sf.path.as_posix(): {
            "hash": sf.hash,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        for sf in sources
    }
    path = context_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def diff_sources(
    sources: list[SourceFile], manifest: dict[str, dict]
) -> ContextDiff:
    by_path = {sf.path.as_posix(): sf for sf in sources}
    current_paths = set(by_path)
    prior_paths = set(manifest)

    added_paths = sorted(current_paths - prior_paths)
    added = [by_path[p] for p in added_paths]

    # changed = same path, different hash → treat as added (re-ingest)
    for path in sorted(current_paths & prior_paths):
        if by_path[path].hash != manifest[path].get("hash"):
            added.append(by_path[path])

    unchanged = [
        by_path[p]
        for p in sorted(current_paths & prior_paths)
        if by_path[p].hash == manifest[p].get("hash")
    ]
    removed = [Path(p) for p in sorted(prior_paths - current_paths)]
    return ContextDiff(added=added, removed=removed, unchanged=unchanged)


def chunk_text(
    text: str, *, chunk_max_tokens: int = DEFAULT_CHUNK_MAX_TOKENS
) -> list[str]:
    """Split text on paragraph boundaries when token count exceeds the cap.

    Uses tiktoken cl100k_base for token counting. Each chunk fits under
    chunk_max_tokens; oversized single paragraphs are hard-split on
    token windows so we never return a chunk above the cap.
    """
    enc = _tiktoken_encoder()
    full_tokens = len(enc.encode(text))
    if full_tokens <= chunk_max_tokens:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for para in paragraphs:
        p_tokens = len(enc.encode(para))
        if p_tokens > chunk_max_tokens:
            if current:
                chunks.append("\n\n".join(current).strip())
                current, current_tokens = [], 0
            chunks.extend(_hard_split(para, enc, chunk_max_tokens))
            continue
        if current_tokens + p_tokens > chunk_max_tokens and current:
            chunks.append("\n\n".join(current).strip())
            current, current_tokens = [], 0
        current.append(para)
        current_tokens += p_tokens
    if current:
        chunks.append("\n\n".join(current).strip())
    return [c for c in chunks if c]


def _tiktoken_encoder():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _hard_split(text: str, encoder, max_tokens: int) -> list[str]:
    tokens = encoder.encode(text)
    out: list[str] = []
    for start in range(0, len(tokens), max_tokens):
        out.append(encoder.decode(tokens[start : start + max_tokens]))
    return out


def next_layer_version(context_dir: Path, prefix: str) -> int:
    """Return next version number for layer files.

    Supports two patterns:
    - Legacy flat:  context_dir/<prefix>_v<N>.md  (prefix like "L0", "L1_theme")
    - Spec subdirs: context_dir/<prefix>/v<N>_*.md (prefix like "v" scanned inside L0/ dir)
    """
    if not context_dir.exists():
        return 1
    best = 0
    # New spec format: files named v<NNN>_*.md inside the dir
    if prefix == "v":
        for path in context_dir.glob("v*.md"):
            m = re.match(r"^v(\d+)_", path.name)
            if m:
                best = max(best, int(m.group(1)))
        return best + 1
    # Legacy flat format: <prefix>_v<N>.md
    for path in context_dir.glob(f"{prefix}_v*.md"):
        m = _LEVEL_VERSION_RE.search(path.name)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


async def write_context_layers(
    armance_root: Path,
    sources: list[SourceFile],
    *,
    writer: WriterFn | None = None,
    chunk_max_tokens: int = DEFAULT_CHUNK_MAX_TOKENS,
) -> ContextWriteResult:
    """Generate L0/L1/L2 markdown files from the source set.

    The writer callable produces the actual prose for a layer; tests
    inject a deterministic stub so this module stays free of LLM I/O.
    The default writer concatenates source text — useful only for the
    unit-test path; real runs supply an LLM-backed writer.
    """
    context_dir = armance_root / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    if writer is None:
        async def _default_writer(layer: str, srcs: list[SourceFile]) -> str:
            joined = "\n\n".join(sf.text for sf in srcs)
            return joined[:1000]

        writer = _default_writer

    themes = _bucket_by_theme(sources)

    l0_text = await writer("L0", sources)
    l0_dir = context_dir / "L0"
    l0_dir.mkdir(parents=True, exist_ok=True)
    l0_version = next_layer_version(l0_dir, "v")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    l0_path = l0_dir / f"v{l0_version:03d}_{date_str}_context.md"
    l0_path.write_text(l0_text, encoding="utf-8")

    l1_paths: list[Path] = []
    l2_paths: list[Path] = []
    for theme, theme_sources in themes.items():
        l1_text = await writer(f"L1_{theme}", theme_sources)
        l1_version = next_layer_version(context_dir, f"L1_{theme}")
        l1_path = context_dir / f"L1_{theme}_v{l1_version}.md"
        l1_path.write_text(l1_text, encoding="utf-8")
        l1_paths.append(l1_path)

        for sub_idx, sf in enumerate(theme_sources):
            for chunk_idx, chunk in enumerate(chunk_text(sf.text, chunk_max_tokens=chunk_max_tokens)):
                sub = f"{sub_idx:02d}_{chunk_idx:02d}_{sf.path.stem}"
                l2_version = next_layer_version(context_dir, f"L2_{theme}_{sub}")
                l2_path = context_dir / f"L2_{theme}_{sub}_v{l2_version}.md"
                l2_path.write_text(chunk, encoding="utf-8")
                l2_paths.append(l2_path)

    manifest_path = write_manifest(armance_root, sources)
    return ContextWriteResult(
        l0_path=l0_path,
        l1_paths=l1_paths,
        l2_paths=l2_paths,
        manifest_path=manifest_path,
    )


def _bucket_by_theme(sources: list[SourceFile]) -> dict[str, list[SourceFile]]:
    """Theme = directory under docs/ or reports/.

    .armance/docs/<theme>/<file>     -> theme = <theme>
    .armance/docs/<file>             -> theme = "general"
    .armance/reports/<role>/<file> -> theme = <role>
    """
    buckets: dict[str, list[SourceFile]] = {}
    for sf in sources:
        parts = sf.path.parts
        theme = "general"
        for marker in ("docs", "reports"):
            if marker in parts:
                idx = parts.index(marker)
                # require at least one intermediate dir between marker and file
                if idx + 2 < len(parts):
                    theme = parts[idx + 1]
                break
        buckets.setdefault(theme, []).append(sf)
    return buckets


def load_context(armance_root: Path, max_level: int = 1) -> str:
    """Read latest L0+L1 (optionally L2) into a single string.

    Returns empty string if no context files exist.
    """
    context_dir = armance_root / "context"
    if not context_dir.exists():
        return ""

    parts: list[str] = []

    # L0: latest v<NNN>_*.md in context/L0/
    l0_path = _latest_l0(context_dir)
    if l0_path is not None:
        text = l0_path.read_text(encoding="utf-8")
        # Strip frontmatter for injection
        try:
            _, body = L0Frontmatter.from_yaml(text)
        except ValueError:
            body = text
        parts.append(f"## L0\n\n{body}")

    # L1: all latest L1_<theme>_v<N>.md
    if max_level >= 1:
        for path in sorted(context_dir.glob("L1_*_v*.md")):
            name = path.stem
            theme_match = re.match(r"L1_(.+)_v\d+", name)
            if theme_match:
                theme = theme_match.group(1)
                text = path.read_text(encoding="utf-8")
                parts.append(f"## L1 — {theme}\n\n{text}")

    # L2: all latest L2_<theme>_<sub>_v<N>.md
    if max_level >= 2:
        for path in sorted(context_dir.glob("L2_*_v*.md")):
            name = path.stem
            sub_match = re.match(r"L2_(.+)_v\d+", name)
            if sub_match:
                sub = sub_match.group(1)
                text = path.read_text(encoding="utf-8")
                parts.append(f"## L2 — {sub}\n\n{text}")

    return "\n\n".join(parts)


def _latest_l0(context_dir: Path) -> Path | None:
    """Find the latest L0 file.

    Checks spec format context/L0/v<NNN>_*.md first,
    then falls back to legacy flat context_dir/L0_v<N>.md.
    """
    best = None
    best_n = 0
    # Spec format: context/L0/v<NNN>_*.md
    l0_dir = context_dir / "L0"
    if l0_dir.exists():
        for path in l0_dir.glob("v*.md"):
            m = _L0_FILE_RE.match(path.name)
            if m:
                n = int(m.group(1))
                if n > best_n:
                    best_n = n
                    best = path
    # Legacy flat format: L0_v<N>.md in context_dir
    if best is None:
        for path in context_dir.glob("L0_v*.md"):
            m = _LEVEL_VERSION_RE.search(path.name)
            if m:
                n = int(m.group(1))
                if n > best_n:
                    best_n = n
                    best = path
    return best


def read_current_l0(armance_root: Path) -> Path | None:
    """Return the current L0 file path, or None if none exists."""
    return _latest_l0(armance_root / "context")


def _slugify(text: str, max_len: int = 40) -> str:
    """Create a kebab-case slug from text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\u00c0-\u017f\s-]", "", slug)  # keep accented chars
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len] if slug else "context"


def _latest_file(context_dir: Path, prefix: str) -> Path | None:
    """Find the latest versioned file.

    For L0: checks spec subdir context_dir/L0/v<N>_*.md first,
    then falls back to legacy flat context_dir/L0_v<N>.md.
    For other prefixes: legacy flat only.
    """
    best = None
    best_n = 0
    if prefix == "L0":
        # Spec format: context/L0/v<NNN>_<date>_<slug>.md
        l0_subdir = context_dir / "L0"
        if l0_subdir.exists():
            for path in l0_subdir.glob("v*.md"):
                m = re.match(r"^v(\d+)_", path.name)
                if m:
                    n = int(m.group(1))
                    if n > best_n:
                        best_n = n
                        best = path
        if best is not None:
            return best
    # Legacy flat format: <prefix>_v<N>.md
    for path in context_dir.glob(f"{prefix}_v*.md"):
        m = _LEVEL_VERSION_RE.search(path.name)
        if m:
            n = int(m.group(1))
            if n > best_n:
                best_n = n
                best = path
    return best


def append_to_layer(
    armance_root: Path,
    layer: str = "L1",
    theme: str = "checkpoint",
    text: str = "",
) -> Path:
    """Write a new versioned layer file (used by human_checkpoint step).

    E.g. layer=L1, theme=checkpoint → .armance/context/L1_checkpoint_v1.md
    """
    context_dir = armance_root / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{layer}_{theme}"
    version = next_layer_version(context_dir, prefix)
    path = context_dir / f"{prefix}_v{version}.md"
    path.write_text(text, encoding="utf-8")
    logger.info("wrote %s", path)
    return path
