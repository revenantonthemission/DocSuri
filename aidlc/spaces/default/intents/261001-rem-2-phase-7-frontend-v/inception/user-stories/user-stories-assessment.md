# User Stories Assessment — Phase 7 Frontend Wiring

## Decision and Sources

**Decision: Execute.** This brownfield feature changes user-visible submission, tracking, recovery, results, assets, and accessibility across multiple integration boundaries. Independently testable scenarios clarify error behavior and prevent previously drafted retry semantics from promising unsupported re-execution.

Sources: approved `../requirements-analysis/requirements.md`; confirmed `user-stories-questions.md`; `aidlc/spaces/default/codekb/DocSuri/business-overview.md` and `component-inventory.md`; `../practices-discovery/team-practices.md`. Historical inventory assertions must be checked against live contracts before implementation. Contributor files contain limited source spot-checks, not runtime certification.

## Story Set and Scope

| Area | Active stories | Count |
|---|---|---|
| Submission and identity | US1.1–US1.5 | 5 |
| Progress, connection lifecycle and truthful outcomes | US2.1–US2.6 | 6 |
| Results, exact identity and asset-ID copy | US3.1–US3.4 | 4 |
| Failure and same-key recovery | US4.1–US4.2 | 2 |
| Secure assets and zoom/pan | US5.1–US5.3 | 3 |
| Accessibility | US6.1–US6.3 | 3 |
| Failure containment | US7.1–US7.3 | 3 |
| Operational visibility and responsiveness | US8.1–US8.2 | 2 |
| Total active | All Must Have | 28 |

