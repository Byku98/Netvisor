import { useQueryClient } from "@tanstack/react-query";
import { usePcapUpload } from "@/hooks/use-pcap-upload";
import { useGraphState } from "@/hooks/use-graph-state";
import { useUiStore, SIDEBAR_DEFAULT } from "@/stores/ui.store";
import { useAuthStore } from "@/stores/auth.store";
import { NetworkGraph } from "@/components/graph/NetworkGraph";
import { GraphControls } from "@/components/graph/GraphControls";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { TopologyFilters } from "@/components/graph/TopologyFilters";
import { NodeDetails } from "@/components/details/NodeDetails";
import { EdgeDetails } from "@/components/details/EdgeDetails";
import { AppHeader } from "@/components/auth/AppHeader";
import { MySessions } from "@/components/sessions/MySessions";
import { SessionRenameInput } from "@/components/sessions/SessionRenameInput";
import { PacketTable } from "@/components/packets/PacketTable";
import { PacketDetails } from "@/components/packets/PacketDetails";
import { AIAssistantPanel } from "@/components/ai/AIAssistantPanel";
import { AISettingsPage } from "@/components/ai/AISettingsPage";
import { DebugLogPanel } from "@/components/DebugLogPanel";
import { useAiStore } from "@/stores/ai.store";
import type { TopologyResponse } from "@/types/network.types";
import { Upload, History, Clock, Trash2, Share2, ArrowDownUp, BarChart3, Pencil } from "lucide-react";
import { useCallback, useState, useEffect, useRef, useMemo, type ReactNode } from "react";
import { Starfield } from "@/components/atmosphere/Starfield";
import { useDropzone, type FileRejection } from "react-dropzone";
import { useI18n } from "@/i18n";
import { useConfigStore, formatMb } from "@/stores/config.store";
import { fetchSessions, deleteSession, fetchSessionTopology, fetchPacketEndpoints, renameSession } from "@/api/sessions.api";
import type { SessionListItem } from "@/api/sessions.api";
import { UploadPanel } from "@/components/upload/UploadPanel";

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
  /** Show the full-page AI Settings. */
  onAISettings: () => void;
  /** Logout — clears auth and returns to the pristine start screen. */
  onLogout: () => void;
  /** Rename the loaded session (display label). Throws on failure so the
   *  inline editor can show the error; the caller reverts its state. */
  onRenameSession: (newName: string) => Promise<void>;
}

/**
 * Full graph visualization view.
 * Shows the network graph, controls, legend, stats, and detail panels.
 */
