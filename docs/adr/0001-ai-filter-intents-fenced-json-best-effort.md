# AI filter intents ride `/ask` as fenced JSON, validated best-effort, applied on user consent

The AI assistant must be able to act on the graph it talks about (highlight
elements, propose filters). We decided the model emits a prompt-instructed
fenced JSON block inside its reply; the backend parses it, strips it from the
prose, and returns it as an optional `insights` field on the existing
`POST /api/sessions/{id}/ask` response. Validation is best-effort per intent
(invalid ones are dropped and surfaced, never fatal), and Filter Intents are
applied only on explicit user consent (one-click card), patching the current
filter state. Rejected provider-native structured output for this slice
because it works non-uniformly across OpenAI-compatible (incl. local Ollama),
OpenRouter and Anthropic adapters, while fenced JSON needs zero adapter
surgery and keeps validation in one place.

**Considered options**: provider-native tool-calls/`response_format` (per-adapter
work, uneven local-model support — revisit as an invisible upgrade path);
auto-applying filters without consent (rejected: suggestions can be wrong and
the panel is the user's); replace-all instead of patch on apply (rejected:
silently destroys manual filter state).

**Consequences**: LLM responses carry headroom for the JSON block
(`max_tokens` bump); the FE gets a greenfield highlight styling layer that must
never prune graph elements (the element-ID no-op guard in `NetworkGraph` would
mask it); the contract is extensible — future AI actions (explain-packet,
analyze endpoints) can join `insights` without a new endpoint.
