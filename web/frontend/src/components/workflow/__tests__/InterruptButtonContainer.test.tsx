import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InterruptButtonContainer } from "../InterruptButtonContainer";
import * as api from "@/lib/api";
import * as live from "@/lib/useLiveManifest";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("@/lib/api", () => ({ stopWorkflow: vi.fn().mockResolvedValue({ cancelled: true }) }));
vi.mock("@/lib/useLiveManifest", () => ({ useLiveManifest: vi.fn() }));

// Expose the props the container computes onto a stub child.
vi.mock("../InterruptButton", () => ({
  InterruptButton: ({ status, onInterrupt, runId }: { status: string; onInterrupt: (r: string) => Promise<void>; runId: string }) => (
    <button data-testid="ib" data-status={status} onClick={() => onInterrupt(runId)}>
      interrupt
    </button>
  ),
}));

function renderC() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InterruptButtonContainer pid="default" sid="s1" workflowName="wf" runId="run-1" />
    </QueryClientProvider>
  );
}

describe("InterruptButtonContainer", () => {
  beforeEach(() => vi.clearAllMocks());

  it("derives status from the live manifest.json", () => {
    vi.mocked(live.useLiveManifest).mockReturnValue({
      data: { "manifest.json": JSON.stringify({ status: "completed" }) },
      isLoading: false, isError: false, error: null,
    } as ReturnType<typeof live.useLiveManifest>);
    renderC();
    expect(screen.getByTestId("ib").getAttribute("data-status")).toBe("completed");
  });

  it("falls back to 'running' when no manifest is present yet", () => {
    vi.mocked(live.useLiveManifest).mockReturnValue({
      data: null, isLoading: true, isError: false, error: null,
    } as ReturnType<typeof live.useLiveManifest>);
    renderC();
    expect(screen.getByTestId("ib").getAttribute("data-status")).toBe("running");
  });

  it("calls stopWorkflow on interrupt", async () => {
    vi.mocked(live.useLiveManifest).mockReturnValue({
      data: null, isLoading: false, isError: false, error: null,
    } as ReturnType<typeof live.useLiveManifest>);
    renderC();
    fireEvent.click(screen.getByTestId("ib"));
    await waitFor(() => expect(api.stopWorkflow).toHaveBeenCalledWith("default", "s1", "wf"));
  });
});
