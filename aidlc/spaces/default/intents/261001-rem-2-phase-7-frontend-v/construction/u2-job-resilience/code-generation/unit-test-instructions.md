# U2 Unit Test and Verification Instructions

## Contract, Current Authority and Ordering

Use the complete unchanged Testing Contract embedded in `code-generation-plan.md`, hash `sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153`: test-after / test-last per component, Standard five–eight meaningful tests per component with happy path and at least two error/edge cases, and at least 80% line coverage over the new/changed u2 frontend sources. Existing suites must remain green (u1 scoped suite 23 files / 104 tests; full base suite 73 files / 421 tests).

This plan and these instructions descend from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `910a3a5ad706c1705121f43d3a8a35d96038f3b01cecb2b5eaf2623a8a807d61`). They are current proposals, not implementation permission: the fresh exact Plan Approval precedes developer writes. The plan is not current implementation or execution authority.

U2 is a frontend-behavior unit: implement the affected component fully, then write and run its tests. The data-model/repository/API layers are consumed as delivered U1 guarantees (validated in the u1 suite), not re-implemented.

## Unit-Scoped Runner and Commands

| Working directory | Exact scoped command | Meaning |
|---|---|---|
| `frontend` | `corepack pnpm@9.15.9 exec vitest run --config vitest.u2.config.ts` (or `./node_modules/.bin/vitest run --config vitest.u2.config.ts`) | Step 1 creates the config (jsdom, `test/u2*.test.{ts,tsx}` plus the retained compatibility files); the selected tests plus the config checks |
| `frontend` | `./node_modules/.bin/vitest run --config vitest.u2.config.ts --coverage` | ≥80% lines over new/changed u2 frontend sources |
| `frontend` | `./node_modules/.bin/tsc --project tsconfig.u2.json --noEmit --incremental false` | Strict u2 graph; pre-existing errors on untouched lines are reported, never introduced |
| `frontend` | `./node_modules/.bin/eslint components/JobSubmissionForm.tsx components/JobStatus.tsx components/SummaryModal.tsx components/TranslationView.tsx lib/jobState.ts lib/jobDiagnostics.ts lib/idempotencyService.ts` | Scoped lint; no rule weakening |
| `frontend` | `./node_modules/.bin/vitest run --config vitest.u1.config.ts` and `./node_modules/.bin/vitest run` | Combined u1 + full base regression before completion |
| `ops` | `.venv/bin/python -m pytest tests/test_u1_colima_executor.py tests/test_u1_db_bootstrap.py -q` | The intent's recorded Construction Verification Command remains runnable for the later checkpoint |

## Exact Test Files and Required Behaviors

| Component/layer | Exact new/extended tests | Required behavior |
|---|---|---|
| Submission (translate) | `frontend/test/u2JobSubmissionForm.test.tsx` | No POST on mount or selection change; complete C1 `JobInput` (paperId, version, targetLang 'ko', persona, scope); capture-before-send; recovery replays the captured original under the same key; owner mismatch or foreign original disables recovery; definite vs uncertain outcomes |
| Reload/storage/reconciliation | `frontend/test/u2Idempotency.test.ts` | Corrupt/corrupt-JSON, unavailable, and quota-exceeded reads and writes degrade to no-original without throwing; valid owner-bound original round-trips; slots isolated per paper/task/owner |
| Replay/reconnection | `frontend/test/u2JobStatus.test.tsx` | A recreated `EventSource` resumes from the last accepted cursor; duplicate/stale frames suppressed by `seq` watermark; poll-ahead then stream history never regresses; fallback↔live handoff without overlap; unmount/terminal/access-loss cleanup |
| Projection | `frontend/test/u2JobState.test.ts` | `seq` ordering, terminal stickiness, channel-restoration semantics, announcement deduplication |
| Result states (translate) | `frontend/test/u2PreparedResult.test.tsx` | Every controlled state renders for the translate branch (not-ready/expired/unavailable/transient/auth/not-found + ready); string fidelity; conditional focus continuity; zero generation/enqueue on any read |
| Asset-ID copy | `frontend/test/u2AssetIdCopy.test.tsx` | Copies the exact supplied authorized asset identifier as text (no URLs/tokens); absent id → no control; clipboard failure degrades quietly; keyboard operable |
| Telemetry | `frontend/test/u2JobDiagnostics.test.ts` | Connection latency/drop/recovery sequences; failing sender swallowed; bounded scrubbed records; no recursion |
| Accessibility/measurement | `frontend/test/u2InteractionMatrix.test.tsx` | Keyboard/focus across the new states; deduplicated polite announcements; bounded measurement values (connection timing, status mount timing) |

## Coverage and Failure Rules

- ≥80% lines over new/changed u2 frontend sources; Standard-strategy volume; all existing suites green; never weaken a test or threshold to pass — surface the gap instead.
- Read paths never generate/enqueue/submit; retries re-read; recovery replays only the owner-bound captured original; terminal states never regress (ADR-013); the fixed two-second fallback never overlaps the stream.
- Project mandates apply: native `fetch`/`EventSource`/`SWR`/`crypto.subtle`, `clsx` + `tailwind-merge`, CSS Modules + Tailwind, BFF-only content-job routing (`/bff/api/content-jobs/*`), strict TypeScript (no `any`), ARIA live region and Error Boundary on the SSE surface, no secrets or presigned URLs.
- No real database/operational evidence is claimed; backend/SQL/realm and staging/collector obligations remain as recorded outside this unit.
