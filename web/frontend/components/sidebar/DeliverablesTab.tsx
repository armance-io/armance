import { type CSSProperties, type FC, useMemo, useState } from "react";
import { tokens, Fleuron } from "../_shared/armance-tokens";

export type DeliverableFormat = "md" | "pdf" | "docx" | "pptx";

export interface DeliverableRow {
  id: string;
  title: string;
  kind: "synthesis" | "mona-deliverable" | "export";
  format: DeliverableFormat;
  workflow?: string;
  created_at: string;
  starred: boolean;
}

export interface DeliverablesTabProps {
  deliverables: DeliverableRow[];
  onOpen: (id: string) => void;
  onStar: (id: string, starred: boolean) => void;
  t: (key: string) => string;
}

/* Crude "X ago" formatter — locale-aware fallback via Intl.RelativeTimeFormat. */
function humanAgo(iso: string, locale = "fr"): string {
  const diff = Date.now() - new Date(iso).getTime();
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const sec = Math.round(diff / 1000);
  if (sec < 60) return rtf.format(-sec, "second");
  const min = Math.round(sec / 60);
  if (min < 60) return rtf.format(-min, "minute");
  const hr = Math.round(min / 60);
  if (hr < 24) return rtf.format(-hr, "hour");
  const day = Math.round(hr / 24);
  if (day < 30) return rtf.format(-day, "day");
  const mo = Math.round(day / 30);
  if (mo < 12) return rtf.format(-mo, "month");
  return rtf.format(-Math.round(mo / 12), "year");
}

const ALL_FORMATS: DeliverableFormat[] = ["md", "pdf", "docx", "pptx"];

export const DeliverablesTab: FC<DeliverablesTabProps> = ({
  deliverables,
  onOpen,
  onStar,
  t,
}) => {
  const [workflow, setWorkflow] = useState<string>("");
  const [formats, setFormats] = useState<Set<DeliverableFormat>>(new Set());
  const [starredFirst, setStarredFirst] = useState(false);

  const workflows = useMemo(
    () => Array.from(new Set(deliverables.map((d) => d.workflow).filter(Boolean))) as string[],
    [deliverables],
  );

  const rows = useMemo(() => {
    let list = deliverables.filter((d) => {
      if (workflow && d.workflow !== workflow) return false;
      if (formats.size > 0 && !formats.has(d.format)) return false;
      return true;
    });
    if (starredFirst) {
      list = [...list].sort((a, b) => Number(b.starred) - Number(a.starred));
    }
    return list;
  }, [deliverables, workflow, formats, starredFirst]);

  const toggleFmt = (f: DeliverableFormat) =>
    setFormats((s) => {
      const next = new Set(s);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });

  const root: CSSProperties = {
    background: tokens.bgPaper,
    color: tokens.ink,
    fontFamily: tokens.ffSans,
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
  };
  const filterRow: CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    padding: "12px 16px",
    borderBottom: `1px solid ${tokens.rule}`,
    alignItems: "center",
  };
  const select: CSSProperties = {
    padding: "5px 8px",
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperCard,
    fontFamily: tokens.ffMono,
    fontSize: 12,
    color: tokens.ink,
  };

  return (
    <div style={root}>
      <div style={filterRow}>
        <select
          value={workflow}
          onChange={(e) => setWorkflow(e.target.value)}
          style={select}
          aria-label={t("sidebar:deliverables.filter.workflow")}
        >
          <option value="">{t("sidebar:deliverables.filter.all_workflows")}</option>
          {workflows.map((w) => (
            <option key={w}>{w}</option>
          ))}
        </select>

        <div style={{ display: "flex", gap: 4 }}>
          {ALL_FORMATS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => toggleFmt(f)}
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                border: `1px solid ${formats.has(f) ? tokens.accent : tokens.rule}`,
                background: formats.has(f) ? tokens.accent : "transparent",
                color: formats.has(f) ? tokens.bgPaperCard : tokens.inkSoft,
                fontFamily: tokens.ffMono,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                cursor: "pointer",
              }}
            >
              {f}
            </button>
          ))}
        </div>

        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            color: tokens.inkSoft,
            marginLeft: "auto",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={starredFirst}
            onChange={(e) => setStarredFirst(e.target.checked)}
          />
          {t("sidebar:deliverables.starred_first")}
        </label>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {rows.length === 0 && (
          <div
            style={{
              padding: "60px 24px",
              textAlign: "center",
              color: tokens.inkFaint,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              alignItems: "center",
            }}
          >
            <Fleuron />
            <p style={{ margin: 0, fontStyle: "italic" }}>
              {t("sidebar:deliverables.empty")}
            </p>
          </div>
        )}

        {rows.map((d) => (
          <DeliverableRowItem
            key={d.id}
            row={d}
            onOpen={() => onOpen(d.id)}
            onStar={() => onStar(d.id, !d.starred)}
            t={t}
          />
        ))}
      </div>
    </div>
  );
};

const DeliverableRowItem: FC<{
  row: DeliverableRow;
  onOpen: () => void;
  onStar: () => void;
  t: (key: string) => string;
}> = ({ row, onOpen, onStar, t }) => (
  <div
    onClick={onOpen}
    onMouseEnter={(e) => (e.currentTarget.style.background = tokens.bgPaperDeep)}
    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    style={{
      height: 48,
      display: "grid",
      gridTemplateColumns: "auto 1fr auto auto",
      gap: 12,
      alignItems: "center",
      padding: "0 16px",
      borderBottom: `1px solid ${tokens.rule}`,
      cursor: "pointer",
      transition: "background 120ms ease",
    }}
  >
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onStar();
      }}
      aria-label={t("sidebar:deliverables.star_aria")}
      style={{
        background: "transparent",
        border: "none",
        cursor: "pointer",
        color: row.starred ? tokens.accent : tokens.inkFaint,
        padding: 0,
        display: "grid",
        placeItems: "center",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill={row.starred ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.3">
        <path d="M8 1.5l2 4.5 4.8.4-3.7 3.2 1.2 4.7L8 11.8l-4.3 2.5 1.2-4.7L1.2 6.4 6 6z" strokeLinejoin="round" />
      </svg>
    </button>

    <span style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
      <span
        style={{
          fontSize: 14,
          color: tokens.ink,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {row.title}
      </span>
      {row.workflow && (
        <span
          style={{
            fontSize: 11,
            color: tokens.inkSoft,
            fontStyle: "italic",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {row.workflow}
        </span>
      )}
    </span>

    <span
      style={{
        fontFamily: tokens.ffMono,
        fontSize: 10,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: tokens.accent,
        border: `1px solid ${tokens.rule}`,
        padding: "2px 6px",
        borderRadius: 3,
      }}
    >
      {row.format}
    </span>

    <span style={{ fontSize: 11, color: tokens.inkFaint, fontFamily: tokens.ffMono }}>
      {humanAgo(row.created_at)}
    </span>
  </div>
);

export default DeliverablesTab;
