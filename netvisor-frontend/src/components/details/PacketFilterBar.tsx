import { useEffect, useRef, useState } from "react";
import { Search, X, Loader2, AlertTriangle } from "lucide-react";
import { fetchPackets, fetchPacketPayload } from "@/api/sessions.api";
import type { FilteredPacket } from "@/api/sessions.api";
import { cn } from "@/lib/utils";

/** Protocol color mapping for packet rows. */
const PROTOCOL_COLORS: Record<string, { bg: string; dot: string; text: string }> = {
  TCP:   { bg: "hover:bg-blue-950/30",  dot: "bg-blue-500",   text: "text-blue-400"   },
  UDP:   { bg: "hover:bg-purple-950/30", dot: "bg-purple-500", text: "text-purple-400" },
  HTTP:  { bg: "hover:bg-green-950/30",  dot: "bg-green-500",  text: "text-green-400"  },
  HTTPS: { bg: "hover:bg-emerald-950/30",dot: "bg-emerald-500",text: "text-emerald-400"},
  TLS:   { bg: "hover:bg-emerald-950/30",dot: "bg-emerald-500",text: "text-emerald-400"},
  DNS:   { bg: "hover:bg-yellow-950/30", dot: "bg-yellow-500", text: "text-yellow-400" },
  ICMP:  { bg: "hover:bg-orange-950/30", dot: "bg-orange-500", text: "text-orange-400" },
  ARP:   { bg: "hover:bg-pink-950/30",   dot: "bg-pink-500",   text: "text-pink-400"   },
  SSH:   { bg: "hover:bg-cyan-950/30",   dot: "bg-cyan-500",   text: "text-cyan-400"   },
  FTP:   { bg: "hover:bg-rose-950/30",   dot: "bg-rose-500",   text: "text-rose-400"   },
  SMTP:  { bg: "hover:bg-indigo-950/30", dot: "bg-indigo-500", text: "text-indigo-400" },
  DHCP:  { bg: "hover:bg-teal-950/30",   dot: "bg-teal-500",   text: "text-teal-400"   },
};

function getPacketColor(proto: string) {
  return PROTOCOL_COLORS[proto.toUpperCase()] ?? { bg: "hover:bg-zinc-800/30", dot: "bg-zinc-500", text: "text-zinc-400" };
}

/** Protocol filter dropdown options. */
const PROTOCOL_OPTIONS = [
  { value: "",       label: "All Protocols" },
  { value: "tcp",    label: "TCP" },
  { value: "udp",    label: "UDP" },
  { value: "http",   label: "HTTP" },
  { value: "https",  label: "HTTPS / TLS" },
  { value: "dns",    label: "DNS" },
  { value: "icmp",   label: "ICMP" },
  { value: "ssh",    label: "SSH" },
  { value: "arp",    label: "ARP" },
  { value: "ftp",    label: "FTP" },
  { value: "smtp",   label: "SMTP" },
  { value: "dhcp",   label: "DHCP" },
];

/** Port filter dropdown options. */
const PORT_OPTIONS = [
  { value: 0,    label: "All Ports" },
  { value: 80,   label: "80 (HTTP)" },
  { value: 443,  label: "443 (HTTPS)" },
  { value: 53,   label: "53 (DNS)" },
  { value: 22,   label: "22 (SSH)" },
  { value: 25,   label: "25 (SMTP)" },
  { value: 21,   label: "21 (FTP)" },
  { value: 3389, label: "3389 (RDP)" },
  { value: 8080, label: "8080 (Alt HTTP)" },
];

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface PacketFilterBarProps {
  /** Session ID for API calls. */
  sessionId: string;
  /** Filter by source IP (pre-filled, e.g. selected node). */
  srcIp?: string | null;
  /** Filter by destination IP (pre-filled, e.g. edge target). */
  dstIp?: string | null;
}

/**
 * Wireshark-style packet drill-down with filter dropdowns.
 * Gen Z / Alpha friendly: dropdowns, not raw expressions.
 */
