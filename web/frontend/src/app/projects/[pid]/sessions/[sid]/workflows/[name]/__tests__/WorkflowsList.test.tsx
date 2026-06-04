import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { WorkflowsList } from "../WorkflowsList";
import * as api from "@/lib/api";
import { emitViewChange } from "@/lib/navigationBus";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("@/lib/routeParams", () => ({
  useRouteParams: () => ({ pid: "default", sid: "s1" }),
}));
vi.mock("@/lib/api", () => ({ listWorkflows: vi.fn() }));
vi.mock("@/lib/navigationBus", () => ({ emitViewChange: vi.fn() }));

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <WorkflowsList />
    </QueryClientProvider>,
  );
}

describe("WorkflowsList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState(null, "", "/projects/default/sessions/s1/workflows/_");
  });

  it("lists every designed workflow with name, scope and step count", async () => {
    vi.mocked(api.listWorkflows).mockResolvedValue({
      workflows: [
        { name: "conference-climat", scope: "Cadrer une conférence.", step_count: 3 },
        { name: "audit-marque", scope: "", step_count: 5 },
      ],
    });
    renderList();
    await waitFor(() => expect(screen.getByTestId("workflow-row-conference-climat")).toBeTruthy());
    expect(screen.getByTestId("workflow-row-audit-marque")).toBeTruthy();
    expect(screen.getByText("Cadrer une conférence.")).toBeTruthy();
  });

  it("clicking a row soft-navigates to its detail (URL change + view event, no reload)", async () => {
    vi.mocked(api.listWorkflows).mockResolvedValue({
      workflows: [{ name: "conference-climat", scope: "x", step_count: 3 }],
    });
    renderList();
    await waitFor(() => screen.getByTestId("workflow-row-conference-climat"));
    fireEvent.click(screen.getByTestId("workflow-row-conference-climat"));
    expect(window.location.pathname).toBe(
      "/projects/default/sessions/s1/workflows/conference-climat",
    );
    expect(emitViewChange).toHaveBeenCalledWith("workflows");
  });

  it("shows the designed empty state when no workflow exists", async () => {
    vi.mocked(api.listWorkflows).mockResolvedValue({ workflows: [] });
    renderList();
    await waitFor(() => expect(screen.getByTestId("no-workflow-state")).toBeTruthy());
  });
});
