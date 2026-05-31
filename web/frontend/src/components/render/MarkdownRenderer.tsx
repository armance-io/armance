import { type CSSProperties, type FC, type ReactNode, useMemo, useState, useCallback } from "react";
import { marked, type Tokens } from "marked";
import { tokens } from "../_shared/armance-tokens";
import { CodeBlock } from "./CodeBlock";
import { MermaidBlock } from "./MermaidBlock";
import { SvgBlock } from "./SvgBlock";
import { InlineImage, type InlineImageProps } from "./InlineImage";

export interface MarkdownRendererProps {
  markdown: string;
  className?: string;
  t: (key: string) => string;
}

/**
 * Tokenizes Markdown with `marked.lexer` and dispatches each block kind to
 * the matching React subcomponent. Standard prose blocks fall back to a
 * `marked.parser`-rendered HTML island styled via `.prose` tokens.
 */
export const MarkdownRenderer: FC<MarkdownRendererProps> = ({
  markdown,
  className,
  t,
}) => {
  const [copied, setCopied] = useState(false);

  const blocks = useMemo(
    () => marked.lexer(markdown, { gfm: true }),
    [markdown],
  );

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* noop */
    }
  }, [markdown]);

  const containerStyle: CSSProperties = {
    color: tokens.ink,
    display: "flex",
    flexDirection: "column",
  };

  const copyBtnStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
    alignSelf: "flex-end",
    border: "none",
    background: "transparent",
    color: copied ? tokens.accent : tokens.inkFaint,
    fontFamily: tokens.ffMono,
    fontSize: 10,
    cursor: "pointer",
    padding: "2px 4px",
    borderRadius: 2,
    transition: "color 160ms ease",
    opacity: 0.7,
  };

  return (
    <div className={`prose ${className ?? ""}`} style={containerStyle}>
      <style>{PROSE_CSS}</style>
      {blocks.map((tok, i) => renderBlock(tok, i, t))}
      <button
        type="button"
        style={copyBtnStyle}
        onClick={() => { void handleCopy(); }}
        aria-label={t("render:code.copy")}
        title={copied ? t("render:code.copied") : t("render:code.copy")}
        className="prose-copy-btn"
      >
        {copied ? (
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="2 8 6 12 14 4" />
          </svg>
        ) : (
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="5" y="2" width="9" height="11" rx="1" />
            <path d="M11 2V1a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h1" />
          </svg>
        )}
      </button>
    </div>
  );
};

function renderBlock(
  tok: Tokens.Generic,
  key: number,
  t: (k: string) => string,
): ReactNode {
  if (tok.type === "code") {
    const lang = ((tok as Tokens.Code).lang || "").toLowerCase().trim();
    const code = (tok as Tokens.Code).text;
    if (lang === "mermaid") return <MermaidBlock key={key} source={code} t={t} />;
    if (lang === "svg") return <SvgBlock key={key} source={code} t={t} />;
    return <CodeBlock key={key} code={code} language={lang || "text"} t={t} />;
  }

  if (tok.type === "paragraph") {
    const para = tok as Tokens.Paragraph;
    const first = para.tokens?.[0];
    // Detect a paragraph that contains a single image token → InlineImage.
    if (para.tokens?.length === 1 && first?.type === "image") {
      const img = first as Tokens.Image;
      const props: InlineImageProps = {
        src: img.href,
        alt: img.text || "",
        t,
      };
      if (img.title) props.caption = img.title;
      return <InlineImage key={key} {...props} />;
    }
  }

  // Fallback: let marked parse this block into HTML.
  const html = marked.parser([tok as Tokens.Generic], { gfm: true });
  return (
    <div
      key={key}
      style={{ display: "contents" }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/* ─── Prose stylesheet ───────────────────────────────────────────────────── */

const PROSE_CSS = `
.prose {
  font-family: ${tokens.ffSans};
  font-size: 16px;
  line-height: 1.7;
  color: ${tokens.ink};
  max-width: 68ch;
}
.prose h1, .prose h2, .prose h3, .prose h4 {
  font-family: ${tokens.ffSerif};
  font-weight: 400;
  color: ${tokens.ink};
  letter-spacing: -0.01em;
  text-wrap: balance;
}
.prose h1 { font-size: 38px; line-height: 1.1; margin: 8px 0 24px; }
.prose h2 { font-size: 28px; line-height: 1.2; margin: 40px 0 16px; }
.prose h3 { font-size: 22px; line-height: 1.25; margin: 32px 0 12px; font-style: italic; }
.prose h4 { font-size: 18px; line-height: 1.3; margin: 24px 0 8px; }
.prose p  { margin: 0 0 18px; text-wrap: pretty; }
.prose a  {
  color: ${tokens.accent};
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-decoration-color: ${tokens.accentSoft};
}
.prose a:hover { text-decoration-color: ${tokens.accent}; }
.prose strong { font-weight: 600; }
.prose em { font-style: italic; }
.prose ul, .prose ol { margin: 0 0 18px; padding-left: 24px; }
.prose li { margin: 4px 0; }
.prose li::marker { color: ${tokens.accent}; }
.prose blockquote {
  margin: 24px 0;
  padding: 4px 0 4px 20px;
  border-left: 2px solid ${tokens.accentSoft};
  font-family: ${tokens.ffSerif};
  font-style: italic;
  font-size: 19px;
  color: ${tokens.inkSoft};
}
.prose hr { border: 0; border-top: 1px solid ${tokens.rule}; margin: 32px 0; }
.prose code {
  font-family: ${tokens.ffMono};
  font-size: 0.88em;
  padding: 2px 6px;
  background: ${tokens.bgPaperDeep};
  color: ${tokens.accentDeep};
  border-radius: 2px;
}
.prose table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }
.prose th, .prose td { padding: 8px 12px; border-bottom: 1px solid ${tokens.rule}; text-align: left; }
.prose th {
  font-family: ${tokens.ffSans};
  font-weight: 600;
  color: ${tokens.inkSoft};
  border-bottom: 1.5px solid ${tokens.inkSoft};
}
`;

export default MarkdownRenderer;
