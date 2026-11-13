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
    loadPcapHint: "Load a PCAP to enable filters",
    appliedFilter: "Applied filter",
    notInCapture: "Not present in this capture",

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
    presetWebBrowsing: "Web browsing",
    presetWebBrowsingDesc:
      "Shows DNS lookups, HTTP requests and TLS connections — the everyday traffic behind opening a website. Everything else drops away.",

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

    // AI assistant panel
    aiAssistant: "AI Assistant",
    aiEnterpriseBadge: "Enterprise AI",
    aiLoadFirst: "Load a capture first.",
    aiSignInNeeded: "No personal key provided — sign in and add your key to chat.",
    aiNoKey: "No enterprise key configured. Provide your own key to use the AI assistant.",
    aiEnterpriseOnly: "AI is provided by the enterprise key. Contact the administrator.",
    aiConfigError: "Could not load the AI configuration.",
    aiSettings: "AI Settings",
    aiOpenSettings: "Open AI Settings",
    aiBack: "Back",
    aiBackToChat: "Back to chat",
    aiKeySaved: "Key saved.",
    aiProviderLabel: "Provider",
    aiProviderAnthropic: "Anthropic",
    aiProviderOpenAICompat: "OpenAI-compatible",
    aiBaseUrl: "Base URL",
    aiModel: "Model",
    aiModelPlaceholder: "Select model…",
    aiModelManual: "Paste model manually",
    aiModelFromList: "Select from list",
    aiApiKey: "API key",
    aiApiKeyStored: "Stored key: {masked}",
    aiConnect: "Connect",
    aiConnecting: "Connecting...",
    aiConnectAuthFailed: "Authentication failed — check the API key.",
    aiConnectFailed: "Could not reach the provider — check the Base URL.",
    aiModelsFound: "{n} models found",
    aiSave: "Save",
    aiSaving: "Saving...",
    aiRemoveKey: "Remove key",
    aiRemoveKeyConfirm: "Remove your personal API key?",
    aiInputPlaceholder: "Ask about this capture...",
    aiSend: "Send",
    aiThinking: "Thinking...",
    aiTokens: "tokens",
    aiRateLimit: "{n}/{m} questions (15 min)",
    aiRateLimitHit: "Rate limit reached — try again in {seconds}s.",
    aiKeyStoredKeep: "Key stored — leave empty to keep",
    aiRefreshModels: "Refresh model list",
    aiPriceIn: "Price in ($ / 1M tokens)",
    aiPriceOut: "Price out ($ / 1M tokens)",
    aiUsage: "Usage",
    aiUsageMessages: "Messages",
    aiUsageTokensIn: "Tokens in",
    aiUsageTokensOut: "Tokens out",
    aiUsageCost: "≈$ cost",
    aiUsageMsgCount: "{n} messages",
    aiUsageMsgOne: "{n} message",
    aiUsageEmpty: "No usage yet.",
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
    loadPcapHint: "Wgraj plik PCAP, aby włączyć filtry",
    appliedFilter: "Zastosowany filtr",
    notInCapture: "Brak w tym nagraniu",

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
    presetWebBrowsing: "Przeglądanie WWW",
    presetWebBrowsingDesc:
      "Pokazuje zapytania DNS, ruch HTTP i połączenia TLS — codzienny ruch towarzyszący otwieraniu stron. Wszystko inne znika.",

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

    // AI assistant panel
    aiAssistant: "Asystent AI",
    aiEnterpriseBadge: "AI firmowy",
    aiLoadFirst: "Najpierw wczytaj plik przechwytywania.",
    aiSignInNeeded: "Brak osobistego klucza — zaloguj się i dodaj klucz.",
    aiNoKey: "Brak klucza firmowego. Aby korzystać z asystenta AI, dodaj własny klucz.",
    aiEnterpriseOnly: "AI jest udostępniane kluczem firmowym. Skontaktuj się z administratorem.",
    aiConfigError: "Nie udało się wczytać konfiguracji AI.",
    aiSettings: "Ustawienia AI",
    aiOpenSettings: "Otwórz ustawienia AI",
    aiBack: "Wróć",
    aiBackToChat: "Wróć do czatu",
    aiKeySaved: "Klucz zapisany.",
    aiProviderLabel: "Dostawca",
    aiProviderAnthropic: "Anthropic",
    aiProviderOpenAICompat: "Zgodny z OpenAI",
    aiBaseUrl: "Adres bazowy (Base URL)",
    aiModel: "Model",
    aiModelPlaceholder: "Wybierz model…",
    aiModelManual: "Wklej model ręcznie",
    aiModelFromList: "Wybierz z listy",
    aiApiKey: "Klucz API",
    aiApiKeyStored: "Zapisany klucz: {masked}",
    aiConnect: "Połącz",
    aiConnecting: "Łączenie...",
    aiConnectAuthFailed: "Uwierzytelnianie nie powiodło się — sprawdź klucz API.",
    aiConnectFailed: "Nie można połączyć się z dostawcą — sprawdź Base URL.",
    aiModelsFound: "Znaleziono {n} modeli",
    aiSave: "Zapisz",
    aiSaving: "Zapisywanie...",
    aiRemoveKey: "Usuń klucz",
    aiRemoveKeyConfirm: "Usunąć osobisty klucz API?",
    aiInputPlaceholder: "Zapytaj o to przechwytywanie...",
    aiSend: "Wyślij",
    aiThinking: "Myślę...",
    aiTokens: "tokenów",
    aiRateLimit: "{n}/{m} pytań (15 min)",
    aiRateLimitHit: "Osiągnięto limit — spróbuj ponownie za {seconds} s.",
    aiKeyStoredKeep: "Klucz zapisany — zostaw puste, aby zachować",
    aiRefreshModels: "Odśwież listę modeli",
    aiPriceIn: "Cena wej. ($ / 1M tokenów)",
    aiPriceOut: "Cena wyj. ($ / 1M tokenów)",
    aiUsage: "Użycie",
    aiUsageMessages: "Wiadomości",
    aiUsageTokensIn: "Tokeny wej.",
    aiUsageTokensOut: "Tokeny wyj.",
    aiUsageCost: "≈$ koszt",
    aiUsageMsgCount: "{n} wiadomości",
    aiUsageMsgOne: "{n} wiadomość",
    aiUsageEmpty: "Brak użycia.",
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
