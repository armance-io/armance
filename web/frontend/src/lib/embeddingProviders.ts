/**
 * Providers that can serve embeddings. claude-code (Claude subscription) has
 * no embeddings endpoint, so it is intentionally excluded. Single source for
 * the embedding provider dropdowns (setup, admin config, library banner) so
 * embedding_provider is never left empty.
 */
export const EMBEDDING_PROVIDERS = ["openrouter", "gemini", "custom-openai"] as const;

/**
 * Providers that can serve a Cohere-style /rerank endpoint. gemini and
 * claude-code expose none. custom-openai first: openrouter.ai itself has no
 * /rerank route — it only works via a proxy base URL, so the OpenAI-compatible
 * path is the supported one. Decoupled from the embedding provider.
 */
export const RERANK_PROVIDERS = ["custom-openai", "openrouter"] as const;
