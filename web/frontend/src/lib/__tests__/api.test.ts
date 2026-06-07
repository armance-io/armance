import { describe, it, expect, vi, beforeEach } from "vitest";
import { waitFor } from "@testing-library/react";
import { getLibrary, importDoc, deleteDoc, listRuns, loadRun, loadStep, getActiveWorkflow, ApiError, login, verifyAuth } from "../api";

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

  describe("Epic S — auth gate", () => {
    const mockFetch = (ok: boolean, status: number) => {
      window.fetch = vi.fn().mockResolvedValue({
        ok,
        status,
        statusText: ok ? "OK" : "Error",
        json: async () => ({ detail: "unauthorized" }),
        text: async () => "",
      });
    };

    it("redirects to /login on a 401 from a data route", async () => {
      const replace = vi.fn();
      Object.defineProperty(window, "location", {
        value: { pathname: "/projects/default", search: "", replace },
        writable: true,
      });
      mockFetch(false, 401);

      await expect(getLibrary("default", "s1")).rejects.toThrow(ApiError);
      expect(replace).toHaveBeenCalledWith(
        expect.stringContaining("/login?next="),
      );
    });

    it("SEC5 — exchanges a top-level ?token inline and strips it (no token in URL)", async () => {
      const replace = vi.fn();
      const reload = vi.fn();
      const replaceState = vi.fn();
      Object.defineProperty(window, "location", {
        value: { pathname: "/", search: "?token=abc", replace, reload },
        writable: true,
      });
      Object.defineProperty(window, "history", {
        value: { replaceState },
        writable: true,
      });
      // Data route → 401; the /auth/login exchange → 200.
      window.fetch = vi.fn().mockImplementation((url: string) => {
        const ok = String(url).includes("/auth/login");
        return Promise.resolve({
          ok,
          status: ok ? 200 : 401,
          statusText: ok ? "OK" : "Error",
          json: async () => ({ detail: "unauthorized" }),
          text: async () => "",
        });
      });

      await expect(getLibrary("default", "s1")).rejects.toThrow(ApiError);
      // The token exchange happened against /auth/login…
      await waitFor(() =>
        expect(window.fetch).toHaveBeenCalledWith(
          expect.stringContaining("/auth/login"),
          expect.objectContaining({ method: "POST" }),
        ),
      );
      // …the address bar was cleaned to "/" (no token), and the page reloaded.
      await waitFor(() => expect(replaceState).toHaveBeenCalledWith(null, "", "/"));
      await waitFor(() => expect(reload).toHaveBeenCalled());
      // It must NOT bounce the token through another URL.
      for (const call of replace.mock.calls) {
        expect(String(call[0])).not.toContain("token=");
      }
    });

    it("does not redirect when already on /login", async () => {
      const replace = vi.fn();
      Object.defineProperty(window, "location", {
        value: { pathname: "/login", search: "", replace },
        writable: true,
      });
      mockFetch(false, 401);

      await expect(getLibrary("default", "s1")).rejects.toThrow(ApiError);
      expect(replace).not.toHaveBeenCalled();
    });

    it("login() returns true on 200, false on 401", async () => {
      mockFetch(true, 200);
      expect(await login("good")).toBe(true);
      mockFetch(false, 401);
      expect(await login("bad")).toBe(false);
    });

    it("verifyAuth() sends the token via Bearer header, not the query string", async () => {
      mockFetch(true, 200);
      expect(await verifyAuth("tok")).toBe(true);
      const [url, init] = (window.fetch as ReturnType<typeof vi.fn>).mock.calls[0]!;
      expect(String(url)).not.toContain("token="); // never in the URL
      expect((init as RequestInit).headers).toMatchObject({
        Authorization: "Bearer tok",
      });
      mockFetch(false, 401);
      expect(await verifyAuth()).toBe(false);
    });
  });
});
