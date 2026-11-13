/**
 * AI Assistant panel — right slide-in chat about the loaded capture.
 *
 * Follows the existing right-panel grammar: drag handle to resize,
 * slide-fade entrance, X close. Non-streaming: the answer arrives whole.
 * Key/settings management lives on the AISettingsPage — this panel is
 * chat-only; its no-key empty state links there.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import {
  Sparkles,
  X,
  Send,
  Paperclip,
  MessageCircle,
  Loader2,
  AlertTriangle,
  Download,
  Trash2,
  Plus,
} from "lucide-react";
import { useAiStore } from "@/stores/ai.store";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

/** Panel width bounds (px). */
const PANEL_MIN = 280;
const PANEL_MAX = 640;
const PANEL_DEFAULT = 380;

/** Render markdown to sanitized HTML (marked + DOMPurify — tiny, no bloat). */
function renderMarkdown(md: string): string {
  const html = marked.parse(md, { async: false, breaks: true });
  return DOMPurify.sanitize(html);
}

/** Tailwind arbitrary variants styling the markdown output. */
const MD_CLASSES =
  "[&_h1]:text-base [&_h1]:font-semibold [&_h1]:my-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:my-2 " +
  "[&_h3]:text-sm [&_h3]:font-medium [&_h3]:my-2 [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-2 " +
  "[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:my-2 [&_li]:my-0.5 [&_strong]:font-semibold " +
  "[&_code]:bg-zinc-800 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[11px] [&_code]:font-mono " +
  "[&_pre]:bg-zinc-800 [&_pre]:rounded [&_pre]:p-2 [&_pre]:overflow-x-auto [&_pre]:my-2 [&_pre_code]:bg-transparent [&_pre_code]:p-0 " +
  "[&_a]:text-blue-400 [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-zinc-700 " +
  "[&_blockquote]:pl-2 [&_blockquote]:text-zinc-400 [&_table]:text-xs [&_table]:my-2 " +
  "[&_th]:border [&_th]:border-zinc-700 [&_th]:px-1.5 [&_th]:py-0.5 [&_td]:border [&_td]:border-zinc-700 [&_td]:px-1.5 [&_td]:py-0.5";

/** Format a token count compactly: 1234 → "1.2k". */
function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

/** Format a message timestamp as a short local time label. */
function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface AIAssistantPanelProps {
  /** Current session ID, or null when no capture is loaded. */
  sessionId: string | null;
  /** Navigate to the full-page AI Settings (closes this panel). */
  onOpenSettings: () => void;
}

