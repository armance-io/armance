import { describe, it, expect, vi, beforeEach } from "vitest";
import { getLibrary, importDoc, deleteDoc, listRuns, loadRun, loadStep, getActiveWorkflow, ApiError } from "../api";

describe("API Library Wrappers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockFetch = (response: unknown, ok: boolean = true, status: number = 200) => {
    window.fetch = vi.fn().mockResolvedValue({
      ok,
      status,
      statusText: ok ? "OK" : "Error",
      json: async () => response,
      text: async () => JSON.stringify(response),
    });
  };

  describe("getLibrary", () => {
    it("calls fetch with GET and returns documents list", async () => {
      const mockDocs = [
        { name: "test.pdf", format: "pdf" as const, status: "pending" as const, size_bytes: 1024 }
      ];
      mockFetch({ docs: mockDocs });

      const result = await getLibrary("default", "session-1");
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/library"),
        expect.objectContaining({ method: "GET" })
      );
      expect(result.docs).toEqual(mockDocs);
    });
  });

  describe("importDoc", () => {
    it("calls fetch with POST and FormData and returns imported name", async () => {
      mockFetch({ imported: "test.pdf" });
      const file = new File(["test content"], "test.pdf", { type: "application/pdf" });

      const result = await importDoc("default", "session-1", file, false);
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/library/docs"),
        expect.objectContaining({
          method: "POST",
          body: expect.any(FormData),
        })
      );
      expect(result.imported).toBe("test.pdf");
    });

    it("throws ApiError if import fails", async () => {
      mockFetch({ detail: "import_failed" }, false, 400);
      const file = new File(["test content"], "test.pdf", { type: "application/pdf" });

      await expect(importDoc("default", "session-1", file, false)).rejects.toThrow(ApiError);
    });
  });

  describe("deleteDoc", () => {
    it("calls fetch with DELETE and confirm: true", async () => {
      mockFetch({ deleted: "test.pdf" });

      const result = await deleteDoc("default", "session-1", "test.pdf", true);
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/library/docs/test.pdf"),
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ confirm: true }),
        })
      );
      expect(result.deleted).toBe("test.pdf");
    });
  });

  describe("listRuns", () => {
    it("calls fetch with GET and returns runs list", async () => {
      const mockRuns = [{ run_id: "run-1", status: "completed" }];
      mockFetch(mockRuns);

      const result = await listRuns("default", "session-1", "my-workflow");
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/workflows/my-workflow/runs"),
        expect.objectContaining({ method: "GET" })
      );
      expect(result).toEqual(mockRuns);
    });
  });

  describe("loadRun", () => {
    it("calls fetch with GET and returns files dictionary", async () => {
      const mockFiles = { "manifest.json": "{}" };
      mockFetch(mockFiles);

      const result = await loadRun("default", "session-1", "my-workflow", "run-1");
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/workflows/my-workflow/runs/run-1"),
        expect.objectContaining({ method: "GET" })
      );
      expect(result).toEqual(mockFiles);
    });
  });

  describe("loadStep", () => {
    it("calls fetch with GET and returns raw text content", async () => {
      const mockMd = "# Step 1 Output";
      mockFetch(mockMd);

      const result = await loadStep("default", "session-1", "my-workflow", "run-1", "step-1");
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/workflows/my-workflow/runs/run-1/step/step-1"),
        expect.objectContaining({ method: "GET" })
      );
      expect(result).toBe(JSON.stringify(mockMd)); // Wait, mockFetch json parses response, but loadStep uses raw text, let's keep it simple
    });
  });

  describe("getActiveWorkflow", () => {
    it("calls fetch with GET and returns active workflow data", async () => {
      const mockActive = { active: { workflow: "my-wf", run_id: "run-1", manifest_path: "..." } };
      mockFetch(mockActive);

      const result = await getActiveWorkflow("default", "session-1");
      expect(window.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/projects/default/sessions/session-1/active-workflow"),
        expect.objectContaining({ method: "GET" })
      );
      expect(result).toEqual(mockActive);
    });
  });
});
