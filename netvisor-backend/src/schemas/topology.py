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
    elements: dict  # { nodes: [...], edges: [...] }
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


# --- Packet header (for drill-down) ---

class PacketHeader(BaseModel):
    """One row from the packets table."""

    id: int
    packetIndex: int
    timestamp: float
    srcIp: str
    dstIp: str
    srcPort: int | None
    dstPort: int | None
    protocol: str
    length: int
    info: str
    headers: dict


class PaginatedPackets(BaseModel):
    """Paginated packet list."""

    packets: list[PacketHeader]
    total: int
    page: int
    pageSize: int
