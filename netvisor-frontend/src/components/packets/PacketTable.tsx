import { useEffect, useState } from "react";
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
 * Shows every packet as gathered from the PCAP file, paginated.
 * Row click → select packet (details appear in right sidebar).
 */
export function PacketTable({ sessionId, localSubnet }: PacketTableProps) {
  const [packets, setPackets] = useState<FilteredPacket[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const isolatedNodeId = useUiStore((s) => s.filters.isolatedNodeId);
  const selectedProtocols = useUiStore((s) => s.filters.protocols);
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
  const [sourceMode, setSourceMode] = useState<"tshark" | "scapy" | null>(null);

  useEffect(() => {
    checkTsharkStatus()
      .then((s) => setSourceMode(s.mode))
      .catch(() => setSourceMode(null));
  }, [sessionId]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPackets(sessionId, {
      protocol: selectedProtocols.length > 0 ? selectedProtocols.join(",") : undefined,
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
  }, [sessionId, isolatedNodeId, selectedProtocols, followedStream, filterIp, filterSrcIp, filterDstIp, subnetScope, localSubnet, filterPort, filterSrcPort, filterDstPort, filterSearch, synOnly, page]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [isolatedNodeId, selectedProtocols, followedStream, filterIp, filterSrcIp, filterDstIp, subnetScope, filterPort, filterSrcPort, filterDstPort, filterSearch, synOnly]);

  const totalPages = Math.max(1, Math.ceil(totalPackets / PAGE_SIZE));

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
            className="flex items-center gap-1 text-blue-300 hover:text-white underline"
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

      {/* Packet rows */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
          </div>
        ) : packets.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-zinc-500">No packets</p>
          </div>
        ) : (
          packets.map((pkt) => {
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
          })
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-3 py-2 text-xs text-zinc-500 border-t border-zinc-800 shrink-0">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1 || loading}
          className="px-3 py-1.5 bg-zinc-800 rounded-lg disabled:opacity-30 hover:bg-zinc-700 transition-colors"
        >
          Prev
        </button>
        <span className="text-zinc-400">
          Page {page} of {totalPages.toLocaleString()}
          <span className="text-zinc-600 ml-2">({totalPackets.toLocaleString()} pkts)</span>
        </span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages || loading}
          className="px-3 py-1.5 bg-zinc-800 rounded-lg disabled:opacity-30 hover:bg-zinc-700 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}
