# Reorder Armance → Kim → Malik flow

> Status: **partial mitigation shipped, full reorder pending**.
> Carry-over from `roadmap/04_roadmap.md` "Open user-journey decisions".

## Symptom

Current flow: Armance frames → Malik recruits → Kim designs the
workflow. Malik picks the roster without knowing what workflow Kim is
going to design, so Kim often re-asks for skills Malik already chose, or
inherits a team whose shape doesn't fit the workflow strategy. This
creates role duplication and a step of negotiation between the two
agents that the user can hear.

## Desired flow

Armance frames → Kim picks the workflow shape (and therefore the roles
needed) → Kim asks Malik to fill those roles → Malik recruits to the
spec.

If the user just wants to chat (no workflow), Armance routes directly to
a specialist (recruiting on demand via Malik if needed) and skips Kim
altogether.

## Mitigation already shipped

Kim's prompt instructs her to **reuse the Malik roster** when possible.
She emits `@Malik, recrute <missing>` only if a role is missing and
nobody can stretch into it. The dispatcher forwards the request. This
removes most of the duplication but does not change the order — Kim
still arrives after Malik has cast.

## Pending work

- Armance's framing prompt: after `[EXECUTE:/save]`, default routing is
  **Kim** (not Malik), unless the user explicitly asks for a chat with
  a specialist.
- Kim's first message asks the workflow goal + deliverable, then names
  the roles needed (still without recruiting), then hands off to Malik
  with a precise role spec.
- Malik recruits to spec. The agent name returns to Kim, who then runs
  the workflow.

## Acceptance

- [ ] A fresh project, framed and saved, routes by default to Kim.
- [ ] Kim names roles before any agent is created.
- [ ] Malik recruits exactly the roles Kim asked for, with the
      disagreement axis Kim specified.
- [ ] If the user asks for "a quick chat with an expert", Armance routes
      to Malik for a single-agent recruit + drops the user into DM
      chat — Kim is skipped.
