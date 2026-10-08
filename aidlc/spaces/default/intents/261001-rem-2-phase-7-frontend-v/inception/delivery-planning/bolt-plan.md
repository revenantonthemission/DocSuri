# Delivery Plan — Phase 7

## Sources and Decisions

Confirmed `delivery-planning-questions.md` Q8–Q12 and its current consolidated summary govern this bounded update. Inputs are `../requirements-analysis/requirements.md`, `../user-stories/stories.md`, `../refined-mockups/mockups.md`, `../domain-design/components.md` and ADR-014–ADR-016, `../units-generation/unit-of-work.md`, `../units-generation/unit-of-work-dependency.md`, `../units-generation/unit-of-work-story-map.md`, approved `../contract-design/contract-summary.md` C1–C8, and `../practices-discovery/team-practices.md` with the affirmed active-space rules. The initial frontend integration request includes the explicitly approved bounded backend remediation.

Recovery inputs are `../../construction/u1-job-skeleton/code-generation/{code-summary,recovery-impact}.md` and the confirmed planning handoff `../../verification/u1-isolated-postgres-bootstrap-plan.md`. They establish partial implementation and prerequisites, not a completed Unit or operational readiness. Prior delivery documents and the earlier completeness report are preserved byte-for-byte under `../../archive/2026-10-05T16-04-22Z-delivery-planning/`; this questions record retains its prior answers and historical confirmation.

A **Bolt**, one build pass over a piece of work ending in something runnable, contains one approved Unit here. The **walking skeleton**, the smallest working end-to-end integration slice, is U1. This plan schedules work; it does not certify implementation or authorize deployment.

## Sequence and Calendar

| Order | Bolt / Unit | Directory | Kind / relative size | Prerequisite |
|---|---|---|---|---|
| 1 | Integrated job skeleton / U1 | u1-job-skeleton | service / XL | Applicable design and implementation approvals; required environment readiness |
| 2 | Job resilience / U2 | u2-job-resilience | ui / L | U1 integrated verification and human skeleton checkpoint approval |
| 3 | Secure assets / U3 | u3-secure-assets | service / M | U1 prerequisite; follows U2 by the human-selected sequence |

The Unit DAG has only U2 → U1 and U3 → U1. U2 before U3 is an economic sequencing choice, not an invented architectural dependency. The listed order matches the current resolved Unit order. Keep unit-major serial execution, one-session ownership, and existing human checkpoints; do not overlap shared source edits.

- **Original planned Construction start:** Monday, 2026-10-05. This remains the recorded calendar anchor, not a new start date or evidence that prerequisites passed. U1 now has a preserved partial implementation awaiting recovery/revalidation.
- **Week 2 security review:** Wednesday, 2026-10-14, within October 12–18; accountable reviewer **revenantonthemission**.
- **No promised completion date:** XL/L/M are relative complexity, not person-days. Reassess estimates after the physical persistence/fencing design and real environment readiness checks.
- If asset implementation is unavailable on October 14, hold the review on actual available design/code and require a follow-up on completed asset implementation before its release. The review is not silently moved or declared complete from design alone.

## Bolt 1 — Integrated Job Skeleton

**Unit:** U1 / `u1-job-skeleton`.

**Walking Skeleton:** Yes.

**Owner:** One-session AI implementation, with revenantonthemission as accountable human decision/readiness contact. Applicable architect, QA and security assistance is targeted, not a claim of separate staffed teams.

**Scope:** Frontend submission/tracking/read-only result integration plus ContentJobController, ContentJobService, ContentJobWorker and necessary persistence/queue adapter changes. Shared backend guarantees apply to both summary and translation fixtures; the first browser demonstration is summarize. Preserve C4's prepareAttempt handle before POST and original-request recovery, including allowed dispatch-failure replacement without old-terminal restart.

### Internal Milestones

- Revalidate affected U1 designs against the approved C2 shared reproducibility object and existing C1–C8 obligations. Preserve the already selected persistence/fencing/timing choices where compatible; prior artifacts or review receipts do not by themselves approve this new attempt.
- Reconcile the narrow migration-admission extension, supplemental original-byte/source-footprint capture and current implementation plan/test instructions through their owning approval path. Preserve registered migration identity/digest, same-connection current authority, locking, transaction/ledger and guarded commit; no raw rejected-SQL bypass or general procedural exemption.
- Qualify the isolated PostgreSQL artifact/runtime and concrete operator-owned launcher/network/database/role configuration described by the bootstrap handoff. Obtain operational authorization before resource/rule application, measure isolation, and bind independent public proof/digests before mutation-capable fixture access. The full authority database and later minimal-schema purge database remain distinct.
- With admitted registered SQL and real realm, rerun the required schema/owner-lifecycle lane without vacuous skips. The recorded handoff's one admission failure and ten missing-realm errors remain failed historical evidence, not a passed prerequisite. The retained destructive purge fixture waits for its scheduled guard/bridge implementation and separate target preflight.
- Resume the ordered implement-then-test work only with current implementation authority and the required passed prerequisite. Preserve the existing partial source and immutable dirty-source baseline; never recapture modified bytes or substitute HEAD as the pre-write source. Resolve the stricter imported TypeScript and supply-chain/runtime gaps within their approved boundaries.
- Implement and test shared backend outcome/result contracts, actual queue dispatch, authorized exact reads and backend/BFF SSE framing/cursors. These milestones are within U1, not additional units or a substitute for its integrated result.
- Integrate separate initial submission and read-only result surfaces, native EventSource, two-second fallback, stable parent recovery context, containment, accessible feedback/focus and scrubbed telemetry.
- Run integrated verification against the real authenticated BFF/gateway/API/worker/persistence path and present the result for the human skeleton checkpoint.

