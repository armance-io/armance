# CR réunion technique — 19/06 — Client Mécalor (équipe DSI)

Présents : RSI adjoint (M. Costa), admin infra, notre consultant +
architecte.

## Précisions techniques

- Tenant Azure : souscription unique, pas de landing zone, pas d'IaC.
  L'admin infra gère « au portail ». Aucun pipeline CI/CD existant.
- Pegase (ERP AS/400) : les exports plats nocturnes sont fiables mais
  la structure des fichiers n'est documentée nulle part — « c'est
  Jean-Marc qui sait », départ en retraite en novembre.
- API Geodis : le compte client existe, personne ne l'a jamais utilisée.
- Sécurité : authentification via l'AD interne exigée (ADFS déjà en
  place pour un autre outil). Le portail clients externes devra être
  « séparé, on ne veut pas les grands comptes dans notre AD ».
- Volumétrie : ~600 expéditions/jour en haute saison, pics à 900.
- M. Costa : « la reprise d'historique, honnêtement, 2 ans suffisent ».

## Demandes explicites

- Environnements : recette + production minimum, « une préprod si ça ne
  double pas le prix ».
- Réversibilité documentée (mauvaise expérience avec le prestataire
  précédent, parti avec la connaissance).
- Maintenance : ils veulent internaliser le run à terme ; prévoir un
  transfert de compétences vers 2 développeurs internes.
