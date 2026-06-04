import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DeliverablesTab, type DeliverableRow } from "../DeliverablesTab";

const mockT = (key: string) => key;

describe("<DeliverablesTab />", () => {
  const deliverables: DeliverableRow[] = [
    {
      id: "exports/wf-a/run-1/synthesis.md",
      title: "Synthesis A",
      kind: "synthesis",
      format: "md",
      workflow: "wf-a",
      created_at: "2026-05-24T15:30:00Z",
      starred: false,
    },
    {
      id: "exports/wf-a/run-1/report.pdf",
      title: "Report A",
      kind: "export",
      format: "pdf",
      workflow: "wf-a",
      created_at: "2026-05-24T15:31:00Z",
      starred: true,
    },
    {
      id: "docs/mona-doc.md",
      title: "Mona Doc",
      kind: "mona-deliverable",
      format: "md",
      created_at: "2026-05-24T15:32:00Z",
      starred: false,
    },
  ];

  it("renders deliverables flat list with correct details", () => {
    const handleOpen = vi.fn();
    const handleStar = vi.fn();

    render(
      <DeliverablesTab
        deliverables={deliverables}
        onOpen={handleOpen}
        onStar={handleStar}
        t={mockT}
      />
    );

    expect(screen.getByText("Synthesis A")).toBeDefined();
    expect(screen.getByText("Report A")).toBeDefined();
    expect(screen.getByText("Mona Doc")).toBeDefined();
  });

  it("calls onOpen when a row is clicked", () => {
    const handleOpen = vi.fn();
    const handleStar = vi.fn();

    render(
      <DeliverablesTab
        deliverables={deliverables}
        onOpen={handleOpen}
        onStar={handleStar}
        t={mockT}
      />
    );

    fireEvent.click(screen.getByText("Synthesis A"));
    expect(handleOpen).toHaveBeenCalledWith("exports/wf-a/run-1/synthesis.md");
  });

  it("calls onStar when star button is clicked", () => {
    const handleOpen = vi.fn();
    const handleStar = vi.fn();

    render(
      <DeliverablesTab
        deliverables={deliverables}
        onOpen={handleOpen}
        onStar={handleStar}
        t={mockT}
      />
    );

    const stars = screen.getAllByRole("button", { name: "sidebar:deliverables.star_aria" });
    const starBtn = stars[0];
    expect(starBtn).toBeDefined();
    if (starBtn) {
      fireEvent.click(starBtn);
    }
    expect(handleStar).toHaveBeenCalledWith("exports/wf-a/run-1/synthesis.md", true);
  });
});
