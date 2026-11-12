/**
 * AI Assistant panel — right slide-in chat about the loaded capture.
 *
 * Follows the existing right-panel grammar: drag handle to resize,
 * slide-fade entrance, X close. Non-streaming: the answer arrives whole.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import {
  Sparkles,
  X,
  Settings,
  Send,
  Paperclip,
  MessageCircle,
  Loader2,
  Check,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { useAiStore } from "@/stores/ai.store";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";
import { fetchPersonalKey, type KeyResponse } from "@/api/ai.api";
import { cn } from "@/lib/utils";

/** Panel width bounds (px). */
const PANEL_MIN = 280;
const PANEL_MAX = 640;
const PANEL_DEFAULT = 380;

/** UI-level provider choices mapped to the backend's provider + default base URL. */
const PROVIDER_OPTIONS = [
  { value: "openrouter", labelKey: "aiProviderOpenRouter", provider: "openai", baseUrl: "https://openrouter.ai/api/v1" },
  { value: "openai", labelKey: "aiProviderOpenAI", provider: "openai", baseUrl: "" },
  { value: "anthropic", labelKey: "aiProviderAnthropic", provider: "anthropic", baseUrl: "" },
] as const;

type ProviderChoice = (typeof PROVIDER_OPTIONS)[number]["value"];

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

interface AIAssistantPanelProps {
  /** Current session ID, or null when no capture is loaded. */
  sessionId: string | null;
}

