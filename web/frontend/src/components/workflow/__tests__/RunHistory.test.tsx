import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RunHistory } from "../RunHistory";

const t = (key: string) => key;

const NOW = new Date("2026-05-29T12:00:00Z").getTime();

function run(overrides: Partial<Parameters<typeof RunHistory>[0]["runs"][number]> = {}) {
  return {
    run_id: "run-1",
    status: "completed" as const,
    started_at: new Date(NOW - 5 * 60_000).toISOString(),
    ended_at: new Date(NOW).toISOString(),
    duration_ms: 90_000,
    tokens_total: 2500,
    ...overrides,
  };
}

describe("RunHistory", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the empty state when there are no runs", () => {
    render(<RunHistory runs={[]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("workflow:history.empty")).toBeTruthy();
  });

  it("renders one row per run and fires onOpen with the run id when clicked", () => {
    const onOpen = vi.fn();
    render(
      <RunHistory runs={[run(), run({ run_id: "run-2" })]} onOpen={onOpen} onDelete={vi.fn()} t={t} />
    );
    const rows = screen.getAllByRole("button", { name: /run run-/ });
    expect(rows).toHaveLength(2);
    fireEvent.click(rows[0]!);
    expect(onOpen).toHaveBeenCalledWith("run-1");
  });

  it("opens via keyboard (Enter) on a focused row", () => {
    const onOpen = vi.fn();
    render(<RunHistory runs={[run()]} onOpen={onOpen} onDelete={vi.fn()} t={t} />);
    fireEvent.keyDown(screen.getByRole("button", { name: /run run-1/ }), { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith("run-1");
  });

  it("formats time-ago in minutes / hours / days buckets", () => {
    const { rerender } = render(
      <RunHistory runs={[run({ started_at: new Date(NOW - 5 * 60_000).toISOString() })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />
    );
    expect(screen.getByText("workflow:history.time_mins")).toBeTruthy();
    rerender(<RunHistory runs={[run({ started_at: new Date(NOW - 3 * 3_600_000).toISOString() })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("workflow:history.time_hours")).toBeTruthy();
    rerender(<RunHistory runs={[run({ started_at: new Date(NOW - 3 * 86_400_000).toISOString() })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("workflow:history.time_days")).toBeTruthy();
  });

  it("formats a duration over an hour as HH:MM", () => {
    render(<RunHistory runs={[run({ duration_ms: 3_900_000 })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("01:05")).toBeTruthy();
  });

  it("formats a 90s duration as 01:30", () => {
    render(<RunHistory runs={[run({ duration_ms: 90_000 })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("01:30")).toBeTruthy();
  });

  it("renders --:-- for a null duration", () => {
    render(<RunHistory runs={[run({ duration_ms: null })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("--:--")).toBeTruthy();
  });

  it("formats 2500 tokens as 2.5k", () => {
    render(<RunHistory runs={[run({ tokens_total: 2500 })]} onOpen={vi.fn()} onDelete={vi.fn()} t={t} />);
    expect(screen.getByText("2.5k")).toBeTruthy();
  });
});
