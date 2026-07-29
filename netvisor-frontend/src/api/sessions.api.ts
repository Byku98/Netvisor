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

/** One packet header row. */
export interface PacketHeader {
  id: number;
  packetIndex: number;
  timestamp: number;
  srcIp: string;
  dstIp: string;
  srcPort: number | null;
  dstPort: number | null;
  protocol: string;
  length: number;
  info: string;
  headers: Record<string, unknown>;
}

/** Paginated packet response. */
export interface PaginatedPackets {
  packets: PacketHeader[];
  total: number;
  page: number;
  pageSize: number;
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

/** Fetch paginated packet headers for a session. */
export async function fetchPackets(
  sessionId: string,
  options: { srcIp?: string; dstIp?: string; page?: number; pageSize?: number } = {},
): Promise<PaginatedPackets> {
  const params = new URLSearchParams();
  if (options.srcIp) params.set("src_ip", options.srcIp);
  if (options.dstIp) params.set("dst_ip", options.dstIp);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));

  const qs = params.toString();
  const url = `${API_BASE}/sessions/${sessionId}/packets${qs ? `?${qs}` : ""}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch packets");
  return response.json() as Promise<PaginatedPackets>;
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
  return response.json() as Promise<{ packetIndex: number; length: number; hex: string }>;
}