function GraphView({ topology, onHome, onMySessions, onNewSession, onAISettings, onLogout, onRenameSession }: GraphViewProps) {
  const { filteredElements, selectedNode, selectedEdge, availableProtocols } =
    useGraphState(topology);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);  const selectedEdgeId = useUiStore((s) => s.selectedEdgeId);
  const showLegend = useUiStore((s) => s.showLegend);
  const mainView = useUiStore((s) => s.mainView);
  const selectedPacketIndex = useUiStore((s) => s.selectedPacketIndex);
  const sidebarWidth = useUiStore((s) => s.sidebarWidth);
  const setSidebarWidth = useUiStore((s) => s.setSidebarWidth);
  const graphLayout = useUiStore((s) => s.graphLayout);
  const trafficView = useUiStore((s) => s.trafficView);
  const { t } = useI18n();
  const maxUploadBytes = useConfigStore((s) => s.maxUploadBytes);
  const user = useAuthStore((s) => s.user);
  const [renamingSession, setRenamingSession] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);
  const filterIp = useUiStore((s) => s.filters.ip);
  const filterSrcIp = useUiStore((s) => s.filters.srcIp);
  const filterDstIp = useUiStore((s) => s.filters.dstIp);
  const filterPort = useUiStore((s) => s.filters.port);
  const filterSrcPort = useUiStore((s) => s.filters.srcPort);
  const filterDstPort = useUiStore((s) => s.filters.dstPort);
  const filterSearch = useUiStore((s) => s.filters.search);
  const synOnly = useUiStore((s) => s.filters.synOnly);
  const rstOnly = useUiStore((s) => s.filters.rstOnly);
  const filterFlags = useUiStore((s) => s.filters.flags);
  const subnetScope = useUiStore((s) => s.filters.subnetScope);
  const filterTimeFrom = useUiStore((s) => s.filters.timeFrom);
  const filterTimeTo = useUiStore((s) => s.filters.timeTo);

  // ── Sidebar resize (drag the border; double-click resets) ────
  const startSidebarResize = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = sidebarWidth;
    const onMove = (ev: MouseEvent) => {
      setSidebarWidth(startW + (ev.clientX - startX));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

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
    filterIp ||
    filterSrcIp ||
    filterDstIp ||
    filterPort ||
    filterSrcPort ||
    filterDstPort ||
    filterSearch ||
    synOnly ||
    rstOnly ||
    filterFlags.length > 0 ||
    subnetScope !== "all" ||
    filterTimeFrom != null ||
    filterTimeTo != null
  );
  const [filterEndpointIps, setFilterEndpointIps] = useState<Set<string> | null>(null);

  useEffect(() => {
    if (!packetFiltersActive) {
      setFilterEndpointIps(null);
      return;
    }
    let cancelled = false;
    fetchPacketEndpoints(topology.sessionId, {
      ip: filterIp || undefined,
      srcIp: filterSrcIp || undefined,
      dstIp: filterDstIp || undefined,
      port: filterPort || undefined,
      srcPort: filterSrcPort || undefined,
      dstPort: filterDstPort || undefined,
      search: filterSearch || undefined,
      synOnly,
      rstOnly,
      flags: filterFlags.length > 0 ? filterFlags : undefined,
      subnet: subnetScope !== "all" ? localSubnet ?? undefined : undefined,
      subnetScope: subnetScope !== "all" ? subnetScope : undefined,
      timeFrom: filterTimeFrom ?? undefined,
      timeTo: filterTimeTo ?? undefined,
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
  }, [packetFiltersActive, filterIp, filterSrcIp, filterDstIp, filterPort, filterSrcPort, filterDstPort, filterSearch, synOnly, rstOnly, filterFlags, subnetScope, localSubnet, filterTimeFrom, filterTimeTo, topology.sessionId]);

  // Graph elements: packet-level filters (ip/port/search/...) prune the graph
  // to the endpoints of matching packets. A followed stream does NOT prune —
  // it only marks the flow yellow (stream focus) and filters the packet list.
  const graphElements = useMemo(() => {
    if (!filterEndpointIps) return filteredElements;
    const nodes = filteredElements.nodes.filter((n) => filterEndpointIps.has(n.data.id));
    const ids = new Set(nodes.map((n) => n.data.id));
    const edges = filteredElements.edges.filter(
      (e) => ids.has(e.data.source) && ids.has(e.data.target),
    );
    return { nodes, edges };
  }, [filteredElements, filterEndpointIps]);

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
    (accepted: File[], rejections: FileRejection[]) => {
      const tooBig = rejections.find((r) => r.errors.some((e) => e.code === "file-too-large"));
      if (tooBig) {
        setRejected(
          `${tooBig.file.name}: ${formatMb(tooBig.file.size)} — ${t("fileTooLarge")} (${formatMb(maxUploadBytes)})`,
        );
        return;
      }
      setRejected(null);
      if (accepted[0]) {
        const file = accepted[0];
        uploadNew(
          { files: [{ file, name: file.name }] },
          {
            onSuccess: (data) => {
              queryClient.setQueryData(["topology", data.sessionId], data);
            },
          },
        );
      }
    },
    [uploadNew, queryClient, t, maxUploadBytes],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.tcpdump.pcap": [".pcap"],
      "application/octet-stream": [".pcap", ".pcapng"],
    },
    maxFiles: 1,
    maxSize: maxUploadBytes,
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
            <p className="text-blue-300 text-lg">{t("dropHere")}</p>
          </div>
        </div>
      )}

      {/* Rejected file banner */}
      {rejected && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 bg-rose-950/90 backdrop-blur border border-rose-700 rounded-lg px-4 py-2 text-sm text-rose-400 shadow-xl">
          {rejected}
        </div>
      )}

      {/* Header */}
      <AppHeader
        onHome={onHome}
        onMySessions={onMySessions}
        onNewSession={onNewSession}
        onAISettings={onAISettings}
        onLogout={onLogout}
        hasSession
      >
        {/* Session identity: file name (falls back to session id for stale
            react-query caches predating the filename field). Wraps to <= 2
            lines within a bounded width so header controls are not pushed.
            Logged-in users can click it (pencil on hover) to rename inline;
            anonymous users get plain text — renaming requires an account. */}
        {user ? (
          renamingSession ? (
            <span className="w-64 max-w-full min-w-0 mr-2">
              <SessionRenameInput
                current={topology.filename?.trim() || topology.sessionId}
                onCommit={onRenameSession}
                onDone={() => setRenamingSession(false)}
                className="w-full rounded border border-blue-500/60 bg-zinc-900 px-2 py-0.5 text-xs text-zinc-100 outline-none focus:border-blue-400"
              />
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setRenamingSession(true)}
              title={t("renameSession")}
              className="group/rename mr-2 flex max-w-xs min-w-0 items-center gap-1.5 text-left text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <span className="min-w-0 whitespace-normal break-words underline-offset-2 group-hover/rename:underline">
                {topology.filename?.trim() || topology.sessionId}
              </span>
              <Pencil className="h-3 w-3 shrink-0 opacity-0 group-hover/rename:opacity-100 transition-opacity" />
            </button>
          )
        ) : (
          <span
            className="text-xs text-zinc-500 mr-2 max-w-xs min-w-0 whitespace-normal break-words"
            title={topology.filename || topology.sessionId}
          >
            {topology.filename?.trim() || topology.sessionId}
          </span>
        )}
        <GraphControls />
      </AppHeader>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left sidebar — Filters */}
        <aside
          className="no-scrollbar relative border-r border-zinc-800 p-4 space-y-6 overflow-y-auto shrink-0"
          style={{ width: sidebarWidth }}
        >
          <TopologyFilters
            availableProtocols={availableProtocols}
            localSubnet={localSubnet}
            captureTimeRange={{
              start: topology.stats.startTime,
              end: topology.stats.endTime,
            }}
          />
          {/* Drag handle — resize, double-click resets to default */}
          <div
            role="separator"
            aria-orientation="vertical"
            title="Drag to resize · double-click to reset"
            onMouseDown={startSidebarResize}
            onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT)}
            className="absolute top-0 -right-1 z-10 h-full w-2 cursor-col-resize
                       hover:bg-blue-600/40 active:bg-blue-600/60 transition-colors"
          />
        </aside>

        {/* Main content — graph or raw packet table */}
        <main className="flex-1 min-w-0 relative flex flex-col">
          {mainView === "packets" ? (
            <PacketTable sessionId={topology.sessionId} localSubnet={localSubnet} />
          ) : (
            <>
              {/* Context strip — what the selected layout does + traffic-weights legend */}
              <div className="shrink-0 flex flex-wrap items-center gap-x-5 gap-y-1 px-3 py-1.5 border-b border-zinc-800 bg-zinc-900/50 text-[11px] text-zinc-500">
                <span className="flex items-center gap-1.5">
                  {graphLayout === "fcose" ? (
                    <Share2 className="h-3 w-3 text-blue-500" />
                  ) : (
                    <ArrowDownUp className="h-3 w-3 text-blue-500" />
                  )}
                  <span className="font-medium text-zinc-300">
                    {t(graphLayout === "dagre" ? "layoutDagreTitle" : "layoutForceTitle")}
                  </span>
                  <span>{t(graphLayout === "dagre" ? "layoutDagreDesc" : "layoutForceDesc")}</span>
                </span>
                {trafficView && (
                  <span className="flex items-center gap-1.5">
                    <BarChart3 className="h-3 w-3 text-amber-500" />
                    <span className="font-medium text-amber-500/90">{t("weights")}</span>
                    <span>{t("weightsLegend")}</span>
                  </span>
                )}
              </div>
              <div className="relative flex-1 min-h-0">
                <NetworkGraph
                  topology={topology}
                  elements={graphElements as unknown as { nodes: Array<{ data: Record<string, unknown> }>; edges: Array<{ data: Record<string, unknown> }> }}
                />

              {/* Floating legend panel */}
              {showLegend && (
                <div className="absolute top-4 left-4 z-30 bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-lg p-4 shadow-xl w-48">
                  <GraphLegend />
                </div>
              )}
              </div>
            </>
          )}

          {/* AI assistant — right slide-in overlay */}
          <AIAssistantPanel sessionId={topology.sessionId} onOpenSettings={onAISettings} />
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
              <PacketDetails key={`table-${selectedPacketIndex}`} sessionId={topology.sessionId} />
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
                  <PacketDetails key={`panel-${selectedPacketIndex}`} sessionId={topology.sessionId} />
                ) : (
                  <>
                    {selectedNode && (
                      <NodeDetails
                        key={selectedNode.data.id}
                        node={selectedNode.data}
                        sessionId={topology.sessionId}
                      />
                    )}
                    {selectedEdge && (
                      <EdgeDetails
                        key={selectedEdge.data.id}
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
  const {
    mutate,
    isPending,
    error: uploadError,
    data: uploadResult,
    reset: resetUpload,
  } = usePcapUpload();
  const { t } = useI18n();
  const reset = useUiStore((s) => s.reset);
  const maxBundleBytes = useConfigStore((s) => s.maxBundleBytes);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const setAiPanelOpen = useAiStore((s) => s.setPanelOpen);
  const [showMySessions, setShowMySessions] = useState(false);
  const [showAISettings, setShowAISettings] = useState(false);
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

  // Auth identity change (login/logout) — drop any stale upload result/error
  // so the remounted upload panel starts clean (no lingering error banner).
  useEffect(() => {
    resetUpload();
  }, [resetUpload, user?.id]);

  const handleHome = useCallback(() => {
    reset();
    setActiveTopology(null);
    setShowMySessions(false);
    setShowAISettings(false);
    queryClient.removeQueries({ queryKey: ["topology"] });
    if (!user) {
      fetchSessions().then(setSessions).catch(console.error);
    }
  }, [queryClient, reset, user]);

  // Logout → pristine start screen: clear auth, then reuse the existing
  // "go home" reset (drops the loaded capture, view state, ui store and
  // topology cache). The anonymous sessions list is cleared up front; the
  // user→null effect refetches it fresh once the cookie is gone.
  const handleLogout = useCallback(() => {
    void logout();
    setSessions([]);
    handleHome();
  }, [logout, handleHome]);

  const handleMySessions = useCallback(() => {
    setActiveTopology(null);
    setShowMySessions(true);
    setShowAISettings(false);
  }, []);

  const handleAISettings = useCallback(() => {
    // Keep the current view state — Back returns to wherever the user came from.
    setShowAISettings(true);
  }, []);

  const handleBackFromAISettings = useCallback(() => {
    setShowAISettings(false);
  }, []);

  // Reopen the AI chat panel (only meaningful with a loaded capture).
  const handleBackToChat = useCallback(() => {
    setShowAISettings(false);
    setAiPanelOpen(true);
  }, [setAiPanelOpen]);

  const handleLoadSession = useCallback(async (sessionId: string) => {
    try {
      const topology = await fetchSessionTopology(sessionId);
      setActiveTopology(topology);
      setShowMySessions(false);
      setShowAISettings(false);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  }, []);

  // Rename the loaded session (graph header): optimistic in-place update of
  // the active topology (header re-renders; the graph itself is untouched —
  // NetworkGraph keys off sessionId and skips unchanged element ID sets) plus
  // any cached copy, then PATCH. On failure revert both and rethrow so the
  // inline editor shows the backend detail.
  const handleRenameActiveSession = useCallback(
    async (newName: string) => {
      const current = activeTopology;
      if (!current) return;
      const updated = { ...current, filename: newName };
      setActiveTopology(updated);
      queryClient.setQueryData<TopologyResponse>(
        ["topology", current.sessionId],
        updated,
      );
      try {
        await renameSession(current.sessionId, newName);
      } catch (err) {
        setActiveTopology(current);
        queryClient.setQueryData(["topology", current.sessionId], current);
        throw err;
      }
    },
    [activeTopology, queryClient],
  );

  // Delete is only reachable from the upload screen's past-sessions list.
  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Delete this session?")) return;
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  // Resolve the active view to a single tree. The starfield below mounts once
  // at the root — remounting it per view would re-randomize the field and
  // kill the smooth dim/un-dim opacity transition.
  let view: ReactNode;
  if (showAISettings) {
    // AI Settings page (keeps the underlying view state for Back)
    view = (
      <AISettingsPage
        onHome={handleHome}
        onBack={handleBackFromAISettings}
        onBackToChat={activeTopology ? handleBackToChat : undefined}
        onMySessions={handleMySessions}
        onNewSession={handleHome}
      />
    );
  } else if (activeTopology) {
    // Graph view once we have topology data
    view = (
      <GraphView
        topology={activeTopology}
        onHome={handleHome}
        onMySessions={handleMySessions}
        onNewSession={handleHome}
        onAISettings={handleAISettings}
        onLogout={handleLogout}
        onRenameSession={handleRenameActiveSession}
      />
    );
  } else if (showMySessions) {
    // My Sessions view (logged-in users)
    view = (
      <MySessions
        onHome={handleHome}
        onLoadSession={handleLoadSession}
        onNewSession={handleHome}
        onAISettings={handleAISettings}
      />
    );
  } else {
    // Upload screen
    view = (
    <div className="min-h-screen flex flex-col">
      <AppHeader
        onHome={handleHome}
        onMySessions={user ? handleMySessions : undefined}
        onNewSession={user ? handleHome : undefined}
        onAISettings={handleAISettings}
        onLogout={handleLogout}
      />

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-2xl w-full space-y-8">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-bold tracking-tight">
              {t("heroTitle")}
            </h2>
            <p className="text-zinc-400">
              {t("heroSubtitle")}
            </p>
          </div>

          <UploadPanel
            key={user?.id ?? "anonymous"}
            onUpload={(files, label) => mutate({ files, label })}
            isPending={isPending}
            uploadError={uploadError}
            onOpenSession={handleLoadSession}
          />

          <div className="flex justify-center gap-6 text-sm text-zinc-500">
            <span>PCAP / PCAPNG</span>
            <span>&bull;</span>
            <span>IPv4 + IPv6</span>
            <span>&bull;</span>
            <span>{t("upToSize").replace("{size}", formatMb(maxBundleBytes))}</span>
          </div>

          {/* Past Sessions — anonymous users only (logged-in users use MySessions) */}
          {!user && sessions.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-zinc-400">
                <History className="h-4 w-4" />
                <span className="text-sm font-medium">{t("pastSessions")}</span>
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
        <span>NetVisor &mdash; {t("footerTagline")}</span>
      </footer>

    </div>
    );
  }

  return (
    <>
      {/* App-wide starfield — fixed canvas behind all content. Intensity keys
          off the loaded-topology state: full on the landing/empty state,
          near-invisible once a capture is loaded. */}
      <Starfield dimmed={activeTopology != null} />
      {view}
      <DebugLogPanel />
    </>
  );
}