# Refonte qualité workflow — Kim prompt-engineer, dossier seed, UI par étape

> **Statut** : design validé (session Fable 5, 2026-07-06), implémentation à
> exécuter par lots. Diagnostic fondé sur le run réel `353-miroirs`
> (`tmp/runtime3`, workflow `reponse-technique-geco-openrag`, 10 steps).
> Branche : `feat/workflow-quality`.

## 1. Diagnostic (preuves dans tmp/runtime3)

Le résultat du workflow est médiocre pour des raisons de **process**, pas de
modèles :

1. **Kim ne génère jamais de `prompt_template`.** Le champ existe pourtant
   déjà (`core/models/workflow.py` L63) ainsi que le moteur de rendu
   `render_template()` (L165-224, refs `{{user_prompt}}`,
   `{{step_id.output}}`, `{{<input_key>}}`…). Son prompt système
   (`service/agents/builtin/system-orchestrator.md` L96-105) ne demande que
   `id/kind/role/depends_on`. Résultat : 100 % des steps passent par
   `_compose_default_prompt()` (L228-298), quasi identique pour tous les
   rôles (« You are a `{role}` » + scope + concat brute des outputs amont).
2. **Les 5 spécialistes parallèles ont chacun réécrit un mémoire technique
   complet** (même titre, même plan, même pile) au lieu de creuser leur axe
   (conformité, data, infra, ML). Aucune consigne de périmètre négatif
   (« ne refais pas l'architecture globale »), aucun contrat de format de
   sortie. Serge l'a lui-même diagnostiqué : « consensus de rédaction, pas
   consensus d'évidence ».
3. **L'injection amont est passive.** `### {dep_id}\n{output}` collé en fin
   de prompt sans instruction « étends ce livrable, ne le réécris pas » →
   traité comme contexte de fond, ignoré.
4. **Traçabilité cassée.** `PROMPT_TRUNCATE_LEN = 150`
   (`service/report.py:23`) ; le prompt réellement envoyé n'est persisté
   nulle part en entier (ni reports, ni `llm_exchanges.jsonl`). Impossible
   d'auditer un run a posteriori — et impossible de construire une UI
   d'édition sans cette matérialisation.
5. **Effondrement silencieux des binômes contradictoires.** Malik avait
   recruté des paires par rôle ; tous les agents en `last_health:
   error:400`, `_step_agent_candidates` (`service/handlers.py` L224-255) ne
   tente que `candidates[:2]` et s'arrête au premier succès → les seconds
   regards (Claire, Sophie, Elise, Laura, Nadine) n'ont jamais tourné, sans
   aucun warning utilisateur.
6. **Chaîne judge→critique→révision→rédaction sans resserrement** : Mona,
   Alice_v2 et Julien_v3 re-rédigent 3× le même contenu.
7. Aucun mécanisme pour donner un **document seed** (ex. un appel d'offres
   déjà rédigé) en input d'un run — aucun champ doc→step dans
   `WorkflowStep`.

## 2. Principes de design

- **Kim devient prompt-engineer under the hood.** Le YAML qu'il produit
  porte, pour chaque step, un prompt complet et *différencié* : mission du
  rôle, périmètre négatif, posture vis-à-vis de l'amont, contrat de sortie,
  destinataire aval. La qualité de l'output du run dépend de la qualité de
  ces prompts — c'est le livrable principal du design dialogue.
- **Contrat de passage de témoin (handoff contract).** Chaque step déclare
  les sections attendues de sa sortie ; le step aval y fait référence. On
  passe d'une concat de textes libres à une chaîne de livrables typés.
- **Tout prompt effectif est persisté.** Un run doit être rejouable et
  auditable ; c'est aussi le substrat de l'UI d'édition.
- **Le default prompt reste un filet de sécurité**, mais durci (anti-
  redondance, posture « étends, ne réécris pas », format imposé) — jamais
  le chemin nominal.
- **Layering intact** : chargement fichiers/bibliothèque côté `service`,
  injecté en texte dans `execute_workflow` via le dict `inputs` déjà
  supporté par `render_template` (`{{<input_key>}}`). `core` ne lit pas le
  disque.

## 3. Lot A — Kim génère un prompt par étape (backend, priorité 1)

### A1. Schéma YAML étendu demandé à Kim
`service/agents/builtin/system-orchestrator.md` (L96-105 + règles L107) —
étendre le format :

```yaml
steps:
  - id: qualifier_conformite
    kind: task
    role: securite
    depends_on: [extraire_exigences]
    prompt: |
      Tu reçois en input {{extraire_exigences.output}} : la matrice
      d'exigences produite par le chef de projet. Ne la réécris pas, ne
      refais ni l'architecture ni le positionnement général — d'autres
      steps s'en chargent. Ta mission : qualifier UNIQUEMENT l'axe
      conformité/souveraineté (RGPD, SecNumCloud, localisation, chaîne de
      sous-traitance). Produis exactement ces sections :
      ## Exigences conformité identifiées / ## Risques / ## Engagements
      proposés / ## Points à arbitrer.
      Ta sortie sera consommée par le step de synthèse (mona) qui assemble
      les axes : reste dans ton périmètre, sois dense, zéro redite.
```

Règles imposées à Kim (à écrire dans le prompt système) :
1. `prompt` **obligatoire** pour `kind` ∈ {task, judge, critique} ;
2. doit référencer chaque dépendance via `{{<dep_id>.output}}` avec une
   phrase disant *ce que c'est* et *quoi en faire* ;
3. doit contenir : mission spécifique du rôle, **périmètre négatif**
   (« ne fais pas X, le step Y s'en charge »), **contrat de sortie**
   (sections exactes), et le **destinataire aval** ;
4. pour les steps parallèles de même niveau : périmètres mutuellement
   exclusifs, explicités.
5. `seed_docs` optionnel (voir Lot B).

Nommage : réutiliser le champ existant `prompt_template`
(`WorkflowStep.prompt_template`, `core/models/workflow.py` L63). Accepter
`prompt:` comme alias dans le parsing (plus naturel pour le LLM) — mapping
dans `design_workflow.py`.

### A2. Validation
`service/skills/design_workflow.py::_validate` (L230-304) :
- chaque `{{ref}}` du template résout vers un `dep_id` de `depends_on`,
  `user_prompt`, ou un input déclaré — sinon erreur explicite renvoyée à
  Kim (il corrige dans le dialogue, comme pour les autres erreurs) ;
- `prompt_template` vide sur un `task/judge/critique` → warning renvoyé à
  Kim (pas bloquant : rétrocompat avec YAML legacy) ;
- test : templates avec refs invalides / manquants / valides.

### A3. Default prompt durci (filet)
`core/models/workflow.py::_compose_default_prompt` (L228-298) :
- section upstream renommée « Deliverable from step `{dep_id}` (extend it,
  do NOT rewrite or restate it) » ;
- ajout : « Stay strictly on your `{role}` axis; other steps cover the
  rest. Do not produce a standalone full document. » ;
- ajout d'un contrat de sortie minimal par `kind`.
- tests existants à adapter : `tests/unit/service/test_workflow_default_prompt.py`.

### A4. Chaîne finale sans re-rédaction en boucle
Dans les consignes de Kim : `critique` reçoit la synthèse et produit des
**deltas numérotés** (pas un nouveau document) ; `revision` applique les
deltas sur la synthèse (diff-oriented) ; `deliverable` met en forme sans
réécrire le fond.

## 4. Lot B — Dossier/document seed en input d'un run (priorité 2)

Cas d'usage : « j'ai déjà un appel d'offres rédigé, je veux le faire
challenger par la pipeline ».

- **Modèle** : `WorkflowStep.seed_docs: list[str] = []` (noms de fichiers
  de la bibliothèque `docs/`), + au niveau run un input libre
  `seed:<clé>=<chemin>` (document hors bibliothèque).
- **Injection (layering !)** : dans `service/handlers.py::_cmd_workflow_run`
  (avant l'appel `execute_workflow` L742-751), charger le texte des
  `seed_docs` (réutiliser/extraire le helper de lecture de
  `host_agent.py::_load_docs_raw` L897 vers un module `service/` partagé,
  plafond ~6000 chars/fichier) et le passer dans le dict `inputs` →
  disponible dans les templates via `{{seed.<basename>}}` et injecté par
  `_compose_default_prompt` dans une section « ## Seed documents ».
- **CLI/TUI** : `/workflow run <name> --input <fichier>` (+ alias NL) ;
  Kim `[EXECUTE:/workflow-run:<name>]` : le design dialogue demande à
  l'utilisateur s'il a un document existant à challenger et le met en
  `seed_docs` du step racine.
- **Web** : `POST /workflows/{name}/run` (`routes/workflows.py::RunIn`
  L179) gagne `seed_docs: list[str]` (fichiers bibliothèque, listés via la
  route library existante).
- **Pattern de workflow « challenge »** : documenter dans le prompt de Kim
  un archétype dédié — step racine = analyse critique du document fourni
  (pas de rédaction from scratch), puis axes spécialisés, puis synthèse
  des écarts + recommandations.

## 5. Lot C — Persistance & auditabilité des prompts (priorité 1, petit)

- `execute_workflow` : le prompt effectif rendu pour chaque step est passé
  au runner — le persister via `workflow_runs.py` :
  `exports/<wf>/run-*/step-<id>.prompt.md` (à côté de `step-<id>.md`), +
  entrée `manifest.json` (`prompt_file`, `template_used: bool`).
- `report.py::PROMPT_TRUNCATE_LEN` reste pour le frontmatter des reports,
  mais le run dir contient désormais la vérité complète.
- C'est le **prérequis data du Lot D** (l'UI lit/écrit ces artefacts).
- Test : après run mock, `step-<id>.prompt.md` existe et contient le texte
  amont injecté.

## 6. Lot D — UI web : visualiser/éditer les inputs par étape (priorité 3)

Le graphe + flèches existe (`web/frontend/src/components/workflow/
WorkflowGraph.tsx`, `@xyflow/react`). À construire :

- **`StepDetailPanel.tsx`** (nouveau, ≤250 LOC ; ne pas gonfler
  `RunDetail.tsx` — déjà 371 LOC, au-dessus de la limite, refactor à
  prévoir) : ouvert au clic sur un node, 3 zones :
  1. **Prompt** (textarea, éditable) — le `prompt_template` du step ;
  2. **Inputs depends-on** (lecture seule) — liste des steps amont avec
     aperçu de leur output (run passé) ou de leur contrat de sortie
     (workflow pas encore lancé) ;
  3. **Autres inputs** — `seed_docs` : picker sur les fichiers de la
     bibliothèque, ajout/retrait.
- **Backend** :
  - `PUT /workflows/{name}/steps/{step_id}` — body
    `{prompt_template?, seed_docs?}` ; recharge le YAML, valide (mêmes
    règles que A2 : refs résolubles), réécrit via
    `workflow_yaml_writer.py`. Réponse = step mis à jour.
  - `GET /workflows/{name}` : exposer `prompt_template`, `seed_docs`,
    `depends_on` par step (vérifier la sérialisation actuelle).
  - `GET /runs/{run_id}/step/{step_id}` (`routes/runs.py`) : exposer aussi
    le prompt effectif (`step-<id>.prompt.md`, Lot C).
- Edges du graphe : au clic sur une flèche, surligner l'input correspondant
  dans le panel (nice-to-have).
- Tests : vitest sur `StepDetailPanel`, route tests backend (suite
  `web/backend/tests/`), e2e Playwright par `data-testid` (jamais par
  label — i18n fragile, cf. mémoire projet).

## 7. Lot E — Fiabilité (bugs relevés, à traiter séparément)

1. Binômes silencieusement perdus : quand un candidat de step est en
   `last_health: error` ou échoue, **warning visible** dans la
   conversation/manifest (« second regard Claire non exécuté : erreur
   400 »). `service/handlers.py::_step_agent_candidates` + boucle L571.
2. Échec de run opaque (« upstream step synthese_mona failed » sans
   cause) : propager le message d'erreur réel dans la conversation et le
   manifest.
3. `reponse-technique-short.yaml` cassé (depends_on vers step inexistant,
   role=step-id) : la validation A2 doit attraper ces deux cas.

## 8. Ordre d'exécution & critères d'acceptation

| Ordre | Lot | Test d'acceptation |
|---|---|---|
| 1 | C (persistance prompts) | run mock → `step-*.prompt.md` complets |
| 2 | A (Kim prompt-engineer) | design dialogue mock → YAML avec `prompt` différencié par step, refs validées ; run → prompts effectifs distincts par rôle |
| 3 | B (seed docs) | run avec `--input` → contenu du doc présent dans le prompt du step racine |
| 4 | E (warnings fiabilité) | candidat en échec → warning visible |
| 5 | D (UI) | éditer un prompt dans le panel → YAML réécrit → run utilise le nouveau prompt |

Validation finale : rejouer le scénario GECO (même user prompt que
`353-miroirs`) et vérifier que les 5 steps parallèles produisent des
contributions **disjointes** (titres/sections différents, pas de
re-cadrage général).

Conventions : commits conventionnels signés (`git commit -s`), fichiers
Python ≤300 LOC / React ≤250 LOC, tests offline uniquement
(pytest/respx/monkeypatch, vitest, Playwright).
