import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RunQualityPanel, RunDerivationNote } from "../RunQualityPanel";

const t = (key: string) => key;

describe("RunQualityPanel", () => {
  it("renders the quality card with the report markdown when present", () => {
    render(
      <RunQualityPanel
        quality={{ present: true, markdown: "# Verdict\n\nAccepted after one revision." }}
        t={t}
      />,
    );
    const panel = screen.getByTestId("run-quality-panel");
    expect(panel).toBeDefined();
    expect(screen.getByText("runs:detail.quality_title")).toBeDefined();
    expect(screen.getByText("Verdict")).toBeDefined();
    expect(screen.getByText("Accepted after one revision.")).toBeDefined();
  });

  it("renders nothing when the report is absent", () => {
    render(<RunQualityPanel quality={{ present: false, markdown: null }} t={t} />);
    expect(screen.queryByTestId("run-quality-panel")).toBeNull();
  });

  it("renders nothing when present is true but markdown is null (no fabrication)", () => {
    render(<RunQualityPanel quality={{ present: true, markdown: null }} t={t} />);
    expect(screen.queryByTestId("run-quality-panel")).toBeNull();
  });
});

describe("RunDerivationNote", () => {
  const derived = [
    {
      run_id: "run-parent-1",
      overrides: [
        { step: "B", source: "b.md" },
        { step: "C", source: "c.md" },
      ],
    },
  ];

  it("shows the parent run id and its overridden steps", () => {
    render(<RunDerivationNote derivedFrom={derived} onOpenRun={vi.fn()} t={t} />);
    expect(screen.getByTestId("run-derivation-note")).toBeDefined();
    expect(screen.getByTestId("run-parent-link-run-parent-1").textContent).toBe(
      "run-parent-1",
    );
    expect(screen.getByTestId("run-overrides-run-parent-1").textContent).toBe(
      "(B, C)",
    );
  });

  it("navigates to the parent run on click", () => {
    const onOpenRun = vi.fn();
    render(<RunDerivationNote derivedFrom={derived} onOpenRun={onOpenRun} t={t} />);
    fireEvent.click(screen.getByTestId("run-parent-link-run-parent-1"));
    expect(onOpenRun).toHaveBeenCalledWith("run-parent-1");
  });

  it("renders nothing for an empty derivation list", () => {
    render(<RunDerivationNote derivedFrom={[]} onOpenRun={vi.fn()} t={t} />);
    expect(screen.queryByTestId("run-derivation-note")).toBeNull();
  });
});
