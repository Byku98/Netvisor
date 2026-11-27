import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/i18n";

/** Backend cap on the session filename (PATCH /sessions/{id}). */
const MAX_NAME_LENGTH = 200;

interface SessionRenameInputProps {
  /** Current session name — pre-fills the input (selected on open). */
  current: string;
  /** Persist the new name. Throws with a user-facing message on failure —
   *  the caller owns any optimistic update and its revert. */
  onCommit: (newName: string) => Promise<void>;
  /** Close the editor (after a successful commit or Esc). */
  onDone: () => void;
  /** Classes for the text input. */
  className?: string;
}

/**
 * Inline rename editor for a session name. Commits on Enter or blur, cancels
 * on Esc. Validates locally with the same rules as the backend (trimmed,
 * non-empty, <= 200 chars) to avoid pointless round-trips; backend errors
 * are surfaced verbatim below the input.
 */
export function SessionRenameInput({
  current,
  onCommit,
  onDone,
  className,
}: SessionRenameInputProps) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const cancel = () => {
    cancelledRef.current = true;
    onDone();
  };

  const commit = async () => {
    if (saving || cancelledRef.current) return;
    const name = draft.trim();
    if (name.length === 0) {
      setError(t("renameEmptyError"));
      return;
    }
    if (name.length > MAX_NAME_LENGTH) {
      setError(t("renameTooLongError"));
      return;
    }
    if (name === current) {
      onDone();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCommit(name);
      cancelledRef.current = true;
      onDone();
    } catch (err) {
      setError((err as Error).message || t("renameFailed"));
      setSaving(false);
    }
  };

  return (
    <span className="block min-w-0">
      <input
        ref={inputRef}
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void commit()}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        className={className}
        aria-label={t("renameSession")}
      />
      {error && (
        <span className="mt-0.5 block text-xs text-rose-400">{error}</span>
      )}
    </span>
  );
}
