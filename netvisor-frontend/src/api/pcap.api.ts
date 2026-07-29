import type { TopologyResponse } from "@/types/network.types";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

/** Error thrown when the PCAP upload endpoint returns a non-2xx response. */
export class PcapUploadError extends Error {
  /** HTTP status code from the backend. */
  statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = "PcapUploadError";
    this.statusCode = statusCode;
  }
}

/**
 * Uploads a PCAP file to the backend for parsing.
 *
 * @param file - The PCAP/PCAPNG file to upload.
 * @returns The parsed topology response containing nodes, edges, and stats.
 * @throws {PcapUploadError} If the backend returns a non-2xx response.
 */
export async function uploadPcapFile(file: File): Promise<TopologyResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/pcap/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new PcapUploadError(
      response.status,
      (error as { message?: string }).message ?? "Upload failed",
    );
  }

  return response.json() as Promise<TopologyResponse>;
}
