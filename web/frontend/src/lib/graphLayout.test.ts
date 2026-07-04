import { describe, it, expect } from "vitest";
import { computeLayout, type RawNode, type RawEdge } from "./graphLayout";

function node(id: string, started?: string, ended?: string): RawNode {
  return {
    id,
    data: {
      step_id: id,
      role: "specialist",
      status: "completed",
      started_at: started,
      ended_at: ended,
    },
  };
}

describe("computeLayout", () => {
  it("returns a positioned node per input and preserves edges", () => {
    const nodes = [node("a"), node("b")];
    const edges: RawEdge[] = [{ id: "e1", source: "a", target: "b" }];
    const out = computeLayout(nodes, edges);
    expect(out.nodes).toHaveLength(2);
    expect(out.nodes[0]).toMatchObject({ id: "a", type: "stepNode" });
    expect(out.nodes[0]!.position).toHaveProperty("x");
    expect(out.nodes[0]!.position).toHaveProperty("y");
    expect(out.edges).toEqual([{ id: "e1", source: "a", target: "b" }]);
  });

  it("separates same-rank (parallel) nodes vertically without overlap", () => {
    // Diamond: a → b, a → c — b and c share a rank and must not overlap.
    const nodes = [node("a"), node("b"), node("c")];
    const edges: RawEdge[] = [
      { id: "e1", source: "a", target: "b" },
      { id: "e2", source: "a", target: "c" },
    ];
    const out = computeLayout(nodes, edges);
    const yb = out.nodes.find((n) => n.id === "b")!.position.y;
    const yc = out.nodes.find((n) => n.id === "c")!.position.y;
    expect(Math.abs(yb - yc)).toBeGreaterThanOrEqual(72);
  });

  it("does not shift positions when run timing data is present", () => {
    // Regression: a time-based lane offset used to stack +120px per
    // overlapping step ON TOP of dagre's y, corrupting live-run layouts.
    const plain = computeLayout([node("a"), node("b")], [
      { id: "e1", source: "a", target: "b" },
    ]);
    const timed = computeLayout(
      [
        node("a", "2026-01-01T00:00:00Z", "2026-01-01T00:02:00Z"),
        node("b", "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z"),
      ],
      [{ id: "e1", source: "a", target: "b" }],
    );
    expect(timed.nodes.map((n) => n.position)).toEqual(
      plain.nodes.map((n) => n.position),
    );
  });
});
