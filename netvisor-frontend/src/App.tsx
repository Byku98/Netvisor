import { useQueryClient } from "@tanstack/react-query";
import { usePcapUpload } from "@/hooks/use-pcap-upload";
import { useGraphState } from "@/hooks/use-graph-state";
import { useUiStore } from "@/stores/ui.store";
import { useAuthStore } from "@/stores/auth.store";
import { NetworkGraph } from "@/components/graph/NetworkGraph";
import { GraphControls } from "@/components/graph/GraphControls";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { TopologyFilters } from "@/components/graph/TopologyFilters";
import { StatsPanel } from "@/components/stats/StatsPanel";
import { NodeDetails } from "@/components/details/NodeDetails";
import { EdgeDetails } from "@/components/details/EdgeDetails";
import { AppHeader } from "@/components/auth/AppHeader";
import { MySessions } from "@/components/sessions/MySessions";
import { PacketTable } from "@/components/packets/PacketTable";
import { PacketDetails } from "@/components/packets/PacketDetails";
import { DebugLogPanel } from "@/components/DebugLogPanel";
import type { TopologyResponse } from "@/types/network.types";
import { Upload, History, Clock, Trash2, Link2Off } from "lucide-react";
import { useCallback, useState, useEffect, useRef, useMemo } from "react";
import { useDropzone } from "react-dropzone";
import { cn } from "@/lib/utils";
import { fetchSessions, deleteSession, fetchSessionTopology, fetchStreamEndpoints, fetchPacketEndpoints } from "@/api/sessions.api";
import type { SessionListItem } from "@/api/sessions.api";

/** Format bytes to human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface GraphViewProps {
  /** The topology data to visualize. */
  topology: TopologyResponse;
  /** Go back to the upload screen. */
  onHome: () => void;
  /** Show My Sessions page. */
  onMySessions: () => void;
  /** Go to new session (upload screen). */
  onNewSession: () => void;
}

/**
 * Full graph visualization view.
 * Shows the network graph, controls, legend, stats, and detail panels.
 */
