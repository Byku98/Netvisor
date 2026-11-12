# auth.md — how agents authenticate with NetVisor

> Procedural metadata for software agents, following the [auth.md](https://github.com/workos/auth.md) convention.
> Live instance: https://netvisor.tomaszbyczek.pl · Source: https://github.com/Byku98/Netvisor (MIT)

## Who agents act for

NetVisor is a self-hostable PCAP analysis app used by human analysts: upload a
network capture, get an interactive topology graph, drill into packets. An
agent interacting with NetVisor acts on behalf of such a user.

## Current authentication model (accurate as of 2026-11)

- **Human sessions:** users sign in with username + password or Google
  Sign-In. The session is a single httpOnly cookie (`access_token`, 7-day
  expiry, `Secure` in production).
- **API access:** every endpoint under `/api` uses the same cookie session.
- There are **no API tokens, no agent registration endpoints, and no
  machine-to-machine credentials** today.

## What agents CAN do right now

- Read public, machine-readable metadata:
  - `/llms.txt` — product overview for agents (llmstxt.org format)
  - `/about.md` — markdown product page with local-run instructions
  - `/backend/openapi.json` — full API catalog (read-only reference)
- Self-host the product from source and configure it freely (see `/about.md`).

## What agents CANNOT do right now (stated explicitly)

- **Programmatic registration is not available.** There is no registration or
  provisioning endpoint, no claim ceremony, and no token issuance. Unauthenticated
  requests to `/api/*` are rejected (401), and the demo UI cannot be driven by
  agents (SPA with file-picker upload).

## Planned: agentic registration (roadmap)

Agentic API access is planned as part of the NetVisor AI-assistant roadmap.
When it ships, NetVisor intends to follow the auth.md profile:

- OAuth Protected Resource Metadata (RFC 9728) at
  `/.well-known/oauth-protected-resource`
- Authorization Server metadata (RFC 8414) with an `agent_auth` block at
  `/.well-known/oauth-authorization-server`
- Identity assertion support (ID-JAG,
  draft-ietf-oauth-identity-assertion-authz-grant) and an RFC 8628-style
  claim ceremony for agents without an agent provider

This file will be updated and the `/.well-known/` documents published at that
time — **until those endpoints actually exist, the section above ("cannot do
today") is the operative truth.** Check the repository for progress.

## Contact

- Issues & questions: https://github.com/Byku98/Netvisor/issues
