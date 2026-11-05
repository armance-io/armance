# Launcher auto-login passes the long-lived web secret in the URL

> Status: **known, accepted for now** (recorded 2026-06-10, flagged by
> automated security review on the `feat/grandma-launcher` merge).
> MEDIUM. The sibling HIGH finding (missing loopback gate on
> `/launcher/open`) was fixed the same day.

## Symptom

`cli.py` (launcher path) opens the browser at
`http://127.0.0.1:8000/...?token=<secret>` when the secret was
auto-generated. The SPA exchanges it for the HttpOnly session cookie
and strips it via `history.replaceState` (SEC5), but the secret still
transits in a URL: it can land in browser history (the initial entry)
and in any access log that records the query string.

## Why accepted for now

- The server is loopback-only and the secret is auto-generated (not a
  user password reused elsewhere).
- The URL is opened locally in the user's own browser by the CLI; it
  is never sent over a network beyond 127.0.0.1.
- The SPA strips the token from the address bar immediately after the
  cookie exchange.

## What "fixed" looks like

Mint a short-lived one-shot login nonce (random bytes, single use,
~60s TTL) at launch; pass THAT in the query string; the backend
exchanges it for the session cookie and burns it. The long-lived
secret never appears in a URL. Also exclude the `token` query param
from the uvicorn access log format.

## Trigger to revisit

Before any deployment where the web server binds beyond loopback
(LAN mode, V3 cloud), this becomes a hard blocker.
