import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AgentPortrait } from "@/components/visual/AgentPortrait";

describe("<AgentPortrait />", () => {
  it("renders an <img> with alt=name when src is supplied", () => {
    render(
      <AgentPortrait
        name="Armance"
        src="/portraits/armance.png"
        tint="#6b4f8a"
      />,
    );

    const img = screen.getByRole("img", { name: "Armance" }) as HTMLImageElement;
    expect(img.tagName).toBe("IMG");
    expect(img.getAttribute("src")).toBe("/portraits/armance.png");
    expect(img.getAttribute("alt")).toBe("Armance");
  });

  it("renders a monogram (first letter, uppercase) when src is absent", () => {
    const { container } = render(
      <AgentPortrait name="aisha" tint="#b87333" />,
    );

    // No <img> element when src is missing.
    expect(container.querySelector("img")).toBeNull();

    // Root frame exposes role="img" + aria-label = name.
    const frame = screen.getByRole("img", { name: "aisha" });
    expect(frame.textContent).toBe("A");

    // Monogram span carries the tint background.
    const span = frame.querySelector("span") as HTMLElement;
    expect(span).toBeTruthy();
    expect(span.style.background).toBe("rgb(184, 115, 51)");
  });

  it("falls back to an empty initial when name is whitespace", () => {
    render(<AgentPortrait name="   " tint="#000" />);
    const frame = screen.getByRole("img");
    expect(frame.textContent).toBe("");
  });

  it("tilts the frame on mouseEnter and resets on mouseLeave", () => {
    const { container } = render(
      <AgentPortrait name="Kim" tint="#6b4f8a" />,
    );
    const frame = container.firstElementChild as HTMLElement;

    expect(frame.style.transform).toContain("rotate(0deg)");

    fireEvent.mouseEnter(frame);
    expect(frame.style.transform).toContain("rotate(2deg)");
    expect(frame.style.transform).toContain("translateY(-3px)");

    fireEvent.mouseLeave(frame);
    expect(frame.style.transform).toContain("rotate(0deg)");
  });

  it("honours the size prop on the frame diameter", () => {
    const { container, rerender } = render(
      <AgentPortrait name="K" tint="#000" size="sm" />,
    );
    let frame = container.firstElementChild as HTMLElement;
    expect(frame.style.width).toBe("56px");
    expect(frame.style.height).toBe("56px");

    rerender(<AgentPortrait name="K" tint="#000" size="lg" />);
    frame = container.firstElementChild as HTMLElement;
    expect(frame.style.width).toBe("128px");
    expect(frame.style.height).toBe("128px");
  });
});
