/**
 * C.6 — Stable per-agent colour assignment.
 *
 * Staff agents are reserved violet shades (the eyes of the portraits).
 * Specialists get assigned a colour from a curated non-violet palette
 * keyed by agent name, persisted in localStorage so the same agent
 * keeps the same colour across reloads.
 */

const STAFF: Record<string, string> = {
  "system-context": "var(--accent-deep, #4a3666)",
  Armance: "var(--accent-deep, #4a3666)",
  "system-hr": "var(--accent, #6b4f8a)",
  Malik: "var(--accent, #6b4f8a)",
  "system-orchestrator": "var(--accent-soft, #b7a4c9)",
  Kim: "var(--accent-soft, #b7a4c9)",
  "system-judge": "#7a5da4",
  Mona: "#7a5da4",
  "system-challenger": "#3a2b54",
  Serge: "#3a2b54",
};

// 12-colour curated specialist palette — warm earths + muted blues.
const SPECIALIST_PALETTE: ReadonlyArray<string> = [
  "#9c6b4a", // sienne
  "#b08a3a", // ocre
  "#7e8b5c", // sauge
  "#5f7e88", // bleu ardoise
  "#a44141", // terracotta
  "#6e5e3f", // brun olivâtre
  "#4d6e7a", // bleu pétrole doux
  "#8a6d4e", // brun clair
  "#5a7351", // vert mousse
  "#7f6952", // beige profond
  "#3f5e6e", // bleu nuit doux
  "#a07a5a", // caramel
];

const STORAGE_KEY = "armance.agent_colours";

let cache: Record<string, string> | null = null;

function loadCache(): Record<string, string> {
  if (cache !== null) return cache;
  if (typeof window === "undefined") {
    cache = {};
    return cache;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    cache = raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    cache = {};
  }
  return cache;
}

function saveCache(): void {
  if (typeof window === "undefined" || cache === null) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch {
    /* quota — silently ignore */
  }
}

/**
 * Deterministic non-cryptographic hash of a string (djb2).
 * Used to map specialist names into the palette so the same name
 * always lands on the same colour.
 */
function djb2(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i += 1) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function isStaff(name: string): boolean {
  return name in STAFF;
}

export function assignAgentColour(
  name: string,
  palette: ReadonlyArray<string> = SPECIALIST_PALETTE,
): string {
  const reserved = STAFF[name];
  if (reserved !== undefined) return reserved;
  const cached = loadCache();
  const existing = cached[name];
  if (existing !== undefined) return existing;
  const idx = djb2(name) % palette.length;
  const picked = palette[idx] ?? palette[0] ?? "#888888";
  cached[name] = picked;
  saveCache();
  return picked;
}

/** Test-only — reset the in-memory + storage cache. */
export function _resetColourCache(): void {
  cache = {};
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}
