import {
  X,
  List,
} from "lucide-react";
import type { NetworkNode } from "@/types/network.types";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";
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
  const setFilters = useUiStore((s) => s.setFilters);
  const setProtoMode = useUiStore((s) => s.setProtoMode);
  const filters = useUiStore((s) => s.filters);
  const { t } = useI18n();

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
            <span className="group relative inline-block">
              <button
                onClick={() => setFilters({ ip: node.id, srcIp: "", dstIp: "" })}
                className="text-zinc-200 font-mono text-xs underline decoration-dotted decoration-zinc-500
                           underline-offset-2 hover:text-blue-400 hover:decoration-blue-400
                           transition-colors active:scale-95"
              >
                {node.id}
              </button>
              {/* Hint appears after ~2s of hovering */}
              <span
                className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5
                           w-max max-w-44 bg-zinc-800 border border-zinc-700 text-zinc-300
                           text-[10px] leading-snug rounded px-2 py-1 shadow-lg z-50
                           opacity-0 group-hover:opacity-100 transition-opacity
                           delay-[1800ms] duration-200"
              >
                {t("clickToFilterIp")}
              </span>
            </span>
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
            {node.protocols.map((p) => {
              const isOnlyFilter =
                filters.protocols.length === 1 && filters.protocols.includes(p);
              return (
                <span key={p} className="group relative inline-block">
                  <button
                    onClick={() => {
                      if (isOnlyFilter) {
                        // clicking the active one clears the protocol filter
                        setFilters({ protocols: [], excludedProtocols: [] });
                        setProtoMode("all");
                      } else {
                        setFilters({ protocols: [p], excludedProtocols: [] });
                        setProtoMode("include");
                      }
                    }}
                    className={cn(
                      "px-2 py-0.5 text-xs rounded transition-colors active:scale-95",
                      isOnlyFilter
                        ? "bg-blue-600 text-white"
                        : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
                    )}
                  >
                    {p}
                  </button>
                  {/* Hint appears after ~2s of hovering */}
                  <span
                    className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5
                               w-max max-w-44 bg-zinc-800 border border-zinc-700 text-zinc-300
                               text-[10px] leading-snug rounded px-2 py-1 shadow-lg z-50
                               opacity-0 group-hover:opacity-100 transition-opacity
                               delay-[1800ms] duration-200"
                  >
                    {t("clickToFilterProto")}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
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