export function PacketFilterBar({ sessionId, srcIp, dstIp }: PacketFilterBarProps) {
  const [packets, setPackets] = useState<FilteredPacket[]>([]);
  const [totalPackets, setTotalPackets] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [protocol, setProtocol] = useState("");
  const [port, setPort] = useState(0);
  const [searchText, setSearchText] = useState("");

  // Packet detail state
  const [selectedPacket, setSelectedPacket] = useState<number | null>(null);
  const [payload, setPayload] = useState<string | null>(null);
  const [payloadLoading, setPayloadLoading] = useState(false);

  // Debounce search
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchText);
    }, 300);
    return () => { if (debounceTimer.current) clearTimeout(debounceTimer.current); };
  }, [searchText]);

  // Fetch packets
  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPackets(sessionId, {
      protocol: protocol || undefined,
      port: port || undefined,
      srcIp: srcIp || undefined,
      dstIp: dstIp || undefined,
      search: debouncedSearch || undefined,
      page,
      pageSize: 30,
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
  }, [sessionId, srcIp, dstIp, protocol, port, debouncedSearch, page]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [protocol, port, debouncedSearch]);

  // Lazy-load hex payload
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

  const totalPages = Math.ceil(totalPackets / 30);

  return (
    <div className="flex flex-col">
      {/* ── Filter Bar ──────────────────────────────────────── */}
      <div className="p-3 space-y-2 border-b border-zinc-800">
        {/* Row 1: Protocol + Port dropdowns */}
        <div className="flex gap-2">
          <select
            value={protocol}
            onChange={(e) => setProtocol(e.target.value)}
            className="flex-1 bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       cursor-pointer appearance-none"
          >
            {PROTOCOL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <select
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
            className="flex-1 bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       cursor-pointer appearance-none"
          >
            {PORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Row 2: Search bar */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search packets..."
            className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg pl-8 pr-8 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       placeholder:text-zinc-500"
          />
          {searchText && (
            <button
              onClick={() => setSearchText("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Status line */}
        <div className="flex items-center justify-between text-[11px] text-zinc-500">
          <span>
            {loading ? "Loading..." : `Showing ${packets.length} of ${totalPackets.toLocaleString()} packets`}
          </span>
          {(protocol || port || debouncedSearch) && (
            <button
              onClick={() => { setProtocol(""); setPort(0); setSearchText(""); }}
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* ── Error State ─────────────────────────────────────── */}
      {error && (
        <div className="p-3 flex items-center gap-2 text-xs text-amber-400 bg-amber-950/20 border-b border-zinc-800">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Packet List ─────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
        </div>
      ) : packets.length === 0 ? (
        <div className="p-6 text-center">
          <p className="text-sm text-zinc-500">No packets found</p>
          {(protocol || port || debouncedSearch) && (
            <p className="text-xs text-zinc-600 mt-1">Try adjusting your filters</p>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {packets.map((pkt) => {
            const color = getPacketColor(pkt.protocol);
            return (
              <div key={pkt.packetIndex}>
                <button
                  onClick={() => handlePacketClick(pkt.packetIndex)}
                  className={cn(
                    "w-full text-left px-3 py-2 text-xs transition-colors border-b border-zinc-800/50",
                    color.bg,
                    selectedPacket === pkt.packetIndex && "bg-zinc-800/50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-zinc-600 w-7 shrink-0 text-right">
                        {pkt.packetIndex}
                      </span>
                      <span className="text-zinc-300 font-mono truncate">
                        {pkt.srcIp}:{pkt.srcPort ?? "*"} → {pkt.dstIp}:{pkt.dstPort ?? "*"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded">
                        <span className={cn("w-1.5 h-1.5 rounded-full", color.dot)} />
                        <span className={cn("font-medium", color.text)}>{pkt.protocol}</span>
                      </span>
                      <span className="text-zinc-500 w-14 text-right">
                        {formatBytes(pkt.length)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-zinc-600 w-16 shrink-0 text-right">
                      {pkt.timestampFormatted}
                    </span>
                    <span className="text-zinc-500 truncate">{pkt.info}</span>
                  </div>
                </button>

                {/* Hex payload (lazy loaded) */}
                {selectedPacket === pkt.packetIndex && (
                  <div className="px-3 py-2 bg-zinc-950 border-b border-zinc-800/50">
                    {payloadLoading ? (
                      <div className="flex items-center gap-2 text-zinc-500">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span className="text-xs">Loading payload...</span>
                      </div>
                    ) : (
                      <pre className="text-[11px] text-zinc-400 font-mono whitespace-pre-wrap break-all leading-relaxed">
                        {payload
                          ? payload.match(/.{1,32}/g)?.join("\n") ?? payload
                          : "No payload"}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Pagination ──────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-3 text-xs text-zinc-500 border-t border-zinc-800">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 bg-zinc-800 rounded-lg disabled:opacity-30 hover:bg-zinc-700 transition-colors"
          >
            Prev
          </button>
          <span className="text-zinc-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 bg-zinc-800 rounded-lg disabled:opacity-30 hover:bg-zinc-700 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}