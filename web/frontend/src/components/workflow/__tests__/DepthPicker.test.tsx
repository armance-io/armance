import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DepthPicker } from "../DepthPicker";

const t = (key: string) => key;

describe("DepthPicker", () => {
  it("defaults to quick depth + interactive mode on launch", () => {
    const onLaunch = vi.fn();
    render(<DepthPicker workflowName="wf" onLaunch={onLaunch} t={t} />);
    fireEvent.click(screen.getByText("workflow:picker.launch"));
    expect(onLaunch).toHaveBeenCalledWith("interactive", "quick");
  });

  it("selecting deep card + autonomous mode is reflected in the launch payload", () => {
    const onLaunch = vi.fn();
    render(<DepthPicker workflowName="wf" onLaunch={onLaunch} t={t} />);
    fireEvent.click(screen.getByText("workflow:picker.deep_title"));
    fireEvent.click(screen.getByText("workflow:picker.mode_autonomous"));
    fireEvent.click(screen.getByText("workflow:picker.launch"));
    expect(onLaunch).toHaveBeenCalledWith("autonomous", "deep");
  });

  it("depth card is keyboard-selectable via Enter", () => {
    const onLaunch = vi.fn();
    render(<DepthPicker workflowName="wf" onLaunch={onLaunch} t={t} />);
    const deepCard = screen.getByText("workflow:picker.deep_title").closest("[role=radio]")!;
    fireEvent.keyDown(deepCard, { key: "Enter" });
    fireEvent.click(screen.getByText("workflow:picker.launch"));
    expect(onLaunch).toHaveBeenCalledWith("interactive", "deep");
  });

  it("hint text switches with the selected mode", () => {
    render(<DepthPicker workflowName="wf" onLaunch={vi.fn()} t={t} />);
    expect(screen.getByText("workflow:picker.hint_interactive")).toBeTruthy();
    fireEvent.click(screen.getByText("workflow:picker.mode_autonomous"));
    expect(screen.getByText("workflow:picker.hint_autonomous")).toBeTruthy();
  });

  it("renders the workflow name as heading", () => {
    render(<DepthPicker workflowName="My Workflow" onLaunch={vi.fn()} t={t} />);
    expect(screen.getByText("My Workflow")).toBeTruthy();
  });
});
