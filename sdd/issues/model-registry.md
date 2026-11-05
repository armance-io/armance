# Un registre de modèles unique

Décidé en juillet 2026 ([décision 11](../decisions.md)), pas construit. L'identité d'un modèle vit aujourd'hui dans
trois systèmes qui divergent : le catalogue de découverte (`providers/`, avec un fallback statique anthropic), la
résolution de famille (`workflow_crucible.model_family`) et les facteurs d'impact (EcoLogits plus les tables YAML de
`service/`). Un modèle ajouté chez un provider doit être connu des trois ; vécu : un modèle absent du provider
claude-code, une empreinte estimée sur un modèle générique, des tiers d'effort faux.

A faire : une seule source par modèle (`id`, type de provider, famille, tier d'effort, facteurs env, fenêtre de
contexte, date de mise à jour), versionnée dans le repo (données Python ou Markdown, pas de base). Le fallback
anthropic, `order_models_by_effort`, `model_family` et le footprint la lisent. La découverte live la complète, jamais
l'inverse. Premier livrable : le catalogue anthropic et claude-code à jour, avec ses facteurs env.
