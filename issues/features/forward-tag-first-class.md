# First-class `[FORWARD:@<agent>]` tag for agent-to-agent forwarding

> Status: **proposed, not started**.
> Carry-over from `roadmap/04_roadmap.md` "Open user-journey decisions".

## Symptom

When an agent wants to hand the conversation to another agent (Kim
asking Malik to recruit a missing role, Armance routing the user to
Mona after `[EXECUTE:/save]`), the convention today is to start a line
with `@<MetaAgent>, <request>`. The dispatcher detects this prefix and
reroutes the next turn.

This works but is a **string convention**, not a contract:

- An agent that varies the phrasing (`@malik :`, `Malik, peux-tu …`,
  `Hey @Malik`) silently fails to forward.
- The dispatcher's regex is fragile and lives in
  `service/tui_bridge.py` separate from the agents' system prompts that
  emit the convention.
- No way to chain a forward with a structured payload (role spec, scope
  hint) without baking it into prose.

## Goal

Promote the forwarding to a first-class `[FORWARD:@<agent>]` tag
following the same pattern as `[EXECUTE:/...]`:

- Per-role allow-list in `service/agent_sandbox.py` (each meta-agent
  may forward to a defined subset).
- Optional payload: `[FORWARD:@Malik]` on its own line followed by a
  short instruction block (no YAML required — natural-language request
  is fine, but the *intent* is now structured).
- Dispatcher intercepts the tag the same way it intercepts
  `[EXECUTE:/...]`: removes the tag, switches `current_agent`, queues
  the payload for the target.

## Implementation sketch

| Step | File | Notes |
|---|---|---|
| 1 | `service/agent_sandbox.py` | add `_ROLE_FORWARD_ALLOWLIST` (Armance → Malik/Kim/Mona; Kim → Malik; etc.) |
| 2 | `service/tui_bridge.py` | replace the `@<name>` regex sniff with `[FORWARD:@<name>]` parser; keep the legacy regex with a deprecation warning for one cycle |
| 3 | meta-agent system prompts | switch every example of `@Malik, …` to `[FORWARD:@Malik]` followed by the request |
| 4 | tests | round-trip forward through `dispatch_input`; assert scrubbed tag, switched agent, payload delivered |

## Acceptance

- [ ] Armance emits `[FORWARD:@Malik]` after `[EXECUTE:/save]` when the
      user opts for the brainstorm route.
- [ ] Kim emits `[FORWARD:@Malik]` when she needs a missing role.
- [ ] Legacy `@Malik, …` still resolves (1 cycle), with a `logger.warning`.
- [ ] Tag scrubber strips a `[FORWARD:@X]` emitted by an agent not
      allowed to forward to `X`.
