"use client";

import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Fleuron } from "@/components/visual/Fleuron";
import { ThemeToggle } from "@/components/visual/ThemeToggle";
import { login } from "@/lib/api";

/**
 * Sanitise the post-login `next` target. `next` comes from the URL and is
 * attacker-controllable, so only a same-origin **relative** path is allowed —
 * anything else (absolute URL, scheme-relative `//host`, backslash trick)
 * falls back to "/". Prevents an open redirect.
 */
function safeNext(raw: string | null): string {
  const v = raw || "/";
  if (v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/\\")) {
    return v;
  }
  return "/";
}

/**
 * Epic S · login screen. Asks for the access token / password and exchanges
 * it for an HttpOnly session cookie. Also performs SEC5 auto-login: a
 * ``?token=`` in the URL is verified, stored via the cookie, and stripped.
 *
 * Styling follows web/frontend/DESIGN.md (Belle-Époque parchment charte):
 * centred card with sharp corners, fleuron, serif display, violet action.
 */
export default function LoginPage() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(true);

  // SEC5 — auto-login from a ?token= query param, then clean the URL.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    const next = safeNext(params.get("next"));
    if (!urlToken) {
      setBusy(false);
      return;
    }
    let cancelled = false;
    void login(urlToken).then((ok) => {
      if (cancelled) return;
      if (ok) {
        // Strip the token from the address bar before navigating on.
        window.location.replace(next);
      } else {
        setError(true);
        setBusy(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(false);
    const ok = await login(token.trim());
    if (ok) {
      const next = safeNext(new URLSearchParams(window.location.search).get("next"));
      window.location.replace(next);
      return;
    }
    setError(true);
    setBusy(false);
  }

  const page: CSSProperties = {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-paper, #f4ede0)",
    padding: "2rem",
  };
  const card: CSSProperties = {
    width: "100%",
    maxWidth: 420,
    background: "var(--bg-paper-card, #faf6ef)",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: 2,
    padding: "2.5rem 2rem",
    textAlign: "center",
    boxShadow: "0 1px 0 var(--rule-soft, #e8dfcd)",
  };
  const title: CSSProperties = {
    fontFamily: "var(--ff-display, 'Instrument Serif', Georgia, serif)",
    fontSize: "2.2rem",
    color: "var(--ink, #2a2520)",
    margin: "0.5rem 0 0.25rem",
  };
  const prompt: CSSProperties = {
    fontFamily: "var(--ff-body, Inter, sans-serif)",
    color: "var(--ink-soft, #5b5145)",
    fontSize: "0.95rem",
    margin: "0 0 1.5rem",
  };
  const input: CSSProperties = {
    width: "100%",
    boxSizing: "border-box",
    padding: "0.7rem 0.8rem",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "0.95rem",
    color: "var(--ink, #2a2520)",
    background: "var(--bg-paper, #f4ede0)",
    border: `1px solid var(--${error ? "danger" : "rule"}, ${error ? "#a44141" : "#d6c8ad"})`,
    borderRadius: 2,
    marginBottom: "1rem",
  };
  const button: CSSProperties = {
    width: "100%",
    padding: "0.7rem 1rem",
    fontFamily: "var(--ff-body, Inter, sans-serif)",
    fontWeight: 500,
    fontSize: "0.95rem",
    color: "#faf6ef",
    background: "var(--accent, #6b4f8a)",
    border: "none",
    borderRadius: 2,
    cursor: busy ? "default" : "pointer",
    opacity: busy ? 0.6 : 1,
  };
  const errorText: CSSProperties = {
    color: "var(--danger, #a44141)",
    fontFamily: "var(--ff-body, Inter, sans-serif)",
    fontSize: "0.85rem",
    margin: "0 0 1rem",
  };

  return (
    <div style={page} data-testid="login-page">
      <div style={{ position: "fixed", top: "1rem", right: "1rem" }}>
        <ThemeToggle t={t} />
      </div>
      <form style={card} onSubmit={onSubmit}>
        <Fleuron />
        <h1 style={title}>{t("auth:title")}</h1>
        <p style={prompt}>{t("auth:prompt")}</p>
        {error && (
          <p style={errorText} data-testid="login-error">
            {t("auth:error")}
          </p>
        )}
        <input
          type="password"
          style={input}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder={t("auth:placeholder")}
          autoFocus
          data-testid="login-input"
        />
        <button
          type="submit"
          style={button}
          disabled={busy || token.trim().length === 0}
          data-testid="login-submit"
        >
          {busy ? t("auth:checking") : t("auth:submit")}
        </button>
      </form>
    </div>
  );
}
