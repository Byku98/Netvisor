# NetVisor AI Insights — contract design (approved 2026-11-17)

> Brainstormed + approved in session (grilling rounds 1–3). Implementation
> branch: `feat/ai-insights`. This is the next slice of the AI Traffic
> Assistant (work order #1 in both TODOs). Glossary terms: `GLOSSARY.md`;
> decision record: `docs/adr/0001-ai-filter-intents-fenced-json-best-effort.md`.

## Scope

One contract covering BOTH capabilities, implemented as sub-slices on one branch:

1. **Graph Highlight** — the AI *shows* what it talks about (highlight nodes/edges).
2. **Filter Intents** — the AI *proposes* filters; the user applies them one-click.

Slice 1 (chat) stays untouched except for the response shape (additive).

## Decisions (all user-approved)

| # | Decision | Choice |
|---|---|---|
| 1 | Scope | One contract, both capabilities |
| 2 | Autonomy | Filters = propose + one-click apply (never auto); highlights = automatic |
| 3 | Highlight mechanics | Greenfield styling layer, never prunes; replaced by next answer; explicit × clear |
| 4 | Structured output | Prompt-instructed fenced JSON in the reply, backend-parsed (no tool-calls this slice) |
| 5 | Transport | Optional `insights` field on the existing `POST /api/sessions/{id}/ask` response |
| 6 | Payload shape | Two sections: `highlight` + `filter_intents` |
| 7 | Intent vocabulary | Small typed vocabulary (below), NOT raw store-field patches |
| 8 | Apply semantics | PATCH the current filter state (only listed fields change) |
| 9 | Validation | Best-effort per intent; dropped ones surfaced to the user |
| 10 | Highlight targets | Nodes + edges (edges given as IP pairs, FE normalizes) |
| 11 | Vocabulary injection | Explicit protocol-name vocabulary + node IP list added to the prompt context |
| 12 | Answer rendering | Backend strips the JSON block from `answer_md` — user sees clean prose |

## Contract

### Response shape (additive to `AskResponse`)

```json
{
  "answer_md": "…clean prose…",
  "insights": {
    "highlight": {
      "nodes": ["10.0.0.5"],
      "edges": [["10.0.0.5", "8.8.8.8"]]
    },
    "filter_intents": [
      { "type": "ip",       "side": "either", "value": "10.0.0.5" },
      { "type": "port",     "side": "src",    "value": "53" },
      { "type": "protocol", "mode": "include", "names": ["DNS"] },
      { "type": "scope",    "value": "local" },
      { "type": "search",   "value": "error" },
      { "type": "syn_only" },
      { "type": "rst_only" }
    ]
  }
}
```

`insights` is `null`/absent when the answer implies no actions. `answer_md`
never contains the JSON block (backend strips it).

### Filter Intent vocabulary

| `type` | Fields | Maps to (FE store) |
|---|---|---|
| `ip` | `side: either\|src\|dst`, `value: <ip or octet prefix>` | `ip` / `srcIp`+`dstIp` |
| `port` | `side: either\|src\|dst`, `value: <port>` | `port` / `srcPort` / `dstPort` |
| `protocol` | `mode: include\|exclude`, `names: [str]` | `protocols` / `excludedProtocols` + `protoMode` |
| `scope` | `value: all\|local\|external` | `subnetScope` |
| `search` | `value: str` | `search` |
| `syn_only` | — | `synOnly: true` |
| `rst_only` | — | `rstOnly: true` |

FE maps intents onto `setFilters(partial)` — the existing draft-mirror effect
keeps the panel in sync (including ipMode/portMode flip via the side-channel).
The Apply card lists exactly which fields will change before the click.

### Validation rules (best-effort, per item)

- **Backend**: shape/type checks; protocol `names` checked against the
  capture's protocol vocabulary; `value` sanity (numeric ports, IP shape).
  Invalid intent → dropped, recorded as "could not map X".
- **Frontend**: highlight node ids must exist in the topology; edge pairs
  normalized FE-side to the direction-normalized edge id `min(IP)-max(IP)`,
  dropped if no such edge exists. Highlight targets currently pruned out of
  the graph are silent no-ops (no error).
- **Feedback**: the Apply card / highlight chip reports partial success
  ("2 of 3 applied · could not map 'beaconing'"). Un-expressible claims
  (anomalies, behavior patterns) simply stay as prose — the model should not
  force them into intents.

### Graph Highlight mechanics

- Styling via Cytoscape classes (`ai-highlight` / `ai-highlight-edge`) — must
  NOT reuse element add/remove (the NetworkGraph ID-set no-op guard would mask
  a pruned-implementation) and must not touch selection.
- Auto-applied when an answer arrives; replaced by the next answer; cleared by
  an explicit small × control (chat chip and/or graph overlay).
- Works under traffic-weights view and both themes (theme-driven palette).

### Context injection

The context builder additionally injects, explicitly: the capture's exact
protocol-name list (engine-aware: scapy HTTPS vs tshark TLS) and the node IP
list — so the model can only emit names that validate.

## Implementation notes

- `max_tokens` 1000 → ~1500 for JSON headroom (both adapters).
- Parser: tolerant fenced-block extraction (```` ```json ```` or ```` ``` ````),
  defensive try/except, malformed block ⇒ `insights: null`, prose intact.
- `AskResponse` extension is backward compatible (existing consumers ignore
  unknown fields; FE `AiMessage` gains optional `insights`).
- Card UI lives in `AIAssistantPanel`; highlight state in `ui.store` (e.g.
  `aiHighlight: {nodes, edges} | null`), consumed by `NetworkGraph` via a
  dedicated styling effect.
- System prompt: describe the vocabulary + when to emit (only when the answer
  concretely points at hosts/edges or implies a filter).

## Out of scope (this slice)

- Provider-native structured output / tool-calls (ADR-0001 upgrade path).
- Streaming.
- Explain-packet & analyze endpoints (separate TODO items, may join `insights` later).
- Backend auto-applying anything.

## References

- ADR: `docs/adr/0001-ai-filter-intents-fenced-json-best-effort.md`
- Glossary: `GLOSSARY.md` (Filter Intent, Graph Highlight, Insight)
- Prior art: `plans/2026-11-12-ai-chat-slice1-design.md` (slice 1, merged v1.2.0)
