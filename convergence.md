# Convergence — Hand-off log

> Sessions de travail entre Guillaume (user) et Claude (Opus 4.7) sur la
> préparation du sprint **P1.5 — Service API consolidation** et la
> stratégie web (V2).
>
> Format: log chronologique des échanges essentiels. Destiné à être repris
> par un autre agent (tokens user presque épuisés sur cette session).
>
> Branche: `feat/convergence-0.1.1`
> Date début: 2026-05-21

---

## 0. Contexte projet (snapshot)

- Armance = multi-agent strategic brain. Python CLI. Markdown = source of
  truth. Single-user, local-first.
- 4 layers: `client → transport → service → core`. Lint clean.
- Tests: **836 pass / 8 skip** (docs disent 889 — drift).
- Invariants: 31/31 vert.
- LOC total: **22 715**.
- BUG_FIXING_GUIDE.md = contrat strict pour agents correcteurs.
- WEB_NEXT.md = spec pré-existant pour V2 web (FastAPI + Next.js + SSE).

---

## 1. Revue de code initiale (demandée par user)

**User question:** "Est-on prêt pour la phase web ?"

**Verdict Claude:** **Non, pas prêt.** Service layer ~70% prêt. Bloquants
réels identifiés:

### Bloquants P0

1. **`src/armance/service/armance_service.py` = stub vide.**
   `ArmanceService.create_task`, `run_task`, `run_workflow`,
   `load_context`, `switch_agent`, `events` → toutes `pass` /
   placeholder. WEB_NEXT.md prétend "service layer frontend-agnostic"
   mais `LocalTransport` délègue à un service qui ne fait rien.
   Vrai entrypoint = `service/tui_bridge.dispatch_input(text, ctx)` +
   `handlers.HANDLERS[name]`.

2. **Deux systèmes d'événements parallèles.**
   - `service/events.py::LocalEventBus.emit(name, attrs)` (JSONL +
     queue, utilisé en prod).
   - `transport/events.py` + `transport/dto.Event` (dataclass,
     inutilisé sauf import dans `transport/local.py` placeholder).

3. **`asyncio.run` blocker dans `service/agents/_rag_inject.py:82`** —
   crash garanti sous FastAPI (event loop déjà running).

4. **Pas de spec session multi-client** (rétracté plus tard — voir §2).

### Warnings P1

5. **Doc drift sévère:**
   - BUG_FIXING_GUIDE.md: "889 passed" → réel **836**.
   - ONBOARDING.md mentionne `service/workflow_engine.py ~1100 LOC` →
     **fichier supprimé** (BUG_FIXING §4 dit "old WorkflowEngine deleted").
   - ONBOARDING.md: `handlers.py ~1700 LOC` → réel **708** (split en
     `chat_handlers/{malik,kim,mona}.py` déjà fait).
   - CLAUDE.md: `handlers.py (~1250 LOC)` → réel **708**.

6. **Files >300 LOC (Rule 5 BUG_FIXING_GUIDE):**

   | File | LOC |
   |---|---|
   | `service/agents/host_agent.py` | 1082 |
   | `service/agents/recruiter_agent.py` | 933 |
   | `cli.py` | 880 |
   | `core/models/context.py` | 756 |
   | `service/handlers.py` | 708 |
   | `client/tui/screens/main.py` | 663 |
   | `core/models/workflow.py` | 616 |
   | `service/agents/agent_lifecycle_service.py` | 556 |
   | `client/tui/widgets/sidebar.py` | 541 |
   | `service/chat_handlers/malik.py` | 475 |
   | `service/chat_handlers/kim.py` | 463 |

   CLAUDE.md disait "handlers.py = remaining exception" → faux. À
   mettre à jour.

7. **Story 1/2/3 de `roadmap/06_workflow_runtime_ux.md`** :
   - Story 1 (`workflow.scope` + run-mode tag) landed.
   - Story 2 (parallel `asyncio.gather`) partiel.
   - Story 3 (pipeline view) bloque l'UX web — manifest enrichi prêt,
     TUI sidebar poll non implémenté.

8. **CheckpointHandler — pas de `is_abort` propagation testée vers
   workflow runner.** Web client qui se déconnecte peut bloquer
   indéfiniment.

