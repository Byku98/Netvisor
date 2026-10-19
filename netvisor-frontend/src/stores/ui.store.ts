import { create } from "zustand";
import { devtools } from "zustand/middleware";

/** Color theme. Applied as `light` class on <html> — CSS palette remap in index.css. */
export type Theme = "dark" | "light";

function initialTheme(): Theme {
  const saved = localStorage.getItem("netvisor-theme");
  const theme: Theme = saved === "light" ? "light" : "dark";
  if (theme === "light") document.documentElement.classList.add("light");
  return theme;
}

/** UI state managed by Zustand — graph selection, layout, and filters. */
interface UiState {
  /** ID of the currently selected graph node, or null. */
  selectedNodeId: string | null;
  /** ID of the currently selected graph edge, or null. */
  selectedEdgeId: string | null;
  /** Active Cytoscape layout algorithm. */
  graphLayout: "cose" | "dagre" | "circle" | "grid";
  /** Main content view: topology graph or raw packet table. */
  mainView: "graph" | "packets";
  /** Index of the packet selected in the packet table (tshark frame number), or null. */
  selectedPacketIndex: number | null;
  /** TCP stream index of the selected packet, or null. */
  selectedPacketStream: number | null;
  /** TCP stream currently being followed (filters graph + packet list), or null. */
  followedStream: number | null;
  /** Color theme ("light" adds .light class to <html> — palette remap). */
  theme: Theme;
  /** Toggle dark/light theme. */
  toggleTheme: () => void;
  /** Active graph filters. */
  filters: {
    /** Only show nodes that use at least one of these protocols. */
    protocols: string[];
    /** Isolate traffic to/from this node only (show only connected edges/nodes). */
    isolatedNodeId: string | null;
    /** Either-side IP filter (matches src OR dst; octet prefix = range). Empty = off. */
    ip: string;
    /** Source IP filter (Specify mode). Empty = off. */
    srcIp: string;
    /** Destination IP filter (Specify mode). Empty = off. */
    dstIp: string;
    /** Local/external subnet scope ("all" = off). */
    subnetScope: "all" | "local" | "external";
    /** Either-side port filter — strict equality, OR list '443, 8443'. Empty = off. */
    port: string;
    /** Source-port-only filter (Specify mode, same syntax as port). Empty = off. */
    srcPort: string;
    /** Destination-port-only filter (Specify mode, same syntax as port). Empty = off. */
    dstPort: string;
    /** Keyword search in packet Info column. */
    search: string;
    /** Only TCP SYN without ACK (connection attempts / scans). */
    synOnly: boolean;
  };
  /** Select a node by ID (clears edge selection). */
  setSelectedNode: (id: string | null) => void;
  /** Select an edge by ID (clears node selection). */
  setSelectedEdge: (id: string | null) => void;
  /** Change the graph layout algorithm. */
  setGraphLayout: (layout: UiState["graphLayout"]) => void;
  /** Merge partial filter values into the current filters. */
  setFilters: (filters: Partial<UiState["filters"]>) => void;
  /** Toggle a protocol filter on/off. */
  toggleProtocol: (protocol: string) => void;
  /** Isolate traffic to/from a specific node. */
  setIsolatedNode: (nodeId: string | null) => void;
  /** Switch the main content view. */
  setMainView: (view: UiState["mainView"]) => void;
  /** Select a packet by index (node/edge selection is kept as back-context). */
  setSelectedPacket: (index: number | null, stream?: number | null) => void;
  /** Follow a TCP stream (filters graph + packet lists). */
  setFollowedStream: (stream: number | null) => void;
  /** Whether the legend panel is visible. */
  showLegend: boolean;
  /** Toggle legend panel visibility. */
  toggleLegend: () => void;
  /** Reset all UI state to defaults. */
  reset: () => void;
}

/** Global UI store for graph selection, layout, and filter state. */
export const useUiStore = create<UiState>()(
  devtools((set) => ({
    selectedNodeId: null,
    selectedEdgeId: null,
    graphLayout: "cose",
    mainView: "graph",
    selectedPacketIndex: null,
    selectedPacketStream: null,
    followedStream: null,
    theme: initialTheme(),
    showLegend: false,
    filters: { protocols: [], isolatedNodeId: null, ip: "", srcIp: "", dstIp: "", subnetScope: "all", port: "", srcPort: "", dstPort: "", search: "", synOnly: false },
    setSelectedNode: (id) =>
      set({ selectedNodeId: id, selectedEdgeId: null, selectedPacketIndex: null }),
    setSelectedEdge: (id) =>
      set({ selectedEdgeId: id, selectedNodeId: null, selectedPacketIndex: null }),
    setGraphLayout: (layout) => set({ graphLayout: layout }),
    setFilters: (filters) =>
      set((state) => ({ filters: { ...state.filters, ...filters } })),
    toggleProtocol: (protocol) =>
      set((state) => {
        const current = state.filters.protocols;
        const next = current.includes(protocol)
          ? current.filter((p) => p !== protocol)
          : [...current, protocol];
        return { filters: { ...state.filters, protocols: next } };
      }),
    setIsolatedNode: (nodeId) =>
      set((state) => ({
        filters: {
          ...state.filters,
          isolatedNodeId: state.filters.isolatedNodeId === nodeId ? null : nodeId,
        },
      })),
    toggleLegend: () => set((state) => ({ showLegend: !state.showLegend })),
    setMainView: (view) => set({ mainView: view }),
    setSelectedPacket: (index, stream = null) =>
      set({ selectedPacketIndex: index, selectedPacketStream: stream }),
    setFollowedStream: (stream) => set({ followedStream: stream }),
    toggleTheme: () =>
      set((state) => {
        const next: Theme = state.theme === "dark" ? "light" : "dark";
        localStorage.setItem("netvisor-theme", next);
        document.documentElement.classList.toggle("light", next === "light");
        return { theme: next };
      }),
    reset: () =>
      set({
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedPacketIndex: null,
        selectedPacketStream: null,
        followedStream: null,
        mainView: "graph",
        showLegend: false,
        filters: { protocols: [], isolatedNodeId: null, ip: "", srcIp: "", dstIp: "", subnetScope: "all", port: "", srcPort: "", dstPort: "", search: "", synOnly: false },
      }),
  }))
);
