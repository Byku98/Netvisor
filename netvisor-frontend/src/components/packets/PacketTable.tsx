import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, AlertTriangle, Link2Off, Zap } from "lucide-react";
import { fetchPackets, checkTsharkStatus } from "@/api/sessions.api";
import type { FilteredPacket } from "@/api/sessions.api";
import { useUiStore } from "@/stores/ui.store";
import { getPacketColor } from "@/lib/protocol-colors";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface PacketTableProps {
  /** Session ID for API calls. */
  sessionId: string;
  /** Dominant local subnet in CIDR (for Local/External scope), e.g. "192.168.1.0/24". */
  localSubnet: string | null;
}

/**
 * Full-width Wireshark-style packet table for the main content area.
 * Shows every packet as gathered from the PCAP file, appending pages
 * as you scroll (infinite scroll — no pagination buttons).
 * Row click → select packet (details appear in right sidebar).
 */
export function PacketTable({ sessionId, localSubnet }: PacketTableProps) {
  const [packets, setPackets] = useState<FilteredPacket[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const isolatedNodeId = useUiStore((s) => s.filters.isolatedNodeId);
  const selectedProtocols = useUiStore((s) => s.filters.protocols);
  const excludedProtocols = useUiStore((s) => s.filters.excludedProtocols);
  const followedStream = useUiStore((s) => s.followedStream);
  const setFollowedStream = useUiStore((s) => s.setFollowedStream);
  const filterIp = useUiStore((s) => s.filters.ip);
  const filterSrcIp = useUiStore((s) => s.filters.srcIp);
  const filterDstIp = useUiStore((s) => s.filters.dstIp);
  const subnetScope = useUiStore((s) => s.filters.subnetScope);
  const filterPort = useUiStore((s) => s.filters.port);
  const filterSrcPort = useUiStore((s) => s.filters.srcPort);
  const filterDstPort = useUiStore((s) => s.filters.dstPort);
  const filterSearch = useUiStore((s) => s.filters.search);
  const synOnly = useUiStore((s) => s.filters.synOnly);
  const rstOnly = useUiStore((s) => s.filters.rstOnly);
  const [sourceMode, setSourceMode] = useState<"tshark" | "scapy" | null>(null);

  useEffect(() => {
    checkTsharkStatus()
      .then((s) => setSourceMode(s.mode))
      .catch(() => setSourceMode(null));
  }, [sessionId]);

  // First page — resets the accumulated list whenever the filter context changes
  const filterKey = [
    sessionId, isolatedNodeId, selectedProtocols.join(","), excludedProtocols.join(","),
    followedStream, filterIp, filterSrcIp, filterDstIp, subnetScope, localSubnet,
    filterPort, filterSrcPort, filterDstPort, filterSearch, synOnly, rstOnly,
  ].join("|");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPackets([]);
    setTotalPackets(0);
    fetchPackets(sessionId, {
      protocol: selectedProtocols.length > 0 ? selectedProtocols.join(",") : undefined,
      protocolExclude: excludedProtocols.length > 0 ? excludedProtocols.join(",") : undefined,
      // Node isolation = traffic TO/FROM the node (either side) — wins over
      // all manual IP filters; ghost ARP-only nodes stay visible
      ip: isolatedNodeId || filterIp || undefined,
      srcIp: isolatedNodeId ? undefined : filterSrcIp || undefined,
      dstIp: isolatedNodeId ? undefined : filterDstIp || undefined,
      stream: followedStream ?? undefined,
      subnet: subnetScope !== "all" ? localSubnet ?? undefined : undefined,
      subnetScope: subnetScope !== "all" ? subnetScope : undefined,
      port: filterPort || undefined,
      srcPort: filterSrcPort || undefined,
      dstPort: filterDstPort || undefined,
      search: filterSearch || undefined,
      synOnly,
      rstOnly,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  // Auto-load the next page (called when the table is scrolled near its end)
  const loadMore = useCallback(() => {
    if (loading || loadingMore) return;
    if (packets.length === 0 || packets.length >= totalPackets) return;
    const nextPage = Math.floor(packets.length / PAGE_SIZE) + 1;
    setLoadingMore(true);
    setError(null);
    fetchPackets(sessionId, {
      protocol: selectedProtocols.length > 0 ? selectedProtocols.join(",") : undefined,
      protocolExclude: excludedProtocols.length > 0 ? excludedProtocols.join(",") : undefined,
      ip: isolatedNodeId || filterIp || undefined,
      srcIp: isolatedNodeId ? undefined : filterSrcIp || undefined,
      dstIp: isolatedNodeId ? undefined : filterDstIp || undefined,
      stream: followedStream ?? undefined,
      subnet: subnetScope !== "all" ? localSubnet ?? undefined : undefined,
      subnetScope: subnetScope !== "all" ? subnetScope : undefined,
      port: filterPort || undefined,
      srcPort: filterSrcPort || undefined,
      dstPort: filterDstPort || undefined,
      search: filterSearch || undefined,
      synOnly,
      rstOnly,
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
  }, [loading, loadingMore, packets.length, totalPackets, sessionId, isolatedNodeId,
      selectedProtocols, excludedProtocols, followedStream, filterIp, filterSrcIp,
      filterDstIp, subnetScope, localSubnet, filterPort, filterSrcPort, filterDstPort,
      filterSearch, synOnly, rstOnly]);

  // Scroll sentinel: trigger loadMore ~150px before the bottom
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 150) {
      loadMore();
    }
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      {/* Table header */}
      <div className="grid grid-cols-[3rem_6.5rem_11rem_11rem_4.5rem_4.5rem_1fr] gap-2 px-3 py-2 text-[11px] font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800 bg-zinc-900 shrink-0">
        <span className="text-right">#</span>
        <span>Time</span>
        <span>Source</span>
        <span>Destination</span>
        <span>Proto</span>
        <span className="text-right">Len</span>
        <span>Info</span>
      </div>

      {/* Following stream banner */}
      {followedStream != null && (
        <div className="flex items-center justify-between px-3 py-1.5 text-[11px] bg-blue-950/40 border-b border-blue-800/50 text-blue-300 shrink-0">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            Following TCP Stream {followedStream}
          </span>
          <button
            onClick={() => setFollowedStream(null)}
            className="flex items-center gap-1 text-blue-300 hover:text-white underline transition-colors active:scale-95"
          >
            <Link2Off className="h-3 w-3" />
            Stop following
          </button>
        </div>
      )}

      {/* Status line */}
      <div className="flex items-center justify-between px-3 py-1.5 text-[11px] text-zinc-500 border-b border-zinc-800/50 shrink-0">
        <span>
          {loading
            ? "Loading packets..."
            : `Showing ${packets.length} of ${totalPackets.toLocaleString()} packets`}
          {isolatedNodeId && !loading && (
            <span className="text-amber-400 ml-2">(isolated: {isolatedNodeId})</span>
          )}
          {selectedProtocols.length > 0 && !loading && (
            <span className="text-blue-400 ml-2">
              ({selectedProtocols.join(", ")})
            </span>
          )}
          {sourceMode === "scapy" && (
            <span
              className="flex items-center gap-1 text-amber-400 ml-2"
              title="tshark not installed — simplified dissection via scapy"
            >
              <Zap className="h-3 w-3" />
              Scapy mode
            </span>
          )}
        </span>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-amber-400 bg-amber-950/20 shrink-0">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Packet rows — appending pages as you scroll */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto" onScroll={handleScroll}>
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
          </div>
        ) : packets.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-zinc-500">No packets</p>
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
                    "w-full grid grid-cols-[3rem_6.5rem_11rem_11rem_4.5rem_4.5rem_1fr] gap-2 px-3 py-1.5 text-xs text-left border-b border-zinc-800/50 transition-colors",
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
                  <span className="text-zinc-300 font-mono truncate" title={pkt.srcIp}>
                    {pkt.srcIp}{pkt.srcPort != null && `:${pkt.srcPort}`}
                  </span>
                  <span className="text-zinc-300 font-mono truncate" title={pkt.dstIp}>
                    {pkt.dstIp}{pkt.dstPort != null && `:${pkt.dstPort}`}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", color.dot)} />
                    <span className={cn("font-medium truncate", color.text)}>
                      {pkt.protocol}
                    </span>
                  </span>
                  <span className="text-right text-zinc-500 font-mono">
                    {formatBytes(pkt.length)}
                  </span>
                  <span className="text-zinc-500 truncate" title={pkt.info}>
                    {pkt.info}
                  </span>
                </button>
              );
            })}
            {loadingMore && (
              <div className="flex items-center justify-center p-3">
                <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom status */}
      <div className="px-3 py-1.5 text-[10px] text-zinc-600 border-t border-zinc-800 shrink-0 text-center">
        {loadingMore
          ? "Loading more packets..."
          : packets.length > 0 && packets.length >= totalPackets
            ? `End of list — all ${totalPackets.toLocaleString()} packets loaded`
            : packets.length > 0
              ? `Scroll for more — ${packets.length.toLocaleString()} of ${totalPackets.toLocaleString()} loaded`
              : ""}
      </div>
    </div>
  );
}
