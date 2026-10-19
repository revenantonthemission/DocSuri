# Requirements — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run producing this workflow's requirements record for unit tracing. Sources: [requirements-analysis-questions.md](requirements-analysis-questions.md) (confirmed Q1–Q5), [intent statement](../ideation/intent-capture/intent-statement.md), [scope document](../ideation/scope-definition/scope-document.md), reverse-engineering inventory ([business overview](../../../codekb/DocSuri/business-overview.md), [architecture](../../../codekb/DocSuri/architecture.md), [code structure](../../../codekb/DocSuri/code-structure.md)).

## Intent Analysis

Finish the interrupted v2 rebuild: deliver the three unbuilt units (U5 topics & digests, U6 approved export, U8 complete service integration), then produce honest build/CI and operation evidence over the complete application — which must run at production level as the maintainer's real daily service. Built capabilities (U1–U7) are retained context, not re-implementation targets. [Q1] [Q4]

## Functional Requirements

### FR1 — Topics & digests (U5)

- **FR1.1** — Persisted topic follow and unfollow per owner. [Q2]
- **FR1.2** — Per-topic digest settings: cadence, delivery time in the owner's timezone, content window, language/level inherited from preferences. [Q2]
- **FR1.3** — Digest content selected from eligible corpus within the configured window. [Q2]
- **FR1.4** — Delivery outcomes recorded; unknown outcomes reconciled before any further effect. [Q2]
- **FR1.5** — Unsubscribe honored even with queued work: nothing sends after unsubscribe. [Q2]
- **FR1.6** — Digest registration participates in the account lifecycle so withdrawal stops digests. [Q2]

### FR2 — Approved export (U6)

- **FR2.1** — Owner Notion connection with a protected, never-exposed token. [Q3] [NFR3]
- **FR2.2** — Read-only inspection and preview of a prepared artifact; neither ever triggers an export. [Q3]
- **FR2.3** — Exactly one explicit approve-and-export action, bound to the exact artifact revision and chosen destination. [Q3]
- **FR2.4** — Export outcomes are sent, failed, or unknown; unknown outcomes reconcile without a silent duplicate. [Q3]
- **FR2.5** — An approval is invalidated by artifact revision change, destination change, or revoked authority. [Q3]

### FR3 — Complete integration (U8)

- **FR3.1** — All views and lifecycle participants assemble into one application with coherent navigation and consistent behavior. [Q4]
- **FR3.2** — The complete application verifies cumulatively through real boundaries, not per-unit checks alone. [Q4]

### FR4 — Production-level operation (tail redo)

- **FR4.1** — The finished service runs continuously on this machine with real accounts and real papers. [Q4]
- **FR4.2** — Build/CI and all seven operation stages produce real evidence over the complete application, covering its real operating mode. [Q4]

## Non-Functional Requirements

- **NFR1** — Owner isolation enforced on every read and write across the new units. [Q5]
- **NFR2** — Consent honored for digests: late consent changes stop delivery. [Q5]
- **NFR3** — Notion tokens stored protected and never exposed or logged. [Q5]
- **NFR4** — Digest delivery and export effects are idempotent with explicit reconciliation. [Q5]
- **NFR5** — Korean responsive UI with the established WCAG 2.2 AA target on all new screens. [Q5]
- **NFR6** — $0 operation: free or local stacks only, no paid fallback. [Q5]

## Constraints

- The existing local stack is retained (Python backend, Next.js frontend, local model runtimes, synthetic verification realms). [Q4 via scope-document; code-structure]
- No new product features beyond parity. [Q1 via intent-statement]
- Retained capabilities from U1–U7 are already delivered; the capability inventory (CAP-01–CAP-20) is context, not re-implementation work. [Q1; business-overview]
- The construction verification command needs separate human approval before any unit checkpoint verifies. [scope-document Assumptions]

## Assumptions

- Local model runtimes remain available for digest generation and whole-application verification. [assumption — carried from feasibility RAID A1]
- Notion token-based integration remains available on free terms. [assumption — carried from feasibility RAID A3]

## Out of Scope

- New product features; paid services or billable APIs; data-migration or continuity commitments beyond evidence. [Q1 via scope-document]

## Open Questions

- The exact construction verification command (carried to Delivery Planning; mandatory human approval). [constraint from scope-document]
