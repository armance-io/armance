import { describe, it, expect } from "vitest";
import type { Node } from "@xyflow/react";
import { computeCrucibleZones } from "../WorkflowGraph";

function node(id: string, x: number, y: number, stage?: string): Node {
  return {
    id,
    type: "stepNode",
    position: { x, y },
    data: { step_id: id, role: "specialist", status: "queued", stage },
  };
}

describe("computeCrucibleZones", () => {
  it("returns no zone for a workflow without crucible stages", () => {
    const nodes = [node("a", 0, 0), node("b", 320, 0, "standard")];
    expect(computeCrucibleZones(nodes)).toEqual([]);
  });

  it("wraps a draft→critique→synthesis→gate pipeline in ONE zone", () => {
    const nodes = [
      node("intro", 0, 0),
      node("d1", 320, 0, "draft"),
      node("d2", 320, 120, "draft"),
      node("crit", 640, 60, "critique"),
      node("syn", 960, 60, "synthesis"),
      node("gate", 1280, 60, "gate"),
      node("outro", 1600, 60),
    ];
    const zones = computeCrucibleZones(nodes);
    expect(zones).toHaveLength(1);
    const z = zones[0]!;
    // Encloses every staged node (200×72 nodes + padding)…
    expect(z.x).toBeLessThan(320);
    expect(z.x + z.w).toBeGreaterThan(1280 + 200);
    expect(z.y).toBeLessThan(0);
    expect(z.y + z.h).toBeGreaterThan(120 + 72);
    // …but not the plain steps on either side.
    expect(z.x).toBeGreaterThan(0 + 200);
    expect(z.x + z.w).toBeLessThan(1600);
  });

  it("splits two crucibles separated by a wide standard gap into two zones", () => {
    const nodes = [
      node("d1", 0, 0, "draft"),
      node("g1", 320, 0, "gate"),
      node("mid", 640, 0),
      node("d2", 1200, 0, "draft"),
      node("g2", 1520, 0, "gate"),
    ];
    const zones = computeCrucibleZones(nodes);
    expect(zones).toHaveLength(2);
  });
});
