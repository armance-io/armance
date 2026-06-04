import {
  type CSSProperties,
  type FC,
  useState,
} from "react";
import { DeliverableReader } from "@/components/library/DeliverableReader";
import { ArgumentLedger } from "@/components/run/ArgumentLedger";
import { SourceList } from "@/components/run/SourceList";
import { HypothesisList } from "@/components/hypotheses/HypothesisList";

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface Deliverable {
  title: string;
  markdown: string;
  downloadUrl: string;
  format: "md" | "pdf" | "docx" | "pptx";
}

interface Argument {
  id: string;
  claim: string;
  status: "retained" | "rejected" | "open";
  proposed_by: string[];
  proposed_in_steps: string[];
  rejected_by?: string;
  rejection_reason?: string;
  sources: string[];
  weight?: number;
}

interface Source {
  id: string;
  kind: "doc" | "user_msg" | "web";
  ref: string;
  label: string;
}

interface Hypothesis {
  step_id: string;
  text: string;
  invalidator?: string;
}

interface Download {
  format: string;
  url: string;
}

export interface LivePanelProps {
  mode: "interactive" | "autonomous";
  deliverable: Deliverable;
  arguments: Argument[];
  sources: Source[];
  hypotheses: Hypothesis[];
  downloads: Download[];
  t: (key: string) => string;
}

/* ─── Collapsible Section ────────────────────────────────────────────────── */

const Section: FC<{
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}> = ({ title, defaultOpen = true, children }) => {
  const [open, setOpen] = useState(defaultOpen);

  const headerStyle: CSSProperties = {
    position: "sticky",
    top: 0,
    zIndex: 5,
    background: "var(--bg-paper, #f4ede0)",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "12px 0",
    cursor: "pointer",
    borderBottom: "1px solid var(--rule, #d6c8ad)",
    userSelect: "none",
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "17px",
    color: "var(--ink, #2a2520)",
    flex: 1,
  };

  const chevronStyle: CSSProperties = {
    width: "12px",
    height: "12px",
    color: "var(--ink-faint, #9c8e7e)",
    transform: open ? "rotate(90deg)" : "rotate(0deg)",
    transition: "transform 160ms ease",
    flexShrink: 0,
  };

  const bodyStyle: CSSProperties = {
    padding: open ? "16px 0" : "0",
    maxHeight: open ? "9999px" : "0",
    overflow: "hidden",
  };

  return (
    <div>
      <button
        style={headerStyle}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <svg
          style={chevronStyle}
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 4l4 4-4 4" />
        </svg>
        <span style={titleStyle}>{title}</span>
      </button>
      <div style={bodyStyle}>{children}</div>
    </div>
  );
};

/* ─── Fleuron separator ──────────────────────────────────────────────────── */

const Fleuron: FC = () => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: "14px",
      padding: "12px 0",
    }}
    aria-hidden="true"
  >
    <span
      style={{
        width: "40px",
        height: 0,
        borderTop: "1px solid var(--rule, #d6c8ad)",
      }}
    />
    <span
      style={{
        fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
        fontSize: "14px",
        color: "var(--accent, #6b4f8a)",
        lineHeight: 1,
      }}
    >
      ❦
    </span>
    <span
      style={{
        width: "40px",
        height: 0,
        borderTop: "1px solid var(--rule, #d6c8ad)",
      }}
    />
  </div>
);

/* ─── Main Component ─────────────────────────────────────────────────────── */

export const LivePanel: FC<LivePanelProps> = ({
  mode,
  deliverable,
  arguments: args,
  sources,
  hypotheses,
  downloads,
  t,
}) => {
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);

  const handleSourceClick = (sourceId: string) => {
    const element = document.getElementById(`source-row-${sourceId}`);
    if (element) {
      const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      element.scrollIntoView({
        behavior: prefersReduced ? "auto" : "smooth",
        block: "nearest",
      });

      setHighlightedSourceId(sourceId);
      setTimeout(() => {
        setHighlightedSourceId(null);
      }, 600);
    }
  };

  const sourcesById = Object.fromEntries(
    sources.map((s) => [s.id, { kind: s.kind, ref: s.ref, label: s.label }]),
  );

  const rootStyle: CSSProperties = {
    width: "420px",
    height: "100%",
    overflow: "auto",
    background: "var(--bg-paper, #f4ede0)",
    borderLeft: "1px solid var(--rule, #d6c8ad)",
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: "0",
  };

  const modeChipStyle: CSSProperties = {
    alignSelf: "flex-end",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    padding: "3px 10px",
    borderRadius: "999px",
    border: "1px solid var(--accent-soft, #b7a4c9)",
    color: "var(--accent, #6b4f8a)",
    marginBottom: "12px",
  };

  const downloadRowStyle: CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    padding: "8px 0",
  };

  const dlBtnStyle: CSSProperties = {
    padding: "6px 14px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "transparent",
    color: "var(--ink, #2a2520)",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    textDecoration: "none",
    cursor: "pointer",
    transition: "background 120ms ease, border-color 120ms ease",
  };

  // Removed unused inline source list styles

  return (
    <div style={rootStyle}>
      <style>{`
        @media (max-width: 860px) {
          .live-panel-root { width: 100% !important; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>

      {/* 1. Mode chip */}
      <span style={modeChipStyle}>
        {t(`run:panel.mode.${mode}`)}
      </span>

      {/* 2. Deliverable */}
      <Section title={t("run:panel.deliverable")} defaultOpen>
        <div style={{ height: "360px", border: "1px solid var(--rule, #d6c8ad)", borderRadius: "4px", overflow: "hidden" }}>
          <DeliverableReader
            title={deliverable.title}
            markdown={deliverable.markdown}
            downloadUrl={deliverable.downloadUrl}
            downloadFormat={deliverable.format}
            sourcePath={deliverable.downloadUrl}
            t={t}
          />
        </div>
      </Section>

      <Fleuron />

      {/* 3. Arguments */}
      <Section title={t("run:panel.arguments")}>
        <ArgumentLedger
          arguments={args}
          sourcesById={sourcesById}
          onClickSource={handleSourceClick}
          t={t}
        />
      </Section>

      <Fleuron />

      {/* 4. Sources */}
      <Section title={t("run:panel.sources")}>
        <SourceList
          sources={sources}
          onClickSource={(src) => handleSourceClick(src.id)}
          highlightedId={highlightedSourceId}
          t={t}
        />
      </Section>

      <Fleuron />

      {/* 5. Hypotheses */}
      {hypotheses.length > 0 && (
        <>
          <Section title={t("run:panel.hypotheses")}>
            <HypothesisList hypotheses={hypotheses} t={t} />
          </Section>
          <Fleuron />
        </>
      )}

      {/* 6. Downloads */}
      {downloads.length > 0 && (
        <Section title={t("run:panel.downloads")}>
          <div style={downloadRowStyle}>
            {downloads.map((dl) => (
              <a
                key={dl.format}
                href={dl.url}
                download
                style={dlBtnStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background =
                    "var(--bg-paper-deep, #e8dfcd)";
                  e.currentTarget.style.borderColor =
                    "var(--ink-soft, #5b5145)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.borderColor =
                    "var(--rule, #d6c8ad)";
                }}
              >
                {dl.format}
              </a>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

export default LivePanel;
