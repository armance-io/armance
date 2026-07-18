# Chiffrage Mécalor — suivi des expéditions (estimation initiale)

## 1. Périmètre retenu

**Inclus** : application de suivi des expéditions (~40 utilisateurs
internes, 3 sites), portail de consultation pour ~15 clients grands
comptes (identité séparée de l'AD interne), intégration Pegase par
fichiers plats nocturnes, intégration API Geodis, alertes retard,
tableaux de bord hebdo, reprise d'historique 2 ans, environnements
recette + production, documentation de réversibilité, transfert de
compétences vers 2 développeurs internes.

**Hors périmètre** : autres transporteurs que Geodis (explicitement
reporté), application mobile native.

**Zones grises — à trancher avant engagement** :

- **Scan caristes** : contradiction ouverte entre DSI (« pas de mobile »)
  et supply (« pointage palettes au scan, évidemment »). Impact fort :
  terminaux durcis, mode déconnecté quai, UX dédiée. Chiffré en option
  séparée, pas moyenné.
- **Préprod** : demandée « si ça ne double pas le prix » — proposée en
  option (elle ne double pas le prix, cf. lot 6).
- **Qualité réelle de l'historique Excel** : « propre » vs « dans tous
  les sens » selon l'interlocuteur ; fourchette large sur la reprise.

## 2. Hypothèses structurantes

1. Stack .NET 8 / Azure App Service sur le tenant client (contrainte
   DSI), SQL Azure, Entra External ID pour le portail clients (identité
   séparée exigée), ADFS/Entra pour l'interne.
2. Les exports Pegase restent en fichiers plats nocturnes (pas d'API
   AS/400) ; **rétro-documentation des formats obligatoire avant le
   départ de Jean-Marc en novembre** — traitée en tâche dédiée au lot 1,
   à démarrer en premier.
3. Le tenant Azure n'a ni landing zone ni CI/CD : mise en place d'une
   base IaC + pipeline minimale incluse (sinon ni réversibilité ni
   transfert de compétences ne sont tenables).
4. Volumétrie faible (900 expéditions/jour en pic) : pas d'enjeu de
   performance dimensionnant.
5. Démo COMEX fin de trimestre : maquette cliquable + périmètre « suivi
   interne » réduit, pas le produit complet.

## 3. Décomposition et charges (bottom-up)

| Lot | Contenu | JH min | JH max | Profils dominants | Confiance |
|---|---|---|---|---|---|
| 1. Cadrage & rétro-doc Pegase | ateliers, spécification des flux, doc formats fichiers avec Jean-Marc | 18 | 25 | Consultant confirmé, archi solution senior | Moyenne (dépend dispo Jean-Marc) |
| 2. Socle technique | IaC de base, CI/CD, environnements REC+PROD, ADFS | 20 | 28 | DevOps confirmé, archi cloud senior | Haute |
| 3. Cœur applicatif | expéditions, statuts, alertes, import Pegase, dashboards | 55 | 70 | 2 dev .NET confirmés, 1 tech lead senior | Haute |
| 4. Portail clients externes | Entra External ID, consultation, notifications | 25 | 35 | Dev .NET confirmé, tech lead | Moyenne |
| 5. Intégration Geodis | API jamais utilisée par le client : spike 3 JH inclus | 8 | 15 | Dev confirmé | Basse |
| 6. Reprise historique 2 ans | qualité incertaine : fourchette large assumée | 8 | 20 | Data engineer confirmé | Basse |
| 7. Recette, mise en prod, réversibilité | cahier de recette, doc réversibilité, runbooks | 15 | 20 | Consultant + tech lead | Haute |
| 8. Transfert de compétences | pairing 2 devs internes, ateliers, doc | 8 | 10 | Tech lead senior | Haute |
| **Sous-total build** | | **157** | **223** | | |
| Pilotage (12 % du build) | comitologie ETI légère, jalons | 19 | 27 | Chef de projet confirmé | Haute |
| **Total** | | **176** | **250** | | |

**Option scan caristes** (si tranché oui) : +25 à 40 JH (PWA durcie,
mode dégradé quai, matériel à valider) — décision nécessaire avant la
fin du lot 1.

## 4. Contre-vue analogique

Projets comparables (portail logistique ETI, intégration legacy +
portail externe) : 180-260 JH. Le bottom-up est cohérent. Points de
vigilance analogiques : les intégrations AS/400 non documentées dérivent
dans 1 cas sur 2 — la provision basse-confiance du lot 1 et la fourchette
du lot 6 portent ce risque ; l'absence totale de pratiques cloud chez le
client (gestion « au portail ») justifie le lot 2 complet, souvent
sous-estimé de 30 % quand on suppose une landing zone existante.

## 5. Provisions et risques

- Risque documentation Pegase / départ Jean-Marc : **démarrage lot 1
  sous 4 semaines impératif** — sinon +15 JH de rétro-ingénierie.
- Risque API Geodis inconnue : spike inclus, fourchette large maintenue.
- Provision globale recommandée : 10 % sur le total (confiance moyenne
  d'ensemble), affichée séparément, non diluée.

## 6. Questions au client avant engagement

1. Scan caristes : oui ou non ? (décision structurante, option chiffrée)
2. Préprod : l'option est à ~12 JH + coûts Azure — go ?
3. Reprise : échantillon réel des fichiers Excel sous 15 jours pour
   resserrer la fourchette du lot 6 (8-20 JH).
4. Disponibilité de Jean-Marc avant novembre : combien de jours ?
5. Démo COMEX : périmètre maquette validé (suivi interne seul) ?
6. Les 2 développeurs internes : profils et disponibilité pour le
   transfert (lot 8) ?
