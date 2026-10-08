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

The human-selected path completed: `u1-job-skeleton`'s frontend completion pass settled on its restarted attempt (fresh Plan Approval `sha256:v3:ea953058…`, adversarial review READY with all prior findings resolved, walking-skeleton checkpoint verified with the recorded command and human-approved on 2026-10-08). The delivered U1 frontend job surface U2 extends now exists on disk: BFF-routed content-job transport with typed contracts/`seq` watermarking (`lib/api/contentJobApi.ts`, `lib/api/contentJobContracts.ts`), `idempotencyService`, `jobState`, `jobDiagnostics`, `cn`, `JobSubmissionForm`/`JobDialog`, `ErrorBoundary`/`ErrorBoundaryFallback`, the live `JobStatus` with the fixed two-second SWR fallback, the query-only `SummaryModal`, and the `PaperDetailIsland` composition — with 23 u1 test files (104 tests) green alongside the base suite (421 tests). U2's plan therefore builds on that delivered surface as its unit definition prescribes. The Q1 situation text above is retained as provenance of the state at the time of the question; it no longer describes the current tree.
