import { cn } from "@/lib/utils";

/** Node type color legend for the network graph. */
const NODE_TYPES = [
  { type: "Router", color: "bg-amber-500" },
  { type: "Server", color: "bg-blue-500" },
  { type: "Client", color: "bg-green-500" },
  { type: "Unknown", color: "bg-gray-500" },
];

/**
 * Legend showing node type color mapping.
 * Displayed alongside the network graph.
 */
export function GraphLegend() {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
        Node Types
      </h4>
      <div className="space-y-1.5">
        {NODE_TYPES.map(({ type, color }) => (
          <div key={type} className="flex items-center gap-2">
            <div className={cn("w-3 h-3 rounded-full", color)} />
            <span className="text-xs text-zinc-400">{type}</span>
          </div>
        ))}
      </div>
      <div className="pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
          Edge Weight
        </h4>
        <p className="text-xs text-zinc-500">
          Thicker lines = more packets between hosts
        </p>
      </div>
    </div>
  );
}
