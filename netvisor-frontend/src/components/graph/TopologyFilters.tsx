import { useEffect, useRef, useState } from "react";
import {
  Filter,
  RotateCcw,
  Crosshair,
  Check,
  Search,
  X,
  Globe,
  Home,
  ShieldAlert,
  MailOpen,
  Waypoints,
} from "lucide-react";
import { useUiStore } from "@/stores/ui.store";
import { cn } from "@/lib/utils";

/** Color mapping for known protocols. */
const PROTOCOL_COLORS: Record<string, { bg: string; active: string; text: string }> = {
  TCP:   { bg: "bg-blue-900/40",   active: "bg-blue-600",   text: "text-blue-300"   },
  UDP:   { bg: "bg-purple-900/40", active: "bg-purple-600", text: "text-purple-300" },
  HTTP:  { bg: "bg-green-900/40",  active: "bg-green-600",  text: "text-green-300"  },
  HTTPS: { bg: "bg-emerald-900/40", active: "bg-emerald-600", text: "text-emerald-300" },
  TLS:   { bg: "bg-emerald-900/40", active: "bg-emerald-600", text: "text-emerald-300" },
  DNS:   { bg: "bg-yellow-900/40", active: "bg-yellow-600", text: "text-yellow-300" },
  ICMP:  { bg: "bg-orange-900/40", active: "bg-orange-600", text: "text-orange-300" },
  ARP:   { bg: "bg-pink-900/40",   active: "bg-pink-600",   text: "text-pink-300"   },
  SSH:   { bg: "bg-cyan-900/40",   active: "bg-cyan-600",   text: "text-cyan-300"   },
  FTP:   { bg: "bg-rose-900/40",   active: "bg-rose-600",   text: "text-rose-300"   },
  SMTP:  { bg: "bg-indigo-900/40", active: "bg-indigo-600", text: "text-indigo-300" },
  DHCP:  { bg: "bg-teal-900/40",   active: "bg-teal-600",   text: "text-teal-300"   },
  OTHER: { bg: "bg-zinc-800",      active: "bg-zinc-600",   text: "text-zinc-300"   },
};

function getProtocolStyle(proto: string) {
  return PROTOCOL_COLORS[proto.toUpperCase()] ?? PROTOCOL_COLORS.OTHER;
}

/** Section heading. */
function SectionHeading({ icon: Icon, children }: { icon: typeof Filter; children: React.ReactNode }) {
  return (
    <p className="text-[11px] text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
      <Icon className="h-3 w-3" />
      {children}
    </p>
  );
}

/** Segmented control (small 2-3 option switch). */
function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex rounded-lg bg-zinc-800 p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "flex-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all",
            value === opt.value
              ? "bg-blue-600 text-white"
              : "text-zinc-400 hover:text-zinc-200",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

interface TopologyFiltersProps {
  /** All unique protocols found in the current topology. */
  availableProtocols: string[];
  /** Dominant local subnet in CIDR (computed from topology), e.g. "192.168.1.0/24". */
  localSubnet: string | null;
}

/**
 * Global filter panel — applies to the packet table and (partially) the graph.
 * Wireshark-grade filters, newbie-friendly UI: no expressions, just toggles.
 */
