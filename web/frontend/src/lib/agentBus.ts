"use client";

import { useEffect, useState } from "react";

/**
 * Decoupled bus for the active conversation agent (TUI parity).
 *
 * - The sidebar Staff list publishes a *switch* (user picked an agent).
 * - The chat container subscribes, submits `@Name` (a switch turn), and
 *   publishes the *current* agent back (e.g. after `turn.completed`).
 * - The sidebar subscribes to current to highlight the active L2 row.
 *
 * One active conversation in V2 (single session). For V3/SaaS this becomes a
 * per-session store; the component API (useCurrentAgent / requestSwitch) stays
 * the same, so wiring doesn't change.
 */
type SwitchListener = (firstName: string) => void;
type CurrentListener = (slugOrName: string) => void;
type BusyListener = (busyName: string | null) => void;

const switchListeners = new Set<SwitchListener>();
const currentListeners = new Set<CurrentListener>();
const busyListeners = new Set<BusyListener>();
let current = "system-context"; // Armance by default
let busyAgent: string | null = null; // the agent currently thinking (display name)

export function requestAgentSwitch(firstName: string): void {
  switchListeners.forEach((fn) => fn(firstName));
}

export function onAgentSwitch(fn: SwitchListener): () => void {
  switchListeners.add(fn);
  return () => switchListeners.delete(fn);
}

export function setCurrentAgent(slugOrName: string): void {
  current = slugOrName;
  currentListeners.forEach((fn) => fn(slugOrName));
}

export function useCurrentAgent(): string {
  const [value, setValue] = useState(current);
  useEffect(() => {
    setValue(current);
    currentListeners.add(setValue);
    return () => {
      currentListeners.delete(setValue);
    };
  }, []);
  return value;
}

export function setBusyAgent(name: string | null): void {
  busyAgent = name;
  busyListeners.forEach((fn) => fn(name));
}

export function useBusyAgent(): string | null {
  const [value, setValue] = useState(busyAgent);
  useEffect(() => {
    setValue(busyAgent);
    busyListeners.add(setValue);
    return () => {
      busyListeners.delete(setValue);
    };
  }, []);
  return value;
}
