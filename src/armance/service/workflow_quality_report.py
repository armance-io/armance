"""Creuset quality report (Lot H) — auditable evidence for a crucible run.

Makes the "almost blind trust" in a crucible run JUSTIFIED: per-criterion
gate scores, gate verdicts + reasons, iteration count, paired draft
divergences (critique) ↔ resolution (synthesis), and families-per-stage with
an explicit degraded flag (in-flight vs mono-family-from-the-start).

Pure functions over a *finalized manifest dict* + the run directory (to read
`step-<id>.md` outputs). No LLM, no network. Activates ONLY when the run has
real crucible stages — a plain `standard` run yields ``None`` (no section).

Data producer only: the paired divergences + resolved gate scores are the
substrate consumed by `reasoning-receipt-export` (aggregate receipt) and
`disagreement-memory` (sediment draft-vs-draft dissent). This module does NOT
persist into those — # see disagreement-memory / reasoning-receipt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from armance.service.gate_parsing import parse_gate_scores, parse_gate_verdict

CRUCIBLE_STAGES = {"draft", "critique", "synthesis", "gate"}


@dataclass
class GateEvidence:
    """One gate step's verdict + scores + reasons (Lot H §1/§2)."""

    step_id: str
    verdict: str | None  # ACCEPT | REVISE | None (broken gate → treated REVISE)
    scores: dict[str, float] = field(default_factory=dict)
    threshold: float | None = None
    reasons: str = ""

    @property
    def effective_verdict(self) -> str:
        """A gate with no tag is a broken gate → REVISE (§F4)."""
        return self.verdict or "REVISE"

    @property
    def weighted_mean(self) -> float | None:
        if not self.scores:
            return None
        return round(sum(self.scores.values()) / len(self.scores), 2)


@dataclass
class CrucibleReport:
    """Structured quality evidence for one crucible run."""

    families_by_stage: dict[str, str] = field(default_factory=dict)
    gates: list[GateEvidence] = field(default_factory=list)
    iterations: int = 0  # 0 = direct ACCEPT, 1 = one REVISE→synthesis_v2 round
    draft_divergences: str = ""     # `## Divergences entre drafts` (critique)
    resolved_divergences: str = ""  # `## Divergences résolues` (synthesis)
    degraded: bool = False
    degraded_reason: str = ""       # names the cause, never a bare "degraded"
    available_families: int | None = None
    threshold_met: bool = True      # False when delivered below threshold


def _step_output(run_dir: Path, output_path: str | None, step_id: str) -> str:
    """Read a step's raw output; prefer the manifest's relative path, else
    fall back to the conventional `step-<id>.md` name."""
    candidates: list[Path] = []
    if output_path:
        candidates.append(run_dir / output_path)
    safe = re.sub(r"[^\w-]", "_", step_id)[:64]
    candidates.append(run_dir / f"step-{safe}.md")
    for p in candidates:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def _extract_section(text: str, heading: str) -> str:
    """Return the body under a `## <heading>` markdown section (up to the next
    heading of the same-or-higher level), stripped. Empty if not present."""
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    want = heading.strip().lower()
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            title = m.group(2).strip().lower()
            level = len(m.group(1))
            if capturing:
                # Stop at the next heading of level <= the section's (##) level.
                if level <= 2:
                    break
                out.append(line)
                continue
            if title.startswith(want) or want in title:
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def build_crucible_report(
    manifest: dict[str, Any], run_dir: Path,
) -> CrucibleReport | None:
    """Assemble a :class:`CrucibleReport` from a finalized manifest + run_dir.

    Returns ``None`` when the run has no crucible stage (a plain `standard`
    workflow) — the caller then writes no quality section. `available_families`
    (optional, from the run's degraded diagnostics) lets §G4 mono-family be
    named explicitly; when absent it is inferred from the families actually used.
    """
    steps: list[dict[str, Any]] = manifest.get("steps") or []
    staged = [s for s in steps if (s.get("stage") or "standard") in CRUCIBLE_STAGES]
    if not staged:
        return None

    report = CrucibleReport()

    # Families per stage (draft steps keyed by their own id; single-instance
    # stages keyed by stage name).
    draft_count = 0
    for s in staged:
        stage = s.get("stage") or "standard"
        fam = s.get("family") or "?"
        if stage == "draft":
            report.families_by_stage[s["id"]] = fam
            draft_count += 1
        else:
            report.families_by_stage[stage] = fam

    # Gate evidence (one entry per gate step, in manifest order → gate_1, gate_2).
    threshold_map = _thresholds_from_manifest(manifest)
    for s in staged:
        if (s.get("stage") or "") != "gate":
            continue
        if (s.get("status") or "") in ("skipped", "queued"):
            continue  # a gate_2 that never fired (direct ACCEPT) is not evidence
        text = _step_output(run_dir, s.get("output_path"), s["id"])
        ev = GateEvidence(
            step_id=s["id"],
            verdict=parse_gate_verdict(text),
            scores=parse_gate_scores(text),
            threshold=threshold_map.get(s["id"]),
            reasons=_gate_reasons(text),
        )
        report.gates.append(ev)

    # Iteration count: a fired gate_2 (any second gate that actually ran) means
    # one revision happened.
    report.iterations = max(0, len(report.gates) - 1)

    # threshold_met: the LAST gate's verdict is terminal.
    if report.gates:
        last = report.gates[-1]
        report.threshold_met = last.effective_verdict == "ACCEPT"

    # Paired divergences: critique's `## Divergences entre drafts` ↔ synthesis's
    # `## Divergences résolues`.
    for s in staged:
        stage = s.get("stage") or ""
        text = _step_output(run_dir, s.get("output_path"), s["id"])
        if stage == "critique" and not report.draft_divergences:
            report.draft_divergences = _extract_section(text, "Divergences entre drafts")
        elif stage == "synthesis" and not report.resolved_divergences:
            report.resolved_divergences = _extract_section(text, "Divergences résolues")

    _flag_degraded(report, manifest, draft_count)
    return report


