"""Service-layer workflow ASCII representation helper.

Decouples workflow visualization logic from client rendering.
"""
from __future__ import annotations
from typing import Any

def render_dag_ascii(steps: list[dict[str, Any]], width: int = 72) -> str:
    """Return a multi-line ASCII string representing the workflow DAG.

    Each step is rendered as a box. Dependency arrows are vertical (│, ▼).
    Parallel steps at the same depth are shown side-by-side separated by
    spaces, connected via a branching line.

    Args:
        steps: List of step dicts with at least ``id``, ``kind``, and
               optional ``depends_on`` (list of step-id strings).
        width: Target width for line wrapping (informational, not enforced).

    Returns:
        Multi-line string ready to print in a monospace context.
    """
    if not steps:
        return "(no steps)"

    # Build id→step index and parents map
    by_id: dict[str, dict[str, Any]] = {s["id"]: s for s in steps}
    children: dict[str, list[str]] = {s["id"]: [] for s in steps}
    for s in steps:
        for dep in s.get("depends_on", []):
            if dep in children:
                children[dep].append(s["id"])

    # Compute depth (longest path from a root)
    depth: dict[str, int] = {}

    def _depth(sid: str) -> int:
        if sid in depth:
            return depth[sid]
        deps = by_id[sid].get("depends_on", [])
        d = max((_depth(p) for p in deps if p in by_id), default=-1) + 1
        depth[sid] = d
        return d

    for sid in by_id:
        _depth(sid)

    # Group by depth
    levels: dict[int, list[str]] = {}
    for sid, d in depth.items():
        levels.setdefault(d, []).append(sid)

    lines: list[str] = []
    max_depth = max(levels)

    for lvl in range(max_depth + 1):
        group = levels.get(lvl, [])
        # Render each step as [id · kind]
        boxes = [f"[{sid} · {by_id[sid].get('kind', 'task')}]" for sid in group]
        lines.append("   ".join(boxes))
        if lvl < max_depth:
            # Arrow between levels — simple vertical for now
            lines.append("   │")
            lines.append("   ▼")

    return "\n".join(lines)
