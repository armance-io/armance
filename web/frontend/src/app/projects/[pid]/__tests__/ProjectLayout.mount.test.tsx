import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

import ProjectLayout from "../layout";
import { emitViewChange } from "@/lib/navigationBus";

// The regression this guards: switching tabs used to UNMOUNT the chat view
// (the SPA layout rendered it via `&&`), losing its agent-switch separators and
// tearing down its SSE EventSource → lost turn.completed → stuck input. Chat
// must stay mounted across tab switches.

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/default/sessions/s1",
}));
vi.mock("@/components/visual/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("../sessions/[sid]/SessionView", () => ({
  default: () => <div data-testid="chat-view">chat</div>,
}));
vi.mock("../sessions/[sid]/library/LibraryView", () => ({
  default: () => <div data-testid="library-view">library</div>,
}));
vi.mock("../sessions/[sid]/workflows/[name]/WorkflowView", () => ({
  default: () => <div data-testid="workflow-view">workflow</div>,
}));
vi.mock("@/components/admin/AdminPageContainer", () => ({
  default: () => <div data-testid="admin-view">admin</div>,
}));

describe("ProjectLayout — chat stays mounted across tab switches", () => {
  beforeEach(() => {
    // navigationBus is a module singleton; reset to chat before each test.
    act(() => emitViewChange("chat"));
  });

  it("keeps the chat view in the DOM when another tab is active", () => {
    render(<ProjectLayout>{null}</ProjectLayout>);
    expect(screen.getByTestId("chat-view")).toBeTruthy();

    // Switch to the Workflows tab.
    act(() => emitViewChange("workflows"));

    // Workflow view shows AND chat is still mounted (just hidden) — not removed.
    expect(screen.getByTestId("workflow-view")).toBeTruthy();
    expect(screen.getByTestId("chat-view")).toBeTruthy();
  });

  it("hides the chat view (does not unmount) when inactive", () => {
    render(<ProjectLayout>{null}</ProjectLayout>);
    act(() => emitViewChange("admin"));

    const chat = screen.getByTestId("chat-view");
    // Its wrapper is display:none, so it is present but not displayed.
    const wrapper = chat.parentElement as HTMLElement;
    expect(wrapper.style.display).toBe("none");
    expect(screen.getByTestId("admin-view")).toBeTruthy();
  });
});
