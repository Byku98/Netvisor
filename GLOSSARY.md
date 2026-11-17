# NetVisor

Network topology visualization from PCAP captures: upload a capture, get an
interactive device/traffic graph, drill down into packets, ask an AI assistant
about the traffic.

## Language

**Filter Intent**:
A structured, machine-checkable proposal by the AI assistant to change the
current filter state. Never applied without the user's consent.
_Avoid_: filter action, auto-filter, follow-up action

**Graph Highlight**:
Temporary visual emphasis on topology elements that already exist in the
graph, produced by an AI answer and replaced by the next one.
_Avoid_: selection, marker, pin

**Insight**:
Structured, machine-readable output that accompanies an AI answer; may carry a
Graph Highlight and/or Filter Intents.
_Avoid_: analysis, result
