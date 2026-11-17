import { useEffect, useRef } from "react";
import { useUiStore, type Theme } from "@/stores/ui.store";

/**
 * App-wide starfield atmosphere.
 *
 * One fixed, full-viewport canvas layered ABOVE the page background (which
 * lives on <body>) and BELOW all app content (z-index -10 — panels and cards
 * keep their own backgrounds, so text readability is untouched).
 *
 * - ~150-250 stars (viewport-area-derived, capped), devicePixelRatio-aware
 *   sizing (capped at 2x).
 * - 3 parallax depth layers drifting a few px/sec; gentle sinusoidal twinkle
 *   with random phase/period per star.
 * - The rAF loop pauses while the tab is hidden; resize re-reads size once
 *   per debounced tick. No per-frame allocations.
 * - prefers-reduced-motion: reduce -> one static frame, no loop.
 * - Theme switches recolor the stars in place; the animation never restarts.
 *
 * Intensity is driven by the `dimmed` prop: once a topology is loaded the
 * canvas fades to near-invisible (CSS opacity transition) so the atmosphere
 * never competes with the graph, panels, or filters.
 */

/** Per-theme star palettes: dark -> white/pale-blue, light -> deep indigo/violet. */
const STAR_PALETTES: Record<Theme, readonly string[]> = {
  dark: ["255, 255, 255", "191, 204, 255", "226, 232, 255"],
  light: ["79, 70, 229", "124, 58, 237", "67, 56, 202"],
};

/** Alpha multiplier baked into fill colors (light stars stay clearly visible on white). */
const THEME_ALPHA: Record<Theme, number> = { dark: 1, light: 0.75 };

/** Radius multiplier per theme — light-mode stars get +25% so they read on white. */
const RADIUS_SCALE: Record<Theme, number> = { dark: 1, light: 1.25 };

/** Drift speed per depth layer in px/s (back -> front). */
const LAYER_SPEED = [1.5, 3, 5] as const;

const MAX_DPR = 2;
const TWO_PI = Math.PI * 2;
/** > 2 * max star radius (light theme), keeps the wrap-around seam invisible. */
const WRAP_MARGIN = 5;

interface Star {
  x: number;
  y: number;
  /** Unscaled radius; the drawn radius applies the per-theme RADIUS_SCALE. */
  baseRadius: number;
  radius: number;
  vx: number;
  vy: number;
  /** Per-star brightness baked into the fill color (before twinkle). */
  baseAlpha: number;
  /** Seconds for one full twinkle oscillation. */
  twinklePeriod: number;
  /** Random twinkle start phase in radians. */
  phase: number;
  /** CSS fill color, regenerated on theme change (never per frame). */
  color: string;
}

/** (Re)scatter stars across the viewport, resizing the array to the area budget. */
function seedStars(stars: Star[], width: number, height: number): void {
  const count = Math.max(150, Math.min(250, Math.round((width * height) / 12000)));
  stars.length = count;
  for (let i = 0; i < count; i++) {
    const layer = i % LAYER_SPEED.length;
    const angle = Math.random() * TWO_PI;
    const speed = LAYER_SPEED[layer] * (0.75 + Math.random() * 0.5);
    // ~8% brighter accent stars (visible in both themes).
    const accent = Math.random() < 0.08;
    const radius = accent ? 1.1 + Math.random() * 0.5 : 0.4 + Math.random() * 0.8;
    stars[i] = {
      x: Math.random() * width,
      y: Math.random() * height,
      baseRadius: radius,
      radius,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      baseAlpha: accent ? 0.85 : 0.4 + Math.random() * 0.45,
      twinklePeriod: 2 + Math.random() * 4,
      phase: Math.random() * TWO_PI,
      color: "",
    };
  }
}

/** Recolor + rescale existing stars for the theme — mutates in place, animation untouched. */
function applyTheme(stars: Star[], theme: Theme): void {
  const palette = STAR_PALETTES[theme];
  const alphaScale = THEME_ALPHA[theme];
  const radiusScale = RADIUS_SCALE[theme];
  for (let i = 0; i < stars.length; i++) {
    const star = stars[i];
    star.radius = star.baseRadius * radiusScale;
    star.color =
      `rgba(${palette[i % palette.length]}, ${(star.baseAlpha * alphaScale).toFixed(2)})`;
  }
}

