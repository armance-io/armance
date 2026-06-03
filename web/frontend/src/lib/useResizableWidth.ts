import { useCallback, useEffect, useState } from "react";

export interface ResizableWidthOptions {
  /** localStorage key to persist the chosen width. */
  storageKey: string;
  /** Initial width when nothing is persisted. */
  initial: number;
  min: number;
  max: number;
  /** Which edge carries the drag handle. A left-edge handle (right-docked
   * panel) grows the panel as the pointer moves left. @default "left" */
  edge?: "left" | "right";
}

export interface ResizableWidth {
  width: number;
  dragging: boolean;
  /** Attach to the drag handle's onMouseDown. */
  onDragStart: (e: React.MouseEvent) => void;
}

/**
 * Drag-to-resize a panel by one of its vertical edges, persisting the width.
 * Mirrors the sidebar resize behaviour (AppShell) as a reusable hook so the
 * workflow panel and future panels share one implementation.
 */
export function useResizableWidth(opts: ResizableWidthOptions): ResizableWidth {
  const { storageKey, initial, min, max, edge = "left" } = opts;
  const [width, setWidth] = useState(initial);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const v = localStorage.getItem(storageKey);
    if (v != null) {
      const n = Number(v);
      if (Number.isFinite(n)) setWidth(Math.max(min, Math.min(max, n)));
    }
  }, [storageKey, min, max]);

  const onDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = width;
      const sign = edge === "left" ? -1 : 1;
      setDragging(true);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";

      const onMove = (ev: MouseEvent) => {
        const next = startW + sign * (ev.clientX - startX);
        setWidth(Math.max(min, Math.min(max, next)));
      };
      const onUp = () => {
        setDragging(false);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        setWidth((w) => {
          localStorage.setItem(storageKey, String(w));
          return w;
        });
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [width, edge, min, max, storageKey],
  );

  return { width, dragging, onDragStart };
}
