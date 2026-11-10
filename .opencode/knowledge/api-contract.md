# NetVisor — API Contract + Filter Semantics (ground truth)

REST API (all under the API base: `/api` local, `/backend/api` prod):

- `GET  /api/config` — public runtime config: googleClientId, maxUploadBytes
- `POST /api/pcap/upload` — multipart file; 413 over limit; dedup by SHA256
  (same checksum+owner returns the EXISTING session — cached topology JSON!)
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
- page, page_size

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
