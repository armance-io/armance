import { type CSSProperties, type FC, useState } from "react";

export interface LibraryEmbeddingBannerProps {
  options: { provider: string; id: string; name: string }[];
  onSet: (model: string) => Promise<void>;
  t: (key: string) => string;
}

/**
 * Inline banner shown in the library when no embedding model is configured.
 * Lets the user pick (type-ahead over the cross-provider catalogue) or type
 * any embedding model id to enable indexing — without leaving for admin.
 */
export const LibraryEmbeddingBanner: FC<LibraryEmbeddingBannerProps> = ({ options, onSet, t }) => {
  const [draft, setDraft] = useState("");

  const R = "var(--rule,#d6c8ad)";
  const P = "var(--bg-paper,#f4ede0)";
  const I = "var(--ink,#2a2520)";
  const SFT = "var(--ink-soft,#5b5145)";
  const A = "var(--accent,#6b4f8a)";
  const MONO = "var(--ff-mono,monospace)" as CSSProperties["fontFamily"];
  const SANS = "var(--ff-sans,sans-serif)" as CSSProperties["fontFamily"];

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap",
      padding: "10px 14px", borderBottom: `1px solid ${R}`,
      background: "color-mix(in srgb, var(--accent) 6%, transparent)",
    }}>
      <span style={{ fontFamily: SANS, fontSize: "12px", color: SFT, flex: "1 1 200px" }}>
        {t("library:embedding.prompt")}
      </span>
      <input
        list="library-embedding-list"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        placeholder={t("library:embedding.placeholder")}
        style={{ height: "30px", padding: "0 10px", minWidth: "180px",
          border: `1px solid ${R}`, borderRadius: "4px", background: P,
          color: I, fontFamily: MONO, fontSize: "12px", outline: "none" }}
      />
      <datalist id="library-embedding-list">
        {options.map(m => (
          <option key={`${m.provider}:${m.id}`} value={m.id}>
            {`${m.name} (${m.provider})`}
          </option>
        ))}
      </datalist>
      <button
        type="button"
        disabled={!draft.trim()}
        style={{
          height: "30px", padding: "0 12px", borderRadius: "4px",
          border: `1px solid ${A}`, background: A, color: P,
          fontFamily: SANS, fontSize: "13px", fontWeight: 500,
          cursor: draft.trim() ? "pointer" : "not-allowed", flexShrink: 0,
        }}
        onClick={() => draft.trim() && onSet(draft.trim())}
      >
        {t("library:embedding.set")}
      </button>
    </div>
  );
};

export default LibraryEmbeddingBanner;