/** Right slide-in AI chat panel. */
export function AIAssistantPanel({ sessionId, onOpenSettings }: AIAssistantPanelProps) {
  const { t } = useI18n();

  const panelOpen = useAiStore((s) => s.panelOpen);
  const setPanelOpen = useAiStore((s) => s.setPanelOpen);
  const messages = useAiStore((s) => s.messages);
  const sending = useAiStore((s) => s.sending);
  const error = useAiStore((s) => s.error);
  const retryAfterSeconds = useAiStore((s) => s.retryAfterSeconds);
  const aiConfig = useAiStore((s) => s.aiConfig);
  const configStatus = useAiStore((s) => s.configStatus);
  const signedOut = useAiStore((s) => s.signedOut);
  const sendQuestion = useAiStore((s) => s.sendQuestion);
  const currentChatId = useAiStore((s) => s.currentChatId);
  const newChat = useAiStore((s) => s.newChat);
  const deleteChat = useAiStore((s) => s.deleteChat);
  const exportChatById = useAiStore((s) => s.exportChatById);

  // Focus hints from the current UI state (selected node, followed stream).
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const followedStream = useUiStore((s) => s.followedStream);

  const [width, setWidth] = useState(PANEL_DEFAULT);
  const [input, setInput] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  const resizing = useRef(false);

  // ── Panel resize (drag the left handle) ─────────────────────────
  const startResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    resizing.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!resizing.current) return;
      setWidth(Math.min(PANEL_MAX, Math.max(PANEL_MIN, window.innerWidth - e.clientX)));
    };
    const onUp = () => {
      if (!resizing.current) return;
      resizing.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  // ── Auto-scroll to the newest message ───────────────────────────
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sending]);

  if (!panelOpen) return null;

  const isEnterprise = aiConfig?.mode === "enterprise";

  const handleSend = () => {
    if (!sessionId || !input.trim() || sending) return;
    const focus = {
      node_id: selectedNodeId ?? undefined,
      stream_id: followedStream ?? undefined,
    };
    void sendQuestion(sessionId, input, Object.values(focus).some((v) => v != null) ? focus : null);
    setInput("");
  };

  const handleExport = () => {
    if (!currentChatId) return;
    void exportChatById(currentChatId);
  };

  const handleClear = () => {
    if (!currentChatId) return;
    if (!confirm(t("aiDeleteChatConfirm"))) return;
    void deleteChat(currentChatId);
  };

  // ── Empty / blocked states ──────────────────────────────────────
  const isLoading = configStatus === "idle" || configStatus === "loading";
  const emptyState = (() => {
    if (!sessionId) return t("aiLoadFirst");
    if (isLoading) return null; // spinner
    if (configStatus === "error") return t("aiConfigError");
    if (signedOut) return t("aiSignInNeeded");
    if (!aiConfig) return t("aiConfigError");
    if (aiConfig.mode === "unavailable") return aiConfig.reasons.join(" ");
    if (aiConfig.mode === "none") {
      return aiConfig.allowPersonalKeys ? t("aiNoKey") : t("aiEnterpriseOnly");
    }
    return null; // enterprise | personal → chat
  })();

  const chatBlocked = emptyState !== null || isLoading;
  // No-key states (with or without personal keys allowed) link to the settings page.
  const showSettingsButton = aiConfig?.mode === "none";

  const rateLimit = aiConfig?.rateLimit ?? null;
  const showRateLimit = isEnterprise && rateLimit != null && rateLimit.limit > 0;

  return (
    <div
      className="absolute inset-y-0 right-0 z-40 flex animate-fade-slide-in-right"
      style={{ width }}
    >
      {/* Drag handle — resize */}
      <div
        onPointerDown={startResize}
        className="w-1 shrink-0 cursor-col-resize bg-zinc-800 hover:bg-blue-500 transition-colors"
        title="Drag to resize"
      />
      <div className="flex-1 min-w-0 flex flex-col bg-zinc-900 border-l border-zinc-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 shrink-0">
          <Sparkles className="h-4 w-4 text-blue-400 shrink-0" />
          <h3 className="font-semibold text-zinc-200 truncate">{t("aiAssistant")}</h3>
          {isEnterprise && (
            <span className="px-2 py-0.5 text-[10px] font-medium rounded bg-blue-950/60 text-blue-300 border border-blue-800/60 shrink-0">
              {t("aiEnterpriseBadge")}
            </span>
          )}
          <div className="flex-1" />
          {sessionId && !chatBlocked && (
            <button
              onClick={newChat}
              className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
              title={t("aiNewChat")}
            >
              <Plus className="h-4 w-4" />
            </button>
          )}
          {/* Export / Clear act on the CURRENT chat (needs a saved chat id). */}
          {sessionId && !chatBlocked && currentChatId && (
            <>
              <button
                onClick={handleExport}
                className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
                title={t("aiExportChat")}
              >
                <Download className="h-4 w-4" />
              </button>
              <button
                onClick={handleClear}
                className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
                title={t("aiClearChat")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
          <button
            onClick={() => setPanelOpen(false)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages / empty state */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {emptyState ? (
            <div className="h-full flex flex-col items-center justify-center gap-3">
              <div className="flex items-start gap-2 text-sm text-zinc-400 bg-zinc-800/60 border border-zinc-700/60 rounded-lg p-3 max-w-[85%]">
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <span>{emptyState}</span>
              </div>
              {showSettingsButton && (
                <button
                  onClick={() => {
                    setPanelOpen(false);
                    onOpenSettings();
                  }}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-all active:scale-[0.97] shadow-lg"
                >
                  {t("aiOpenSettings")}
                </button>
              )}
            </div>
          ) : isLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
            </div>
          ) : (
            <>
              {messages.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center gap-2 text-zinc-600">
                  <MessageCircle className="h-5 w-5" />
                  <span className="text-xs">{t("aiNoMessages")}</span>
                </div>
              )}
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex flex-col items-end">
                    <span className="mb-0.5 text-[10px] text-zinc-600">
                      {formatTime(m.ts)}
                    </span>
                    <div className="max-w-[85%] bg-blue-600 text-white text-sm rounded-lg rounded-br-sm px-3 py-2 whitespace-pre-wrap break-words">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="flex flex-col items-start">
                    <span className="mb-0.5 text-[10px] text-zinc-600">
                      {formatTime(m.ts)}
                    </span>
                    <div
                      className={cn(
                        "max-w-[95%] bg-zinc-800 text-zinc-200 text-sm rounded-lg rounded-bl-sm px-3 py-2 break-words",
                        MD_CLASSES,
                      )}
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                    />
                    {/* Context chip: what was sent + approx tokens */}
                    {m.context && m.context.length > 0 && (
                      <span className="mt-1 flex items-center gap-1 text-[10px] text-zinc-500">
                        <Paperclip className="h-3 w-3" />
                        {m.context.map((b) => b.name).join(" + ")}
                        <span className="text-zinc-600">
                          · ~{formatTokens(m.context.reduce((sum, b) => sum + b.approxTokens, 0))}{" "}
                          {t("aiTokens")}
                        </span>
                      </span>
                    )}
                  </div>
                ),
              )}
              {sending && (
                <div className="flex items-center gap-2 text-zinc-500 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("aiThinking")}
                </div>
              )}
            </>
          )}
        </div>

        {/* Error banner (e.g. 429 rate limit) */}
        {error && !chatBlocked && (
          <div className="mx-4 mb-2 px-3 py-2 text-xs text-rose-300 bg-rose-950/60 border border-rose-800/60 rounded-lg flex items-start gap-1.5 shrink-0">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>
              {retryAfterSeconds != null
                ? t("aiRateLimitHit").replace("{seconds}", String(retryAfterSeconds))
                : error}
            </span>
          </div>
        )}

        {/* Input + rate-limit counter */}
        {!chatBlocked && (
          <div className="p-3 border-t border-zinc-800 shrink-0 space-y-2">
            {showRateLimit && (
              <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <MessageCircle className="h-3 w-3" />
                {t("aiRateLimit")
                  .replace("{n}", String(rateLimit.remaining))
                  .replace("{m}", String(rateLimit.limit))}
              </div>
            )}
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={2}
                placeholder={t("aiInputPlaceholder")}
                className="flex-1 resize-none bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200
                           placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || sending}
                className="p-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors
                           disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                title={t("aiSend")}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
