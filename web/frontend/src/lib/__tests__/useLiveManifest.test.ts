import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLiveManifest } from "../useLiveManifest";
import { loadRun } from "../api";

vi.mock("../api", () => ({
  loadRun: vi.fn(),
}));

describe("useLiveManifest", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls every second while status is running", async () => {
    const mockLoadRun = vi.mocked(loadRun);
    
    // First call returns running
    mockLoadRun.mockResolvedValueOnce({
      "manifest.json": JSON.stringify({ status: "running" }),
    });
    // Second call returns running
    mockLoadRun.mockResolvedValueOnce({
      "manifest.json": JSON.stringify({ status: "running" }),
    });
    // Third call returns completed
    mockLoadRun.mockResolvedValueOnce({
      "manifest.json": JSON.stringify({ status: "completed" }),
    });

    const { result } = renderHook(() =>
      useLiveManifest("pid-1", "sid-1", "workflow-1", "run-1")
    );

    // Initial load is loading
    expect(result.current.isLoading).toBe(true);

    // Flush the initial microtasks (the first poll() call)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toEqual({
      "manifest.json": '{"status":"running"}',
    });
    expect(mockLoadRun).toHaveBeenCalledTimes(1);

    // Advance time by 1 second to trigger the first interval tick
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(mockLoadRun).toHaveBeenCalledTimes(2);
    expect(result.current.data).toEqual({
      "manifest.json": '{"status":"running"}',
    });

    // Advance time by another 1 second -> should transition to completed and stop polling
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(mockLoadRun).toHaveBeenCalledTimes(3);
    expect(result.current.data).toEqual({
      "manifest.json": '{"status":"completed"}',
    });

    // Advance time by 5 more seconds -> no more calls should happen because it's completed
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockLoadRun).toHaveBeenCalledTimes(3);
  });

  it("handles errors and updates error state", async () => {
    const mockLoadRun = vi.mocked(loadRun);
    mockLoadRun.mockRejectedValueOnce(new Error("Network Error"));

    const { result } = renderHook(() =>
      useLiveManifest("pid-1", "sid-1", "workflow-1", "run-1")
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBe(true);
    expect(result.current.error).toBeInstanceOf(Error);
    expect((result.current.error as Error).message).toBe("Network Error");
  });

  it("stops polling on unmount", async () => {
    const mockLoadRun = vi.mocked(loadRun);
    mockLoadRun.mockResolvedValue({
      "manifest.json": JSON.stringify({ status: "running" }),
    });

    const { unmount } = renderHook(() =>
      useLiveManifest("pid-1", "sid-1", "workflow-1", "run-1")
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockLoadRun).toHaveBeenCalledTimes(1);

    unmount();

    // Advance time -> no more calls should be made
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(mockLoadRun).toHaveBeenCalledTimes(1);
  });
});
