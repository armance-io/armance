import { type CSSProperties, type FC, useMemo } from "react";
import { marked } from "marked";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export type DeliverableFormat = "md" | "pdf" | "docx" | "pptx";

export interface DeliverableReaderProps {
  /** Document title — rendered in the top bar. */
  title: string;
  /** Raw Markdown source. */
  markdown: string;
  /** URL pointing to the downloadable artefact. */
  downloadUrl: string;
  /** Format of the downloadable artefact (label + filename hint). */
  downloadFormat: DeliverableFormat;
  /** Absolute or workspace-relative path shown in the footer. */
  sourcePath: string;
  /**
   * i18n accessor. Keys consumed:
   *   library:reader.download_aria
   *   library:reader.download_label
   *   library:reader.format.md
   *   library:reader.format.pdf
   *   library:reader.format.docx
   *   library:reader.format.pptx
   *   library:reader.opened_from
   */
  t: (key: string) => string;
}

/* ─── Markdown configuration ─────────────────────────────────────────────── */

const md = new marked.Marked({
  gfm: true,
  breaks: false,
  async: false,
});

/* ─── Component ──────────────────────────────────────────────────────────── */

export const DeliverableReader: FC<DeliverableReaderProps> = ({
  title,
  markdown,
  downloadUrl,
  downloadFormat,
  sourcePath,
  t,
}) => {
  const html = useMemo(
    () => md.parse(markdown, { async: false }) as string,
    [markdown],
  );

  const formatLabel = t(`library:reader.format.${downloadFormat}`);
  const downloadLabel = t("library:reader.download_label");

  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
    background: "var(--bg-paper, #f4ede0)",
    color: "var(--ink, #2a2520)",
  };

  const topBarStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "16px",
    padding: "14px 24px",
    borderBottom: "1px solid var(--rule, #d6c8ad)",
    background: "var(--bg-paper-card, #faf6ef)",
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "20px",
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
    color: "var(--ink, #2a2520)",
    margin: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const downloadStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "8px 16px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "transparent",
    color: "var(--ink, #2a2520)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontWeight: 500,
    letterSpacing: "0.01em",
    textDecoration: "none",
    flexShrink: 0,
    transition:
      "background 160ms ease, border-color 160ms ease, color 160ms ease",
  };

  const formatBadgeStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--accent, #6b4f8a)",
  };

  const scrollStyle: CSSProperties = {
    flex: 1,
    minHeight: 0,
    overflow: "auto",
    padding: "40px 56px 64px",
  };

  const proseStyle: CSSProperties = {
    maxWidth: "68ch",
    margin: "0 auto",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "16px",
    lineHeight: 1.7,
    color: "var(--ink, #2a2520)",
  };

  const footerStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 24px",
    borderTop: "1px solid var(--rule, #d6c8ad)",
    background: "var(--bg-paper-deep, #e8dfcd)",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    flexShrink: 0,
  };

  const footerLabelStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    color: "var(--ink-faint, #9c8e7e)",
  };

  const footerPathStyle: CSSProperties = {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    direction: "rtl",
    textAlign: "left",
  };

  return (
    <article className="deliverable-reader" style={rootStyle}>
      <style>{PROSE_CSS}</style>

      <header style={topBarStyle}>
        <h1 style={titleStyle} title={title}>
          {title}
        </h1>
        <a
          href={downloadUrl}
          download
          aria-label={t("library:reader.download_aria")}
          style={downloadStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--accent, #6b4f8a)";
            e.currentTarget.style.borderColor = "var(--accent, #6b4f8a)";
            e.currentTarget.style.color = "var(--bg-paper-card, #faf6ef)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.borderColor = "var(--rule, #d6c8ad)";
            e.currentTarget.style.color = "var(--ink, #2a2520)";
          }}
        >
          <DownloadIcon />
          <span>{downloadLabel}</span>
          <span style={formatBadgeStyle}>{formatLabel}</span>
        </a>
      </header>

      <div style={scrollStyle}>
        <div
          className="prose"
          style={proseStyle}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>

      <footer style={footerStyle}>
        <span style={footerLabelStyle}>
          {t("library:reader.opened_from")}
        </span>
        <span style={footerPathStyle} dir="ltr" title={sourcePath}>
          {sourcePath}
        </span>
      </footer>
    </article>
  );
};

