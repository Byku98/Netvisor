/**
 * AI Settings page — full-page personal-key management.
 *
 * Follows the MySessions page pattern: AppHeader, back button, signed-out
 * state. Hosts the settings form that used to live inside AIAssistantPanel:
 * base URL + key → Connect → model dropdown → Save / Remove. With a stored
 * key the model list can be refreshed without re-entering the key, and a
 * usage card shows the last 30 days of AI usage.
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
  listProviderModels,
  listStoredModels,
  type AiUsageResponse,
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logger } from "@/utils/logger";

/** Default prefill for the Base URL input (OpenRouter). */
const DEFAULT_BASE_URL = "https://openrouter.ai/api/v1";

/** Resolve the backend provider from the Base URL: Anthropic API vs anything OpenAI-compatible. */
function resolveProvider(baseUrl: string): "anthropic" | "openai" {
  return baseUrl.includes("api.anthropic.com") ? "anthropic" : "openai";
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

  /** Fetch (or re-fetch) the usage summary. */
  const loadUsage = useCallback(() => {
    setUsageState("loading");
    fetchAiUsage()
      .then((data) => {
        setUsage(data);
        setUsageState("ok");
      })
      .catch(() => setUsageState("error"));
  }, []);

  // Load the config and prefill the form from the stored key.
  useEffect(() => {
    if (!user) return;
    void loadConfig();
    loadUsage();
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
  }, [user, loadConfig, loadUsage]);

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

          {/* Usage & history — last 30 days (personal and enterprise modes) */}
          {configLoaded && (isEnterprise || showForm) && (
            <div className="mt-4 bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-blue-500" />
                <h3 className="text-sm font-semibold text-zinc-200">{t("aiUsage")}</h3>
                {usageState === "ok" && usage && usage.totals.messages > 0 && (
                  <div className="flex-1 flex items-center justify-end gap-2">
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

                  {/* Daily history — newest first */}
                  {usage.days.length === 0 ? (
                    <p className="text-xs text-zinc-500">{t("aiUsageEmpty")}</p>
                  ) : (
                    <div className="max-h-56 overflow-y-auto divide-y divide-zinc-800 rounded-lg border border-zinc-800">
                      {usage.days.map((day) => (
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
