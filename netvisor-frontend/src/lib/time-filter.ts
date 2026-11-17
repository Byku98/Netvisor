/**
 * Time-filter helpers — the capture clock is UTC (the packet table shows UTC,
 * so the filter panel's clock inputs mean UTC too).
 *
 * Anchor resolution: a clock-only input ("HH:MM:SS[.mmm]") is resolved against
 * the capture's start DATE — multi-day captures are out of scope by design.
 */

/** Parse "HH:MM[:SS[.fff…]]" into seconds-of-day; null when malformed. */
export function parseClockText(text: string): number | null {
  const m = /^(\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:\.(\d{1,6}))?)?$/.exec(text.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  const s = Number(m[3] ?? "0");
  const frac = m[4] ? Number(`0.${m[4]}`) : 0;
  if (h > 23 || min > 59 || s > 59) return null;
  return h * 3600 + min * 60 + s + frac;
}

/** Format epoch seconds as a UTC clock "HH:MM:SS" (+ ".mmm" only when fractional). */
export function formatClock(epochSec: number): string {
  const totalMs = Math.round(epochSec * 1000);
  const d = new Date(totalMs);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  const ss = String(d.getUTCSeconds()).padStart(2, "0");
  const ms = ((totalMs % 1000) + 1000) % 1000;
  const frac = ms > 0 ? `.${String(ms).padStart(3, "0").replace(/0+$/, "")}` : "";
  return `${hh}:${mm}:${ss}${frac}`;
}

/**
 * Resolve a seconds-of-day clock against the capture start's UTC date →
 * epoch seconds. Falls back to today's UTC date when the capture start is
 * unknown or unparseable.
 */
export function resolveAnchorEpoch(
  clockSec: number,
  captureStartIso: string | null | undefined,
): number {
  let start = captureStartIso ? new Date(captureStartIso) : new Date();
  if (Number.isNaN(start.getTime())) start = new Date();
  const midnight = Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate());
  return midnight + clockSec;
}

/** Format an ISO 8601 datetime as a UTC clock (raw string when unparseable). */
export function formatIsoClock(iso: string): string {
  const ms = new Date(iso).getTime();
  return Number.isFinite(ms) ? formatClock(ms / 1000) : iso;
}
