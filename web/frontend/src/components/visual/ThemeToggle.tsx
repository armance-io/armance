import {
  type CSSProperties,
  type FC,
  useEffect,
  useRef,
  useState,
} from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface ThemeToggleProps {
  /** i18n accessor — key: `visual:theme.toggle_aria` */
  t: (key: string) => string;
  /** Extra classes merged onto the root `<button>`. */
  className?: string;
}

type Theme = "light" | "dark";

/* ─── Constants ──────────────────────────────────────────────────────────── */

const STORAGE_KEY = "armance.theme";

/* SVG path data (Feather-style, 24 × 24 viewBox, stroke-only) */
const PATH_SUN =
  "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z " +
  "M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42" +
  "M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42";
const PATH_MOON = "M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z";

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function commitTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(STORAGE_KEY, theme);
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<ThemeToggle />` — 32 × 32 circular button that toggles `data-theme` on
 * `<html>` and persists the choice to `localStorage` under `armance.theme`.
 *
 * On mount it reads localStorage, falling back to `prefers-color-scheme`.
 * The icon swaps with a 200 ms fade + scale animation (suppressed when
 * `prefers-reduced-motion: reduce` is active).
 *
 * i18n keys:
 *   `visual:theme.toggle_aria` — aria-label of the button.
 */
export const ThemeToggle: FC<ThemeToggleProps> = ({ t, className }) => {
  /* theme tracks what is committed to <html>; icon always mirrors theme */
  const [theme, setTheme]       = useState<Theme>("light");
  /* animating drives the fade-out before the icon swaps */
  const [animating, setAnimating] = useState(false);

  const prefersReduced = useRef<boolean>(
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );

  /* ── mount: read persisted / system preference ── */
  useEffect(() => {
    const initial = resolveInitialTheme();
    setTheme(initial);
    commitTheme(initial);
  }, []);

  /* ── click handler ── */
  function toggle(): void {
    const next: Theme = theme === "light" ? "dark" : "light";

    if (prefersReduced.current) {
      setTheme(next);
      commitTheme(next);
      return;
    }

    /* fade out → swap → fade in */
    setAnimating(true);
    setTimeout(() => {
      setTheme(next);
      commitTheme(next);
      setAnimating(false);
    }, 110);
  }

  /* ── styles ── */
  const buttonStyle: CSSProperties = {
    width: "32px",
    height: "32px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "var(--bg-paper-deep, #e8dfcd)",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    flexShrink: 0,
    padding: 0,
    transition: "border-color 0.20s ease, background 0.20s ease",
  };

  const iconStyle: CSSProperties = {
    width: "15px",
    height: "15px",
    color: "var(--accent, #6b4f8a)",
    opacity:   animating ? 0 : 1,
    transform: animating
      ? "scale(0.65) rotate(30deg)"
      : "scale(1) rotate(0deg)",
    transition: prefersReduced.current
      ? "none"
      : "opacity 0.11s ease, transform 0.20s ease",
  };

  const rootClassName = ["theme-toggle", className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={rootClassName}
      style={buttonStyle}
      onClick={toggle}
      aria-label={t("visual:theme.toggle_aria")}
      aria-pressed={theme === "dark"}
    >
      <svg
        style={iconStyle}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d={theme === "light" ? PATH_SUN : PATH_MOON} />
      </svg>
    </button>
  );
};

export default ThemeToggle;
