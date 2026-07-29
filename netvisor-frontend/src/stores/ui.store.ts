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
  /** Active graph filters. */
  filters: {
    /** Only show nodes that use at least one of these protocols. */
    protocols: string[];
    /** Only show nodes with at least this many packets. */
    minPackets: number;
  };
  /** Select a node by ID (clears edge selection). */
  setSelectedNode: (id: string | null) => void;
  /** Select an edge by ID (clears node selection). */
  setSelectedEdge: (id: string | null) => void;
  /** Change the graph layout algorithm. */
  setGraphLayout: (layout: UiState["graphLayout"]) => void;
  /** Merge partial filter values into the current filters. */
  setFilters: (filters: Partial<UiState["filters"]>) => void;
  /** Reset all UI state to defaults. */
  reset: () => void;
}

/** Global UI store for graph selection, layout, and filter state. */
export const useUiStore = create<UiState>()(
  devtools((set) => ({
    selectedNodeId: null,
    selectedEdgeId: null,
    graphLayout: "cose",
    filters: { protocols: [], minPackets: 0 },
    setSelectedNode: (id) =>
      set({ selectedNodeId: id, selectedEdgeId: null }),
    setSelectedEdge: (id) =>
      set({ selectedEdgeId: id, selectedNodeId: null }),
    setGraphLayout: (layout) => set({ graphLayout: layout }),
    setFilters: (filters) =>
      set((state) => ({ filters: { ...state.filters, ...filters } })),
    reset: () =>
      set({
        selectedNodeId: null,
        selectedEdgeId: null,
        filters: { protocols: [], minPackets: 0 },
      }),
  }))
);
