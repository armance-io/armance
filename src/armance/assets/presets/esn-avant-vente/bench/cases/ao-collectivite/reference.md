# Mémoire technique — Portail citoyen « Mon Agglo » (Val-de-Bresle)

*(Structure calibrée sur la grille de notation du RC ; 20 pages en
version mise en forme, annexes hors décompte : CV, audit RGAA type,
plan de réversibilité détaillé.)*

## 1. Compréhension du besoin et enjeux (critère 20 %)

Val-de-Bresle ne cherche pas un site web mais la bascule de quatre
services communautaires (petite enfance, déchets, transports scolaires,
signalements) vers un guichet numérique unique — sans rupture pour les
12 000 usagers existants et sans exclure les publics éloignés du
numérique (d'où le parcours sans compte d'EX-02 et le RGAA AA d'EX-03,
que nous lisons comme un choix politique d'inclusion, pas une case
réglementaire). Trois enjeux structurent notre réponse :

1. **Continuité** : la reprise chiffrée des comptes (EX-07) et
   l'interopérabilité Concerto/SIG (EX-05) sont les deux risques réels
   du projet — nous les traitons en premier, pas en fin de projet.
2. **Autonomie des agents** : le circuit de traitement no-code (EX-06)
   conditionne l'adoption ; un back-office paramétrable mal conçu
   recrée la dépendance au prestataire que l'agglomération veut quitter
   (EX-08, réversibilité).
3. **Souveraineté pragmatique** : EX-04 offre une alternative
   (SecNumCloud ou trajectoire 18 mois) — nous proposons un hébergeur
   qualifié SecNumCloud dès la mise en service, supprimant le risque
   de migration en cours de marché.

**Matrice de conformité** : EX-01 → §2.1 ; EX-02 → §2.2 ; EX-03 → §5.1 ;
EX-04 → §2.4 ; EX-05 → §2.3 ; EX-06 → §2.1 ; EX-07 → §4.2 ; EX-08 →
§6 ; EX-09 → §5.3. Aucune exigence sans réponse.

## 2. Solution proposée

### 2.1 Guichet unique et back-office (EX-01, EX-06)

Socle open source de gestion de la relation usager éprouvé en
collectivité (type Publik), personnalisé aux couleurs de l'agglomération :
formulaires de démarches paramétrables, suivi de dossier usager,
notifications. Le circuit de traitement est configuré par les agents
habilités via l'interface graphique de workflow — nous nous engageons à
ce que les quatre démarches initiales soient **reconfigurables sans
développement**, et le démontrons en recette sur un scénario modifié en
séance par vos agents.

### 2.2 Identité (EX-02)

FranceConnect pour les démarches nominatives ; dépôt de signalement
accessible sans compte avec référence de suivi anonyme. Les comptes
locaux existants restent utilisables pendant 12 mois (transition douce).

### 2.3 Interopérabilité (EX-05)

Concerto (Arpège) : intégration par les API standard de l'éditeur là où
elles existent ; pour les flux non couverts, échanges de fichiers
sécurisés avec contrat d'interface documenté. **Hypothèse honnête** :
la profondeur d'intégration dépend de la version Concerto déployée et
du droit d'usage des API — nous demandons un atelier avec Arpège en
phase de cadrage et prévoyons les deux scénarios dans le planning.
SIG : export GeoJSON natif des signalements géolocalisés.

### 2.4 Hébergement (EX-04)

Hébergeur qualifié SecNumCloud, données en France, chiffrement au repos
et en transit, sauvegardes quotidiennes externalisées. Pas de trajectoire
de migration à piloter : la conformité est effective au premier jour.

## 3. Organisation, équipe, planning (critère 15 %)

Équipe cœur : 1 chef de projet secteur public (confirmé, 0,4 ETP),
1 architecte solution (senior, 0,3 ETP), 2 développeurs (confirmés,
plein temps), 1 expert accessibilité (interventions ciblées),
1 consultant conduite du changement (ateliers agents). CV en annexe.

Planning 10 mois tenu par la mise en service **par paliers** :

- M1-M2 : cadrage, ateliers démarches, atelier Arpège, POC reprise.
- M3-M5 : socle + démarches déchets et signalements (palier 1 en
  service à M5 — visible pour le délai noté à 10 %).
- M5-M8 : petite enfance (Concerto), transports scolaires, reprise
  complète des comptes.
- M9 : audit RGAA externe, corrections, recette générale.
- M10 : mise en service complète, formation des agents.

Comitologie légère : COPIL mensuel, revue de sprint bimensuelle ouverte
aux agents référents. Top 3 risques suivis à chaque COPIL : intégration
Concerto (mitigation : atelier éditeur M1, double scénario), qualité de
l'export comptes (POC de reprise dès M2 sur données réelles), délai
audit RGAA (auditeur réservé dès M1).

## 4. Méthodologie et qualité

### 4.1 Démarche

Agile cadré : les démarches sont spécifiées en ateliers avec les agents
(2 ateliers par démarche), livrées par paliers, recettées sur cahier de
recette co-construit. Chaque palier en service est irréversiblement
acquis — pas d'effet tunnel de 10 mois.

### 4.2 Reprise des comptes (EX-07)

POC de reprise à M2 sur l'export CSV réel (structure documentée
fournie) : déchiffrement, mapping, dédoublonnage, rapport d'anomalies.
Reprise à blanc à M7, reprise finale à la bascule avec gel court
(< 48 h) et communication usagers préparée avec vos services.

## 5. Accessibilité, sécurité, éco-conception (critère 15 %)

### 5.1 RGAA (EX-03)

Accessibilité intégrée dès la conception (composants du design system
de l'État audités), revue à chaque palier, **audit RGAA 4 externe à M9
livré avec la déclaration de conformité** — l'engagement porte sur le
niveau AA des parcours usager complets, mesuré, pas déclaratif.

### 5.2 Sécurité

Homologation appuyée sur une analyse de risque proportionnée (démarche
ANSSI), journalisation, MFA agents, cloisonnement usagers/back-office,
tests d'intrusion avant mise en service complète.

### 5.3 Éco-conception (EX-09)

Budget de poids de page (< 500 Ko hors première visite sur les parcours
usager), images optimisées, pas de dépendances tierces superflues.
Indicateur suivi en COPIL : poids médian des 5 parcours principaux +
score EcoIndex, publiés sur le portail (transparence).

## 6. Maintenance et réversibilité (EX-08)

Maintenance corrective 3 ans, GTI 4 h jours ouvrés sur incident
bloquant (engagement contractuel, mesuré depuis notre outil de tickets
accessible à vos agents). Réversibilité : documentation d'exploitation
tenue à jour en continu (pas rédigée en fin de marché), export complet
des données et configurations testé une fois par an, assistance de
3 mois au successeur incluse.

## 7. Références et limites honnêtes

Deux références de portails citoyens en collectivité de taille
comparable (détail en annexe, contacts vérifiables). Nous n'avons pas
encore travaillé pour Val-de-Bresle : nous compensons par un démarrage
en immersion (M1 dans vos services) et un palier visible dès M5 qui
vous permet de juger sur pièces avant la moitié du marché.
