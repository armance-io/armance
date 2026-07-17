"""Preset benchmark — pure logic (no network, no disk writes outside report).

A preset pack may ship a replayable benchmark:

    bench/
        bench.yaml           # cases list (id, workflow, smoke flag)
        cases/<id>/
            input.md         # the user brief fed to the workflow
            rubric.md        # explicit scoring grid for the judge
            reference.md     # frontier one-shot ideal answer (versioned)
            attachments/*.md # optional seed documents

The live driver (``scripts/bench_presets.py``) produces the Armance
output; this module holds everything testable offline: bench loading,
A/B anonymisation (bias control), judge prompt construction, score-table
parsing, report rendering and delta vs the previous run.

Honesty rules (doctrine): the judge never learns which answer is
Armance's; sides are shuffled per case; the report always states the
judge model so cross-family choice is auditable.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from armance.core.models.preset import Preset, PresetError


@dataclass(frozen=True)
class BenchCase:
    id: str
    workflow: str
    title: str = ""
    smoke: bool = False
    root: Path = Path(".")

    @property
    def input_path(self) -> Path:
        return self.root / "input.md"

    @property
    def rubric_path(self) -> Path:
        return self.root / "rubric.md"

    @property
    def reference_path(self) -> Path:
        return self.root / "reference.md"

    def attachments(self) -> list[Path]:
        adir = self.root / "attachments"
        if not adir.is_dir():
            return []
        return sorted(p for p in adir.iterdir() if p.is_file())

    def validate(self) -> list[str]:
        """Return missing-file complaints (empty = runnable)."""
        problems = []
        for p in (self.input_path, self.rubric_path, self.reference_path):
            if not p.is_file():
                problems.append(f"{self.id}: missing {p.name}")
        return problems


def load_bench(preset: Preset) -> list[BenchCase]:
    """Parse ``bench/bench.yaml``. Raises PresetError when malformed."""
    bench_yaml = preset.bench_dir / "bench.yaml"
    if not bench_yaml.is_file():
        raise PresetError(f"preset '{preset.name}' has no bench/bench.yaml")
    data = yaml.safe_load(bench_yaml.read_text(encoding="utf-8")) or {}
    cases_raw = data.get("cases") or []
    if not isinstance(cases_raw, list) or not cases_raw:
        raise PresetError(f"bench.yaml of '{preset.name}' declares no cases")
    cases: list[BenchCase] = []
    for entry in cases_raw:
        if not isinstance(entry, dict) or "id" not in entry or "workflow" not in entry:
            raise PresetError(f"bench.yaml case needs id+workflow: {entry!r}")
        cases.append(
            BenchCase(
                id=str(entry["id"]),
                workflow=str(entry["workflow"]),
                title=str(entry.get("title", "")),
                smoke=bool(entry.get("smoke", False)),
                root=preset.bench_dir / "cases" / str(entry["id"]),
            )
        )
    return cases


# ── A/B anonymisation ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnonymisedPair:
    text_a: str
    text_b: str
    armance_side: str  # "A" | "B"


def anonymise_pair(
    armance_output: str, reference: str, rng: random.Random | None = None
) -> AnonymisedPair:
    """Shuffle which side Armance lands on; the judge only sees A and B."""
    rng = rng or random.Random()
    if rng.random() < 0.5:
        return AnonymisedPair(text_a=armance_output, text_b=reference, armance_side="A")
    return AnonymisedPair(text_a=reference, text_b=armance_output, armance_side="B")


def build_judge_prompt(case: BenchCase, pair: AnonymisedPair, rubric_text: str) -> str:
    """Blind comparative judging prompt. Output contract: one markdown
    table ``| criterion | A | B |`` (scores /10) then ``VERDICT: A|B|TIE``."""
    return (
        "Tu es un évaluateur indépendant. Deux réponses anonymes (A et B) "
        "répondent au même brief. Note-les selon la grille, sans préférence "
        "de style pour l'une ou l'autre origine.\n\n"
        f"## Brief\n\n{case.input_path.read_text(encoding='utf-8')}\n\n"
        f"## Grille de notation\n\n{rubric_text}\n\n"
        f"## Réponse A\n\n{pair.text_a}\n\n"
        f"## Réponse B\n\n{pair.text_b}\n\n"
        "## Format de sortie (strict)\n\n"
        "Une table markdown exactement de la forme :\n"
        "| critère | A | B |\n|---|---|---|\n| <nom> | <note/10> | <note/10> |\n"
        "(une ligne par critère de la grille), puis une ligne finale "
        "`VERDICT: A` ou `VERDICT: B` ou `VERDICT: TIE`, puis 3 phrases "
        "de justification maximum."
    )


_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+(?:[.,]\d+)?)\s*(?:/\s*10)?\s*\|\s*(\d+(?:[.,]\d+)?)\s*(?:/\s*10)?\s*\|\s*$")
_VERDICT_RE = re.compile(r"VERDICT\s*:\s*(A|B|TIE)", re.IGNORECASE)


@dataclass
class CaseScore:
    case_id: str
    armance_side: str
    scores: dict[str, tuple[float, float]] = field(default_factory=dict)  # crit → (A, B)
    verdict: str = ""  # "armance" | "reference" | "tie" | ""

    @property
    def armance_mean(self) -> float:
        return self._mean(0 if self.armance_side == "A" else 1)

    @property
    def reference_mean(self) -> float:
        return self._mean(1 if self.armance_side == "A" else 0)

    def _mean(self, idx: int) -> float:
        if not self.scores:
            return 0.0
        return sum(v[idx] for v in self.scores.values()) / len(self.scores)


def parse_judge_reply(case: BenchCase, pair: AnonymisedPair, reply: str) -> CaseScore:
    """Extract the score table + verdict, de-anonymised to armance/reference."""
    score = CaseScore(case_id=case.id, armance_side=pair.armance_side)
    for line in reply.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        name = m.group(1).strip().lower()
        if name in ("critère", "criterion", "---", ""):
            continue
        a = float(m.group(2).replace(",", "."))
        b = float(m.group(3).replace(",", "."))
        score.scores[name] = (a, b)
    m = _VERDICT_RE.search(reply)
    if m:
        raw = m.group(1).upper()
        if raw == "TIE":
            score.verdict = "tie"
        else:
            score.verdict = "armance" if raw == pair.armance_side else "reference"
    return score


# ── Report ────────────────────────────────────────────────────────────────


def render_report(
    preset_name: str,
    judge_model: str,
    scores: list[CaseScore],
    previous: dict[str, float] | None = None,
) -> str:
    """bench-report.md — per-case scores, aggregate, delta vs previous run."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wins = sum(1 for s in scores if s.verdict == "armance")
    losses = sum(1 for s in scores if s.verdict == "reference")
    ties = sum(1 for s in scores if s.verdict == "tie")
    lines = [
        f"# Bench — preset `{preset_name}`",
        "",
        f"- date : {now}",
        f"- juge (cross-family, aveugle A/B) : `{judge_model}`",
        f"- verdict global : **{wins} victoires Armance / {losses} référence / {ties} égalités**",
        "",
        "| cas | Armance | référence frontier | verdict | delta vs run précédent |",
        "|---|---|---|---|---|",
    ]
    for s in scores:
        delta = ""
        if previous and s.case_id in previous:
            d = s.armance_mean - previous[s.case_id]
            delta = f"{d:+.1f}"
        lines.append(
            f"| {s.case_id} | {s.armance_mean:.1f}/10 | {s.reference_mean:.1f}/10 "
            f"| {s.verdict or 'n/a'} | {delta or '—'} |"
        )
    if scores:
        overall = sum(s.armance_mean for s in scores) / len(scores)
        ref_overall = sum(s.reference_mean for s in scores) / len(scores)
        lines += ["", f"Moyenne Armance : **{overall:.1f}/10** · référence : {ref_overall:.1f}/10"]
    lines += [
        "",
        "> Méthode : sorties anonymisées (côté A/B tiré au sort par cas), juge",
        "> d'une autre famille de modèles que les agents, grille par cas",
        "> (`rubric.md`). La référence est la réponse one-shot d'un modèle",
        "> frontier, versionnée dans le pack.",
    ]
    return "\n".join(lines)


def load_previous_means(report_dir: Path) -> dict[str, float] | None:
    """Read ``latest.json`` (case_id → armance mean) if a prior run exists."""
    path = report_dir / "latest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {str(k): float(v) for k, v in data.items()} if isinstance(data, dict) else None


def save_latest_means(report_dir: Path, scores: list[CaseScore]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "latest.json").write_text(
        json.dumps({s.case_id: round(s.armance_mean, 2) for s in scores}, indent=2),
        encoding="utf-8",
    )
