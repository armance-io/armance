/**
 * Providers that can serve embeddings. claude-code (Claude subscription) has
 * no embeddings endpoint, so it is intentionally excluded. Single source for
 * the embedding provider dropdowns (setup, admin config, library banner) so
 * embedding_provider is never left empty.
 */
export const EMBEDDING_PROVIDERS = ["openrouter", "gemini", "custom-openai"] as const;
