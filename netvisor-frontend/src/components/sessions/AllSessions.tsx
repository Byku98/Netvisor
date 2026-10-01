import { useState, useEffect } from "react";
import { X, Loader2, Trash2, RefreshCw, Clock } from "lucide-react";
import type { SessionListItem } from "@/api/sessions.api";
import { fetchSessions, deleteSession, fetchSessionTopology } from "@/api/sessions.api";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Format timestamp to readable string. */
function formatTime(timestamp: string): string {
  const dt = new Date(timestamp);
  return dt.toLocaleString();
}

interface AllSessionsProps {
  /** Go back to the previous screen. */
  onBack: () => void;
}

/**
 * All Sessions page — shows all uploaded sessions (both logged-in and anonymous).
 * Accessible to everyone, not just logged-in users.
 */
export function AllSessions({ onBack }: AllSessionsProps) {
  const queryClient = useQueryClient();
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Load all sessions on mount
  const loadSessions = () => {
    setLoading(true);
    setError(null);
    fetchSessions()
      .then((data) => setSessions(data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load sessions"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleLoadSession = async (sessionId: string) => {
    try {
      const topology = await fetchSessionTopology(sessionId);
      queryClient.setQueryData(["topology", sessionId], topology);
      onBack();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session");
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Delete this session and all its data?")) return;

    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      queryClient.removeQueries({ queryKey: ["topology", sessionId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete session");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-900">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold text-zinc-200">All Sessions</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadSessions}
              disabled={loading}
              className="p-2 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-200 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </button>
            <button
              onClick={onBack}
              className="p-2 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-200 rounded-lg transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
          </div>
        ) : error ? (
          <div className="max-w-md mx-auto mt-8 p-4 bg-red-950/20 border border-red-900 rounded-lg text-red-400">
            {error}
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-12">
            <div className="inline-block p-4 bg-zinc-800 rounded-full mb-4">
              <Clock className="h-8 w-8 text-zinc-500 mx-auto" />
            </div>
            <h3 className="text-lg font-medium text-zinc-300">No sessions yet</h3>
            <p className="text-zinc-500 mt-1">Upload a PCAP file to get started</p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-4">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="group relative p-4 bg-zinc-800 border border-zinc-700 rounded-lg hover:border-zinc-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="p-1.5 bg-zinc-700 rounded text-zinc-400">
                        <Clock className="h-4 w-4" />
                      </div>
                      <h3 className="text-sm font-medium text-zinc-200 truncate">
                        {s.filename}
                      </h3>
                    </div>
                    <p className="text-xs text-zinc-500">{formatTime(s.createdAt)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleLoadSession(s.id)}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
                    >
                      Load
                    </button>
                    <button
                      onClick={() => handleDeleteSession(s.id)}
                      disabled={deleting === s.id}
                      className="px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 hover:text-zinc-200 text-xs rounded-lg transition-colors disabled:opacity-50"
                    >
                      <Trash2 className={cn("h-3.5 w-3.5", deleting === s.id && "animate-spin")} />
                    </button>
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-4 gap-3 mt-3 text-xs">
                  <div>
                    <p className="text-zinc-500">Packets</p>
                    <p className="text-zinc-200 font-mono">{s.totalPackets.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Bytes</p>
                    <p className="text-zinc-200 font-mono">{formatBytes(s.totalBytes)}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Hosts</p>
                    <p className="text-zinc-200 font-mono">{s.uniqueHosts}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Duration</p>
                    <p className="text-zinc-200 font-mono">{s.durationSec.toFixed(1)}s</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}