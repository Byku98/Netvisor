"""Chronological PCAP merge for multi-file uploads.

Primary path: mergecap (ships with Wireshark, next to tshark) — its
default merge mode orders packets chronologically by frame timestamp.
Fallback path (shared hosting without Wireshark): scapy reads every
packet, sorts by timestamp (stable — ties keep file/intra-file order)
and writes a pcapng via PcapNgWriter.

Parity requirement: both paths must produce the SAME packet sequence
(order + counts) for the same inputs — verified by tests.
"""

import shutil
import subprocess
from pathlib import Path

from src.logging import get_logger

log = get_logger("pcap_merge")

# Common mergecap installation paths on Windows (next to tshark.exe)
_WINDOWS_MERGECAP_PATHS = [
    Path(r"C:\Program Files\Wireshark\mergecap.exe"),
    Path(r"C:\Program Files (x86)\Wireshark\mergecap.exe"),
]

_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_mergecap() -> str | None:
    """Locate the mergecap executable; None when unavailable.

    Search order: PATH (shutil.which), then common Windows install
    locations (same layout as the tshark finder in services/tshark.py).
    """
    found = shutil.which("mergecap")
    if found:
        return found
    for p in _WINDOWS_MERGECAP_PATHS:
        if p.exists():
            log.info("mergecap found at non-PATH location: %s", p)
            return str(p)
    return None


def merge_pcaps(input_paths: list[Path], output_path: Path) -> str:
    """Merge capture files chronologically into output_path (pcapng).

    Returns the method used: "mergecap" or "scapy". Raises RuntimeError
    when both paths fail.
    """
    mergecap = find_mergecap()
    if mergecap:
        try:
            _merge_with_mergecap(mergecap, input_paths, output_path)
            return "mergecap"
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            # Fall through to scapy — shared hosting may have a broken
            # mergecap; the upload must not fail because of it.
            log.warning("mergecap merge failed (%s); falling back to scapy", e)
    _merge_with_scapy(input_paths, output_path)
    return "scapy"


def _merge_with_mergecap(
    mergecap: str, input_paths: list[Path], output_path: Path
) -> None:
    """mergecap -w out.pcapng in1 in2 ... (default = chronological merge)."""
    cmd = [mergecap, "-w", str(output_path), *[str(p) for p in input_paths]]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=_no_window,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mergecap error: {result.stderr.strip()}")


def _merge_with_scapy(input_paths: list[Path], output_path: Path) -> None:
    """scapy fallback: read all packets, sort by timestamp, write pcapng.

    Python's sort is stable, so packets with identical timestamps keep
    their input order (file order, then intra-file order) — the same
    deterministic sequence the parity test asserts against mergecap.
    """
    from scapy.all import PcapNgWriter, PcapReader

    packets = []
    for path in input_paths:
        with PcapReader(str(path)) as reader:
            packets.extend(reader)
    packets.sort(key=lambda p: float(p.time))
    writer = PcapNgWriter(str(output_path))
    try:
        for pkt in packets:
            writer.write(pkt)
    finally:
        writer.close()
