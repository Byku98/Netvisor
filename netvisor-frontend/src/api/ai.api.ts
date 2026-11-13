/**
 * AI assistant API client — mirrors netvisor-backend/src/api/routes/ai.py.
 *
 * Endpoints:
 *   POST   /sessions/{id}/ask   — ask a question about the loaded capture;
 *                               optional chat_id appends to that chat, omitting
 *                               it auto-creates a new chat (response carries chat_id)
 *   GET    /ai/chats            — all of the user's chats, newest first
 *   DELETE /ai/chats/{id}       — delete one chat and its messages (204)
 *   GET    /ai/chats/{id}/export  — one chat as a markdown download
 *   GET    /ai/config           — which AI mode is active for this user
 *   PUT    /ai/key              — save personal LLM key (encrypted server-side);
 *                               api_key optional (omit = keep stored key)
 *   GET    /ai/key              — stored key metadata (NEVER the raw key)
 *   DELETE /ai/key              — remove the personal key
 *   POST   /ai/list-models      — models available at the provider (saves nothing)
 *   POST   /ai/models           — models via the STORED key (no body; saves nothing)
 *   GET    /ai/usage            — per-day usage for the last 30 days
 *   GET    /ai/usage/export     — usage as a markdown download
 *   DELETE /ai/usage            — clear all usage rows (204)
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
  /** Append to this chat; omit/null → the server auto-creates a new chat. */
  chat_id?: string | null;
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
  /** Chat the question was appended to (created on the fly when omitted). */
  chat_id: string;
}

/** One chat summary from GET /ai/chats (newest first). */
export interface ChatSummary {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
  /** Sum of ai_usage.tokens for this chat (0 when nothing was recorded). */
  tokens: number;
  /** Filename of the session the chat belongs to, when available. */
  session_filename: string | null;
}

/** GET /ai/chats response. */
export interface ChatListResponse {
  chats: ChatSummary[];
}

/** PUT /ai/key request body. */
export interface KeyPayload {
  provider: "openai" | "anthropic";
  base_url?: string;
  model: string;
  /** Optional: omit/empty keeps the stored key (e.g. model-only updates). */
  api_key?: string;
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

/** One aggregated day from GET /ai/usage (UTC days, newest first). */
export interface AiUsageDay {
  date: string;
  messages: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number | null;
}

/** GET /ai/usage response — last 30 days plus totals and the active mode. */
export interface AiUsageResponse {
  days: AiUsageDay[];
  totals: {
    messages: number;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number | null;
  };
  current: { mode: string; provider: string | null; model: string | null };
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

/** Download a fetch Response body using its Content-Disposition filename. */
async function downloadResponse(response: Response, fallbackName: string): Promise<void> {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] ?? fallbackName;
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

/** GET /ai/chats — all of the user's chats across all sessions, newest first. */
export async function fetchUserChats(): Promise<ChatListResponse> {
  const url = `${API_BASE}/ai/chats`;
  logger.debug("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<ChatListResponse>;
}

/** DELETE /ai/chats/{chatId} — delete one chat and its messages (204). */
export async function deleteChatById(chatId: string): Promise<void> {
  const url = `${API_BASE}/ai/chats/${chatId}`;
  logger.info("ai-api", `DELETE ${url}`);
  const response = await fetch(url, { method: "DELETE", credentials: "include" });
  if (!response.ok) throw await parseError(response);
}

/** GET /ai/chats/{chatId}/export — download one chat as a markdown file. */
export async function exportChatById(chatId: string): Promise<void> {
  const url = `${API_BASE}/ai/chats/${chatId}/export`;
  logger.info("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw await parseError(response);
  await downloadResponse(response, `netvisor-chat-${chatId}.md`);
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

/** POST /ai/models — list models using the STORED key (no body; pure lookup). */
export async function listStoredModels(): Promise<{
  models: ProviderModel[];
  source: "personal" | "enterprise";
}> {
  const url = `${API_BASE}/ai/models`;
  logger.info("ai-api", `POST ${url}`);
  const response = await fetch(url, { method: "POST", credentials: "include" });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<{
    models: ProviderModel[];
    source: "personal" | "enterprise";
  }>;
}

/** GET /ai/usage — per-day usage aggregation for the last 30 days. */
export async function fetchAiUsage(): Promise<AiUsageResponse> {
  const url = `${API_BASE}/ai/usage`;
  logger.debug("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<AiUsageResponse>;
}

/** GET /ai/usage/export — download the usage summary as a markdown file. */
export async function exportAiUsage(): Promise<void> {
  const url = `${API_BASE}/ai/usage/export`;
  logger.info("ai-api", `GET ${url}`);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw await parseError(response);
  await downloadResponse(response, "netvisor-ai-usage.md");
}

/** DELETE /ai/usage — clear all usage rows (204). */
export async function clearAiUsage(): Promise<void> {
  const url = `${API_BASE}/ai/usage`;
  logger.info("ai-api", `DELETE ${url}`);
  const response = await fetch(url, { method: "DELETE", credentials: "include" });
  if (!response.ok) throw await parseError(response);
}