### Bonnes nouvelles

- Layering propre (lint clean).
- `dispatch_input` = entry point single, NL-aware.
- Side effects tag-driven uniquement → web n'introduit aucun chemin
  caché.
- `CheckpointHandler` Protocol = bonne abstraction.
- `LocalEventBus` JSONL → trivialement bridgable.
- Zéro `print` debug en service/core. Zéro `questionary` en
  service/core (uniquement `cli.py` + `client/tui/`).

---

## 2. Sprint P1.5 proposé (PREMIER JET — partiellement obsolète)

Claude proposait 7 stories. **User a recadré** ensuite — voir §3.

### Stories initiales

| Story | Description | Effort |
|---|---|---|
| S1 | Décider `ArmanceService` (drop ou câbler) — reco: **drop** | 30min |
| S2 | Unifier Event systems sur `core.models.event` | 3h |
| S3 | Fix `asyncio.run` dans `_rag_inject.py` (async-ifier) | 1h |
| S4 | Spec session multi-client web (FastAPI process model, TTL, locks) | 2h |
| S5 | CheckpointHandler abort propagation + test workflow canceled | 2h |
| S6 | Sync docs (LOC, test counts, modules disparus) | 1h |
| S7 | Hygiène finale + nouveau check invariant `asyncio.run` | 1h |
| **Total** | | **~10h / 1.5j** |

### Commits prévus

```
refactor(service): drop ArmanceService stub + LocalTransport (dead code)
refactor(transport): unify Event on core.models.event, drop dataclass shadow
fix(rag): make inject_rag_section async, remove asyncio.run blocker
test(checkpoint): cover is_abort propagation through workflow runner
docs(web): spec session lifecycle for FastAPI host
docs: sync LOC counts + test counts across CLAUDE/ONBOARDING/BUG_FIXING
chore(invariants): forbid asyncio.run in service+core
```

### Definition of done

| Check | Target |
|---|---|
| `pytest tests/ -q` | 836+ pass, 0 fail |
| `ruff check src/` | clean |
| `scripts/check_invariants.sh` | 31/31 + nouveau check `asyncio.run` |
| `grep -rn "armance_service\|transport.local" src/ tests/` | 0 matches |
| `grep -rn "asyncio.run" src/armance/{service,core}` | 0 matches |
| WEB_NEXT.md | pointe `dispatch_input`, pas `ArmanceService` |
| Doc LOC counts | match `wc -l` réel |

---

## 3. RECADRAGE USER — web = swap UI, pas SaaS

**User a corrigé:**

> "L'objectif du web, c'est pas du SaaS, c'est JUSTE l'interface qui
> switche d'un TUI à WebUI. Donc pour les sessions etc, ça reste la même
> infra, la même archi : files = source of truth."

**Implications:**

- Pas de multi-client, pas de TTL, pas de process model SaaS.
- 1 user = 1 browser tab = 1 process Python = 1 `.armance/sessions/<sid>/`.
- Web frontend = juste afficher TUI dans un browser au lieu de Textual.
- S4 (spec session multi-client) **devient mort**.
- Locks: `storage/filesystem.lockfile` suffit déjà.

### Sprint P1.5 RÉDUIT post-recadrage

| Story | État après recadrage |
|---|---|
| S1 — drop `ArmanceService` | ✅ toujours valide |
| S2 — unify Events | ⚠️ partiel: drop `transport/dto.Event` mais garder `LocalEventBus` JSONL (aligne files-as-truth) |
| S3 — `asyncio.run` fix | ✅ toujours valide (bug latent) |
| S4 — session multi-client | ❌ **mort** → devient 1-liner WEB_NEXT.md "single user, single tab, same on-disk session" |
| S5 — checkpoint abort | ⚠️ optionnel court terme (TUI checkpoint marche déjà) |
| S6 — sync docs | ✅ toujours valide |
| S7 — hygiène | ✅ toujours valide |

**Sprint réduit (selon option web choisie):** ~3h si Option C/D, ~10h si A/B.

---

## 4. Options d'architecture web

### Option A — FastAPI + SSE + frontend Next.js
Stack séparée Python back + Node front. WEB_NEXT.md actuel.
- **Pour:** spec écrit, REST standard, UI moderne.
- **Contre:** lourd pour single-user local. Build Node, deploy front+back.
- **Effort:** 5-7j.

