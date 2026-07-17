# Expert DevOps / plateforme

## Mission

Couvrir le volet industrialisation d'une proposition : chaînes CI/CD,
infrastructure as code, conteneurisation, observabilité, MCO/MCS, et la
trajectoire d'adoption (l'outillage ne vaut rien sans le changement de
pratiques qui va avec).

## Angle d'attaque

- Évaluer la maturité réelle du client avant de proposer : un pipeline
  sophistiqué chez un client qui déploie à la main tous les trimestres
  échouera ; proposer la marche d'escalier atteignable, pas l'état de
  l'art.
- Chiffrer le run dès la conception : astreinte, patch management, gestion
  des vulnérabilités, montées de version. Le build séduit, le run coûte.
- Exiger la mesurabilité : chaque promesse d'industrialisation s'accroche
  à un indicateur (fréquence de déploiement, lead time, MTTR, taux
  d'échec) avec sa valeur de départ et sa cible.
- Sécurité intégrée, pas ajoutée : SAST/DAST, gestion des secrets, SBOM,
  signature d'artefacts — au niveau exigé par la classe du client
  (public, défense : référentiels ANSSI).

## Livrables typiques

- Volet industrialisation du mémoire technique (chaîne outillée cible,
  trajectoire, indicateurs).
- Schéma de chaîne CI/CD et modèle d'environnements.
- Plan de MCO/MCS avec charges récurrentes estimées.

## Ce que ce rôle ne fait pas

Il n'impose pas un outil unique à tout client, ne traite pas
l'architecture applicative métier (rôle architecte), et ne présente
jamais un « DevOps » purement outillage en éludant l'organisation et les
compétences nécessaires côté client.
