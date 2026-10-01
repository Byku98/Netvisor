import { useState } from "react";
import {
  X,
  ChevronDown,
  ChevronUp,
  Crosshair,
} from "lucide-react";
import type { NetworkNode } from "@/types/network.types";
import { useUiStore } from "@/stores/ui.store";
import { cn } from "@/lib/utils";
import { PacketFilterBar } from "./PacketFilterBar";

interface NodeDetailsProps {
  /** The selected node data. */
  node: NetworkNode;
  /** Current session ID. */
  sessionId: string;
}

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Color class for each node type. */
const TYPE_COLORS: Record<string, string> = {
  router: "bg-amber-500",
  switch: "bg-violet-500",
  server: "bg-blue-500",
  firewall: "bg-red-500",
  client: "bg-green-500",
  unknown: "bg-gray-500",
};

/** Detail panel for a selected network node with packet drill-down. */
export function NodeDetails({ node, sessionId }: NodeDetailsProps) {
  const setSelectedNode = useUiStore((s) => s.setSelectedNode);
  const setIsolatedNode = useUiStore((s) => s.setIsolatedNode);
  const isolatedNodeId = useUiStore((s) => s.filters.isolatedNodeId);
  const [expanded, setExpanded] = useState(false);

  const isIsolated = isolatedNodeId === node.id;

  return (
    <div className="h-full flex flex-col bg-zinc-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-3 h-3 rounded-full",
              TYPE_COLORS[node.type] ?? TYPE_COLORS.unknown,
            )}
          />
          <h3 className="font-semibold text-zinc-200">{node.label}</h3>
        </div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Stats */}
        <div className="p-4 space-y-3 border-b border-zinc-800">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-zinc-500">Type</p>
              <p className="text-zinc-200 capitalize">{node.type}</p>
            </div>
            <div>
              <p className="text-zinc-500">IP Address</p>
              <p className="text-zinc-200 font-mono text-xs">{node.id}</p>
            </div>
            <div>
              <p className="text-zinc-500">Packets</p>
              <p className="text-zinc-200 font-mono">
                {node.totalPackets.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-zinc-500">Bytes</p>
              <p className="text-zinc-200 font-mono">
                {formatBytes(node.totalBytes)}
              </p>
            </div>
          </div>
          <div>
            <p className="text-zinc-500 text-sm">Protocols</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {node.protocols.map((p) => (
                <span
                  key={p}
                  className="px-2 py-0.5 bg-zinc-800 text-zinc-300 text-xs rounded"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>

          {/* Isolate button */}
          <button
            onClick={() => setIsolatedNode(node.id)}
            className={cn(
              "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all",
              isIsolated
                ? "bg-amber-600 text-white hover:bg-amber-500"
                : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
            )}
          >
            <Crosshair className="h-3.5 w-3.5" />
            {isIsolated ? "Stop Isolating" : "Isolate This Node"}
          </button>
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
            <PacketFilterBar sessionId={sessionId} srcIp={node.id} />
          </div>
        )}
      </div>
    </div>
  );
}