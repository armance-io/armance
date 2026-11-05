# Multimodal capabilities — transverse V1 + V2 + V3

> Status: **partial, transverse** (verified 2026-06-04 on
> `feat/environmental-impact`). `judge_model` removed; `capability_models`
> on `Agent`. Web render shipped (`components/render/MarkdownRenderer.tsx`,
> `MermaidBlock.tsx`). Voice **frontend** shipped but **not backed**
> (`components/audio/{VoiceInput,AudioReply}.tsx` call an `sttUrl`/TTS URL,
> but there is no STT/TTS route in `web/backend`). Vision/OCR + image
> generation still unbuilt. Touches V1 (CLI), V2 (web local), V3 (SaaS);
> each section flags its phase.
> Part of `web-layer-stories.md`.

## Why

V1 indexes text-only documents. The user wants to drop images, PDFs
without OCRed text, mixed corpora — and have the firm reason over
them. The user also wants agents to **answer visually** when a
schema beats a paragraph (Mermaid, SVG). And, as a product principle:
"un workflow peut produire des images, des schémas, des PDFs avec
images insérées" — outputs are also multimodal.

V3 SaaS extends this to voice (STT input, TTS output) and to a
broader catalogue of generation models.

## Scope

| Phase | Capability | Spec section |
|---|---|---|
| **V1** | Restructure config: kill `judge_model`, introduce extensible `capability_models` dict | §1 |
| **V1** | Vision / OCR model — accept images + scanned PDFs in the library, LLM-driven (no Tesseract) | §2 |
| **V1** | Image generation model — Mona / specialists can produce diagrams via `[EXECUTE:/generate-image:<prompt>]` | §3 |
| **V2** | Render Markdown + code highlight + Mermaid + SVG (sanitised) in the chat | §4 |
| **V2** | Visual overlay — runtime instruction to staff agents on web client: *« vous pouvez glisser un bloc mermaid ou svg »* | §5 |
| **V2** | Mermaid pre-render to SVG for PDF deliverables (Python lib, no headless chrome — keep simple) | §6 |
| **V2** | Auto-discovery proposal — Armance proposes a vision model the first time an image is dropped | §7 |
| **V3** | Speech-to-text + text-to-speech (asymmetric → user speaks, agents reply text + TTS) | §8 |
| **V4** | Realtime voice agent (streaming STT + streaming TTS, conversational) | logged in `web-v4-collaboration.md` |

## §1 — Config: kill `judge_model`, introduce `capability_models`

### Current state (V1)

`armance.config.Config` has `default_model`, `judge_model`,
`embedding_model`. `judge_model` is a legacy field that should not
exist anymore — the judge step uses the configured Mona agent's own
model, not a global override.

### Target shape

```python
@dataclass
class ModelBinding:
    provider: str           # openrouter | gemini | claude-code | custom-openai
    model: str              # vendor model id
    reasoning: Reasoning | None = None

CapabilityKey = Literal[
    "chat",                 # default chat completion (was "default_model")
    "embedding",            # was "embedding_model"
    "vision",               # new — image / scanned PDF understanding
    "image_gen",            # new — diagram / image generation
    "tts",                  # V3 only
    "stt",                  # V3 only
]

@dataclass
class Config:
    providers: list[ProviderConfig]
    capability_models: dict[CapabilityKey, ModelBinding]
    language: Language
    budget_effort: BudgetEffort
    log_level: LogLevel
    prices: dict[str, ModelPriceOverride]
```

The dict is **extensible** — adding `pdf_render` or `audio_describe`
later does not require a schema migration.

A capability is **active** iff `capability_models[key]` is set with
a non-empty `model`. The UI / agent prompts gate features on
activeness:

- Library accepts image uploads iff `vision` is active.
- `[EXECUTE:/generate-image:...]` tag scrubber rejects the tag iff
  `image_gen` is inactive.
- TTS controls hidden iff `tts` is inactive.

### Breaking changes

We are alpha; no backward compatibility. Migration: existing
`config.yaml` files have `default_model` and `embedding_model` at
the top level; a one-shot migrator on `armance run` rewrites them
into `capability_models.chat` / `.embedding`. `judge_model` is
dropped silently with a logged warning.

### Tasks

```
M.1 — Config refactor
  1. Delete `Config.judge_model`.
  2. Replace `Config.default_model` / `Config.embedding_model` with
     `Config.capability_models: dict[CapabilityKey, ModelBinding]`.
  3. Migrator: on load, if old fields present → rewrite + warn.
  4. Update every caller (~15 call sites across providers, service,
     agents).
  5. Tests: round-trip old YAML → new shape. Missing capability →
     `KeyError` with helpful message.

M.2 — Capability gate helpers
  1. `armance.config.is_capability_active(cfg, "vision") -> bool`.
  2. `armance.config.get_binding(cfg, "vision") -> ModelBinding`
     raises `CapabilityNotConfiguredError` if absent.
  3. Tests.

M.3 — Update `armance init`
  1. Wizard writes `capability_models.chat` (instead of
     `default_model`) and `capability_models.embedding`.
  2. The wizard does NOT ask about vision / image_gen / tts / stt
     at first run — those are configured on demand
     (auto-discovery, see §7).
```

