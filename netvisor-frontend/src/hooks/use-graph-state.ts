import { useMemo } from "react";
import { useUiStore } from "@/stores/ui.store";
import type { TopologyResponse } from "@/types/network.types";

/**
 * Derives filtered graph elements and selection state from a topology response.
 *
 * Reads protocol, packet-count, and node isolation filters from the Zustand UI store,
 * applies them to the topology nodes, and prunes orphaned edges.
 * Also resolves the currently selected node/edge objects by ID.
 *
 * @param topology - The full topology response from the backend, or `undefined` if not loaded.
 * @returns Filtered elements, selected node/edge, and available protocols from the data.
 */
export function useGraphState(topology: TopologyResponse | undefined) {
  const filters = useUiStore((s) => s.filters);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectedEdgeId = useUiStore((s) => s.selectedEdgeId);

  // Extract all unique protocols from the topology data
  const availableProtocols = useMemo(() => {
    if (!topology) return [];
    const protoSet = new Set<string>();
    for (const node of topology.elements.nodes) {
      for (const p of node.data.protocols ?? []) {
        protoSet.add(p);
      }
    }
    for (const edge of topology.elements.edges) {
      for (const p of edge.data.protocols ?? []) {
        protoSet.add(p);
      }
    }
    return [...protoSet].sort();
  }, [topology]);

  // Find max packet count for slider range
  // (kept for potential future use; not used by current filters)
  const maxPacketCount = useMemo(() => {
    if (!topology) return 0;
    let max = 0;
    for (const node of topology.elements.nodes) {
      if (node.data.totalPackets > max) max = node.data.totalPackets;
    }
    return max;
  }, [topology]);

  const filteredElements = useMemo(() => {
    if (!topology) return { nodes: [], edges: [] };

    let nodes = topology.elements.nodes;
    let edges = topology.elements.edges;

    // Protocol filters. Wireshark semantics:
    // - include list → node kept if it uses at least one INCLUDED protocol
    // - exclude list → node hidden only if EVERY protocol it uses is excluded
    //   (a node doing dns+tls survives excluding dns — it still has tls)
    // - include wins when both are set (node has included traffic)
    const hasInclude = filters.protocols.length > 0;
    const hasExclude = filters.excludedProtocols.length > 0;
    if (hasInclude || hasExclude) {
      const keepNode = (protocols: string[]) =>
        hasInclude
          ? protocols.some((p) => filters.protocols.includes(p))
          : protocols.some((p) => !filters.excludedProtocols.includes(p));
      nodes = nodes.filter((n) => keepNode(n.data.protocols ?? []));
    }

    // Prune edges that reference removed nodes
    const nodeIds = new Set(nodes.map((n) => n.data.id));
    edges = edges.filter(
      (e) => nodeIds.has(e.data.source) && nodeIds.has(e.data.target),
    );

    // Edge protocol filter: also filter edges by protocol
    if (hasInclude || hasExclude) {
      const keepEdge = (protocols: string[]) =>
        hasInclude
          ? protocols.some((p) => filters.protocols.includes(p))
          : protocols.some((p) => !filters.excludedProtocols.includes(p));
      edges = edges.filter((e) => keepEdge(e.data.protocols ?? []));
      // Re-prune nodes that lost all edges after edge filtering (keep isolated node)
      const edgeNodeIds = new Set<string>();
      for (const e of edges) {
        edgeNodeIds.add(e.data.source);
        edgeNodeIds.add(e.data.target);
      }
      nodes = nodes.filter((n) => edgeNodeIds.has(n.data.id));
    }

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

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.protocols.length > 0 || filters.excludedProtocols.length > 0) count++;
    if (filters.ip) count++;
    if (filters.srcIp) count++;
    if (filters.dstIp) count++;
    if (filters.subnetScope !== "all") count++;
    if (filters.port) count++;
    if (filters.srcPort) count++;
    if (filters.dstPort) count++;
    if (filters.search) count++;
    if (filters.synOnly) count++;
    if (filters.rstOnly) count++;
    return count;
  }, [filters]);

  return {
    filteredElements,
    selectedNode,
    selectedEdge,
    availableProtocols,
    maxPacketCount,
    activeFilterCount,
  };
}