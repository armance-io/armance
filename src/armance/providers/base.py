"""Provider abstraction + canonical ModelSpec.

Every provider that Armance talks to (openrouter, claude-code, gemini,
custom-openai) exposes its model catalogue through the same async interface:
a list of ``ModelSpec`` instances with pricing, context window, and capability
flags. Malik / Kim / cost estimators rely on this single shape; they never
parse provider-specific JSON.

Discovery is session-cached (re-fetched on each `armance run`) — see
`armance.providers.discovery.discover_all`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# Cost tier derived from prompt+completion price; surfaced as a coloured gem
# in Malik's proposals.
Tier = str  # "free" | "low" | "medium" | "high"


SearchMode = str  # "builtin" | "suffix" | "tool" | "" (none)


@dataclass(slots=True, frozen=True)
class ModelSpec:
    """Canonical model description, provider-agnostic.

    `id` is the string the agent YAML writes under `model:` — it must be
    accepted by the provider's chat API as-is.
    """
    id: str
    provider: str
    pricing_in_per_mtok: float = 0.0
    pricing_out_per_mtok: float = 0.0
    context_window: int = 0
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_search: bool = False
    search_mode: SearchMode = ""
    # Whether this model is "effectively free" from the user's POV:
    # - OpenRouter `:free` models: True (zero pricing)
    # - Claude Code SDK models: True (subscription — no per-token cost)
    # - Gemini paid (gemini-2.5-pro): False
    effectively_free: bool = False
    tier: Tier = "free"
    display_name: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_free(self) -> bool:
        return self.pricing_in_per_mtok == 0 and self.pricing_out_per_mtok == 0


def derive_tier(price_in_per_mtok: float, price_out_per_mtok: float) -> Tier:
    """Sum the two prices (per Mtok) and bucket: free / low / medium / high.

    Thresholds match armance.providers.model_discovery (free=0, <0.5=low,
    <5=medium, else high). Kept here so providers don't have to import the
    legacy module."""
    total = price_in_per_mtok + price_out_per_mtok
    if total == 0:
        return "free"
    if total < 0.5:
        return "low"
    if total < 5.0:
        return "medium"
    return "high"


class BaseProvider(ABC):
    """Abstract provider — every concrete provider must implement list_models().

    Implementations stay narrow: discovery + capability flags. Actual chat
    calls live in `armance.providers.<name>` (legacy modules), unchanged for
    this refactor.
    """

    #: Stable name used in config.yaml under `provider:` and in agent YAML.
    name: str = ""

    @abstractmethod
    async def list_models(self) -> list[ModelSpec]:
        """Return the model catalogue. Implementation may cache internally."""

    def validate_model_id(self, model_id: str, models: list[ModelSpec]) -> bool:
        """True if `model_id` exists verbatim in the catalogue."""
        return any(m.id == model_id for m in models)
