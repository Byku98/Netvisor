import { useEffect, useRef, useState } from "react";
import { Loader2, AlertTriangle, X, ChevronDown, ChevronRight, Copy, Check, ArrowLeft, Link2 } from "lucide-react";
import { fetchPacketDetail } from "@/api/sessions.api";
import type { PacketDetail, PacketLayer } from "@/api/sessions.api";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";

interface PacketDetailsProps {
  /** Session ID for API calls. */
  sessionId: string;
}

/** Format hex string into Wireshark-style rows: offset | hex | ascii. */
function formatHexDump(hex: string, bytesPerRow = 16): string[] {
  if (!hex) return [];
  const lines: string[] = [];
  const totalBytes = hex.length / 2;
  for (let row = 0; row < totalBytes; row += bytesPerRow) {
    const rowBytes: string[] = [];
    const ascii: string[] = [];
    for (let i = row; i < Math.min(row + bytesPerRow, totalBytes); i++) {
      const byteHex = hex.slice(i * 2, i * 2 + 2);
      rowBytes.push(byteHex);
      const byteVal = parseInt(byteHex, 16);
      ascii.push(byteVal >= 32 && byteVal < 127 ? String.fromCharCode(byteVal) : ".");
    }
    const offset = row.toString(16).padStart(4, "0");
    const hexPart = rowBytes.join(" ").padEnd(bytesPerRow * 3 - 1, " ");
    lines.push(`${offset}  ${hexPart}  |${ascii.join("")}|`);
  }
  return lines;
}

/** Dissection fields that can be applied as filters (key match is case-insensitive). */
const FILTERABLE_FIELDS: Record<
  string,
  { kind: "srcIp" | "dstIp" | "srcPort" | "dstPort" | "time"; hintKey: import("@/i18n").TKey }
> = {
  "source address": { kind: "srcIp", hintKey: "clickFilterSrcIp" },
  "destination address": { kind: "dstIp", hintKey: "clickFilterDstIp" },
  "source port": { kind: "srcPort", hintKey: "clickFilterSrcPort" },
  "destination port": { kind: "dstPort", hintKey: "clickFilterDstPort" },
  // ARP — sender/target protocol addresses (scapy keys + tshark -V labels)
  "sender ip": { kind: "srcIp", hintKey: "clickFilterSrcIp" },
  "target ip": { kind: "dstIp", hintKey: "clickFilterDstIp" },
  "sender ip address": { kind: "srcIp", hintKey: "clickFilterSrcIp" },
  "target ip address": { kind: "dstIp", hintKey: "clickFilterDstIp" },
  // Frame arrival time — opens the time popover (fills the panel's Time drafts)
  "arrival time": { kind: "time", hintKey: "clickFilterTime" },
};

/**
 * TCP flag tokens in the dissection tree's Flags row, mapped to the value
 * the flags filter API accepts. Two spellings per flag: tshark abbreviations
 * (PSH/RST) and scapy full names (PUSH/RESET). URG/ECE/CWR are intentionally
 * absent — the flags filter doesn't accept them, so those tokens stay plain.
 */
const TCP_FLAG_TOKENS: Record<string, string> = {
  ACK: "ack",
  PSH: "psh",
  PUSH: "psh",
  RST: "rst",
  RESET: "rst",
  FIN: "fin",
  SYN: "syn",
};
/** Splits a Flags value into captured flag tokens (odd parts) and text. */
const TCP_FLAG_TOKEN_RE = /(ACK|PSH|PUSH|RST|RESET|FIN|SYN)/;

/**
 * Arrival-time click-to-filter popover: From here / To here / ± N around.
 * Choices FILL the filter panel's Time section drafts (Apply commits) —
 * nothing is applied directly from here.
 */
