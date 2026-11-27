# NetVisor — API Contract + Filter Semantics (ground truth)

REST API (all under the API base: `/api` local, `/backend/api` prod):

- `GET  /api/config` — public runtime config: googleClientId, maxUploadBytes,
  maxBundleBytes (multi-file upload bundle cap, NETVISOR_MAX_BUNDLE_BYTES,
  default 15 MB), searchFields (fields the free-text packet search matches:
  info, srcIp, dstIp, srcPort, dstPort, protocol, payloadText, hexBytes —
  FE renders the searchbar hint from it)
- `POST /api/pcap/upload` — multipart, 1..N files as repeated `files` parts
  (field name exactly `files`; FE sends one part per file) + optional
  `label` form field (logged-in users' session name; anonymous omit it —
  server auto-labels). Validation order: extensions (400 naming file) →
  per-file size vs maxUploadBytes (413 naming file) → bundle total vs
  maxBundleBytes (413) → batch-internal SHA256 duplicates (400 naming the
  duplicate) → deep parse per file, all-or-nothing (400 naming the failing
  file; nothing left on disk). N>=2 files are merged chronologically into
  ONE pcapng (mergecap, scapy PcapNgWriter fallback). Dedup by checksum:
  single file = plain SHA256 of the file; N files = ","-joined SORTED
  individual SHA256s (order-insensitive: A+B and B+A dedup to the same
  session; same checksum+owner returns the EXISTING session — cached
  topology JSON!). Session filename = `label` if provided, else auto-label
  (1 file: its own name; 2: "A + B"; >2: "A + B (+N more)" — basenames
  without extension). Anonymous retention 24h hardcoded (cookie max_age
  86400); logged-in sessions never expire.
- `POST /api/pcap/checksums` — JSON body `{checksums: ["<64 hex>", ...]}`
  (max 20 → 400 over; invalid format → 400). Owner-scoped (access_token
  user or netvisor_session cookie — same resolution as upload dedup).
  Response: array aligned with input order: `{owned: true, sessionId,
  filename}` or `{owned: false}`. NEVER reports other users' sessions —
  a checksum existing under another user is owned:false (transparency).
- `GET  /api/sessions` — owner-scoped (cookie_id or user_id)
- `GET  /api/sessions/{id}` — topology JSON (self-edges stripped at load)
- `DELETE /api/sessions/{id}`
- `GET  /api/sessions/{id}/packets?...` — filtered packets, paginated
- `GET  /api/sessions/{id}/packets/endpoints?...` — endpoint IPs for graph pruning
- `GET  /api/sessions/{id}/packets/{index}/payload` | `/detail`
- `GET  /api/sessions/{id}/tshark-status` — {available, mode: tshark|scapy}
- `POST /api/auth/register|login|google|logout`, `GET /api/auth/me`
- `GET  /api/users/me/sessions` — auth-required session list

Packet filter query params (BOTH /packets and /packets/endpoints):
- protocol, protocol_exclude (comma lists; OR within, AND across)
- port, src_port, dst_port (OR syntax: "443, 8443", "443||8443"; STRICT equality —
  443 never matches 8443; bogus input matches NOTHING, never "no filter")
- ip (either side), src_ip, dst_ip — octet-prefix semantics via parse_ip_filter():
  dotted input = CIDR prefix ("192." → 192.0.0.0/8, full IP = exact);
  bare number = ANY octet equals it ("117" matches x.x.x.117 AND 117.x.x.x)
- subnet + subnet_scope (local|external), stream, search, syn_only, rst_only
- flags (comma-separated TCP flag names: ack, psh, rst, fin, syn —
  case-insensitive, order-insensitive, deduplicated; AND semantics: a
  packet must have ALL requested flags set in its TCP layer; packets
  without a TCP layer are excluded; unknown name → 400 listing the
  valid values; empty/absent → no flag filtering)
- page, page_size
- `search` semantics (BOTH engines, shared sanitizer in
  src/services/search_terms.py): one case-insensitive substring term,
  OR across info/srcIp/dstIp/srcPort/dstPort/protocol + payload text
  (case-insensitive ASCII inside the full frame bytes) + hex bytes
  (hex syntax = `0x` prefix or `:`/`-`/space separators with even-length
  pure-hex remainder; bare words are NOT hex; invalid hex → text
  fallback; hex matches the raw byte sequence, tshark: `frame contains
  de:ad:..`, verified on 4.4.5); term is stripped of `"` `\` `^` +
  outer whitespace (WSRE cannot express a literal caret — verified on
  tshark 4.4.5); whitespace/sanitized-empty term ⇒ no filter. tshark
  3.x degrades to Info-only search (never a 500; payload/hex are 4.x
  capabilities).

Engine parity rules (tshark vs scapy — MUST stay identical):
- packet_source.py dispatches; NETVISOR_PACKET_SOURCE env/settings overrides
- IP filters match ARP protocol addresses (arp.src/dst.proto_ipv4; scapy uses
  parser psrc/pdst); self-traffic (src==dst) never becomes an edge
- Parity regressions = the recurring bug class; test BOTH engines on the SAME pcap

Cytoscape-compatible topology response: {session_id, elements:{nodes,edges},
stats} — node: id/label/type/totalPackets/totalBytes/protocols; edge:
id/source/target/weight/protocols/totalBytes/totalPackets. Frontend mirror:
netvisor-frontend/src/types/network.types.ts — KEEP IN SYNC with
netvisor-backend/src/schemas/topology.py.
