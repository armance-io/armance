# Premier run live du bench des presets

Les presets et leur bench sont livrés (PR #44), mais le bench n'a jamais tourné en vrai : la logique offline est
testée, le driver live `scripts/bench_presets.py` attend du quota API. Tant qu'il n'a pas tourné, deux promesses
restent sans preuve :

- le pack `auteur-compagnon` bat-il une réponse frontier sur ses 3 cas ?
- le Creuset bat-il le pipeline manuel qui a servi de référence à sa conception ? C'est le dernier critère
  d'acceptation de la refonte qualité workflow, jamais mesuré.

Fait quand : un rapport de bench daté existe pour le pack, avec un juge d'une autre famille, et sert de base au
delta des runs suivants. Le tuning des prompts vient après cette première mesure.
