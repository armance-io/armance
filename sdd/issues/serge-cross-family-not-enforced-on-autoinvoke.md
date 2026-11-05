---
status: captured
severity: high
module: serge-adversarial
found: 2026-07-05 (audit)
---
# Serge : la garantie cross-family n'est pas appliquée sur l'auto-invoke

> **Etat au 2026-11-05.** Le seuil d'auto-invocation est passé de 3 juges à 1 sur `main` (commit
> `9d7a09b`, repris du patch `b0a5520` de la PR #24 fermée). Le fond du bug reste ouvert : l'auto-invoke hérite
> de la config d'exécution sans revérifier la famille, et `validate_cross_family` ne fait qu'avertir.

## Symptôme

Serge est un **pilier doctrinal** : critique adversarial sur une famille de
modèle **différente** du reste de l'équipe, obligatoire (anti-sycophantie
structurelle). Mais la garantie n'est **dure que sur un seul chemin** :

- ✅ `ChallengerAgent.__init__` lève `CrossFamilyConfigError` si même famille.
- ❌ L'auto-invoke par consensus (`service/workflow_hooks.py`,
  `check_consensus_and_maybe_invoke_serge`) passe par le `critique_runner` du
  workflow et **hérite de la config d'exécution sans re-vérifier** la famille.
- ❌ `validate_cross_family` est **purement advisory** — retourne toujours
  `None`, ne bloque jamais.

## Impact

Dans le chemin workflow/consensus, Serge peut tourner sur **la même famille** que
l'équipe qu'il est censé contredire → sycophantie possible, la doctrine est
silencieusement violée. Le mécanisme anti-mensonge n°1 a une faille sur son
chemin le plus fréquent (les workflows).

## Piste (à raffiner en COMPILE)

Rendre la vérification cross-family **uniforme** : soit centraliser un garde dur
appelé par les deux chemins (init direct + auto-invoke), soit faire de
`validate_cross_family` un vrai bloquant et le câbler dans `workflow_hooks`.
Décider la politique quand une seule famille est disponible (warn-and-continue
vs hard-fail) — cf. interaction avec `local-inference-ollama.md` (mode
tout-local où deux familles ne sont pas garanties).

## Vérification (done)

Un test montre qu'un consensus déclenchant Serge avec une config mono-famille
lève désormais (ou journalise explicitement) au lieu de passer silencieusement.
