import { type CSSProperties, type FC, useCallback } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface Source {
  id: string;
  kind: "doc" | "user_msg" | "web";
  ref: string;
  label: string;
}

export interface SourceListProps {
  sources: Source[];
  onClickSource: (source: Source) => void;
  highlightedId?: string | null;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const SourceList: FC<SourceListProps> = ({
  sources,
  onClickSource,
  highlightedId,
  t,
}) => {
  const handleDocOrMsgClick = useCallback(
    (source: Source) => {
      onClickSource(source);
    },
    [onClickSource]
  );

  /* ─── Styles ───────────────────────────────────────────────────────────── */

  const listStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    width: "100%",
  };

  const rowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 8px",
    gap: "12px",
  };

  const chipStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "9px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    padding: "2px 6px",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "2px",
    background: "var(--bg-paper-deep, #e8dfcd)",
    color: "var(--ink-soft, #5b5145)",
    display: "inline-block",
    whiteSpace: "nowrap",
    userSelect: "none",
  };

  const labelStyle: CSSProperties = {
    flex: 1,
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    color: "var(--ink, #2a2520)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const actionStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    lineHeight: 1,
  };

  const emptyStyle: CSSProperties = {
    padding: "16px 8px",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  };

  const emptyTextStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    fontSize: "13px",
    color: "var(--ink-soft, #5b5145)",
  };

  return (
    <div style={listStyle}>
      <style>{`
        .source-row {
          border-bottom: 1px solid var(--rule, #d6c8ad);
          transition: background 120ms ease;
        }
        .source-row:hover {
          background: var(--bg-paper-deep, #e8dfcd);
        }
        .source-action {
          color: var(--ink-soft, #5b5145);
          transition: color 120ms ease;
          cursor: pointer;
          text-decoration: none;
          background: none;
          border: none;
          padding: 0;
          display: inline-flex;
          align-items: center;
          outline: none;
        }
        .source-action:hover,
        .source-action:focus {
          color: var(--accent, #6b4f8a) !important;
        }
        @media (prefers-reduced-motion: reduce) {
          * {
            transition: none !important;
          }
        }
      `}</style>

      {sources.length === 0 ? (
        <div style={emptyStyle}>
          <span style={emptyTextStyle}>{t("run:sources.empty")}</span>
        </div>
      ) : (
        sources.map((src) => {
          const isWeb = src.kind === "web";
          const kindLabel = t(`run:sources.kind.${src.kind}`).toUpperCase();

          const isHighlighted = src.id === highlightedId;
          return (
            <div
              key={src.id}
              id={`source-row-${src.id}`}
              className="source-row"
              style={{
                ...rowStyle,
                background: isHighlighted ? "color-mix(in srgb, var(--accent, #6b4f8a) 15%, transparent)" : undefined,
                transition: isHighlighted ? "none" : "background 600ms ease-out",
              }}
            >
              {/* Kind chip */}
              <div style={chipStyle}>{kindLabel}</div>

              {/* Label */}
              <span style={labelStyle} title={src.label}>
                {src.label}
              </span>

              {/* Action */}
              <div style={actionStyle}>
                {isWeb ? (
                  <a
                    href={src.ref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="source-action"
                    onClick={() => onClickSource(src)}
                    aria-label={t("run:sources.open_aria")}
                    title={t("run:sources.open_aria")}
                  >
                    <span aria-hidden="true">↗</span>
                  </a>
                ) : (
                  <button
                    onClick={() => handleDocOrMsgClick(src)}
                    className="source-action"
                    aria-label={t("run:sources.open_aria")}
                    title={t("run:sources.open_aria")}
                  >
                    <span aria-hidden="true">→</span>
                  </button>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};

export default SourceList;
