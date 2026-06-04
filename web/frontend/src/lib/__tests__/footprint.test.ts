/**
 * EI.8 — getFootprint API wrapper + useFootprint hook types.
 *
 * Tests the typed wrapper and the shape of the response.
 * Visual rendering (chip + Empreinte tab) is covered by Playwright
 * after the Design hand-off delivers the visual components.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getFootprint,
  type FootprintBucket,
  type FootprintEquiv,
  type FootprintResponse,
} from "../footprint";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(body: unknown, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(String(body)),
  } as Response);
}

const SAMPLE_BUCKET: FootprintBucket = {
  gco2e: 0.42,
  water_ml: 2.1,
  calls: 3,
  has_estimate: false,
  has_unknown: false,
};

const SAMPLE_RESPONSE: FootprintResponse = {
  by_agent: { alice: SAMPLE_BUCKET },
  by_day: { "2026-05-29": SAMPLE_BUCKET },
  by_month: { "2026-05": SAMPLE_BUCKET },
  by_session: { sid1: SAMPLE_BUCKET },
  dominant_zone: "WOR",
};

// ---------------------------------------------------------------------------
// getFootprint
// ---------------------------------------------------------------------------

describe("getFootprint", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls /api/projects/{pid}/admin/footprint?group_by=agent", async () => {
    mockFetch(SAMPLE_RESPONSE);
    await getFootprint("default", "agent");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/projects/default/admin/footprint"),
      expect.anything(),
    );
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]![0] as string;
    expect(url).toContain("group_by=agent");
  });

  it("returns typed FootprintResponse", async () => {
    mockFetch(SAMPLE_RESPONSE);
    const result = await getFootprint("default", "agent");
    expect(result.by_agent).toBeDefined();
    expect(result.dominant_zone).toBe("WOR");
  });

  it("defaults group_by to agent", async () => {
    mockFetch(SAMPLE_RESPONSE);
    await getFootprint("default");
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]![0] as string;
    expect(url).toContain("group_by=agent");
  });

  it("passes group_by=session when requested", async () => {
    mockFetch(SAMPLE_RESPONSE);
    await getFootprint("default", "session");
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]![0] as string;
    expect(url).toContain("group_by=session");
  });
});

// ---------------------------------------------------------------------------
// Type shape tests (compile-time checks expressed as runtime assertions)
// ---------------------------------------------------------------------------

describe("FootprintBucket type", () => {
  it("has required numeric fields", () => {
    const b: FootprintBucket = {
      gco2e: 0.5,
      water_ml: 2.0,
      calls: 1,
      has_estimate: false,
      has_unknown: false,
    };
    expect(typeof b.gco2e).toBe("number");
    expect(typeof b.water_ml).toBe("number");
    expect(typeof b.calls).toBe("number");
    expect(typeof b.has_estimate).toBe("boolean");
    expect(typeof b.has_unknown).toBe("boolean");
  });
});

describe("FootprintResponse type", () => {
  it("has all four dimension keys plus dominant_zone", () => {
    const r: FootprintResponse = SAMPLE_RESPONSE;
    expect(r.by_agent).toBeDefined();
    expect(r.by_day).toBeDefined();
    expect(r.by_month).toBeDefined();
    expect(r.by_session).toBeDefined();
    // dominant_zone is string | null
    expect(r.dominant_zone === null || typeof r.dominant_zone === "string").toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Bounds + equivalence (D3)
// ---------------------------------------------------------------------------

describe("FootprintBucket bounds (D3)", () => {
  it("carries optional carbon and water range bounds", () => {
    const b: FootprintBucket = {
      gco2e: 0.4,
      water_ml: 2.0,
      calls: 2,
      has_estimate: true,
      has_unknown: false,
      gco2e_min: 0.2,
      gco2e_max: 0.6,
      water_ml_min: 1.0,
      water_ml_max: 3.0,
    };
    expect(b.gco2e_min).toBe(0.2);
    expect(b.gco2e_max).toBe(0.6);
    expect(b.water_ml_min).toBe(1.0);
    expect(b.water_ml_max).toBe(3.0);
  });

  it("allows bounds to be absent (pre-D1 records)", () => {
    const b: FootprintBucket = SAMPLE_BUCKET;
    expect(b.gco2e_min).toBeUndefined();
    expect(b.gco2e_max).toBeUndefined();
  });
});

describe("FootprintResponse equiv (D3)", () => {
  it("carries an optional ADEME equivalence on the total", () => {
    const equiv: FootprintEquiv = {
      phone_charges: 1.2,
      car_km: 0.05,
      water_glasses: 0.8,
    };
    const r: FootprintResponse = { ...SAMPLE_RESPONSE, equiv };
    expect(r.equiv?.phone_charges).toBe(1.2);
    expect(r.equiv?.car_km).toBe(0.05);
    expect(r.equiv?.water_glasses).toBe(0.8);
  });

  it("returns equiv from getFootprint when present in the payload", async () => {
    const equiv: FootprintEquiv = {
      phone_charges: 2.0,
      car_km: 0.1,
      water_glasses: 1.5,
    };
    mockFetch({ ...SAMPLE_RESPONSE, equiv });
    const result = await getFootprint("default", "agent");
    expect(result.equiv).toEqual(equiv);
  });
});
