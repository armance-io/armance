import { describe, it, expect } from "vitest";
import { packLanes, computeLayout, type RawNode, type RawEdge } from "./graphLayout";

function node(id: string, started?: string, ended?: string): RawNode {
  return {
    id,
    // packLanes/computeLayout read started_at/ended_at off the data bag
    // (StepNodeData extends Record<string, unknown>); the named fields are
    // required by the type but unused by the layout.
    data: {
      step_id: id,
      role: "specialist",
      status: "completed",
      started_at: started,
      ended_at: ended,
    },
  };
}

describe("packLanes", () => {
  it("keeps sequential (non-overlapping) nodes in a single lane", () => {
    const lanes = packLanes([
      node("a", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z"),
      node("b", "2026-01-01T00:01:00Z", "2026-01-01T00:02:00Z"),
    ]);
    expect(lanes).toEqual({ a: 0, b: 0 });
  });

  it("splits overlapping nodes onto separate lanes", () => {
    const lanes = packLanes([
      node("a", "2026-01-01T00:00:00Z", "2026-01-01T00:02:00Z"),
      node("b", "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z"),
    ]);
    expect(lanes.a).toBe(0);
    expect(lanes.b).toBe(1);
  });

  it("places nodes without timing in lane 0", () => {
    expect(packLanes([node("queued")])).toEqual({ queued: 0 });
  });

  it("reuses a freed lane once an earlier node has ended", () => {
    const lanes = packLanes([
      node("a", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z"),
      node("b", "2026-01-01T00:00:30Z", "2026-01-01T00:02:00Z"),
      node("c", "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z"),
    ]);
    // c starts when a ends → it can reuse lane 0; b stays on lane 1.
    expect(lanes.a).toBe(0);
    expect(lanes.b).toBe(1);
    expect(lanes.c).toBe(0);
  });
});

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

  it("offsets concurrent lanes vertically", () => {
    const nodes = [
      node("a", "2026-01-01T00:00:00Z", "2026-01-01T00:02:00Z"),
      node("b", "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z"),
    ];
    const out = computeLayout(nodes, []);
    const ya = out.nodes.find((n) => n.id === "a")!.position.y;
    const yb = out.nodes.find((n) => n.id === "b")!.position.y;
    expect(yb - ya).toBeGreaterThanOrEqual(120);
  });
});
