# Session Persistence & Storage Architecture Approaches

**Date:** September 13, 2026
**Context:** Investigation Mode Workflow - Users upload smaller files, iterate frequently, need fast reload
**Goal:** Balance cost optimization, performance, and user experience with stateless frontend/backend processes

## Current State Analysis

**What we have now:**
- Every packet = 1 DB row (millions of rows per session)
- Sessions have nullable `user_id` (works for both logged-in and anonymous users)
- PCAP files stored on disk, parsed once and stored in DB
- `get_session()` loads ALL packets to compute stats (performance issue)

**Requirements:**
- Anonymous users: Cookie-based session, single session per user, expires with cookie
- Logged-in users: Permanent session persistence
- Stateless processes: Frontend/backend processes must be stateless on production server
- Self-hosted deployment

---

## Approach 1: "Hot Data + Cold Storage" Architecture

### Storage Design
- **Hot Data (DB)**: User metadata, session metadata, aggregated topology (nodes/edges/stats)
- **Cold Storage (S3-compatible)**: Raw PCAP files only - never parsed again
- **Cache Layer (Redis)**: Anonymous session IDs, topology caching

### Session Persistence Logic
- **Anonymous users**: Cookie-based session ID stored in Redis (expires with cookie/7 days)
- **Logged-in users**: DB-based session persistence with Redis caching
- **Single anonymous session**: Redis ensures one session per cookie key

### PCAP Processing Flow
1. Upload → S3 (raw file)
2. Parse once → Extract topology → Store in DB
3. Delete intermediate packet data from DB
4. Packet drill-down: Read directly from S3 (seekable)

### Pros
- ✅ Extremely fast for topology view (no packet loading)
- ✅ Stateless processes (everything external)
- ✅ Cost-effective (DB stays small)
- ✅ Fast session switching (cached)

### Cons
- ⚠️ Packet drill-down requires S3 reads (slower than DB)
- ⚠️ Needs Redis infrastructure
- ⚠️ More complex setup (3 systems: DB + S3 + Redis)

---

## Approach 2: "Smart Hybrid" Architecture ⭐ **RECOMMENDED**

### Storage Design
- **Metadata Only (DB)**: Users, sessions, aggregated stats
- **Binary Blobs (S3)**: PCAP files + serialized topology JSON
- **No Packet Database**: Packet drill-down reads from PCAP file

### Session Persistence Logic
- **Anonymous users**: Cookie → S3 object prefix + DB metadata
- **Logged-in users**: DB metadata + organized S3 storage
- **Session limits**: Enforced via DB constraints

### PCAP Processing Flow
1. Upload → S3
2. Parse → Generate topology JSON → Store alongside PCAP in S3
3. Store only session stats in DB (no nodes/edges/packets tables)
4. Topology view: Load JSON from S3 (fast)
5. Packet drill-down: Seek in PCAP file

### Pros
- ✅ Extremely minimal DB (users + session stats only)
- ✅ Simpler architecture (DB + S3, no Redis needed)
- ✅ Topology loads fast from S3 (small JSON files)
- ✅ Stateless processes
- ✅ Easy backup/cleanup (just delete S3 folders)

### Cons
- ⚠️ Can't query across sessions (no aggregated packet data)
- ⚠️ S3 dependency for every topology view
- ⚠️ No complex packet filtering in DB

### Recommendation Reasoning
- Perfect for Investigation Mode (fast topology loading, quick session switching)
- Minimal complexity (only DB + S3)
- Cost-effective (small DB, S3 is cheap)
- Self-hosted friendly (MinIO + PostgreSQL)
- Future-proof (easy to add Redis later)

---

## Approach 3: "Lazy Eager" Architecture

### Storage Design
- **Progressive DB**: Users, sessions, aggregated topology only
- **S3 Storage**: Raw PCAP files
- **Optional Redis**: Anonymous session tracking

### Session Persistence Logic
- **Anonymous users**: Cookie → temporary session (7-day TTL in DB)
- **Logged-in users**: Permanent DB sessions
- **Anonymous limits**: DB query ensures single session

### PCAP Processing Flow
1. Upload → S3
2. Parse → Extract topology → Store aggregated only (no raw packets)
3. Packet drill-down: Lazy-load from PCAP via S3 ranges
4. Session loading: Fast (aggregated data only)

### Pros
- ✅ Minimal DB size (aggregated data only)
- ✅ Fast session loading (no packet data)
- ✅ Stateless processes
- ✅ Simple cleanup (old sessions = DB + S3 delete)
- ✅ Packet drill-down still works via S3 seeking

### Cons
- ⚠️ No packet filtering/querying in DB
- ⚠️ Session statistics recomputed from metadata only
- ⚠️ Packet drill-down requires S3 access

---

## Approach 4: "Event-Sourced Analysis" Architecture

### Storage Design
- **Event Store (DB or EventStore)**: Users, session events, analysis actions
- **Object Storage (S3)**: PCAP files + derived artifacts
- **Cache Layer (Redis)**: Session state, topology cache

### Session Persistence Logic
- **Anonymous users**: Cookie → event stream (session start, analysis, end)
- **Logged-in users**: Persistent event streams per user
- **Session limits**: Event stream state enforcement

### PCAP Processing Flow
1. Upload → S3
2. Emit "session_created" event → DB event store
3. Parse → Emit "topology_analyzed" event with results
4. Analysis actions → Emit "node_selected", "filter_applied" events
5. Restore session: Replay events to build current state

### Pros
- ✅ Perfect audit trail (every action recorded)
- ✅ Can replay/undo analysis actions
- ✅ Stateless processes (all state in storage)
- ✅ Very flexible for future features
- ✅ Easy to implement session restoration

### Cons
- ⚠️ Most complex architecture
- ⚠️ Requires event replay logic
- ⚠️ Learning curve for event sourcing
- ⚠️ May be overkill for current needs

---

## Decision Framework

### Key Considerations
1. **Investigation Mode Priority**: Fast topology loading > Complex packet filtering
2. **Self-Hosted Constraints**: Need simple, maintainable infrastructure
3. **Cost Sensitivity**: Minimize DB storage, optimize for S3 cheap storage
4. **Stateless Requirement**: No local file storage, everything external

### Trade-offs Summary

| Approach | Complexity | Cost | Performance | Maintainability | Self-Hosted Ready |
|----------|------------|------|-------------|-----------------|-------------------|
| Approach 1 | High | Low | Very High | Medium | Good |
| **Approach 2** | **Low** | **Very Low** | **High** | **Very High** | **Excellent** |
| Approach 3 | Medium | Low | High | High | Excellent |
| Approach 4 | Very High | Medium | Medium | Low | Medium |

---

## Next Steps

**Status**: User needs to review approaches and provide decision.

**Recommended Action**: Implement Approach 2 ("Smart Hybrid") - minimal complexity, perfect fit for investigation mode.

**Implementation Plan** (pending approval):
1. Set up MinIO for S3-compatible storage
2. Redesign DB schema (remove nodes/edges/packets tables)
3. Implement PCAP upload → S3 flow
4. Implement topology JSON generation and storage
5. Implement cookie-based anonymous session management
6. Implement session restoration from S3
7. Cleanup old sessions (scheduled job)
8. Performance testing

---

## Questions for Next Session

1. Do you agree with Approach 2, or want to modify it?
2. What S3-compatible storage solution for self-hosting? (MinIO, SeaweedFS, local?)
3. Do we need Redis for anonymous session management, or can DB handle it?
4. Session cleanup schedule? (7 days, 30 days, never?)
5. Do we need packet-level filtering in the future?