/* ─── DownloadIcon ───────────────────────────────────────────────────────── */

const DownloadIcon: FC = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M8 2v8" />
    <path d="M4.5 7L8 10.5 11.5 7" />
    <path d="M2.5 13.5h11" />
  </svg>
);

/* ─── Prose stylesheet ───────────────────────────────────────────────────── */

const PROSE_CSS = `
.deliverable-reader .prose h1,
.deliverable-reader .prose h2,
.deliverable-reader .prose h3,
.deliverable-reader .prose h4 {
  font-family: var(--ff-serif, "Instrument Serif", serif);
  font-weight: 400;
  color: var(--ink, #2a2520);
  letter-spacing: -0.01em;
  text-wrap: balance;
}
.deliverable-reader .prose h1 { font-size: 38px; line-height: 1.1; margin: 8px 0 24px; }
.deliverable-reader .prose h2 { font-size: 28px; line-height: 1.2; margin: 40px 0 16px; }
.deliverable-reader .prose h3 { font-size: 22px; line-height: 1.25; margin: 32px 0 12px; font-style: italic; }
.deliverable-reader .prose h4 { font-size: 18px; line-height: 1.3; margin: 24px 0 8px; }

.deliverable-reader .prose p {
  margin: 0 0 18px;
  text-wrap: pretty;
}
.deliverable-reader .prose a {
  color: var(--accent, #6b4f8a);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-decoration-color: var(--accent-soft, #b7a4c9);
}
.deliverable-reader .prose a:hover {
  text-decoration-color: var(--accent, #6b4f8a);
}
.deliverable-reader .prose strong { font-weight: 600; color: var(--ink, #2a2520); }
.deliverable-reader .prose em { font-style: italic; }

.deliverable-reader .prose ul,
.deliverable-reader .prose ol {
  margin: 0 0 18px;
  padding-left: 24px;
}
.deliverable-reader .prose li { margin: 4px 0; }
.deliverable-reader .prose li::marker { color: var(--accent, #6b4f8a); }

.deliverable-reader .prose blockquote {
  margin: 24px 0;
  padding: 4px 0 4px 20px;
  border-left: 2px solid var(--accent-soft, #b7a4c9);
  font-family: var(--ff-serif, "Instrument Serif", serif);
  font-style: italic;
  font-size: 19px;
  line-height: 1.5;
  color: var(--ink-soft, #5b5145);
}

.deliverable-reader .prose hr {
  border: 0;
  border-top: 1px solid var(--rule, #d6c8ad);
  margin: 32px 0;
}

.deliverable-reader .prose code {
  font-family: var(--ff-mono, "JetBrains Mono", monospace);
  font-size: 0.88em;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-paper-deep, #e8dfcd);
  color: var(--accent-deep, #4a3666);
}
.deliverable-reader .prose pre {
  margin: 20px 0;
  padding: 16px 18px;
  border-radius: 6px;
  border: 1px solid var(--rule, #d6c8ad);
  background: var(--bg-paper-deep, #e8dfcd);
  overflow-x: auto;
  line-height: 1.55;
}
.deliverable-reader .prose pre code {
  padding: 0;
  background: transparent;
  color: var(--ink, #2a2520);
  font-size: 13px;
}

.deliverable-reader .prose table {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  font-size: 14px;
}
.deliverable-reader .prose th,
.deliverable-reader .prose td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--rule, #d6c8ad);
  text-align: left;
}
.deliverable-reader .prose th {
  font-family: var(--ff-sans, "Inter", sans-serif);
  font-weight: 600;
  color: var(--ink-soft, #5b5145);
  border-bottom: 1.5px solid var(--ink-soft, #5b5145);
}

.deliverable-reader .prose img {
  border-radius: 4px;
  border: 1px solid var(--rule, #d6c8ad);
  margin: 20px 0;
}

@media (prefers-reduced-motion: reduce) {
  .deliverable-reader * { transition: none !important; }
}
`;

export default DeliverableReader;
