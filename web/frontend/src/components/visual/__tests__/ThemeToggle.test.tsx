import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ThemeToggle } from "@/components/visual/ThemeToggle";

const STORAGE_KEY = "armance.theme";
const stub = (k: string): string => k;

function installStorage(): void {
  const store: Record<string, string> = {};
  const fake: Storage = {
    get length(): number {
      return Object.keys(store).length;
    },
    clear(): void {
      for (const k of Object.keys(store)) delete store[k];
    },
    getItem(key: string): string | null {
      return Object.prototype.hasOwnProperty.call(store, key)
        ? (store[key] as string)
        : null;
    },
    key(index: number): string | null {
      return Object.keys(store)[index] ?? null;
    },
    removeItem(key: string): void {
      delete store[key];
    },
    setItem(key: string, value: string): void {
      store[key] = String(value);
    },
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    writable: true,
    value: fake,
  });
}

function mockMatchMedia(matches: Record<string, boolean>): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: matches[query] ?? false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("<ThemeToggle />", () => {
  beforeEach(() => {
    installStorage();
    document.documentElement.removeAttribute("data-theme");
    mockMatchMedia({});
    vi.useRealTimers();
  });

  it("reads localStorage on mount and writes data-theme to <html>", () => {
    localStorage.setItem(STORAGE_KEY, "dark");
    render(<ThemeToggle t={stub} />);
    expect(document.documentElement.dataset.theme).toBe("dark");
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-pressed")).toBe("true");
  });

  it("falls back to prefers-color-scheme: dark when storage is empty", () => {
    mockMatchMedia({ "(prefers-color-scheme: dark)": true });
    render(<ThemeToggle t={stub} />);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("defaults to light when neither storage nor system preference is set", () => {
    render(<ThemeToggle t={stub} />);
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
  });

  it("flips data-theme + localStorage on click (reduced motion path)", () => {
    mockMatchMedia({ "(prefers-reduced-motion: reduce)": true });
    render(<ThemeToggle t={stub} />);

    const btn = screen.getByRole("button");
    expect(document.documentElement.dataset.theme).toBe("light");

    act(() => {
      btn.click();
    });

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
    expect(btn.getAttribute("aria-pressed")).toBe("true");

    act(() => {
      btn.click();
    });

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
  });

  it("flips data-theme after the 110ms animation when motion is allowed", () => {
    vi.useFakeTimers();
    render(<ThemeToggle t={stub} />);
    const btn = screen.getByRole("button");

    act(() => {
      btn.click();
    });
    // Mid-animation: theme still light.
    expect(document.documentElement.dataset.theme).toBe("light");

    act(() => {
      vi.advanceTimersByTime(120);
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("uses the t prop for the aria-label", () => {
    render(
      <ThemeToggle t={(k) => (k === "visual:theme.toggle_aria" ? "Switch" : k)} />,
    );
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-label")).toBe("Switch");
  });
});
