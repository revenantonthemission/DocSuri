# Logical Components — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q2), [tech stack decisions](../nfr-requirements/tech-stack-decisions.md), [functional spec](../functional-design/functional-spec.md).

## Component Inventory

| Logical component | Responsibility | Runtime location |
|---|---|---|
| Scheduler hook | The existing worker entry evaluates each active topic's cadence + delivery time and invokes preparation | Inside the application process (existing worker) |
| Preparation service | Chronological window selection (BR2.4), run creation with settings-revision stamp, empty-digest recording (BR2.3) | Inside the application process |
| Delivery client | Assembles the digest email and sends it through the built email capability; writes the SendLogEntry; pathKind real/local-sink (BR1.4) | Inside the application process, adapter to the built email path |
| Reconciliation sweep | Detects orphaned `sending` runs after restart (BR3.4) and drives scheduled evidence checks (BR3.2) | Inside the application process (existing worker) |
| Lifecycle participant | Registers at application assembly; reports digest disposition on account lifecycle requests (BR4.3) | Inside the application process |
| Repositories | The module's six owned entities, one writer per table | Shared PostgreSQL |

## Failure Domains and Blast Radius

- **One failure domain**: all six components live inside the existing application process; U5 deploys no separate service, worker fleet, or store. [Q2]
- **Blast radius**: a digest failure (selection error, delivery failure, reconciliation stall) degrades digest sends for the affected topics only — search, library, accounts and research modules are untouched; the topic's own pause state is visible to its owner (BR3.2). [Q2]
- **Isolation strategy**: no cross-module writes (lifecycle participation is the only outward interaction and writes only this module's tables); scheduled paths run under service identity with repository-scoped access. [Q2]

## Shared Resources

| Resource | Sharing mode | Contention risk |
|---|---|---|
| Shared PostgreSQL | This module's tables only; standard transactional access | Low — digest rows are small and per-owner |
| Built email capability | Send path shared with account email (verification etc.) | Low — digest sends are rate-limited by schedule; no retry storms (BR3.3) |
| Existing worker entry points | Shared scheduler/worker loop | Low — each topic's preparation is bounded and single-flight per topic (BR3.1) |

## Handoff to Code Generation and Infrastructure Design

Code Generation places these components in the built module layout (backend module conventions, one repository per owned aggregate). Infrastructure Design inherits: no new infrastructure components, no new deployment surface; the shared PostgreSQL and the built email path are the only dependencies.
