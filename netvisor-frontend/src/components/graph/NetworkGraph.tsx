import { useCallback, useEffect, useRef } from "react";
import cytoscape, { type Core, type EventObject } from "cytoscape";
import dagre from "cytoscape-dagre";
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
  switch: "#8b5cf6",
  server: "#3b82f6",
  firewall: "#ef4444",
  client: "#22c55e",
  unknown: "#6b7280",
};

/** SVG icons for each device type — rendered as Cytoscape node backgrounds. */
const NODE_ICONS: Record<string, string> = {
  // Router: arrows in/out
  router: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>')}`,
  // Switch: network switch with ports
  switch: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="6" cy="12" r="1.5" fill="white"/><circle cx="10" cy="12" r="1.5" fill="white"/><circle cx="14" cy="12" r="1.5" fill="white"/><circle cx="18" cy="12" r="1.5" fill="white"/></svg>')}`,
  // Server: monitor with status LED
  server: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="4" y1="8" x2="20" y2="8"/><line x1="4" y1="14" x2="20" y2="14"/><circle cx="8" cy="5" r="1" fill="white"/><circle cx="8" cy="11" r="1" fill="white"/><circle cx="8" cy="17" r="1" fill="white"/></svg>')}`,
  // Firewall: shield
  firewall: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4M12 16h.01"/></svg>')}`,
  // Client: user/person
  client: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>')}`,
  // Unknown: question mark
  unknown: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>')}`,
};

/** Build Cytoscape stylesheet, theme-aware (light mode needs dark text/selection colors). */
function getStylesheet(theme: "dark" | "light") {
  const labelColor = theme === "light" ? "#3f3f46" : "#e4e4e7";
  const selectionColor = theme === "light" ? "#18181b" : "#ffffff";
  const edgeColor = theme === "light" ? "#a1a1aa" : "#52525b";
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "background-color": (ele: cytoscape.NodeSingular) =>
          NODE_COLORS[ele.data("type") as string] ?? NODE_COLORS.unknown,
        "background-image": (ele: cytoscape.NodeSingular) => {
          const type = ele.data("type") as string;
          return NODE_ICONS[type] ?? NODE_ICONS.unknown;
        },
        "background-fit": "cover",
        "background-clip": "none",
        "border-width": 2,
        "border-color": (ele: cytoscape.NodeSingular) => {
          const color = NODE_COLORS[ele.data("type") as string] ?? NODE_COLORS.unknown;
          // Darken the border slightly
          return color;
        },
        color: labelColor,
        "text-valign": "bottom",
        "text-margin-y": 5,
        "font-size": "11px",
        width: (ele: cytoscape.NodeSingular) =>
          Math.max(32, Math.min(70, (ele.data("totalPackets") as number) / 10 + 20)),
        height: (ele: cytoscape.NodeSingular) =>
          Math.max(32, Math.min(70, (ele.data("totalPackets") as number) / 10 + 20)),
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 3,
        "border-color": selectionColor,
        "background-color": (ele: cytoscape.NodeSingular) =>
          NODE_COLORS[ele.data("type") as string] ?? NODE_COLORS.unknown,
      },
    },
    {
      selector: "edge",
      style: {
        width: (ele: cytoscape.EdgeSingular) =>
          Math.max(1, Math.min(8, (ele.data("weight") as number) / 5)),
        "line-color": edgeColor,
        "target-arrow-color": edgeColor,
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.8,
        "curve-style": "bezier",
        opacity: 0.7,
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": selectionColor,
        "target-arrow-color": selectionColor,
        width: (ele: cytoscape.EdgeSingular) =>
          Math.max(2, Math.min(10, (ele.data("weight") as number) / 5)),
        opacity: 1,
      },
    },
  ];
}

/** Register cytoscape-dagre extension for Dagre layout. */
cytoscape.use(dagre);

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
  const theme = useUiStore((s) => s.theme);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...elements.nodes, ...elements.edges] as cytoscape.ElementDefinition[],
      style: getStylesheet(theme) as unknown as cytoscape.StylesheetCSS[],
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

  // Re-apply stylesheet when theme changes
  useEffect(() => {
    cyRef.current
      ?.style(getStylesheet(theme) as unknown as cytoscape.StylesheetCSS[])
      .update();
  }, [theme]);

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
