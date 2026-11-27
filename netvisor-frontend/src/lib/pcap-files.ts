/**
 * Local PCAP file checks for the multi-file upload flow — all client-side,
 * no network: extension, magic bytes, SHA-256. The server remains the real
 * validation gate (deep parse happens after upload).
 */

/** Extensions accepted for upload. */
const PCAP_EXTENSIONS = [".pcap", ".pcapng"];

/** Magic byte sequences: pcap (microsecond + nanosecond variants, both
 *  endiannesses) and pcapng. */
const PCAP_MAGICS: number[][] = [
  [0xa1, 0xb2, 0xc3, 0xd4], // pcap, big-endian
  [0xd4, 0xc3, 0xb2, 0xa1], // pcap, little-endian
  [0xa1, 0xb2, 0x3c, 0x4d], // pcap nanosecond, big-endian
  [0x4d, 0x3c, 0xb2, 0xa1], // pcap nanosecond, little-endian
  [0x0a, 0x0d, 0x0d, 0x0a], // pcapng
];

/** True when the file name has a pcap/pcapng extension (case-insensitive). */
export function hasPcapExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return PCAP_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

/**
 * Reads the first 4 bytes locally (File.slice, no network) and checks them
 * against the pcap/pcapng magic numbers.
 */
export async function hasPcapMagic(file: File): Promise<boolean> {
  const header = new Uint8Array(await file.slice(0, 4).arrayBuffer());
  if (header.length < 4) return false;
  return PCAP_MAGICS.some((magic) =>
    magic.every((byte, i) => header[i] === byte),
  );
}

/**
 * SHA-256 of the file contents as lowercase hex — the key for the batch
 * duplicate/ownership lookup. Returns null when crypto.subtle is unavailable
 * (non-secure context) or hashing fails; the upload then simply skips the
 * checksum lookup.
 */
export async function sha256Hex(file: File): Promise<string | null> {
  if (!globalThis.crypto?.subtle) return null;
  try {
    const digest = await crypto.subtle.digest(
      "SHA-256",
      await file.arrayBuffer(),
    );
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return null;
  }
}
