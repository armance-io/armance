import { afterEach, describe, expect, it } from "vitest";

import {
  _resetColourCache,
  assignAgentColour,
  isStaff,
} from "./agent_colours";

afterEach(() => {
  _resetColourCache();
});

describe("assignAgentColour", () => {
  it("returns a reserved violet for each staff agent", () => {
    expect(isStaff("Armance")).toBe(true);
    expect(isStaff("Malik")).toBe(true);
    expect(isStaff("Kim")).toBe(true);
    expect(isStaff("Mona")).toBe(true);
    expect(isStaff("Serge")).toBe(true);
    expect(assignAgentColour("Armance")).toContain("accent");
  });

  it("returns a stable colour for the same specialist name", () => {
    const c1 = assignAgentColour("Aisha");
    const c2 = assignAgentColour("Aisha");
    expect(c1).toBe(c2);
  });

  it("returns different colours for different specialists (statistically)", () => {
    const colours = new Set<string>();
    ["Aisha", "Lars", "Priya", "Élise", "Théo"].forEach((n) =>
      colours.add(assignAgentColour(n)),
    );
    // At least 3 distinct colours among 5 names — collisions allowed,
    // total collapse would be a bug.
    expect(colours.size).toBeGreaterThanOrEqual(3);
  });

  it("never assigns a specialist colour matching a staff slot", () => {
    const staffName = "Armance";
    const reserved = assignAgentColour(staffName);
    const specialist = assignAgentColour("Aisha");
    expect(specialist).not.toBe(reserved);
  });

  it("isStaff returns false for unknown names", () => {
    expect(isStaff("Aisha")).toBe(false);
    expect(isStaff("")).toBe(false);
  });
});
