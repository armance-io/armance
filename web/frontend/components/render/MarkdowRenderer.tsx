import { type FC, type ReactNode, useMemo } from "react";
import { marked, type Tokens } from "marked";
import { tokens } from "../_shared/armance-tokens";
import { CodeBlock } from "./CodeBlock";
import { MermaidBlock } from "./MermaidBlock";
import { SvgBlock } from "./SvgBlock";
import { InlineImage } from "./InlineImage";

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
  const blocks = useMemo(
    () => marked.lexer(markdown, { gfm: true }),
    [markdown],
  );

  return (
    <div className={`prose ${className ?? ""}`} style={{ color: tokens.ink }}>
      <style>{PROSE_CSS}</style>
      {blocks.map((tok, i) => renderBlock(tok, i, t))}
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
    // Detect a paragraph that contains a single image token → InlineImage.
    if (para.tokens.length === 1 && para.tokens[0].type === "image") {
      const img = para.tokens[0] as Tokens.Image;
      return (
        <InlineImage
          key={key}
          src={img.href}
          alt={img.text || ""}
          caption={img.title || undefined}
          t={t}
        />
      );
    }
  }

  // Fallback: let marked parse this block into HTML.
  const html = marked.parser([tok as Tokens.Token], { gfm: true });
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
