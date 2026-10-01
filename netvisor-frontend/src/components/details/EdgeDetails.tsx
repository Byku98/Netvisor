import { useState } from "react";
import { X, ChevronDown, ChevronUp } from "lucide-react";
import type { NetworkEdge } from "@/types/network.types";
import { useUiStore } from "@/stores/ui.store";
import { PacketFilterBar } from "./PacketFilterBar";

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

/** Detail panel for a selected network edge with packet drill-down. */
export function EdgeDetails({ edge, sessionId }: EdgeDetailsProps) {
  const setSelectedEdge = useUiStore((s) => s.setSelectedEdge);
  const [expanded, setExpanded] = useState(false);

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
          <span>Packets</span>
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {/* Packet list with filters */}
        {expanded && (
          <div className="border-t border-zinc-800">
            <PacketFilterBar
              sessionId={sessionId}
              srcIp={edge.source}
              dstIp={edge.target}
            />
          </div>
        )}
      </div>
    </div>
  );
}