import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@/lib/api", () => ({
  browseFolders: vi.fn(),
}));

import * as api from "@/lib/api";
import { FolderExplorer } from "../FolderExplorer";

const browseFolders = vi.mocked(api.browseFolders);

const HOME = {
  path: "/home/u",
  root: "/home/u",
  parent: null,
  dirs: [{ name: "projects", path: "/home/u/projects" }],
};

describe("FolderExplorer", () => {
  beforeEach(() => browseFolders.mockReset());

  it("lists subdirs of the starting folder", async () => {
    browseFolders.mockResolvedValue(HOME);
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("explorer-dir")).toHaveTextContent("projects"));
    expect(screen.getByTestId("explorer-path")).toHaveTextContent("/home/u");
  });

  it("descends into a clicked subdir", async () => {
    browseFolders.mockResolvedValueOnce(HOME).mockResolvedValueOnce({
      path: "/home/u/projects",
      root: "/home/u",
      parent: "/home/u",
      dirs: [],
    });
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-dir"));
    fireEvent.click(screen.getByTestId("explorer-dir"));
    await waitFor(() => expect(browseFolders).toHaveBeenCalledWith("/home/u/projects"));
  });

  it("returns the current path on select", async () => {
    const onSelect = vi.fn();
    browseFolders.mockResolvedValue(HOME);
    render(<FolderExplorer onSelect={onSelect} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-select"));
    fireEvent.click(screen.getByTestId("explorer-select"));
    expect(onSelect).toHaveBeenCalledWith("/home/u");
  });

  it("shows an error when a descend fails", async () => {
    // First load (effect) succeeds; the failing browse is triggered from a
    // click handler — the rejection is consumed inside an event, not a
    // fire-and-forget effect, so it renders the error cleanly.
    browseFolders.mockResolvedValueOnce(HOME).mockRejectedValueOnce(new Error("nope"));
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-dir"));
    fireEvent.click(screen.getByTestId("explorer-dir"));
    expect(await screen.findByTestId("explorer-error")).toBeInTheDocument();
  });
});
