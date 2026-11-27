import { useCallback, useEffect, useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X } from "lucide-react";
import { useI18n, type TKey } from "@/i18n";
import { useAuthStore } from "@/stores/auth.store";
import { useConfigStore, formatMb } from "@/stores/config.store";
import { cn } from "@/lib/utils";
import { hasPcapExtension, hasPcapMagic, sha256Hex } from "@/lib/pcap-files";
import {
  lookupOwnedChecksums,
  type PcapUploadError,
  type UploadFile,
} from "@/api/pcap.api";

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Why a staged row is invalid — a local add-time check or the server's
 *  upload-error detail (row marked red after a failed upload). */
type StagedError =
  | { kind: "i18n"; key: TKey; sizeBytes?: number }
  | { kind: "server"; message: string };

/** One file staged for upload. */
interface StagedFile {
  id: string;
  file: File;
  /** Current (possibly renamed) name — sent as the multipart filename. */
  name: string;
  size: number;
  /** Hex SHA-256; null while hashing or when crypto.subtle is unavailable. */
  checksum: string | null;
  error: StagedError | null;
}

/** Aggregated "already on the platform" notice for the latest add-batch —
 *  replaces (never appends to) the previous notice. */
interface DuplicateNotice {
  /** How many staged files were auto-removed as already owned. */
  count: number;
  /** Distinct owning sessions in first-seen order (open-session links). */
  sessions: Array<{ sessionId: string; filename: string }>;
}

/** Session links shown in one notice before collapsing into "+N more". */
const MAX_SESSION_LINKS = 3;

let nextId = 1;

function makeStaged(file: File, error: StagedError | null): StagedFile {
  return {
    id: `staged-${nextId++}`,
    file,
    name: file.name,
    size: file.size,
    checksum: null,
    error,
  };
}

/** Strip the extension — auto-label joins basenames. */
function basename(name: string): string {
  return name.replace(/\.[^.]+$/, "");
}

/** Upload-button plural key (Polish needs 1 / 2-4 / 5+ forms). */
function uploadButtonKey(n: number): TKey {
  if (n === 1) return "uploadBtnOne";
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
    return "uploadBtnFew";
  }
  return "uploadBtnMany";
}

/** Duplicate-notice plural key (same 1 / 2-4 / 5+ pattern). */
function duplicateNoticeKey(n: number): TKey {
  if (n === 1) return "alreadyOnPlatformOne";
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
    return "alreadyOnPlatformFew";
  }
  return "alreadyOnPlatformMany";
}

/**
 * Multi-file upload panel for the main screen.
 *
 * Files are validated locally as they are added (extension, magic bytes,
 * per-file size, running bundle total — no network), hashed with SHA-256 and
 * checked against the backend checksum index in one batch request per
 * add-action; files already on the platform (own sessions) are auto-removed
 * with an "open session" notice. The user curates the list (remove / rename
 * rows), optionally names the session (logged-in only), then uploads
 * everything as one multipart request. Failures keep the list intact and
 * mark the offending row red.
 */
