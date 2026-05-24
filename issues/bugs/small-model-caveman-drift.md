# Small models drift to telegraphic register on long transcripts

> Status: **mitigated again by the v23 prompt rewrite (2026-05-24)**.
> First v22 rewrite was not enough — Haiku 4.5 still drifted after
> three turns, and started referring to a *« caveman mode »* by name
> because the word appeared in the prompt's *Forbidden* lists.

## Symptom

When a user-facing meta-agent (Armance, Malik, Kim, Mona, Serge) runs on
a small model (Haiku 4.5, Gemini Flash, free-tier 7B/8B) and the
conversation transcript grows past a handful of turns, the agent's reply
register drifts toward telegraphic prose: missing articles, fragments
without verbs, stacked headings instead of paragraphs, em-dash chains.
The voice the user signed up for — Belle Époque host, quiet recruiter,
sharp VP — disappears.

## Cause

Three reinforcing factors:

1. **Persona pressure** — phrases like *« short sentences »*, *« no
   padding »*, *« crisp »* are interpreted by a small model as
   *clipping*, not as *precision*. The model maximises what it
   understands as the explicit signal.
2. **Mimicry on history** — once the assistant has emitted one
   clipped reply (often early, on a list of pending docs), every
   subsequent reply is mimicked from the transcript pattern. The drift
   compounds turn by turn.
3. **No positive register anchor** — until the v22 rewrite, the prompts
   described the persona abstractly without showing concrete examples of
   *good* output the model could imitate.

## Mitigations shipped

**v22 (2026-05-24, first attempt) — partial.** All five meta-agent
prompts rewritten with bio sections, *Voice — concrete examples* with
`❌ Bad` / `✅ Good` pairs, *Forbidden* lists, and a *Cadence* paragraph
for Armance. Defensive `truncate_simulated_turns` scrubber added.
Caveman A2A policy made explicit in `service/handlers.py` (workflow
`judge` / `deliverable` steps = `caveman_level="none"`, other steps =
`"ultra"`).

**v22 was insufficient.** Haiku 4.5 still drifted after a few turns and,
worse, started referring to *« caveman mode »* by name — because the
*Forbidden* lists contained the word *caveman* multiple times. The
model treated that word as a system mode it could switch on and off,
and at one point literally wrote *« Caveman revert un instant »* mid
reply.

**v23 (2026-05-24, second attempt) — current.**

- The word *caveman* is now banned from every prompt body. The
  `caveman_level: none` field stays in the frontmatter (it gates the
  protocol overlay file, not the persona text).
- Each prompt was shortened to ~80–100 lines. The pattern that hurt was
  *too many `❌ Bad` examples*: a small model imitates the *Bad*
  examples it sees (the Q/A simulation pattern shipped with the
  examples themselves). v23 keeps **one positive cadence example** per
  agent — no `❌ Bad` blocks at all.
- *Iron rules* moved to the top of every prompt, in 5 numbered lines.
  Rule 1 is always: *« Your reply contains only your voice. Never
  write the user's reply, never simulate a dialogue. »*
- POV is consistent (second person throughout, no slipping between
  *« She »* and *« You »*).
- The `truncate_simulated_turns` scrubber threshold dropped from 3 to 2
  acknowledgements, and the token list expanded with the FR forms that
  Haiku used in the 2026-05-24 prod session (*« voilà »*, *« exactement »*,
  *« c'est ça »*, *« bonne question »*, *« tout à fait »*).

## Remaining risk

Even with the v22 prompts, a sufficiently small / hot / unfamiliar
model may still drift on a long transcript. The mitigations above raise
the bar but do not formally bound the failure.

## Possible fixes (if drift resurfaces)

- **Stronger model floor for meta-agents.** Recommend Sonnet-tier or
  better in `armance init`; warn when the user picks a sub-Sonnet
  default for the staff.
- **Periodic register re-anchoring.** Inject the *Voice — concrete
  examples* section every N turns (cheap, ~150 tokens) so it stays in
  the active context window even on small models with aggressive
  attention decay.
- **Reply linter.** A regex-based linter that flags fragments without
  verbs / stacked headings in the agent reply and asks the model for
  a rewrite. Costs one extra call on flagged replies only. Useful as a
  fallback if prompt-level fixes prove insufficient.

## Acceptance for the latent fix

- [ ] On a 20-turn conversation with Haiku 4.5, Armance's last reply
      still reads in complete, articulated sentences (manually verified
      against the *Voice — concrete examples* good column).
- [ ] No reply in the same conversation triggers `truncate_simulated_turns`.
