"""Build the LLM prompt context for a session (design: option B).

Always includes the session summary (hosts, device types, top edges,
protocol breakdown, stream list, duration) read from the saved topology
JSON. Question-aware focus adds node/stream detail when hints are given.
Evidence is a protocol-spanning packet sample of 15-20 formatted one-line
rows — formatted rows only, NEVER raw dumps/hex.

Token budget ~4000 (chars/4 estimate). Truncation order when over budget:
packet sample -> stream details -> edge details. The summary is never
truncated.
"""

from pathlib import Path

from src.logging import get_logger
from src.services.packet_source import filter_packets, get_stream_endpoints
from src.services.topology import load_topology

log = get_logger("context_builder")

TOKEN_BUDGET = 4000
CHARS_PER_TOKEN = 4
SAMPLE_SIZE = 18  # within the 15-20 row target
MAX_TOP_EDGES = 15
MAX_STREAMS = 10

SYSTEM_PROMPT = (
    "You are NetVisor's AI Traffic Assistant, a network-analysis expert. "
    "You answer ONLY questions about the packet capture and network "
    "topology provided in the context. Interpret protocols, flows, TCP "
    "streams, latency patterns, device roles and anomalies. If a question "
    "is off-topic (not about the capture or networking), refuse briefly in "
    "one sentence and offer a capture-related question instead. Answer in "
    "concise Markdown. Cite concrete evidence from the context (hosts, "
    "edges, streams, packet rows) when supporting a claim. If the context "
    "does not contain the answer, say so plainly instead of guessing."
)


def _fmt_row(row: dict) -> str:
    """One formatted packet row — no hex, no raw dumps."""
    ports = ""
    if row.get("srcPort") is not None and row.get("dstPort") is not None:
        ports = f":{row['srcPort']} -> {row['dstIp']}:{row['dstPort']}"
    stream = row.get("stream")
    stream_s = f" stream={stream}" if stream is not None else ""
    return (
        f"#{row['packetIndex']} {row['timestampFormatted']} "
        f"{row['srcIp']}{ports} [{row['protocol']}] "
        f"{row['length']}B {row['info']}{stream_s}"
    )


def _protocol_spanning_sample(packets: list[dict], size: int) -> list[dict]:
    """Pick rows spanning distinct protocols first, then fill by order."""
    by_proto: dict[str, dict] = {}
    rest: list[dict] = []
    for row in packets:
        proto = row.get("protocol", "?")
        if proto not in by_proto:
            by_proto[proto] = row
        else:
            rest.append(row)
    sample = list(by_proto.values())
    seen = {r["packetIndex"] for r in sample}
    for row in rest:
        if len(sample) >= size:
            break
        if row["packetIndex"] not in seen:
            sample.append(row)
            seen.add(row["packetIndex"])
    return sample[:size]


