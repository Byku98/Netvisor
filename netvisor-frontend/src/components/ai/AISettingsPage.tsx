/**
 * AI Settings page — full-page personal-key management.
 *
 * Follows the MySessions page pattern: AppHeader, back button, signed-out
 * state. Hosts the settings form that used to live inside AIAssistantPanel:
 * base URL + key → Connect → model dropdown → Save / Remove. With a stored
 * key a tabbed section (Usage / Chat history) shows the last 30 days of AI
 * usage and every saved chat with per-row export / delete — both lists
 * paginated client-side, 20 rows per page.
 */

import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/auth/AppHeader";
import { useAuthStore } from "@/stores/auth.store";
import { useAiStore } from "@/stores/ai.store";
import { useI18n } from "@/i18n";
import {
  ApiError,
  clearAiUsage,
  exportAiUsage,
  fetchAiUsage,
  fetchPersonalKey,
  fetchUserChats,
  listProviderModels,
  listStoredModels,
  type AiUsageResponse,
  type ChatSummary,
  type KeyPayload,
  type KeyResponse,
  type ProviderModel,
} from "@/api/ai.api";
import {
  Settings,
  ArrowLeft,
  Loader2,
  Check,
  AlertTriangle,
  Download,
  Trash2,
  RefreshCw,
  BarChart3,
  History,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logger } from "@/utils/logger";

/** Default prefill for the Base URL input (OpenRouter). */
const DEFAULT_BASE_URL = "https://openrouter.ai/api/v1";

/** Rows per page in the paginated Usage / Chat history lists (client-side). */
const PAGE_SIZE = 20;

/** Resolve the backend provider from the Base URL: Anthropic API vs anything OpenAI-compatible. */
function resolveProvider(baseUrl: string): "anthropic" | "openai" {
  return baseUrl.includes("api.anthropic.com") ? "anthropic" : "openai";
}

/** Format an ISO date as a local date + time label (chat history rows). */
function formatDate(iso: string): string {
  return new Date(iso).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Pagination footer for the paginated lists: ‹ Prev / Next › + "Page X of Y". */
function PaginationFooter({
  page,
  totalPages,
  onPrev,
  onNext,
}: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  const { t } = useI18n();
  const btn =
    "px-2 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="flex items-center justify-end gap-2 text-xs">
      <button onClick={onPrev} disabled={page <= 1} className={btn}>
        ‹ {t("aiPagePrev")}
      </button>
      <span className="text-zinc-500">
        {t("aiPageOf").replace("{x}", String(page)).replace("{y}", String(totalPages))}
      </span>
      <button onClick={onNext} disabled={page >= totalPages} className={btn}>
        {t("aiPageNext")} ›
      </button>
    </div>
  );
}

interface AISettingsPageProps {
  /** Return to the view the user came from. */
  onBack: () => void;
  /** Go to the upload screen (header logo). */
  onHome: () => void;
  /** Show My Sessions (header profile dropdown). */
  onMySessions: () => void;
  /** Go back to the upload screen (header "New Session"). */
  onNewSession: () => void;
  /** Reopen the AI chat panel — offered after saving a key (needs a loaded capture). */
  onBackToChat?: () => void;
}

