import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { useAuthStore } from "@/stores/auth.store";
import { App } from "./App";

// Deploy guard: a prod bundle built without VITE_API_URL falls back to "/api",
// which only works under the Vite dev proxy — on netvisor.tomaszbyczek.pl it
// 404s every API call (the backend lives under /backend). Fail loudly here
// instead of mysteriously in the Network tab.
const apiBase = import.meta.env.VITE_API_URL ?? "/api";
if (apiBase === "/api" && !window.location.hostname.startsWith("localhost")) {
  // eslint-disable-next-line no-console
  console.error(
    "[NetVisor] This bundle was built without VITE_API_URL — API calls target " +
      window.location.origin +
      "/api and will 404. Rebuild with MSYS_NO_PATHCONV=1 VITE_API_URL=/backend/api and redeploy the dist.",
  );
}
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

/** API base — same pattern as api modules (Vite proxy locally, /backend/api in prod). */
const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

/** Wrapper that checks auth state on mount. */
function AppWithAuth() {
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  return <App />;
}

/**
 * Boot: fetch public runtime config (Google client ID) from the backend,
 * then mount the app. Works identically for localhost (Vite proxy) and
 * production (same bundle, different API base) — no build-time client ID.
 */
async function boot() {
  let googleClientId = "";
  try {
    const res = await fetch(`${API_BASE}/config`);
    if (res.ok) {
      const cfg = await res.json();
      googleClientId = cfg.googleClientId ?? "";
    }
  } catch {
    // Backend unreachable — app still renders; Google button just won't work.
  }

  const root = document.getElementById("root");
  if (!root) throw new Error("Root element not found");

  const appTree = (
    <QueryClientProvider client={queryClient}>
      <AppWithAuth />
    </QueryClientProvider>
  );

  createRoot(root).render(
    <StrictMode>
      {googleClientId ? (
        <GoogleOAuthProvider clientId={googleClientId}>{appTree}</GoogleOAuthProvider>
      ) : (
        appTree
      )}
    </StrictMode>,
  );
}

void boot();
