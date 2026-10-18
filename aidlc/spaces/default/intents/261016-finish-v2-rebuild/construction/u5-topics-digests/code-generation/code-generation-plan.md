# U5 — Topics and digests · Code generation plan

Unit: `u5-topics-digests`. Branch: `feature/u5-topics-digests`. Scope: `docsuri-v2-finish` (express base), test-after, standard strategy; existing suites stay green.

## Summary

- Builds: the topics-and-digests capability (follow/unsubscribe/reactivate, per-topic digest settings, scheduled preparation from eligible corpus within the configured window, real email delivery with single-flight and explicit reconciliation, account lifecycle participation) as an embedded contribution of the existing release.
- Touches: `backend/modules/topics/**`, `backend/u5_*.py`, migration SQL, mounted routes and the worker chain, `backend/lifecycle_effects.py` + `backend/control_worker.py` (participant registration), `frontend/src/u5-topics/**`, `tests/u5_topics_digests/**`, `scripts/verify_docsuri_u5.py` + `scripts/serve_docsuri_u5.py`, per-unit frontend configs, CI lane.
- Tests: standard strategy — five to eight tests per component plus integration tests for the key boundaries, run per layer after each layer is implemented (test-after); existing suites remain green.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "express",
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
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
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
  "input_sha256": "sha256:feb040c7898e5b924695da36d1e6633e1d2cad660b370bc4d3d863451b5e0cf9",
  "contract_sha256": "sha256:0b3bdbd990d6def665d447995282ba760f054c761c3ccf40dbbb9fc1b114553b"
}
```

## Plan steps (test-after: implement each layer, then write and run its tests)

- [x] **Step 1 — Branch and project structure and production configuration skeleton.** Create `feature/u5-topics-digests` from the current develop-equal HEAD; create `backend/modules/topics/` (`http.py`, `service.py`, `scheduler.py`, `preparation.py`, `delivery.py`, `repository.py`, `errors.py`, `u5_schema.sql`, `__init__.py`) as an embedded module of the existing release, leaving the superseded legacy `backend/modules/trends/` untouched (it is not part of the v2 assembly chain); `backend/u5_host.py` contribution chained on `assemble_u4` (service, owner-scoped router, worker hook on the existing worker entry that evaluates due topics each pass); configuration entries for bounded limits (selection budget, digest size, recovery bounds) with recorded values, no paid provider; the email delivery capability reused from the built application (`backend/modules/accounts/integrations/email.py` seam: local sink/mock in test profiles, the maintainer-configured path in real operation). Trace: unit-of-work U5; NFR6.1; infrastructure-design `cicd-pipeline.md`.
- [x] **Step 2 — Verify the existing test runner/configuration and record the exact unit-scoped command.** Create `backend/pytest.u5-topics-digests.ini` and the `tests/u5_topics_digests/{database,repository,component,integration,operations,runtime}` roots; confirm `backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q` collects cleanly before any test is written and record the exact commands in `unit-test-instructions.md`. Trace: Testing Contract `runner_step`.
- [x] **Step 3 — Data model / database behavior — implement.** `topics` schema tables and constraints for `FollowedTopic` (status active/unsubscribed, normalized topic key, identity preserved across reactivation), `DigestSettings` (cadence, delivery time, delivery day, window, revision), `DigestRun` (explicit state machine `prepared→sending→sent|failed|unknown`, plus `empty`/`discarded`; window bounds; settings-revision stamp; chronological window uniqueness excluding discarded runs, BR2.4), `DeliveryOutcome` (observed + reconciled states, assumption named), `SendLogEntry` (transport receipt, timestamps, `pathKind`), `TopicDeliveryWatermark` (per-topic sent content), and `topics.lifecycle_evidence` (coordinator contract); migrations applied through the unit verify runner per the U4 precedent. Trace: entities.md; FR1.1–FR1.4; NFR4.1.
- [x] **Step 4 — Data model / database behavior — write and run its tests after implementation.** Constraint probes: one active subscription per (account, normalized key); reactivation keeps identity/watermark/history; window uniqueness with discarded runs excluded; watermark uniqueness; run states restricted to the machine. Trace: FR1.1, FR1.3; NFR4.1.
- [x] **Step 5 — Repository / data access — implement.** Owner-scoped repositories for every entity; settings save with revision bump and discard of prepared runs (BR1.3); single-flight query (BR3.1); unreconciled-unknown pause query (BR3.2); chronological window ordering guard (BR2.4); watermark reads and appends; run transitions as checked state changes; lifecycle evidence writes; owner isolation on every read and write (BR5.1). Trace: FR1.1–FR1.4; NFR1.1, NFR1.2.
- [x] **Step 6 — Repository / data access — write and run its tests after implementation.** Cross-owner denial on every path; duplicate active refusal; revision advance discards prepared runs; duplicate window refusal under racing ticks; watermark exclusion. Trace: BR1.1, BR1.3, BR2.2, BR2.4; NFR1.1.
- [x] **Step 7 — Business logic — implement.** Follow/unsubscribe/reactivate semantics (BR1.1, BR4.1, including queued-work drop and in-flight attempt completion); settings validation and revision handling (BR1.2, BR1.3); scheduler evaluation of cadence + delivery time in the account's timezone with idempotent preparation (BR1.2, BR2.4); content selection from eligible corpus inside the inclusive window, watermark excluded, empty recorded explicitly (BR2.1–BR2.3); send attempt through the built email capability with single-flight, active-status, consent, and reconciliation-pause guards (BR3.1, BR3.2, BR1.4, BR4.2), writing the SendLogEntry and recording `sent`/`failed`/`unknown`; reconciliation check reading send-log/recipient evidence plus the owner's explicit run-scoped resolve action with the assumption named (BR3.2); restart/recovery sweep moving orphaned `sending` runs to `unknown` with the evidence gap recorded (BR3.4); failed runs never auto-resent (BR3.3); lifecycle participant `TopicsDigests` (writes only its own tables) registered with the coordinator (BR4.3; `backend/lifecycle_effects.py` map + `backend/control_worker.py` participants). Trace: FR1.1–FR1.6; NFR2.1, NFR2.2; NFR4.2, NFR4.3.
- [x] **Step 8 — Business logic — write and run its tests after implementation.** Timezone boundaries and late firing; re-fire idempotence; chronological ordering; empty vs failed distinction; single-flight race; unknown pause blocks new sends; resolve delivered re-applies the watermark and resolve not-delivered leaves the window able to re-deliver inside later bounds; orphan sweep; unsubscribe queued vs mid-flight; consent stop and restore; reactivation produces no repeat delivery; lifecycle disposition reporting. Trace: BR1.1–BR5.1; NFR2.1; NFR4.1–4.3.
- [x] **Step 9 — API / endpoint — implement.** Mount `GET topics`, `POST topics` (follow), `DELETE topics/{id}` (unsubscribe), `GET/PUT topics/{id}/settings` (revision-checked save), `POST topics/{id}/runs/{runId}/resolve` (body names the assumption) on the existing host with the shared error vocabulary; owner checks on every access; denials surface as plain refusals. Trace: FR1.1, FR1.2, FR1.4, FR1.5; NFR1.1, NFR1.2.
- [x] **Step 10 — API / endpoint — write and run its tests after implementation.** Mounted-boundary contract conformance: state-machine guards, revision conflict response, owner denial, idempotent retry, duplicate notice, anonymous refusal. Trace: NFR1.1, NFR4.1; BR5.1.
- [x] **Step 11 — Frontend behavior — implement.** `frontend/src/u5-topics/**` per frontend-components.md: `TopicsView`, `FollowedTopicsSection`, `TopicList`, `TopicRow` (`TopicSummary`, `DigestSettingsLink`, `ResolveUnknownControl`, `UnsubscribeButton`), `FollowTopicAction`, `DigestSettingsForm` (`CadenceSelect`, `DeliveryTimeInput`, `DeliveryDaySelect`, `ContentWindowSelect`, `InheritedLevelNote`, `SaveButton`), `ConfirmationDialog`; established Transport/SWR patterns, acknowledged-before-optimistic states, inline validation on blur, polite live region for outcome changes (never color-only), Korean labels, WCAG 2.2 AA. Trace: FR1.1, FR1.2, FR1.4, FR1.5; NFR5.1; NFR6.1.
- [x] **Step 12 — Frontend behavior — write and run its tests after implementation.** Vitest + RTL per component (loading/empty/error/ready/partial, duplicate notice, save-failure retry-safe state, stale-revision reload offer, dialog focus trapping and return) plus mounted browser journeys over the real API/DB (follow → settings → unsubscribe; resolve control; empty digest state). Trace: NFR5.1; FR1.1–FR1.5.
- [x] **Step 13 — Environment/build configuration.** `scripts/verify_docsuri_u5.py` (phases `setup/migrate/database/repository/component/integration/browser/coverage` following the U4 runner precedent; `SCHEMAS` extended with `topics`; `MIGRATIONS` = the U4 tuple plus U5's SQL), `scripts/serve_docsuri_u5.py` (owned realm and HTTPS local transport), `frontend/vitest.u5-topics.config.ts`, `frontend/tsconfig.u5-topics.json`, `frontend/playwright.u5-topics.config.ts`, `backend/.coveragerc.u5`, and the scoped CI lane `.github/workflows/u5-topics-digests.yml` (shared contracts, frontend, backend, browser jobs mirroring the U4 lane); refusal states never converted into skips. Trace: NFR6.1; infrastructure-design `cicd-pipeline.md`.
- [x] **Step 14 — Documentation and traceability.** `code-summary.md`, `source-manifest.json` (every created/modified/deleted application path), `traceability.json` for this stage, and the `scripts/verify_docsuri_u5.py` phases used by the completion checkpoint (real email path evidence with `pathKind`). Trace: stage Step 5.

## Requirement → step traceability

| Requirement | Steps |
|---|---|
| FR1.1 | 3, 5, 7, 9, 11 |
| FR1.2 | 3, 5, 7, 9, 11 |
| FR1.3 | 3, 5, 7, 11 |
| FR1.4 | 3, 5, 7, 8, 9, 10, 11, 12 |
| FR1.5 | 3, 5, 7, 9, 11 |
| FR1.6 | 3, 5, 7, 8 |
| NFR1 | 5, 6, 9, 10 |
| NFR2 | 7, 8 |
| NFR3 | — (N/A for U5: no external-service credentials; the Notion token belongs to U6) |
| NFR4 | 3, 7, 8, 10 |
| NFR5 | 11, 12, 13 |
| NFR6 | 1, 13 |
