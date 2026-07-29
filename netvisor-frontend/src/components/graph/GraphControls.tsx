import { LayoutGrid, Circle, Grid3x3, ArrowDownUp } from "lucide-react";
import { useUiStore } from "@/stores/ui.store";
import { cn } from "@/lib/utils";

const LAYOUTS = [
  { id: "cose" as const, label: "COSE", icon: LayoutGrid },
  { id: "dagre" as const, label: "Dagre", icon: ArrowDownUp },
  { id: "circle" as const, label: "Circle", icon: Circle },
  { id: "grid" as const, label: "Grid", icon: Grid3x3 },
];

/**
 * Layout switcher controls for the network graph.
 * Allows switching between COSE, Dagre, Circle, and Grid layouts.
 */
export function GraphControls() {
  const graphLayout = useUiStore((s) => s.graphLayout);
  const setGraphLayout = useUiStore((s) => s.setGraphLayout);

  return (
    <div className="flex items-center gap-1">
      <span className="text-xs text-zinc-500 mr-2">Layout:</span>
      {LAYOUTS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => setGraphLayout(id)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs transition-colors",
            graphLayout === id
              ? "bg-blue-600 text-white"
              : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200",
          )}
          title={`Switch to ${label} layout`}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}
