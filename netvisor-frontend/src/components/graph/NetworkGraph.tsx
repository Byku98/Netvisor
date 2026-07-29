import type { CytoscapeElements } from "@/types/cytoscape.types";

interface NetworkGraphProps {
  /** Cytoscape-compatible node and edge elements. */
  elements: CytoscapeElements;
  /** Called when a graph node is clicked. */
  onNodeSelect: (nodeId: string) => void;
  /** Called when a graph edge is clicked. */
  onEdgeSelect: (edgeId: string) => void;
}

/**
 * Renders the interactive network graph using Cytoscape.js.
 * Currently a placeholder — Cytoscape integration is pending.
 */
export function NetworkGraph({
  elements,
  onNodeSelect: _onNodeSelect,
  onEdgeSelect: _onEdgeSelect,
}: NetworkGraphProps) {
  return (
    <div className="w-full h-full flex items-center justify-center text-zinc-500">
      <p>
        Network graph &mdash; {elements.nodes.length} nodes,{" "}
        {elements.edges.length} edges
      </p>
    </div>
  );
}
