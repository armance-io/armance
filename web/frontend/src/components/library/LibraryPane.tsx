import {
  type ChangeEvent,
  type CSSProperties,
  type FC,
  useRef,
  useState,
} from "react";

import { EmptyLibrary } from "../visual/EmptyState/EmptyLibrary";
import { PulseDot } from "../_shared/PulseDot";
import { LibraryEmbeddingBanner } from "./LibraryEmbeddingBanner";
import { type Doc, type DocFormat, type DocStatus } from "@/lib/api";

export interface LibraryPaneProps {
  docs: Doc[];
  /** Total indexed slips (feuillets) across all sources. */
  totalFeuillets?: number;
  /** False when no embedding model is configured — disables indexing actions. */
  embeddingAvailable?: boolean;
  onImport:   (file: File)    => Promise<void>;
  /** Mutations resolve to an ok flag so the button can flash a check. */
  onIndexAll: ()              => Promise<boolean>;
  onIndex:    (name: string)  => Promise<boolean>;
  onLoad:     (name: string)  => Promise<boolean>;
  onUnload:   (name: string)  => Promise<boolean>;
  onUnindex:  (name: string)  => Promise<boolean>;
  /**
   * Deletion is confirmed inside the pane via an inline modal before this is
   * called — the prop itself performs the actual removal.
   */
  onDelete:   (name: string)  => Promise<void>;
  /** Embedding catalogue for the inline picker (type-ahead + free text). */
  embeddingOptions?: { provider: string; id: string; name: string }[];
  /** Set the project embedding provider + model (enables indexing). */
  onSetEmbedding?: (provider: string, model: string) => Promise<void>;
  t: (key: string) => string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const FMTS: DocFormat[] = ["pdf", "docx", "md", "txt"];

const DOT_CLR: Record<DocStatus, string> = {
  pending: "var(--ink-faint,#9c8e7e)",
  indexed: "var(--accent-soft,#b7a4c9)",
  loaded:  "var(--accent,#6b4f8a)",
};

function fmtSize(b: number): string {
  if (b >= 1_048_576) return `${(b / 1_048_576).toFixed(1)} MB`;
  if (b >= 1_024)     return `${Math.round(b / 1_024)} KB`;
  return `${b} B`;
}

/* ─── LibraryPane ────────────────────────────────────────────────────────── */

/**
 * `<LibraryPane />` — document library for `.armance/docs`.
 *
 * Lists every document with format chip, index status pill, file size and
 * per-row actions (index / load / unload / unindex / delete).
 * Delete triggers an inline confirmation strip before calling `onDelete`.
 *
 * Top toolbar: name search · format filter · "Tout indexer" (when pending
 * docs exist) · "Importer" (opens system file picker).
 */
export const LibraryPane: FC<LibraryPaneProps> = ({
  docs, totalFeuillets = 0, embeddingAvailable = true, onImport, onIndexAll, onIndex, onLoad, onUnload, onUnindex, onDelete,
  embeddingOptions = [], onSetEmbedding, t,
}) => {
  const [search,  setSearch]  = useState("");
  const [fmts,    setFmts]    = useState<Set<DocFormat>>(new Set());
  const [del,     setDel]     = useState<string | null>(null);
  const [busy,    setBusy]    = useState<Set<string>>(new Set());
  const [done,    setDone]    = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<string | null>(null);
  const fileRef               = useRef<HTMLInputElement>(null);

  /* ── Action wrapper ── */
  // On success, flash an ephemeral check on the row's button for ~1.6s.
  // `fn` may return void (delete) — only an explicit `true` flashes the check.
  async function act(name: string, fn: () => Promise<boolean | void>): Promise<void> {
    setBusy(s => new Set(s).add(name));
    try {
      const ok = await fn();
      if (ok === true) {
        setDone(s => new Set(s).add(name));
        setTimeout(() => setDone(s => { const n = new Set(s); n.delete(name); return n; }), 1600);
      }
    } finally {
      setBusy(s => { const n = new Set(s); n.delete(name); return n; });
    }
  }

  function toggleFmt(f: DocFormat): void {
    setFmts(s => { const n = new Set(s); n.has(f) ? n.delete(f) : n.add(f); return n; });
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = e.target.files?.[0]; if (file) await onImport(file);
    e.target.value = "";
  }

  const visible = docs
    .filter(d => fmts.size === 0 || fmts.has(d.format))
    .filter(d => !search || d.name.toLowerCase().includes(search.toLowerCase()));

  /* ── Style tokens ── */
  const R = "var(--rule,#d6c8ad)";
  const D = "var(--bg-paper-deep,#e8dfcd)";
  const A = "var(--accent,#6b4f8a)";
  const I = "var(--ink,#2a2520)";
  const SFT = "var(--ink-soft,#5b5145)";
  const P = "var(--bg-paper,#f4ede0)";
  const MONO = "var(--ff-mono,monospace)" as CSSProperties["fontFamily"];
  const SANS = "var(--ff-sans,sans-serif)" as CSSProperties["fontFamily"];

  const chipSty = (on: boolean): CSSProperties => ({
    padding: "2px 7px", borderRadius: "2px",
    border: `1px solid ${on ? A : R}`,
    background: on ? "color-mix(in srgb,var(--accent) 12%,transparent)" : "transparent",
    color: on ? A : SFT, fontFamily: MONO, fontSize: "10px",
    letterSpacing: "0.08em", textTransform: "uppercase", cursor: "pointer",
    transition: "all 0.15s ease",
  });

  const tbBtnSty = (primary?: boolean): CSSProperties => ({
    height: "30px", padding: "0 12px", borderRadius: "4px",
    border: `1px solid ${primary ? A : R}`,
    background: primary ? A : "transparent",
    color: primary ? P : I,
    fontFamily: SANS, fontSize: "13px", fontWeight: 500,
    cursor: "pointer", flexShrink: 0, transition: "all 0.15s ease",
  });

  const actBtnSty = (dest?: boolean): CSSProperties => ({
    padding: "3px 8px", borderRadius: "3px",
    border: `1px solid ${dest ? "oklch(0.62 0.14 22)" : R}`,
    background: "transparent",
    color: dest ? "oklch(0.42 0.14 22)" : SFT,
    fontFamily: MONO, fontSize: "10px", letterSpacing: "0.06em",
    cursor: "pointer", transition: "all 0.15s ease",
  });

  // Ephemeral success check (bug: buttons gave no visual confirmation).
  const Check = () => (
    <svg width="11" height="11" viewBox="0 0 14 14" fill="none" stroke="currentColor"
      strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"
      style={{ display: "block", color: A }}>
      <path d="M2.5 7.5l3 3 6-7" />
    </svg>
  );

  // Indexing action button — grayed out when no embedding model is configured.
  // Keyed by row `name` so busy/done track the right row.
  const EmbedBtn = ({ name, label, onClick }: { name: string; label: string; onClick: () => void }) => (
    <button
      type="button"
      disabled={busy.has(name) || !embeddingAvailable}
      style={{
        ...actBtnSty(),
        opacity: embeddingAvailable ? 1 : 0.45,
        cursor: embeddingAvailable ? "pointer" : "not-allowed",
        display: "inline-flex", alignItems: "center", gap: "4px",
      }}
      title={embeddingAvailable ? undefined : t("library:no_embedding_tooltip")}
      onClick={() => embeddingAvailable && onClick()}
    >
      {done.has(name) ? <Check /> : label}
    </button>
  );

  /* ── Render ── */
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: P, overflow: "hidden" }}>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px",
        padding: "10px 14px", borderBottom: `1px solid ${R}`,
        background: D, flexWrap: "wrap", flexShrink: 0 }}>

        <input
          style={{ flex: "1 1 140px", minWidth: 0, height: "30px", padding: "0 10px",
            border: `1px solid ${R}`, borderRadius: "4px", background: P,
            color: I, fontFamily: SANS, fontSize: "13px", outline: "none" }}
          placeholder={t("library:toolbar.search_placeholder")}
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        <div style={{ display: "flex", gap: "4px" }}>
          {FMTS.map(f => (
            <button key={f} type="button" style={chipSty(fmts.has(f))} onClick={() => toggleFmt(f)}>
              {f}
            </button>
          ))}
        </div>

        {docs.some(d => d.status === "pending") && (
          <button
            type="button"
            style={{
              ...tbBtnSty(),
              opacity: embeddingAvailable ? 1 : 0.45,
              cursor: embeddingAvailable ? "pointer" : "not-allowed",
            }}
            disabled={busy.has("__all__") || !embeddingAvailable}
            title={embeddingAvailable ? undefined : t("library:no_embedding_tooltip")}
            onClick={() => embeddingAvailable && act("__all__", onIndexAll)}
          >
            {done.has("__all__")
              ? <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}><Check /> {t("library:toolbar.index_all")}</span>
              : t("library:toolbar.index_all")}
          </button>
        )}

        <button type="button" style={tbBtnSty(true)} onClick={() => fileRef.current?.click()}>
          {t("library:toolbar.import")}
        </button>

        {/* BUG-01: total indexed feuillets across all sources */}
        <span
          data-testid="feuillet-total"
          title={t("library:feuillets_total_aria")}
          style={{ marginLeft: "auto", fontFamily: MONO, fontSize: "11px", color: "var(--ink-faint,#9c8e7e)" }}
        >
          {t("library:feuillets_count").replace("{n}", String(totalFeuillets))}
        </span>

        <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt"
          style={{ display: "none" }} onChange={handleFile} />
      </div>

      {/* ── Embedding setup banner (shown when no model configured) ──────── */}
      {!embeddingAvailable && onSetEmbedding && (
        <LibraryEmbeddingBanner options={embeddingOptions} onSet={onSetEmbedding} t={t} />
      )}

      {/* ── List ─────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto" }} role="list" aria-label={t("library:list_aria")}>

        {docs.length === 0 && (
          <EmptyLibrary t={t} onCta={() => fileRef.current?.click()} />
        )}

        {visible.map(doc => {
          const b   = busy.has(doc.name);
          const isDel = del === doc.name;

          return (
            <div key={doc.name} role="listitem">

              {/* Row */}
              <div
                style={{ height: "56px", display: "flex", alignItems: "center",
                  padding: "0 14px", gap: "10px",
                  borderBottom: `1px solid var(--rule-soft,#e8dfcd)`,
                  background: hovered === doc.name ? D : "transparent",
                  transition: "background 0.12s ease" }}
                onMouseEnter={() => setHovered(doc.name)}
                onMouseLeave={() => setHovered(null)}
              >
                {/* Name */}
                <span style={{ flex: 1, minWidth: 0, overflow: "hidden",
                  textOverflow: "ellipsis", whiteSpace: "nowrap",
                  fontFamily: SANS, fontSize: "13px", color: I }}>
                  {doc.name}
                </span>

                {/* Format chip */}
                <span style={{ padding: "1px 5px", borderRadius: "2px",
                  border: `1px solid ${R}`, fontFamily: MONO, fontSize: "9px",
                  letterSpacing: "0.10em", textTransform: "uppercase",
                  color: SFT, flexShrink: 0 }}>
                  {doc.format}
                </span>

                {/* Status pill */}
                <span style={{ display: "inline-flex", alignItems: "center", gap: "5px",
                  fontFamily: MONO, fontSize: "10px", letterSpacing: "0.06em",
                  color: DOT_CLR[doc.status], flexShrink: 0 }}>
                  <span style={{ width: "6px", height: "6px", borderRadius: "999px",
                    background: DOT_CLR[doc.status], flexShrink: 0 }} />
                  {t(`library:status.${doc.status}`)}
                </span>

                {/* Size */}
                <span style={{ fontFamily: MONO, fontSize: "10px", color: SFT, flexShrink: 0 }}>
                  {fmtSize(doc.size_bytes)}
                </span>

                {/* Feuillet count (indexed docs) */}
                {doc.feuillets ? (
                  <span style={{ fontFamily: MONO, fontSize: "10px", color: "var(--accent,#6b4f8a)", flexShrink: 0 }}
                    title={t("library:feuillets_total_aria")}>
                    {t("library:feuillets_count").replace("{n}", String(doc.feuillets))}
                  </span>
                ) : null}

                {/* Busy indicator while an action runs */}
                {b && <PulseDot size={8} />}

                {/* Actions */}
                <div style={{ display: "flex", gap: "4px", flexShrink: 0, marginLeft: "4px" }}>
                  {doc.status === "pending"  && <EmbedBtn name={doc.name} label={t("library:action.index")}  onClick={() => act(doc.name, () => onIndex(doc.name))} />}
                  {doc.status === "indexed"  && <EmbedBtn name={doc.name} label={t("library:action.load")}   onClick={() => act(doc.name, () => onLoad(doc.name))} />}
                  {doc.status === "loaded"   && <EmbedBtn name={doc.name} label={t("library:action.unload")} onClick={() => act(doc.name, () => onUnload(doc.name))} />}
                  {doc.status !== "pending"  && <button type="button" disabled={b} style={actBtnSty()} onClick={() => act(doc.name, () => onUnindex(doc.name))}>{t("library:action.unindex")}</button>}
                  <button type="button" disabled={b} style={actBtnSty(true)} onClick={() => setDel(doc.name)}>{t("library:action.delete")}</button>
                </div>
              </div>

              {/* Confirm delete */}
              {isDel && (
                <div role="alertdialog" aria-label={t("library:confirm.delete_title")}
                  style={{ padding: "10px 14px",
                    borderLeft: "3px solid oklch(0.60 0.14 22)",
                    background: "oklch(0.99 0.005 22)",
                    display: "flex", alignItems: "center", gap: "10px",
                    fontFamily: SANS, fontSize: "13px", color: I }}>
                  <span style={{ flex: 1, color: SFT }}>{t("library:confirm.delete_hint")}</span>
                  <button type="button" style={tbBtnSty()} onClick={() => setDel(null)}>
                    {t("library:confirm.cancel")}
                  </button>
                  <button type="button" disabled={b}
                    style={{ ...actBtnSty(true), padding: "0 12px", height: "30px" }}
                    onClick={async () => { setDel(null); await act(doc.name, () => onDelete(doc.name)); }}>
                    {t("library:confirm.confirm")}
                  </button>
                </div>
              )}

            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LibraryPane;
