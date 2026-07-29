import { useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadPcapFile, PcapUploadError } from "@/api/pcap.api";

/**
 * Mutation hook for uploading a PCAP file.
 * On success, caches the topology response under `["topology", sessionId]`.
 */
export function usePcapUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadPcapFile,
    onSuccess: (data) => {
      queryClient.setQueryData(["topology", data.sessionId], data);
    },
    onError: (error: PcapUploadError) => {
      console.error(`Upload failed: ${error.message}`);
    },
  });
}
