# Delivery Plan — Phase 7

## Sources and Decisions

Confirmed `delivery-planning-questions.md` Q8–Q11 and consolidated summary; approved requirements, stories, refined mockups, Domain Design ADR-014–ADR-016, Unit definitions/DAG/story map and Contract Design C1–C8. All referenced stage directories are siblings of this directory. The initial frontend integration request now includes the explicitly approved bounded backend remediation.

A **Bolt**, one build pass over a piece of work ending in something runnable, contains one approved Unit here. The **walking skeleton**, the smallest working end-to-end integration slice, is U1. This plan schedules work; it does not certify implementation or authorize deployment.

## Sequence and Calendar

| Order | Bolt / Unit | Directory | Kind / relative size | Prerequisite |
|---|---|---|---|---|
| 1 | Integrated job skeleton / U1 | u1-job-skeleton | service / XL | Applicable design and implementation approvals; required environment readiness |
| 2 | Job resilience / U2 | u2-job-resilience | ui / L | U1 integrated verification and human skeleton checkpoint approval |
| 3 | Secure assets / U3 | u3-secure-assets | service / M | U1 prerequisite; follows U2 by the human-selected sequence |

The Unit DAG has only U2 → U1 and U3 → U1. U2 before U3 is an economic sequencing choice, not an invented architectural dependency. The listed order matches the current resolved Unit order. Keep unit-major serial execution, one-session ownership, and existing human checkpoints; do not overlap shared source edits.

- **Planned Construction start:** Monday, 2026-10-05. A target date does not waive unresolved entry prerequisites.
- **Week 2 security review:** Wednesday, 2026-10-14, within October 12–18; accountable reviewer **revenantonthemission**.
- **No promised completion date:** XL/L/M are relative complexity, not person-days. Reassess estimates after the physical persistence/fencing design and real environment readiness checks.
- If asset implementation is unavailable on October 14, hold the review on actual available design/code and require a follow-up on completed asset implementation before its release. The review is not silently moved or declared complete from design alone.

## Bolt 1 — Integrated Job Skeleton

**Unit:** U1 / `u1-job-skeleton`.

**Walking Skeleton:** Yes.

**Owner:** One-session AI implementation, with revenantonthemission as accountable human decision/readiness contact. Applicable architect, QA and security assistance is targeted, not a claim of separate staffed teams.

**Scope:** Frontend submission/tracking/read-only result integration plus ContentJobController, ContentJobService, ContentJobWorker and necessary persistence/queue adapter changes. Shared backend guarantees apply to both summary and translation fixtures; the first browser demonstration is summarize. Preserve C4's prepareAttempt handle before POST and original-request recovery, including allowed dispatch-failure replacement without old-terminal restart.

### Internal Milestones

- Settle C7 persistence/binding/fence operations, crash reconciliation, lease/heartbeat/visibility configuration, and C8 compatibility constraints in the applicable Construction design stages.
- Implement and test shared backend outcome/result contracts, actual queue dispatch, authorized exact reads and backend/BFF SSE framing/cursors. These milestones are within U1, not additional units or a substitute for its integrated result.
- Integrate separate initial submission and read-only result surfaces, native EventSource, two-second fallback, stable parent recovery context, containment, accessible feedback/focus and scrubbed telemetry.
- Run integrated verification against the real authenticated BFF/gateway/API/worker/persistence path and present the result for the human skeleton checkpoint.

### Definition of Done

- Actual summarize submission reaches durable dispatch and the worker; browser receives real SSE progress and COMPLETED, then reads the exact authorized prepared result. A raw reference or mock response is insufficient.
- C1–C4/C6–C8 acceptance for delivered behavior passes, including backend summary/translation outcome fixtures, durable prepared personalization, 401/404/owner-only 410, controlled unavailable references and zero generation/enqueue on reads.
- Verify all declared effect/crash windows and conservative ambiguous-generation failure without a second invocation. No existing ledger capability is assumed without evidence.
- Verify retained replay, definite failed-dispatch replacement, uncertain response, immutable originals, missing-original disabled recovery and obsolete old-job/context suppression for the delivered slice.
- Include polling fallback, cleanup, render containment, required accessibility and scrubbed diagnostics now; do not postpone these to U2.
- Tests follow implementation per component, meet ≥80% new-code line coverage, and pass applicable current-suite, lint/typecheck and integration checks. Record actual commands/results rather than historical counts.
- Human-authorized integrated check succeeds and the separate skeleton checkpoint is approved before later Units. All remaining release stories are still mandatory.

**Confidence hypothesis:** The actual multi-runtime path can produce and retrieve the correct immutable owner-bound result while preserving identity and preventing generation on reads or unsafe repeated execution under the specified recovery cases.

