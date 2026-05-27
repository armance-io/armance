import { type CSSProperties, type FC, useEffect, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface CodeBlockProps {
  code: string;
  language: string;
  showLines?: boolean;
  t: (key: string) => string;
}

/* Lazy singleton shiki highlighter, loaded on first use. */
let highlighterPromise: Promise<{
  codeToHtml: (code: string, opts: { lang: string; themes: { light: string; dark: string } }) => string;
}> | null = null;

const LIGHT_THEME = "min-light";
const DARK_THEME = "vitesse-dark";

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      const shiki = await import("shiki");
      const hl = await shiki.createHighlighter({
        themes: [LIGHT_THEME, DARK_THEME],
        langs: [
          "ts", "tsx", "js", "jsx", "json", "bash", "sh", "python",
          "html", "css", "md", "yaml", "rust", "go", "sql", "diff",
        ],
      });
      return {
        codeToHtml: (code, opts) =>
          hl.codeToHtml(code, {
            lang: opts.lang as never,
            themes: opts.themes,
            defaultColor: "light",
          }),
      };
    })();
  }
  return highlighterPromise;
}

export const CodeBlock: FC<CodeBlockProps> = ({ code, language, showLines, t }) => {
  const [html, setHtml] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const hl = await getHighlighter();
        const out = hl.codeToHtml(code, {
          lang: language || "text",
          themes: { light: LIGHT_THEME, dark: DARK_THEME },
        });
        if (!cancelled) setHtml(out);
      } catch {
        if (!cancelled) setHtml(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code, language]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* noop */
    }
  };

  const wrap: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    borderRadius: 2,
    margin: "20px 0",
    overflow: "hidden",
    fontFamily: tokens.ffMono,
  };
  const header: CSSProperties = {
    height: 28,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 10px",
    borderBottom: `1px solid ${tokens.rule}`,
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
  const body: CSSProperties = {
    margin: 0,
    padding: 0,
    fontSize: 13,
    lineHeight: 1.55,
    overflowX: "auto",
  };

  return (
    <div style={wrap}>
      <div style={header}>
        <span style={pill} aria-label={t("render:code.lang_aria")}>
          {language || "text"}
        </span>
        <button type="button" style={copyBtn} onClick={handleCopy}>
          {copied ? t("render:code.copied") : t("render:code.copy")}
        </button>
      </div>
      {html ? (
        <div
          style={{ ...body, padding: "12px 14px" }}
          className={showLines ? "code-with-lines" : undefined}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre style={{ ...body, padding: "12px 14px", color: tokens.ink }}>
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
};

export default CodeBlock;
