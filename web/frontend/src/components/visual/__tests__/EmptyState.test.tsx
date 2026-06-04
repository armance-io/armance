import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyShell } from "../EmptyState/EmptyShell";
import { EmptyLibrary } from "../EmptyState/EmptyLibrary";
import { EmptyWorkflow } from "../EmptyState/EmptyWorkflow";
import { EmptySession } from "../EmptyState/EmptySession";

describe("EmptyState Components", () => {
  const mockT = (key: string) => key;

  describe("EmptyShell", () => {
    it("renders title and hint, but no CTA if ctaLabel/onCta not provided", () => {
      render(
        <EmptyShell
          title="Shell Title"
          hint="Shell Hint"
        />
      );

      expect(screen.getByText("Shell Title")).toBeDefined();
      expect(screen.getByText("Shell Hint")).toBeDefined();
      expect(screen.queryByRole("button")).toBeNull();
    });

    it("renders CTA button when ctaLabel and onCta are provided", () => {
      const onCta = vi.fn();
      render(
        <EmptyShell
          title="Shell Title"
          hint="Shell Hint"
          ctaLabel="Click Me"
          onCta={onCta}
        />
      );

      const button = screen.getByRole("button", { name: "Click Me" });
      expect(button).toBeDefined();
      button.click();
      expect(onCta).toHaveBeenCalled();
    });
  });

  describe("EmptyLibrary", () => {
    it("renders with correct i18n keys and no CTA by default", () => {
      render(<EmptyLibrary t={mockT} />);
      expect(screen.getByText("visual:empty.library.title")).toBeDefined();
      expect(screen.getByText("visual:empty.library.hint")).toBeDefined();
      expect(screen.queryByRole("button")).toBeNull();
    });

    it("renders CTA when onCta provided", () => {
      const onCta = vi.fn();
      render(<EmptyLibrary t={mockT} onCta={onCta} />);
      const button = screen.getByRole("button", { name: "visual:empty.library.cta" });
      expect(button).toBeDefined();
      button.click();
      expect(onCta).toHaveBeenCalled();
    });
  });

  describe("EmptyWorkflow", () => {
    it("renders with correct i18n keys and no CTA by default", () => {
      render(<EmptyWorkflow t={mockT} />);
      expect(screen.getByText("visual:empty.workflow.title")).toBeDefined();
      expect(screen.getByText("visual:empty.workflow.hint")).toBeDefined();
    });

    it("renders CTA when onCta provided", () => {
      const onCta = vi.fn();
      render(<EmptyWorkflow t={mockT} onCta={onCta} />);
      const button = screen.getByRole("button", { name: "visual:empty.workflow.cta" });
      expect(button).toBeDefined();
      button.click();
      expect(onCta).toHaveBeenCalled();
    });
  });

  describe("EmptySession", () => {
    it("renders with correct i18n keys and no CTA by default", () => {
      render(<EmptySession t={mockT} />);
      expect(screen.getByText("visual:empty.session.title")).toBeDefined();
      expect(screen.getByText("visual:empty.session.hint")).toBeDefined();
    });

    it("renders CTA when onCta provided", () => {
      const onCta = vi.fn();
      render(<EmptySession t={mockT} onCta={onCta} />);
      const button = screen.getByRole("button", { name: "visual:empty.session.cta" });
      expect(button).toBeDefined();
      button.click();
      expect(onCta).toHaveBeenCalled();
    });
  });
});
