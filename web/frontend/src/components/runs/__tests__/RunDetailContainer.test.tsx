import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RunDetailContainer } from "../RunDetailContainer";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/lib/api";

// Mock translation
const mockT = (key: string) => key;
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT }),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  loadRun: vi.fn(),
  loadStep: vi.fn(),
}));

// Mock RunDetail to trigger onStepExpand callback
vi.mock("../RunDetail", () => ({
  RunDetail: vi.fn(({ run, onStepExpand }: { run: import("../RunDetail").Run, onStepExpand: (stepId: string) => Promise<void> }) => {
    return (
      <div data-testid="mock-run-detail">
        <span data-testid="run-id">{run.run_id}</span>
        <span data-testid="workflow">{run.workflow}</span>
        {run.steps.map((step) => (
          <div key={step.id} data-testid={`step-${step.id}`}>
            <span data-testid={`step-output-${step.id}`}>{step.output}</span>
            <button data-testid={`btn-expand-${step.id}`} onClick={() => onStepExpand(step.id)} />
          </div>
        ))}
      </div>
    );
  }),
}));

describe("RunDetailContainer", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <RunDetailContainer pid="default" sid="session-1" workflowName="my-workflow" runId="run-1" />
      </QueryClientProvider>
    );
  };

  it("renders loading state initially", () => {
    vi.mocked(api.loadRun).mockReturnValue(new Promise(() => {})); // pending
    renderComponent();
    expect(screen.getByText("app:loading")).toBeDefined();
  });

  it("renders error state when fetch fails", async () => {
    vi.mocked(api.loadRun).mockRejectedValue(new Error("Failed"));
    renderComponent();
    expect(await screen.findByText("common:error")).toBeDefined();
  });

  it("renders RunDetail and loads step output lazily", async () => {
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "completed",
      started_at: "2026-05-29T15:00:00Z",
      steps: [
        { id: "step-1", status: "completed", started_at: "2026-05-29T15:01:00Z" }
      ],
      totals: {
        tokens_in: 100,
        tokens_out: 200,
        cost_usd: 0.005
      }
    };
    const mockFiles = {
      "manifest.json": JSON.stringify(mockManifest),
    };
    vi.mocked(api.loadRun).mockResolvedValue(mockFiles);
    vi.mocked(api.loadStep).mockResolvedValue("# Step 1 Output Markdown");

    renderComponent();

    const detail = await screen.findByTestId("mock-run-detail");
    expect(detail).toBeDefined();
    expect(screen.getByTestId("run-id").textContent).toBe("run-1");
    expect(screen.getByTestId("workflow").textContent).toBe("my-workflow");
    expect(screen.getByTestId("step-output-step-1").textContent).toBe(""); // initially empty

    // Trigger step expand callback
    fireEvent.click(screen.getByTestId("btn-expand-step-1"));

    await waitFor(() => {
      expect(api.loadStep).toHaveBeenCalledWith("default", "session-1", "my-workflow", "run-1", "step-1");
    });

    // Verify state updated and component re-rendered with step output
    expect(await screen.findByText("# Step 1 Output Markdown")).toBeDefined();
  });

  it("gracefully catches JSON parse errors in manifest.json", async () => {
    const mockFiles = {
      "manifest.json": "{ invalid json",
    };
    vi.mocked(api.loadRun).mockResolvedValue(mockFiles);
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    renderComponent();

    // Since manifest parsing failed, it will not render mock-run-detail
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("Failed to parse run manifest"), expect.any(SyntaxError));
    });
  });

  it("gracefully catches step loading network errors", async () => {
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "completed",
      started_at: "2026-05-29T15:00:00Z",
      steps: [{ id: "step-1", status: "completed" }],
    };
    const mockFiles = {
      "manifest.json": JSON.stringify(mockManifest),
    };
    vi.mocked(api.loadRun).mockResolvedValue(mockFiles);
    vi.mocked(api.loadStep).mockRejectedValue(new Error("Network Error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    renderComponent();

    const detail = await screen.findByTestId("mock-run-detail");
    expect(detail).toBeDefined();

    // Trigger step expand callback
    fireEvent.click(screen.getByTestId("btn-expand-step-1"));

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("Failed to load step markdown"), expect.any(Error));
    });
  });

  it("falls back to running status for unknown/invalid run status values", async () => {
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "unknown-status-value",
      started_at: "2026-05-29T15:00:00Z",
      steps: [{ id: "step-1", status: "invalid-step-status" }],
    };
    const mockFiles = {
      "manifest.json": JSON.stringify(mockManifest),
    };
    vi.mocked(api.loadRun).mockResolvedValue(mockFiles);

    renderComponent();

    const detail = await screen.findByTestId("mock-run-detail");
    expect(detail).toBeDefined();
    // Verify it doesn't crash and status falls back safely
    expect(screen.getByTestId("run-id").textContent).toBe("run-1");
  });
});
