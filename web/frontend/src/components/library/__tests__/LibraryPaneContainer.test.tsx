import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LibraryPaneContainer } from "../LibraryPaneContainer";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/lib/api";

// Mock translation
const mockT = (key: string) => key;
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT }),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  getLibrary: vi.fn(),
  importDoc: vi.fn(),
  deleteDoc: vi.fn(),
  submitTurn: vi.fn(),
}));

// Mock LibraryPane to easily trigger callbacks and test container integration
vi.mock("../LibraryPane", () => ({
  LibraryPane: vi.fn(({ onImport, onDelete, onIndex, onLoad, onUnload, onUnindex, onIndexAll }) => {
    return (
      <div data-testid="mock-pane">
        <button data-testid="btn-import" onClick={() => onImport(new File([], "test.txt"))} />
        <button data-testid="btn-delete" onClick={() => onDelete("test.pdf")} />
        <button data-testid="btn-index" onClick={() => onIndex("test.pdf")} />
        <button data-testid="btn-load" onClick={() => onLoad("test.pdf")} />
        <button data-testid="btn-unload" onClick={() => onUnload("test.pdf")} />
        <button data-testid="btn-unindex" onClick={() => onUnindex("test.pdf")} />
        <button data-testid="btn-index-all" onClick={() => onIndexAll()} />
      </div>
    );
  }),
}));

describe("LibraryPaneContainer", () => {
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
        <LibraryPaneContainer pid="default" sid="session-1" />
      </QueryClientProvider>
    );
  };

  it("renders loading state initially", () => {
    vi.mocked(api.getLibrary).mockReturnValue(new Promise(() => {})); // pending
    renderComponent();
    expect(screen.getByText("app:loading")).toBeDefined();
  });

  it("renders error state when fetch fails", async () => {
    vi.mocked(api.getLibrary).mockRejectedValue(new Error("Failed"));
    renderComponent();
    expect(await screen.findByText("common:error")).toBeDefined();
  });

  it("triggers api wrappers and refetches when callbacks are executed", async () => {
    const mockDocs = [{ name: "test.pdf", format: "pdf" as const, status: "pending" as const, size_bytes: 1024 }];
    vi.mocked(api.getLibrary).mockResolvedValue({ docs: mockDocs, total_feuillets: 0, doc_count: mockDocs.length });
    vi.mocked(api.importDoc).mockResolvedValue({ imported: "test.txt" });
    vi.mocked(api.deleteDoc).mockResolvedValue({ deleted: "test.pdf" });
    vi.mocked(api.submitTurn).mockResolvedValue({ ack: true });

    renderComponent();

    const pane = await screen.findByTestId("mock-pane");
    expect(pane).toBeDefined();

    // 1. Test onImport
    fireEvent.click(screen.getByTestId("btn-import"));
    await waitFor(() => {
      expect(api.importDoc).toHaveBeenCalledWith("default", "session-1", expect.any(File), false);
    });

    // 2. Test onDelete
    fireEvent.click(screen.getByTestId("btn-delete"));
    await waitFor(() => {
      expect(api.deleteDoc).toHaveBeenCalledWith("default", "session-1", "test.pdf", true);
    });

    // 3. Test onIndex
    fireEvent.click(screen.getByTestId("btn-index"));
    await waitFor(() => {
      expect(api.submitTurn).toHaveBeenCalledWith("default", "session-1", "/library-index test.pdf");
    });

    // 4. Test onLoad
    fireEvent.click(screen.getByTestId("btn-load"));
    await waitFor(() => {
      expect(api.submitTurn).toHaveBeenCalledWith("default", "session-1", "/library-load test.pdf");
    });

    // 5. Test onUnload
    fireEvent.click(screen.getByTestId("btn-unload"));
    await waitFor(() => {
      expect(api.submitTurn).toHaveBeenCalledWith("default", "session-1", "/library-unload test.pdf");
    });

    // 6. Test onUnindex
    fireEvent.click(screen.getByTestId("btn-unindex"));
    await waitFor(() => {
      expect(api.submitTurn).toHaveBeenCalledWith("default", "session-1", "/library-unindex test.pdf");
    });

    // 7. Test onIndexAll
    fireEvent.click(screen.getByTestId("btn-index-all"));
    await waitFor(() => {
      expect(api.submitTurn).toHaveBeenCalledWith("default", "session-1", "/library-index");
    });

    // Refetching is triggered after callbacks (import/delete refetch
    // immediately; index/load defer + poll), so it is called more than once.
    await waitFor(() => {
      expect((api.getLibrary as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBeGreaterThan(1);
    });
  });
});