### Option B — FastAPI + HTMX server-rendered (full Python)
Jinja2 + HTMX swaps. Zéro JS toolchain.
- **Pour:** Python pur. Single binary `armance web`. Pas de build front.
- **Contre:** HTMX limite UX riche (claims panel sophistiqué difficile).
- **Effort:** 3-4j.

### Option C — `textual serve` (Textual native web)
Textual expose nativement une app via `textual serve`. Zéro code à
écrire pour wrapper.
- **Pour:** **~1h**, code TUI réutilisé tel quel.
- **Contre:** UX terminale dans browser (look texte).
- **Effort:** ~1h test.

### Option D — Hybride C maintenant + B plus tard
- **V2.0:** ship `armance web` = wrapper `textual serve`. Marche en 1h.
- **V2.1:** si users demandent vraie UI moderne, build Option B.

**Reco Claude:** **Option D**. Match éthos "brain not maker". User
obtient web ASAP. Évite sur-engineering FastAPI/Next.js si textual
serve suffit.

**EN ATTENTE DE DÉCISION USER.**

---

## 5. État actuel (avant clôture session)

- Aucune modification de code faite. Discussion + spec only.
- `convergence.md` créé (ce fichier).
- Branche `feat/convergence-0.1.1` (clean, pas de commit en cours).

---

## 6. Pour l'agent suivant — checklist reprise

1. **Lire ce fichier en entier.**
2. **Lire les sources essentielles** dans cet ordre:
   - `CLAUDE.md` (project rules)
   - `BUG_FIXING_GUIDE.md` (contrat correctional agents)
   - `ONBOARDING.md` §2-5 (architecture overview)
   - `roadmap/02_architecture.md` (module map)
   - `WEB_NEXT.md` (spec actuel — à challenger contre §4 ci-dessus)
3. **Demander à user** quelle option web (A/B/C/D) il retient.
4. **Lancer le sprint réduit:** S1 → S3 → S6 → S7 minimum.
5. **Avant tout code:** `bash scripts/check_invariants.sh` + `uv run
   pytest tests/ -q` → vérifier baseline propre.
6. **Commits:** Conventional Commits, scope = top-level module.
7. **Ne PAS:**
   - Réintroduire `service/workflow_engine.py` (supprimé volontairement).
   - Ajouter chemin code hors `[EXECUTE:/...]` tags.
   - Hard-coder strings user-facing (utiliser `t("key")` + YAMLs).
   - Faire amend/force-push.

---

## 7. Fichiers-clés mentionnés

| Path | Pourquoi |
|---|---|
| `src/armance/service/armance_service.py` | À drop (stub vide) |
| `src/armance/transport/local.py` | À drop (mort après S1) |
| `src/armance/transport/dto.py` | Garder DTOs read-only utiles, drop Event variants |
| `src/armance/transport/events.py` | À drop |
| `src/armance/service/events.py::LocalEventBus` | Canonical event bus, garder |
| `src/armance/service/tui_bridge.py::dispatch_input` | Vrai entry point, promouvoir API publique (rename → `dispatch.py` ?) |
| `src/armance/service/agents/_rag_inject.py:82` | `asyncio.run` à virer |
| `src/armance/service/checkpoint.py` | Protocol bon, abort à tester |
| `WEB_NEXT.md` | À réviser fortement post-décision option |
| `roadmap/06_workflow_runtime_ux.md` | Story 3 bloque pipeline view — à arbitrer |

---

## 8. Décisions ouvertes

- [x] Option web A / B / C / D ? → **A** (FastAPI + Next.js)
- [ ] Sprint P1.5 — complet (10h) car Option A nécessite tout
- [x] Garder `transport/dto.py` DTOs read-only ? → **OUI** (response
      models FastAPI)
- [ ] Story 3 (pipeline view TUI sidebar poll) — landed avant ou après
      sprint P1.5 ?
- [ ] Split `host_agent.py` (1082 LOC), `recruiter_agent.py` (933 LOC),
      `cli.py` (880 LOC) — bundle dans P1.5 ou P1.6 dédié ?

---

## 9. SECOND RECADRAGE USER — SaaS horizon + esthétique