## §2 — Vision / OCR pipeline

### Approach

LLM vision model. No Tesseract. The model both transcribes any text
present and describes the image. Output = Markdown blob indexed like
any other doc.

### Pipeline

```
.armance/docs/<file>   (.png|.jpg|.webp|.tiff|.pdf-without-text)
   │
   │  /library-index (vision branch)
   ▼
storage/vision_ingestion.py
   │  - detect format
   │  - call capability_models["vision"] with the image bytes
   │  - cache result by sha256(file_bytes) in
   │    .armance/vector/vision_cache/<sha>.md
   │  - return Markdown description + extracted text
   ▼
storage/ingestion.py — chunks the Markdown like a normal doc
   │  - chunks tagged with `source_kind: image`
   │  - additionally, copy original to
   │    .armance/vector/images/<sha><.ext>
   │  - manifest entry stores both paths
```

### Mapping for re-display

When an agent cites a chunk whose `source_kind: image`, the chat UI
can re-display the original. Mapping table:

```
.armance/vector/manifest.json (extended)
  "feuillets": {
    "f_001": {
      "doc_id": "<sha>",
      "source_kind": "image",                ← new
      "original_path": "vector/images/<sha>.png",  ← new
      ...
    }
  }
```

### PDF without text

Same pipeline. PDFs with embedded text use the existing text pipeline
(no vision call). PDFs without text → vision per page (each page is
sent as an image). Cost scales with page count; the user is warned at
upload if the PDF is large.

### Caching

`vector/vision_cache/<sha>.md` — TTL infinite (key = file sha = stable).
Re-indexing the same image hits the cache, no provider call.

### Tasks

```
M.4 — Vision ingestion module
  1. New `armance.storage.vision_ingestion`.
  2. `transcribe_image(path, capability_binding) -> str` returns
     Markdown.
  3. Cache layer hit / miss tests.
  4. Tests with respx mocking Gemini vision.

M.5 — Library accepts images
  1. `sync_docs` detects image / scanned-PDF formats and routes to
     `vision_ingestion`.
  2. Original copied to `vector/images/<sha>.<ext>`.
  3. Manifest stores `source_kind` + `original_path`.
  4. Tests.

M.6 — Chat UI re-display (web V2)
  1. Frontend hook reads `source_kind: image` and renders the
     original via `GET /sessions/{sid}/library/source/<sha>.<ext>`.
  2. New route serves the file via Storage ABC.
```

## §3 — Image generation as output

### `[EXECUTE:/generate-image:<prompt>]` tag

Allowed roles: `mona` + `specialist`. Scrubber rejects it on any
other role.

Behaviour on intercept:

1. If `capability_models["image_gen"]` is inactive → tag stripped,
   emit warning event on bus, agent's reply continues without the
   image.
2. If active → call `image_gen` model with the prompt. Store the
   image at:
   - workflow context: `.armance/exports/<wf>/run-<id>/images/<n>.png`
   - direct chat context: `.armance/sessions/<sid>/images/<ts>.png`
3. Replace the tag in the reply with `![](images/<n>.png)` (Markdown
   embed) so the chat UI / deliverable PDF picks it up automatically.

### Tag conditional on capability

The scrubber's per-role allow-list adds a runtime gate: tag is
allowed only when the matching capability is active.

```python
def is_tag_allowed(role: Role, tag: Tag, cfg: Config) -> bool:
    if tag not in _ROLE_TAG_ALLOWLIST[role]:
        return False
    if tag == "/generate-image" and not is_capability_active(cfg, "image_gen"):
        return False
    return True
```

### Tasks

```
M.7 — Image generation tag + scrubber
  1. Add `/generate-image` to `_ROLE_TAG_ALLOWLIST` for mona +
     specialist.
  2. Implement the capability gate in `is_tag_allowed`.
  3. New `armance.service.image_gen` module — call model,
     persist file, return path.
  4. Intercept rewrites the tag → `![](images/...)` in the reply.
  5. Tests: active + inactive paths, mona / specialist roles, other
     roles rejected.
```

## §4 — Render Markdown, code, Mermaid, SVG in chat (V2 web)

### Requirements

- Markdown via `marked` or `remark` with GitHub-flavoured fenced
  blocks.
- Code highlighting via `shiki` (build-time themes, dual light+dark
  via the V2 theme tokens).
