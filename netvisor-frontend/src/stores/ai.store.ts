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
  deleteChatById,
  deletePersonalKey,
  exportChatById as exportChatByIdApi,
  fetchAiConfig,
  fetchChatById,
  fetchSessionChats,
  savePersonalKey,
  ApiError,
  type AiConfig,
  type AskResponse,
  type ChatSummary,
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
  /** Persisted-history load state for the chat currently in view. */
  historyStatus: "idle" | "loading" | "loaded" | "error";

  /** Chat the panel is viewing; null = fresh unsaved chat (next send creates one). */
  currentChatId: string | null;
  /** Previous chats for the loaded session (newest first). */
  chats: ChatSummary[];
  /** Chat-list load state. */
  chatsStatus: "idle" | "loading" | "loaded" | "error";
  /** Session the chats list was loaded for (guards duplicate loads). */
  chatsSessionId: string | null;

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
  /** Load (or reload) the chat list for a session; resets to a fresh chat
   *  when the session changes. `force` bypasses the already-loaded guard. */
  loadChats: (sessionId: string, force?: boolean) => Promise<void>;
  /** Start a fresh unsaved chat: the next send auto-creates one server-side. */
  newChat: () => void;
  /** Load a previous chat into the message area and make it current. */
  switchChat: (chatId: string) => Promise<void>;
  /** Delete a chat server-side; if it was current, fall back to a fresh chat. */
  deleteChat: (chatId: string) => Promise<boolean>;
  /** Download one chat as a markdown file. */
  exportChatById: (chatId: string) => Promise<void>;
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

    currentChatId: null,
    chats: [],
    chatsStatus: "idle",
    chatsSessionId: null,

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

    loadChats: async (sessionId, force = false) => {
      if (
        !force &&
        get().chatsSessionId === sessionId &&
        get().chatsStatus !== "error"
      ) {
        return; // already loaded for this session
      }
      // New session → start a fresh unsaved chat.
      set({
        chatsSessionId: sessionId,
        chatsStatus: "loading",
        chats: [],
        currentChatId: null,
        messages: [],
        error: null,
        retryAfterSeconds: null,
        historyStatus: "loaded",
      });
      try {
        const data = await fetchSessionChats(sessionId);
        logger.info("ai-store", "Chat list loaded", { count: data.chats.length });
        set({ chats: data.chats, chatsStatus: "loaded" });
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Chat list load failed", { detail });
        set({ chatsStatus: "error", error: detail });
      }
    },

    newChat: () =>
      set({
        currentChatId: null,
        messages: [],
        error: null,
        retryAfterSeconds: null,
        historyStatus: "loaded",
      }),

    switchChat: async (chatId) => {
      if (get().currentChatId === chatId) return;
      set({ historyStatus: "loading", error: null, retryAfterSeconds: null });
      try {
        const detail = await fetchChatById(chatId);
        const messages: AiMessage[] = detail.messages.map((m, i) => ({
          id: `ai-chat-${chatId}-${i}`,
          role: m.role,
          content: m.content,
          ts: new Date(m.created_at).getTime() || Date.now(),
        }));
        logger.info("ai-store", "Chat loaded", { chatId, count: messages.length });
        set({ currentChatId: chatId, messages, historyStatus: "loaded" });
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Chat load failed", { detail });
        set({ historyStatus: "error", error: detail });
      }
    },

    deleteChat: async (chatId) => {
      try {
        await deleteChatById(chatId);
        logger.info("ai-store", "Chat deleted", { chatId });
        set((state) => ({ chats: state.chats.filter((c) => c.id !== chatId) }));
        if (get().currentChatId === chatId) get().newChat();
        return true;
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Delete chat failed", { detail });
        set({ error: detail });
        return false;
      }
    },

    exportChatById: async (chatId) => {
      try {
        await exportChatByIdApi(chatId);
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.detail : (e as Error).message ?? "Request failed";
        logger.error("ai-store", "Chat export failed", { detail });
        set({ error: detail });
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
        const chatId = get().currentChatId;
        const response: AskResponse = await askQuestion(sessionId, {
          question: trimmed,
          focus,
          chat_id: chatId,
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
          currentChatId: response.chat_id,
        }));
        // A brand-new chat was created server-side → refresh the chat list.
        if (!chatId) void get().loadChats(sessionId, true);
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
