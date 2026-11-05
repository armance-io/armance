# Découper les gros fichiers

Les fichiers neufs respectent la limite (Python 300 lignes, composant React 250) ; les anciens qui la dépassent se
découpent avant de grossir. Les deux plus gros sont actés depuis juillet 2026 : `cli.py` vers un package `cli/` à
un module par commande, et `service/handlers.py` vers les shells de chat déjà amorcés dans `service/chat_handlers/`.

Pour lister ceux qui dépassent :

```bash
git ls-files 'src/*.py' | xargs wc -l | sort -rn | awk '$1 > 300'
git ls-files 'web/frontend/src/*.tsx' | grep -v __tests__ | xargs wc -l | sort -rn | awk '$1 > 250'
```
