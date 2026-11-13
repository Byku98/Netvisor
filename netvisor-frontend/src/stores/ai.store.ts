/**
 * AI assistant store — chat panel state, AI config, personal key management.
 *
 * Chat is non-streaming: sendQuestion() posts the question (+ focus hints from
 * ui.store) and appends the whole answer when it arrives.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import {
  askQuestion,
  clearChat as clearChatApi,
  deletePersonalKey,
  fetchAiConfig,
  fetchChat,
  savePersonalKey,
  ApiError,
  type AiConfig,
  type AskResponse,
  type ContextBlock,
  type FocusHints,
  type KeyPayload,
} from "@/api/ai.api";
import { logger } from "@/utils/logger";

/** One chat message. AI answers carry the context manifest + token usage. */
export interface AiMessage {
  id: string;
  role: "user" | "assistant";
  /** Markdown content (user messages are plain text). */
  content: string;
  /** Context blocks sent to the LLM for this answer (assistant only). */
  context?: ContextBlock[];
  /** Token usage for this answer (assistant only). */
  usage?: { promptTokens: number; completionTokens: number };
  ts: number;
}

interface AiState {
  /** Chat panel visibility. */
  panelOpen: boolean;
  /** Chat history (oldest first). */
  messages: AiMessage[];
  /** True while awaiting an answer. */
  sending: boolean;
  /** Last ask error (shown as a banner above the input). */
  error: string | null;
  /** Retry-After seconds from a 429, or null. */
  retryAfterSeconds: number | null;
  /** Persisted-history load state for the current session. */
  historyStatus: "idle" | "loading" | "loaded" | "error";

  /** GET /ai/config result, or null before the first load. */
  aiConfig: AiConfig | null;
  configStatus: "idle" | "loading" | "loaded" | "error";
  /** True when /ai/config returned 401 (not signed in). */
  signedOut: boolean;

  /** Saving / removing the personal key. */
  keyBusy: boolean;
  /** Last key-management error. */
  keyError: string | null;

  togglePanel: () => void;
  setPanelOpen: (open: boolean) => void;
  clearMessages: () => void;
  /** Load the persisted conversation for a session into messages. */
  loadHistory: (sessionId: string) => Promise<void>;
  /** Delete the persisted conversation server-side and clear the local list. */
  clearChat: (sessionId: string) => Promise<boolean>;
  /** Load (or reload) the AI config. */
  loadConfig: () => Promise<void>;
  /** Send a question about the session's capture. */
  sendQuestion: (sessionId: string, question: string, focus: FocusHints | null) => Promise<void>;
  /** Save the personal key; returns true on success. */
  saveKey: (payload: KeyPayload) => Promise<boolean>;
  /** Remove the personal key; returns true on success. */
  removeKey: () => Promise<boolean>;
}

let messageSeq = 0;
function nextMessageId(): string {
  messageSeq += 1;
  return `ai-msg-${Date.now()}-${messageSeq}`;
}

export const useAiStore = create<AiState>()(
  devtools((set, get) => ({
    panelOpen: false,
    messages: [],
    sending: false,
    error: null,
    retryAfterSeconds: null,
    historyStatus: "idle",

    aiConfig: null,
    configStatus: "idle",
    signedOut: false,

    keyBusy: false,
    keyError: null,

    togglePanel: () => {
      const open = !get().panelOpen;
      set({ panelOpen: open });
      // Load the config on first open (and refresh on re-open).
      if (open && get().configStatus !== "loading") {
        void get().loadConfig();
      }
    },

    setPanelOpen: (open) => {
      set({ panelOpen: open });
      if (open && get().configStatus !== "loading") {
        void get().loadConfig();
      }
    },

    clearMessages: () => set({ messages: [], error: null, retryAfterSeconds: null }),

    loadHistory: async (sessionId) => {
      if (get().historyStatus === "loading") return;
      set({ historyStatus: "loading", messages: [], error: null, retryAfterSeconds: null });
      try {
        const history = await fetchChat(sessionId);
        const messages: AiMessage[] = history.messages.map((m, i) => ({
          id: `ai-history-${sessionId}-${i}`,
          role: m.role,
          content: m.content,
          ts: new Date(m.created_at).getTime() || Date.now(),
        }));
        logger.info("ai-store", "Chat history loaded", { count: messages.length });
        set({ messages, historyStatus: "loaded" });
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Chat history load failed", { detail });
        set({ historyStatus: "error", error: detail });
      }
    },

    clearChat: async (sessionId) => {
      try {
        await clearChatApi(sessionId);
        logger.info("ai-store", "Chat cleared", { sessionId });
        set({
          messages: [],
          error: null,
          retryAfterSeconds: null,
          historyStatus: "loaded",
        });
        return true;
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Clear chat failed", { detail });
        set({ error: detail });
        return false;
      }
    },

    loadConfig: async () => {
      if (get().configStatus === "loading") return;
      set({ configStatus: "loading", signedOut: false });
      try {
        const config = await fetchAiConfig();
        logger.info("ai-store", "AI config loaded", { mode: config.mode });
        set({ aiConfig: config, configStatus: "loaded", signedOut: false });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          logger.info("ai-store", "AI config: not signed in");
          set({ aiConfig: null, configStatus: "loaded", signedOut: true });
        } else {
          logger.error("ai-store", "AI config load failed", e);
          set({ aiConfig: null, configStatus: "error", signedOut: false });
        }
      }
    },

    sendQuestion: async (sessionId, question, focus) => {
      const trimmed = question.trim();
      if (!trimmed || get().sending) return;
      const userMessage: AiMessage = {
        id: nextMessageId(),
        role: "user",
        content: trimmed,
        ts: Date.now(),
      };
      set((state) => ({
        messages: [...state.messages, userMessage],
        sending: true,
        error: null,
        retryAfterSeconds: null,
      }));
      try {
        const response: AskResponse = await askQuestion(sessionId, {
          question: trimmed,
          focus,
        });
        const assistantMessage: AiMessage = {
          id: nextMessageId(),
          role: "assistant",
          content: response.answer_md,
          context: response.context,
          usage: {
            promptTokens: response.usage.prompt_tokens,
            completionTokens: response.usage.completion_tokens,
          },
          ts: Date.now(),
        };
        set((state) => ({
          messages: [...state.messages, assistantMessage],
          sending: false,
        }));
        // Refresh the enterprise rate-limit counter from the response.
        if (response.rate_limit) {
          const config = get().aiConfig;
          if (config) {
            set({
              aiConfig: { ...config, rateLimit: response.rate_limit },
            });
          }
        }
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Ask failed", { detail });
        set({
          sending: false,
          error: detail,
          retryAfterSeconds: e instanceof ApiError ? e.retryAfterSeconds : null,
        });
      }
    },

    saveKey: async (payload) => {
      set({ keyBusy: true, keyError: null });
      try {
        await savePersonalKey(payload);
        logger.info("ai-store", "Personal key saved", { provider: payload.provider });
        set({ keyBusy: false });
        await get().loadConfig();
        return true;
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Save key failed", { detail });
        set({ keyBusy: false, keyError: detail });
        return false;
      }
    },

    removeKey: async () => {
      set({ keyBusy: true, keyError: null });
      try {
        await deletePersonalKey();
        logger.info("ai-store", "Personal key removed");
        set({ keyBusy: false });
        await get().loadConfig();
        return true;
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Remove key failed", { detail });
        set({ keyBusy: false, keyError: detail });
        return false;
      }
    },

  }))
);
