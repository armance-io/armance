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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-title chip
# ---------------------------------------------------------------------------

def format_token_subtitle(snapshot: dict[str, Any], *, show_water: bool) -> str:
    """Return the full sub_title string including the footprint chip.

    Mirrors the existing ``↑ti ↓to $cost`` format and appends:
      ``· 🌱{gco2e:.2g}gCO₂e``  (or ``🌱?`` when unknown)
      ``· 💧{water_ml:.0f}mL``   (when show_water=True and not unknown)

    Estimate flag adds ``~`` prefix to the 🌱 chip.
    """
    total = snapshot.get("total", {})
    ti = total.get("tokens_in", 0)
    to_ = total.get("tokens_out", 0)
    cost = total.get("cost_usd", 0.0)
    gco2e = total.get("gco2e", 0.0)
    water_ml = total.get("water_ml", 0.0)
    has_estimate = total.get("has_estimate", False)
    has_unknown = total.get("has_unknown", False)

    parts = [f"↑{ti:,} ↓{to_:,} ${cost:.4f}"]

    if has_unknown and gco2e == 0.0:
        parts.append("🌱?")
    else:
        prefix = "~" if has_estimate else ""
        chip = f"{prefix}🌱{gco2e:.2g}gCO₂e"
        parts.append(chip)
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
            "by_agent":  {name: {gco2e, water_ml, calls, has_estimate, has_unknown}},
            "by_day":    {"YYYY-MM-DD": {gco2e, water_ml, calls, has_estimate}},
            "by_month":  {"YYYY-MM": {gco2e, water_ml, calls, has_estimate}},
            "dominant_zone": str | None,
        }

    Only ``event == "response"`` lines are processed; others are skipped.
    ``gco2e=null`` entries count toward ``has_unknown`` but contribute 0 gco2e.
    """

    def _empty_bucket() -> dict[str, Any]:
        return {"gco2e": 0.0, "water_ml": 0.0, "calls": 0,
                "has_estimate": False, "has_unknown": False}

    by_agent: dict[str, dict[str, Any]] = defaultdict(lambda: _empty_bucket())
    by_day: dict[str, dict[str, Any]] = defaultdict(lambda: _empty_bucket())
    by_month: dict[str, dict[str, Any]] = defaultdict(lambda: _empty_bucket())
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
            water_ml = rec.get("water_ml")
            estimate = rec.get("estimate")
            zone = rec.get("zone")

            if zone:
                zone_counter[zone] += 1

            for bucket in (by_agent[agent], by_day[day], by_month[month]):
                bucket["calls"] += 1
                if gco2e is None:
                    bucket["has_unknown"] = True
                else:
                    bucket["gco2e"] += gco2e
                    if water_ml is not None:
                        bucket["water_ml"] += water_ml
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
