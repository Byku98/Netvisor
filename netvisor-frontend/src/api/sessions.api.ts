import type { TopologyResponse } from "@/types/network.types";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

/** Summary of a past session. */
export interface SessionListItem {
  id: string;
  filename: string;
  totalPackets: number;
  totalBytes: number;
  uniqueHosts: number;
  durationSec: number;
  createdAt: string;
}

/** One filtered packet row (from tshark). */
export interface FilteredPacket {
  packetIndex: number;
  timestamp: number;
  timestampFormatted: string;  // HH:MM:SS.mmm
  srcIp: string;
  dstIp: string;
  srcPort: number | null;
  dstPort: number | null;
  protocol: string;
  length: number;
  info: string;
  /** TCP stream index (Follow TCP Stream), null for non-TCP. */
  stream: number | null;
}

/** Filtered packet response. */
export interface FilteredPacketsResponse {
  packets: FilteredPacket[];
  total: number;
  page: number;
  pageSize: number;
  filterApplied: string | null;
}

/** Fetch all sessions (metadata only). */
export async function fetchSessions(): Promise<SessionListItem[]> {
  const response = await fetch(`${API_BASE}/sessions`);
  if (!response.ok) throw new Error("Failed to fetch sessions");
  return response.json() as Promise<SessionListItem[]>;
}

/** Fetch full topology for one session. */
export async function fetchSessionTopology(
  sessionId: string,
): Promise<TopologyResponse> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!response.ok) throw new Error("Failed to fetch session");
  return response.json() as Promise<TopologyResponse>;
}

/** Delete a session and all its data. */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete session");
}

/** Fetch filtered packets for a session using tshark. */
export async function fetchPackets(
  sessionId: string,
  options: {
    protocol?: string;
    port?: string;
    srcPort?: string;
    dstPort?: string;
    srcIp?: string;
    dstIp?: string;
    stream?: number;
    subnet?: string;
    subnetScope?: "local" | "external";
    search?: string;
    synOnly?: boolean;
    page?: number;
    pageSize?: number;
  } = {},
): Promise<FilteredPacketsResponse> {
  const params = new URLSearchParams();
  if (options.protocol) params.set("protocol", options.protocol);
  if (options.port) params.set("port", String(options.port));
  if (options.srcPort) params.set("src_port", String(options.srcPort));
  if (options.dstPort) params.set("dst_port", String(options.dstPort));
  if (options.srcIp) params.set("src_ip", options.srcIp);
  if (options.dstIp) params.set("dst_ip", options.dstIp);
  if (options.stream != null) params.set("stream", String(options.stream));
  if (options.subnet) params.set("subnet", options.subnet);
  if (options.subnetScope) params.set("subnet_scope", options.subnetScope);
  if (options.search) params.set("search", options.search);
  if (options.synOnly) params.set("syn_only", "true");
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));

  const qs = params.toString();
  const url = `${API_BASE}/sessions/${sessionId}/packets${qs ? `?${qs}` : ""}`;

  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      (error as { detail?: string }).detail ?? "Failed to fetch packets",
    );
  }
  return response.json() as Promise<FilteredPacketsResponse>;
}

/** Endpoints of packets matching the current filters (for graph pruning). */
export interface FilteredEndpoints {
  ips: string[];
  packetCount: number;
  filterApplied: string | null;
}

/** Fetch unique endpoint IPs of packets matching the given filters. */
export async function fetchPacketEndpoints(
  sessionId: string,
  options: Parameters<typeof fetchPackets>[1] = {},
): Promise<FilteredEndpoints> {
  const params = new URLSearchParams();
  const o = options as Record<string, unknown>;
  if (o.protocol) params.set("protocol", String(o.protocol));
  if (o.port) params.set("port", String(o.port));
  if (o.srcPort) params.set("src_port", String(o.srcPort));
  if (o.dstPort) params.set("dst_port", String(o.dstPort));
  if (o.srcIp) params.set("src_ip", String(o.srcIp));
  if (o.dstIp) params.set("dst_ip", String(o.dstIp));
  if (o.stream != null) params.set("stream", String(o.stream));
  if (o.subnet) params.set("subnet", String(o.subnet));
  if (o.subnetScope) params.set("subnet_scope", String(o.subnetScope));
  if (o.search) params.set("search", String(o.search));
  if (o.synOnly) params.set("syn_only", "true");

  const qs = params.toString();
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/packets/endpoints${qs ? `?${qs}` : ""}`,
  );
  if (!response.ok) throw new Error("Failed to fetch filtered endpoints");
  return response.json() as Promise<FilteredEndpoints>;
}

/** Endpoints of a TCP stream (for graph filtering when following). */
export interface StreamEndpoints {
  stream: number;
  ips: string[];
  packetCount: number;
}

/** Fetch the unique endpoint IPs of a TCP stream. */
export async function fetchStreamEndpoints(
  sessionId: string,
  stream: number,
): Promise<StreamEndpoints> {
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/streams/${stream}/endpoints`,
  );
  if (!response.ok) throw new Error("Failed to fetch stream endpoints");
  return response.json() as Promise<StreamEndpoints>;
}

/** One parsed protocol layer from tshark -V dissection. */
export interface PacketLayer {
  /** Layer name, e.g. "Ethernet II", "Internet Protocol Version 4". */
  name: string;
  /** Full summary line from tshark. */
  summary: string;
  /** Key/value fields within the layer. */
  fields: Array<{ key: string; value: string }>;
}

/** Detailed packet response: dissection tree + raw hex. */
export interface PacketDetail {
  packetIndex: number;
  layers: PacketLayer[];
  /** Raw packet bytes as hex string (may be empty on error). */
  raw: string;
  /** Full tshark -V text output. */
  rawDissection: string;
}

/** Fetch full protocol dissection for one packet (lazy load). */
export async function fetchPacketDetail(
  sessionId: string,
  packetIndex: number,
): Promise<PacketDetail> {
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/packets/${packetIndex}/detail`,
  );
  if (!response.ok) throw new Error("Failed to fetch packet detail");
  return response.json() as Promise<PacketDetail>;
}

/** Check the packet source: tshark availability + active mode. */
export async function checkTsharkStatus(): Promise<{
  available: boolean;
  mode: "tshark" | "scapy";
}> {
  const response = await fetch(`${API_BASE}/sessions/status/tshark`);
  if (!response.ok) throw new Error("Failed to check tshark status");
  return response.json() as Promise<{ available: boolean; mode: "tshark" | "scapy" }>;
}

/** Fetch hex payload for a specific packet (lazy load). */
export async function fetchPacketPayload(
  sessionId: string,
  packetIndex: number,
): Promise<{ packetIndex: number; length: number; hex: string }> {
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/packets/${packetIndex}/payload`,
  );
  if (!response.ok) throw new Error("Failed to fetch packet payload");
  return response.json() as Promise<{
    packetIndex: number;
    length: number;
    hex: string;
  }>;
}