import { useEffect, useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { fetchPackets } from "@/api/sessions.api";
import type { FilteredPacket } from "@/api/sessions.api";
import { useUiStore } from "@/stores/ui.store";
import { getPacketColor } from "@/lib/protocol-colors";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 30;

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface PacketListProps {
  /** Session ID for API calls. */
  sessionId: string;
  /** Filter by source IP (e.g. selected node). */
  srcIp?: string | null;
  /** Filter by destination IP (e.g. edge target). */
  dstIp?: string | null;
}

/**
 * Compact packet list for the right sidebar (node/edge drill-down).
 * Wireshark-style rows; clicking a row opens the full packet dissection view.
 */
export function PacketList({ sessionId, srcIp, dstIp }: PacketListProps) {
  const [packets, setPackets] = useState<FilteredPacket[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPackets(sessionId, {
      srcIp: srcIp || undefined,
      dstIp: dstIp || undefined,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        setPackets(data.packets);
        setTotalPackets(data.total);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load packets");
        setPackets([]);
        setTotalPackets(0);
      })
      .finally(() => setLoading(false));
  }, [sessionId, srcIp, dstIp, page]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [srcIp, dstIp]);

  const totalPages = Math.max(1, Math.ceil(totalPackets / PAGE_SIZE));

  return (
    <div className="flex flex-col">
      {/* Status line */}
      <div className="flex items-center justify-between px-3 py-1.5 text-[11px] text-zinc-500 border-b border-zinc-800/50">
        <span>
          {loading
            ? "Loading..."
            : `${totalPackets.toLocaleString()} packet${totalPackets !== 1 ? "s" : ""}`}
        </span>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-amber-400 bg-amber-950/20">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Rows */}
      <div className="overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center p-6">
            <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
          </div>
        ) : packets.length === 0 ? (
          <div className="p-4 text-center">
            <p className="text-xs text-zinc-500">No packets</p>
          </div>
        ) : (
          packets.map((pkt) => {
            const color = getPacketColor(pkt.protocol);
            const isSelected = selectedPacketIndex === pkt.packetIndex;
            return (
              <button
                key={pkt.packetIndex}
                onClick={() => setSelectedPacket(isSelected ? null : pkt.packetIndex)}
                className={cn(
                  "w-full grid grid-cols-[2.25rem_4rem_1fr_2.75rem] gap-1.5 px-2.5 py-1.5 text-[11px] text-left border-b border-zinc-800/50 transition-colors",
                  color.bg,
                  isSelected
                    ? "bg-blue-950/50 ring-1 ring-inset ring-blue-500/50"
                    : "hover:bg-zinc-800/50",
                )}
              >
                <span className="text-right text-zinc-600 font-mono">
                  {pkt.packetIndex}
                </span>
                <span className="text-zinc-400 font-mono truncate">
                  {pkt.timestampFormatted}
                </span>
                <span className="flex items-center gap-1 min-w-0">
                  <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", color.dot)} />
                  <span className={cn("font-medium shrink-0", color.text)}>
                    {pkt.protocol}
                  </span>
                  <span className="text-zinc-400 font-mono truncate">
                    {pkt.srcIp}:{pkt.srcPort ?? "*"} &rarr; {pkt.dstIp}:{pkt.dstPort ?? "*"}
                  </span>
                </span>
                <span className="text-right text-zinc-500 font-mono">
                  {formatBytes(pkt.length)}
                </span>
                <span className="col-span-4 text-zinc-500 truncate pl-1" title={pkt.info}>
                  {pkt.info}
                </span>
              </button>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 text-[11px] text-zinc-500 border-t border-zinc-800">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
            className="px-2.5 py-1 bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700 transition-colors"
          >
            Prev
          </button>
          <span className="text-zinc-400">
            Page {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || loading}
            className="px-2.5 py-1 bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
