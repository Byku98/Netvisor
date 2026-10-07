"""Pydantic schemas matching the frontend TypeScript types exactly.

Frontend types: netvisor-frontend/src/types/network.types.ts
"""

from pydantic import BaseModel


# --- Node & Edge data (inside Cytoscape { data: ... } wrapper) ---

class NetworkNodeData(BaseModel):
    """Matches frontend NetworkNode interface."""

    id: str
    label: str
    type: str  # "router" | "server" | "client" | "unknown"
    totalPackets: int
    totalBytes: int
    protocols: list[str]


class NetworkEdgeData(BaseModel):
    """Matches frontend NetworkEdge interface."""

    id: str
    source: str
    target: str
    weight: int
    protocols: list[str]
    totalBytes: int
    totalPackets: int


# --- Cytoscape element wrappers ---

class CytoscapeNode(BaseModel):
    """Cytoscape node element: { data: NetworkNodeData }."""

    data: NetworkNodeData


class CytoscapeEdge(BaseModel):
    """Cytoscape edge element: { data: NetworkEdgeData }."""

    data: NetworkEdgeData


class CytoscapeElements(BaseModel):
    """Cytoscape elements container: { nodes: [...], edges: [...] }."""

    nodes: list[CytoscapeNode]
    edges: list[CytoscapeEdge]


# --- Session stats ---

class SessionStats(BaseModel):
    """Matches frontend SessionStats interface."""

    totalPackets: int
    totalBytes: int
    uniqueHosts: int
    protocols: dict[str, int]
    duration: float
    startTime: str
    endTime: str


# --- Top-level response ---

class TopologyResponse(BaseModel):
    """Matches frontend TopologyResponse interface."""

    sessionId: str
    elements: CytoscapeElements
    stats: SessionStats


# --- Session list item (lightweight) ---

class SessionListItem(BaseModel):
    """Summary of a session for the list endpoint."""

    id: str
    filename: str
    totalPackets: int
    totalBytes: int
    uniqueHosts: int
    durationSec: float
    createdAt: str


# --- Packet filtering (tshark-based) ---

class FilteredPacket(BaseModel):
    """One packet row from tshark filtering."""

    packetIndex: int
    timestamp: float
    timestampFormatted: str  # human-readable HH:MM:SS.mmm
    srcIp: str
    dstIp: str
    srcPort: int | None
    dstPort: int | None
    protocol: str
    length: int
    info: str
    stream: int | None = None  # TCP stream index (Follow TCP Stream)


class FilteredPacketsResponse(BaseModel):
    """Paginated filtered packet list from tshark."""

    packets: list[FilteredPacket]
    total: int
    page: int
    pageSize: int
    filterApplied: str | None  # the tshark display filter string used