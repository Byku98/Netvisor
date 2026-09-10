import { useQueryClient } from "@tanstack/react-query";
import { usePcapUpload } from "@/hooks/use-pcap-upload";
import { useGraphState } from "@/hooks/use-graph-state";
import { useUiStore } from "@/stores/ui.store";
import { NetworkGraph } from "@/components/graph/NetworkGraph";
import { GraphControls } from "@/components/graph/GraphControls";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { StatsPanel } from "@/components/stats/StatsPanel";
import { NodeDetails } from "@/components/details/NodeDetails";
import { EdgeDetails } from "@/components/details/EdgeDetails";
import { AppHeader } from "@/components/auth/AppHeader";
import { MySessions } from "@/components/sessions/MySessions";
import { DebugLogPanel } from "@/components/DebugLogPanel";
import type { TopologyResponse } from "@/types/network.types";
import { Upload } from "lucide-react";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { cn } from "@/lib/utils";

interface GraphViewProps {
  /** The topology data to visualize. */
  topology: TopologyResponse;
  /** Go back to the upload screen. */
  onBack: () => void;
}

/**
 * Full graph visualization view.
 * Shows the network graph, controls, legend, stats, and detail panels.
 */
function GraphView({ topology, onBack }: GraphViewProps) {
  const { filteredElements, selectedNode, selectedEdge } =
    useGraphState(topology);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectedEdgeId = useUiStore((s) => s.selectedEdgeId);

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
      <AppHeader onBack={onBack}>
        <span className="text-xs text-zinc-500 mr-2 truncate max-w-xs">
          {topology.sessionId}
        </span>
        <GraphControls />
      </AppHeader>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left sidebar — Legend + Stats */}
        <aside className="w-56 border-r border-zinc-800 p-4 space-y-6 overflow-y-auto shrink-0">
          <GraphLegend />
          <StatsPanel stats={topology.stats} />
        </aside>

        {/* Graph */}
        <main className="flex-1 min-w-0">
          <NetworkGraph
            topology={topology}
            elements={filteredElements as unknown as { nodes: Array<{ data: Record<string, unknown> }>; edges: Array<{ data: Record<string, unknown> }> }}
          />
        </main>

        {/* Right sidebar — Details */}
        {(selectedNodeId || selectedEdgeId) && (
          <aside className="w-80 border-l border-zinc-800 shrink-0 overflow-hidden">
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
          </aside>
        )}
      </div>
    </div>
  );
}

/** Root application component. Shows upload screen or graph view. */
export function App() {
  const queryClient = useQueryClient();
  const { mutate, isPending, data: topology } = usePcapUpload();
  const reset = useUiStore((s) => s.reset);
  const [showMySessions, setShowMySessions] = useState(false);

  // Check if we have topology data (from current upload or cache)
  const activeTopology = topology ?? null;

  const handleBack = useCallback(() => {
    // Clear the topology from cache and reset UI state
    if (activeTopology) {
      queryClient.removeQueries({
        queryKey: ["topology", activeTopology.sessionId],
      });
    }
    reset();
    setShowMySessions(false);
  }, [activeTopology, queryClient, reset]);

  // Show graph view if we have topology data
  if (activeTopology) {
    return (
      <>
        <GraphView topology={activeTopology} onBack={handleBack} />
        <DebugLogPanel />
      </>
    );
  }

  // Show My Sessions view
  if (showMySessions) {
    return (
      <>
        <MySessions onBack={() => setShowMySessions(false)} />
        <DebugLogPanel />
      </>
    );
  }

  // Upload screen
  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader onMySessions={() => setShowMySessions(true)} />

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
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-6 py-3 text-center text-sm text-zinc-500">
        NetVisor &mdash; Interactive network topology visualization from PCAP
        files
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
