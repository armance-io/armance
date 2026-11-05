# Config globale : page éditable, bouton home, niveau root

> Status: proposed.
> Linked to: `launcher-global-setup.md`
> (grandma launcher — le split global/local des *fichiers* existe déjà ;
> cette issue ajoute le split dans l'**UI web**).

Demandé par le mainteneur 2026-07-04.

## Besoin

La séparation des fichiers existe (`~/.config/armance` global vs
`.armance/` par projet) mais l'UI web ne la reflète pas :

1. `armance` en ligne de commande → arrive sur la **page globale**
   (launcher, liste des projets) **ET** cette page doit permettre de
   modifier la **config globale** (providers, clés API, modèle par défaut,
   langue, budget, embedding/rerank par défaut, zone électrique…).
2. Dans un projet, l'onglet Administration/config ne montre que le
   **subset projet** (overrides propres au projet : brief, docs, équipe,
   workflows, éventuels overrides de modèle/budget) — plus les champs
   globaux dupliqués.
3. **Bouton « home »** en haut à gauche, à côté du bouton collapse de la
   sidebar gauche, pour revenir à la page des projets depuis n'importe
   quel écran projet.

KISS et pragmatisme : pas de nouveau système de config, on expose la
frontière déjà existante côté fichiers.

## Implementation sketch

| Zone | Action |
|---|---|
| Backend | Route(s) config globale (`GET/PUT /config` hors scope `pid`) adossées à `~/.config/armance` ; les routes admin projet ne servent plus que le subset projet. Attention au gate sécurité (Epic S) : les deux mounts. |
| Frontend launcher | Section « Configuration » sur la page globale (réutiliser les composants admin existants, scope global). |
| Frontend projet | Filtrer l'admin projet au subset ; lien « config globale » vers le launcher. |
| Frontend layout | Bouton home (icône) en haut à gauche à côté du collapse sidebar → route launcher. Testid dédié (e2e par testid, pas par label). |
| Frontière | Décision explicite champ par champ : global = providers/secrets/langue/budget/défauts modèles/zone ; projet = brief, overrides éventuels. Documenter dans le fichier d'issue au moment de l'implémentation. |

## Acceptance

- [ ] `armance` (CLI) ouvre la page globale : liste projets + config
      globale éditable.
- [ ] La config d'un projet n'affiche que le subset projet ; les champs
      globaux ne sont ni dupliqués ni éditables là.
- [ ] Bouton home visible sur tout écran projet, en haut à gauche à côté
      du collapse de la sidebar ; retour à la liste des projets.
- [ ] Modifs de config globale persistées dans `~/.config/armance`,
      celles du projet dans `.armance/` du projet.
- [ ] Sécurité : routes globales derrière le même gate que le reste
      (les deux mounts `""` et `/api`).

## Out of scope

- Multi-utilisateur / rôles (V3).
- Migration de configs existantes au-delà de ce que le grandma launcher
  fait déjà.

## Niveau root : traçabilité et budgets

Fusionné depuis `global-config-root-panel` (décision 2, b).

**Prérequis de la gouvernance carbone (b).** Aujourd'hui la config est par projet
(`.armance/`). Créer un niveau **root** qui embrasse *tous* les projets Armance de
la machine :

- **Traçabilité root** : depuis la racine, voir **quel projet a le plus consommé**
  (€ + CO₂e + eau), **idéalement par période** (jour/mois/session). Agrégation des
  ledgers par-projet existants.
- **Budget total root** : plafond global mensuel, exprimable en **$/mois OU
  CO₂/mois** (l'une OU l'autre unité déclenche).
- **Budgets par projet EN PLUS du global** : ex. armance 100 $/mois OU 2 kg
  CO₂/mois ; projet X 20 $/mois OU 500 g CO₂/mois.

Interaction : postures budgétaires, `service/stats.py`, `env-impact-ledger`.
