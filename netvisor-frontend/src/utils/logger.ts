/**
 * Frontend logger — outputs to browser console AND the in-app debug panel.
 *
 * Usage:
 *   import { logger } from "@/utils/logger";
 *   logger.info("auth", "Login attempt", { email });
 *   logger.error("api", "Request failed", { status: 500 });
 */

import { useLogStore, type LogLevel } from "@/stores/log.store";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const LEVEL_LABEL: Record<LogLevel, string> = {
  debug: "DBG",
  info: "INF",
  warn: "WRN",
  error: "ERR",
};

const MIN_LEVEL: LogLevel = import.meta.env.DEV ? "debug" : "warn";

function shouldLog(level: LogLevel): boolean {
  return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[MIN_LEVEL];
}

function formatTimestamp(): string {
  return new Date().toISOString().slice(11, 23); // HH:MM:SS.mmm
}

function emit(level: LogLevel, domain: string, message: string, data?: unknown): void {
  if (!shouldLog(level)) return;

  const tag = `${formatTimestamp()} | ${LEVEL_LABEL[level]} | ${domain.padEnd(12)} | ${message}`;

  switch (level) {
    case "debug":
      data !== undefined ? console.debug(tag, data) : console.debug(tag);
      break;
    case "info":
      data !== undefined ? console.log(tag, data) : console.log(tag);
      break;
    case "warn":
      data !== undefined ? console.warn(tag, data) : console.warn(tag);
      break;
    case "error":
      data !== undefined ? console.error(tag, data) : console.error(tag);
      break;
  }

  // Push to the in-app debug panel store
  try {
    useLogStore.getState().push({ level, domain, message, data });
  } catch {
    // store not yet initialized — ignore
  }
}

export const logger = {
  debug: (domain: string, message: string, data?: unknown) =>
    emit("debug", domain, message, data),
  info: (domain: string, message: string, data?: unknown) =>
    emit("info", domain, message, data),
  warn: (domain: string, message: string, data?: unknown) =>
    emit("warn", domain, message, data),
  error: (domain: string, message: string, data?: unknown) =>
    emit("error", domain, message, data),
};
