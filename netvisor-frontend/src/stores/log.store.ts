import { create } from "zustand";

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  id: number;
  timestamp: string;
  level: LogLevel;
  domain: string;
  message: string;
  data?: unknown;
}

interface LogState {
  entries: LogEntry[];
  push: (entry: Omit<LogEntry, "id" | "timestamp">) => void;
  clear: () => void;
}

let nextId = 0;

export const useLogStore = create<LogState>()((set) => ({
  entries: [],

  push: (entry) => {
    const id = nextId++;
    const timestamp = new Date().toISOString().slice(11, 23);
    set((state) => ({
      entries: [...state.entries.slice(-199), { ...entry, id, timestamp }], // keep last 200
    }));
  },

  clear: () => set({ entries: [] }),
}));