- Mermaid via `mermaid` JS library, lazy-loaded.
- SVG inlined with **DOMPurify** sanitization (strict config: no
  script, no foreignObject, no external href, no event handlers).

### Component shape

```
web/frontend/src/components/render/
  MarkdownRenderer.tsx        top-level: pipes through marked, dispatches blocks
  CodeBlock.tsx               shiki highlighted, with language pill + copy button
  MermaidBlock.tsx            lazy mermaid, error fallback shows the raw text
  SvgBlock.tsx                DOMPurify sanitised then dangerouslySetInnerHTML
  InlineImage.tsx             with lightbox on click
```

### Bundle impact

- `marked` ~12 KB.
- `shiki` (oniguruma + themes lazy) ~80 KB on first code block.
- `mermaid` ~250 KB lazy on first mermaid block.
- `dompurify` ~20 KB.

`shiki` and `mermaid` are dynamic imports — pages without code /
diagrams stay fast.

### Tasks

```
M.8 — MarkdownRenderer + CodeBlock
  1. Component + Storybook stories (light + dark).
  2. Playwright test: a reply with ```python``` block renders
     highlighted + copy works.

M.9 — MermaidBlock
  1. Lazy dynamic import; error boundary shows raw text on failure.
  2. Theme integration: light + dark Mermaid themes wired to the
     V2 theme token.
  3. Playwright test: a `mermaid` fenced block renders the SVG.

M.10 — SvgBlock + sanitization
  1. DOMPurify config locked: forbid `script`, `foreignObject`,
     `iframe`, `embed`, `object`, all `on*` event handlers, `href`
     pointing outside same-origin.
  2. Test (red): an SVG with `<script>` is rendered without the
     script tag.
  3. Test (red): an SVG with `onclick="..."` has the attribute
     removed.
  4. Test: a legitimate SVG renders intact.
```

## §5 — Visual overlay: agent prompt addon, web client only

### Approach

Same pattern as the existing `_voice_overlay.py` for languages.
A new `_visual_overlay.py` returns a short Markdown block to append
to the agent system prompt **only when the client is web** (the
client kind is already in `LoopContext`).

### Overlay text (one line max)

```
You may, when a schema would clarify your point, glide a ```mermaid
or ```svg block into your reply. The web client renders them inline.
```

That's it. Discreet (lets the agent judge), one line, no example
(no contamination of the small-model prompt).

### Conditional injection

```python
def build_system_prompt(agent: Agent, ctx: LoopContext) -> str:
    parts = [agent.system_prompt]
    parts.append(voice_overlay(ctx.cfg.language))
    if ctx.client_kind == "web":
        parts.append(visual_overlay())
    return "\n\n".join(parts)
```

`client_kind` is a new field on `LoopContext`, defaults to `"tui"`,
set to `"web"` by the FastAPI session factory.

### Tasks

```
M.11 — Visual overlay module
  1. New `armance.service.agents._visual_overlay.visual_overlay()`.
  2. Add `client_kind: Literal["tui", "web"]` to `LoopContext`.
  3. Web `make_loop_context` sets `client_kind="web"`.
  4. Update agent system-prompt builders to append overlay when
     web.
  5. Tests: TUI loop → no overlay; web loop → overlay present.
```

## §6 — Mermaid pre-render for PDF deliverables (V2)

### Decision

User said: *« faisons simple pour l'instant, lib Python »*. We do
NOT take the headless-chromium dependency. We use a pure-Python /
small-dep Mermaid renderer.

### Library options

- `python-mermaid` — wrapper around mermaid-cli (requires Node + Chrome).
  **REJECTED**.
- Pre-render at session-end via a small HTTP call to a local
  Mermaid live editor (requires network). **REJECTED**.
- **Accepted**: use a pure-Python SVG generator for the simple
  subset of Mermaid we expect (flowchart LR/TD, sequence, basic
  state diagram). If a diagram is too complex, the PDF embeds the
  raw text in a code block as a fallback. The user is warned in
  the deliverable: *« diagram not rendered, see source »*.

### Approach

`armance.service.mermaid_render.try_render(source: str) -> SvgOrNone`.
Returns SVG bytes if the diagram fits the supported subset; None
otherwise. The PDF pipeline (WeasyPrint) embeds the SVG inline; on
None, it embeds the source as a `<pre>` block with a one-line
caption.

The supported subset is **explicitly limited** in V2:
- `flowchart LR` and `flowchart TD` with simple `[label]` /
  `(label)` / `{label}` shapes
- `sequenceDiagram` with `participant` + simple arrows
- Falls back to source-as-text for anything else

### Tasks

