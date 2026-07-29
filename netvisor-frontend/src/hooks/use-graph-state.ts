import { useMemo } from "react";
import { useUiStore } from "@/stores/ui.store";
import type { TopologyResponse } from "@/types/network.types";

/**
 * Derives filtered graph elements and selection state from a topology response.
 *
 * Reads protocol and packet-count filters from the Zustand UI store,
 * applies them to the topology nodes, and prunes orphaned edges.
 * Also resolves the currently selected node/edge objects by ID.
 *
 * @param topology - The full topology response from the backend, or `undefined` if not loaded.
 * @returns Filtered elements and the currently selected node/edge (if any).
 */
export function useGraphState(topology: TopologyResponse | undefined) {
  const filters = useUiStore((s) => s.filters);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectedEdgeId = useUiStore((s) => s.selectedEdgeId);

  const filteredElements = useMemo(() => {
    if (!topology) return { nodes: [], edges: [] };

    let nodes = topology.elements.nodes;
    let edges = topology.elements.edges;

    if (filters.protocols.length > 0) {
      nodes = nodes.filter((n) =>
        n.data.protocols.some((p) => filters.protocols.includes(p)),
      );
    }

    if (filters.minPackets > 0) {
      nodes = nodes.filter((n) => n.data.totalPackets >= filters.minPackets);
    }

    const nodeIds = new Set(nodes.map((n) => n.data.id));
    edges = edges.filter(
      (e) => nodeIds.has(e.data.source) && nodeIds.has(e.data.target),
    );

    return { nodes, edges };
  }, [topology, filters]);

  const selectedNode = useMemo(() => {
    if (!topology || !selectedNodeId) return null;
    return (
      topology.elements.nodes.find((n) => n.data.id === selectedNodeId) ?? null
    );
  }, [topology, selectedNodeId]);

  const selectedEdge = useMemo(() => {
    if (!topology || !selectedEdgeId) return null;
    return (
      topology.elements.edges.find((e) => e.data.id === selectedEdgeId) ?? null
    );
  }, [topology, selectedEdgeId]);

  return {
    filteredElements,
    selectedNode,
    selectedEdge,
  };
}
