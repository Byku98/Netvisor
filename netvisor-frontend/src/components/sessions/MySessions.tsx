import { useEffect, useState } from "react";
import { fetchMySessions } from "@/api/auth.api";
import { deleteSession } from "@/api/sessions.api";
import { AppHeader } from "@/components/auth/AppHeader";
import { useAuthStore } from "@/stores/auth.store";
import { FolderOpen, FileText, Trash2, Upload } from "lucide-react";

interface SessionItem {
  id: string;
  filename: string;
  totalPackets: number;
  totalBytes: number;
  uniqueHosts: number;
  durationSec: number;
  createdAt: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface MySessionsProps {
  onHome: () => void;
  onLoadSession: (sessionId: string) => void;
  onNewSession: () => void;
}

export function MySessions({ onHome, onLoadSession, onNewSession }: MySessionsProps) {
  const user = useAuthStore((s) => s.user);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    fetchMySessions()
      .then((data) => setSessions(data as SessionItem[]))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [user]);

  const handleDelete = async (sessionId: string) => {
    if (!confirm("Delete this session and all its data?")) return;
    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
    } finally {
      setDeleting(null);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppHeader onHome={onHome} />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-zinc-500">Please sign in to view your sessions.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader onHome={onHome} onMySessions={() => {}} onNewSession={onNewSession} />

      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <FolderOpen className="h-6 w-6 text-blue-500" />
              <h2 className="text-2xl font-bold">My Sessions</h2>
              <span className="text-sm text-zinc-500 ml-2">
                {sessions.length} session{sessions.length !== 1 ? "s" : ""}
              </span>
            </div>
            <button
              onClick={onNewSession}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
            >
              <Upload className="h-4 w-4" />
              New Session
            </button>
          </div>

          {loading && (
            <div className="text-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent mx-auto" />
              <p className="text-zinc-500 mt-3">Loading sessions...</p>
            </div>
          )}

          {error && (
            <div className="text-center py-12">
              <p className="text-red-400">{error}</p>
            </div>
          )}

          {!loading && !error && sessions.length === 0 && (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-500">No sessions yet</p>
              <p className="text-sm text-zinc-600 mt-1">
                Upload a PCAP file to create your first session
              </p>
              <button
                onClick={onNewSession}
                className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
              >
                Upload PCAP
              </button>
            </div>
          )}

          {!loading && !error && sessions.length > 0 && (
            <div className="space-y-3">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="group bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <FileText className="h-5 w-5 text-zinc-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-200 truncate">
                          {s.filename}
                        </p>
                        <p className="text-xs text-zinc-500 mt-0.5">
                          {s.totalPackets.toLocaleString()} packets &bull;{" "}
                          {formatBytes(s.totalBytes)} &bull;{" "}
                          {s.uniqueHosts} hosts &bull;{" "}
                          {s.durationSec.toFixed(1)}s
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-zinc-600 mr-2">
                        {new Date(s.createdAt).toLocaleDateString()}
                      </span>
                      <button
                        onClick={() => onLoadSession(s.id)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleDelete(s.id)}
                        disabled={deleting === s.id}
                        className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}