### Definition of Done

- Actual summarize submission reaches durable dispatch and the worker; browser receives real SSE progress and COMPLETED, then reads the exact authorized prepared result. A raw reference or mock response is insufficient.
- C1–C4/C6–C8 acceptance for delivered behavior passes, including backend summary/translation outcome fixtures, durable prepared personalization, owner-first 401/indistinguishable 404/409/owner-only 410/422/transient 503/504 behavior, controlled unavailable references and zero generation/enqueue on reads. Summary capture and consumer validation preserve the exact required string `code`/`data` object from the shared Reproducibility definition, not flattened text or guessed defaults; retain preparedResult v1 and test legacy/consumer compatibility.
- Verify all declared effect/crash windows and conservative ambiguous-generation failure without a second invocation. No existing ledger capability is assumed without evidence.
- Verify retained replay, definite failed-dispatch replacement, uncertain response, immutable originals, missing-original disabled recovery and obsolete old-job/context suppression for the delivered slice.
- Include polling fallback, cleanup, render containment, required accessibility and scrubbed diagnostics now; do not postpone these to U2.
- Tests follow implementation per component, meet ≥80% new-code line coverage, and pass applicable current-suite, lint/typecheck and integration checks. Record actual commands/results rather than historical counts.
- Real-store acceptance includes source-bound schema/constraint/owner proof and meaningful expiry/timestamp behavior. The current document validator's payload-shape checks do not establish malformed-timestamp rejection or runtime TTL correctness; preserve the accepted upstream timestamp-validation risk rather than inferring a pass.
- Human-authorized integrated check succeeds and the separate skeleton checkpoint is approved before later Units. All remaining release stories are still mandatory.

**Confidence hypothesis:** The actual multi-runtime path can produce and retrieve the correct immutable owner-bound result while preserving identity and preventing generation on reads or unsafe repeated execution under the specified recovery cases.

**Expected demo:** Sign in to real staging, select an accessible paper and initial summary level, submit once, observe actual job progress over SSE, open completed content, and verify repeated result reads do not submit/generate. Supplement the visible demo with backend evidence for both tasks, negative ownership/expiry tests and crash/recovery cases. A successful demo alone does not prove those negative guarantees.

### Preserved Partial Work and Entry Status

The historical `code-summary.md` claims 29 actual writes in model/codec, schema-source, runner/configuration/lock and safe-copy support. Its reported 94 passing model tests, 356 passing existing frontend tests and mock-default production-mode build are useful local evidence with their recorded source/environment limits. They are not current full-source coverage, admitted PostgreSQL, finished backend/browser integration or skeleton proof. The C2 string/object mismatch is now corrected in the approved specification; preserved model/application conformance still requires current verification. Migration admission, the actual realm, stricter imported typing and artifact/runtime qualification remain open. This plan leaves the partial implementation in place and assigns recovery to U1, without completing or skipping it.

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

**Selection status: Explicitly deferred by the human in Q11 and retained in the confirmed amendment.** No invocation is approved or stored by this plan. The previously inspected default Playwright configuration is mock-first; the partial implementation's dedicated real-origin configuration does not demonstrate a completed durable-job journey. U1 must supply a runnable real integrated check, identify prerequisites and propose its exact invocation for separate authorization before the first checkpoint. Never substitute a placeholder, a mock-only test or a generic unit suite as the skeleton demonstration.

The intent-wide check must remain valid as later Units complete, checking their delivered results without requiring unimplemented later features at U1. Design this capability incrementally with explicit completed-unit coverage. Existing test/contract/build/e2e scripts are supporting-check candidates, not proof of sufficient integrated coverage. Use the current runner/source handoff rather than treating older missing-script observations as present facts; qualify the stricter imported graph and complete actual all-source coverage/CI collectors without weaker flags or excluded authority code. Test command selection does not authorize environment provisioning or production changes.

## Release and Cross-Runtime Handoff

Frontend/BFF, backend API and worker are existing separate runtimes. C8 governs compatibility. Plan additive persistence/readers and compatible workers before new queue messages or UI exposure, drain/isolate incompatible workers, and preserve readable prepared records throughout rollback, including the exact code/data object and prepared personalization. No atomic deployment is assumed. Keep incomplete feature exposure gated under the recorded production-on-merge practice; automatic production delivery requires the exact release's required CI/staging/compatibility evidence. Concrete approved infrastructure/pipeline/deployment procedures must qualify environment commands, smoke checks, rollback and operational application before the affected merge/exposure. Delivery-plan approval grants neither merge nor operational execution.

Every release must satisfy all 28 active stories, required backend regressions, combined accessibility/performance evidence, current CI checks, and security dispositions. Engineering skeleton completion is not full release completion. `external-dependency-map.md` names readiness blockers and accountability; `risk-and-sequencing-rationale.md` explains prioritization and escalation.

## Upstream Evidence and Findings

Contract Design R-03 remains **Accepted risk** from the human approval: the documented validator environment did not register a date-time checker and accepted malformed preparedAt/expiresAt/DocModel generatedAt. Its complete-envelope shape checks establish the corrected reproducibility and translation references, not timestamp validation or runtime TTL. Retain the recorded Required action with its owning contract review; separate required application/store expiry evidence still applies. Requirements R-01/R-02 remain accepted wording risks. Historical U1 Functional Design R-05, NFR Requirements R-01 and Infrastructure Design R-01/R-02 keep their owning records/dispositions and must be surfaced at applicable checkpoints; this plan does not mark them resolved. `../../verification/phase-check-inception.md` is a refreshed coverage-only report, not implementation or environment approval.
