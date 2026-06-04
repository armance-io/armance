/**
 * Human-readable provider labels. `claude-code` drives Claude through a
 * subscription login, so it shows as "Claude Subscription" rather than the
 * internal id. Single source so Settings → Configuration and Agents agree.
 */
const PROVIDER_LABELS: Record<string, string> = {
  "claude-code": "Claude Subscription",
  openrouter: "OpenRouter",
  gemini: "Gemini",
  "custom-openai": "Custom (OpenAI-compatible)",
};

export function providerLabel(name: string): string {
  return PROVIDER_LABELS[name] ?? name;
}

/**
 * Canonical list of provider ids Armance supports. Live discovery
 * (`GET /providers`) only returns *configured* providers, so the
 * "add a provider" picker must source the full set from here — otherwise
 * Gemini / Custom never show up until they're already configured.
 */
export const KNOWN_PROVIDERS = Object.keys(PROVIDER_LABELS);
