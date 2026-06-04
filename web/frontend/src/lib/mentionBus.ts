"use client";

/**
 * Tiny pub/sub so the sidebar Staff list can inject `@Agent ` into the active
 * chat input without navigation or prop drilling. The chat input subscribes;
 * the sidebar publishes. One active input at a time (single-session V2).
 */
type Listener = (mention: string) => void;

const listeners = new Set<Listener>();

export function emitMention(agentName: string): void {
  const mention = `@${agentName} `;
  listeners.forEach((fn) => fn(mention));
}

export function onMention(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
