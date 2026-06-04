"use client";

import { useEffect, useState } from "react";

/**
 * Tracks whether the current session is "locked" — i.e. the user has sent a
 * first message, committing to the pre-loaded session. The header session
 * selector becomes read-only once locked (no switching to an older session
 * mid-conversation), mirroring the TUI's resume flow.
 *
 * Reset on navigation to a different session (the View remounts).
 */
type Listener = (locked: boolean) => void;
const listeners = new Set<Listener>();
let locked = false;

export function lockSession(): void {
  if (locked) return;
  locked = true;
  listeners.forEach((fn) => fn(true));
}

export function resetSessionLock(): void {
  locked = false;
  listeners.forEach((fn) => fn(false));
}

export function useSessionLocked(): boolean {
  const [value, setValue] = useState(locked);
  useEffect(() => {
    setValue(locked);
    listeners.add(setValue);
    return () => {
      listeners.delete(setValue);
    };
  }, []);
  return value;
}
