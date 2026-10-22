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

/**
 * SVG icons for each device type — rendered as Cytoscape node backgrounds.
 * 32×32 viewBox with the glyph inside a ~24×24 safe area: node backgrounds are
 * clipped to the ellipse shape, so edge-adjacent strokes would get cut otherwise.
 */
const NODE_ICONS: Record<string, string> = {
  // Router (Cisco-style): circle with counter-flowing arrows
  router: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="16" cy="16" r="12.5"/><path d="M8.5 12.5h11.5"/><path d="M17 9.5l3.5 3-3.5 3"/><path d="M23.5 19.5H12"/><path d="M15 16.5l-3.5 3 3.5 3"/></svg>')}`,
  // Switch: box with staggered pass-through arrows
  switch: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="9.5" width="25" height="13" rx="2"/><path d="M7 13.5h5.5"/><path d="M10.5 11.5l2.5 2-2.5 2"/><path d="M25 18.5h-5.5"/><path d="M21.5 16.5L19 18.5l2.5 2"/></svg>')}`,
  // Server: two rack units with status LEDs
  server: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="5.5" width="20" height="9.5" rx="1.5"/><rect x="6" y="17" width="20" height="9.5" rx="1.5"/><circle cx="9.5" cy="10.2" r="1" fill="white" stroke="none"/><circle cx="9.5" cy="21.7" r="1" fill="white" stroke="none"/><path d="M14 9h9"/><path d="M14 12h6"/><path d="M14 20.5h9"/><path d="M14 23.5h6"/></svg>')}`,
  // Firewall: staggered brick wall
  firewall: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="7.5" width="23" height="17" rx="1.5"/><path d="M4.5 12.8h23"/><path d="M4.5 18.2h23"/><path d="M13 7.5v5.3"/><path d="M19 12.8v5.4"/><path d="M13 18.2v5.3"/></svg>')}`,
  // Client: desktop workstation
  client: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="6" width="22" height="14" rx="2"/><path d="M9.5 16.5l3.5-4 3 3 4-5.5 3 4.5" /><path d="M16 20v4.5"/><path d="M10.5 24.5h11"/></svg>')}`,
  // Unknown: question-mark badge
  unknown: `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="16" cy="16" r="12.5"/><path d="M12.7 12.9a3.4 3.4 0 0 1 6.6 1.1c0 2.2-3.3 2.6-3.3 4.6"/><line x1="16" y1="22.2" x2="16.01" y2="22.2"/></svg>')}`,
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
        // Clip the icon to the node ellipse — without this the SVG corners
        // poke outside the circle
        "background-clip": "node",
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

/**
 * Map element definitions for Cytoscape.
 */
function toCyElements(
  elements: NetworkGraphProps["elements"],
): cytoscape.ElementDefinition[] {
  return [...elements.nodes, ...elements.edges];
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
      elements: toCyElements(elements),
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
    cy.add(toCyElements(elements));
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
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-sm font-bold border border-zinc-700 transition-colors active:scale-90"
          title="Zoom in"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-sm font-bold border border-zinc-700 transition-colors active:scale-90"
          title="Zoom out"
        >
          &minus;
        </button>
        <button
          onClick={handleFit}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 w-8 h-8 rounded text-xs border border-zinc-700 transition-colors active:scale-90"
          title="Fit to screen"
        >
          ⊞
        </button>
      </div>
    </div>
  );
}
