# Atelier de cadrage IA générative — Groupe Ferrand

## 1. Déroulé minuté (4 h, présentiel)

**Objectif de sortie affiché dès l'invitation** : « À 18 h, nous avons
choisi 2 à 3 cas d'usage, nommé un sponsor par cas, et validé le plan
des 6 prochaines semaines pour le CODIR groupe. »

| Heure | Séquence | Format | Note |
|---|---|---|---|
| 14:00 | Ouverture par le DG (cadré avec lui en amont : ambition + « pas de projet à 7 chiffres, des preuves ») | 10 min plénière | Le cadrage budgétaire vient du DG, pas de nous : désamorce le dir. industriel |
| 14:10 | Démythification : ce que l'IA générative fait / ne fait pas, 3 exemples industriels comparables (pas de démo gadget) | 25 min présentation | Inclut 5 min « pourquoi les POC IA échouent » — crédibilité auprès des sceptiques |
| 14:35 | Restitution des douleurs collectées en entretiens : devis 9 j, rapports 8D, PDF maintenance, veille brevets | 20 min plénière | Leurs mots, cités ; validation/correction à chaud par les métiers |
| 14:55 | Sous-groupes (2 × 4 pers., métier + support mélangés) : sur 6 cas d'usage pré-instruits, compléter valeur / faisabilité / prérequis. Consigne affichée : « Pour chaque cas : qu'est-ce qui change concrètement pour vos équipes ? Qu'est-ce qui vous manque pour y croire ? » | 45 min | Cartes A3 pré-remplies : le groupe corrige, il ne part pas de zéro |
| 15:40 | Pause | 10 min | |
| 15:50 | Restitution croisée + matrice valeur × faisabilité construite en direct au mur | 30 min | L'animateur place, le groupe conteste — les contraintes (secret industriel, DSI sous l'eau) servent de filtre visible |
| 16:20 | Priorisation par vote pondéré (chaque directeur : 3 points) puis débat sur les écarts | 25 min | Le DG vote en dernier — évite l'alignement de complaisance |
| 16:45 | Conditions de réussite des 2-3 cas retenus : sponsor, données nécessaires, mesure de valeur, risques sociaux (préparer le passage en CSE avec la DRH) | 35 min plénière | Chaque cas repart avec un protocole de mesure : baseline actuelle → cible → comment on mesure |
| 17:20 | Plan 6 semaines vers le CODIR : qui, quoi, jalons | 25 min | Livrable projeté et amendé en séance |
| 17:45 | Tour de table d'engagement + clôture DG | 15 min | Chacun dit ce qu'il porte |

**Si dérapage** : la séquence 14:35 (restitution douleurs) peut se
compresser à 10 min (les cartes des sous-groupes la contiennent).
**Incompressible** : priorisation (16:20) et plan 6 semaines (17:20) —
sans eux, pas de livrable et le DG n'a rien pour le CODIR.

## 2. Les 6 cas d'usage pré-instruits (cartes A3)

1. **Accélération des devis ADV** (4 000/an, 9 j → cible < 3 j) :
   assistant de montage s'appuyant sur l'historique de devis et les
   plans. Valeur forte, faisabilité moyenne (historique structuré dans
   l'ERP, mais plans = secret industriel → hébergement souverain ou
   on-premise requis). Prérequis : extraction historique post-migration
   S/4HANA — **coordonner avec le projet ERP, pas en parallèle sauvage**.
2. **Aide à la rédaction 8D / réponses d'audit** (qualité) : génération
   assistée sur trame IATF avec citations de la base documentaire.
   Valeur forte, faisabilité forte — la mieux placée pour un premier
   succès en 6 semaines (périmètre pilote : 1 ligne, 1 client).
3. **Exploitation des 30 ans de CR maintenance en PDF scannés** : OCR +
   recherche sémantique (« ce roulement a-t-il déjà lâché ? »). Valeur
   moyenne-forte, faisabilité moyenne (qualité OCR à prouver sur
   échantillon — spike de 2 semaines avant tout engagement).