/** Full-page AI settings view. */
export function AISettingsPage({
  onBack,
  onHome,
  onMySessions,
  onNewSession,
  onBackToChat,
}: AISettingsPageProps) {
  const { t } = useI18n();
  const user = useAuthStore((s) => s.user);

  const aiConfig = useAiStore((s) => s.aiConfig);
  const configStatus = useAiStore((s) => s.configStatus);
  const loadConfig = useAiStore((s) => s.loadConfig);
  const saveKey = useAiStore((s) => s.saveKey);
  const removeKey = useAiStore((s) => s.removeKey);
  const keyBusy = useAiStore((s) => s.keyBusy);
  const keyError = useAiStore((s) => s.keyError);
  const deleteChat = useAiStore((s) => s.deleteChat);
  const exportChatById = useAiStore((s) => s.exportChatById);

  const [storedKey, setStoredKey] = useState<KeyResponse | null>(null);
  const [baseUrl, setBaseUrl] = useState<string>(DEFAULT_BASE_URL);
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  /** Models fetched from the provider (null = not connected yet). */
  const [models, setModels] = useState<ProviderModel[] | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  /** Paste the model id manually instead of the provider-fetched dropdown. */
  const [manualModel, setManualModel] = useState(false);
  /** True right after a successful save — enables the "Back to chat" affordance. */
  const [justSaved, setJustSaved] = useState(false);
  /** GET /ai/usage result + load state. */
  const [usage, setUsage] = useState<AiUsageResponse | null>(null);
  const [usageState, setUsageState] = useState<"loading" | "ok" | "error">("loading");
  /** True while the stored-key model lookup (POST /ai/models) is in flight. */
  const [refreshingModels, setRefreshingModels] = useState(false);
  /** Usage-card action in flight ("export" | "delete") — disables both buttons. */
  const [usageAction, setUsageAction] = useState<"export" | "delete" | null>(null);
  /** GET /ai/chats result + load state (saved chats, newest first). */
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chatsState, setChatsState] = useState<"loading" | "ok" | "error">("loading");
  /** Chat-row action in flight ("export" | "delete") — disables the row buttons. */
  const [chatAction, setChatAction] = useState<"export" | "delete" | null>(null);
  /** Active tab in the usage/history section. */
  const [activeTab, setActiveTab] = useState<"usage" | "chats">("usage");
  /** Pagination pages (1-based) — reset to 1 on data refresh / tab switch. */
  const [usagePage, setUsagePage] = useState(1);
  const [chatsPage, setChatsPage] = useState(1);

  /** Fetch (or re-fetch) the usage summary. */
  const loadUsage = useCallback(() => {
    setUsageState("loading");
    fetchAiUsage()
      .then((data) => {
        setUsage(data);
        setUsagePage(1);
        setUsageState("ok");
      })
      .catch(() => setUsageState("error"));
  }, []);

  /** Fetch (or re-fetch) the saved-chat list. */
  const loadChatList = useCallback(() => {
    setChatsState("loading");
    fetchUserChats()
      .then((data) => {
        setChats(data.chats);
        setChatsPage(1);
        setChatsState("ok");
      })
      .catch(() => setChatsState("error"));
  }, []);

  /** Switch tabs and reset both paginations to the first page. */
  const handleTabChange = (tab: "usage" | "chats") => {
    setActiveTab(tab);
    setUsagePage(1);
    setChatsPage(1);
  };

  // Load the config and prefill the form from the stored key.
  useEffect(() => {
    if (!user) return;
    void loadConfig();
    loadUsage();
    loadChatList();
    let cancelled = false;
    fetchPersonalKey()
      .then((key) => {
        if (cancelled) return;
        setStoredKey(key);
        if (key) {
          setBaseUrl(key.base_url ?? "");
          setModel(key.model);
        }
      })
      .catch(() => {
        /* 404 = no stored key — leave the form empty */
      });
    return () => {
      cancelled = true;
    };
  }, [user, loadConfig, loadUsage, loadChatList]);

  /** Connect: resolve the provider from the Base URL and fetch its model list. */
  const handleConnect = async () => {
    if (!apiKey.trim() || connecting) return;
    setConnecting(true);
    setConnectError(null);
    setModels(null);
    try {
      const list = await listProviderModels({
        provider: resolveProvider(baseUrl),
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
      });
      const sorted = [...list].sort((a, b) => a.id.localeCompare(b.id));
      setModels(sorted);
      // Re-editing a saved key → preselect its model when still offered.
      setModel((current) =>
        storedKey && sorted.some((m) => m.id === storedKey.model) ? storedKey.model : current,
      );
      // Refresh the page state (usage + config) after a successful connect.
      loadUsage();
      void loadConfig();
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setConnectError(
        status === 401 || status === 403 ? t("aiConnectAuthFailed") : t("aiConnectFailed"),
      );
    } finally {
      setConnecting(false);
    }
  };

  /** Refresh the model list using the STORED key — no key re-entry needed. */
  const handleRefreshModels = async () => {
    if (refreshingModels) return;
    setRefreshingModels(true);
    setConnectError(null);
    try {
      const data = await listStoredModels();
      const sorted = [...data.models].sort((a, b) => a.id.localeCompare(b.id));
      setModels(sorted);
      setModel((current) =>
        storedKey && sorted.some((m) => m.id === storedKey.model) ? storedKey.model : current,
      );
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setConnectError(
        status === 401 || status === 403 ? t("aiConnectAuthFailed") : t("aiConnectFailed"),
      );
    } finally {
      setRefreshingModels(false);
    }
  };

  /** Download the usage summary as a markdown file. */
  const handleExportUsage = () => {
    if (usageAction) return;
    setUsageAction("export");
    exportAiUsage()
      .catch((e) => logger.error("ai-settings", "Usage export failed", e))
      .finally(() => setUsageAction(null));
  };

  /** Clear all usage rows, then re-fetch so the card shows the empty state. */
  const handleDeleteUsage = async () => {
    if (usageAction) return;
    if (!confirm(t("aiUsageDeleteConfirm"))) return;
    setUsageAction("delete");
    try {
      await clearAiUsage();
      loadUsage();
    } catch (e) {
      logger.error("ai-settings", "Usage delete failed", e);
    } finally {
      setUsageAction(null);
    }
  };

  /** Download one saved chat as a markdown file. */
  const handleExportChat = (chatId: string) => {
    if (chatAction) return;
    setChatAction("export");
    void exportChatById(chatId).finally(() => setChatAction(null));
  };

  /** Delete one saved chat, then drop the row and refresh the list. */
  const handleDeleteChat = async (chatId: string) => {
    if (chatAction) return;
    if (!confirm(t("aiDeleteChatConfirm"))) return;
    setChatAction("delete");
    const ok = await deleteChat(chatId);
    if (ok) {
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      loadChatList();
    }
    setChatAction(null);
  };

  /** Changing credentials invalidates the fetched model list. */
  const handleCredentialsChange =
    (setter: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setter(e.target.value);
      setModels(null);
      setConnectError(null);
    };

  const handleSaveKey = async () => {
    if (keyBusy || !model.trim()) return;
    // Without a stored key the API key is required; with one it may be omitted
    // (model-only update keeps the stored key).
    if (!storedKey && !apiKey.trim()) return;
    const payload: KeyPayload = {
      provider: resolveProvider(baseUrl),
      base_url: baseUrl.trim(),
      model: model.trim(),
    };
    if (apiKey.trim()) payload.api_key = apiKey.trim();
    const ok = await saveKey(payload);
    if (ok) {
      setApiKey("");
      setJustSaved(true);
      // Refresh the stored-key metadata (masked hint).
      fetchPersonalKey()
        .then(setStoredKey)
        .catch(() => {});
      // Config is reloaded by the store; refresh the usage stats too.
      loadUsage();
    }
  };

  const handleRemoveKey = async () => {
    if (!confirm(t("aiRemoveKeyConfirm"))) return;
    const ok = await removeKey();
    if (ok) {
      setStoredKey(null);
      setBaseUrl(DEFAULT_BASE_URL);
      setModel("");
      setApiKey("");
      setModels(null);
      setConnectError(null);
      setJustSaved(false);
      // Config is reloaded by the store; refresh the usage stats too.
      loadUsage();
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppHeader onHome={onHome} />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-zinc-500">{t("aiSignInNeeded")}</p>
        </main>
      </div>
    );
  }

  // Full-screen spinner only on the first load — refetches (after save/remove/
  // connect) update silently so the form stays in place.
  const isLoading = configStatus === "idle" || (configStatus === "loading" && !aiConfig);
  const isEnterprise = aiConfig?.mode === "enterprise";
  const showForm =
    aiConfig != null &&
    (aiConfig.mode === "personal" ||
      (aiConfig.mode === "none" && aiConfig.allowPersonalKeys));
  const configLoaded = !isLoading && configStatus !== "error";
  // Dropdown options; keep the current model selectable even before a list
  // is fetched (e.g. a stored model before the first refresh).
  const modelChoices = (() => {
    const list = models ?? [];
    if (model && !list.some((m) => m.id === model)) {
      return [{ id: model, name: model }, ...list];
    }
    return list;
  })();

  // Tabbed usage/history section: the Usage tab only exists when usage is
  // applicable (enterprise mode or a personal-key form is shown).
  const showUsageTab = isEnterprise || showForm;
  const effectiveTab = activeTab === "usage" && !showUsageTab ? "chats" : activeTab;
  // Pagination math — clamp the page so a shrinking list never renders blank.
  const usageTotalPages = Math.max(1, Math.ceil((usage?.days.length ?? 0) / PAGE_SIZE));
  const usageSafePage = Math.min(usagePage, usageTotalPages);
  const usageStart = (usageSafePage - 1) * PAGE_SIZE;
  const chatsTotalPages = Math.max(1, Math.ceil(chats.length / PAGE_SIZE));
  const chatsSafePage = Math.min(chatsPage, chatsTotalPages);
  const chatsStart = (chatsSafePage - 1) * PAGE_SIZE;

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader
        onHome={onHome}
        onMySessions={onMySessions}
        onNewSession={onNewSession}
        onAISettings={() => {}}
      />

      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Settings className="h-6 w-6 text-blue-500" />
              <h2 className="text-2xl font-bold">{t("aiSettings")}</h2>
            </div>
            <button
              onClick={onBack}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("aiBack")}
            </button>
          </div>

          {isLoading && (
            <div className="text-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-500 mx-auto" />
            </div>
          )}

          {configStatus === "error" && (
            <div className="text-center py-12">
              <p className="text-red-400">{t("aiConfigError")}</p>
            </div>
          )}

          {/* Enterprise mode — AI comes from the admin key, shown read-only */}
          {configLoaded && isEnterprise && (
            <div className="bg-zinc-900 border border-blue-900/60 rounded-lg p-4 space-y-3">
              <p className="text-sm text-zinc-300">{t("aiEnterpriseOnly")}</p>
              <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                <span className="text-zinc-500">{t("aiProviderLabel")}</span>
                <span className="text-zinc-200 font-mono truncate">
                  {aiConfig?.provider ?? "—"}
                </span>
                <span className="text-zinc-500">{t("aiModel")}</span>
                <span className="text-zinc-200 font-mono truncate">
                  {aiConfig?.model ?? "—"}
                </span>
              </div>
            </div>
          )}

          {/* Mode unavailable — show the backend's reasons */}
          {configLoaded && aiConfig?.mode === "unavailable" && (
            <div className="bg-zinc-900 border border-amber-900/60 rounded-lg p-4 text-sm text-amber-300">
              {aiConfig.reasons.join(" ")}
            </div>
          )}

          {/* No enterprise key and personal keys are disabled */}
          {configLoaded && aiConfig?.mode === "none" && !aiConfig.allowPersonalKeys && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-sm text-zinc-400">
              {t("aiEnterpriseOnly")}
            </div>
          )}

          {/* Personal-key form (personal mode, or none with personal keys allowed) */}
          {configLoaded && showForm && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              <label className="block">
                <span className="flex items-center justify-between text-xs text-zinc-500">
                  {t("aiBaseUrl")}
                  <span
                    className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-medium border",
                      resolveProvider(baseUrl) === "anthropic"
                        ? "bg-orange-950/60 text-orange-300 border-orange-900/60"
                        : "bg-sky-950/60 text-sky-300 border-sky-900/60",
                    )}
                  >
                    {resolveProvider(baseUrl) === "anthropic"
                      ? t("aiProviderAnthropic")
                      : t("aiProviderOpenAICompat")}
                  </span>
                </span>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={handleCredentialsChange(setBaseUrl)}
                  placeholder={DEFAULT_BASE_URL}
                  className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </label>

              <label className="block">
                <span className="text-xs text-zinc-500">{t("aiApiKey")}</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={handleCredentialsChange(setApiKey)}
                  placeholder={storedKey ? t("aiKeyStoredKeep") : ""}
                  className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
                />
                {storedKey && (
                  <span className="mt-1 block text-[11px] text-zinc-500">
                    {t("aiApiKeyStored").replace("{masked}", storedKey.keyMasked)}
                  </span>
                )}
              </label>

              <label className="block">
                <span className="flex items-center justify-between text-xs text-zinc-500">
                  {t("aiModel")}
                  <button
                    type="button"
                    onClick={() => {
                      setManualModel((v) => !v);
                      setConnectError(null);
                    }}
                    className="text-[11px] text-zinc-500 hover:text-zinc-300 underline underline-offset-2 transition-colors"
                  >
                    {manualModel ? t("aiModelFromList") : t("aiModelManual")}
                  </button>
                </span>
                {manualModel ? (
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="anthropic/claude-3.5-haiku"
                    className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
                  />
                ) : (
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    disabled={modelChoices.length === 0}
                    className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <option value="">{t("aiModelPlaceholder")}</option>
                    {modelChoices.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id}
                      </option>
                    ))}
                  </select>
                )}
              </label>

              {/* Connect — resolves the provider and lists its models.
                  Refresh — lists models via the stored key (no re-entry). */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => void handleConnect()}
                  disabled={!apiKey.trim() || connecting}
                  className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {connecting ? t("aiConnecting") : t("aiConnect")}
                </button>
                {storedKey && (
                  <button
                    onClick={() => void handleRefreshModels()}
                    disabled={refreshingModels}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <RefreshCw className={cn("h-3 w-3", refreshingModels && "animate-spin")} />
                    {t("aiRefreshModels")}
                  </button>
                )}
                {connectError && (
                  <span className="flex items-center gap-1 text-xs text-rose-400">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    {connectError}
                  </span>
                )}
                {models && !connectError && (
                  <span className="flex items-center gap-1 text-xs text-emerald-400">
                    <Check className="h-3 w-3 shrink-0" />
                    {t("aiModelsFound").replace("{n}", String(models.length))}
                  </span>
                )}
              </div>

              {/* Save / Remove */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => void handleSaveKey()}
                  disabled={(!apiKey.trim() && !storedKey) || !model.trim() || keyBusy}
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

              {justSaved && onBackToChat && (
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 text-xs text-emerald-400">
                    <Check className="h-3 w-3 shrink-0" />
                    {t("aiKeySaved")}
                  </span>
                  <button
                    onClick={onBackToChat}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-all active:scale-[0.97]"
                  >
                    {t("aiBackToChat")}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Usage & chat history — tabbed, both lists paginated 20/page */}
          {configLoaded && (
            <div className="mt-4 bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              {/* Tab bar + (Usage tab) export/delete actions */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex rounded-lg bg-zinc-800 p-0.5">
                  {showUsageTab && (
                    <button
                      onClick={() => handleTabChange("usage")}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all active:scale-[0.97]",
                        effectiveTab === "usage"
                          ? "bg-blue-600 text-white"
                          : "text-zinc-400 hover:text-zinc-200",
                      )}
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      {t("aiUsage")}
                    </button>
                  )}
                  <button
                    onClick={() => handleTabChange("chats")}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all active:scale-[0.97]",
                      effectiveTab === "chats"
                        ? "bg-blue-600 text-white"
                        : "text-zinc-400 hover:text-zinc-200",
                    )}
                  >
                    <History className="h-3.5 w-3.5" />
                    {t("aiChatHistory")}
                  </button>
                </div>
                {effectiveTab === "usage" &&
                  usageState === "ok" &&
                  usage &&
                  usage.totals.messages > 0 && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleExportUsage}
                        disabled={usageAction !== null}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <Download className="h-3 w-3" />
                        {t("aiUsageExport")}
                      </button>
                      <button
                        onClick={() => void handleDeleteUsage()}
                        disabled={usageAction !== null}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-rose-900/60 hover:text-rose-300 text-zinc-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <Trash2 className="h-3 w-3" />
                        {t("aiUsageDelete")}
                      </button>
                    </div>
                  )}
              </div>

              {/* Usage tab — totals grid + paginated daily history */}
              {effectiveTab === "usage" && showUsageTab && (
                <>
                  {usageState === "loading" && (
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
                  )}

                  {usageState === "ok" && usage && (
                    <>
                      {/* Totals row */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div>
                          <p className="text-[11px] text-zinc-500">{t("aiUsageMessages")}</p>
                          <p className="text-sm text-zinc-200 font-mono">
                            {usage.totals.messages.toLocaleString()}
                          </p>
                        </div>
                        <div>
                          <p className="text-[11px] text-zinc-500">{t("aiUsageTokensIn")}</p>
                          <p className="text-sm text-zinc-200 font-mono">
                            {usage.totals.prompt_tokens.toLocaleString()}
                          </p>
                        </div>
                        <div>
                          <p className="text-[11px] text-zinc-500">{t("aiUsageTokensOut")}</p>
                          <p className="text-sm text-zinc-200 font-mono">
                            {usage.totals.completion_tokens.toLocaleString()}
                          </p>
                        </div>
                        {usage.totals.cost_usd != null && (
                          <div>
                            <p className="text-[11px] text-zinc-500">{t("aiUsageCost")}</p>
                            <p className="text-sm text-zinc-200 font-mono">
                              ≈${usage.totals.cost_usd.toFixed(4)}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Daily history — newest first, 20 rows per page */}
                      {usage.days.length === 0 ? (
                        <p className="text-xs text-zinc-500">{t("aiUsageEmpty")}</p>
                      ) : (
                        <>
                          <div className="max-h-56 overflow-y-auto divide-y divide-zinc-800 rounded-lg border border-zinc-800">
                            {usage.days
                              .slice(usageStart, usageStart + PAGE_SIZE)
                              .map((day) => (
                                <div
                                  key={day.date}
                                  className="px-3 py-2 text-xs text-zinc-400 font-mono"
                                >
                                  {day.date}
                                  {" · "}
                                  {(day.messages === 1
                                    ? t("aiUsageMsgOne")
                                    : t("aiUsageMsgCount")
                                  ).replace("{n}", day.messages.toLocaleString())}
                                  {" · "}
                                  {`↑${day.prompt_tokens.toLocaleString()} ↓${day.completion_tokens.toLocaleString()}`}
                                  {" "}
                                  {t("aiTokens")}
                                  {day.cost_usd != null && ` · ≈$${day.cost_usd.toFixed(4)}`}
                                </div>
                              ))}
                          </div>
                          <PaginationFooter
                            page={usageSafePage}
                            totalPages={usageTotalPages}
                            onPrev={() => setUsagePage((p) => Math.max(1, p - 1))}
                            onNext={() =>
                              setUsagePage((p) => Math.min(usageTotalPages, p + 1))
                            }
                          />
                        </>
                      )}
                    </>
                  )}
                </>
              )}

              {/* Chat history tab — paginated saved chats */}
              {effectiveTab === "chats" && (
                <>
                  {chatsState === "loading" && (
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
                  )}

                  {chatsState === "ok" && chats.length === 0 && (
                    <p className="text-xs text-zinc-500">{t("aiNoChats")}</p>
                  )}

                  {chatsState === "ok" && chats.length > 0 && (
                    <>
                      <div className="max-h-56 overflow-y-auto divide-y divide-zinc-800 rounded-lg border border-zinc-800">
                        {chats.slice(chatsStart, chatsStart + PAGE_SIZE).map((chat) => (
                          <div key={chat.id} className="px-3 py-2 flex items-center gap-2">
                            <div className="flex-1 min-w-0">
                              <span className="block truncate text-xs text-zinc-200">
                                {chat.title ?? t("aiChatFallback")}
                              </span>
                              <span className="block truncate text-[10px] text-zinc-500">
                                {formatDate(chat.created_at)}
                                {chat.session_filename ? ` · ${chat.session_filename}` : ""}
                                {" · "}
                                {t("aiUsageMsgCount").replace("{n}", String(chat.message_count))}
                                {" · "}
                                {chat.tokens.toLocaleString()} {t("aiTokens")}
                              </span>
                            </div>
                            <button
                              onClick={() => handleExportChat(chat.id)}
                              disabled={chatAction !== null}
                              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                            >
                              <Download className="h-3 w-3" />
                              {t("aiExport")}
                            </button>
                            <button
                              onClick={() => void handleDeleteChat(chat.id)}
                              disabled={chatAction !== null}
                              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-zinc-800 hover:bg-rose-900/60 hover:text-rose-300 text-zinc-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                            >
                              <Trash2 className="h-3 w-3" />
                              {t("aiDelete")}
                            </button>
                          </div>
                        ))}
                      </div>
                      <PaginationFooter
                        page={chatsSafePage}
                        totalPages={chatsTotalPages}
                        onPrev={() => setChatsPage((p) => Math.max(1, p - 1))}
                        onNext={() => setChatsPage((p) => Math.min(chatsTotalPages, p + 1))}
                      />
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
