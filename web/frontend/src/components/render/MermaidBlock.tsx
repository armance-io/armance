import { type CSSProperties, type FC, useEffect, useRef, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface MermaidBlockProps {
  source: string;
  t: (key: string) => string;
}

let idCounter = 0;
const nextId = () => `mmd-${++idCounter}-${Date.now()}`;

export const MermaidBlock: FC<MermaidBlockProps> = ({ source, t }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaidMod = await import("mermaid");
        const mermaid = mermaidMod.default;

        const prefersReduced =
          typeof window !== "undefined" &&
          window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

        const cssVar = (name: string, fallback: string): string => {
          if (typeof window === "undefined") return fallback;
          const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
          return v || fallback;
        };

        mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          securityLevel: "strict",
          themeVariables: {
            background: cssVar("--bg-paper-deep", "#e8dfcd"),
            primaryColor: cssVar("--accent", "#6b4f8a"),
            primaryTextColor: cssVar("--ink", "#2a2520"),
            primaryBorderColor: cssVar("--rule", "#d6c8ad"),
            lineColor: cssVar("--ink-soft", "#5b5145"),
            secondaryColor: cssVar("--bg-paper-card", "#faf6ef"),
            tertiaryColor: cssVar("--bg-paper", "#f4ede0"),
            edgeLabelBackground: "transparent",
            fontFamily: cssVar("--ff-sans", "Inter, sans-serif"),
          },
          flowchart: { useMaxWidth: true },
          ...(prefersReduced ? { sequence: { mirrorActors: false } } : {}),
        });

        const { svg } = await mermaid.render(nextId(), source);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          if (prefersReduced) {
            ref.current
              .querySelectorAll("svg *")
              .forEach((el) => ((el as SVGElement).style.animation = "none"));
          }
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source]);

  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* noop */
    }
  };

  const container: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    borderRadius: 2,
    margin: "20px 0",
    overflow: "hidden",
  };

  const header: CSSProperties = {
    height: 28,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 10px",
    borderBottom: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperCard,
  };

  const pill: CSSProperties = {
    fontFamily: tokens.ffMono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: tokens.inkSoft,
  };

  const copyBtn: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: "transparent",
    color: tokens.inkSoft,
    fontFamily: tokens.ffMono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    padding: "2px 8px",
    cursor: "pointer",
    borderRadius: 2,
  };

  const wrap: CSSProperties = {
    background: tokens.bgPaperDeep,
    padding: 16,
    overflowX: "auto",
    textAlign: "center",
  };

  if (error) {
    return (
      <div style={{ ...wrap, border: `1px solid ${tokens.rule}`, borderRadius: 2, margin: "20px 0" }}>
        <Chip label={t("render:mermaid.error_title")} />
        <pre
          style={{
            margin: "12px 0 0",
            padding: 12,
            background: tokens.bgPaper,
            border: `1px solid ${tokens.rule}`,
            fontFamily: tokens.ffMono,
            fontSize: 12,
            color: tokens.inkSoft,
            textAlign: "left",
            overflow: "auto",
          }}
        >
          {source}
        </pre>
        <p
          style={{
            margin: "8px 0 0",
            color: tokens.inkFaint,
            fontSize: 12,
            fontStyle: "italic",
          }}
        >
          {t("render:mermaid.error_hint")}
        </p>
      </div>
    );
  }

  return (
    <div style={container}>
      <div style={header}>
        <span style={pill}>MERMAID</span>
        <button type="button" style={copyBtn} onClick={handleCopy}>
          {copied ? t("render:code.copied") : t("render:code.copy")}
        </button>
      </div>
      <div style={wrap} ref={ref} />
    </div>
  );
};

const Chip: FC<{ label: string }> = ({ label }) => (
  <span
    style={{
      display: "inline-block",
      padding: "3px 10px",
      borderRadius: 999,
      border: `1px solid ${tokens.accentSoft}`,
      background: tokens.bgPaperCard,
      color: tokens.accentDeep,
      fontFamily: tokens.ffMono,
      fontSize: 11,
      textTransform: "uppercase",
      letterSpacing: "0.08em",
    }}
  >
    {label}
  </span>
);

export default MermaidBlock;
