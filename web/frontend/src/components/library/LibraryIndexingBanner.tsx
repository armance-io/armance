import { type FC } from "react";

/**
 * Prominent "indexing in progress" banner shown while an index action runs.
 * A violet ring rotates (clock-like) with a centred glyph — far more visible
 * than the discreet per-row pulse dot. The backend index call is a single
 * synchronous request (no per-document streaming yet), so the ring is
 * indeterminate rather than a true percentage.
 */
export const LibraryIndexingBanner: FC<{ t: (k: string) => string }> = ({ t }) => {
  const A = "var(--accent,#6b4f8a)";
  const R = "var(--rule,#d6c8ad)";
  return (
    <div
      data-testid="library-indexing-banner"
      role="status"
      aria-live="polite"
      style={{
        display: "flex", alignItems: "center", gap: "12px",
        padding: "12px 16px", borderBottom: `1px solid ${R}`,
        background: "color-mix(in srgb, var(--accent) 8%, transparent)",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "22px", height: "22px", borderRadius: "999px",
          border: `2px solid color-mix(in srgb, ${A} 25%, transparent)`,
          borderTopColor: A,
          display: "inline-block",
          animation: "armance-spin 0.8s linear infinite",
        }}
      />
      <span style={{ fontFamily: "var(--ff-sans,sans-serif)", fontSize: "13px", fontWeight: 500, color: A }}>
        {t("library:indexing.in_progress")}
      </span>
      <style>{`@keyframes armance-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default LibraryIndexingBanner;
