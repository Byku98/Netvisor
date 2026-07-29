import type { SessionStats } from "@/types/network.types";

interface StatsPanelProps {
  /** Session statistics to display. */
  stats: SessionStats;
}

/** Displays aggregate session statistics in a 2x2 grid: packets, bytes, hosts, protocols. */
export function StatsPanel({ stats }: StatsPanelProps) {
  return (
    <div className="p-4 space-y-2">
      <h3 className="font-semibold text-zinc-300">Session Statistics</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-zinc-500">Packets</p>
          <p className="text-zinc-200 font-mono">
            {stats.totalPackets.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-zinc-500">Bytes</p>
          <p className="text-zinc-200 font-mono">
            {(stats.totalBytes / 1024).toFixed(1)} KB
          </p>
        </div>
        <div>
          <p className="text-zinc-500">Hosts</p>
          <p className="text-zinc-200 font-mono">{stats.uniqueHosts}</p>
        </div>
        <div>
          <p className="text-zinc-500">Protocols</p>
          <p className="text-zinc-200 font-mono">
            {Object.keys(stats.protocols).length}
          </p>
        </div>
      </div>
    </div>
  );
}
