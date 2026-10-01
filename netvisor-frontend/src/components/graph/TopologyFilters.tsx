import { useMemo } from "react";
import { Filter, RotateCcw, Crosshair, Check } from "lucide-react";
import { useUiStore } from "@/stores/ui.store";
import { cn } from "@/lib/utils";

/** Color mapping for known protocols. */
const PROTOCOL_COLORS: Record<string, { bg: string; active: string; text: string }> = {
  TCP:   { bg: "bg-blue-900/40",   active: "bg-blue-600",   text: "text-blue-300"   },
  UDP:   { bg: "bg-purple-900/40", active: "bg-purple-600", text: "text-purple-300" },
  HTTP:  { bg: "bg-green-900/40",  active: "bg-green-600",  text: "text-green-300"  },
  HTTPS: { bg: "bg-emerald-900/40", active: "bg-emerald-600", text: "text-emerald-300" },
  TLS:   { bg: "bg-emerald-900/40", active: "bg-emerald-600", text: "text-emerald-300" },
  DNS:   { bg: "bg-yellow-900/40", active: "bg-yellow-600", text: "text-yellow-300" },
  ICMP:  { bg: "bg-orange-900/40", active: "bg-orange-600", text: "text-orange-300" },
  ARP:   { bg: "bg-pink-900/40",   active: "bg-pink-600",   text: "text-pink-300"   },
  SSH:   { bg: "bg-cyan-900/40",   active: "bg-cyan-600",   text: "text-cyan-300"   },
  FTP:   { bg: "bg-rose-900/40",   active: "bg-rose-600",   text: "text-rose-300"   },
  SMTP:  { bg: "bg-indigo-900/40", active: "bg-indigo-600", text: "text-indigo-300" },
  DHCP:  { bg: "bg-teal-900/40",   active: "bg-teal-600",   text: "text-teal-300"   },
  OTHER: { bg: "bg-zinc-800",      active: "bg-zinc-600",   text: "text-zinc-300"   },
};

function getProtocolStyle(proto: string) {
  return PROTOCOL_COLORS[proto.toUpperCase()] ?? PROTOCOL_COLORS.OTHER;
}

interface TopologyFiltersProps {
  /** All unique protocols found in the current topology. */
  availableProtocols: string[];
  /** Max packet count in the dataset (for slider range). */
  maxPacketCount: number;
}

/**
 * Topology filter panel — protocol toggles, min-packets slider, quick actions.
 * Gen Z / Alpha friendly: big buttons, visual feedback, no raw expressions.
 */
export function TopologyFilters({
  availableProtocols,
  maxPacketCount,
}: TopologyFiltersProps) {
  const filters = useUiStore((s) => s.filters);
  const toggleProtocol = useUiStore((s) => s.toggleProtocol);
  const setFilters = useUiStore((s) => s.setFilters);
  const setIsolatedNode = useUiStore((s) => s.setIsolatedNode);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);

  const hasActiveFilters = filters.protocols.length > 0 || filters.minPackets > 0 || filters.isolatedNodeId;

  // Compute a nice slider step based on max value
  const sliderStep = useMemo(() => {
    if (maxPacketCount <= 100) return 1;
    if (maxPacketCount <= 1000) return 10;
    if (maxPacketCount <= 10000) return 100;
    return 1000;
  }, [maxPacketCount]);

  // Empty state: no protocols
  if (availableProtocols.length === 0) {
    return (
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          Filters
        </h4>
        <p className="text-xs text-zinc-500">Load a PCAP to enable filters</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          Filters
          {hasActiveFilters && (
            <span className="ml-1 px-1.5 py-0.5 bg-blue-600 text-white text-[10px] rounded-full font-bold">
              {(filters.protocols.length > 0 ? 1 : 0) +
                (filters.minPackets > 0 ? 1 : 0) +
                (filters.isolatedNodeId ? 1 : 0)}
            </span>
          )}
        </h4>
      </div>

      {/* Protocol toggles */}
      <div className="space-y-2">
        <p className="text-[11px] text-zinc-500 uppercase tracking-wider">Protocols</p>
        <div className="flex flex-wrap gap-1.5">
          {availableProtocols.map((proto) => {
            const style = getProtocolStyle(proto);
            const isActive = filters.protocols.includes(proto);
            return (
              <button
                key={proto}
                onClick={() => toggleProtocol(proto)}
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                  isActive
                    ? [style.active, "text-white shadow-lg"]
                    : [style.bg, style.text, "hover:brightness-125"],
                )}
              >
                {isActive && <Check className="h-3 w-3" />}
                {proto}
              </button>
            );
          })}
        </div>
      </div>

      {/* Min packets slider */}
      {maxPacketCount > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-zinc-500 uppercase tracking-wider">
              Min Packets
            </p>
            <span className="text-xs text-zinc-300 font-mono">
              {filters.minPackets > 0 ? `>= ${filters.minPackets}` : "All"}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={maxPacketCount}
            step={sliderStep}
            value={filters.minPackets}
            onChange={(e) => setFilters({ minPackets: Number(e.target.value) })}
            className="w-full h-1.5 bg-zinc-700 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none
                       [&::-webkit-slider-thumb]:w-3.5
                       [&::-webkit-slider-thumb]:h-3.5
                       [&::-webkit-slider-thumb]:rounded-full
                       [&::-webkit-slider-thumb]:bg-blue-500
                       [&::-webkit-slider-thumb]:hover:bg-blue-400
                       [&::-webkit-slider-thumb]:transition-colors
                       [&::-webkit-slider-thumb]:shadow-lg"
          />
          <div className="flex justify-between text-[10px] text-zinc-600">
            <span>0</span>
            <span>{maxPacketCount.toLocaleString()}</span>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="space-y-1.5 pt-1">
        {/* Isolate selected node */}
        <button
          onClick={() => {
            if (selectedNodeId) {
              setIsolatedNode(selectedNodeId);
            }
          }}
          disabled={!selectedNodeId}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all",
            filters.isolatedNodeId
              ? "bg-amber-600 text-white hover:bg-amber-500"
              : selectedNodeId
                ? "bg-zinc-800 text-zinc-200 hover:bg-zinc-700"
                : "bg-zinc-800/50 text-zinc-500 cursor-not-allowed",
          )}
        >
          <Crosshair className="h-3.5 w-3.5" />
          {filters.isolatedNodeId
            ? `Isolating: ${filters.isolatedNodeId}`
            : "Isolate Selected Node"}
        </button>

        {/* Reset filters */}
        {hasActiveFilters && (
          <button
            onClick={() =>
              setFilters({
                protocols: [],
                minPackets: 0,
                isolatedNodeId: null,
              })
            }
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium
                       bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-all"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Clear All Filters
          </button>
        )}
      </div>
    </div>
  );
}