/**
 * AI assistant API client — mirrors netvisor-backend/src/api/routes/ai.py.
 *
 * Endpoints:
 *   POST   /sessions/{id}/ask   — ask a question about the loaded capture
 *   GET    /ai/config           — which AI mode is active for this user
 *   PUT    /ai/key              — save personal LLM key (encrypted server-side)
 *   GET    /ai/key              — stored key metadata (NEVER the raw key)
 *   DELETE /ai/key              — remove the personal key
 *   POST   /ai/list-models      — models available at the provider (saves nothing)
 */

import { logger } from "@/utils/logger";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

// ── Types (mirror the backend schemas) ──────────────────────────────────

/** AI mode: enterprise (admin env key) | personal (BYO key) | none | unavailable. */
export type AiMode = "enterprise" | "personal" | "none" | "unavailable";

/** GET /ai/config response. */
export interface AiConfig {
  mode: AiMode;
  provider: string | null;
  model: string | null;
  allowPersonalKeys: boolean;
  /** {limit, remaining} on the enterprise key, or null (unlimited / personal). */
  rateLimit: { limit: number; remaining: number } | null;
  /** Human-readable reasons why the current mode is not usable. */
  reasons: string[];
}

/** Question-aware focus hints (node / stream the user is looking at). */
export interface FocusHints {
  node_id?: string;
  stream_id?: number;
}

export interface AskRequest {
  question: string;
  focus?: FocusHints | null;
}

/** One context block sent to the LLM (from the response manifest). */
export interface ContextBlock {
  name: string;
  approxTokens: number;
}

export interface AskUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface AskResponse {
  answer_md: string;
  context: ContextBlock[];
  usage: AskUsage;
  /** {limit, remaining} after this question, or null (personal / unlimited). */
  rate_limit: { limit: number; remaining: number } | null;
}

/** PUT /ai/key request body. */
export interface KeyPayload {
  provider: "openai" | "anthropic";
  base_url?: string;
  model: string;
  api_key: string;
}

/** GET/PUT /ai/key response — metadata only, never the raw key. */
export interface KeyResponse {
  provider: string;
  base_url: string | null;
  model: string;
  keyMasked: string;
}

/** POST /ai/list-models request body. */
export interface ListModelsPayload {
  provider: "openai" | "anthropic";
  base_url?: string;
  api_key: string;
}

/** One model entry from the provider's /models endpoint. */
export interface ProviderModel {
  id: string;
  name: string;
}

// ── Error handling ──────────────────────────────────────────────────────

/** API error with HTTP status + FastAPI detail (and Retry-After when 429). */
export class ApiError extends Error {
  status: number;
  detail: string;
  retryAfterSeconds: number | null;

  constructor(status: number, detail: string, retryAfterSeconds: number | null = null) {
    super(detail);
    this.detail = detail;
    this.name = "ApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => ({}))) as { detail?: string };
  const detail = body.detail ?? `Request failed (${response.status})`;
  const retryAfter = response.headers.get("Retry-After");
  return new ApiError(
    response.status,
    detail,
    retryAfter !== null ? Number(retryAfter) : null,
  );
}

// ── Endpoints ───────────────────────────────────────────────────────────

/** POST /sessions/{id}/ask — non-streaming answer about the capture. */
export async function askQuestion(sessionId: string, body: AskRequest): Promise<AskResponse> {
  const url = `${API_BASE}/sessions/${sessionId}/ask`;
  logger.info("ai-api", `POST ${url}`, { questionLength: body.question.length });
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<AskResponse>;
}

/** GET /ai/config — which AI mode is active for this user. */
export async function fetchAiConfig(): Promise<AiConfig> {
  const url = `${API_BASE}/ai/config`;
  logger.debug("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<AiConfig>;
}

/** PUT /ai/key — save (encrypt + upsert) the personal LLM key. */
export async function savePersonalKey(payload: KeyPayload): Promise<KeyResponse> {
  const url = `${API_BASE}/ai/key`;
  logger.info("ai-api", `PUT ${url}`, { provider: payload.provider });
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<KeyResponse>;
}

/** GET /ai/key — stored personal key metadata (never the raw key). 404 = none. */
export async function fetchPersonalKey(): Promise<KeyResponse | null> {
  const url = `${API_BASE}/ai/key`;
  logger.debug("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (response.status === 404) return null;
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<KeyResponse>;
}

/** DELETE /ai/key — remove the personal key. */
export async function deletePersonalKey(): Promise<void> {
  const url = `${API_BASE}/ai/key`;
  logger.info("ai-api", `DELETE ${url}`);
  const response = await fetch(url, { method: "DELETE", credentials: "include" });
  if (!response.ok) throw await parseError(response);
}

/** POST /ai/list-models — models available at the provider (pure lookup). */
export async function listProviderModels(
  payload: ListModelsPayload,
): Promise<ProviderModel[]> {
  const url = `${API_BASE}/ai/list-models`;
  logger.info("ai-api", `POST ${url}`, { provider: payload.provider });
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await parseError(response);
  const data = (await response.json()) as { models: ProviderModel[] };
  return data.models;
}
