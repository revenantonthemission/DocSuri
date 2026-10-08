# U2 Job Resilience — Code Generation Plan

Authority: current attempt of `code-generation` for unit `u2-job-resilience`; this plan descends from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `ba249706a44a196bced2c938af7a6391966fdaa9c45e1140c65576b8bd516729`). Basis: the delivered and approved U1 frontend job surface, `unit-of-work.md` (U2), `contract-summary.md` (C1–C4), and `requirements.md`. No new backend controller/service/worker capability is added; U1's tested shared guarantees are consumed. Fresh Plan Approval precedes generation.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "feature",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "**Methodology:** test-after\n**Ordering:** Test-last per component — Implement component fully, then write its tests.\n\n**Scope floors (feature scope):**\n- 80% line-coverage floor for new code\n- CI execution before merge\n- Existing test suites must remain green (473 backend + 356 frontend)\n\n**Evidence from reverse-engineering:**\n- Current coverage: ~65% overall, but Phase 7 target components at 0% (JobStatus, contentJobApi BFF routing)\n- 356 frontend tests passing (Vitest + React Testing Library)\n- 473 backend tests passing\n- Playwright E2E configured (~25 tests, ~30% coverage)\n- CI runs lint, typecheck, test:coverage, test:e2e\n- **Gap:** Phase 7 components (JobStatus, AssetViewer migration, contentJobApi BFF routing) completely untested\n- **Gap:** No Error Boundary tests, no SSE polling fallback tests, no idempotency key tests\n\n**Affirmed posture for Phase 7:**\n- Maintain test-after methodology (team default)\n- Ordering: Test-last per component (implement fully, then test)\n- 80% coverage floor for new code enforced in CI\n- All existing tests must remain green\n\n---"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Meet an 80% line-coverage floor.",
      "Run the selected tests in CI before merge."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:47a0413847b87a1c376dc0475c75fdb4bb92763764f6800b049333b085452793",
  "contract_sha256": "sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153"
}
```

## Ordered Implementation Steps

U2 is a frontend-behavior unit: the contract's "frontend behavior" layer is implemented and tested per step; the data-model/repository/API layers are consumed as delivered U1 guarantees, not re-implemented. Every step implements its component fully before its tests (test-after).

| Step | Work and completion condition | Story / requirement trace |
|---|---|---|
| [ ] Step 1 | Add the u2 unit-scoped runner and strict-type configuration: `frontend/vitest.u2.config.ts` (jsdom, `test/u2*.test.{ts,tsx}` plus the retained compatibility files), `frontend/tsconfig.u2.json` (base strict flags + the u2 file set), and `package.json` scripts `test:u2`, `test:coverage:u2`, `typecheck:u2`, `lint:u2`; record the exact commands in `unit-test-instructions.md` and verify they run against the current tree. | NFR11; runner step |
| [ ] Step 2 | Author/run the runner-config checks: the u2 config selects u2 + retained tests and excludes e2e; `test:u2` green on the pre-change tree (baseline); typecheck/lint scripts resolve. | NFR11; runner step |
| [ ] Step 3 | Complete the translate submission surface in `JobSubmissionForm` as needed against the confirmed scope: translate branch offers the selected scope (abstract/full) with the supported defaults (`targetLang: 'ko'`, supported persona) and submits the complete five-field `JobInput`; explicit submit only; capture-before-send; owner-bound same-key recovery unchanged. | US1.1/US4.1/US4.2; C1 |
| [ ] Step 4 | Author/run translation submission tests: no POST on mount/selection; complete body; same-key recovery replays the captured original; owner mismatch disables recovery; definite vs uncertain outcomes. | FR1/4/6; BR1.3–5 |
| [ ] Step 5 | Complete reload recovery and unavailable-original feedback: a reload with a missing/corrupt/foreign captured original surfaces the controlled unavailable-original state (no replay, no new key); the affordance disappears; existing captured recovery keeps working. | US4.1/US4.2; C4 |
| [ ] Step 6 | Author/run reload-recovery tests: corrupt/missing/foreign original → feedback + no recovery; valid owner-bound original → same-key replay; diverged draft isolation retained. | US4.1/US4.2; ADR-013 |
| [ ] Step 7 | Complete storage-behavior coverage: corrupt JSON, unavailable storage, quota-exceeded on read and write degrade to no-original without throwing while a valid key/original still round-trips; surface feedback only where the flow promises it. | US4.1; NFR6 |
| [ ] Step 8 | Author/run storage-behavior tests (corrupt/unavailable/quota read+write) incl. the owner-slot isolation. | NFR6; BR1.3–5 |
| [ ] Step 9 | Complete replay ordering/deduplication and recreated-`EventSource` recovery in `JobStatus`: resubscribe with the verified cursor (`Last-Event-ID` precedence through the BFF), duplicate/stale/obsolete suppression via the `seq` watermark, and no state regression below the accepted watermark. | US2.1/US2.2; C3 |
| [ ] Step 10 | Author/run replay tests: recreated source resumes from the last accepted id; duplicates/stale frames ignored; poll-ahead then stream history never regresses; terminal stickiness. | NFR5; BR4 |
| [ ] Step 11 | Complete channel restoration, obsolete timer/response suppression and access-loss cleanup: reconnect backoff/fallback handoff without overlap; timers and in-flight reads cancelled on terminal/unmount/context change; an access loss clears views and cancels work. | US2.4/US2.5; NFR5/6 |
| [ ] Step 12 | Author/run channel-restoration/cleanup tests: fallback→live handoff, obsolete poll responses dropped, unmount/terminal cleanup, access-loss clearing. | NFR5/6/9; BR4 |
| [ ] Step 13 | Complete the translation result-state matrix in `SummaryModal`/`TranslationView` paths: every controlled state renders for the translate branch (not-ready/expired/unavailable/transient/auth/not-found + ready), safe formatting of translated content, and conditional focus continuity. | US3.1/US3.3; C2 |
| [ ] Step 14 | Author/run translation result-state tests: all controlled states; string fidelity; conditional focus; no generation/enqueue on any read outcome. | C2/C4; NFR1.5/12.2 |
| [ ] Step 15 | Implement the authorized asset-ID copy affordance in the result modal: copy the supplied authorized asset identifier as text (no URLs, no tokens), keyboard-operable, with a polite confirmation and no clipboard failure surface break. | US3.4; SEC/asset-ID copy |
| [ ] Step 16 | Author/run asset-ID copy tests: copies the exact identifier; absent id → no control; clipboard failure degrades quietly; keyboard activation. | US3.4; NFR10 |
| [ ] Step 17 | Complete job telemetry scenarios: connection latency, drop and recovery signals plus diagnostic-delivery failure handling through the bounded scrubbed emitter (a failing sender never breaks the UI; no content/ids in records). | US8.1; NFR7/9 |
| [ ] Step 18 | Author/run telemetry tests: latency/drop/recovery sequences; failing sender swallowed; scrubbed bounded records; no recursion. | NFR7.1–4 |
| [ ] Step 19 | Complete the accessibility and performance evidence for the new states: keyboard reachability and focus order across the translate/recovery/result states, live-region politeness, and the measurement points (connection timing, status mount timing) recorded for later benchmark verification. | US2.1/US7 slice; NFR9/10 |
| [ ] Step 20 | Author/run accessibility/measurement tests: focus continuity, announcements deduplicated, measurement hooks emit bounded values. | NFR9/10; AC7.1 |
| [ ] Step 21 | Extend the combined regressions: run the u2 suite together with the u1 suite and the full base suite; repair any cross-suite regressions without weakening expectations. | all U2 slices; NFR12.2 |
| [ ] Step 22 | Verify the coverage floor: `test:coverage:u2` reports ≥80% lines over new/changed u2 frontend sources; surface and close gaps. | scope floor |
| [ ] Step 23 | Record the actual files, decisions, results and deviations; write `code-summary.md`, `source-manifest.json` claims and `traceability.json` rows for this unit. | NFR11 |
| [ ] Step 24 | Obtain the fresh current-attempt review; repair findings through the required flow; present completion. | required review |

## Planned Source Footprint and Blast Radius

Planned additions/changes (all frontend; nothing claimed until written and recorded in `source-manifest.json`):

| Planned source area | Change and consumers | Impact / tests |
|---|---|---|
| `frontend/vitest.u2.config.ts`; `frontend/tsconfig.u2.json`; `frontend/package.json` scripts | Unit-scoped runner/strict config, same pattern as the u1 setup | Config checks; no source weakening |
| `frontend/components/JobSubmissionForm.tsx`; `frontend/lib/idempotencyService.ts` | Translate-submission completion, unavailable-original feedback, storage-behavior surfaces | High; submission/recovery/storage tests |
| `frontend/components/JobStatus.tsx`; `frontend/lib/jobState.ts` | Cursor-resume reconnection, obsolete suppression, restoration/cleanup | High; replay/restoration tests |
| `frontend/components/SummaryModal.tsx`; `frontend/components/TranslationView.tsx` | Translation result-state matrix, safe formatting, focus continuity, asset-ID copy | High; result-state tests |
| `frontend/lib/jobDiagnostics.ts` | Latency/drop/recovery scenarios, failing-sender handling | Medium; telemetry tests |
| `frontend/test/u2*.test.{ts,tsx}` | New unit tests for every changed component | Standard strategy floors |
| `frontend/components/PaperDetailIsland.tsx` | Only if composition gaps surface during integration tests | Parent regression tests |

## Exact Test Files and Required Behaviors

| Component/layer | Exact new/extended tests | Required behavior |
|---|---|---|
| Submission (translate) | `frontend/test/u2JobSubmissionForm.test.tsx` | No submit on mount/selection; complete C1 body; capture-before-send; same-key original replay; owner mismatch/foreign original disabled; definite vs uncertain |
| Reload/storage/reconciliation | `frontend/test/u2Idempotency.test.ts` | Corrupt/unavailable/quota read+write degrade; owner slot isolation; original round-trip; no throw ever |
| Replay/reconnection | `frontend/test/u2JobStatus.test.tsx` | Recreated source resumes from cursor; duplicate/stale suppressed; poll-ahead no regression; fallback↔live handoff; cleanup |
| Projection | `frontend/test/u2JobState.test.ts` | `seq` watermark ordering, terminal stickiness, channel restoration semantics |
| Result states (translate) | `frontend/test/u2PreparedResult.test.tsx` | All controlled states for the translate branch; string fidelity; focus continuity; zero generation |
| Asset-ID copy | `frontend/test/u2AssetIdCopy.test.tsx` | Exact identifier copied; absent → no control; clipboard failure quiet |
| Telemetry | `frontend/test/u2JobDiagnostics.test.ts` | Latency/drop/recovery sequences; failing sender swallowed; bounded scrubbed records |
| Accessibility/measurement | `frontend/test/u2InteractionMatrix.test.tsx` | Keyboard/focus across states; deduplicated announcements; bounded measurement values |

## Planned Exact U2 Commands

| Working directory | Command | Readiness and scope |
|---|---|---|
| `frontend` | `./node_modules/.bin/vitest run --config vitest.u2.config.ts` | After Step 1; exact u2 + retained tests |
| `frontend` | `./node_modules/.bin/vitest run --config vitest.u2.config.ts --coverage` | ≥80% lines over new/changed u2 sources |
| `frontend` | `./node_modules/.bin/tsc --project tsconfig.u2.json --noEmit --incremental false` | Strict u2 graph (pre-existing errors on untouched lines reported, never introduced) |
| `frontend` | `./node_modules/.bin/eslint components/JobSubmissionForm.tsx components/JobStatus.tsx components/SummaryModal.tsx components/TranslationView.tsx lib/jobState.ts lib/jobDiagnostics.ts lib/idempotencyService.ts` | Scoped lint, no rule weakening |
| `frontend` | `./node_modules/.bin/vitest run --config vitest.u1.config.ts` and `./node_modules/.bin/vitest run` | Combined u1 + full base regression before completion |
| `ops` | `.venv/bin/python -m pytest tests/test_u1_colima_executor.py tests/test_u1_db_bootstrap.py -q` | The intent's recorded Construction Verification Command stays runnable for the later checkpoint |

## Coverage, Fixtures and Failure Rules

- Test-after per component; Standard strategy volume (5–8 meaningful tests per component) plus edge cases; ≥80% lines over new/changed u2 sources; all existing suites stay green.
- No test may be weakened to pass; no threshold lowered; no skipping real branches.
- All client behavior stays on the project mandates: native fetch/EventSource/SWR/crypto.subtle, `clsx`+`tailwind-merge`, CSS Modules + Tailwind, BFF-only content-job routing, strict TypeScript (no `any`), ARIA live regions and Error Boundary on the SSE surface.
- Read paths never generate/enqueue; retries re-read; recovery replays only the owner-bound captured original; terminal states never regress.
- No real database/operational evidence is claimed; backend/SQL/realm and staging/collector obligations remain as recorded outside this unit.
