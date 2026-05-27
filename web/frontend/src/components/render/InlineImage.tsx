import { type CSSProperties, type FC, useEffect, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface InlineImageProps {
  src: string;
  alt: string;
  caption?: string | undefined;
  t: (key: string) => string;
}

export const InlineImage: FC<InlineImageProps> = ({ src, alt, caption, t }) => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const thumb: CSSProperties = {
    maxWidth: "100%",
    border: `1px solid ${tokens.rule}`,
    borderRadius: 0,
    margin: "20px 0",
    cursor: "zoom-in",
    display: "block",
  };

  const lightbox: CSSProperties = {
    position: "fixed",
    inset: 0,
    background: `color-mix(in oklab, ${tokens.bgPaper} 95%, transparent)`,
    display: "grid",
    placeItems: "center",
    zIndex: 1000,
    padding: 32,
    cursor: "zoom-out",
    transition: "opacity 200ms ease",
  };

  return (
    <>
      <figure style={{ margin: "20px 0" }}>
        <img
          src={src}
          alt={alt}
          style={thumb}
          onClick={() => setOpen(true)}
          loading="lazy"
        />
        {caption && (
          <figcaption
            style={{
              fontSize: 12,
              fontStyle: "italic",
              color: tokens.inkSoft,
              textAlign: "center",
              marginTop: 6,
            }}
          >
            {caption}
          </figcaption>
        )}
      </figure>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t("render:image.lightbox_aria")}
          style={lightbox}
          onClick={() => setOpen(false)}
        >
          <img
            src={src}
            alt={alt}
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              border: `1px solid ${tokens.rule}`,
              background: tokens.bgPaperCard,
            }}
          />
          <button
            type="button"
            aria-label={t("render:image.close_aria")}
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
            }}
            style={{
              position: "absolute",
              top: 20,
              right: 20,
              width: 36,
              height: 36,
              borderRadius: 999,
              border: `1px solid ${tokens.rule}`,
              background: tokens.bgPaperCard,
              color: tokens.ink,
              cursor: "pointer",
              fontSize: 18,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>
      )}

      <style>{`@media (prefers-reduced-motion: reduce){[role="dialog"]{transition:none!important;}}`}</style>
    </>
  );
};

export default InlineImage;
