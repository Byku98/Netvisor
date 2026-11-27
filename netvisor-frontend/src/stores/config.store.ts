import { create } from "zustand";

/**
 * Public runtime config fetched from GET /api/config at boot.
 * Single source of truth for deployment-configurable values shown in the UI
 * (the backend setting is env-overridable per deployment — Docker/K8s friendly).
 */
interface AppConfigState {
  /** Max upload size in bytes — mirrors backend settings.max_upload_bytes. */
  maxUploadBytes: number;
  /** Max TOTAL bytes across all files of one multi-file upload — mirrors
   *  backend settings.max_bundle_bytes. Older backends omit the field; the
   *  15 MB default then matches the backend's shipped default. */
  maxBundleBytes: number;
  /** Fields covered by the free-text packet search — mirrors backend
   *  GET /api/config searchFields (single source of truth for the FE hint).
   *  Empty until /config responds (or on older backends without the field). */
  searchFields: string[];
  setMaxUploadBytes: (bytes: number) => void;
  setMaxBundleBytes: (bytes: number) => void;
  setSearchFields: (fields: string[]) => void;
}

export const useConfigStore = create<AppConfigState>()((set) => ({
  maxUploadBytes: 5 * 1024 * 1024, // sensible default until /config responds
  maxBundleBytes: 15 * 1024 * 1024, // fallback for older backends without the field
  searchFields: [], // empty = render no searched-fields hint (graceful)
  setMaxUploadBytes: (bytes) => set({ maxUploadBytes: bytes }),
  setMaxBundleBytes: (bytes) => set({ maxBundleBytes: bytes }),
  setSearchFields: (fields) => set({ searchFields: fields }),
}));

/** Bytes -> human MB label ("5 MB", "5.5 MB"). */
export function formatMb(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB`;
}
