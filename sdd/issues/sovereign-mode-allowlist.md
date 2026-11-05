---
status: captured
module: [providers-catalogue, config-and-paths]
source: décision 2 (c) — 2026-07-06
priority: 3
related: [local-inference-ollama]
---
# Mode souverain — contrainte par allowlist domaines/IP

**Reformulation validée du "sceau de souveraineté".** Pas de sceau affiché : tant
qu'on appelle un LLM cloud (Gemini/Claude/OpenRouter), le prompt sort — l'attester
« resté chez vous » serait un mensonge. On garantit la localité des **chunks de
docs**, pas de l'appel LLM.

**Donc : contraindre a priori, pas attester a posteriori.** Un projet marqué
**souverain** n'autorise qu'une **allowlist de domaines/IP** (localhost toujours ;
Ollama local ; endpoint self-hosted explicitement listé). Tout appel hors
allowlist est **bloqué** (pas journalisé). Un projet souverain **ne peut pas**
appeler les providers cloud → exige l'inférence locale.

Souveraineté **vérifiable par construction** (réseau bridé), honnête : on empêche
la sortie au lieu de la nier après coup. Le ledger peut alors légitimement
attester « aucun appel hors allowlist » — car structurellement impossible.

Point de contrôle réseau = `providers-catalogue` (sortie). Couplé à
`local-inference-ollama.md`.

Voir [décision 2 (c)](../decisions.md).
