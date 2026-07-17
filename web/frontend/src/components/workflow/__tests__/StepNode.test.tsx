import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { StepNode, type StepNodeData } from "../StepNode";

const t = (key: string) => key;

function renderNode(data: Partial<StepNodeData> = {}) {
  const full: StepNodeData = {
    step_id: "s1",
    role: "specialist",
    status: "completed",
    t,
    ...data,
  };
  return render(
    <ReactFlowProvider>
      <StepNode data={full} />
    </ReactFlowProvider>,
  );
}

describe("StepNode — Creuset stage badge", () => {
  it.each(["draft", "critique", "synthesis", "gate"] as const)(
    "shows an i18n'd %s badge",
    (stage) => {
      renderNode({ stage });
      const badge = screen.getByTestId("stage-badge-s1");
      expect(badge.textContent).toBe(`workflow:stage.${stage}`);
      expect(badge.getAttribute("data-stage")).toBe(stage);
    },
  );

  it("shows NO badge for a standard step", () => {
    renderNode({ stage: "standard" });
    expect(screen.queryByTestId("stage-badge-s1")).toBeNull();
  });

  it("shows NO badge when stage is absent (legacy runs)", () => {
    renderNode({});
    expect(screen.queryByTestId("stage-badge-s1")).toBeNull();
  });
});

describe("StepNode — cost line (never invented)", () => {
  it("shows cost_usd when present", () => {
    renderNode({ cost_usd: 0.0421, tokens_in: 10, tokens_out: 20 });
    expect(screen.getByTestId("step-cost-s1").textContent).toBe("$0.0421");
  });

  it("falls back to tokens when cost is missing", () => {
    renderNode({ cost_usd: null, tokens_in: 1500, tokens_out: 1000 });
    expect(screen.getByTestId("step-cost-s1").textContent).toBe("2.5k");
  });

  it("shows nothing when neither exists", () => {
    renderNode({});
    expect(screen.queryByTestId("step-cost-s1")).toBeNull();
  });
});

describe("StepNode — family and provided", () => {
  it("renders the family in discreet mono", () => {
    renderNode({ family: "anthropic" });
    expect(screen.getByTestId("step-family-s1").textContent).toBe("anthropic");
  });

  it("marks a hand-provided step", () => {
    renderNode({ status: "provided", provided: true });
    expect(screen.getByTestId("step-provided-s1").textContent).toBe(
      "workflow:step.provided",
    );
  });

  it("omits family and provided when absent", () => {
    renderNode({});
    expect(screen.queryByTestId("step-family-s1")).toBeNull();
    expect(screen.queryByTestId("step-provided-s1")).toBeNull();
  });
});
