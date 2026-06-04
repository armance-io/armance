import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeliverablesTabContainer } from "../DeliverablesTabContainer";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "@/lib/api";

const mockT = (key: string) => key;
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

vi.mock("../DeliverablesTab", () => ({
  DeliverablesTab: vi.fn(({ deliverables, onOpen, onStar }) => (
    <div data-testid="mock-tab">
      <button data-testid="btn-open" onClick={() => onOpen("exports/wf/run-1/synthesis.md")} />
      <button data-testid="btn-star" onClick={() => onStar("exports/wf/run-1/synthesis.md", true)} />
      <div data-testid="count">{deliverables.length}</div>
    </div>
  )),
}));

describe("DeliverablesTabContainer", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  const renderComponent = (onOpen: (id: string) => void) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <DeliverablesTabContainer pid="default" sid="session-1" onOpen={onOpen} />
      </QueryClientProvider>
    );
  };

  it("fetches deliverables and renders list count", async () => {
    const mockData = [
      { id: "exports/wf/run-1/synthesis.md", title: "Synthesis", kind: "synthesis", format: "md", created_at: "2026-05-24T15:30:00Z", starred: false }
    ];
    vi.mocked(api.get).mockResolvedValue(mockData);

    renderComponent(vi.fn());

    await waitFor(() => {
      expect(screen.getByTestId("count").textContent).toBe("1");
    });
  });

  it("calls patch API on star toggle", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    vi.mocked(api.patch).mockResolvedValue({});

    renderComponent(vi.fn());

    fireEvent.click(screen.getByTestId("btn-star"));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        "/projects/default/sessions/session-1/deliverables/exports/wf/run-1/synthesis.md/star",
        { starred: true }
      );
    });
  });
});
