---
governs: [src/armance/web/, src/armance/transport/, web/frontend/src/, web/frontend/e2e/]
depends: [chat-dispatch]
---
# web-layer

The local web interface: a FastAPI backend, a pure transport adapter over `Storage`, and a Next.js frontend shipped
as a static bundle, both served from the user's machine by `armance web`. It plays back the conversation, roster,
workflows, library and renders through REST routes and an SSE stream. By doctrine it is a local single-user UI, never
a hosted or multi-tenant service: single writer, files on disk as the source of truth, LAN clients read-only.

Constraints and non-goals:

- One owner secret, configured or generated: no accounts, no tenants, no server database.
- Fail-closed: every data route outside `/healthz` and `/auth/*` needs the secret, on both mounts (root and `/api`).
- No business logic and no LLM call in the backend; no direct `Path.write_*`.
- URLs follow `/projects/{pid}/sessions/{sid}/...`. Without a frontend build, the backend starts API-only.

Criteria:

- A data route without credentials, or with a bad token, answers 401, also on the root mount:
  [test_api_route_without_credentials_is_401](../../src/armance/web/backend/tests/test_s_security_gate.py),
  [test_api_route_with_bad_token_is_401](../../src/armance/web/backend/tests/test_s_security_gate.py),
  [test_root_mounted_data_routes_are_also_gated](../../src/armance/web/backend/tests/test_s_security_gate.py).
- Login sets the cookie and refuses a bad secret:
  [test_auth_login_sets_cookie](../../src/armance/web/backend/tests/test_s_security_gate.py),
  [test_auth_login_rejects_bad_secret](../../src/armance/web/backend/tests/test_s_security_gate.py).
- Static assets are served without the secret, data routes stay gated, no path traversal:
  [test_data_route_still_gated](../../src/armance/web/backend/tests/test_static_assets_ungated.py),
  [test_no_path_traversal_via_static](../../src/armance/web/backend/tests/test_static_assets_ungated.py).
- Events reach the client as a server-sent stream:
  [test_events_generator_delivers_events](../../src/armance/web/backend/tests/test_events.py).
- Binding to the LAN prints a warning: [test_lan_warning_printed_on_bind_0000](../../src/armance/web/backend/tests/test_lan_bind.py).