/** Right slide-in AI chat panel. */
export function AIAssistantPanel({ sessionId }: AIAssistantPanelProps) {
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
  const saveKey = useAiStore((s) => s.saveKey);
  const removeKey = useAiStore((s) => s.removeKey);
  const testKey = useAiStore((s) => s.testKey);
  const keyBusy = useAiStore((s) => s.keyBusy);
  const keyTesting = useAiStore((s) => s.keyTesting);
  const keyTestResult = useAiStore((s) => s.keyTestResult);
  const keyError = useAiStore((s) => s.keyError);

  // Focus hints from the current UI state (selected node, followed stream).
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const followedStream = useUiStore((s) => s.followedStream);

  const [width, setWidth] = useState(PANEL_DEFAULT);
  const [input, setInput] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [storedKey, setStoredKey] = useState<KeyResponse | null>(null);
  const [providerChoice, setProviderChoice] = useState<ProviderChoice>("openrouter");
  const [baseUrl, setBaseUrl] = useState<string>(PROVIDER_OPTIONS[0].baseUrl);
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");

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

  // ── Prefill the settings form from the stored key ───────────────
  useEffect(() => {
    if (!showSettings) return;
    let cancelled = false;
    fetchPersonalKey()
      .then((key) => {
        if (cancelled) return;
        setStoredKey(key);
        if (key) {
          const choice =
            key.provider === "anthropic"
              ? "anthropic"
              : key.base_url === "https://openrouter.ai/api/v1"
                ? "openrouter"
                : "openai";
          setProviderChoice(choice);
          setBaseUrl(key.base_url ?? "");
          setModel(key.model);
        }
      })
      .catch(() => {
        if (!cancelled) setStoredKey(null);
      });
    return () => {
      cancelled = true;
    };
  }, [showSettings]);

  if (!panelOpen) return null;

  const isEnterprise = aiConfig?.mode === "enterprise";
  const showGear = aiConfig !== null && !isEnterprise;

  const handleSend = () => {
    if (!sessionId || !input.trim() || sending) return;
    const focus = {
      node_id: selectedNodeId ?? undefined,
      stream_id: followedStream ?? undefined,
    };
    void sendQuestion(sessionId, input, Object.values(focus).some((v) => v != null) ? focus : null);
    setInput("");
  };

  const handleProviderChange = (choice: ProviderChoice) => {
    setProviderChoice(choice);
    const option = PROVIDER_OPTIONS.find((o) => o.value === choice);
    if (option) setBaseUrl(option.baseUrl);
  };

  const handleSaveKey = async () => {
    const option = PROVIDER_OPTIONS.find((o) => o.value === providerChoice);
    if (!option || !apiKey.trim()) return;
    const ok = await saveKey({
      provider: option.provider,
      base_url: baseUrl.trim(),
      model: model.trim(),
      api_key: apiKey.trim(),
    });
    if (ok) {
      setApiKey("");
      setShowSettings(false);
    }
  };

  const handleRemoveKey = async () => {
    if (!confirm(t("aiRemoveKeyConfirm"))) return;
    const ok = await removeKey();
    if (ok) {
      setStoredKey(null);
      setProviderChoice("openrouter");
      setBaseUrl(PROVIDER_OPTIONS[0].baseUrl);
      setModel("");
      setApiKey("");
    }
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
  // mode=none & signed in → the setup form is always visible inline.
  const settingsVisible = showSettings || (aiConfig?.mode === "none" && aiConfig.allowPersonalKeys);

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
          {showGear && (
            <button
              onClick={() => setShowSettings((v) => !v)}
              className={cn(
                "text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90",
                showSettings && "text-blue-400 hover:text-blue-300",
              )}
              title={t("aiSettings")}
            >
              <Settings className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setPanelOpen(false)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Settings form (personal mode; always inline when no key is set) */}
        {settingsVisible && (
          <div className="border-b border-zinc-800 p-4 space-y-3 shrink-0 overflow-y-auto max-h-[60%]">
            <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
              {t("aiSettings")}
            </p>

            <label className="block">
              <span className="text-xs text-zinc-500">{t("aiProvider")}</span>
              <select
                value={providerChoice}
                onChange={(e) => handleProviderChange(e.target.value as ProviderChoice)}
                className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
              >
                {PROVIDER_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {t(o.labelKey)}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs text-zinc-500">{t("aiBaseUrl")}</span>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://openrouter.ai/api/v1"
                className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </label>

            <label className="block">
              <span className="text-xs text-zinc-500">{t("aiModel")}</span>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="anthropic/claude-3.5-haiku"
                className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </label>

            <label className="block">
              <span className="text-xs text-zinc-500">{t("aiApiKey")}</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={storedKey ? storedKey.keyMasked : ""}
                className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
              />
              {storedKey && (
                <span className="mt-1 block text-[11px] text-zinc-500">
                  {t("aiApiKeyStored").replace("{masked}", storedKey.keyMasked)}
                </span>
              )}
            </label>

            {/* Test connection */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  const option = PROVIDER_OPTIONS.find((o) => o.value === providerChoice);
                  if (!option || !apiKey.trim()) return;
                  void testKey({
                    provider: option.provider,
                    base_url: baseUrl.trim(),
                    model: model.trim(),
                    api_key: apiKey.trim(),
                  });
                }}
                disabled={!apiKey.trim() || keyTesting}
                className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {keyTesting ? t("aiTesting") : t("aiTestConnection")}
              </button>
              {keyTestResult && (
                <span
                  className={cn(
                    "flex items-center gap-1 text-xs",
                    keyTestResult.ok ? "text-emerald-400" : "text-rose-400",
                  )}
                >
                  {keyTestResult.ok ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <AlertTriangle className="h-3 w-3" />
                  )}
                  {keyTestResult.ok ? t("aiTestOk") : keyTestResult.message}
                </span>
              )}
            </div>

            {/* Save / Remove */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => void handleSaveKey()}
                disabled={!apiKey.trim() || keyBusy}
                className="px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {keyBusy ? t("aiSaving") : t("aiSave")}
              </button>
              {storedKey && (
                <button
                  onClick={() => void handleRemoveKey()}
                  disabled={keyBusy}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-rose-900/60 hover:text-rose-300 text-zinc-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Trash2 className="h-3 w-3" />
                  {t("aiRemoveKey")}
                </button>
              )}
            </div>

            {keyError && (
              <p className="text-xs text-rose-400 flex items-start gap-1">
                <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                {keyError}
              </p>
            )}
          </div>
        )}

        {/* Messages / empty state */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {emptyState ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex items-start gap-2 text-sm text-zinc-400 bg-zinc-800/60 border border-zinc-700/60 rounded-lg p-3 max-w-[85%]">
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <span>{emptyState}</span>
              </div>
            </div>
          ) : isLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
            </div>
          ) : (
            <>
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[85%] bg-blue-600 text-white text-sm rounded-lg rounded-br-sm px-3 py-2 whitespace-pre-wrap break-words">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="flex flex-col items-start">
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
