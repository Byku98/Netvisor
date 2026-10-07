import { create } from "zustand";
import { devtools } from "zustand/middleware";

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
  /** Active graph filters. */
  filters: {
    /** Only show nodes that use at least one of these protocols. */
    protocols: string[];
    /** Only show nodes with at least this many packets. */
    minPackets: number;
    /** Isolate traffic to/from this node only (show only connected edges/nodes). */
    isolatedNodeId: string | null;
    /** Max minPackets value (set from topology data). */
    maxPackets: number;
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
    showLegend: false,
    filters: { protocols: [], minPackets: 0, isolatedNodeId: null, maxPackets: 0 },
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
    reset: () =>
      set({
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedPacketIndex: null,
        selectedPacketStream: null,
        followedStream: null,
        mainView: "graph",
        showLegend: false,
        filters: { protocols: [], minPackets: 0, isolatedNodeId: null, maxPackets: 0 },
      }),
  }))
);
