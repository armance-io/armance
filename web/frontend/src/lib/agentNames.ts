/**
 * Resolve a raw agent key (as it appears in logs / footprint buckets) to a
 * human-readable display name. Single source so Statistics, Empreinte and the
 * sidebar all show the same labels (e.g. "system-context" → "Armance",
 * "embedding" → "Library").
 */
const STAFF_DISPLAY: Record<string, string> = {
  "system-context": "Armance",
  "context": "Armance",
  "system-hr": "Malik",
  "hr": "Malik",
  "system-orchestrator": "Kim",
  "orchestrator": "Kim",
  "system-judge": "Mona",
  "judge": "Mona",
  "system-challenger": "Serge",
  "challenger": "Serge",
  embedding: "Library",
};

export function displayAgentName(rawKey: string): string {
  const cleanKey = rawKey.replace(/[{}]/g, "").replace(/_/g, "-").trim().toLowerCase();
  if (cleanKey in STAFF_DISPLAY) return STAFF_DISPLAY[cleanKey]!;
  return rawKey; // specialists are already friendly (e.g. "Sarah")
}
