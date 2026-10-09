# U2 Job Resilience — Code Generation Questions

## Q1. U1 Frontend Surface Reconciliation

U1 (`u1-job-skeleton`) is recorded complete, and its walking-skeleton checkpoint was verified with the recorded command (`cd ops && .venv/bin/python -m pytest tests/test_u1_colima_executor.py -q && cd ../frontend && node --test scripts/u1-sandbox.test.mjs`, exit 0) and approved. U1's own record documents its implementation as partial ("current planning is not current implementation or execution authority"; Step 2 partial, Step 5 unchecked, Step 6 incomplete).

Reality on disk: U1's planned frontend job surface is absent. U1's 50-step plan contains the frontend steps (Step 21 ContentJobApi/IdempotencyService, Step 25 JobSubmissionForm, Step 27 ErrorBoundary, Step 31 JobStatus, Step 33 SummaryModal, Step 35 parent composition), and all are unchecked. Missing files include `frontend/components/JobSubmissionForm.tsx`, `frontend/components/ErrorBoundary.tsx`, `frontend/components/ErrorBoundaryFallback.tsx`, `frontend/components/JobDialog.tsx`, `frontend/lib/idempotencyService.ts`, `frontend/lib/jobState.ts`, `frontend/lib/jobDiagnostics.ts`, `frontend/lib/cn.ts`, `frontend/lib/api/contentJobContracts.ts`; `contentJobApi.ts` is unwired (its base is `/api/content-jobs`, not `/bff/api/content-jobs`), and no job tests exist. U1's delivered frontend files on disk are configuration and scripts: `package.json`, `pnpm-lock.yaml`, `eslint.config.mjs`, `vitest.u1.config.ts`, `tsconfig.u1.json`, `playwright.u1.config.ts`, `postcss.config.mjs`, `scripts/u1-sandbox.mjs`, `scripts/u1-sandbox.test.mjs`.

U2's unit definition says it "extends U1's frontend job surfaces" and that "U1-delivered fallback, security, accessibility and tests already exist". U2's assigned acceptance cases (translate submission/results, reload recovery, replay/reconnection resilience, expanded result states, telemetry) presuppose that surface.

How should this code-generation plan handle the missing surface?

A. U2 delivers the needed surface as prerequisites — the plan explicitly includes establishing the missing frontend job-surface pieces (submission form, error containment, BFF-routed ContentJobApi/transport, idempotency service, JobStatus and SummaryModal rework) that U2's translate/resilience acceptance cases require, then delivers U2's scope on top; verification covers the combined U2 slice.
B. Reopen U1 for a completion pass first — the workflow goes back so the missing frontend work lands under `u1-job-skeleton`, and U2 starts after that pass settles.
X. Other (please specify)

[Answer]: B

## Q1 Resolution

The human-selected path completed: `u1-job-skeleton`'s frontend completion pass settled on its restarted attempt (fresh Plan Approval `sha256:v3:ea953058…`, adversarial review READY with all prior findings resolved, walking-skeleton checkpoint verified with the recorded command and human-approved on 2026-10-08). The delivered U1 frontend job surface U2 extends now exists on disk: BFF-routed content-job transport with typed contracts/`seq` watermarking (`lib/api/contentJobApi.ts`, `lib/api/contentJobContracts.ts`), `idempotencyService`, `jobState`, `jobDiagnostics`, `cn`, `JobSubmissionForm`/`JobDialog`, `ErrorBoundary`/`ErrorBoundaryFallback`, the live `JobStatus` with the fixed two-second SWR fallback, the query-only `SummaryModal`, and the `PaperDetailIsland` composition — with 23 u1 test files (104 tests) green alongside the base suite (421 tests). U2's plan therefore builds on that delivered surface as its unit definition prescribes. The Q1 situation text above is retained as provenance of the state at the time of the question; it no longer describes the current tree. (Since superseded: the stage restart recorded below re-settled U1 on a new attempt — current Plan Approval `sha256:v3:bdcce478…`, checkpoint re-verified and re-approved; see the Re-entry Context.)

## Plan Approval

Approve this exact Code Generation plan?

This current-attempt decision covers `code-generation-plan.md`, its embedded complete native Testing Contract and `unit-test-instructions.md` for `u2-job-resilience`. Actual partial source/baseline/evidence and qualified-realm/admission/coverage obligations remain binding.

