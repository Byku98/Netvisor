import { useCallback, useEffect, useRef } from "react";
import cytoscape, { type Core, type EventObject } from "cytoscape";
import type { TopologyResponse } from "@/types/network.types";
import { useUiStore } from "@/stores/ui.store";

interface NetworkGraphProps {
  /** Full topology response from the backend. */
  topology: TopologyResponse;
  /** Filtered Cytoscape elements to render. */
  elements: {
    nodes: Array<{ data: Record<string, unknown> }>;
    edges: Array<{ data: Record<string, unknown> }>;
  };
}

/** Color map for node types. */
const NODE_COLORS: Record<string, string> = {
  router: "#f59e0b",
  server: "#3b82f6",
  client: "#22c55e",
  unknown: "#6b7280",
};

/** Build Cytoscape stylesheet. */
function getStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "background-color": (ele: cytoscape.NodeSingular) =>
          NODE_COLORS[ele.data("type") as string] ?? NODE_COLORS.unknown,
        color: "#e4e4e7",
        "text-valign": "bottom",
        "text-margin-y": 5,
        "font-size": "11px",
        width: (ele: cytoscape.NodeSingular) =>
          Math.max(20, Math.min(60, (ele.data("totalPackets") as number) / 10)),
        height: (ele: cytoscape.NodeSingular) =>
          Math.max(20, Math.min(60, (ele.data("totalPackets") as number) / 10)),
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 3,
        "border-color": "#ffffff",
        "background-color": (ele: cytoscape.NodeSingular) =>
          NODE_COLORS[ele.data("type") as string] ?? NODE_COLORS.unknown,
      },
    },
    {
      selector: "edge",
      style: {
        width: (ele: cytoscape.EdgeSingular) =>
          Math.max(1, Math.min(8, (ele.data("weight") as number) / 5)),
        "line-color": "#52525b",
        "target-arrow-color": "#52525b",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.8,
        "curve-style": "bezier",
        opacity: 0.7,
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": "#ffffff",
        "target-arrow-color": "#ffffff",
        width: (ele: cytoscape.EdgeSingular) =>
          Math.max(2, Math.min(10, (ele.data("weight") as number) / 5)),
        opacity: 1,
      },
    },
  ];
}

/** Get layout options for the given algorithm. */
function getLayoutOptions(layoutName: string): cytoscape.LayoutOptions {
  const base = { animate: true, animationDuration: 500 };

  switch (layoutName) {
    case "dagre":
      return { ...base, name: "dagre" } as unknown as cytoscape.LayoutOptions;
    case "circle":
      return { ...base, name: "circle" };
    case "grid":
      return { ...base, name: "grid" };
    case "cose":
    default:
      return {
        ...base,
        name: "cose",
        idealEdgeLength: 120,
        nodeOverlap: 20,
        refresh: 20,
        randomize: false,
      } as unknown as cytoscape.LayoutOptions;
  }
}

/**
 * Renders the interactive network graph using Cytoscape.js.
 * Handles node/edge selection, layout changes, and resize.
 */
export function NetworkGraph({ topology, elements }: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const graphLayout = useUiStore((s) => s.graphLayout);
  const setSelectedNode = useUiStore((s) => s.setSelectedNode);
  const setSelectedEdge = useUiStore((s) => s.setSelectedEdge);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...elements.nodes, ...elements.edges] as cytoscape.ElementDefinition[],
      style: getStylesheet() as unknown as cytoscape.StylesheetCSS[],
      layout: getLayoutOptions(graphLayout),
      minZoom: 0.2,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    // Node click
    cy.on("tap", "node", (evt: EventObject) => {
      const nodeId = evt.target.data("id") as string;
      setSelectedNode(nodeId);
    });

    // Edge click
    cy.on("tap", "edge", (evt: EventObject) => {
      const edgeId = evt.target.data("id") as string;
      setSelectedEdge(edgeId);
    });

    // Background click — deselect
    cy.on("tap", (evt: EventObject) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        setSelectedEdge(null);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // Only re-create when topology changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topology.sessionId]);

  // Update elements when filters change
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().remove();
    cy.add([...elements.nodes, ...elements.edges]);
    cy.layout(getLayoutOptions(graphLayout)).run();
  }, [elements, graphLayout]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      cyRef.current?.resize();
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Zoom controls (exposed via callbacks for GraphControls)
  const handleZoomIn = useCallback(() => {
    cyRef.current?.zoom({ level: cyRef.current.zoom() * 1.3, renderedPosition: { x: 0, y: 0 } });
  }, []);

  const handleZoomOut = useCallback(() => {
    cyRef.current?.zoom({ level: cyRef.current.zoom() / 1.3, renderedPosition: { x: 0, y: 0 } });
  }, []);

  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 50);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      {/* Zoom/Fit buttons overlay */}
      <div className="absolute top-3 right-3 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-sm font-bold border border-zinc-700"
          title="Zoom in"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-sm font-bold border border-zinc-700"
          title="Zoom out"
        >
          &minus;
        </button>
        <button
          onClick={handleFit}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-xs border border-zinc-700"
          title="Fit to screen"
        >
          ⊞
        </button>
      </div>
    </div>
  );
}