function TimeFilterPopover({
  anchorEpoch,
  onClose,
}: {
  anchorEpoch: number;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const setTimeDraftProposal = useUiStore((s) => s.setTimeDraftProposal);
  const [windowText, setWindowText] = useState("5");

  /** Stage a draft proposal into the filter panel's Time section. */
  const propose = (mode: "from" | "to" | "around") => {
    const n = Number(windowText);
    setTimeDraftProposal({
      mode,
      anchor: anchorEpoch,
      windowS: Number.isFinite(n) && n > 0 ? n : 5,
    });
    onClose();
  };

  const choiceClasses =
    "text-left text-[11px] px-2 py-1 rounded text-zinc-200 hover:bg-zinc-700 hover:text-blue-300 transition-colors whitespace-nowrap";

  return (
    <div
      className="absolute left-0 top-full mt-1 z-50 w-max bg-zinc-800 border border-zinc-700
                 rounded-lg p-1.5 shadow-xl flex flex-col gap-1"
    >
      <button onClick={() => propose("from")} className={choiceClasses}>
        {t("timeFromHere")}
      </button>
      <button onClick={() => propose("to")} className={choiceClasses}>
        {t("timeToHere")}
      </button>
      <div className="flex items-center gap-1 px-1">
        <span className="text-[11px] text-zinc-500">±</span>
        <input
          value={windowText}
          onChange={(e) => setWindowText(e.target.value)}
          inputMode="decimal"
          className="w-10 bg-zinc-900 text-zinc-200 text-[11px] rounded px-1 py-0.5
                     border border-zinc-700 focus:border-blue-500 focus:outline-none
                     text-center font-mono"
        />
        <button onClick={() => propose("around")} className={choiceClasses}>
          {t("timeAroundHere")}
        </button>
      </div>
    </div>
  );
}

/**
 * Click-to-filter flag tokens inside the TCP Flags row value. A token click
 * adds the flag to filters.flags (additive, idempotent — clicking an already
 * applied flag does nothing); non-filterable tokens render as plain text.
 * Hover hint appears after ~2s like the other click-to-filter targets.
 */
function TcpFlagTokens({ value }: { value: string }) {
  const { t } = useI18n();
  const setFilters = useUiStore((s) => s.setFilters);
  const filterFlags = useUiStore((s) => s.filters.flags);

  return (
    <>
      {value.split(TCP_FLAG_TOKEN_RE).map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="group relative">
            <button
              onClick={() => {
                const flag = TCP_FLAG_TOKENS[part];
                if (!filterFlags.includes(flag)) {
                  setFilters({ flags: [...filterFlags, flag] });
                }
              }}
              className={`font-mono transition-colors ${
                filterFlags.includes(TCP_FLAG_TOKENS[part])
                  ? "text-blue-300 cursor-default"
                  : "text-zinc-200 underline decoration-dotted decoration-zinc-500 underline-offset-2 hover:text-blue-400 hover:decoration-blue-400 active:scale-95"
              }`}
            >
              {part}
            </button>
            <span
              className="pointer-events-none absolute left-0 top-full mt-1
                         w-max max-w-52 bg-zinc-800 border border-zinc-700 text-zinc-300
                         text-[10px] leading-snug rounded px-2 py-1 shadow-lg z-50
                         opacity-0 group-hover:opacity-100 transition-opacity
                         delay-[1800ms] duration-200"
            >
              {t("clickFilterTcpFlag")}
            </span>
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/** One collapsible protocol layer in the dissection tree. */
function LayerSection({
  layer,
  defaultOpen,
  timestamp,
}: {
  layer: PacketLayer;
  defaultOpen: boolean;
  /** Packet capture timestamp (epoch seconds) — enables the time popover. */
  timestamp: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [timePopOpen, setTimePopOpen] = useState(false);
  const timeFieldRef = useRef<HTMLSpanElement>(null);
  const setFilters = useUiStore((s) => s.setFilters);
  const { t } = useI18n();

  // Close the time popover on outside click / Esc.
  useEffect(() => {
    if (!timePopOpen) return;
    const onDown = (e: MouseEvent) => {
      if (timeFieldRef.current && !timeFieldRef.current.contains(e.target as Node)) {
        setTimePopOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setTimePopOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [timePopOpen]);

  /** Apply a filterable field value to the matching Specify-side filter. */
  const applyFieldFilter = (target: { kind: string }, raw: string) => {
    const value = raw.trim().split(" ")[0];
    if (target.kind === "srcIp") setFilters({ srcIp: value, ip: "" });
    else if (target.kind === "dstIp") setFilters({ dstIp: value, ip: "" });
    else if (target.kind === "srcPort") setFilters({ srcPort: value, port: "" });
    else if (target.kind === "dstPort") setFilters({ dstPort: value, port: "" });
  };

  return (
    <div className="border-b border-zinc-800/50 last:border-b-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-2 text-left hover:bg-zinc-800/50 transition-colors active:scale-[0.98]"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
        )}
        <span className="text-xs font-medium text-zinc-200 truncate">{layer.name}</span>
      </button>

      {open && (
        <div className="pb-2">
          <p className="px-3 pb-1.5 text-[11px] text-zinc-500 break-words">{layer.summary}</p>
          <div className="space-y-0.5">
            {layer.fields.map((f, i) =>
              f.key ? (() => {
                // TCP Flags row — flag names are click-to-filter tokens.
                if (f.key.toLowerCase() === "flags") {
                  return (
                    <div key={i} className="flex gap-2 px-3 py-0.5 text-[11px] hover:bg-zinc-800/30">
                      <span className="text-zinc-500 shrink-0">{f.key}</span>
                      <span className="text-zinc-200 font-mono break-all min-w-0">
                        <TcpFlagTokens value={f.value} />
                      </span>
                    </div>
                  );
                }
                const target = FILTERABLE_FIELDS[f.key.toLowerCase()];
                // Time needs the exact epoch from the detail response —
                // without it (older backend) the field stays plain text.
                if (!target || (target.kind === "time" && !Number.isFinite(timestamp))) {
                  return (
                    <div key={i} className="flex gap-2 px-3 py-0.5 text-[11px] hover:bg-zinc-800/30">
                      <span className="text-zinc-500 shrink-0">{f.key}</span>
                      <span className="text-zinc-200 font-mono break-all min-w-0">{f.value}</span>
                    </div>
                  );
                }
                const isTime = target.kind === "time";
                return (
                  <div key={i} className="flex gap-2 px-3 py-0.5 text-[11px] hover:bg-zinc-800/30">
                    <span className="text-zinc-500 shrink-0">{f.key}</span>
                    <span
                      className="group relative min-w-0"
                      ref={isTime ? timeFieldRef : undefined}
                    >
                      <button
                        onClick={() => {
                          if (isTime) setTimePopOpen((v) => !v);
                          else applyFieldFilter(target, f.value);
                        }}
                        className="text-zinc-200 font-mono break-all underline decoration-dotted decoration-zinc-500
                                   underline-offset-2 hover:text-blue-400 hover:decoration-blue-400
                                   transition-colors active:scale-95 text-left"
                      >
                        {f.value}
                      </button>
                      {isTime && timePopOpen && (
                        <TimeFilterPopover
                          anchorEpoch={timestamp}
                          onClose={() => setTimePopOpen(false)}
                        />
                      )}
                      {/* Hint appears after ~2s of hovering */}
                      <span
                        className="pointer-events-none absolute left-0 top-full mt-1
                                   w-max max-w-52 bg-zinc-800 border border-zinc-700 text-zinc-300
                                   text-[10px] leading-snug rounded px-2 py-1 shadow-lg z-50
                                   opacity-0 group-hover:opacity-100 transition-opacity
                                   delay-[1800ms] duration-200"
                      >
                        {t(target.hintKey)}
                      </span>
                    </span>
                  </div>
                );
              })() : (
                <div key={i} className="px-3 py-0.5 text-[11px] text-zinc-400">
                  {f.value}
                </div>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Right sidebar: full packet dissection tree + hex dump + follow stream. */
export function PacketDetails({ sessionId }: PacketDetailsProps) {
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const selectedPacketStream = useUiStore((s) => s.selectedPacketStream);
  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const setSelectedNode = useUiStore((s) => s.setSelectedNode);
  const setSelectedEdge = useUiStore((s) => s.setSelectedEdge);
  const setFollowedStream = useUiStore((s) => s.setFollowedStream);
  const followedStream = useUiStore((s) => s.followedStream);
  const setStreamFocus = useUiStore((s) => s.setStreamFocus);
  const hasBackContext = useUiStore(
    (s) => s.selectedNodeId != null || s.selectedEdgeId != null,
  );

  const [detail, setDetail] = useState<PacketDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHex, setShowHex] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (selectedPacketIndex == null) {
      setDetail(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    setDetail(null);
    fetchPacketDetail(sessionId, selectedPacketIndex)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load packet detail"),
      )
      .finally(() => setLoading(false));
  }, [sessionId, selectedPacketIndex]);

  const hexLines = detail ? formatHexDump(detail.raw) : [];

  /**
   * Scrape the current packet's src/dst IPs from the IP layer (same fields
   * the old graph-jump handler used). The current packet is part of the
   * stream being followed, so its endpoints define the stream focus. Null
   * when the packet has no IP layer (non-IP traffic) — the stream is still
   * followed, just without a graph marker.
   */
  const scrapeStreamIps = (): { srcIp: string; dstIp: string } | null => {
    if (!detail) return null;
    const ipLayer = detail.layers.find((l) => /Internet Protocol/i.test(l.name));
    const srcField = ipLayer?.fields.find((f) => /source address/i.test(f.key));
    const dstField = ipLayer?.fields.find((f) => /destination address/i.test(f.key));
    const srcIp = srcField?.value.split(" ")[0];
    const dstIp = dstField?.value.split(" ")[0];
    return srcIp && dstIp ? { srcIp, dstIp } : null;
  };

  /**
   * Follow a stream — one-way: clicking the active stream's button is a
   * no-op (cancelling happens only via the filter panel's stream-focus row).
   * Following a DIFFERENT stream replaces the previous one. Follow-start
   * also sets the stream focus from the current packet's endpoints and
   * returns the panel to the (now stream-filtered) packet list — no manual
   * Back click needed.
   */
  const handleFollowStream = () => {
    if (selectedPacketStream == null) return;
    if (followedStream === selectedPacketStream) return;
    setStreamFocus(scrapeStreamIps());
    setFollowedStream(selectedPacketStream);
    setSelectedPacket(null);
  };

  const handleCopyHex = async () => {
    if (!detail?.raw) return;
    try {
      await navigator.clipboard.writeText(detail.raw);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };

  if (selectedPacketIndex == null) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-zinc-900 text-center p-6">
        <p className="text-sm text-zinc-500">No packet selected</p>
        <p className="text-xs text-zinc-600 mt-1">Click a row in the packet table</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-zinc-900 animate-fade-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          {hasBackContext && (
            <button
              onClick={() => setSelectedPacket(null)}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-zinc-400 bg-zinc-800 hover:bg-zinc-700 hover:text-zinc-200 transition-colors shrink-0 active:scale-95"
              title="Back to details"
            >
              <ArrowLeft className="h-3 w-3" />
              Back
            </button>
          )}
          <h3 className="font-semibold text-zinc-200">
            Packet #{selectedPacketIndex}
          </h3>
        </div>
        <button
          onClick={() => {
            // Close the whole panel: packet + node/edge selection
            setSelectedPacket(null);
            setSelectedNode(null);
            setSelectedEdge(null);
          }}
          className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center p-8 gap-2">
            <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
            <span className="text-xs text-zinc-500">Dissecting packet...</span>
          </div>
        ) : error ? (
          <div className="p-3 flex items-center gap-2 text-xs text-amber-400 bg-amber-950/20 m-3 rounded-lg">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        ) : detail ? (
          <>
            {/* Follow TCP stream — starting a follow sets the graph stream focus */}
            <div className="p-3 space-y-2 border-b border-zinc-800">
              {selectedPacketStream != null && (
                followedStream === selectedPacketStream ? (
                  // Active state is a passive badge, NOT a button — the
                  // stream is cancelled only from the filter panel's
                  // stream-focus row, so this must not look clickable.
                  <div
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-blue-600/20 text-blue-300 border border-blue-600/40"
                    aria-live="polite"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    Following Stream {selectedPacketStream}
                  </div>
                ) : (
                  <button
                    onClick={handleFollowStream}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97] bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    Follow TCP Stream {selectedPacketStream}
                  </button>
                )
              )}
            </div>

            {/* Dissection tree */}
            <div>
              <div className="px-3 py-2 text-[11px] font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800/50">
                Protocol Dissection
              </div>
              {detail.layers.map((layer, i) => (
                <LayerSection
                  key={i}
                  layer={layer}
                  defaultOpen={i === detail.layers.length - 1}
                  timestamp={detail.timestamp}
                />
              ))}
            </div>

            {/* Hex dump */}
            <div className="border-t border-zinc-800">
              <button
                onClick={() => setShowHex(!showHex)}
                className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-medium text-zinc-400 uppercase tracking-wider hover:bg-zinc-800/50 transition-colors"
              >
                <span>Hex Dump ({detail.raw.length / 2} bytes)</span>
                {showHex ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>

              {showHex && (
                <div className="pb-3">
                  <button
                    onClick={handleCopyHex}
                    className="mx-3 mb-2 flex items-center gap-1.5 px-2 py-1 text-[11px] text-zinc-400 bg-zinc-800 hover:bg-zinc-700 rounded transition-colors active:scale-95"
                  >
                    {copied ? (
                      <Check className="h-3 w-3 text-green-400" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                    {copied ? "Copied" : "Copy hex"}
                  </button>
                  <pre className="px-3 text-[10px] leading-relaxed font-mono text-zinc-400 overflow-x-auto">
                    {hexLines.length > 0
                      ? hexLines.join("\n")
                      : "Hex dump unavailable"}
                  </pre>
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
