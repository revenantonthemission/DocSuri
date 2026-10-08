# U2 Code Generation Summary — Remaining Job Capabilities and Resilience

## Sources and Evidence Identity

This record descends from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `ba249706a44a196bced2c938af7a6391966fdaa9c45e1140c65576b8bd516729`) and the fresh Plan Approval recorded against the current plan/test-instruction bytes (`sha256:v3:a20115e644e51b0d435f8754627e5de04e6758537a4cd908c546139e40c086b0`, `testing-posture verify --unit u2-job-resilience` => `ok:true`/`execution_allowed:true`). The plan and unit-test instructions were written after that confirmation and descend from it; the claim authority is this directory's `source-manifest.json` (15 writes for this unit). No lifecycle/approval/review setter was invoked outside the sanctioned flow.

## Implemented

- **Runner lane (Steps 1–2):** `frontend/vitest.u2.config.ts` (u2 + combined u1 regression + retained compatibility files, coverage → `./coverage/u2`, 80% line threshold), `frontend/tsconfig.u2.json` (strict graph for the u2 sources), and `package.json` scripts `test:u2`, `test:coverage:u2`, `typecheck:u2`, `lint:u2`.
- **Translate submission (Steps 3–4):** verified the translate branch sends the complete C1 `JobInput` (`paperId, version, targetLang:'ko', persona, scope`) with explicit-submit-only semantics, capture-before-send and owner-bound recovery; tests added.
- **Reload recovery and unavailable-original feedback (Steps 5–8):** `JobSubmissionForm` now surfaces controlled feedback when a stored attempt exists but its captured original is missing/corrupt/foreign, while a usable owner-bound original keeps same-key recovery; captured-original storage behavior covered end to end (corrupt JSON, task-type mismatch, ownerless records, quota/unavailable on every operation, owner scoping).
- **Replay/reconnection and restoration (Steps 9–12):** `JobStatus` recreates the stream after an error carrying the verified cursor (`lastEventId`), hands over to the fixed two-second SWR fallback without overlap, closes the replaced stream, never recreates after terminal, and treats an access loss (401 `auth` / 403 `forbidden` from the owner-scoped read) as view-clearing, work-cancelling cleanup; a 404 stays retryable because the contract's generic not-owned/unknown body is indistinguishable from propagation lag.
- **Translation result states and copy (Steps 13–16):** the query-only `SummaryModal` renders the translate branch across every controlled read state; a keyboard-operable **자산 ID 복사** control copies the exact authorized identifier as text (no URLs/tokens), confirms politely, renders nothing without an id, and degrades quietly on clipboard denial.
- **Telemetry and measurement (Steps 17–20):** scenario tests for the live → fallback → recreated-live sequence with a failing sender, terminal recorded once; `jobDiagnostics` gained two bounded measurement points wired to JobStatus — the live stream's mount-to-open `latencyMs` and a `status` mount-to-first-committed-status `latencyMs`, recorded once per job identity — with invalid values dropped and valid ones rounded; interaction-matrix tests cover the single polite live region with honest `aria-busy`, deduplicated announcements, and dialog initial focus.

## Tests and Evidence

| Lane | Result | Command |
|---|---|---|
| u2 scoped suite | 31 files / 141 tests green | `vitest run --config vitest.u2.config.ts` |
| u1 scoped suite (combined regression) | 23 files / 104 tests green | `vitest run --config vitest.u1.config.ts` |
| Full base suite | 81 files / 458 tests green | `vitest run` |
| u2 coverage | 84.83% lines over the u2 include set (threshold 80) | `vitest run --config vitest.u2.config.ts --coverage` |
| Strict types (u2 graph) | 81 pre-existing errors, none on u2-touched lines; changed files clean | `tsc --project tsconfig.u2.json --noEmit` |
| Lint | clean on the u2-touched source and test files | `eslint components/JobSubmissionForm.tsx components/JobStatus.tsx components/SummaryModal.tsx components/TranslationView.tsx lib/jobState.ts lib/jobDiagnostics.ts lib/idempotencyService.ts test/u2JobState.test.ts test/u2JobStatus.test.tsx test/u2JobDiagnostics.test.tsx` |

## Deviations

- The telemetry test file is `frontend/test/u2JobDiagnostics.test.tsx` (JSX, since it renders `JobStatus`) rather than the planned `.test.ts`.
- `TranslationView.tsx` sits at 30.7% in the u2 lane; it is unchanged by this unit and the aggregate (84.64%) clears the threshold. Aggregate, not per-file, is the enforced u2 floor here; the final changed-executable-line gate remains Step 47 territory.

## Known Remaining Obligations (not complete, not counted as done)

- The stricter imported-graph reconciliation (81 pre-existing errors in brownfield transitive files) and the final frozen-baseline changed-line coverage gate remain recorded at the stage level.
- Real-origin E2E, the real integrated invocation, and the skeleton/checkpoint re-verification remain outside this unit's dispatch.
- `traceability.json` enumerates all 129 assigned upstream ids (18 story/quality ids + 111 acceptance ids) with an all-GAP allocation — no row is upgraded to OK without executed acceptance evidence, so the traceability sensor reports an advisory all-GAP gap set with `missing_from_upstream_ids` empty; partial evidence pointers list this unit's test files.
- No real database/operational evidence is claimed; backend/SQL/realm and staging/collector obligations remain as recorded.
