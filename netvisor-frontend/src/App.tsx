import { Network, ExternalLink } from "lucide-react";
import { FileDropzone } from "@/components/upload/FileDropzone";

/** Root application component. Renders the upload screen with header and footer. */
export function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="h-6 w-6 text-blue-500" />
            <h1 className="text-xl font-bold tracking-tight">NetVisor</h1>
          </div>
          <a
            href="https://github.com/NetVisor"
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ExternalLink className="h-5 w-5" />
          </a>
        </div>
      </header>

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

          <FileDropzone />

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
        NetVisor &mdash; Interactive network topology visualization from PCAP files
      </footer>
    </div>
  );
}
