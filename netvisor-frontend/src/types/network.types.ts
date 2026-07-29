/** Classification of a network host based on its role. */
export type NodeType = "router" | "server" | "client" | "unknown";

/** Represents a single network host (node) in the topology graph. */
export interface NetworkNode {
  /** Unique identifier (typically the IP address). */
  id: string;
  /** Display label for the node. */
  label: string;
  /** Role classification of this host. */
  type: NodeType;
  /** Total number of packets sent or received by this host. */
  totalPackets: number;
  /** Total bytes transferred by this host. */
  totalBytes: number;
  /** List of protocols used by this host (e.g. "TCP", "UDP", "HTTP"). */
  protocols: string[];
}

/** Represents a connection (edge) between two network hosts. */
export interface NetworkEdge {
  /** Unique identifier for this edge. */
  id: string;
  /** ID of the source node. */
  source: string;
  /** ID of the target node. */
  target: string;
  /** Connection weight (typically packet count between the two hosts). */
  weight: number;
  /** Protocols observed on this connection. */
  protocols: string[];
  /** Total bytes transferred on this connection. */
  totalBytes: number;
  /** Total packets transferred on this connection. */
  totalPackets: number;
}

/** Aggregate statistics for an entire PCAP parsing session. */
export interface SessionStats {
  /** Total number of packets in the capture. */
  totalPackets: number;
  /** Total bytes in the capture. */
  totalBytes: number;
  /** Number of unique host IPs detected. */
  uniqueHosts: number;
  /** Map of protocol name to packet count (e.g. { "TCP": 150, "UDP": 42 }). */
  protocols: Record<string, number>;
  /** Duration of the capture in seconds. */
  duration: number;
  /** ISO 8601 timestamp of the first packet. */
  startTime: string;
  /** ISO 8601 timestamp of the last packet. */
  endTime: string;
}

/** Full response from the PCAP upload endpoint. */
export interface TopologyResponse {
  /** Unique session identifier, used as a cache key. */
  sessionId: string;
  /** Graph elements formatted for Cytoscape.js consumption. */
  elements: {
    nodes: Array<{ data: NetworkNode }>;
    edges: Array<{ data: NetworkEdge }>;
  };
  /** Aggregate statistics for the parsed capture. */
  stats: SessionStats;
}
