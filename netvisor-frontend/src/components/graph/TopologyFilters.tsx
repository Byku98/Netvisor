import { useState } from "react";
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
  Ban,
} from "lucide-react";
import { useUiStore } from "@/stores/ui.store";
import { useI18n } from "@/i18n";
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
            "flex-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all active:scale-[0.97]",
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
  const { t } = useI18n();
  const toggleProtocol = useUiStore((s) => s.toggleProtocol);
  const setFilters = useUiStore((s) => s.setFilters);
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
    filters.rstOnly;

  // ── Any / Specify modes (UI-only concept; store stays value-driven) ──
  const [ipMode, setIpMode] = useState<"any" | "custom">(
    filters.srcIp || filters.dstIp ? "custom" : "any",
  );
  const [portMode, setPortMode] = useState<"any" | "custom">(
    filters.srcPort || filters.dstPort ? "custom" : "any",
  );
  const [protoMode, setProtoMode] = useState<"all" | "include" | "exclude">(
    filters.protocols.length > 0 ? "include" : filters.excludedProtocols.length > 0 ? "exclude" : "all",
  );

  // ── Local input state (drafts — applied on Apply / Enter, NOT live) ──
  const [searchText, setSearchText] = useState(filters.search);
  const [ipText, setIpText] = useState(filters.ip);
  const [srcIpText, setSrcIpText] = useState(filters.srcIp);
  const [dstIpText, setDstIpText] = useState(filters.dstIp);
  const [portText, setPortText] = useState(filters.port);
  const [srcPortText, setSrcPortText] = useState(filters.srcPort);
  const [dstPortText, setDstPortText] = useState(filters.dstPort);

  // The filter values that WOULD be applied right now, given the current
  // drafts + mode. "Any" mode feeds the either-side ip/port fields,
  // "Specify" the src/dst pairs — the inactive set is always cleared.
  const draftValues = {
    search: searchText.trim(),
    ip: ipMode === "any" ? ipText.trim() : "",
    srcIp: ipMode === "custom" ? srcIpText.trim() : "",
    dstIp: ipMode === "custom" ? dstIpText.trim() : "",
    port: portMode === "any" ? portText.trim() : "",
    srcPort: portMode === "custom" ? srcPortText.trim() : "",
    dstPort: portMode === "custom" ? dstPortText.trim() : "",
  };

  // Commit the drafts — the ONLY path from typing to the graph/packets
  const applyFilters = () => setFilters(draftValues);

  // Dirty = drafts differ from the applied store values (drives the Apply button)
  const isDirty =
    draftValues.search !== filters.search ||
    draftValues.ip !== filters.ip ||
    draftValues.srcIp !== filters.srcIp ||
    draftValues.dstIp !== filters.dstIp ||
    draftValues.port !== filters.port ||
    draftValues.srcPort !== filters.srcPort ||
    draftValues.dstPort !== filters.dstPort;

  /** Enter key in any text input applies the filters. */
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") applyFilters();
  };

  /** Switch IP mode; clears the deactivated side's drafts (applied on Apply). */
  const handleIpMode = (mode: "any" | "custom") => {
    setIpMode(mode);
    if (mode === "any") {
      setSrcIpText("");
      setDstIpText("");
    } else {
      setIpText("");
    }
  };

  /** Switch protocol mode; clears the list the mode deactivates. */
  const handleProtoMode = (mode: "all" | "include" | "exclude") => {
    setProtoMode(mode);
    if (mode === "all") {
      setFilters({ protocols: [], excludedProtocols: [] });
    } else if (mode === "include") {
      setFilters({ excludedProtocols: [] });
    } else {
      setFilters({ protocols: [] });
    }
  };

  /** Chip click in the current protocol mode — one click, one meaning. */
  const handleProtoChip = (proto: string) => {
    if (protoMode === "include") {
      toggleProtocol(proto); // toggles on AND off
    } else if (protoMode === "exclude") {
      const cur = filters.excludedProtocols;
      setFilters({
        excludedProtocols: cur.includes(proto)
          ? cur.filter((x) => x !== proto)
          : [...cur, proto],
      });
    }
  };

  /** Switch port mode; clears whichever side is being deactivated. */
  const handlePortMode = (mode: "any" | "custom") => {
    setPortMode(mode);
    if (mode === "any") {
      setSrcPortText("");
      setDstPortText("");
    } else {
      setPortText("");
    }
  };

  // ── Quick recipes ─────────────────────────────────────────────
  // Only presets that combine DIFFERENT filter kinds earn a button here —
  // anything reachable with one control (scope, single protocol chip) stays out.
  const _NOISE_PROTOCOLS = ["ARP", "DHCP", "MDNS", "SSDP"];
  const recipes: Array<{
    label: string;
    description: string;
    icon: typeof Filter;
    apply: () => void;
    active: boolean;
  }> = [
    {
      label: t("presetPlaintext"),
      description: t("presetPlaintextDesc"),
      icon: MailOpen,
      active:
        filters.protocols.length === 4 &&
        ["http", "ftp", "smtp", "telnet"].every((p) =>
          filters.protocols.some((x) => x.toLowerCase() === p),
        ),
      apply: () => {
        const isOn =
          filters.protocols.length === 4 &&
          ["http", "ftp", "smtp", "telnet"].every((p) =>
            filters.protocols.some((x) => x.toLowerCase() === p),
          );
        setFilters({
          protocols: isOn ? [] : ["HTTP", "FTP", "SMTP", "TELNET"],
          excludedProtocols: [],
        });
        setProtoMode("include");
      },
    },
    {
      label: t("presetHideNoise"),
      description: t("presetHideNoiseDesc"),
      icon: ShieldAlert,
      active:
        _NOISE_PROTOCOLS.every((p) => filters.excludedProtocols.includes(p)) &&
        filters.protocols.length === 0,
      apply: () => {
        const isOn =
          _NOISE_PROTOCOLS.every((p) => filters.excludedProtocols.includes(p)) &&
          filters.protocols.length === 0;
        setFilters({
          protocols: [],
          excludedProtocols: isOn ? [] : [..._NOISE_PROTOCOLS],
        });
        setProtoMode("exclude");
      },
    },
    {
      label: t("presetPortScans"),
      description: t("presetPortScansDesc"),
      icon: Crosshair,
      active: filters.synOnly,
      apply: () => setFilters({ synOnly: !filters.synOnly }),
    },
    {
      label: t("presetRejected"),
      description: t("presetRejectedDesc"),
      icon: Ban,
      active: filters.rstOnly,
      apply: () => setFilters({ rstOnly: !filters.rstOnly }),
    },
  ];

  // Empty state: no protocols
  if (availableProtocols.length === 0) {
    return (
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          {t("filters")}
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
          {t("filters")}
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
                (filters.rstOnly ? 1 : 0)
              )}
            </span>
          )}
        </h4>
      </div>

      {/* ── Search ── */}
      <div className="space-y-2">
        <SectionHeading icon={Search}>{t("search")}</SectionHeading>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
 onKeyDown={handleInputKeyDown}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg pl-8 pr-7 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       placeholder:text-zinc-500"
          />
          {searchText && (
            <button
              onClick={() => setSearchText("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors active:scale-90"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ── Scope (All / Local / External) ── */}
      <div className="space-y-2">
        <SectionHeading icon={Home}>{t("scope")}</SectionHeading>
        <Segmented
          value={filters.subnetScope}
          onChange={(v) => setFilters({ subnetScope: v })}
          options={[
            { value: "all", label: t("all") },
            { value: "local", label: localSubnet ? `${t("local")} (${localSubnet.split("/")[0]})` : t("local") },
            { value: "external", label: t("external") },
          ]}
        />
      </div>

      {/* ── IP / Device ── */}
      <div className="space-y-2">
        <SectionHeading icon={Globe}>{t("ipDevice")}</SectionHeading>
        <Segmented
          value={ipMode}
          onChange={handleIpMode}
          options={[
            { value: "any", label: t("anyIp") },
            { value: "custom", label: t("specify") },
          ]}
        />
        {ipMode === "any" ? (
          <div className="relative">
            <input
              type="text"
 onKeyDown={handleInputKeyDown}
              value={ipText}
              onChange={(e) => setIpText(e.target.value)}
              placeholder={t("ipAnyPlaceholder")}
              className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                         border border-zinc-700 focus:border-blue-500 focus:outline-none
                         placeholder:text-zinc-500 font-mono"
            />
            {selectedNodeId && (
              <button
                onClick={() => setIpText(selectedNodeId)}
                title={`Use selected node: ${selectedNodeId}`}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px]
                           bg-blue-600/80 hover:bg-blue-600 text-white rounded transition-colors active:scale-95"
              >
                {t("useNode")}
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">{t("srcIp")}</span>
              <input
                type="text"
 onKeyDown={handleInputKeyDown}
                value={srcIpText}
                onChange={(e) => setSrcIpText(e.target.value)}
                placeholder={t("anyPlaceholder")}
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">{t("dstIp")}</span>
              <input
                type="text"
 onKeyDown={handleInputKeyDown}
                value={dstIpText}
                onChange={(e) => setDstIpText(e.target.value)}
                placeholder={t("anyPlaceholder")}
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
          </div>
        )}
        <p className="text-[10px] text-zinc-600">
          {t("ipHint")}
        </p>
      </div>

      {/* ── Port ── */}
      <div className="space-y-2">
        <SectionHeading icon={Waypoints}>{t("port")}</SectionHeading>
        <Segmented
          value={portMode}
          onChange={handlePortMode}
          options={[
            { value: "any", label: t("anyPort") },
            { value: "custom", label: t("specify") },
          ]}
        />
        {portMode === "any" ? (
          <input
            type="text"
 onKeyDown={handleInputKeyDown}
            inputMode="numeric"
            value={portText}
            onChange={(e) => setPortText(e.target.value)}
            placeholder={t("portAnyPlaceholder")}
            className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                       border border-zinc-700 focus:border-blue-500 focus:outline-none
                       placeholder:text-zinc-500 font-mono"
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">{t("srcPort")}</span>
              <input
                type="text"
 onKeyDown={handleInputKeyDown}
                inputMode="numeric"
                value={srcPortText}
                onChange={(e) => setSrcPortText(e.target.value)}
                placeholder={t("anyPlaceholder")}
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
            <div>
              <span className="block text-[10px] text-zinc-500 mb-1">{t("dstPort")}</span>
              <input
                type="text"
 onKeyDown={handleInputKeyDown}
                inputMode="numeric"
                value={dstPortText}
                onChange={(e) => setDstPortText(e.target.value)}
                placeholder={t("anyPlaceholder")}
                className="w-full bg-zinc-800 text-zinc-200 text-xs rounded-lg px-2.5 py-2
                           border border-zinc-700 focus:border-blue-500 focus:outline-none
                           placeholder:text-zinc-500 font-mono"
              />
            </div>
          </div>
        )}
        <p className="text-[10px] text-zinc-600">
          {t("portHint")}
        </p>
      </div>

      {/* ── Protocols ── */}
      <div className="space-y-2">
        <SectionHeading icon={Filter}>{t("protocols")}</SectionHeading>
        <Segmented
          value={protoMode}
          onChange={handleProtoMode}
          options={[
            { value: "all", label: t("protoModeAll") },
            { value: "include", label: t("protoModeInclude") },
            { value: "exclude", label: t("protoModeExclude") },
          ]}
        />
        {protoMode !== "all" && (
          <>
            <div className="flex flex-wrap gap-1.5">
              {availableProtocols.map((proto) => {
                const style = getProtocolStyle(proto);
                const active =
                  protoMode === "include"
                    ? filters.protocols.includes(proto)
                    : filters.excludedProtocols.includes(proto);
                return (
                  <button
                    key={proto}
                    onClick={() => handleProtoChip(proto)}
                    title={
                      protoMode === "include"
                        ? `${proto}: ${active ? "stop filtering by this" : "show only this"}`
                        : `${proto}: ${active ? "stop hiding this" : "hide this"}`
                    }
                    className={cn(
                      "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all active:scale-[0.95]",
                      active && protoMode === "include" && [style.active, "text-white shadow-lg"],
                      active && protoMode === "exclude" && [
                        "bg-rose-900/60 text-rose-300 border border-rose-700",
                        "line-through",
                      ],
                      !active && [style.bg, style.text, "hover:brightness-125"],
                    )}
                  >
                    {active && protoMode === "include" && <Check className="h-3 w-3" />}
                    {active && protoMode === "exclude" && <X className="h-3 w-3" />}
                    {proto}
                  </button>
                );
              })}
            </div>
            <p className="text-[10px] text-zinc-600">
              {protoMode === "include" ? t("protoHintInclude") : t("protoHintExclude")}
            </p>
          </>
        )}
      </div>

      {/* ── Quick recipes ── */}
      <div className="space-y-2">
        <SectionHeading icon={ShieldAlert}>{t("quickFilters")}</SectionHeading>
        <div className="flex flex-wrap gap-1.5">
          {recipes.map((r) => (
            <button
              key={r.label}
              onClick={r.apply}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all active:scale-[0.95]",
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
        {/* Purpose of every active preset — appears after clicking */}
        {recipes
          .filter((r) => r.active)
          .map((r) => (
            <p
              key={r.label}
              className="text-[10px] text-zinc-400 leading-relaxed border-l-2 border-blue-600/60 pl-2"
            >
              <span className="font-medium text-zinc-300">{r.label}:</span> {r.description}
            </p>
          ))}
      </div>

      {/* ── Apply + Reset ── */}
      <div className="space-y-1.5 pt-1">
        <button
          onClick={applyFilters}
          disabled={!isDirty}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.98]",
            isDirty
              ? "bg-blue-600 text-white hover:bg-blue-500 shadow-lg"
              : "bg-zinc-800 text-zinc-500 cursor-not-allowed",
          )}
        >
          <Filter className="h-3.5 w-3.5" />
          {isDirty ? t("applyFilters") : t("filtersApplied")}
        </button>

        {hasActiveFilters && (
          <button
            onClick={() => {
              setFilters({
                protocols: [],
                excludedProtocols: [],
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
              setProtoMode("all");
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium
                       bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-all active:scale-[0.98]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {t("clearAll")}
          </button>
        )}
      </div>
    </div>
  );
}
