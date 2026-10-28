import { useEffect, useState } from "react";
import { Loader2, AlertTriangle, X, ChevronDown, ChevronRight, Workflow, Copy, Check, ArrowLeft, Link2, Link2Off } from "lucide-react";
import { fetchPacketDetail } from "@/api/sessions.api";
import type { PacketDetail, PacketLayer } from "@/api/sessions.api";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

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
const FILTERABLE_FIELDS: Record<string, { kind: "srcIp" | "dstIp" | "srcPort" | "dstPort"; hintKey: string }> = {
  "source address": { kind: "srcIp", hintKey: "clickFilterSrcIp" },
  "destination address": { kind: "dstIp", hintKey: "clickFilterDstIp" },
  "source port": { kind: "srcPort", hintKey: "clickFilterSrcPort" },
  "destination port": { kind: "dstPort", hintKey: "clickFilterDstPort" },
};

/** One collapsible protocol layer in the dissection tree. */
function LayerSection({ layer, defaultOpen }: { layer: PacketLayer; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const setFilters = useUiStore((s) => s.setFilters);
  const { t } = useI18n();

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
                const target = FILTERABLE_FIELDS[f.key.toLowerCase()];
                if (!target) {
                  return (
                    <div key={i} className="flex gap-2 px-3 py-0.5 text-[11px] hover:bg-zinc-800/30">
                      <span className="text-zinc-500 shrink-0">{f.key}</span>
                      <span className="text-zinc-200 font-mono break-all min-w-0">{f.value}</span>
                    </div>
                  );
                }
                return (
                  <div key={i} className="flex gap-2 px-3 py-0.5 text-[11px] hover:bg-zinc-800/30">
                    <span className="text-zinc-500 shrink-0">{f.key}</span>
                    <span className="group relative min-w-0">
                      <button
                        onClick={() => applyFieldFilter(target, f.value)}
                        className="text-zinc-200 font-mono break-all underline decoration-dotted decoration-zinc-500
                                   underline-offset-2 hover:text-blue-400 hover:decoration-blue-400
                                   transition-colors active:scale-95 text-left"
                      >
                        {f.value}
                      </button>
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

/** Right sidebar: full packet dissection tree + hex dump + show on graph. */
export function PacketDetails({ sessionId }: PacketDetailsProps) {
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const selectedPacketStream = useUiStore((s) => s.selectedPacketStream);
  const setSelectedPacket = useUiStore((s) => s.setSelectedPacket);
  const setSelectedNode = useUiStore((s) => s.setSelectedNode);
  const setSelectedEdge = useUiStore((s) => s.setSelectedEdge);
  const setMainView = useUiStore((s) => s.setMainView);
  const setFollowedStream = useUiStore((s) => s.setFollowedStream);
  const followedStream = useUiStore((s) => s.followedStream);
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

  const handleShowOnGraph = () => {
    if (!detail) return;
    // Find the packet's source node in the topology and select it.
    // The layers summary contains "Src: x.x.x.x" / srcIp style data; use frame + IP layers.
    const ipLayer = detail.layers.find((l) => /Internet Protocol/i.test(l.name));
    const srcField = ipLayer?.fields.find((f) => /source address/i.test(f.key));
    const srcIp = srcField?.value.split(" ")[0];
    setMainView("graph");
    setSelectedPacket(null);
    if (srcIp) setSelectedNode(srcIp);
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
            {/* Show on graph + Follow TCP stream */}
            <div className="p-3 space-y-2 border-b border-zinc-800">
              <button
                onClick={handleShowOnGraph}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-all active:scale-[0.97]"
              >
                <Workflow className="h-3.5 w-3.5" />
                Show on Graph
              </button>

              {selectedPacketStream != null && (
                <button
                  onClick={() =>
                    setFollowedStream(
                      followedStream === selectedPacketStream ? null : selectedPacketStream,
                    )
                  }
                  className={cn(
                    "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]",
                    followedStream === selectedPacketStream
                      ? "bg-blue-600 text-white hover:bg-blue-500"
                      : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
                  )}
                >
                  {followedStream === selectedPacketStream ? (
                    <>
                      <Link2Off className="h-3.5 w-3.5" />
                      Stop Following Stream {selectedPacketStream}
                    </>
                  ) : (
                    <>
                      <Link2 className="h-3.5 w-3.5" />
                      Follow TCP Stream {selectedPacketStream}
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Dissection tree */}
            <div>
              <div className="px-3 py-2 text-[11px] font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800/50">
                Protocol Dissection
              </div>
              {detail.layers.map((layer, i) => (
                <LayerSection key={i} layer={layer} defaultOpen={i === detail.layers.length - 1} />
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
