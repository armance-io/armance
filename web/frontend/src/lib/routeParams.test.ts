import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

// usePathname is the only external dependency; mock it per-case.
const mockPathname = vi.fn<() => string | null>();
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

import { useRouteParams } from "./routeParams";

function paramsFor(path: string | null) {
  mockPathname.mockReturnValue(path);
  return renderHook(() => useRouteParams()).result.current;
}

describe("useRouteParams", () => {
  it("reads pid + sid from a session path", () => {
    expect(paramsFor("/projects/proj-1/sessions/sess-2/library")).toMatchObject({
      pid: "proj-1",
      sid: "sess-2",
    });
  });

  it("reads workflow name and runId from a deep run path", () => {
    const p = paramsFor("/projects/p/sessions/s/workflows/wf-x/runs/run-9");
    expect(p).toMatchObject({ pid: "p", sid: "s", name: "wf-x", runId: "run-9" });
  });

  it("decodes URL-encoded segments", () => {
    const p = paramsFor("/projects/p/sessions/s/workflows/my%20flow");
    expect(p.name).toBe("my flow");
  });

  it("returns empty strings when segments are absent", () => {
    expect(paramsFor("/projects/p/admin")).toMatchObject({ pid: "p", sid: "" });
  });

  it("never reads the static-export sentinel as a real id", () => {
    // The sentinel shell is served at /projects/_/...; the live URL carries
    // the real ids, so the hook must reflect the live URL, not "_".
    const p = paramsFor("/projects/real-pid/admin");
    expect(p.pid).toBe("real-pid");
    expect(p.pid).not.toBe("_");
  });

  it("tolerates a null pathname", () => {
    expect(paramsFor(null)).toMatchObject({ pid: "", sid: "" });
  });
});
