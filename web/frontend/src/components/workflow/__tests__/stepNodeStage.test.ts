import { describe, it, expect } from "vitest";
import {
  STAGE_GEMS,
  stageGem,
  stepCostLabel,
  fmtCost,
  fmtTokens,
} from "../stepNodeStage";

describe("stageGem", () => {
  it("returns a gem for each crucible stage", () => {
    for (const stage of ["draft", "critique", "synthesis", "gate"] as const) {
      const gem = stageGem(stage);
      expect(gem).not.toBeNull();
      expect(gem!.key).toBe(stage);
      expect(gem!.hue).toBeTruthy();
    }
  });

  it("returns null for standard / null / undefined / unknown", () => {
    expect(stageGem("standard")).toBeNull();
    expect(stageGem(null)).toBeNull();
    expect(stageGem(undefined)).toBeNull();
    expect(stageGem("weird" as never)).toBeNull();
  });

  it("uses four DISTINCT hues (badges must be tellable apart)", () => {
    const hues = Object.values(STAGE_GEMS).map((g) => g.hue);
    expect(new Set(hues).size).toBe(hues.length);
  });
});

describe("stepCostLabel — never invents a figure", () => {
  it("prefers cost_usd when present", () => {
    expect(stepCostLabel(0.0123, 100, 200)).toBe("$0.0123");
    expect(stepCostLabel(0, 100, 200)).toBe("$0.0000");
  });

  it("falls back to summed tokens when cost is missing", () => {
    expect(stepCostLabel(null, 1500, 1000)).toBe("2.5k");
    expect(stepCostLabel(undefined, 1500, null)).toBe("1.5k");
  });

  it("returns an empty string when neither cost nor tokens exist", () => {
    expect(stepCostLabel(null, null, null)).toBe("");
    expect(stepCostLabel(undefined, undefined, undefined)).toBe("");
  });
});

describe("formatters", () => {
  it("fmtCost renders 4 decimals and empty for null", () => {
    expect(fmtCost(1.5)).toBe("$1.5000");
    expect(fmtCost(null)).toBe("");
  });

  it("fmtTokens buckets k / M and empty for null", () => {
    expect(fmtTokens(999)).toBe("999");
    expect(fmtTokens(2500)).toBe("2.5k");
    expect(fmtTokens(3_000_000)).toBe("3.0M");
    expect(fmtTokens(null)).toBe("");
  });
});
