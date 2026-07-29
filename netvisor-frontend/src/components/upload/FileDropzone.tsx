import { Upload } from "lucide-react";
import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { usePcapUpload } from "@/hooks/use-pcap-upload";
import { cn } from "@/lib/utils";

/**
 * Drag-and-drop zone for PCAP file uploads.
 * Accepts `.pcap` and `.pcapng` files up to 200 MB.
 * Shows a spinner while the file is being parsed by the backend.
 */
export function FileDropzone() {
  const { mutate, isPending } = usePcapUpload();

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) mutate(accepted[0]);
    },
    [mutate],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.tcpdump.pcap": [".pcap"],
      "application/octet-stream": [".pcap", ".pcapng"],
    },
    maxFiles: 1,
    maxSize: 200 * 1024 * 1024,
    disabled: isPending,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors",
        isDragActive
          ? "border-blue-500 bg-blue-500/10"
          : "border-zinc-700 hover:border-zinc-500",
        isPending && "opacity-50 cursor-not-allowed",
      )}
    >
      <input {...getInputProps()} />
      {isPending ? (
        <div className="flex items-center justify-center gap-2">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent" />
          <span className="text-zinc-300">Parsing PCAP file...</span>
        </div>
      ) : isDragActive ? (
        <p className="text-blue-400 text-lg">Drop the file here...</p>
      ) : (
        <div>
          <Upload className="h-12 w-12 mx-auto mb-3 text-zinc-500" />
          <p className="text-zinc-300 text-lg">
            Drag &amp; drop a .pcap / .pcapng file
          </p>
          <p className="text-sm text-zinc-500 mt-1">
            or click to select (max 200 MB)
          </p>
        </div>
      )}
    </div>
  );
}
