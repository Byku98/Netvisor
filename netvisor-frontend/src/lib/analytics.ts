/**
 * GA4 visitor analytics — demo-only, env-gated via the backend.
 *
 * GET /api/config surfaces `ga4MeasurementId` ONLY when the deployment's
 * operator set it (the public demo). Empty/absent (every self-hosted or
 * Docker deployment, and older backends without the field) = analytics OFF:
 * nothing is injected, no request to googletagmanager.com is ever made,
 * zero trace in the served page.
 */

/** GA4 measurement IDs look like "G-XXXXXXXXXX" — defensive against junk in env. */
const GA4_ID_PATTERN = /^G-[A-Z0-9]+$/;

/** Guard against double injection (boot runs once, but stay idempotent). */
let initialized = false;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

/**
 * Inject the standard GA4 gtag snippet when — and only when — the backend
 * serves a well-formed Measurement ID. Idempotent: only the first valid
 * call has any effect; empty/missing/malformed IDs are a silent no-op.
 */
export function initAnalytics(measurementId: string | undefined): void {
  if (initialized) return;
  if (!measurementId || !GA4_ID_PATTERN.test(measurementId)) return;
  initialized = true;

  // Standard GA4 snippet, step 1: async gtag.js loader.
  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
  document.head.appendChild(script);

  // Standard GA4 snippet, step 2: gtag bootstrap — gtag() only queues its
  // arguments onto dataLayer; gtag.js drains the queue when it arrives.
  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args: unknown[]) => {
    window.dataLayer?.push(args);
  };
  window.gtag("js", new Date());
  window.gtag("config", measurementId);
}
