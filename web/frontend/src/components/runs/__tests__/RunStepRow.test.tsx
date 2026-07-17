import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RunStepRow, type RunStep } from "../RunStepRow";

vi.mock("@/components/library/DeliverableReader", () => ({
  DeliverableReader: ({ markdown }: { markdown: string }) => (
    <div data-testid="mock-reader">{markdown}</div>
  ),
}));

const t = (key: string) => key;

function step(overrides: Partial<RunStep> = {}): RunStep {
  return {
    id: "s1",
    role: "specialist",
    status: "completed",
    started_at: "2026-07-01T10:00:00Z",
    ended_at: "2026-07-01T10:01:00Z",
    duration_ms: 60_000,
    tokens_in: null,
    tokens_out: null,
    output: "",
    ...overrides,
  };
}

describe("RunStepRow — Creuset metadata", () => {
  it("shows a stage badge for a crucible step", () => {
    render(
      <RunStepRow step={step({ stage: "critique" })} expanded={false} onToggle={vi.fn()} t={t} />,
    );
    const badge = screen.getByTestId("run-step-stage-s1");
    expect(badge.textContent).toBe("workflow:stage.critique");
    expect(badge.getAttribute("data-stage")).toBe("critique");
  });

  it("shows no badge for standard or missing stage", () => {
    const { rerender } = render(
      <RunStepRow step={step({ stage: "standard" })} expanded={false} onToggle={vi.fn()} t={t} />,
    );
    expect(screen.queryByTestId("run-step-stage-s1")).toBeNull();
    rerender(<RunStepRow step={step()} expanded={false} onToggle={vi.fn()} t={t} />);
    expect(screen.queryByTestId("run-step-stage-s1")).toBeNull();
  });

  it("shows family in mono and the provided marker", () => {
    render(
      <RunStepRow
        step={step({ family: "google", provided: true, status: "provided" })}
        expanded={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );
    expect(screen.getByTestId("run-step-family-s1").textContent).toBe("google");
    expect(screen.getByTestId("run-step-provided-s1").textContent).toBe(
      "workflow:step.provided",
    );
  });

  it("shows cost_usd when present, tokens otherwise, nothing when neither", () => {
    const { rerender } = render(
      <RunStepRow
        step={step({ cost_usd: 0.05, tokens_in: 10, tokens_out: 10 })}
        expanded={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );
    expect(screen.getByTestId("run-step-cost-s1").textContent).toBe("$0.0500");

    rerender(
      <RunStepRow
        step={step({ tokens_in: 2000, tokens_out: 500 })}
        expanded={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );
    expect(screen.getByTestId("run-step-cost-s1").textContent).toBe("2.5k");

    rerender(<RunStepRow step={step()} expanded={false} onToggle={vi.fn()} t={t} />);
    expect(screen.queryByTestId("run-step-cost-s1")).toBeNull();
  });

  it("toggles and renders the lazily loaded output when expanded", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <RunStepRow step={step({ output: "# Out" })} expanded={false} onToggle={onToggle} t={t} />,
    );
    fireEvent.click(screen.getByTestId("run-step-toggle-s1"));
    expect(onToggle).toHaveBeenCalled();
    rerender(
      <RunStepRow step={step({ output: "# Out" })} expanded={true} onToggle={onToggle} t={t} />,
    );
    expect(screen.getByTestId("mock-reader").textContent).toBe("# Out");
  });
});
