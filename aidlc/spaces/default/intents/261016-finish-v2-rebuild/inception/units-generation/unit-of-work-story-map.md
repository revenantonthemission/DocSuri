# Unit of Work Story Map — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Keyed by `FR` (no stories are produced in this workflow; user-stories remains skipped). Source: [requirements.md](../requirements-analysis/requirements.md) (this workflow). Built-unit capabilities are retained context, not rows here.

| Req ID | Requirement (abbreviated) | Implementing Unit | Directory |
|---|---|---|---|
| FR1.1 | Persisted topic follow/unfollow | U5 | u5-topics-digests |
| FR1.2 | Per-topic digest settings (cadence, time, window, level) | U5 | u5-topics-digests |
| FR1.3 | Digest content selection from eligible corpus | U5 | u5-topics-digests |
| FR1.4 | Delivery outcomes recorded; unknown outcomes reconciled | U5 | u5-topics-digests |
| FR1.5 | Unsubscribe honored despite queued work | U5 | u5-topics-digests |
| FR1.6 | Lifecycle participation: withdrawal stops digests | U5 | u5-topics-digests |
| FR2.1 | Owner Notion connection, protected token | U6 | u6-approved-export |
| FR2.2 | Read-only inspection/preview never exports | U6 | u6-approved-export |
| FR2.3 | Explicit approve-and-export bound to revision + destination | U6 | u6-approved-export |
| FR2.4 | Outcomes sent/failed/unknown with reconciliation | U6 | u6-approved-export |
| FR2.5 | Approval invalidated on change or revocation | U6 | u6-approved-export |
| FR3.1 | Assemble all views and lifecycle participants | U8 | u8-service-operations-integration |
| FR3.2 | Cumulative whole-application verification | U8 | u8-service-operations-integration |
| FR4.1 | Continuous local operation on real data | U8 | u8-service-operations-integration |
| FR4.2 | Honest tail evidence over the real operating mode | U8 | u8-service-operations-integration |

## Cross-cutting rows

| Concern | Spans | Note |
|---|---|---|
| Owner isolation (NFR1) | U5, U6, U8 | Enforced at every new read/write; verified cumulatively at U8 |
| Idempotency & reconciliation (NFR4) | U5, U6 | Delivery and export effects; verified with failure/interruption paths |
| Korean responsive UI + WCAG 2.2 AA (NFR5) | U5, U6, U8 | New screens extend the built workspace conventions |
| Consent honoring (NFR2) | U5 (+ lifecycle) | Late consent changes stop delivery; participant manifest coverage at U8 |
| Token protection (NFR3) | U6 | Notion token stored protected, never exposed or logged |
| $0 operation (NFR6) | U5, U6, U8 | Free/local only; sustainable free terms verified before reliance |

## Implementation order within each unit

Backend module and persistence first, then worker/delivery or export effect paths, then the UI contribution, then real-integration verification (per the approved test-last posture). Cross-unit acceptance is not closed by one unit: U5/U6 verify their lifecycle participation with installed participants; U8 verifies the complete manifest.

## Coverage verification

Every enumerated FR (14) is assigned to exactly one unit; every unit has rows. NFRs are carried as cross-cutting rows and unit constraints. No orphan requirements, no unassigned units.