function GraphView({ topology, onHome, onMySessions, onNewSession }: GraphViewProps) {
  const { filteredElements, selectedNode, selectedEdge, availableProtocols } =
    useGraphState(topology);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);  const selectedEdgeId = useUiStore((s) => s.selectedEdgeId);
  const showLegend = useUiStore((s) => s.showLegend);
  const mainView = useUiStore((s) => s.mainView);
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const followedStream = useUiStore((s) => s.followedStream);
  const setFollowedStream = useUiStore((s) => s.setFollowedStream);
  const filterSrcIp = useUiStore((s) => s.filters.srcIp);
  const filterDstIp = useUiStore((s) => s.filters.dstIp);
  const filterPort = useUiStore((s) => s.filters.port);
  const filterSrcPort = useUiStore((s) => s.filters.srcPort);
  const filterDstPort = useUiStore((s) => s.filters.dstPort);
  const filterSearch = useUiStore((s) => s.filters.search);
  const synOnly = useUiStore((s) => s.filters.synOnly);
  const subnetScope = useUiStore((s) => s.filters.subnetScope);

  // ── Followed stream: fetch endpoint IPs, filter graph ────────
  const [followedIps, setFollowedIps] = useState<Set<string> | null>(null);

  useEffect(() => {
    if (followedStream == null) {
      setFollowedIps(null);
      return;
    }
    fetchStreamEndpoints(topology.sessionId, followedStream)
      .then((data) => setFollowedIps(new Set(data.ips)))
      .catch(() => setFollowedIps(null));
  }, [followedStream, topology.sessionId]);

  // ── Packet-level filters: prune graph to nodes with matching packets ──
  // ── Dominant local subnet (for Local/External filters) ───────
  const localSubnet = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of topology.elements.nodes) {
      const parts = n.data.id.split(".");
      if (parts.length === 4 && n.data.id !== "255.255.255.255" &&
          !n.data.id.startsWith(("224.")) && !n.data.id.startsWith(("239."))) {
        const prefix = parts.slice(0, 3).join(".");
        counts.set(prefix, (counts.get(prefix) ?? 0) + 1);
      }
    }
    let best: string | null = null;
    let bestCount = 0;
    for (const [prefix, count] of counts) {
      if (count > bestCount) {
        best = `${prefix}.0/24`;
        bestCount = count;
      }
    }
    return bestCount > 1 ? best : null;
  }, [topology]);

  const packetFiltersActive = !!(
    filterSrcIp ||
    filterDstIp ||
    filterPort ||
    filterSrcPort ||
    filterDstPort ||
    filterSearch ||
    synOnly ||
    subnetScope !== "all"
  );
  const [filterEndpointIps, setFilterEndpointIps] = useState<Set<string> | null>(null);

  useEffect(() => {
    if (!packetFiltersActive) {
      setFilterEndpointIps(null);
      return;
    }
    let cancelled = false;
    fetchPacketEndpoints(topology.sessionId, {
      srcIp: filterSrcIp || undefined,
      dstIp: filterDstIp || undefined,
      port: filterPort || undefined,
      srcPort: filterSrcPort || undefined,
      dstPort: filterDstPort || undefined,
      search: filterSearch || undefined,
      synOnly,
      subnet: subnetScope !== "all" ? localSubnet ?? undefined : undefined,
      subnetScope: subnetScope !== "all" ? subnetScope : undefined,
    })
      .then((data) => {
        if (!cancelled) setFilterEndpointIps(new Set(data.ips));
      })
      .catch(() => {
        if (!cancelled) setFilterEndpointIps(null);
      });
    return () => {
      cancelled = true;
    };
  }, [packetFiltersActive, filterSrcIp, filterDstIp, filterPort, filterSrcPort, filterDstPort, filterSearch, synOnly, subnetScope, localSubnet, topology.sessionId]);

  const streamElements = useMemo(() => {
    // Intersect: followed stream ∪/∩ packet-filter endpoints (whichever active)
    const allowed =
      followedIps && filterEndpointIps
        ? new Set([...followedIps].filter((x) => filterEndpointIps.has(x)))
        : followedIps ?? filterEndpointIps;
    if (!allowed) return filteredElements;
    const nodes = filteredElements.nodes.filter((n) => allowed.has(n.data.id));
    const ids = new Set(nodes.map((n) => n.data.id));
    const edges = filteredElements.edges.filter(
      (e) => ids.has(e.data.source) && ids.has(e.data.target),
    );
    return { nodes, edges };
  }, [filteredElements, followedIps, filterEndpointIps]);

  // ── Resizable right sidebar ──────────────────────────────────
  const [rightWidth, setRightWidth] = useState(320);
  const isResizing = useRef(false);

  const startResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!isResizing.current) return;
      const w = window.innerWidth - e.clientX;
      setRightWidth(Math.min(640, Math.max(240, w)));
    };
    const onUp = () => {
      if (!isResizing.current) return;
      isResizing.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  const { mutate: uploadNew, isPending: isUploading } = usePcapUpload();
  const queryClient = useQueryClient();

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) {
        uploadNew(accepted[0], {
          onSuccess: (data) => {
            queryClient.setQueryData(["topology", data.sessionId], data);
          },
        });
      }
    },
    [uploadNew, queryClient],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.tcpdump.pcap": [".pcap"],
      "application/octet-stream": [".pcap", ".pcapng"],
    },
    maxFiles: 1,
    maxSize: 200 * 1024 * 1024,
    disabled: isUploading,
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div className="h-screen flex flex-col" {...getRootProps()}>
      <input {...getInputProps()} />

      {/* Drag overlay */}
      {isDragActive && (
        <div className="fixed inset-0 z-50 bg-blue-500/20 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-zinc-900 border-2 border-dashed border-blue-500 rounded-xl p-12 text-center">
            <Upload className="h-12 w-12 mx-auto mb-3 text-blue-400" />
            <p className="text-blue-300 text-lg">Drop to analyze new PCAP</p>
          </div>
        </div>
      )}

      {/* Header */}
      <AppHeader onHome={onHome} onMySessions={onMySessions} onNewSession={onNewSession}>
        <span className="text-xs text-zinc-500 mr-2 truncate max-w-xs">
          {topology.sessionId}
        </span>
        <GraphControls />
      </AppHeader>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left sidebar — Filters + Stats */}
        <aside className="w-64 border-r border-zinc-800 p-4 space-y-6 overflow-y-auto shrink-0">
          <TopologyFilters
            availableProtocols={availableProtocols}
            localSubnet={localSubnet}
          />
          <StatsPanel stats={topology.stats} />
        </aside>

        {/* Main content — graph or raw packet table */}
        <main className="flex-1 min-w-0 relative">
          {mainView === "packets" ? (
            <PacketTable sessionId={topology.sessionId} localSubnet={localSubnet} />
          ) : (
            <>
              <NetworkGraph
                topology={topology}
                elements={streamElements as unknown as { nodes: Array<{ data: Record<string, unknown> }>; edges: Array<{ data: Record<string, unknown> }> }}
              />

              {/* Floating legend panel */}
              {showLegend && (
                <div className="absolute top-4 left-4 z-30 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-lg p-4 shadow-xl w-48">
                  <GraphLegend />
                </div>
              )}

              {/* Following TCP stream banner */}
              {followedStream != null && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 bg-blue-950/90 backdrop-blur border border-blue-700 rounded-lg px-3 py-2 text-xs text-blue-300 shadow-xl">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  Following TCP Stream {followedStream}
                  <button
                    onClick={() => setFollowedStream(null)}
                    className="flex items-center gap-1 text-blue-300 hover:text-white underline"
                  >
                    <Link2Off className="h-3 w-3" />
                    Stop
                  </button>
                </div>
              )}
            </>
          )}
        </main>

        {/* Right sidebar — Details (resizable) */}
        {mainView === "packets" ? (
          <>
            <div
              onPointerDown={startResize}
              className="w-1 shrink-0 cursor-col-resize bg-zinc-800 hover:bg-blue-500 transition-colors"
              title="Drag to resize"
            />
            <aside
              style={{ width: rightWidth }}
              className="border-l border-zinc-800 shrink-0 overflow-hidden"
            >
              <PacketDetails sessionId={topology.sessionId} />
            </aside>
          </>
        ) : (
          (selectedNodeId || selectedEdgeId || selectedPacketIndex != null) && (
            <>
              <div
                onPointerDown={startResize}
                className="w-1 shrink-0 cursor-col-resize bg-zinc-800 hover:bg-blue-500 transition-colors"
                title="Drag to resize"
              />
              <aside
                style={{ width: rightWidth }}
                className="border-l border-zinc-800 shrink-0 overflow-hidden"
              >
                {selectedPacketIndex != null ? (
                  <PacketDetails sessionId={topology.sessionId} />
                ) : (
                  <>
                    {selectedNode && (
                      <NodeDetails
                        node={selectedNode.data}
                        sessionId={topology.sessionId}
                      />
                    )}
                    {selectedEdge && (
                      <EdgeDetails
                        edge={selectedEdge.data}
                        sessionId={topology.sessionId}
                      />
                    )}
                  </>
                )}
              </aside>
            </>
          )
        )}
      </div>
    </div>
  );
}