/** Move stars by their drift velocity, wrapping around the viewport edges. */
function driftStars(stars: Star[], dt: number, width: number, height: number): void {
  const spanX = width + WRAP_MARGIN * 2;
  const spanY = height + WRAP_MARGIN * 2;
  for (let i = 0; i < stars.length; i++) {
    const star = stars[i];
    star.x += star.vx * dt;
    star.y += star.vy * dt;
    if (star.x < -WRAP_MARGIN) star.x += spanX;
    else if (star.x > width + WRAP_MARGIN) star.x -= spanX;
    if (star.y < -WRAP_MARGIN) star.y += spanY;
    else if (star.y > height + WRAP_MARGIN) star.y -= spanY;
  }
}

/** Draw all stars; the only per-frame state is numbers + prebuilt color strings. */
function drawStars(
  ctx: CanvasRenderingContext2D,
  stars: Star[],
  width: number,
  height: number,
  time: number,
): void {
  ctx.clearRect(0, 0, width, height);
  for (let i = 0; i < stars.length; i++) {
    const star = stars[i];
    const twinkle = 0.5 + 0.5 * Math.sin((time / star.twinklePeriod) * TWO_PI + star.phase);
    ctx.globalAlpha = 0.35 + 0.65 * twinkle;
    ctx.fillStyle = star.color;
    ctx.beginPath();
    ctx.arc(star.x, star.y, star.radius, 0, TWO_PI);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

interface StarfieldProps {
  /** True once a topology is loaded — the field fades to near-invisible. */
  dimmed: boolean;
}

/** Canvas opacity levels: full on the landing/empty state, ~15% when loaded. */
const OPACITY_ACTIVE = 1;
const OPACITY_DIMMED = 0.15;

export function Starfield({ dimmed }: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const starsRef = useRef<Star[]>([]);

  // Canvas lifecycle: sizing, rAF loop, listeners, theme subscription.
  // Runs once; nothing here re-runs on prop/state changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const stars = starsRef.current;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0;
    let height = 0;
    let raf = 0;
    let running = false;
    let reduced = media.matches;
    let last = performance.now();
    const start = last;

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seedStars(stars, width, height);
      applyTheme(stars, useUiStore.getState().theme);
      // No loop running (reduced motion, or tab hidden): keep the frozen
      // frame correct at the new size.
      if (!running) drawStars(ctx, stars, width, height, 0);
    };

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      driftStars(stars, dt, width, height);
      drawStars(ctx, stars, width, height, (now - start) / 1000);
      raf = requestAnimationFrame(frame);
    };

    const startLoop = () => {
      if (running || reduced) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };

    const stopLoop = () => {
      if (!running) return;
      running = false;
      cancelAnimationFrame(raf);
    };

    const onVisibility = () => {
      if (document.hidden) stopLoop();
      else startLoop();
    };

    const onReducedChange = () => {
      reduced = media.matches;
      if (reduced) {
        stopLoop();
        drawStars(ctx, stars, width, height, 0);
      } else {
        startLoop();
      }
    };

    let resizeTimer = 0;
    const onResize = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(resize, 150);
    };

    // Recolor in place on theme toggle; under reduced motion re-render the
    // frozen frame so the new palette shows immediately.
    const unsubscribeTheme = useUiStore.subscribe((state, prev) => {
      if (state.theme === prev.theme) return;
      applyTheme(stars, state.theme);
      if (reduced) drawStars(ctx, stars, width, height, 0);
    });

    resize();
    startLoop();

    media.addEventListener("change", onReducedChange);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", onResize);
    return () => {
      stopLoop();
      window.clearTimeout(resizeTimer);
      unsubscribeTheme();
      media.removeEventListener("change", onReducedChange);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 transition-opacity duration-1000"
      style={{ opacity: dimmed ? OPACITY_DIMMED : OPACITY_ACTIVE }}
    />
  );
}
