import { useEffect, useState } from "react";
import { fetchMySessions } from "@/api/auth.api";
import { AppHeader } from "@/components/auth/AppHeader";
import { useAuthStore } from "@/stores/auth.store";
import { FolderOpen, FileText } from "lucide-react";

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

export function MySessions({ onBack }: { onBack: () => void }) {
  const user = useAuthStore((s) => s.user);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    fetchMySessions()
      .then((data) => setSessions(data as SessionItem[]))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col">
        <AppHeader onBack={onBack} />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-zinc-500">Please sign in to view your sessions.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader onBack={onBack} />

      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-6">
            <FolderOpen className="h-6 w-6 text-blue-500" />
            <h2 className="text-2xl font-bold">My Sessions</h2>
            <span className="text-sm text-zinc-500 ml-2">
              {sessions.length} session{sessions.length !== 1 ? "s" : ""}
            </span>
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
            </div>
          )}

          {!loading && !error && sessions.length > 0 && (
            <div className="space-y-3">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-zinc-500" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">
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
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-600">
                        {new Date(s.createdAt).toLocaleDateString()}
                      </span>
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