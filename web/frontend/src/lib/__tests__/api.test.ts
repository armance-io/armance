import { describe, it, expect, vi, beforeEach } from "vitest";
import { getLibrary, importDoc, deleteDoc, ApiError } from "../api";

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
});