/** Root application component. Shows upload screen or graph view. */
export function App() {
  const queryClient = useQueryClient();
  const { mutate, isPending, data: uploadResult } = usePcapUpload();
  const reset = useUiStore((s) => s.reset);
  const user = useAuthStore((s) => s.user);
  const [showMySessions, setShowMySessions] = useState(false);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [activeTopology, setActiveTopology] = useState<TopologyResponse | null>(null);

  // Load all sessions on mount (only for anonymous users — logged-in use MySessions)
  useEffect(() => {
    if (!user) {
      fetchSessions()
        .then(setSessions)
        .catch(console.error);
    }
  }, [user]);

  // When upload completes, show graph
  useEffect(() => {
    if (uploadResult) {
      setActiveTopology(uploadResult);
    }
  }, [uploadResult]);

  const handleHome = useCallback(() => {
    reset();
    setActiveTopology(null);
    setShowMySessions(false);
    queryClient.removeQueries({ queryKey: ["topology"] });
    if (!user) {
      fetchSessions().then(setSessions).catch(console.error);
    }
  }, [queryClient, reset, user]);

  const handleMySessions = useCallback(() => {
    setActiveTopology(null);
    setShowMySessions(true);
  }, []);

  const handleLoadSession = useCallback(async (sessionId: string) => {
    try {
      const topology = await fetchSessionTopology(sessionId);
      setActiveTopology(topology);
      setShowMySessions(false);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  }, []);

  // Show graph view if we have topology data
  if (activeTopology) {
    return (
      <>
        <GraphView
          topology={activeTopology}
          onHome={handleHome}
          onMySessions={handleMySessions}
          onNewSession={handleHome}
        />
        <DebugLogPanel />
      </>
    );
  }

  // Show My Sessions view (logged-in users)
  if (showMySessions) {
    return (
      <>
        <MySessions
          onHome={handleHome}
          onLoadSession={handleLoadSession}
          onNewSession={handleHome}
        />
        <DebugLogPanel />
      </>
    );
  }

  // Upload screen
  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Delete this session?")) return;
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader
        onHome={handleHome}
        onMySessions={user ? handleMySessions : undefined}
        onNewSession={user ? handleHome : undefined}
      />

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-2xl w-full space-y-8">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-bold tracking-tight">
              Network Topology Visualization
            </h2>
            <p className="text-zinc-400">
              Upload a PCAP file to generate an interactive network map
            </p>
          </div>

          <FileDropzoneWithUpload onUpload={mutate} isPending={isPending} />

          <div className="flex justify-center gap-6 text-sm text-zinc-500">
            <span>PCAP / PCAPNG</span>
            <span>&bull;</span>
            <span>IPv4 + IPv6</span>
            <span>&bull;</span>
            <span>Up to 200 MB</span>
          </div>

          {/* Past Sessions — anonymous users only (logged-in users use MySessions) */}
          {!user && sessions.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-zinc-400">
                <History className="h-4 w-4" />
                <span className="text-sm font-medium">Past Sessions</span>
                <span className="text-xs text-zinc-600">({sessions.length})</span>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between gap-3 p-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg hover:border-zinc-600 transition-colors group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                        <span className="text-sm text-zinc-200 truncate">{s.filename}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                        <span>{s.totalPackets.toLocaleString()} pkts</span>
                        <span>{formatBytes(s.totalBytes)}</span>
                        <span>{s.uniqueHosts} hosts</span>
                        <span>{new Date(s.createdAt).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleLoadSession(s.id)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleDeleteSession(s.id)}
                        className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-6 py-3 flex items-center justify-center gap-4 text-sm text-zinc-500">
        <span>NetVisor &mdash; Interactive network topology visualization from PCAP files</span>
      </footer>

      <DebugLogPanel />
    </div>
  );
}

/** File dropzone with upload handler. */
function FileDropzoneWithUpload({
  onUpload,
  isPending,
}: {
  onUpload: (file: File) => void;
  isPending: boolean;
}) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) onUpload(accepted[0]);
    },
    [onUpload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.tcpdump.pcap": [".pcap"],
      "application/octet-stream": [".pcap", ".pcapng"],
    },
    maxFiles: 1,
    maxSize: 200 * 1024 * 1024,
    disabled: isPending,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors",
        isDragActive
          ? "border-blue-500 bg-blue-500/10"
          : "border-zinc-700 hover:border-zinc-500",
        isPending && "opacity-50 cursor-not-allowed",
      )}
    >
      <input {...getInputProps()} />
      {isPending ? (
        <div className="flex items-center justify-center gap-2">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent" />
          <span className="text-zinc-300">Parsing PCAP file...</span>
        </div>
      ) : isDragActive ? (
        <p className="text-blue-400 text-lg">Drop the file here...</p>
      ) : (
        <div>
          <Upload className="h-12 w-12 mx-auto mb-3 text-zinc-500" />
          <p className="text-zinc-300 text-lg">
            Drag &amp; drop a .pcap / .pcapng file
          </p>
          <p className="text-sm text-zinc-500 mt-1">
            or click to select (max 200 MB)
          </p>
        </div>
      )}
    </div>
  );
}