import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InterruptButton } from "../InterruptButton";

const t = (key: string) => key;

function setup(status: "running" | "completed" | "failed" | "cancelled", onInterrupt = vi.fn().mockResolvedValue(undefined)) {
  render(<InterruptButton runId="run-1" status={status} onInterrupt={onInterrupt} t={t} />);
  return { onInterrupt };
}

describe("InterruptButton", () => {
  it("only enables the trigger while the run is running", () => {
    setup("completed");
    fireEvent.click(screen.getByRole("button", { name: "workflow:interrupt.label" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("opens confirm, then calls onInterrupt with the run id", async () => {
    const { onInterrupt } = setup("running");
    fireEvent.click(screen.getByRole("button", { name: "workflow:interrupt.label" }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByTestId("interrupt-confirm"));
    await waitFor(() => expect(onInterrupt).toHaveBeenCalledWith("run-1"));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("cancel closes the dialog without interrupting", () => {
    const { onInterrupt } = setup("running");
    fireEvent.click(screen.getByRole("button", { name: "workflow:interrupt.label" }));
    fireEvent.click(screen.getByTestId("interrupt-cancel"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(onInterrupt).not.toHaveBeenCalled();
  });

  it("surfaces the rejection error message", async () => {
    const onInterrupt = vi.fn().mockRejectedValue(new Error("kaboom"));
    setup("running", onInterrupt);
    fireEvent.click(screen.getByRole("button", { name: "workflow:interrupt.label" }));
    fireEvent.click(screen.getByTestId("interrupt-confirm"));
    await waitFor(() => expect(screen.getByText("kaboom")).toBeTruthy());
  });

  it("falls back to the generic error key for a non-Error rejection", async () => {
    const onInterrupt = vi.fn().mockRejectedValue("x");
    setup("running", onInterrupt);
    fireEvent.click(screen.getByRole("button", { name: "workflow:interrupt.label" }));
    fireEvent.click(screen.getByTestId("interrupt-confirm"));
    await waitFor(() => expect(screen.getByText("workflow:interrupt.error")).toBeTruthy());
  });
});
