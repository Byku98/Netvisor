/** Generic collection of Cytoscape-compatible node and edge elements. */
export interface CytoscapeElements {
  nodes: Array<{ data: Record<string, unknown> }>;
  edges: Array<{ data: Record<string, unknown> }>;
}

/** Data shape for a Cytoscape graph node. */
export interface CytoscapeNodeData {
  /** Unique node identifier. */
  id: string;
  /** Display label. */
  label: string;
  /** Node type (e.g. "router", "server", "client"). */
  type: string;
  /** Total packets associated with this node. */
  totalPackets: number;
  /** Total bytes associated with this node. */
  totalBytes: number;
  /** Protocols used by this node. */
  protocols: string[];
}

/** Data shape for a Cytoscape graph edge. */
export interface CytoscapeEdgeData {
  /** Unique edge identifier. */
  id: string;
  /** Source node ID. */
  source: string;
  /** Target node ID. */
  target: string;
  /** Edge weight (packet count between hosts). */
  weight: number;
  /** Protocols observed on this edge. */
  protocols: string[];
  /** Total bytes on this edge. */
  totalBytes: number;
  /** Total packets on this edge. */
  totalPackets: number;
}
