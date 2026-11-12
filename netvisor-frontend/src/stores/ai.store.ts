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
  deletePersonalKey,
  fetchAiConfig,
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
  /** True when the panel was opened directly in settings mode (profile menu). */
  settingsMode: boolean;
  /** Chat history (oldest first). */
  messages: AiMessage[];
  /** True while awaiting an answer. */
  sending: boolean;
  /** Last ask error (shown as a banner above the input). */
  error: string | null;
  /** Retry-After seconds from a 429, or null. */
  retryAfterSeconds: number | null;

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
  /** Open the panel directly in settings mode (profile menu → AI Settings). */
  openSettings: () => void;
  /** Leave settings mode (gear toggle close). */
  closeSettings: () => void;
  clearMessages: () => void;
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
    settingsMode: false,
    messages: [],
    sending: false,
    error: null,
    retryAfterSeconds: null,

    aiConfig: null,
    configStatus: "idle",
    signedOut: false,

    keyBusy: false,
    keyError: null,

    togglePanel: () => {
      const open = !get().panelOpen;
      set({ panelOpen: open, settingsMode: open ? get().settingsMode : false });
      // Load the config on first open (and refresh on re-open).
      if (open && get().configStatus !== "loading") {
        void get().loadConfig();
      }
    },

    setPanelOpen: (open) => {
      set({ panelOpen: open, settingsMode: open ? get().settingsMode : false });
      if (open && get().configStatus !== "loading") {
        void get().loadConfig();
      }
    },

    openSettings: () => {
      set({ panelOpen: true, settingsMode: true });
      if (get().configStatus !== "loading") {
        void get().loadConfig();
      }
    },

    closeSettings: () => set({ settingsMode: false }),

    clearMessages: () => set({ messages: [], error: null, retryAfterSeconds: null }),

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
