import {
  X,
  Crosshair,
  List,
} from "lucide-react";
import type { NetworkNode } from "@/types/network.types";
import { useUiStore } from "@/stores/ui.store";
import { cn } from "@/lib/utils";
import { PacketList } from "./PacketList";

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

  const isIsolated = isolatedNodeId === node.id;

  return (
    <div className="h-full flex flex-col bg-zinc-900 animate-fade-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={cn(
              "w-3 h-3 rounded-full shrink-0",
              TYPE_COLORS[node.type] ?? TYPE_COLORS.unknown,
            )}
          />
          <h3 className="font-semibold text-zinc-200 truncate">{node.label}</h3>
        </div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 active:scale-90"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Stats */}
      <div className="p-4 space-y-3 border-b border-zinc-800 shrink-0">
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
            "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]",
            isIsolated
              ? "bg-amber-600 text-white hover:bg-amber-500"
              : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
          )}
        >
          <Crosshair className="h-3.5 w-3.5" />
          {isIsolated ? "Stop Isolating" : "Isolate This Node"}
        </button>
      </div>

      {/* Packet list header */}
      <div className="flex items-center gap-2 px-3 py-2 text-[11px] font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800/50 shrink-0">
        <List className="h-3 w-3" />
        Packets
      </div>

      {/* Packet list — click a row for full dissection */}
      <div className="flex-1 overflow-y-auto">
        <PacketList sessionId={sessionId} srcIp={node.id} />
      </div>
    </div>
  );
}
