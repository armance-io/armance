import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const routeParams = vi.fn();
vi.mock("@/lib/routeParams", () => ({
  useRouteParams: () => routeParams(),
}));

import ProjectEntryView from "../ProjectEntryView";

function setReplace() {
  const replace = vi.fn();
  Object.defineProperty(window, "location", {
    value: { replace, pathname: "/projects/projb-1234" },
    writable: true,
  });
  return replace;
}

describe("ProjectEntryView", () => {
  beforeEach(() => {
    routeParams.mockReset();
    vi.restoreAllMocks();
  });

  it("resolves the latest session for the URL pid and lands on it", async () => {
    routeParams.mockReturnValue({ pid: "projb-1234", sid: "" });
    const replace = setReplace();
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ id: "sess-9" }),
    } as Response);

    render(<ProjectEntryView />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/projects/projb-1234/sessions/sess-9"),
    );
    // Resolves against the URL pid, never a hard-coded "default".
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/projects/projb-1234/sessions/latest",
      expect.anything(),
    );
  });

  it("shows an error when the project cannot be resolved", async () => {
    routeParams.mockReturnValue({ pid: "projb-1234", sid: "" });
    setReplace();
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 404 } as Response);

    render(<ProjectEntryView />);
    await waitFor(() =>
      expect(screen.getByTestId("project-entry-error")).toBeInTheDocument(),
    );
  });
});
