import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RunHistoryContainer } from "../RunHistoryContainer";
import * as api from "@/lib/api";

const push = vi.fn();
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({
  listRuns: vi.fn(),
  deleteRun: vi.fn().mockResolvedValue({ deleted: true }),
}));

vi.mock("../RunHistory", () => ({
  RunHistory: ({ runs, onOpen, onDelete }: { runs: { run_id: string }[]; onOpen: (r: string) => void; onDelete: (r: string) => Promise<void> }) => (
    <div>
      <span data-testid="count">{runs.length}</span>
      {runs.map((r) => (
        <div key={r.run_id}>
          <button data-testid={`open-${r.run_id}`} onClick={() => onOpen(r.run_id)} />
          <button data-testid={`del-${r.run_id}`} onClick={() => onDelete(r.run_id)} />
        </div>
      ))}
    </div>
  ),
}));

function renderC() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunHistoryContainer pid="default" sid="s1" workflowName="wf" />
    </QueryClientProvider>
  );
}

describe("RunHistoryContainer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    push.mockClear();
  });

  it("maps the listRuns response into RunHistory rows", async () => {
    vi.mocked(api.listRuns).mockResolvedValue([
      { run_id: "run-1" }, { run_id: "run-2" },
    ] as Awaited<ReturnType<typeof api.listRuns>>);
    renderC();
    await waitFor(() => expect(screen.getByTestId("count").textContent).toBe("2"));
  });

  it("routes to the run detail page on open", async () => {
    vi.mocked(api.listRuns).mockResolvedValue([{ run_id: "run-1" }] as Awaited<ReturnType<typeof api.listRuns>>);
    renderC();
    await waitFor(() => screen.getByTestId("open-run-1"));
    fireEvent.click(screen.getByTestId("open-run-1"));
    expect(push).toHaveBeenCalledWith(
      "/projects/default/sessions/s1/workflows/wf/runs/run-1"
    );
  });

  it("calls deleteRun on delete", async () => {
    vi.mocked(api.listRuns).mockResolvedValue([{ run_id: "run-1" }] as Awaited<ReturnType<typeof api.listRuns>>);
    renderC();
    await waitFor(() => screen.getByTestId("del-run-1"));
    fireEvent.click(screen.getByTestId("del-run-1"));
    await waitFor(() => expect(api.deleteRun).toHaveBeenCalledWith("default", "s1", "wf", "run-1"));
  });
});
