/** Protocol color mapping shared by packet list components. */
export const PROTOCOL_COLORS: Record<string, { bg: string; dot: string; text: string }> = {
  TCP:   { bg: "hover:bg-blue-950/30",  dot: "bg-blue-500",   text: "text-blue-400"   },
  UDP:   { bg: "hover:bg-purple-950/30", dot: "bg-purple-500", text: "text-purple-400" },
  HTTP:  { bg: "hover:bg-green-950/30",  dot: "bg-green-500",  text: "text-green-400"  },
  HTTPS: { bg: "hover:bg-emerald-950/30",dot: "bg-emerald-500",text: "text-emerald-400"},
  TLS:   { bg: "hover:bg-emerald-950/30",dot: "bg-emerald-500",text: "text-emerald-400"},
  DNS:   { bg: "hover:bg-yellow-950/30", dot: "bg-yellow-500", text: "text-yellow-400" },
  ICMP:  { bg: "hover:bg-orange-950/30", dot: "bg-orange-500", text: "text-orange-400" },
  ARP:   { bg: "hover:bg-pink-950/30",   dot: "bg-pink-500",   text: "text-pink-400"   },
  SSH:   { bg: "hover:bg-cyan-950/30",   dot: "bg-cyan-500",   text: "text-cyan-400"   },
  FTP:   { bg: "hover:bg-rose-950/30",   dot: "bg-rose-500",   text: "text-rose-400"   },
  SMTP:  { bg: "hover:bg-indigo-950/30", dot: "bg-indigo-500", text: "text-indigo-400" },
  DHCP:  { bg: "hover:bg-teal-950/30",   dot: "bg-teal-500",   text: "text-teal-400"   },
};

export function getPacketColor(proto: string) {
  return PROTOCOL_COLORS[proto.toUpperCase()] ?? { bg: "hover:bg-zinc-800/30", dot: "bg-zinc-500", text: "text-zinc-400" };
}
