# `truncate_simulated_turns` is FR-heavy (multilingual hole)

> Status: **known, accepted for now**. Tracked, not fixed.

## Symptom

The defensive scrubber `armance.service.agent_sandbox.truncate_simulated_turns`
detects a runaway *user-line simulation* by spotting acknowledgement
tokens at the start of paragraphs (*Parfait*, *Exact*, *Voilà*, *Got
it*, *Bonne question*, etc.). The token list is hard-coded and mostly
French, with a handful of English tokens.

Armance supports six interface languages (en, fr, es, de, zh, ja). On
any non-FR / non-EN session, the scrubber is effectively a no-op:

- Spanish: *« Perfecto »*, *« Claro »*, *« Vale »* — none in the list.
- German: *« Verstanden »*, *« Klar »*, *« Gut »* — none in the list.
- 中文: *« 好的 »*, *« 明白 »* — none in the list.
- 日本語: *« わかりました »*, *« はい »* — none in the list.

If a small model drifts into Q/A simulation in one of these languages,
the scrubber will not catch it and the user sees the bug again.

## Why we accept this for now

- The original bug surfaced **only** on `claude-haiku-4-5` and only on
  long FR transcripts in V1 prod testing.
- The v23 prompt rewrite (2026-05-24) addresses the *cause* — the
  scrubber is a defensive net, not the primary fix.
- The first multilingual user has not reported the issue.
- A correct fix is non-trivial; doing it half-way (adding ES / DE / ZH
  / JA hard-coded lists) violates the project's no-language-heuristics
  rule and would itself be a regression.

## What "fixed" would look like

Detect the *structure* of a simulated dialogue, not the vocabulary.
A simulated-user line has a non-linguistic signature inside one reply:

- two or more short paragraphs (< ~200 chars)
- alternating between non-interrogative and interrogative paragraphs
- with no speaker marker between them

A `paragraph_structure_score(text)` returning a float in `[0, 1]` based
on:

- variance of paragraph lengths
- ratio of paragraphs ending in `?`
- count of paragraphs shorter than a threshold
- absence of explicit speaker markers

…and cutting when that score crosses ~0.7 would be language-agnostic.

## Acceptance for the fix

- [ ] `truncate_simulated_turns` no longer reads any language-specific
      token list.
- [ ] Synthetic FR and EN regression tests still cut the runaway reply.
- [ ] A new synthetic ES test (the same shape, with *« Perfecto »* /
      *« Claro »* acks) also cuts.
- [ ] No false positive on a legitimate long Mona synthesis with
      embedded questions.

## Trigger to revisit

Bump the priority when a non-FR user reports the user-simulation bug,
or when the user adds another small model to the staff default.