```
M.12 — Pure-Python Mermaid renderer (subset)
  1. New `armance.service.mermaid_render` module.
  2. Parser + SVG emitter for the supported subset.
  3. Tests: covered cases render; unsupported cases return None.

M.13 — PDF pipeline integration
  1. WeasyPrint deliverable pipeline scans for ```mermaid blocks,
     calls `try_render`, replaces with SVG or fallback `<pre>`.
  2. Tests: deliverable PDF contains the SVG when renderable;
     contains the source `<pre>` otherwise.
```

## §7 — Auto-discovery proposal (vision)

### Behaviour

When the user drops an image in `.armance/docs/` and
`capability_models["vision"]` is inactive, Armance does what she does
for embeddings:

> *« Vous venez de déposer une image. Pour que l'équipe puisse la lire,
> je propose le modèle `gemini-2.0-flash`, qui est gratuit et capable
> de décrire et de transcrire les images. Voulez-vous que je le
> configure ? »*

On user confirmation → emit
`[EXECUTE:/library-configure-capability:vision:<provider>:<model>]`.

This is the natural extension of the `auto-embed-discovery` pattern.
Same tag family, generalised.

### Tasks

```
M.14 — Auto-discovery for vision (V1 + V2)
  1. New tag `/library-configure-capability:<cap>:<provider>:<model>`.
  2. Handler writes `capability_models[cap]` and reloads config.
  3. Armance prompt: add a Step A.5 paragraph on first image
     encounter, only when capability inactive.
  4. Tests.

M.15 — Auto-discovery for image_gen (lazy)
  1. The first time Mona or a specialist would emit
     `[EXECUTE:/generate-image]` and the capability is inactive,
     Armance proposes a model. Until configured, the tag is
     stripped silently with a one-line system message
     appended to the chat: *« génération d'image non configurée. »*
```

## §8 — V3: Speech-to-text + text-to-speech

### Scope (asymmetric)

- User can speak → STT transcribes → agent receives text.
- Agent reply text → TTS plays back via `<audio>` element.
- No realtime streaming (V4).

### Capability bindings (V3)

`capability_models["stt"]` and `capability_models["tts"]`. Two
providers expected first:
- OpenAI Whisper API (STT) + OpenAI TTS-1 (TTS).
- Gemini (multimodal, TTS via Gemini Live API).

### Frontend (V3)

```
web/frontend/src/components/audio/
  VoiceInput.tsx        push-to-talk button + waveform + STT call
  AudioReply.tsx        per-message play button + auto-play toggle
```

### Tasks (V3)

```
M.16 — STT / TTS capability bindings (V3)
  1. Add `stt` and `tts` to `CapabilityKey`.
  2. Provider methods `stt(audio_bytes) -> str`, `tts(text) ->
     audio_bytes`.
  3. Backend routes:
     POST /sessions/{sid}/stt   (multipart audio)
     POST /sessions/{sid}/tts   (body: text)

M.17 — Frontend voice IO (V3)
  1. VoiceInput component: press → record → release → STT call →
     populates ChatInput with the transcription.
  2. AudioReply: per message; cached; per-session "auto-play"
     toggle in user settings.
```

## Acceptance criteria — whole spec

### V1
- [ ] `judge_model` removed; tests still pass.
- [ ] `capability_models` dict introduced; old configs migrate
      transparently.
- [ ] Vision pipeline indexes images and scanned PDFs; cache by
      sha works.
- [ ] `/generate-image` tag works for Mona + specialists when
      capability active.
- [ ] Image-original re-display works in any future client (mapping
      in manifest).

### V2
- [ ] Chat renders Markdown + highlighted code + Mermaid + sanitised
      SVG.
- [ ] Visual overlay injected only on web client.
- [ ] Mermaid in deliverables is rendered or falls back gracefully
      to source.
- [ ] Auto-discovery proposes a vision model on first image upload.
- [ ] DOMPurify rejects `<script>` and `on*` handlers.

### V3
- [ ] STT works end-to-end.
- [ ] TTS plays back agent replies.
- [ ] Capability gates the UI controls.

## Open questions

- **Q-M.1** — For Mermaid pre-render, the supported subset is
  small. If a user produces a diagram outside the subset, do we
  fail loud (block deliverable export) or fail soft (embed
  source)? Reco: fail soft + warn in the deliverable header.
- **Q-M.2** — For image generation, do we let Mona embed a
  generated image **inside her synthesis** or only as a side-car?
  Reco: inside. The synthesis Markdown gets an `![](...)` line;
  the deliverable PDF picks it up.
- **Q-M.3** — Image / vision cost is non-trivial. Do we warn the
  user before a multi-page scanned PDF goes through vision? Reco:
  yes, checkpoint of `kind: confirm` with an estimated cost.

## Out of scope (→ V4)

- Realtime voice agent (streaming STT + streaming TTS).
- Video input / output.
- 3D / interactive diagrams.
