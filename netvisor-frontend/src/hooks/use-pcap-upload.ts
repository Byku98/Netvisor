import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  uploadPcapFiles,
  PcapUploadError,
  type UploadFile,
} from "@/api/pcap.api";
import type { TopologyResponse } from "@/types/network.types";

/** Variables for the upload mutation. */
export interface UploadPcapVars {
  /** One or more files (a single-file upload behaves exactly as before). */
  files: UploadFile[];
  /** Optional session label — logged-in users only; omitted for anonymous
   *  uploads so the server auto-labels the session. */
  label?: string;
}

/**
 * Mutation hook for uploading one or more PCAP files.
 * On success, caches the topology response under `["topology", sessionId]`.
 */
export function usePcapUpload() {
  const queryClient = useQueryClient();

  return useMutation<TopologyResponse, PcapUploadError, UploadPcapVars>({
    mutationFn: ({ files, label }) => uploadPcapFiles(files, label),
    onSuccess: (data) => {
      queryClient.setQueryData(["topology", data.sessionId], data);
    },
    onError: (error) => {
      console.error(`Upload failed: ${error.message}`);
    },
  });
}