**User a précisé:**

> "Je ne veux PAS qu'on ferme de porte pour un SaaS futur. Armance.io
> est lancé, il y aura un app.armance.io un jour qui permettra ce
> front web. L'objectif est donc double : architecture très
> modulaire, pour permettre TUI + WebUI local, PUIS (plus tard), SaaS."

> "On rejette d'emblée C et D. Aucun intérêt à avoir un TUI web. Je
> reste intéressé par l'option A, même si stack UI lourde : l'objectif
> est d'avoir une BELLE UI, propre, élégante. On fait du beau, du
> 'think', de l'élégant, du 'reMarkable' (la tablette), du FR.
> Imagine Armance comme un système dont le visage serait Adèle
> Blanc-Sec."

### Référence esthétique
- Manifeste site `armance.io/index.html` — sérif éditorial, papier
  crème, drop caps, ❦ flourish, chapitres numérotés ("Chapitre
  premier"), italiques `<em>Armance</em>`, ton littéraire bilingue
  FR/EN.
- Adèle Blanc-Sec: silhouette Belle Époque, ironie posée, intelligence
  pratique.
- reMarkable tablet: e-ink, calme, lent, sans notification.
- Refus net du look "AI app moderne" (chat bulles, gradients,
  hover-glow).

### Décisions finales

**Option web retenue: A** (FastAPI back + Next.js front + SSE).
Stack lourde acceptée pour atteindre la qualité visuelle visée.

**Garantie modularité (4 layers) maintenue:**
- `core/` pure ✅
- `service/` orchestration via `LoopContext` paramétré (stateless,
  réentrant, multi-session-ready) ✅
- `transport/` DTOs (`AgentInfo`, `WorkflowInfo`, `SessionState`) +
  `LocalEventBus` JSONL ✅
- `client/` TUI **et** WebUI côte à côte, aucun couplage ✅

**SaaS futur (horizon, pas dans ce sprint):**
- Multi-user auth = couche **au-dessus** de `dispatch_input` quand
  l'heure viendra.
- Project isolation = `armance_root` déjà param de `LoopContext`. Un
  user SaaS = un dossier `.armance/` distinct sur disque serveur.
- Pas de refactor service-layer nécessaire pour passer local → SaaS.
- Collaboratif multi-user temps réel = **très loin**, pas de design
  pour ça maintenant.

### S1 re-grill (résultat)

Drop `armance_service.py` + `transport/local.py` **ne ferme aucune
porte SaaS**. Raisons:

1. Le stub est un **mensonge** (placeholders), pas une fondation.
2. La vraie API publique = `dispatch_input(text, ctx) -> (reply, agent)`,
   déjà stateless et multi-session-ready.
3. Quand SaaS arrive, créer `service/armance_facade.py` (nom neuf,
   pas réutiliser le stub mort) construit **au-dessus** de
   `dispatch_input` + multi-tenant router.
4. Garder DTOs `transport/dto.py` (utiles comme response models FastAPI
   Option A maintenant, et SaaS plus tard).

### Stack technique Option A — proposée

| Couche | Choix |
|---|---|
| Back HTTP | FastAPI |
| Streaming | SSE (EventSource), pas WebSocket (over-kill single-user) |
| Event source | `LocalEventBus` JSONL → tail → SSE |
| Front framework | Next.js 14 App Router + RSC |
| CSS | **PAS Tailwind**. CSS Modules ou Vanilla Extract |
| Typo corps | EB Garamond ou Tiempos |
| Typo UI | Inter discrète ou full sérif |
| Composants UI | Build à la main, zéro shadcn/MUI (look générique) |
| Animations | Framer Motion (transitions douces) |
| Markdown rendering | `react-markdown` + `remark-gfm` |
| Build | Single binary `armance web` lance FastAPI + sert front pré-build |

### Sprint P1.5 final (post double recadrage)

| Story | État | Effort |
|---|---|---|
| S1 — drop `ArmanceService` + `transport/local.py` (garder `dto.py`) | ✅ confirmé | 30min |
| S2 — unify Events sur `core.models.event` + `LocalEventBus` | ✅ | 3h |
| S3 — fix `asyncio.run` dans `_rag_inject.py` | ✅ | 1h |
| S4 — spec session web 1-user/1-tab (1-liner WEB_NEXT) + note SaaS horizon | ✅ réduit | 30min |
| S5 — checkpoint abort propagation + test | ✅ nécessaire pour SSE | 2h |
| S6 — sync docs (LOC, tests, modules disparus) | ✅ | 1h |
| S7 — hygiène + invariant `asyncio.run` | ✅ | 1h |
| **Total** | | **~9h / 1.5j** |

Puis **P2.a — Web Option A** (5-7j, hors scope P1.5):
- FastAPI backend (~8 endpoints WEB_NEXT.md §2)
- `WebCheckpointHandler` (WEB_NEXT.md §3 déjà spec)
- Next.js front éditorial (style manifeste armance.io)
- Single binary `armance web`

---

## 10. Pour l'agent suivant — re-checklist

1. Lire `convergence.md` complet.
2. Lire fichiers source mentionnés §7.
3. **Confirmer décisions §9 avec user avant code.**
4. Lancer Sprint P1.5 complet (~9h, 1.5j) dans l'ordre S1→S3→S2→S5→S4→S6→S7.
5. WEB_NEXT.md à refondre post-sprint (pointer `dispatch_input`,
   pas `ArmanceService`; ajouter section SaaS horizon).
6. **Pas démarrer P2.a (web) avant Sprint P1.5 vert.**

---

*Fin du log de convergence v2. Continuer ici si reprise.*

---

## 11. Sprint P1.5 TDD reformaté Sonnet-grade

Format par story: **UC** → **Red** → **Impl** → **Green** → **NOT**.
Ordre exec: **S0 → S1 → S3 → S2 → S5 → S4 → S6 → S7**.

### S0 — Baseline check (10min)
- Vérifier pytest 836 / ruff clean / invariants 31/31 avant tout code.
- Stop si échec.

### S1 — Drop ArmanceService + transport/local.py (30min)
- **UC:** TUI fonctionne identique après drop. Pas de consumer prod.
- **Red:** `tests/architecture/test_no_dead_facade.py` — assert files absents.
- **Impl:** `git rm` x2 + clean `transport/__init__.py`.
- **NOT:** ne pas toucher `transport/dto.py`, ne pas renommer `tui_bridge.py`.
- **Commit:** `refactor(service): drop ArmanceService stub + LocalTransport`

### S3 — Fix asyncio.run blocker (1h)
- **UC:** Armance marche identique sous event loop FastAPI (et TUI).
- **Red:** `tests/service/agents/test_rag_inject_async.py` — assert
  `iscoroutinefunction(inject_rag_section)`.
- **Impl:** Convert sync→async, `await store.query` au lieu de
  `asyncio.run`. Audit + update callers (host_agent, recruiter,
  specialist_runner — déjà async).
- **NOT:** ne pas changer top-k ni `storage/rag_index.py`.
- **Commit:** `fix(rag): make inject_rag_section async, remove asyncio.run`

### S2 — Unify Event types (3h)
- **UC:** Un seul `Event` = `core.models.event.Event`. `LocalEventBus`
  unique producteur.
- **Audit prérequis:** `grep` consumers de `transport.dto.Event` (audit
  doit montrer 0 consumer prod).
- **Red:** `tests/architecture/test_single_event_type.py` — assert pas
  d'`Event` dataclass dans `transport.dto`.
- **Impl:** Drop `Event`, `AgentStateChanged`, `TaskEvent`,
  `WorkflowEvent`, `ContextEvent`, `BudgetEvent` de `transport/dto.py`.
  Drop `transport/events.py`. Garder `AgentInfo`, `RoleInfo`,
  `ContextInfo`, `WorkflowInfo`, `WorkflowStepInfo`, `SessionState`,
  `AgentKind`, `TaskStatus`, `Mode`, `TaskInfo`, `ContextVersion`.
- **NOT:** ne pas toucher `core/models/event.py` ni
  `service/events.py`. Pas d'adapter SSE ici (P2.a).
- **Commit:** `refactor(transport): drop dead Event dataclasses`

### S5 — Checkpoint abort propagation (2h)
- **UC:** User déconnecte browser ou abort TUI mid-workflow →
  workflow stop propre, manifest `canceled`, pas de leak.
- **Red:** `tests/service/test_checkpoint_abort.py` —
  `AbortingHandler` retourne `is_abort=True` → `execute_workflow`
  stoppe, `result.status == "canceled"`.
- **Impl:** Vérifier `execute_workflow` consomme `is_abort`. Set
  `_run_aborted`. `workflow_runs.finalise(status="canceled")` supporté.
- **NOT:** ne pas ajouter timeout dans Protocol (web handler s'en
  charge). Ne pas modifier sémantique `CheckpointResponse`.
- **Commit:** `test(workflow): cover checkpoint abort → canceled status`

### S4 — Spec session web doc (30min)
- **UC:** WEB_NEXT.md doc V2 local-first single-user + V3 SaaS horizon.
- **Impl:** Ajouter §0.5 + §0.6 dans WEB_NEXT.md. Update §1 table.
  Pointer `dispatch_input`, retirer mentions `ArmanceService`.
- **Green:** `grep ArmanceService WEB_NEXT.md` → 0. `grep
  dispatch_input WEB_NEXT.md` → ≥ 3.
- **Commit:** `docs(web): session model local-first + SaaS horizon`

### S6 — Sync docs (1h)
- **UC:** Tout agent voit vrais chiffres + structure réelle.
- **Red:** `tests/docs/test_docs_accuracy.py`:
  - `test_handlers_loc_matches_doc` — LOC réel ±10% des docs.
  - `test_no_reference_to_deleted_files` — `workflow_engine.py`,
    `armance_service.py`, `transport/local.py` absents de tous les docs.
  - `test_pytest_count_matches_doc` — count BUG_FIXING matche réel.
- **Impl:** Edit BUG_FIXING_GUIDE.md, ONBOARDING.md, CLAUDE.md,
  roadmap/02_architecture.md, WEB_NEXT.md.
- **Commit:** `docs: sync LOC + test counts + drop deleted refs`

### S7 — Hygiène + nouveaux invariants (1h)
- **UC:** Patterns fragiles bloqués au commit.
- **Impl:** Add to `scripts/check_invariants.sh`:
  - `asyncio.run` forbidden in service+core.
  - Dead facade imports forbidden.
- Count attendu: **31 → 33**.
- **Green:**
  - `bash scripts/check_invariants.sh` → 33/33.
  - `uv run pytest tests/ -q` → 839+ pass.
- **Commit:** `chore(invariants): forbid asyncio.run + dead facade refs`

### Definition of done global
| Check | Target |
|---|---|
| `pytest -q` | 839+ pass, 0 fail |
| `ruff check src/` | clean |
| `check_invariants.sh` | **33**/33 |
| `grep armance_service\|transport.local` src/ tests/ | 0 |
| `grep asyncio.run` src/{service,core} | 0 |
| WEB_NEXT.md mentions ArmanceService | 0 |
| `armance run` lance TUI normalement | ✅ manuel |

---

## 12. Live interactive test — décision

**Faisable.** Pas trop d'imbrication. Moi (Claude) je pilote
depuis l'extérieur comme un user humain. Pas d'agent-test-agent.

### Limites identifiées
1. **TUI Textual prend focus clavier.** → Besoin mode
   `armance run --headless --script <file>` OU wrapper `pexpect`.
2. **LLM non-déterministe.** → Tests d'acceptation = patterns
   (`≥2 historiens`, `PPT ≥5 slides`), pas exact match.
3. **Coût.** Free-first + Claude Pro = quasi-gratuit mais lent.
4. **Durée:** ~15-30 min par scénario complet. Hors CI rapide → vit
   à côté de `scripts/qa_live.py` existant.

### Architecture proposée
```
tests/live/scenario_<X>/
  README.md           # objectifs + critères succès
  docs/               # fichiers à dropper dans .armance/docs/
  expected/
    team_composition.yaml
    workflows.yaml
    deliverables.yaml
  script.md           # mes réponses pré-rédigées
  run.sh              # orchestrate install → init → drive
```

### Hors scope P1.5
Live test = **P1.6 ou parallèle**. P1.5 = stabilité service d'abord.

### Use case demo
**EN COURS DE SPEC** (§13 — voir suivant).

---

*Fin convergence v3.*
