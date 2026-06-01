"use client";

export type ViewType = "chat" | "library" | "workflows" | "admin";

type Listener = (view: ViewType) => void;

const listeners = new Set<Listener>();

let currentView: ViewType = "chat";

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
