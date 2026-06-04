"use client";

export type ViewType = "chat" | "library" | "workflows" | "admin" | "deliverables";

type Listener = (view: ViewType) => void;

const listeners = new Set<Listener>();

const getInitialView = (): ViewType => {
  if (typeof window === "undefined") return "chat";
  const p = window.location.pathname;
  if (p.includes("/library")) return "library";
  if (p.includes("/workflows")) return "workflows";
  if (p.includes("/admin")) return "admin";
  if (p.includes("/deliverables")) return "deliverables";
  return "chat";
};

let currentView: ViewType = getInitialView();

export function emitViewChange(view: ViewType): void {
  currentView = view;
  listeners.forEach((fn) => fn(view));
}

export function onViewChange(fn: Listener): () => void {
  listeners.add(fn);
  fn(currentView);
  return () => {
    listeners.delete(fn);
  };
}

export function getCurrentView(): ViewType {
  return currentView;
}