export function TopologyFilters({
  availableProtocols,
  localSubnet,
}: TopologyFiltersProps) {
  const filters = useUiStore((s) => s.filters);
  const cycleProtocol = useUiStore((s) => s.cycleProtocol);
  const setFilters = useUiStore((s) => s.setFilters);
  const setIsolatedNode = useUiStore((s) => s.setIsolatedNode);
  const setFollowedStream = useUiStore((s) => s.setFollowedStream);
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);

  const hasActiveFilters =
    filters.protocols.length > 0 ||
    filters.excludedProtocols.length > 0 ||
    filters.ip !== "" ||
    filters.srcIp !== "" ||
    filters.dstIp !== "" ||
    filters.subnetScope !== "all" ||
    filters.port !== "" ||
    filters.srcPort !== "" ||
    filters.dstPort !== "" ||
    filters.search !== "" ||
    filters.synOnly ||
    !!filters.isolatedNodeId;

  // ── Any / Specify modes (UI-only concept; store stays value-driven) ──
  const [ipMode, setIpMode] = useState<"any" | "custom">(
    filters.srcIp || filters.dstIp ? "custom" : "any",
  );
  const [portMode, setPortMode] = useState<"any" | "custom">(
    filters.srcPort || filters.dstPort ? "custom" : "any",
  );

  // ── Local input state (debounced → store) ────────────────────
  const [searchText, setSearchText] = useState(filters.search);
  const [ipText, setIpText] = useState(filters.ip);
  const [srcIpText, setSrcIpText] = useState(filters.srcIp);
  const [dstIpText, setDstIpText] = useState(filters.dstIp);
  const [portText, setPortText] = useState(filters.port);
  const [srcPortText, setSrcPortText] = useState(filters.srcPort);
  const [dstPortText, setDstPortText] = useState(filters.dstPort);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search + ip + port inputs into the store.
  // "Any" mode feeds the either-side ip/port fields, "Specify" the src/dst
  // pairs — the inactive set is always cleared so only one mode is live.
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setFilters({
        search: searchText,
        ip: ipMode === "any" ? ipText.trim() : "",
        srcIp: ipMode === "custom" ? srcIpText.trim() : "",
        dstIp: ipMode === "custom" ? dstIpText.trim() : "",
        port: portMode === "any" ? portText.trim() : "",
        srcPort: portMode === "custom" ? srcPortText.trim() : "",
        dstPort: portMode === "custom" ? dstPortText.trim() : "",
      });
    }, 350);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText, ipMode, ipText, srcIpText, dstIpText, portMode, portText, srcPortText, dstPortText]);

  /** Switch IP mode; clears whichever side is being deactivated. */
  const handleIpMode = (mode: "any" | "custom") => {
    setIpMode(mode);
    if (mode === "any") {
      setSrcIpText("");
      setDstIpText("");
      setFilters({ srcIp: "", dstIp: "" });
    } else {
      setIpText("");
      setFilters({ ip: "" });
    }
  };

  /** Switch port mode; clears whichever side is being deactivated. */
  const handlePortMode = (mode: "any" | "custom") => {
    setPortMode(mode);
    if (mode === "any") {
      setSrcPortText("");
      setDstPortText("");
      setFilters({ srcPort: "", dstPort: "" });
    } else {
      setPortText("");
      setFilters({ port: "" });
    }
  };

  // ── Quick recipes ─────────────────────────────────────────────
  const recipes: Array<{ label: string; icon: typeof Filter; apply: () => void; active: boolean }> = [
    {
      label: "Local only",
      icon: Home,
      active: filters.subnetScope === "local",
      apply: () =>
        setFilters({ subnetScope: filters.subnetScope === "local" ? "all" : "local" }),
    },
    {
      label: "External only",
      icon: Globe,
      active: filters.subnetScope === "external",
      apply: () =>
        setFilters({ subnetScope: filters.subnetScope === "external" ? "all" : "external" }),
    },
    {
      label: "DNS",
      icon: Waypoints,
      active: filters.protocols.length === 1 && filters.protocols[0].toUpperCase() === "DNS",
      apply: () =>
        setFilters({
          protocols:
            filters.protocols.length === 1 && filters.protocols[0].toUpperCase() === "DNS"
              ? []
              : ["DNS"],
          excludedProtocols: [],
        }),
    },
    {
      label: "Plaintext auth",
      icon: MailOpen,
      active:
        filters.protocols.length === 4 &&
        ["http", "ftp", "smtp", "telnet"].every((p) =>
          filters.protocols.some((x) => x.toLowerCase() === p),
        ),
      apply: () =>
        setFilters({
          protocols:
            filters.protocols.length === 4 &&
            ["http", "ftp", "smtp", "telnet"].every((p) =>
              filters.protocols.some((x) => x.toLowerCase() === p),
            )
              ? []
              : ["HTTP", "FTP", "SMTP", "TELNET"],
          excludedProtocols: [],
        }),
    },
    {
      label: "Scans (SYN)",
      icon: ShieldAlert,
      active: filters.synOnly,
      apply: () => setFilters({ synOnly: !filters.synOnly }),
    },
  ];

  // Empty state: no protocols
  if (availableProtocols.length === 0) {
    return (
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          Filters
        </h4>
        <p className="text-xs text-zinc-500">Load a PCAP to enable filters</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          Filters
          {hasActiveFilters && (
            <span className="ml-1 px-1.5 py-0.5 bg-blue-600 text-white text-[10px] rounded-full font-bold">
              {(
                (filters.protocols.length > 0 || filters.excludedProtocols.length > 0 ? 1 : 0) +
                (filters.ip !== "" ? 1 : 0) +
                (filters.srcIp !== "" ? 1 : 0) +
                (filters.dstIp !== "" ? 1 : 0) +
                (filters.subnetScope !== "all" ? 1 : 0) +
                (filters.port !== "" ? 1 : 0) +
                (filters.srcPort !== "" ? 1 : 0) +
                (filters.dstPort !== "" ? 1 : 0) +
                (filters.search !== "" ? 1 : 0) +
                (filters.synOnly ? 1 : 0) +
                (filters.isolatedNodeId ? 1 : 0)
              )}
            </span>
          )}
        </h4>
      </div>

      {/* ── Search ── */}
      <div className="space-y-2">
        <SectionHeading icon={Search}>Search</SectionHeading>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="in packet info..."
            className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg pl-8 pr-7 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       placeholder:text-zinc-500"
          />
          {searchText && (
            <button
              onClick={() => setSearchText("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ── Scope (All / Local / External) ── */}
      <div className="space-y-2">
        <SectionHeading icon={Home}>Scope</SectionHeading>
        <Segmented
          value={filters.subnetScope}
          onChange={(v) => setFilters({ subnetScope: v })}
          options={[
            { value: "all", label: "All" },
            { value: "local", label: localSubnet ? `Local (${localSubnet.split("/")[0]})` : "Local" },
            { value: "external", label: "External" },
          ]}
        />
      </div>

      {/* ── IP / Device ── */}
      <div className="space-y-2">
        <SectionHeading icon={Globe}>IP / Device</SectionHeading>
        <Segmented
          value={ipMode}
          onChange={handleIpMode}
          options={[
            { value: "any", label: "Any IP" },
            { value: "custom", label: "Specify" },
          ]}
        />
        {ipMode === "any" ? (
          <div className="relative">
            <input
              type="text"
              value={ipText}
              onChange={(e) => setIpText(e.target.value)}
              placeholder="IP address — src or dst..."
              className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                         border border-zinc-700 focus:border-blue-500 focus:outline-none
                         placeholder:text-zinc-500 font-mono"
            />
            {selectedNodeId && (
              <button
                onClick={() => setIpText(selectedNodeId)}
                title={`Use selected node: ${selectedNodeId}`}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px]
                           bg-blue-600/80 hover:bg-blue-600 text-white rounded"
              >
                use node
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">Src IP</span>
              <div className="relative">
                <input
                  type="text"
                  value={srcIpText}
                  onChange={(e) => setSrcIpText(e.target.value)}
                  placeholder="any"
                  className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                             border border-zinc-700 focus:border-blue-500 focus:outline-none
                             placeholder:text-zinc-500 font-mono"
                />
                {selectedNodeId && (
                  <button
                    onClick={() => setSrcIpText(selectedNodeId)}
                    title={`Use selected node as source: ${selectedNodeId}`}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 px-1 py-0.5 text-[9px]
                               bg-blue-600/80 hover:bg-blue-600 text-white rounded"
                  >
                    node
                  </button>
                )}
              </div>
            </div>
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">Dst IP</span>
              <input
                type="text"
                value={dstIpText}
                onChange={(e) => setDstIpText(e.target.value)}
                placeholder="any"
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
          </div>
        )}
        <p className="text-[10px] text-zinc-600">
          Partial is a range: <span className="text-zinc-500 font-mono">192.</span> = all 192.x
        </p>
      </div>

      {/* ── Port ── */}
      <div className="space-y-2">
        <SectionHeading icon={Waypoints}>Port</SectionHeading>
        <Segmented
          value={portMode}
          onChange={handlePortMode}
          options={[
            { value: "any", label: "Any port" },
            { value: "custom", label: "Specify" },
          ]}
        />
        {portMode === "any" ? (
          <input
            type="text"
            inputMode="numeric"
            value={portText}
            onChange={(e) => setPortText(e.target.value)}
            placeholder="Port — src or dst, e.g. 443, 8443"
            className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       placeholder:text-zinc-500 font-mono"
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">Src port</span>
              <input
                type="text"
                inputMode="numeric"
                value={srcPortText}
                onChange={(e) => setSrcPortText(e.target.value)}
                placeholder="any"
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">Dst port</span>
              <input
                type="text"
                inputMode="numeric"
                value={dstPortText}
                onChange={(e) => setDstPortText(e.target.value)}
                placeholder="any"
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
          </div>
        )}
        <p className="text-[10px] text-zinc-600">
          Multiple: <span className="text-zinc-500 font-mono">,</span> ·{" "}
          <span className="text-zinc-500 font-mono">or</span> ·{" "}
          <span className="text-zinc-500 font-mono">||</span> · exact match
        </p>
      </div>

      {/* ── Protocols ── */}
      <div className="space-y-2">
        <SectionHeading icon={Filter}>Protocols</SectionHeading>
        <div className="flex flex-wrap gap-1.5">
          {availableProtocols.map((proto) => {
            const style = getProtocolStyle(proto);
            const isIncluded = filters.protocols.includes(proto);
            const isExcluded = filters.excludedProtocols.includes(proto);
            return (
              <button
                key={proto}
                onClick={() => cycleProtocol(proto)}
                title={
                  isIncluded
                    ? `${proto}: included — click to exclude`
                    : isExcluded
                      ? `${proto}: excluded — click to reset`
                      : `${proto}: click to include`
                }
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                  isIncluded && [style.active, "text-white shadow-lg"],
                  isExcluded && [
                    "bg-rose-900/60 text-rose-300 border border-rose-700",
                    "line-through opacity-80 hover:opacity-100",
                  ],
                  !isIncluded && !isExcluded && [style.bg, style.text, "hover:brightness-125"],
                )}
              >
                {isIncluded && <Check className="h-3 w-3" />}
                {isExcluded && <X className="h-3 w-3" />}
                {proto}
              </button>
            );
          })}
        </div>
        {(filters.protocols.length > 0 || filters.excludedProtocols.length > 0) && (
          <p className="text-[10px] text-zinc-600">
            Click a chip to cycle: include → <span className="text-rose-400">exclude</span> → off
          </p>
        )}
      </div>

      {/* ── Quick recipes ── */}
      <div className="space-y-2">
        <SectionHeading icon={ShieldAlert}>Quick Filters</SectionHeading>
        <div className="flex flex-wrap gap-1.5">
          {recipes.map((r) => (
            <button
              key={r.label}
              onClick={r.apply}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                r.active
                  ? "bg-blue-600 text-white shadow-lg"
                  : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
              )}
            >
              <r.icon className="h-3 w-3" />
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Isolate + Reset ── */}
      <div className="space-y-1.5 pt-1">
        <button
          onClick={() => {
            if (selectedNodeId) {
              setIsolatedNode(selectedNodeId);
            }
          }}
          disabled={!selectedNodeId}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all",
            filters.isolatedNodeId
              ? "bg-amber-600 text-white hover:bg-amber-500"
              : selectedNodeId
                ? "bg-zinc-800 text-zinc-200 hover:bg-zinc-700"
                : "bg-zinc-800/50 text-zinc-500 cursor-not-allowed",
          )}
        >
          <Crosshair className="h-3.5 w-3.5" />
          {filters.isolatedNodeId
            ? `Isolating: ${filters.isolatedNodeId}`
            : "Isolate Selected Node"}
        </button>

        {hasActiveFilters && (
          <button
            onClick={() => {
              setFilters({
                protocols: [],
                excludedProtocols: [],
                isolatedNodeId: null,
                ip: "",
                srcIp: "",
                dstIp: "",
                subnetScope: "all",
                port: "",
                srcPort: "",
                dstPort: "",
                search: "",
                synOnly: false,
              });
              setFollowedStream(null);
              setSearchText("");
              setIpText("");
              setSrcIpText("");
              setDstIpText("");
              setPortText("");
              setSrcPortText("");
              setDstPortText("");
              setIpMode("any");
              setPortMode("any");
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium
                       bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-all"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Clear All Filters
          </button>
        )}
      </div>
    </div>
  );
}
