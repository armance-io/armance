import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom does not implement matchMedia. Provide a default stub so any
// component that consults media queries at render time can mount.
// Individual tests may override via `Object.defineProperty` or
// `window.matchMedia = vi.fn(...)`.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// jsdom does not implement EventSource. Provide an inert stub so components
// that open an SSE stream at mount (sidebar roster refresh, workflow graph)
// can render in tests without a real connection.
if (typeof globalThis !== "undefined" && !("EventSource" in globalThis)) {
  class EventSourceStub {
    onopen: ((this: EventSource, ev: Event) => unknown) | null = null;
    onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
    onmessage: ((this: EventSource, ev: MessageEvent) => unknown) | null = null;
    addEventListener = vi.fn();
    removeEventListener = vi.fn();
    close = vi.fn();
    constructor(public url: string) {}
  }
  (globalThis as unknown as { EventSource: unknown }).EventSource = EventSourceStub;
}

// jsdom ships localStorage; reset between test files via global hook.
