import type { ChecksumLookupItem, TopologyResponse } from "@/types/network.types";

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

/** One file to upload — `name` is the multipart filename (may be user-renamed). */
export interface UploadFile {
  file: File;
  name: string;
}

/**
 * Uploads one or more PCAP/PCAPNG files to the backend for parsing.
 *
 * All parts share the field name `files` (repeated multipart field, matching
 * the backend's `files: list[UploadFile]`). `label` is the optional session
 * name for logged-in users; it is omitted entirely for anonymous uploads so
 * the server auto-labels the session. A single-file upload behaves exactly
 * as the legacy single-file endpoint did.
 *
 * @returns The parsed topology response containing nodes, edges, and stats.
 * @throws {PcapUploadError} If the backend returns a non-2xx response
 *   (400 invalid/duplicate file, 413 over limits — `message` carries the
 *   backend `detail`, which names the offending file when there is one).
 */
export async function uploadPcapFiles(
  files: UploadFile[],
  label?: string,
): Promise<TopologyResponse> {
  const formData = new FormData();
  for (const { file, name } of files) {
    formData.append("files", file, name);
  }
  if (label) {
    formData.append("label", label);
  }

  const response = await fetch(`${API_BASE}/pcap/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const err = error as { detail?: string; message?: string };
    throw new PcapUploadError(
      response.status,
      err.detail ?? err.message ?? "Upload failed",
    );
  }

  return response.json() as Promise<TopologyResponse>;
}

/** Backend caps one checksum lookup request at 20 entries. */
const CHECKSUM_CHUNK_SIZE = 20;

/**
 * Batch lookup: which of these SHA-256 checksums already belong to one of the
 * caller's own sessions? The returned array is aligned by index to the input.
 *
 * Defensive against older backends: a 404 (endpoint does not exist yet) or
 * any other failure returns null — the caller keeps the files and skips the
 * ownership check silently.
 */
export async function lookupOwnedChecksums(
  checksums: string[],
): Promise<ChecksumLookupItem[] | null> {
  if (checksums.length === 0) return [];
  const results: ChecksumLookupItem[] = [];
  for (let i = 0; i < checksums.length; i += CHECKSUM_CHUNK_SIZE) {
    const chunk = checksums.slice(i, i + CHECKSUM_CHUNK_SIZE);
    try {
      const response = await fetch(`${API_BASE}/pcap/checksums`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checksums: chunk }),
      });
      if (response.status === 404) return null; // older backend — skip silently
      if (!response.ok) {
        console.warn(`Checksum lookup failed with status ${response.status}`);
        return null;
      }
      const data = (await response.json()) as unknown;
      if (!Array.isArray(data) || data.length !== chunk.length) return null;
      results.push(...(data as ChecksumLookupItem[]));
    } catch {
      return null;
    }
  }
  return results;
}
