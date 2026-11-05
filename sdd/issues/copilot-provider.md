---
status: captured
module: [providers-catalogue, config-and-paths]
source: conversation 2026-09-16 (étude de faisabilité)
priority: 3
related: [multi-provider-instances-model-allowlist, sdk-hermetic-isolation]
---
# Provider GitHub Copilot (abonnement Copilot comme source de modèles)

Demande : avec un abonnement/jeton GitHub Copilot, brancher Copilot comme
provider Armance. Trois voies identifiées (session Claude Code, 2026-09-16) :

1. **GitHub Models** (`https://models.github.ai/inference`, OpenAI-compatible,
   PAT scope `models:read`) → quasi zéro code via une instance `custom-openai`.
   Quotas séparés de Copilot, contexte limité en free tier.
2. **Copilot SDK** (`github-copilot-sdk`, GA 2026-06) → nouveau `ProviderType`
   `copilot`, calqué sur `claude-code` (runtime agent + CLI embarqué, outils à
   couper, premium requests). Voie officielle pour consommer l'abonnement.
3. **Endpoint interne `api.githubcopilot.com`** (échange de jeton
   `copilot_internal`) → non documenté, hors CGU : écarté.

À trancher : voie 1 (test immédiat) puis 2 si l'abonnement doit être consommé.