4. **Veille brevets/normes R&D** : synthèses périodiques ciblées.
   Valeur moyenne, faisabilité forte, coût faible — bon « quick win »
   pour l'alliée R&D.
5. **Assistant documentation GED** : recherche en langage naturel dans
   SharePoint. Valeur diffuse, faisabilité faible en l'état (GED
   vieillissante mal indexée) — carte présente pour objectiver le
   « pourquoi pas maintenant » et poser le prérequis data.
6. **Chatbot RH interne** : carte volontairement présente car souvent
   demandée — faible valeur ici, sensibilité CSE forte ; sert à montrer
   qu'on sait dire non.

## 3. Support (structure, une idée par slide)

S1 titre + objectif de sortie · S2 « ce que l'IA générative sait faire »
(3 exemples industriels) · S3 « ce qu'elle ne sait pas faire » (limites,
hallucinations, besoin de données propres) · S4 pourquoi les POC
échouent (données, sponsor, mesure) · S5 vos douleurs (verbatims
entretiens) · S6 consigne sous-groupes + timing · S7 matrice vide
valeur × faisabilité (remplie au mur) · S8 contraintes de cadrage
(secret industriel → pas de cloud US non cadré ; budget ; DSI :
capacité réelle pendant la migration ERP) · S9 modèle de « fiche cas
retenu » (sponsor, données, baseline, mesure, risques) · S10 plan
6 semaines vers le CODIR · S11 engagement.

Chaque slide porte des **notes animateur** séparées (ce qu'on dit, pas
ce qu'on montre) — exemples clés :

- S3 : « C'est ici qu'on gagne le directeur industriel : on énonce les
  limites avant qu'il les objecte. »
- S8 : « Ne pas présenter la DSI comme un frein : dire qu'elle arbitre
  la capacité, et que le plan 6 semaines ne lui prend que X jours. »

## 4. Guide animateur — objections anticipées

| Objection probable (qui) | Réponse préparée |
|---|---|
| « L'IA c'est pour les start-ups, pas pour un équipementier » (dir. industriel) | Exemples de pairs industriels + le cas 8D : périmètre qualité qu'il connaît, gain mesurable, zéro impact process de production. |
| « L'équipe est sous l'eau avec S/4HANA » (DSI) | Le plan 6 semaines chiffre la charge DSI (< 5 jours) ; le pilote 8D s'appuie sur un prestataire, la DSI garde le contrôle d'architecture et le choix d'hébergement. |
| « Que dit-on au CSE ? » (DRH) | Cas retenus = assistance, pas suppression de poste ; proposer d'associer la DRH à la fiche « risques sociaux » de chaque cas et de présenter la démarche au CSE avant le lancement du pilote. |
| « Nos plans chez un fournisseur cloud américain, jamais » (DG/dir. industriel) | Contrainte actée en slide 8 : options souveraines ou on-premise pour tout ce qui touche plans/procédés ; le pilote 8D n'expose pas de données de conception. |
| « Pourquoi pas tout faire ? » (DG) | La matrice au mur montre le coût d'opportunité ; 2-3 cas maximum pour avoir des preuves au CODIR — le reste est daté, pas abandonné. |

## 5. Logistique et préparation

- 2 semaines avant : valider avec le DG son message d'ouverture (10 min,
  incluant le cadrage budgétaire) ; imprimer cartes A3 ; envoyer aux
  participants un one-pager (pas le support complet).
- Salle : mur libre pour la matrice, 2 tables de sous-groupes,
  projection.
- Plan B : si le DG est absent → reporter (l'atelier perd son pouvoir
  de décision) ; si un responsable métier manque → son cas d'usage
  reste instruit par sa carte, décision « sous réserve ».
- J+3 : compte rendu d'atelier + fiches des cas retenus + plan 6
  semaines envoyés — c'est le matériau du CODIR.
