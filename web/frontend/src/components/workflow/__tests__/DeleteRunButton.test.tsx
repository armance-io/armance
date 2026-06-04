import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeleteRunButton } from "../DeleteRunButton";

const t = (key: string) => key;

function setup(status: "running" | "completed" | "failed" | "cancelled", onDelete = vi.fn().mockResolvedValue(undefined)) {
  render(<DeleteRunButton runId="run-1" status={status} onDelete={onDelete} t={t} />);
  return { onDelete };
}

describe("DeleteRunButton", () => {
  it("disables the trigger and shows the blocked tooltip while running", () => {
    setup("running");
    const trigger = screen.getByRole("button", { name: "workflow:delete.aria" });
    expect(trigger.getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByText("workflow:delete.blocked_active")).toBeTruthy();
    // Clicking a blocked trigger does nothing — no confirm dialog appears.
    fireEvent.click(trigger);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("opens a confirm dialog, then calls onDelete with the run id on confirm", async () => {
    const { onDelete } = setup("completed");
    fireEvent.click(screen.getByRole("button", { name: "workflow:delete.aria" }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByText("workflow:delete.confirm_yes"));
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith("run-1"));
    // Returns to idle (dialog closed) after a successful delete.
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("cancel closes the dialog without deleting", () => {
    const { onDelete } = setup("failed");
    fireEvent.click(screen.getByRole("button", { name: "workflow:delete.aria" }));
    fireEvent.click(screen.getByText("workflow:delete.confirm_no"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("surfaces the error message when onDelete rejects", async () => {
    const onDelete = vi.fn().mockRejectedValue(new Error("boom"));
    setup("completed", onDelete);
    fireEvent.click(screen.getByRole("button", { name: "workflow:delete.aria" }));
    fireEvent.click(screen.getByText("workflow:delete.confirm_yes"));
    await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());
  });

  it("falls back to the generic error key for a non-Error rejection", async () => {
    const onDelete = vi.fn().mockRejectedValue("nope");
    setup("completed", onDelete);
    fireEvent.click(screen.getByRole("button", { name: "workflow:delete.aria" }));
    fireEvent.click(screen.getByText("workflow:delete.confirm_yes"));
    await waitFor(() => expect(screen.getByText("workflow:delete.error")).toBeTruthy());
  });

  it("Escape closes the confirm dialog", () => {
    setup("completed");
    fireEvent.click(screen.getByRole("button", { name: "workflow:delete.aria" }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});
