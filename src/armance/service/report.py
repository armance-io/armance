"""Report model: versioned markdown artifacts with partial-answer flag.

Reports live at .armance/reports/<role>/<agent>_v<N>.md. Each file is
YAML frontmatter (uuid, timestamp, agent, role, prompt_truncated,
partial) followed by the body. partial=True prepends a #PARTIAL_ANSWER
marker line to the body. write_report() handles version increment by
scanning the role directory for existing <agent>_v<N>.md files.
"""
from __future__ import annotations

import logging
import re
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROMPT_TRUNCATE_LEN = 150
PARTIAL_MARKER = "#PARTIAL_ANSWER"
_VERSION_RE = re.compile(r"_v(\d+)\.md$")


class Report(BaseModel):
    uuid: str = Field(default_factory=lambda: str(_uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_name: str
    role: str
    prompt_truncated: str
    content: str
    partial: bool = False
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None

    @classmethod
    def from_completion(
        cls,
        *,
        agent_name: str,
        role: str,
        prompt: str,
        content: str,
        finish_reason: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: float | None = None,
    ) -> "Report":
        return cls(
            agent_name=agent_name,
            role=role,
            prompt_truncated=truncate_prompt(prompt),
            content=content,
            partial=finish_reason == "length",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
        )


def truncate_prompt(prompt: str) -> str:
    return prompt[:PROMPT_TRUNCATE_LEN]


def next_version(reports_dir: Path, agent_name: str) -> int:
    if not reports_dir.exists():
        return 1
    return _max_existing_version(reports_dir.glob(f"{agent_name}_v*.md")) + 1


def _max_existing_version(paths: Iterable[Path]) -> int:
    best = 0
    for p in paths:
        m = _VERSION_RE.search(p.name)
        if m:
            best = max(best, int(m.group(1)))
    return best


def write_report(report: Report, reports_root: Path) -> Path:
    role_dir = reports_root / report.role
    role_dir.mkdir(parents=True, exist_ok=True)
    version = next_version(role_dir, report.agent_name)
    path = role_dir / f"{report.agent_name}_v{version}.md"

    body = report.content
    if report.partial and not body.lstrip().startswith(PARTIAL_MARKER):
        body = f"{PARTIAL_MARKER}\n{body}"

    meta = {
        "uuid": report.uuid,
        "timestamp": report.timestamp,
        "agent": report.agent_name,
        "role": report.role,
        "prompt_truncated": report.prompt_truncated,
        "partial": report.partial,
    }
    if report.tokens_in is not None:
        meta["tokens_in"] = report.tokens_in
    if report.tokens_out is not None:
        meta["tokens_out"] = report.tokens_out
    if report.cost_usd is not None:
        meta["cost_usd"] = report.cost_usd
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return path


def read_report(path: Path) -> Report:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} is not a report (missing frontmatter)")
    rest = text[3:].lstrip("\n")
    end = rest.find("\n---")
    if end == -1:
        raise ValueError(f"{path} missing closing --- frontmatter delimiter")
    frontmatter = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    meta = yaml.safe_load(frontmatter) or {}
    # migrate legacy "domain"/"métier"/"metier"/"job" keys from old reports
    role = (
        meta.get("role") or meta.get("domain") or meta.get("métier")
        or meta.get("metier") or meta.get("job", "")
    )
    return Report(
        uuid=meta["uuid"],
        timestamp=meta["timestamp"],
        agent_name=meta["agent"],
        role=role,
        prompt_truncated=meta["prompt_truncated"],
        content=body,
        partial=bool(meta.get("partial", False)),
        tokens_in=meta.get("tokens_in"),
        tokens_out=meta.get("tokens_out"),
        cost_usd=meta.get("cost_usd"),
    )
