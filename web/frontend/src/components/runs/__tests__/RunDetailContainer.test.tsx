import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RunDetailContainer } from "../RunDetailContainer";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { RunDetailResponse } from "@/lib/api";

// Mock translation
const mockT = (key: string) => key;
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT }),
}));

// Mock router (derived_from parent-run navigation)
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  loadRun: vi.fn(),
  loadRunDetail: vi.fn(),
  loadStep: vi.fn(),
}));

// Mock RunDetail to observe the mapped view model
vi.mock("../RunDetail", () => ({
  RunDetail: vi.fn(
    ({
      run,
      onStepExpand,
      onOpenRun,
    }: {
      run: import("../RunDetail").Run;
      onStepExpand: (stepId: string) => Promise<void>;
      onOpenRun?: (runId: string) => void;
    }) => {
      return (
        <div data-testid="mock-run-detail">
          <span data-testid="run-id">{run.run_id}</span>
          <span data-testid="workflow">{run.workflow}</span>
          <span data-testid="quality-present">
            {String(run.quality?.present ?? false)}
          </span>
          <span data-testid="derived-count">
            {String(run.derived_from?.length ?? 0)}
          </span>
          <span data-testid="cost">{String(run.cost_usd)}</span>
          {run.steps.map((step) => (
            <div key={step.id} data-testid={`step-${step.id}`}>
              <span data-testid={`step-stage-${step.id}`}>{step.stage ?? ""}</span>
              <span data-testid={`step-family-${step.id}`}>{step.family ?? ""}</span>
              <span data-testid={`step-provided-${step.id}`}>
                {String(step.provided ?? false)}
              </span>
              <span data-testid={`step-output-${step.id}`}>{step.output}</span>
              <button
                data-testid={`btn-expand-${step.id}`}
                onClick={() => onStepExpand(step.id)}
              />
            </div>
          ))}
          <button data-testid="btn-open-parent" onClick={() => onOpenRun?.("run-0")} />
        </div>
      );
    },
  ),
}));

const DETAIL: RunDetailResponse = {
  run_id: "run-1",
  workflow: "my-workflow",
  status: "completed",
  started_at: "2026-05-29T15:00:00Z",
  ended_at: "2026-05-29T15:05:00Z",
  derived_from: [{ run_id: "run-0", overrides: [{ step: "B", source: "b.md" }] }],
  quality: { present: true, markdown: "# Quality" },
  steps: [
    {
      id: "draft-a",
      status: "completed",
      stage: "draft",
      family: "anthropic",
      agent: "Serge",
      duration_ms: 1200,
      tokens_in: 100,
      tokens_out: 200,
      cost_usd: 0.01,
      provided: false,
      error: null,
    },
    {
      id: "B",
      status: "provided",
      stage: null,
      family: null,
      agent: null,
      duration_ms: null,
      tokens_in: null,
      tokens_out: null,
      cost_usd: null,
      provided: true,
      error: null,
    },
  ],
};

describe("RunDetailContainer", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // clearAllMocks, not restoreAllMocks: module-factory vi.fn() mocks keep
    // their call history across tests otherwise (restore only affects spies),
    // and the not-called assertion below would see the previous test's call.
    vi.clearAllMocks();
    mockPush.mockReset();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <RunDetailContainer
          pid="default"
          sid="session-1"
          workflowName="my-workflow"
          runId="run-1"
        />
      </QueryClientProvider>,
    );
  };

  it("renders loading state initially", () => {
    vi.mocked(api.loadRunDetail).mockReturnValue(new Promise(() => {})); // pending
    renderComponent();
    expect(screen.getByText("app:loading")).toBeDefined();
  });

  it("renders error state when both detail and fallback fail", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(null);
    vi.mocked(api.loadRun).mockRejectedValue(new Error("Failed"));
    renderComponent();
    expect(await screen.findByText("common:error")).toBeDefined();
  });

  it("maps the structured /detail payload (stage, family, provided, quality, derived_from)", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(DETAIL);
    renderComponent();

    await screen.findByTestId("mock-run-detail");
    expect(screen.getByTestId("run-id").textContent).toBe("run-1");
    expect(screen.getByTestId("quality-present").textContent).toBe("true");
    expect(screen.getByTestId("derived-count").textContent).toBe("1");
    expect(screen.getByTestId("step-stage-draft-a").textContent).toBe("draft");
    expect(screen.getByTestId("step-family-draft-a").textContent).toBe("anthropic");
    expect(screen.getByTestId("step-provided-B").textContent).toBe("true");
    // Totals summed only from steps that HAVE values — nothing invented.
    expect(screen.getByTestId("cost").textContent).toBe("0.01");
    // The raw-file endpoint must not be touched on the structured path.
    expect(api.loadRun).not.toHaveBeenCalled();
  });

  it("navigates to the parent run via onOpenRun", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(DETAIL);
    renderComponent();
    await screen.findByTestId("mock-run-detail");
    fireEvent.click(screen.getByTestId("btn-open-parent"));
    expect(mockPush).toHaveBeenCalledWith(
      "/projects/default/sessions/session-1/workflows/my-workflow/runs/run-0",
    );
  });

  it("falls back to the raw manifest when /detail is unavailable (404)", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(null); // 404 → null
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "completed",
      started_at: "2026-05-29T15:00:00Z",
      steps: [{ id: "step-1", status: "completed", started_at: "2026-05-29T15:01:00Z" }],
      totals: { tokens_in: 100, tokens_out: 200, cost_usd: 0.005 },
    };
    vi.mocked(api.loadRun).mockResolvedValue({
      "manifest.json": JSON.stringify(mockManifest),
    });
    vi.mocked(api.loadStep).mockResolvedValue("# Step 1 Output Markdown");

    renderComponent();

    const detail = await screen.findByTestId("mock-run-detail");
    expect(detail).toBeDefined();
    expect(screen.getByTestId("run-id").textContent).toBe("run-1");
    expect(screen.getByTestId("workflow").textContent).toBe("my-workflow");
    expect(screen.getByTestId("quality-present").textContent).toBe("false");
    expect(screen.getByTestId("step-output-step-1").textContent).toBe("");

    // Lazy step expand still works on the fallback path.
    fireEvent.click(screen.getByTestId("btn-expand-step-1"));
    await waitFor(() => {
      expect(api.loadStep).toHaveBeenCalledWith(
        "default",
        "session-1",
        "my-workflow",
        "run-1",
        "step-1",
      );
    });
    expect(await screen.findByText("# Step 1 Output Markdown")).toBeDefined();
  });

  it("gracefully catches JSON parse errors in manifest.json", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(null);
    vi.mocked(api.loadRun).mockResolvedValue({ "manifest.json": "{ invalid json" });
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    renderComponent();

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining("Failed to parse run manifest"),
        expect.any(SyntaxError),
      );
    });
  });

  it("gracefully catches step loading network errors", async () => {
    vi.mocked(api.loadRunDetail).mockResolvedValue(DETAIL);
    vi.mocked(api.loadStep).mockRejectedValue(new Error("Network Error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    renderComponent();
    await screen.findByTestId("mock-run-detail");
    fireEvent.click(screen.getByTestId("btn-expand-draft-a"));

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining("Failed to load step markdown"),
        expect.any(Error),
      );
    });
  });
});
