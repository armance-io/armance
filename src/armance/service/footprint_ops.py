"""Footprint surface operations for the TUI layer.

Pure functions:
  format_token_subtitle(snapshot, show_water) -> str
  aggregate_footprint_records(log_files)     -> rollup dict

TUI handler:
  cmd_footprint(args, ctx) -> str

The aggregation function is designed for reuse in EI.7 (web stats route)
with zero changes — same pure function, different front-end.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from armance.nls import t
from armance.service.equivalences import humanise

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bucket helpers — shared bound accumulation
# ---------------------------------------------------------------------------

def _empty_footprint_bucket() -> dict[str, Any]:
    """Seed a footprint bucket with carbon, water, bound and flag fields."""
    return {
        "gco2e": 0.0, "water_ml": 0.0, "calls": 0,
        "has_estimate": False, "has_unknown": False,
        "gco2e_min": 0.0, "gco2e_max": 0.0,
        "water_ml_min": 0.0, "water_ml_max": 0.0,
        "tiers": {
            "declared": 0.0,
            "computed": 0.0,
            "estimated": 0.0,
            "bounded": 0.0,
        },
        "details": [],
    }


def _bound(rec: dict[str, Any], key: str, midpoint: float) -> float:
    """Return a bound field, falling back to ``midpoint`` if absent or null.

    Records predating D1 carry no ``*_min``/``*_max`` keys; some D1 records
    may carry an explicit ``null`` bound. Both fall back to the midpoint so
    old/partial logs contribute a degenerate range rather than crashing.
    """
    val = rec.get(key)
    return midpoint if val is None else val


def _accumulate_bounds(bucket: dict[str, Any], rec: dict[str, Any]) -> None:
    """Add the record's carbon/water midpoint plus its min/max bounds.

    The caller has already verified ``gco2e`` is not None (unknown records
    are handled separately).
    """
    gco2e = rec.get("gco2e")
    water_ml = rec.get("water_ml")
    bucket["gco2e"] += gco2e
    bucket["gco2e_min"] += _bound(rec, "gco2e_min", gco2e)
    bucket["gco2e_max"] += _bound(rec, "gco2e_max", gco2e)
    if water_ml is not None:
        bucket["water_ml"] += water_ml
        bucket["water_ml_min"] += _bound(rec, "water_ml_min", water_ml)
        bucket["water_ml_max"] += _bound(rec, "water_ml_max", water_ml)


def _accumulate_tiers(bucket: dict[str, Any], rec: dict[str, Any]) -> None:
    """Accummulate gCO2e by footprint tier and store model-level details."""
    gco2e = rec.get("gco2e", 0.0) or 0.0
    tier = rec.get("tier", "unknown")

    # Map the 6 resolution tiers to 4 user-facing honesty categories.
    # "computed" means a REAL declared parameter count was used; a
    # provider-default size bucket is a guess and belongs in "estimated".
    cat = "bounded"
    if tier in ("exact", "aliased"):
        cat = "declared"
    elif tier == "params":
        cat = "computed"
    elif tier in ("similar", "provider-default"):
        cat = "estimated"
    elif tier == "bounded":
        cat = "bounded"

    # Ensure tiers dictionary exists
    if "tiers" not in bucket:
        bucket["tiers"] = {"declared": 0.0, "computed": 0.0, "estimated": 0.0, "bounded": 0.0}
    bucket["tiers"][cat] += gco2e

    # Collect model details
    model = rec.get("model", "unknown")
    proxy_model = rec.get("proxy_model")

    if "details" not in bucket:
        bucket["details"] = []
    
    details = bucket["details"]
    found = False
    for d in details:
        if d["category"] == cat and d["model"] == model and d["proxy_model"] == proxy_model:
            d["gco2e"] += gco2e
            d["calls"] += 1
            found = True
            break
    if not found:
        details.append({
            "category": cat,
            "model": model,
            "proxy_model": proxy_model,
            "gco2e": gco2e,
            "calls": 1,
        })



# ---------------------------------------------------------------------------
# footprint_stats — shared with EI.7 web route
# ---------------------------------------------------------------------------

def footprint_stats(logs_dir: Path, project_id: str) -> dict[str, Any]:
    """Aggregate footprint records from all session log files under logs_dir.

    Returns::

        {
            "by_agent":   {name: bucket},
            "by_day":     {"YYYY-MM-DD": bucket},
            "by_month":   {"YYYY-MM": bucket},
            "by_session": {sid: bucket},
            "dominant_zone": str | None,
        }

    Each bucket: {gco2e, water_ml, calls, has_estimate, has_unknown,
    gco2e_min, gco2e_max, water_ml_min, water_ml_max}. The bound fields
    accumulate the per-record EcoLogits range; records that predate D1
    (no ``gco2e_min``/``gco2e_max`` keys) fall back to the midpoint value.

    ``by_session`` is keyed by the session-id prefix of the filename
    (``{sid}-llm_exchanges.jsonl``); the bare ``llm_exchanges.jsonl``
    fallback file is keyed ``"default"``.
    """
    if not logs_dir.exists():
        return {
            "by_agent": {}, "by_day": {}, "by_month": {},
            "by_session": {}, "dominant_zone": None,
        }

    log_files = sorted(logs_dir.glob("*.jsonl"))

    # by_agent / by_day / by_month from shared aggregator
    base = aggregate_footprint_records(log_files)

    # by_session — keyed by filename-derived sid
    by_session: dict[str, dict[str, Any]] = defaultdict(_empty_footprint_bucket)

    for log_file in log_files:
        name = log_file.name  # e.g. "abc123-llm_exchanges.jsonl"
        if name == "llm_exchanges.jsonl":
            sid = "default"
        else:
            sid = name.split("-llm_exchanges.jsonl")[0]

        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") != "response":
                continue

            gco2e = rec.get("gco2e")
            estimate = rec.get("estimate")
            bucket = by_session[sid]
            bucket["calls"] += 1
            if gco2e is None:
                bucket["has_unknown"] = True
            else:
                _accumulate_bounds(bucket, rec)
                _accumulate_tiers(bucket, rec)
                if estimate:
                    bucket["has_estimate"] = True

    return {
        "by_agent": base["by_agent"],
        "by_day": base["by_day"],
        "by_month": base["by_month"],
        "by_session": dict(by_session),
        "dominant_zone": base["dominant_zone"],
    }


# ---------------------------------------------------------------------------
# Sub-title chip
# ---------------------------------------------------------------------------

def _render_co2_chip(total: dict[str, Any]) -> str:
    """Return the 🌱 chip string (without water or token parts).

    Range form:   ``~[{min:.2g} – {max:.2g}]gCO₂e (~{n:.2g} phone charges)``
    Single form:  ``~{mid:.2g}gCO₂e (~{n:.2g} phone charges)``
    Unknown form: ``🌱?``  (returned as-is, no equivalence)

    The em-dash used in the range is U+2013 (–).
    """
    gco2e = total.get("gco2e", 0.0)
    gco2e_min = total.get("gco2e_min", gco2e)
    gco2e_max = total.get("gco2e_max", gco2e)
    water_ml = total.get("water_ml", 0.0)
    has_estimate = total.get("has_estimate", False)
    has_unknown = total.get("has_unknown", False)

    if has_unknown and gco2e == 0.0:
        return "🌱?"

    prefix = "~" if has_estimate else ""
    suffix = "?" if has_unknown else ""

    if gco2e_max - gco2e_min > 1e-9:
        co2_part = f"{prefix}🌱[{gco2e_min:.2g} – {gco2e_max:.2g}]gCO₂e{suffix}"
    else:
        co2_part = f"{prefix}🌱{gco2e:.2g}gCO₂e{suffix}"

    # Append ADEME phone-charges equivalence (mid-point value).
    eq = humanise(gco2e=gco2e, water_ml=water_ml)
    label = t("footprint.equiv.phone_charges")
    equiv_str = f"(~{eq.phone_charges:.2g} {label})"
    return f"{co2_part} {equiv_str}"


def format_token_subtitle(snapshot: dict[str, Any], *, show_water: bool) -> str:
    """Return the full sub_title string including the footprint chip.

    Mirrors the existing ``↑ti ↓to $cost`` format and appends:
      ``· 🌱{gco2e:.2g}gCO₂e (~{n} phone charges)``  (or ``🌱?`` when unknown)
      ``· 💧{water_ml:.0f}mL``   (when show_water=True and not unknown)

    When ``gco2e_min`` / ``gco2e_max`` differ, the chip shows a range:
      ``· ~🌱[{min:.2g} – {max:.2g}]gCO₂e (~{n} phone charges)``

    Estimate flag adds ``~`` prefix to the 🌱 chip.

    Three cases:
      * pure unknown (no figures at all) → ``🌱?`` — never a fabricated 0.
      * mixed (some calls had figures, some did not) → the summed chip plus a
        trailing ``?`` so the partial coverage is visible rather than passed
        off as a complete total.
      * fully known → just the chip (``~`` prefix if any figure is an estimate).
    """
    total = snapshot.get("total", {})
    ti = total.get("tokens_in", 0)
    to_ = total.get("tokens_out", 0)
    cost = total.get("cost_usd", 0.0)
    has_unknown = total.get("has_unknown", False)
    water_ml = total.get("water_ml", 0.0)

    parts = [f"↑{ti:,} ↓{to_:,} ${cost:.4f}"]
    parts.append(_render_co2_chip(total))

    if show_water and not has_unknown:
        parts.append(f"💧{water_ml:.0f}mL")

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Log aggregation (shared with EI.7 web stats)
# ---------------------------------------------------------------------------

def aggregate_footprint_records(log_files: list[Path]) -> dict[str, Any]:
    """Parse llm_exchanges.jsonl files and return rollup dicts.

    Returns::

        {
            "by_agent":  {name: bucket},
            "by_day":    {"YYYY-MM-DD": bucket},
            "by_month":  {"YYYY-MM": bucket},
            "dominant_zone": str | None,
        }

    Each bucket carries ``{gco2e, water_ml, calls, has_estimate, has_unknown,
    gco2e_min, gco2e_max, water_ml_min, water_ml_max}``. The bound fields
    accumulate the per-record EcoLogits range, falling back to the midpoint
    for records that predate D1.

    Only ``event == "response"`` lines are processed; others are skipped.
    ``gco2e=null`` entries count toward ``has_unknown`` but contribute 0 gco2e.
    """

    by_agent: dict[str, dict[str, Any]] = defaultdict(_empty_footprint_bucket)
    by_day: dict[str, dict[str, Any]] = defaultdict(_empty_footprint_bucket)
    by_month: dict[str, dict[str, Any]] = defaultdict(_empty_footprint_bucket)
    zone_counter: Counter[str] = Counter()

    for log_file in log_files:
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") != "response":
                continue

            agent = rec.get("agent", "unknown")
            ts = rec.get("timestamp", "")
            day = ts[:10] if len(ts) >= 10 else "unknown"
            month = ts[:7] if len(ts) >= 7 else "unknown"
            gco2e = rec.get("gco2e")
            estimate = rec.get("estimate")
            zone = rec.get("zone")

            if zone:
                zone_counter[zone] += 1

            for bucket in (by_agent[agent], by_day[day], by_month[month]):
                bucket["calls"] += 1
                if gco2e is None:
                    bucket["has_unknown"] = True
                else:
                    _accumulate_bounds(bucket, rec)
                    _accumulate_tiers(bucket, rec)
                    if estimate:
                        bucket["has_estimate"] = True

    dominant_zone: str | None = zone_counter.most_common(1)[0][0] if zone_counter else None

    return {
        "by_agent": dict(by_agent),
        "by_day": dict(by_day),
        "by_month": dict(by_month),
        "dominant_zone": dominant_zone,
    }


# ---------------------------------------------------------------------------
# /footprint TUI command
# ---------------------------------------------------------------------------

async def cmd_footprint(args: list[str], ctx: Any) -> str:
    """Show environmental footprint breakdown by agent (and day/month on request).

    Usage: /footprint [day|month]
    """
    armance_root: Path = ctx.armance_root
    if armance_root.name == ".armance":
        log_dir = armance_root / "logs"
    else:
        log_dir = armance_root / ".armance" / "logs"

    log_files = sorted(log_dir.glob("*.jsonl")) if log_dir.exists() else []
    rollup = aggregate_footprint_records(log_files)

    by_agent = rollup["by_agent"]
    dominant_zone = rollup["dominant_zone"]

    if not by_agent:
        return t("footprint.no_data")

    # Build Rich-compatible markdown table (works in TUI rich text panels)
    lines: list[str] = []
    title = t("footprint.cmd_title")
    if dominant_zone:
        title += f" — {t('footprint.zone_note', zone=dominant_zone)}"
    lines.append(f"**{title}**\n")

    col_agent = t("footprint.col_agent")
    col_gco2e = t("footprint.col_gco2e")
    col_water = t("footprint.col_water")
    col_calls = t("footprint.col_calls")
    col_est = t("footprint.col_estimate")

    lines.append(f"| {col_agent} | {col_gco2e} | {col_water} | {col_calls} | {col_est} |")
    lines.append("|---|---|---|---|---|")

    total_gco2e = 0.0
    total_water = 0.0
    total_calls = 0
    any_estimate = False
    any_unknown = False

    for agent, b in sorted(by_agent.items()):
        prefix = "~" if b["has_estimate"] else ("?" if b["has_unknown"] else "")
        gco2e_str = f"{prefix}{b['gco2e']:.3g}"
        water_str = f"{b['water_ml']:.0f}"
        est_flag = "~" if b["has_estimate"] else ("?" if b["has_unknown"] else "")
        lines.append(
            f"| {agent} | {gco2e_str} | {water_str} | {b['calls']} | {est_flag} |"
        )
        total_gco2e += b["gco2e"]
        total_water += b["water_ml"]
        total_calls += b["calls"]
        any_estimate = any_estimate or b["has_estimate"]
        any_unknown = any_unknown or b["has_unknown"]

    total_prefix = "~" if any_estimate else ("?" if any_unknown else "")
    lines.append(
        f"| **{t('footprint.total_row')}** | **{total_prefix}{total_gco2e:.3g}** "
        f"| **{total_water:.0f}** | **{total_calls}** | |"
    )

    # Optional day/month breakdown
    sub = args[0].lower() if args else ""
    if sub == "day":
        lines.append(f"\n**{t('footprint.by_day')}**\n")
        for day, b in sorted(rollup["by_day"].items()):
            prefix = "~" if b["has_estimate"] else ""
            lines.append(f"- {day}: {prefix}{b['gco2e']:.3g} gCO₂e")
    elif sub == "month":
        lines.append(f"\n**{t('footprint.by_month')}**\n")
        for month, b in sorted(rollup["by_month"].items()):
            prefix = "~" if b["has_estimate"] else ""
            lines.append(f"- {month}: {prefix}{b['gco2e']:.3g} gCO₂e")

    if any_estimate:
        lines.append(f"\n*{t('footprint.estimate_note')}*")
    if any_unknown:
        lines.append(f"\n*{t('footprint.unknown_note')}*")

    return "\n".join(lines)
