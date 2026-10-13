# U7 infrastructure specification

## Scope

Infrastructure for the independently executable U7 controlled operator
(`PlatformControl`) under the $0/local budget: a local process, a bounded child
executor per effect, and owner-isolated local persistence. No cloud resources,
no IaC beyond local supervisor scripts.

## Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Single local operator process + one bounded child process per effect | No separately deployed service; the child is the blast-radius unit for a native effect (logical-components.md) |
| Networking topology | Loopback/Unix-domain only; no inbound listener; any evidence HTTP binding stays compatibility-dependent and authenticated | C10's transport is local stdin/stdout JSON; no public admin surface |
| Storage strategy | Local filesystem for bounded staging/settlement files; local PostgreSQL for durable evidence/authority/receipts | Truthful, recoverable state; no object store/CDN needed |
| Environments | One local `synthetic-local` environment (the U1 local profile extended); no staging/production environment | $0/local budget; no release deployment |
| IaC approach | Local supervisor scripts + optional local compose entries; **no cloud IaC** | CDK-era artifacts are recorded cloud-dependent dispositions, not runtime dependencies |
| Resource sizing | Bounded child-process memory/CPU caps, a finite queue bound and bounded record sizes | NFR8.x; concrete values filled with the retained-inventory reconciliation and a measured baseline |

## Infrastructure Services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| PostgreSQL 16 (local instance) | database | Dedicated `PlatformControl` schema owned by a non-login role; U7's runtime role has DML only on that schema; owner-scoped `SECURITY DEFINER` guard functions | Shared with the application instance but isolated by schema+role (nfr-design Q2); U7 owns and applies its own idempotent migrations |
| Bounded child executor | compute (native effect) | Per-effect spawn with deadline + resource cap; typed result via pipe/staging file | nfr-design Q1; not a service |
| Local supervisor | operations | `status`/`start`/`stop`/`restart`/`backup`/`restore`/`rollback` for the operator process | Small local scripts; no daemon manager dependency |
| Local metrics/status view | observability | Reads the receipt store for counts/unresolved unknowns | No hosted metrics (nfr-design Q4) |
| Cache | — | **Not required** | No hot path needing a cache at single-operator scale |
| Queue/broker | — | **Not required** (bounded local table instead) | No paid broker; NFR8.5 |
| Search/CDN/DNS/load-balancer | — | **Not required** | Local CLI; no inbound traffic |

## Shared Infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| Local PostgreSQL instance | U1 (established the local stack) | U7 (and later units) | Separate `PlatformControl` schema + role; U7's role touches only its schema; application roles cannot touch it; guard functions expose only the bounded authority checks |

## Sources

- [logical-components.md](../nfr-design/logical-components.md)
- [security-design.md](../nfr-design/security-design.md), [reliability-design.md](../nfr-design/reliability-design.md)
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10
