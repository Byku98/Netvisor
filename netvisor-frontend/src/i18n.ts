/**
 * i18n — English / Polish.
 *
 * Rules:
 * - Anonymous users: system language (navigator.language starts with "pl" → Polish).
 * - Choice persists in localStorage ("netvisor-lang") across login/logout.
 * - Server-side per-account preference would need a users-table column +
 *   an endpoint — tracked as follow-up in the TODO.
 */
import { create } from "zustand";

export type Lang = "en" | "pl";

const dict = {
  en: {
    // Header
    debug: "Debug",
    newSession: "New Session",
    mySessions: "My Sessions",
    logout: "Logout",
    signIn: "Sign In",

    // Upload screen
    heroTitle: "Network Topology Visualization",
    heroSubtitle: "Upload a PCAP file to generate an interactive network map",
    dropHere: "Drop to analyze new PCAP",
    dropzoneTitle: "Drag & drop a .pcap / .pcapng file",
    dropzoneHint: "or click to select (max {size})",
    upToSize: "Up to {size}",
    fileTooLarge: "file too large",
    parsing: "Parsing PCAP file...",
    dropHereActive: "Drop the file here...",
    footerTagline: "Interactive network topology visualization from PCAP files",

    // Filter panel
    filters: "Filters",
    search: "Search",
    searchPlaceholder: "In packet info...",
    ipAnyPlaceholder: "IP address — src or dst...",
    anyPlaceholder: "any",
    useNode: "use node",
    clickToFilterIp: "Click to filter by this IP (Any IP field)",
    clickToFilterProto: "Show only this protocol (click)",
    clickFilterSrcIp: "Show only packets from this source (Specify → Src IP)",
    clickFilterDstIp: "Show only packets to this destination (Specify → Dst IP)",
    clickFilterSrcPort: "Show only packets with this source port (Specify → Src port)",
    clickFilterDstPort: "Show only packets with this destination port (Specify → Dst port)",
    scope: "Scope",
    all: "All",
    local: "Local",
    external: "External",
    ipDevice: "IP / Device",
    anyIp: "Any IP",
    specify: "Specify",
    srcIp: "Src IP",
    dstIp: "Dst IP",
    ipHint: "Partial is a range: 192. = all 192.x · bare number = any octet: 117 = x.x.x.117 too",
    port: "Port",
    portAnyPlaceholder: "Port — src or dst, e.g. 443, 8443",
    anyPort: "Any port",
    srcPort: "Src port",
    dstPort: "Dst port",
    portHint: "Multiple: , or || · exact match",
    protocols: "Protocols",
    protoModeAll: "All",
    protoModeInclude: "Include",
    protoModeExclude: "Exclude",
    protoHintInclude: "Show only the selected protocols",
    protoHintExclude: "Hide the selected protocols",
    protocolHint: "Click a chip to cycle: include → exclude → off",
    quickFilters: "Quick Filters",

    presetPlaintext: "Unencrypted passwords",
    presetPlaintextDesc:
      "Shows HTTP, FTP, SMTP and Telnet — protocols that send usernames and passwords unencrypted. Anything here is readable by anyone on the path.",
    presetHideNoise: "Hide noise",
    presetHideNoiseDesc:
      "Hides ARP, DHCP, mDNS and SSDP — the background chatter every device constantly emits. What remains is actual conversations between hosts.",
    presetPortScans: "Port scans",
    presetPortScansDesc:
      "Shows TCP connection attempts (SYN) that never got an answer — typical of port scans, or hosts/services that are down.",
    presetRejected: "Rejected (RST)",
    presetRejectedDesc:
      "Shows TCP resets — connections that were refused by the target or a firewall, or aborted mid-conversation.",

    applyFilters: "Apply Filters",
    filtersApplied: "Filters Applied",
    clearAll: "Clear All Filters",

    // Context strip
    layoutForceTitle: "Force",
    layoutForceDesc:
      "physics-based — connected nodes attract, all nodes repel; densely connected nodes group together",
    layoutDagreTitle: "Dagre",
    layoutDagreDesc:
      "hierarchical top-down — best for spotting flow direction between hosts",
    weightsTitle: "Weights",
    weightsLegend:
      "edge labels = packet count · color gray → blue → amber = busiest link · node labels show totals",

    // GraphControls
    graph: "Graph",
    packets: "Packets",
    layout: "Layout:",
    weights: "Weights",
    legend: "Legend",
    pastSessions: "Past Sessions",

    // Sessions
    sessions: "Sessions",
    loadingSessions: "Loading sessions...",
    noSessions: "No sessions yet",
    noSessionsHint: "Upload a PCAP file to create your first session",
    uploadPcap: "Upload PCAP",
    pleaseSignIn: "Please sign in to view your sessions.",
    deleteConfirm: "Delete this session and all its data?",
    load: "Load",
  },
  pl: {
    debug: "Debug",
    newSession: "Nowa sesja",
    mySessions: "Moje sesje",
    logout: "Wyloguj",
    signIn: "Zaloguj się",

    heroTitle: "Wizualizacja topologii sieci",
    heroSubtitle: "Wgraj plik PCAP, aby wygenerować interaktywną mapę sieci",
    dropHere: "Upuść, aby przeanalizować nowy PCAP",
    dropzoneTitle: "Przeciągnij i upuść plik .pcap / .pcapng",
    dropzoneHint: "lub kliknij, aby wybrać (max {size})",
    upToSize: "Do {size}",
    fileTooLarge: "plik za duży",
    parsing: "Wczytywanie pliku PCAP...",
    dropHereActive: "Upuść plik tutaj...",
    footerTagline: "Interaktywna wizualizacja topologii sieci z plików PCAP",

    filters: "Filtry",
    search: "Szukaj",
    searchPlaceholder: "W info pakietu...",
    ipAnyPlaceholder: "Adres IP — źródłowy lub docelowy...",
    anyPlaceholder: "dowolny",
    useNode: "wstaw węzeł",
    clickToFilterIp: "Kliknij, aby filtrować tym adresem IP (pole Dowolne IP)",
    clickToFilterProto: "Pokaż tylko ten protokół (kliknij)",
    clickFilterSrcIp: "Pokaż tylko pakiety z tego źródła (Określ → IP źródł.)",
    clickFilterDstIp: "Pokaż tylko pakiety do tego celu (Określ → IP celu)",
    clickFilterSrcPort: "Pokaż tylko pakiety z tego portu źródłowego (Określ → Port źródł.)",
    clickFilterDstPort: "Pokaż tylko pakiety z tego portu docelowego (Określ → Port celu)",
    scope: "Zakres",
    all: "Wszystko",
    local: "Lokalne",
    external: "Zewnętrzne",
    ipDevice: "IP / Urządzenie",
    anyIp: "Dowolne IP",
    specify: "Określ",
    srcIp: "IP źródł.",
    dstIp: "IP celu",
    ipHint: "Fragment to zakres: 192. = całe 192.x · sama liczba = dowolny oktet: 117 = też x.x.x.117",
    port: "Port",
    portAnyPlaceholder: "Port — źródł. lub cel, np. 443, 8443",
    anyPort: "Dowolny port",
    srcPort: "Port źródł.",
    dstPort: "Port celu",
    portHint: "Kilka: , lub || · dokładne dopasowanie",
    protocols: "Protokoły",
    protoModeAll: "Wszystkie",
    protoModeInclude: "Uwzględnij",
    protoModeExclude: "Wyklucz",
    protoHintInclude: "Pokazuj tylko zaznaczone protokoły",
    protoHintExclude: "Ukryj zaznaczone protokoły",
    protocolHint: "Klikaj chip: uwzględnij → wyklucz → wyłącz",
    quickFilters: "Szybkie filtry",

    presetPlaintext: "Hasła bez szyfrowania",
    presetPlaintextDesc:
      "Pokazuje HTTP, FTP, SMTP i Telnet — protokoły wysyłające loginy i hasła bez szyfrowania. Widoczne tu dane może odczytać każdy na trasie.",
    presetHideNoise: "Ukryj szum",
    presetHideNoiseDesc:
      "Ukrywa ARP, DHCP, mDNS i SSDP — ciągły szum tła emitowany przez każde urządzenie. Zostają właściwe rozmowy między hostami.",
    presetPortScans: "Skanowanie portów",
    presetPortScansDesc:
      "Pokazuje próby połączeń TCP (SYN) bez odpowiedzi — typowe dla skanowania portów albo niedostępnych hostów/usług.",
    presetRejected: "Odrzucone (RST)",
    presetRejectedDesc:
      "Pokazuje resety TCP — połączenia odrzucone przez cel lub zaporę, albo przerwane w trakcie.",

    applyFilters: "Zastosuj filtry",
    filtersApplied: "Filtry zastosowane",
    clearAll: "Wyczyść filtry",

    layoutForceTitle: "Force",
    layoutForceDesc:
      "fizyczny — połączone węzły się przyciągają, wszystkie się odpychają; gęsto połączone węzły tworzą skupiska",
    layoutDagreTitle: "Dagre",
    layoutDagreDesc:
      "hierarchiczny z góry na dół — najlepszy do śledzenia kierunku przepływu między hostami",
    weightsTitle: "Wagi",
    weightsLegend:
      "etykiety krawędzi = liczba pakietów · kolor szary → niebieski → bursztynowy = najruchliwsze połączenie · etykiety węzłów pokazują sumy",

    graph: "Graf",
    packets: "Pakiety",
    layout: "Układ:",
    weights: "Wagi",
    legend: "Legenda",
    pastSessions: "Poprzednie sesje",

    sessions: "Sesje",
    loadingSessions: "Wczytywanie sesji...",
    noSessions: "Brak sesji",
    noSessionsHint: "Wgraj plik PCAP, aby utworzyć pierwszą sesję",
    uploadPcap: "Wgraj PCAP",
    pleaseSignIn: "Zaloguj się, aby zobaczyć swoje sesje.",
    deleteConfirm: "Usunąć tę sesję i wszystkie jej dane?",
    load: "Wczytaj",
  },
} as const;

export type TKey = keyof typeof dict.en;

function systemLang(): Lang {
  try {
    return navigator.language?.toLowerCase().startsWith("pl") ? "pl" : "en";
  } catch {
    return "en";
  }
}

function initialLang(): Lang {
  const saved = localStorage.getItem("netvisor-lang");
  if (saved === "en" || saved === "pl") return saved;
  return systemLang();
}

interface I18nState {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Translate a key in the current language. */
  t: (key: TKey) => string;
}

export const useI18n = create<I18nState>()((set, get) => ({
  lang: initialLang(),
  setLang: (lang) => {
    localStorage.setItem("netvisor-lang", lang);
    set({ lang });
  },
  t: (key) => dict[get().lang][key] ?? dict.en[key] ?? key,
}));
