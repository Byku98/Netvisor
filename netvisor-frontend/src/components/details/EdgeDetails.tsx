import { useState, useEffect } from "react";
import { X, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import type { NetworkEdge } from "@/types/network.types";
import { fetchPackets, fetchPacketPayload } from "@/api/sessions.api";
import type { PacketHeader } from "@/api/sessions.api";
import { useUiStore } from "@/stores/ui.store";

interface EdgeDetailsProps {
  /** The selected edge data. */
  edge: NetworkEdge;
  /** Current session ID. */
  sessionId: string;
}

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Format timestamp to readable time. */
function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

/** Detail panel for a selected network edge with packet drill-down. */
export function EdgeDetails({ edge, sessionId }: EdgeDetailsProps) {
  const setSelectedEdge = useUiStore((s) => s.setSelectedEdge);
  const [packets, setPackets] = useState<PacketHeader[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [selectedPacket, setSelectedPacket] = useState<number | null>(null);
  const [payload, setPayload] = useState<string | null>(null);
  const [payloadLoading, setPayloadLoading] = useState(false);

  // Fetch packets when expanded (both directions)
  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    fetchPackets(sessionId, {
      srcIp: edge.source,
      dstIp: edge.target,
      page,
      pageSize: 20,
    })
      .then((data) => {
        setPackets(data.packets);
        setTotalPackets(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [expanded, sessionId, edge.source, edge.target, page]);

  // Lazy-load packet payload
  const handlePacketClick = async (packetIndex: number) => {
    if (selectedPacket === packetIndex) {
      setSelectedPacket(null);
      setPayload(null);
      return;
    }
    setSelectedPacket(packetIndex);
    setPayloadLoading(true);
    try {
      const data = await fetchPacketPayload(sessionId, packetIndex);
      setPayload(data.hex);
    } catch {
      setPayload("Failed to load payload");
    } finally {
      setPayloadLoading(false);
    }
  };

  const totalPages = Math.ceil(totalPackets / 20);

  return (
    <div className="h-full flex flex-col bg-zinc-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <h3 className="font-semibold text-zinc-200 text-sm">Connection</h3>
        <button
          onClick={() => setSelectedEdge(null)}
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Stats */}
        <div className="p-4 space-y-3 border-b border-zinc-800">
          <div>
            <p className="text-zinc-500 text-sm">Source</p>
            <p className="text-zinc-200 font-mono text-xs">{edge.source}</p>
          </div>
          <div>
            <p className="text-zinc-500 text-sm">Target</p>
            <p className="text-zinc-200 font-mono text-xs">{edge.target}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-zinc-500">Packets</p>
              <p className="text-zinc-200 font-mono">
                {edge.totalPackets.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-zinc-500">Bytes</p>
              <p className="text-zinc-200 font-mono">
                {formatBytes(edge.totalBytes)}
              </p>
            </div>
          </div>
          <div>
            <p className="text-zinc-500 text-sm">Protocols</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {edge.protocols.map((p) => (
                <span
                  key={p}
                  className="px-2 py-0.5 bg-zinc-800 text-zinc-300 text-xs rounded"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Packet drill-down toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between p-4 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
        >
          <span>Packets ({totalPackets || "?"})</span>
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {/* Packet list */}
        {expanded && (
          <div className="border-t border-zinc-800">
            {loading ? (
              <div className="flex items-center justify-center p-6">
                <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
              </div>
            ) : packets.length === 0 ? (
              <p className="p-4 text-sm text-zinc-500 text-center">
                No packets found
              </p>
            ) : (
              <div>
                {packets.map((pkt) => (
                  <div key={pkt.id}>
                    <button
                      onClick={() => handlePacketClick(pkt.packetIndex)}
                      className="w-full text-left px-4 py-2 text-xs hover:bg-zinc-800/50 transition-colors border-b border-zinc-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-zinc-500 w-8">
                            #{pkt.packetIndex}
                          </span>
                          <span className="text-zinc-300 font-mono">
                            {pkt.srcIp}:{pkt.srcPort ?? "?"} → {pkt.dstIp}:
                            {pkt.dstPort ?? "?"}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded">
                            {pkt.protocol}
                          </span>
                          <span className="text-zinc-500 w-14 text-right">
                            {pkt.length} B
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-zinc-500">
                          {formatTime(pkt.timestamp)}
                        </span>
                        <span className="text-zinc-500">{pkt.info}</span>
                      </div>
                    </button>

                    {/* Hex payload (lazy loaded) */}
                    {selectedPacket === pkt.packetIndex && (
                      <div className="px-4 py-2 bg-zinc-950 border-b border-zinc-800/50">
                        {payloadLoading ? (
                          <div className="flex items-center gap-2 text-zinc-500">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span className="text-xs">Loading payload...</span>
                          </div>
                        ) : (
                          <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap break-all leading-relaxed">
                            {payload
                              ? payload.match(/.{1,32}/g)?.join("\n") ?? payload
                              : "No payload"}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between p-3 text-xs text-zinc-500">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="px-2 py-1 bg-zinc-800 rounded disabled:opacity-30"
                    >
                      Prev
                    </button>
                    <span>
                      Page {page} of {totalPages}
                    </span>
                    <button
                      onClick={() =>
                        setPage((p) => Math.min(totalPages, p + 1))
                      }
                      disabled={page === totalPages}
                      className="px-2 py-1 bg-zinc-800 rounded disabled:opacity-30"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
