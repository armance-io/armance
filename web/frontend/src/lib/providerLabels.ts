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