The current tool-produced approval/source tags are recorded here before presentation.

[Approval Fingerprint]: sha256:v3:e06536ab619bd0750b9b477232c99e7e8e12e319a87b776ab025193296e6f1d1
[Planned Source]: f15e575aa90973275e732081a343b46014dda8f9f5be35f17d14b6c4bffa64fc

- Approve Plan — Authorize developer implementation of this exact current plan and scoped test instructions through its protected receipt.
- Request Changes — Revise the plan or test instructions before implementation.

[Answer]: Approve Plan

## Re-entry Context — Stage Restart (2026-10-08)

The human rejected the stage after U1's skeleton checkpoint could not re-confirm against U2's reviewed repairs (review budget spent); the recorded revision instruction was "Restart the code-generation unit cycle". The engine executed the stage restart (`STAGE_JUMPED`, 2026-10-08T09:50:19Z), and U1's per-unit pass re-settled on the new attempt: fresh summary confirmation (authorization `3118bfb25725d881b5cf1e16613a382e49be2716df2d7269958c9f35e7f24c39`), fresh Plan Approval `sha256:v3:bdcce478a0c60fef225b0412e178a9d543bbf143f83b54536c6c2294cd46dae4`, adversarial review READY (`reviews/review-09.md`; all 16 findings resolved), and a fresh walking-skeleton checkpoint verified with the recorded command and human-approved. U2's recorded answers survive; this re-entry requires a fresh summary confirmation for this attempt, the outputs re-saved under it, a fresh exact Plan Approval, and fresh review passes for this unit. U2's plan and test instructions are retained unchanged; the only source delta since U2's last review is the two translate error-state tests (401/403, 404) added to `frontend/test/u2PreparedResult.test.tsx` under the prior revision, resolving that review's residual R-06 finding (u2 lane now 31 files / 144 tests; full suite 81 files / 461 tests). The earlier attempt's receipts (`sha256:v3:a20115e644e51b0d435f8754627e5de04e6758537a4cd908c546139e40c086b0` and older) no longer bind the current bytes and are not reused.

## Consolidated Summary Confirmation

- **Scope and basis:** U2 extends the delivered U1 frontend job surface (BFF-routed `contentJobApi`/typed contracts, `idempotencyService`, `jobState`, `jobDiagnostics`, `JobSubmissionForm`/`JobDialog`, `ErrorBoundary`/`ErrorBoundaryFallback`, live `JobStatus` with the fixed two-second SWR fallback, query-only `SummaryModal`, `PaperDetailIsland` composition) with translate capability and the remaining job acceptance and resilience cases. The plan derives from `unit-of-work.md` (U2), `contract-summary.md` (C1 submission enum/profile, C3 event/cursor contract, C4 owner/request reconciliation, preparedResult v1 and result error precedence) and `requirements.md`, and consumes the tested U1 shared guarantees; it adds no new backend controller/service/worker capability.
- **Translate:** complete translate parameter selection/submission (`targetLang: 'ko'`, scope abstract/full, supported persona default) and readable translation results through the existing query-only prepared-result path (the translation branch renders via `TranslationView`), preserving safe formatting and conditional focus.
- **Resilience:** complete reload recovery on the owner-bound captured original, corrupt/unavailable/quota-limited storage behavior, owner/request reconciliation and unavailable-original recovery feedback; replay ordering/deduplication and recreated-`EventSource` recovery across the verified BFF cursor contract (Last-Event-ID precedence), channel restoration, obsolete timer/response suppression and access-loss cleanup; terminal states never regress (ADR-013) and the two-second fallback never overlaps the stream.
- **Result coverage:** the full translation result-state matrix (all controlled states honored), authorized asset-ID copy, and conditional focus continuity.
- **Telemetry and evidence:** scrubbed job telemetry (connection latency/drop/recovery and diagnostic-delivery failure handling), applicable performance and accessibility evidence, extended tests plus combined U1/U2 regressions; at least 80% line coverage for new/changed frontend code and all existing suites green.
- **Authority limits:** no real database/operational evidence is claimed; backend/SQL/realm and staging/collector obligations remain as recorded; fresh Plan Approval precedes generation.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

