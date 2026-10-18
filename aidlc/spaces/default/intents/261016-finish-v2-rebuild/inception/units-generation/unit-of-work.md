# Unit of Work — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Re-emits the three remaining approved units from the closed record's catalogue ([approved unit catalogue](../../../261010-docsuri-v2-rebuild/inception/units-generation/unit-of-work.md), rechecked); the five built units are satisfied context, not re-declared work. Requirements traced: [requirements.md](../requirements-analysis/requirements.md).

## Purpose and scope

This catalogue covers only the finish release's remaining construction work. U1–U4 and U7 are built, verified and merged to develop (U4 via PR #51); their capabilities are retained context. Component ownership follows the approved 13-component catalogue — TopicsDigests owns digest state, ApprovedExport owns export/connection state, ServiceOperations owns composition — with no duplicate account, library, job or artifact store. [Q1] [Q2]

## Unit catalogue

| Unit ID | Directory | Kind | Deployment grouping | Complexity | Responsibility |
|---|---|---|---|---|---|
| U5 | u5-topics-digests | library | embedded | M | Topic subscriptions, digest settings, content selection, recoverable delivery with reconciliation, unsubscribe honoring queued work, account-lifecycle participation (FR1) |
| U6 | u6-approved-export | library | embedded | M | Owner Notion connection with protected token, read-only preview, explicit approval bound to artifact revision + destination, reconciled export effect (FR2) |
| U8 | u8-service-operations-integration | service | shared | XL | Complete application assembly, cumulative whole-application verification, production-level operations and tail evidence (FR3, FR4) |

## Unit definitions and acceptance boundaries

### U5 — Topics & digests

- **Owns:** followed-topic rows, per-topic digest settings, digest preparation and delivery records, send/reconciliation log. [Q2] [Q4]
- **Delivers:** persisted follow/unfollow; per-topic cadence/time/window/level settings; content selection from eligible corpus; recorded outcomes with unknown-outcome reconciliation; unsubscribe honored despite queued work; lifecycle-participant registration (withdrawal stops digests). [requirements FR1]
- **UI contribution:** topics management and digest-settings screens per the approved wireframes (Korean, responsive, WCAG 2.2 AA).
- **Constraints:** consent honored (late changes stop delivery); $0 local delivery evidence still required even when fault tests use a local sink; registers as an AccountAccess lifecycle participant without writing account data.

### U6 — Approved export

- **Owns:** owner Notion connection state (protected token), export approvals, export effect records. [Q3] [Q4]
- **Delivers:** token-based owner connection; read-only inspection/preview that never exports; one explicit approve-and-export bound to the exact U4 artifact revision and chosen destination; sent/failed/unknown outcomes with reconciliation and no silent duplicate; approval invalidation on artifact/destination change or revoked authority. [requirements FR2]
- **UI contribution:** export preview/approval panel per the approved wireframes.
- **Constraints:** consumes U4's immutable artifact revision identity (already merged); no OAuth introduction; destructive/release authority stays with the operator path (U7).

### U8 — Complete service operations and integration

- **Owns:** application composition and its verification entrypoints; every business component retains authority over its own entities. [Q4]
- **Delivers:** assembly of all views, contributions and lifecycle participants into one application; cumulative whole-application verification through real boundaries; production-level operating evidence — the finished service runs continuously on this machine with real accounts and real papers, and the tail stages produce honest evidence over that mode. [requirements FR3, FR4]
- **Constraints:** public/private isolation, current authority, late effects, drafts, jobs, exports and controlled restore verified cumulatively; missing mandatory evidence prevents readiness claims.

## Shared release and composition responsibilities

- U5 and U6 are embedded contributions to the shared application; their completion transfers no ownership and creates no second store.
- U8 is the successive assembly of the same application U1 built; it supplies the application and verification entrypoints, while CI/CD and deployment stages retain their release authority.
- Every lifecycle participant (digests, export, plus the built ones) must be present and acknowledged for lifecycle completeness at U8. [Q4]

## Evidence prerequisites and downstream work

- The exact construction verification command remains unset and needs human approval before the first unit checkpoint verifies (carried to Delivery Planning).
- Notion terms, ORCID/Google reachability, content licensing and local model availability are the recorded dependencies (feasibility RAID). [feasibility-assessment]

## Assumptions & Open Questions

- None beyond the carried open item above.
