import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Fleuron } from "@/components/visual/Fleuron";

describe("<Fleuron />", () => {
  it("renders the ❦ glyph flanked by two hairline rules", () => {
    const { container } = render(<Fleuron />);

    const root = container.firstElementChild as HTMLElement;
    expect(root).toBeTruthy();
    expect(root.getAttribute("role")).toBe("separator");
    expect(root.getAttribute("aria-hidden")).toBe("true");
    expect(root.textContent).toBe("❦");

    const spans = Array.from(root.querySelectorAll("span"));
    expect(spans).toHaveLength(3);
    const [ruleLeft, glyph, ruleRight] = spans as [HTMLElement, HTMLElement, HTMLElement];

    expect(glyph.textContent).toBe("❦");
    expect(ruleLeft.textContent).toBe("");
    expect(ruleRight.textContent).toBe("");
    expect(ruleLeft.getAttribute("style") ?? "").toContain("border-top");
    expect(ruleRight.getAttribute("style") ?? "").toContain("border-top");
  });

  it("honours the size prop via data-size + ruleStyle width", () => {
    const { container, rerender } = render(<Fleuron size="sm" />);
    let root = container.firstElementChild as HTMLElement;
    expect(root.dataset.size).toBe("sm");

    rerender(<Fleuron size="lg" />);
    root = container.firstElementChild as HTMLElement;
    expect(root.dataset.size).toBe("lg");
  });

  it("merges a custom className onto the root", () => {
    const { container } = render(<Fleuron className="extra-mark" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("chapter-fleuron");
    expect(root.className).toContain("extra-mark");
  });
});