export function UploadPanel({
  onUpload,
  isPending,
  uploadError,
  onOpenSession,
}: {
  /** Start the upload — receives the valid staged files + optional label. */
  onUpload: (files: UploadFile[], label?: string) => void;
  isPending: boolean;
  /** Error from the last upload attempt (null while pending / before first). */
  uploadError: PcapUploadError | null;
  /** Open one of my sessions (the "Open session" action on duplicate notices). */
  onOpenSession: (sessionId: string) => void;
}) {
  const { t } = useI18n();
  const user = useAuthStore((s) => s.user);
  const maxUploadBytes = useConfigStore((s) => s.maxUploadBytes);
  const maxBundleBytes = useConfigStore((s) => s.maxBundleBytes);
  const isLoggedIn = user != null;

  const [staged, setStaged] = useState<StagedFile[]>([]);
  const [duplicateNotice, setDuplicateNotice] = useState<DuplicateNotice | null>(
    null,
  );
  const [bundleMessage, setBundleMessage] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("");
  const [namePristine, setNamePristine] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [errorDismissed, setErrorDismissed] = useState(false);

  // ── Add files: local validation, then hash + one batch checksum lookup ──
  const addFiles = useCallback(
    async (incoming: File[]) => {
      if (incoming.length === 0) return;
      setBundleMessage(null);
      // New add-batch: the previous duplicate notice never carries over.
      setDuplicateNotice(null);

      // Bundle budget = sizes of currently valid staged rows (invalid rows
      // never reach the server).
      let runningTotal = staged.reduce(
        (sum, row) => sum + (row.error ? 0 : row.size),
        0,
      );
      const rows: StagedFile[] = [];
      let refusedName: string | null = null;

      for (const file of incoming) {
        if (!hasPcapExtension(file.name)) {
          rows.push(makeStaged(file, { kind: "i18n", key: "fileNotPcap" }));
          continue;
        }
        if (file.size > maxUploadBytes) {
          rows.push(
            makeStaged(file, {
              kind: "i18n",
              key: "fileExceedsLimit",
              sizeBytes: maxUploadBytes,
            }),
          );
          continue;
        }
        if (runningTotal + file.size > maxBundleBytes) {
          // Refused at add time — never staged; the other files stay.
          refusedName = refusedName ?? file.name;
          continue;
        }
        runningTotal += file.size;
        rows.push(makeStaged(file, null));
      }

      if (refusedName) {
        setBundleMessage(
          `${refusedName}: ${t("bundleExceeded").replace("{size}", formatMb(maxBundleBytes))}`,
        );
      }
      if (rows.length === 0) return;
      setStaged((prev) => [...prev, ...rows]);

      // Magic bytes + SHA-256 per row (async), then ONE checksum lookup for
      // the whole add-action.
      const validRows = rows.filter((row) => row.error == null);
      const checksums = new Map<string, string>();
      await Promise.all(
        validRows.map(async (row) => {
          if (!(await hasPcapMagic(row.file))) {
            setStaged((prev) =>
              prev.map((r) =>
                r.id === row.id
                  ? { ...r, error: { kind: "i18n", key: "fileNotPcap" } }
                  : r,
              ),
            );
            return;
          }
          const hex = await sha256Hex(row.file);
          if (hex == null) return;
          checksums.set(row.id, hex);
          setStaged((prev) =>
            prev.map((r) => (r.id === row.id ? { ...r, checksum: hex } : r)),
          );
        }),
      );
      if (checksums.size === 0) return;

      const ids = [...checksums.keys()];
      const hexList = ids.map((id) => checksums.get(id) ?? "");
      const results = await lookupOwnedChecksums(hexList);
      if (results == null) return; // older backend / lookup failed — keep files

      const rowById = new Map(validRows.map((row) => [row.id, row]));
      const ownedRowIds: string[] = [];
      const ownedCount = results.reduce((count, item, index) => {
        if (!item?.owned) return count;
        const row = rowById.get(ids[index]);
        if (row) ownedRowIds.push(row.id);
        return count + 1;
      }, 0);
      // Owned results grouped by owning session (first-seen order); the
      // session label comes from the lookup response's filename.
      const ownedSessions = new Map<string, string>();
      results.forEach((item, index) => {
        if (!item?.owned || !item.sessionId) return;
        if (ownedSessions.has(item.sessionId)) return;
        const row = rowById.get(ids[index]);
        ownedSessions.set(
          item.sessionId,
          item.filename || row?.name || item.sessionId,
        );
      });
      if (ownedRowIds.length > 0) {
        setStaged((prev) => prev.filter((row) => !ownedRowIds.includes(row.id)));
      }
      // This response replaces the notice state entirely (null when nothing
      // was owned — the notice never accumulates across add-batches).
      setDuplicateNotice(
        ownedCount === 0
          ? null
          : {
              count: ownedCount,
              sessions: [...ownedSessions].map(([sessionId, filename]) => ({
                sessionId,
                filename,
              })),
            },
      );
    },
    [staged, maxUploadBytes, maxBundleBytes, t],
  );

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      void addFiles(acceptedFiles);
    },
    [addFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: isPending,
  });

  // ── Session name: auto-label from the current list while pristine ──
  const autoLabelText = useMemo(() => {
    const names = staged.map((row) => row.name);
    if (names.length === 0) return "";
    if (names.length === 1) return names[0];
    const head = `${basename(names[0])} + ${basename(names[1])}`;
    return names.length === 2
      ? head
      : `${head} ${t("plusNMore").replace("{n}", String(names.length - 2))}`;
  }, [staged, t]);

  useEffect(() => {
    if (staged.length === 0) {
      // Fresh curation round — re-enable auto-labeling.
      setNamePristine(true);
      setSessionName("");
    } else if (namePristine) {
      setSessionName(autoLabelText);
    }
  }, [staged.length, namePristine, autoLabelText]);

  // ── Upload failure: keep the list, surface the message, mark the named
  //    file's row red (best-effort basename match in the detail string) ──
  useEffect(() => {
    setErrorDismissed(false);
    if (!uploadError) return;
    const detail = uploadError.message;
    setStaged((prev) =>
      prev.map((row) => {
        if (row.error) return row; // keep the existing reason
        const base = basename(row.name);
        if (
          detail.includes(row.name) ||
          (base.length > 0 && detail.includes(base))
        ) {
          return { ...row, error: { kind: "server", message: detail } };
        }
        return row;
      }),
    );
  }, [uploadError]);

  const removeFile = useCallback((id: string) => {
    setStaged((prev) => prev.filter((row) => row.id !== id));
    setRenamingId((current) => (current === id ? null : current));
  }, []);

  const startRename = (row: StagedFile) => {
    setRenamingId(row.id);
    setRenameValue(row.name);
  };

  const commitRename = useCallback(() => {
    if (renamingId == null) return;
    const trimmed = renameValue.trim();
    if (trimmed.length > 0) {
      setStaged((prev) =>
        prev.map((row) =>
          row.id === renamingId ? { ...row, name: trimmed } : row,
        ),
      );
    }
    setRenamingId(null);
  }, [renamingId, renameValue]);

  const validRows = staged.filter((row) => row.error == null);
  const anyInvalid = staged.some((row) => row.error != null);
  const validBytes = validRows.reduce((sum, row) => sum + row.size, 0);

  const handleUpload = () => {
    if (validRows.length === 0 || anyInvalid || isPending) return;
    const label = isLoggedIn ? sessionName.trim() || undefined : undefined;
    onUpload(
      validRows.map((row) => ({ file: row.file, name: row.name })),
      label,
    );
  };

  const uploadLabel =
    validRows.length === 1
      ? t("uploadBtnOne").replace("{size}", formatMb(validBytes))
      : t(uploadButtonKey(validRows.length))
          .replace("{n}", String(validRows.length))
          .replace("{size}", formatMb(validBytes));

  const errorText = (error: StagedError): string => {
    if (error.kind === "server") return error.message;
    const text = t(error.key);
    return error.sizeBytes != null
      ? text.replace("{size}", formatMb(error.sizeBytes))
      : text;
  };

  return (
    <div className="space-y-3">
      {/* Dropzone — multi-select + multi-drag; validation happens on add */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl text-center cursor-pointer transition-colors",
          // Barely-perceptible ambient depth — pairs with the starfield without
          // reading as a glow; kept faint so it works on both themes.
          "shadow-[0_0_48px_-24px_rgba(59,130,246,0.15)]",
          staged.length > 0 ? "p-6" : "p-12",
          isDragActive
            ? "border-blue-500 bg-blue-500/10"
            : "border-zinc-700 hover:border-zinc-500",
          isPending && "opacity-50 cursor-not-allowed",
        )}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-blue-400 text-lg">{t("dropHereActive")}</p>
        ) : (
          <div>
            <Upload className="h-12 w-12 mx-auto mb-3 text-zinc-500" />
            <p className="text-zinc-300 text-lg">{t("dropzoneTitle")}</p>
            <p className="text-sm text-zinc-500 mt-1">
              {t("dropzoneHint").replace("{size}", formatMb(maxBundleBytes))}
            </p>
          </div>
        )}
      </div>

      {/* Upload failure — the list survives; the offending row is red below */}
      {uploadError && !errorDismissed && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-700/60 bg-rose-950/60 px-3 py-2 text-sm text-rose-300">
          <span className="flex-1 min-w-0 break-words">
            {uploadError.message || t("uploadFailed")}
          </span>
          <button
            type="button"
            onClick={() => setErrorDismissed(true)}
            aria-label={t("dismiss")}
            className="shrink-0 p-1 text-rose-400 hover:text-rose-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Duplicates auto-removed — one aggregated notice per add-batch */}
      {duplicateNotice && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-blue-700/50 bg-blue-950/40 px-3 py-2 text-sm text-blue-300">
          <span className="flex-1 min-w-0 break-words">
            {t(duplicateNoticeKey(duplicateNotice.count)).replace(
              "{n}",
              String(duplicateNotice.count),
            )}
          </span>
          {duplicateNotice.sessions.length === 1 ? (
            <button
              type="button"
              onClick={() => onOpenSession(duplicateNotice.sessions[0].sessionId)}
              className="shrink-0 rounded bg-blue-600 hover:bg-blue-500 px-2 py-1 text-xs font-medium text-white transition-colors"
            >
              {t("openSession")}
            </button>
          ) : (
            <span className="flex shrink-0 flex-wrap items-center gap-1">
              {duplicateNotice.sessions.slice(0, MAX_SESSION_LINKS).map((session) => (
                <button
                  key={session.sessionId}
                  type="button"
                  onClick={() => onOpenSession(session.sessionId)}
                  title={t("openSession")}
                  aria-label={`${t("openSession")}: ${session.filename}`}
                  className="max-w-[12rem] truncate rounded bg-blue-600 hover:bg-blue-500 px-2 py-1 text-xs font-medium text-white transition-colors"
                >
                  {session.filename}
                </button>
              ))}
              {duplicateNotice.sessions.length > MAX_SESSION_LINKS && (
                <span className="text-xs">
                  {t("plusNMore").replace(
                    "{n}",
                    String(duplicateNotice.sessions.length - MAX_SESSION_LINKS),
                  )}
                </span>
              )}
            </span>
          )}
          <button
            type="button"
            onClick={() => setDuplicateNotice(null)}
            aria-label={t("dismiss")}
            className="shrink-0 p-1 text-blue-400 hover:text-blue-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Bundle-limit refusal with an empty list (first file alone exceeded
          the bundle) — right under the dropzone, nothing else to anchor to */}
      {staged.length === 0 && bundleMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-300">
          <span className="flex-1 min-w-0 break-words">{bundleMessage}</span>
          <button
            type="button"
            onClick={() => setBundleMessage(null)}
            aria-label={t("dismiss")}
            className="shrink-0 p-1 text-amber-400 hover:text-amber-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Bundle-limit refusal (the file was NOT added) — rendered below the
          list, next to the running bundle-usage line it refers to */}
      {staged.length > 0 && bundleMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-300">
          <span className="flex-1 min-w-0 break-words">{bundleMessage}</span>
          <button
            type="button"
            onClick={() => setBundleMessage(null)}
            aria-label={t("dismiss")}
            className="shrink-0 p-1 text-amber-400 hover:text-amber-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Staged file list — curate before uploading */}
      {staged.length > 0 && (
        <ul className="space-y-2">
          {staged.map((row) => {
            const invalid = row.error != null;
            return (
              <li
                key={row.id}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors",
                  invalid
                    ? "border-rose-700/60 bg-rose-950/40"
                    : "border-zinc-700/50 bg-zinc-800/50",
                )}
              >
                <div className="flex-1 min-w-0">
                  {renamingId === row.id ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          commitRename();
                        } else if (e.key === "Escape") {
                          setRenamingId(null);
                        }
                      }}
                      className="w-full rounded border border-blue-500/60 bg-zinc-900 px-2 py-0.5 text-sm text-zinc-100 outline-none focus:border-blue-400"
                    />
                  ) : isLoggedIn ? (
                    <button
                      type="button"
                      onClick={() => startRename(row)}
                      title={t("renameFile")}
                      className={cn(
                        "block max-w-full truncate text-left hover:text-blue-300 hover:underline",
                        invalid ? "text-rose-300" : "text-zinc-200",
                      )}
                    >
                      {row.name}
                    </button>
                  ) : (
                    <span
                      className={cn(
                        "block max-w-full truncate",
                        invalid ? "text-rose-300" : "text-zinc-200",
                      )}
                    >
                      {row.name}
                    </span>
                  )}
                  {row.error && (
                    <p className="mt-0.5 text-xs text-rose-400">
                      {errorText(row.error)}
                    </p>
                  )}
                </div>
                <span className="shrink-0 text-xs text-zinc-500">
                  {formatBytes(row.size)}
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(row.id)}
                  title={t("removeFile")}
                  aria-label={t("removeFile")}
                  className="shrink-0 p-1 text-zinc-500 hover:text-red-400 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Session name — logged-in users only; auto-label while pristine */}
      {isLoggedIn && staged.length > 0 && (
        <div className="space-y-1">
          <label htmlFor="session-name-input" className="text-xs text-zinc-500">
            {t("sessionNameLabel")}
          </label>
          <input
            id="session-name-input"
            value={sessionName}
            onChange={(e) => {
              setSessionName(e.target.value);
              setNamePristine(false);
            }}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-blue-500"
          />
        </div>
      )}

      {/* Bundle usage — the limit lives HERE, below the file list, where the
          running total is readable against it */}
      {staged.length > 0 && (
        <p className="text-xs text-zinc-500">
          {t("bundleUsage")
            .replace("{used}", formatMb(validBytes))
            .replace("{limit}", formatMb(maxBundleBytes))}
        </p>
      )}

      {/* Upload */}
      {staged.length > 0 && (
        <button
          type="button"
          onClick={handleUpload}
          disabled={isPending || anyInvalid}
          className={cn(
            "w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors",
            isPending || anyInvalid
              ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white",
          )}
        >
          {isPending ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-transparent" />
              <span>{t("parsing")}</span>
            </>
          ) : (
            <span>{uploadLabel}</span>
          )}
        </button>
      )}
    </div>
  );
}