US4.3 remains an excluded historical identifier (Won't Have); it must not be implemented or reassigned. US3.2 and US5.3 preserve the confirmed FR3.4/FR5.5 enhancements. No new cancellation, history, unsupported worker, offline-queue, or native-app feature is introduced.

Requirements Q15/Q16 authorizes bounded summarize/translate backend result remediation and preserves the failed-dispatch key-release exception. US2.6 and US3.4 capture FR2.5/FR3.5 without repurposing existing IDs. The old frontend-only boundary is superseded only for this authorized remediation.

All active behavior is required by the confirmed baseline. Delivery Planning still defines sequencing and the formal MVP boundary; a dependency or cross-cutting implementation task is not permission to downgrade required behavior.

## INVEST and Sizing Assessment

| Criterion | Assessment and qualification |
|---|---|
| Independent | Acceptance scenarios can run against explicit fixtures; implementation dependencies are listed. Integration enablers are not independently deployable products. |
| Negotiable | Implementation details remain open within confirmed contracts, fixed thresholds, and security/accessibility constraints. |
| Valuable | Every active story names a reader and outcome; technical enablers support privacy, reliability, or responsive feedback. |
| Estimable | Relative complexity is described below. Result rendering cannot be reliably estimated until its reference-to-content contract is verified. |
| Small | Copy, state presentation, and fallback pieces are bounded. Streaming lifecycle and telemetry/performance work need technical task decomposition and shared-effort accounting. |
| Testable | Stable Given/When/Then ACs cover happy paths and failures. Real-browser replay, gateway authorization, accessibility, and staging timing need their appropriate verification level. |

No blanket claim that every story is immediately independently shippable or precisely estimated is made.

| Cluster | Relative sizing and prerequisites |
|---|---|
| US1.3–US1.4 | Small-to-medium enablers; verify request reconstruction after reload and account-bound storage behavior. A hash alone cannot reconstruct parameters. |
| US1.5, US2.1–US2.5, US7.3 | Medium-to-large shared integration effort; verify BFF framing/cursor propagation and a coherent SSE/polling lifecycle. Avoid counting the same transport work repeatedly. |
| US1.1–US1.2, US4.2 | Medium workflow slices after identity/transport contracts. Distinguish retained-binding replay from failed-dispatch replacement; neither restarts the old terminal job. US4.2 spans in-session, pre-job and reload fixtures and needs technical task breakdown. |
| US2.6, US3.4 | Medium-to-large backend/integration slices, conditional on immutable binding and crash/redelivery design. Separate successful outcome, persistence interruption, ownership/expiry and read-only proofs into technical testable tasks; no invented duration estimate. |
| US3.1–US3.3 | US3.1/US3.3 sizing depends on the authorized backend remediation contract; US3.2 remains a bounded copy feature. |
| US5.1–US5.3 | Medium migration and interaction work; update actual callers and preserve auth/cookie/cache boundaries. |
| US6.1–US6.3, US7.1–US7.2 | Cross-cutting obligations integrated into affected components, not optional cleanup after shipping. |
| US8.1–US8.2 | Separate instrumentation and real staging-verification tasks. Single-job timing does not establish concurrency or availability capacity. |

## Dependency and Walking-Skeleton Handoff

The story dependency graph is acyclic. A permissible layering is:

- Foundations: US1.3, US1.5, US5.1, US7.1; US2.6 follows US1.5 and is fixture-testable independently.
- Storage/live connection/assets/fallback: US1.4, US2.1, US5.2, US5.3, US7.2.
- Submission/state/replay/polling/recovery/performance: US1.1, US1.2, US2.2, US2.3, US2.4, US4.2, US8.2.
- Cleanup/results/errors/accessibility/connection recovery/telemetry: US2.5, US3.1, US4.1, US6.1, US6.2, US7.3, US8.1.
- Result enhancements and remaining visual acceptance: US3.2, US3.3, US6.3; US3.4 follows US3.1 and US2.6 without a reverse dependency.

This is not a delivery schedule or a Unit DAG. Units Generation must package the first thin integrated **submit -> SSE progress -> COMPLETED -> result** slice, including applicable security, accessibility, and failure containment. BFF streaming/cursor behavior and result-reference resolution are prerequisites. The actual Construction Verification Command requires human approval later; no skeleton verification is claimed here.

## Requirement Coverage and Verification Responsibilities

The accompanying `traceability.json` enumerates all 47 requirement IDs: 7 parent FRs, 28 FR sub-requirements, and 12 NFRs. User-facing obligations map to active story IDs, including US2.6 and US3.4. NFR8 and NFR11 are Deferred only as process-evidence ownership, not optional work:

- **NFR8:** Delivery Planning names/schedules the mid-implementation AssetViewer security review; implementation/release evidence must show its findings were addressed before release.
- **NFR11:** Code Generation authors tests under the affirmed test-after ordering; Build and Test verifies current suites, lint/typecheck, relevant E2E, and at least 80% new-code line coverage. Backend evidence covers exact result binding, ownership/expiry, truthful outcomes, interrupted persistence/redelivery, dispatch-failure replacement and zero generation/enqueue during reads.
- **NFR9:** US8.2 preserves the real staging profile, all three strict p95 limits, raw samples, and reproducible measurement boundaries. Mock timing is not substitute acceptance evidence.
- **NFR10:** US6 criteria plus control-specific stories cover changed-UI accessibility; automated checks alone do not establish screen-reader conformance.

Requirements review findings R-01 and R-02 remain accepted risks in their upstream review. The explicit skeleton path and connection-latency detail in stories elaborate confirmed requirements downstream rather than silently rewriting or claiming to resolve upstream findings.

## Integration of Specialist Input

Independent contributions are retained under `contributions/`. The current amendment received fresh designer, developer and QA input. The lead integrated recovery-success focus continuity, crash-window/effect reconciliation, exact personalized overlays, actual SSE framing verification, backend-before-UI integration prerequisites, and stale-old-job suppression after a replacement. These are requirements-grounded elaborations, not runtime certification. Earlier refinements below remain relevant:

| Concern | Integration |
|---|---|
| Excluded executable task types | AC1.1.6 verifies the scoped submission boundary without removing unrelated workflows. |
| BFF SSE compatibility | AC1.5.6 and the skeleton handoff require preserved framing, IDs, incremental delivery, and cursor propagation. |
| Result reference resolution | US3.1/US3.4 now carry the approved remediation scope and owner-checked expiry; Contract Design pins compatible formal contracts before implementation. |
| Owner change/access loss | AC2.4.4 and AC2.5.5 limit stale retention to unchanged authorized connectivity context and prevent previous-owner updates/content. |
| Unchanged recovery across outcomes | AC4.2.6 tests the no-parameter-change/no-key-rotation restriction on both success and failure. |
| Accessible feedback/focus | AC6.1.6–AC6.1.7 and AC6.2.5 cover nonterminal feedback, unchanged polling, focus continuity, and keyboard escape from the viewer. |
| WCAG breadth and reflow | AC6.3.5–AC6.3.7 require state-based checks, text resizing and reflow; the accessibility handoff requires evidence for existing text alternatives. |

## Technical Gaps and Escalation Boundaries

- **BFF stream/cursor seam:** The developer's source spot-check found content-job events absent from the current streaming branch and missing Last-Event-ID forwarding. Treat historical “BFF ready” prose as unverified. Contract Design and implementation must resolve this before claiming the skeleton works.
- **ResultRef mapping:** The demonstrated gap has been escalated and bounded backend work authorized. Contract Design still must define compatible result identity/delivery and truthful worker mappings; no raw-reference substitute or generation-on-read is acceptable. Remaining scope beyond this bound requires a new explicit decision.
- **Accessible asset equivalents:** Verify captions/text alternatives/table semantics from the existing data and UI. Missing equivalents are an accessibility gap, not authority for a new OCR/content service.
- **Runtime evidence:** Backend compatibility, benchmarks, security review, and implementation tests remain to be executed in their owning stages. No current pass counts or deployment readiness are inferred from historical documentation.

## Specification Verification

The final amended map is checked with `aidlc engine sensor-traceability --output-path aidlc/spaces/default/intents/261001-rem-2-phase-7-frontend-v/inception/user-stories/traceability.json --stage user-stories`; the actual tool output is the verification evidence, not this instruction. Application tests, browser accessibility checks, staging measurements and live security checks remain later-stage evidence; these documents make no current runtime success claim.