def build_context(
    session_id: str,
    pcap_path: Path,
    focus_node_id: str | None = None,
    focus_stream_id: int | None = None,
) -> tuple[str, list[dict]]:
    """Build (context_text, context_manifest).

    The manifest lists each included block with its approximate token
    count (chars/4) — returned to the client as the context chip data.
    """
    topology = load_topology(session_id)
    stats = topology.stats
    nodes = topology.elements.nodes
    edges = topology.elements.edges

    blocks: list[tuple[str, str]] = []  # (name, text)
    manifest: list[dict] = []

    # ── Summary (NEVER truncated) ────────────────────────────────────
    hosts = "\n".join(
        f"- {n.data.id} — type: {n.data.type}, packets: {n.data.totalPackets}, "
        f"bytes: {n.data.totalBytes}, protocols: {', '.join(n.data.protocols)}"
        for n in nodes
    )
    top_edges = sorted(edges, key=lambda e: e.data.totalPackets, reverse=True)[
        :MAX_TOP_EDGES
    ]
    edge_lines = "\n".join(
        f"- {e.data.source} -> {e.data.target}: {e.data.totalPackets} packets, "
        f"{e.data.totalBytes} bytes, protocols: {', '.join(e.data.protocols)}"
        for e in top_edges
    )
    protocols = "\n".join(f"- {k}: {v} packets" for k, v in stats.protocols.items())
    summary = (
        f"Capture file: {stats.startTime} to {stats.endTime} "
        f"(duration {stats.duration:.3f}s), {stats.totalPackets} packets, "
        f"{stats.totalBytes} bytes, {stats.uniqueHosts} unique hosts.\n\n"
        f"## Hosts\n{hosts}\n\n"
        f"## Top edges (by packets)\n{edge_lines}\n\n"
        f"## Protocol breakdown\n{protocols}"
    )
    blocks.append(("summary", summary))

    # ── Node focus ───────────────────────────────────────────────────
    if focus_node_id:
        node = next((n for n in nodes if n.data.id == focus_node_id), None)
        if node:
            node_edges = [
                e for e in edges if focus_node_id in (e.data.source, e.data.target)
            ]
            ne_lines = "\n".join(
                f"- {e.data.source} -> {e.data.target}: {e.data.totalPackets} packets, "
                f"{e.data.totalBytes} bytes, protocols: {', '.join(e.data.protocols)}"
                for e in node_edges
            )
            blocks.append((
                "node_detail",
                f"Focused node {node.data.id} (type: {node.data.type}, "
                f"packets: {node.data.totalPackets}, bytes: {node.data.totalBytes}, "
                f"protocols: {', '.join(node.data.protocols)})\n\n"
                f"Edges involving it:\n{ne_lines}",
            ))

    # ── Stream focus ─────────────────────────────────────────────────
    if focus_stream_id is not None:
        try:
            eps = get_stream_endpoints(pcap_path, focus_stream_id)
            blocks.append((
                "stream_detail",
                f"TCP stream {focus_stream_id}: {eps['packetCount']} packets "
                f"between {', '.join(eps['ips'])}",
            ))
        except Exception as e:  # noqa: BLE001 — stream detail is best-effort
            log.warning("Stream detail failed for stream %s: %s", focus_stream_id, e)

    # ── Packet sample (truncatable) ──────────────────────────────────
    try:
        result = filter_packets(pcap_path, page=1, page_size=1000)
        sample = _protocol_spanning_sample(result["packets"], SAMPLE_SIZE)
        sample_text = "## Packet sample (protocol-spanning)\n" + "\n".join(
            _fmt_row(r) for r in sample
        )
        blocks.append(("packet_sample", sample_text))
    except Exception as e:  # noqa: BLE001 — sample is best-effort
        log.warning("Packet sample failed for session %s: %s", session_id, e)

    # ── Budget enforcement ───────────────────────────────────────────
    # Truncation order: packet_sample -> stream_detail -> node_detail
    # (edge details live inside node_detail/summary). Summary is never
    # truncated. Drop whole blocks while over budget; hard-trim the
    # packet sample as a last resort.
    drop_order = ["packet_sample", "stream_detail", "node_detail"]
    kept = list(blocks)
    while _total_chars(kept) > TOKEN_BUDGET * CHARS_PER_TOKEN and kept:
        for name in reversed(drop_order):
            idx = next((i for i, (n, _) in enumerate(kept) if n == name), None)
            if idx is not None:
                kept.pop(idx)
                break
        else:
            break  # only summary left — never truncated
    # If still over budget with only summary + non-droppable, hard-trim
    # the packet sample text as a last resort.
    if _total_chars(kept) > TOKEN_BUDGET * CHARS_PER_TOKEN:
        kept = [
            (n, t[: TOKEN_BUDGET * CHARS_PER_TOKEN] if n == "packet_sample" else t)
            for n, t in kept
        ]

    context_text = "\n\n".join(t for _, t in kept)
    for name, text in kept:
        manifest.append({"name": name, "approxTokens": len(text) // CHARS_PER_TOKEN})
    return context_text, manifest


def _total_chars(blocks: list[tuple[str, str]]) -> int:
    return sum(len(t) for _, t in blocks)