**Expected demo:** Sign in to real staging, select an accessible paper and initial summary level, submit once, observe actual job progress over SSE, open completed content, and verify repeated result reads do not submit/generate. Supplement the visible demo with backend evidence for both tasks, negative ownership/expiry tests and crash/recovery cases. A successful demo alone does not prove those negative guarantees.

## Bolt 2 — Job Resilience

**Unit:** U2 / `u2-job-resilience`. **Walking Skeleton:** No. **Owner:** Same one-session implementation and human contact.

**Scope:** Translation UI, reload/storage recovery, replay/recreated streams, expanded result/copy interactions, diagnostics, and remaining job accessibility/performance evidence. Consume U1's tested backend contract; explicitly reassess allocation/kind before adding any new backend capability.

**Definition of Done:** All U2 acceptance contributions in `../units-generation/unit-of-work-story-map.md` pass, including C4 recovery after a lost response followed by edited visible draft, safe restoreAttempt behavior, owner/context changes, obsolete attempt rejection, actual response identity, and read-only result retry. Validate translation content, supplied-ID copy success/failure, non-stealing recovery focus and no duplicate announcements. Complete job p95 evidence under NFR9's real staging profile and applicable browser/assistive checks. Run combined U1/U2 regressions and new-code coverage. Mark whole cross-unit stories complete only after every contribution exists.

**Confidence hypothesis:** Users can recover and read the correct job outcome through connection loss, reload and owner changes without stale-job overwrite, cross-owner leakage, or unintended generation.

**Expected demo:** Translate supported input; exercise reconnect/polling, reload with valid originals and with missing originals, result read retry and copy failures. Show accurate recovered/replacement state without guessing dispatch-failure cause. Test fixtures, not production failures induced ad hoc, supply controlled negative cases.

## Bolt 3 — Secure Assets

**Unit:** U3 / `u3-secure-assets`. **Walking Skeleton:** No. **Owner:** Same one-session implementation; **security reviewer:** revenantonthemission.

**Scope:** Same-origin asset BFF integration, DocModelViewer/AssetViewer/ZoomPanControls, text/table equivalents, minimap, safe image failures and asset metrics. Does not own job generation or result persistence.

**Definition of Done:** US5.1–US5.3 and assigned cross-cutting contributions pass. Verify authenticated/licensed server delivery and denials, paper/version/asset matching, explicit redirect refusal, success/error cookie relay, private caching and generic image failure behavior. Verify keyboard/pointer zoom/pan/reset, no traps, existing semantic equivalents, 320 CSS-pixel reflow and 200% text resize. Meet asset decoded-readiness p95 under the approved fixture/profile. Preserve U1 job-stream regressions on shared BFF edits. Retain security findings, fixes and reviewer disposition from the scheduled review plus any required implementation follow-up before release.

**Confidence hypothesis:** Authorized figures/tables remain readable and operable while denied/context-changed access cannot bypass protections through redirects or alternate URLs.

**Expected demo:** Load a versioned authorized asset, inspect keyboard zoom/pan/reset and minimap, then demonstrate denial/missing/redirect and account-change fixtures without protected bytes or false cache-authorization claims.

## Integrated Verification Command

**Selection status: Explicitly deferred by the human in Q11.** No invocation is approved or stored by this plan. Current inspected Playwright configuration is mock-first and does not establish the required durable-job journey. U1 must supply a runnable real integrated check, identify prerequisites and propose its exact invocation for separate authorization before the first checkpoint. Never substitute a placeholder, a mock-only test or a generic unit suite as the skeleton demonstration.

The intent-wide check must remain valid as later Units complete, checking their delivered results without requiring unimplemented later features at U1. Design this capability incrementally with explicit completed-unit coverage. Existing test/contract/build/e2e scripts are candidates for supporting checks, not proof of sufficient integrated coverage. Reconcile missing coverage/typecheck scripts and the current lint entry during approved implementation/tooling work; record actual commands before use. Test command selection does not itself authorize environment provisioning or production changes.

## Release and Cross-Runtime Handoff

Frontend/BFF, backend API and worker are existing separate runtimes. C8 governs compatibility. Plan additive persistence/readers and compatible workers before new queue messages or UI exposure, drain/isolate incompatible workers, and preserve readable prepared records throughout rollback. No atomic deployment is assumed. Keep incomplete feature exposure gated while compatible changes merge under the recorded production-on-merge practice. Exact gating mechanism, environment commands, smoke checks, rollback invocation and operator authorization are deliverables of the applicable infrastructure/pipeline/deployment stages; verify them before the corresponding merge/exposure, not afterward.

Every release must satisfy all 28 active stories, required backend regressions, combined accessibility/performance evidence, current CI checks, and security dispositions. Engineering skeleton completion is not full release completion. `external-dependency-map.md` names readiness blockers and accountability; `risk-and-sequencing-rationale.md` explains prioritization and escalation.
