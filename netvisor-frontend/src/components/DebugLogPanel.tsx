import { useState } from "react";
import { useLogStore, type LogLevel } from "@/stores/log.store";
import { useUiStore } from "@/stores/ui.store";
import { Terminal, ChevronUp, ChevronDown, Trash2 } from "lucide-react";

const LEVEL_COLORS: Record<LogLevel, string> = {
  debug: "text-zinc-500",
  info: "text-blue-400",
  warn: "text-yellow-400",
  error: "text-red-400",
};

const LEVEL_BG: Record<LogLevel, string> = {
  debug: "",
  info: "",
  warn: "bg-yellow-500/5",
  error: "bg-red-500/10",
};

export function DebugLogPanel() {
  // Hidden by default — opt in via the Debug checkbox in the header,
  // `?debug` in the URL, or localStorage netvisor-debug=1
  const enabled = useUiStore((s) => s.debugEnabled);
  const [expanded, setExpanded] = useState(false);
  const entries = useLogStore((s) => s.entries);
  const clear = useLogStore((s) => s.clear);

  const errorCount = entries.filter((e) => e.level === "error").length;

  if (!enabled) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[9999] font-mono text-xs">
      {/* Toggle bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-1.5 bg-zinc-950 border-t border-zinc-700 hover:bg-zinc-900 transition-colors"
      >
        <Terminal className="h-3.5 w-3.5 text-zinc-400" />
        <span className="text-zinc-400">Debug Log</span>
        <span className="text-zinc-600">({entries.length})</span>
        {errorCount > 0 && (
          <span className="ml-1 px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded text-[10px]">
            {errorCount} err
          </span>
        )}
        <div className="flex-1" />
        {expanded && (
          <span
            onClick={(e) => {
              e.stopPropagation();
              clear();
            }}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Clear logs"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </span>
        )}
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 text-zinc-500" />
        )}
      </button>

      {/* Log panel */}
      {expanded && (
        <div className="h-64 overflow-y-auto bg-zinc-950 border-t border-zinc-800 px-2 py-1">
          {entries.length === 0 && (
            <p className="text-zinc-600 text-center py-4">No logs yet</p>
          )}
          {entries.map((entry) => (
            <div
              key={entry.id}
              className={`flex items-start gap-2 py-0.5 px-1 rounded ${LEVEL_BG[entry.level]}`}
            >
              <span className="text-zinc-600 shrink-0 w-[72px]">
                {entry.timestamp}
              </span>
              <span
                className={`shrink-0 w-[28px] font-bold ${LEVEL_COLORS[entry.level]}`}
              >
                {entry.level.toUpperCase().slice(0, 3)}
              </span>
              <span className="text-zinc-500 shrink-0 w-[80px] truncate">
                {entry.domain}
              </span>
              <span className="text-zinc-300 break-all">{entry.message}</span>
              {entry.data !== undefined && (
                <span className="text-zinc-600 break-all">
                  {typeof entry.data === "string"
                    ? entry.data
                    : JSON.stringify(entry.data)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
