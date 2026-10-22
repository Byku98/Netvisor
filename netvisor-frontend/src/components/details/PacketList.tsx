import { useCallback, useEffect, useRef, useState } from "react";
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
 * Infinite scroll: reaching the bottom auto-loads the next page — no buttons.
 */
export function PacketList({ sessionId, srcIp, dstIp }: PacketListProps) {
  const [packets, setPackets] = useState<FilteredPacket[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const followedStream = useUiStore((s) => s.followedStream);

  // First page — resets whenever the data context (filters) changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPackets([]);
    setTotalPackets(0);
    fetchPackets(sessionId, {
      srcIp: srcIp || undefined,
      dstIp: dstIp || undefined,
      stream: followedStream ?? undefined,
      page: 1,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (cancelled) return;
        setPackets(data.packets);
        setTotalPackets(data.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load packets");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, srcIp, dstIp, followedStream]);

  // Auto-load the next page (called when the list is scrolled near its end)
  const loadMore = useCallback(() => {
    if (loading || loadingMore) return;
    if (packets.length === 0 || packets.length >= totalPackets) return;
    const nextPage = Math.floor(packets.length / PAGE_SIZE) + 1;
    setLoadingMore(true);
    setError(null);
    fetchPackets(sessionId, {
      srcIp: srcIp || undefined,
      dstIp: dstIp || undefined,
      stream: followedStream ?? undefined,
      page: nextPage,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        // Merge by packet index — guards against double-fetch races
        setPackets((prev) => {
          const seen = new Set(prev.map((p) => p.packetIndex));
          const fresh = data.packets.filter((p) => !seen.has(p.packetIndex));
          return [...prev, ...fresh];
        });
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load packets");
      })
      .finally(() => setLoadingMore(false));
  }, [loading, loadingMore, packets.length, totalPackets, sessionId, srcIp, dstIp, followedStream]);

  // Scroll sentinel: trigger loadMore ~120px before the bottom
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
      loadMore();
    }
  };

  return (
    <div className="flex flex-col">
      {/* Status line */}
      <div className="flex items-center justify-between px-3 py-1.5 text-[11px] text-zinc-500 border-b border-zinc-800/50">
        <span>
          {loading
            ? "Loading..."
            : `${packets.length.toLocaleString()} of ${totalPackets.toLocaleString()} packet${totalPackets !== 1 ? "s" : ""}`}
        </span>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-amber-400 bg-amber-950/20">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Rows — appending pages as you scroll */}
      <div ref={scrollRef} className="overflow-y-auto" onScroll={handleScroll}>
        {loading ? (
          <div className="flex items-center justify-center p-6">
            <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
          </div>
        ) : packets.length === 0 ? (
          <div className="p-4 text-center">
            <p className="text-xs text-zinc-500">No packets</p>
          </div>
        ) : (
          <>
            {packets.map((pkt) => {
              const color = getPacketColor(pkt.protocol);
              const isSelected = selectedPacketIndex === pkt.packetIndex;
              return (
                <button
                  key={pkt.packetIndex}
                  onClick={() => setSelectedPacket(isSelected ? null : pkt.packetIndex, pkt.stream)}
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
            })}
            {loadingMore && (
              <div className="flex items-center justify-center p-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" />
              </div>
            )}
            {!loadingMore && packets.length < totalPackets && (
              <div className="px-3 py-1.5 text-center text-[10px] text-zinc-600 border-t border-zinc-800/50">
                Scroll for more — {packets.length.toLocaleString()} of{" "}
                {totalPackets.toLocaleString()}
              </div>
            )}
            {!loadingMore && packets.length >= totalPackets && totalPackets > PAGE_SIZE && (
              <div className="px-3 py-1.5 text-center text-[10px] text-zinc-600 border-t border-zinc-800/50">
                End of list — all {totalPackets.toLocaleString()} packets loaded
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