def _thresholds_from_manifest(manifest: dict[str, Any]) -> dict[str, float]:
    """Gate thresholds, if the manifest carried them (optional key)."""
    out: dict[str, float] = {}
    for s in manifest.get("steps") or []:
        thr = s.get("gate_threshold")
        if thr is not None:
            try:
                out[s["id"]] = float(thr)
            except (TypeError, ValueError):
                continue
    return out


def _gate_reasons(text: str) -> str:
    """Everything after the terminal `[GATE:...]` tag = the reasons block."""
    m = list(re.finditer(r"\[GATE:(?:ACCEPT|REVISE)\]", text))
    if not m:
        return text.strip()
    return text[m[-1].end():].strip()


def _flag_degraded(
    report: CrucibleReport, manifest: dict[str, Any], draft_count: int,
) -> None:
    """Set the degraded flag + a NAMED cause (§G3 in-flight vs §G4 mono-family).

    Never a bare "degraded": a run is degraded either because a draft failed in
    flight (a draft step's status is failed) or because only one family was
    available from the start (all draft families collapse to one).
    """
    draft_families = {
        fam for sid, fam in report.families_by_stage.items()
        if any(
            s["id"] == sid and (s.get("stage") == "draft")
            for s in manifest.get("steps") or []
        )
    }
    report.available_families = manifest.get("available_families")
    # G3: a draft failed in flight.
    failed_draft = any(
        (s.get("stage") == "draft") and (s.get("status") == "failed")
        for s in manifest.get("steps") or []
    )
    if failed_draft:
        report.degraded = True
        report.degraded_reason = (
            "dégradé en vol : un draft a échoué en cours de run (§G3) — "
            "la critique cross-family a perdu un brouillon"
        )
        return
    # G4: only one family available/used from the start.
    known = {f for f in draft_families if f and f != "?"}
    if draft_count >= 2 and len(known) == 1:
        n = report.available_families if report.available_families is not None else 1
        report.degraded = True
        report.degraded_reason = (
            f"creuset dégradé : {n} famille(s) de modèles disponible(s) — "
            f"diversité cross-family impossible dès le départ (§G4)"
        )


def render_crucible_report_md(report: CrucibleReport | None) -> str:
    """Render the crucible quality section as markdown. Empty string for a
    ``None`` report (non-crucible run) so callers can append unconditionally."""
    if report is None:
        return ""
    lines: list[str] = ["## Creuset — reçu de qualité", ""]

    # Families per stage.
    lines += ["### Familles par stage", "", "| Stage | Famille |", "|---|---|"]
    lines += [f"| {stage} | {fam} |" for stage, fam in report.families_by_stage.items()]
    lines.append("")
    if report.degraded:
        lines += [f"> ⚠️ {report.degraded_reason}", ""]

    # Iterations.
    if report.iterations == 0:
        lines.append("**Itérations : 0** (ACCEPT direct, aucune révision).")
    else:
        lines.append(
            f"**Itérations : {report.iterations}** "
            f"(REVISE → synthèse révisée puis re-notée)."
        )
    if not report.threshold_met:
        lines.append(
            "> ⚠️ Seuil non atteint après 1 révision — livré quand même (flag qualité)."
        )
    lines.append("")

    # Gate evidence.
    for ev in report.gates:
        lines += [f"### Gate `{ev.step_id}` — {ev.effective_verdict}", ""]
        if ev.scores:
            thr = ev.threshold if ev.threshold is not None else 7.5
            lines += ["| Critère | Score | Seuil |", "|---|---|---|"]
            lines += [f"| {n} | {sc:g}/10 | {thr:g} |" for n, sc in ev.scores.items()]
            mean = ev.weighted_mean
            if mean is not None:
                lines += ["", f"Moyenne : **{mean:g}/10** (seuil {thr:g})."]
        if ev.reasons:
            lines += ["", "Raisons du gate :", "", ev.reasons]
        lines.append("")

    # Paired divergences (the heart of the receipt).
    if report.draft_divergences or report.resolved_divergences:
        lines += ["### Désaccords entre drafts → résolution", ""]
        if report.draft_divergences:
            lines += ["**Divergences relevées (critique) :**", "", report.draft_divergences, ""]
        if report.resolved_divergences:
            lines += ["**Résolution (synthèse) :**", "", report.resolved_divergences, ""]

    # see disagreement-memory / reasoning-receipt: this section is the substrate
    # those features aggregate/persist; not duplicated here.
    return "\n".join(lines).rstrip() + "\n"
