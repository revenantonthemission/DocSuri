# U4 — Research and novelty · Code generation plan

Unit: `u4-research-novelty`. Branch: `feature/u4-research-novelty`. Scope: `feature` (classic), test-after, 80% floor for new code.

## Summary

- Builds: the private research and novelty capability (contexts, sessions, grounded turns, attachments, durable drafts, novelty analysis/discussion, expiring artifacts) as an embedded `ResearchWorkspace` library contribution.
- Touches: `backend/modules/research/**`, `backend/u4_*.py`, DB migrations, mounted routes, `frontend/src/u4-research/**`, `tests/u4_research_novelty/**`, `scripts/verify_docsuri_u4.py`, CI lane.
- Tests: standard strategy — 5–8 unit tests per component plus integration tests for the C07/C14 boundaries, run per-layer after each layer is implemented.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "classic",
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
  "input_sha256": "sha256:77c0b082630216906000ccb37b4fc83a137cb8f411a2d855bc16870d05dda38e",
  "contract_sha256": "sha256:fc00027e4c56b045698e998a393b3797378e1445c0a4b140320cbab37f2d0c36"
}
```

## Plan steps (test-after: implement each layer, then write and run its tests)

- [ ] **Step 1 — Project structure and production configuration skeleton.** Create `backend/modules/research/` (contexts, sessions, turns, evidence, attachments, drafts, novelty, artifacts) as an embedded module of the existing release; configuration entries for bounded limits (upload bytes, queue depth, concurrency, retry counts, artifact retention window) with recorded values and no paid provider. Trace: unit-of-work U4; NFR7.1, NFR8.1, NFR8.2.
- [ ] **Step 2 — Verify the existing test runner/configuration and record the exact unit-scoped command.** Confirm `backend/.venv/bin/python -m pytest tests/u4_research_novelty -q` runs before any test is written; record it in `unit-test-instructions.md`. Trace: Testing Contract `runner_step`.
- [ ] **Step 3 — Data model / database behavior — implement.** Tables and migrations for `ResearchContext` (C00 shape: purpose, revision, lifecycle), `ResearchSession` (lifecycle, tombstone, pending jobs), `ResearchTurn`, `NoveltyAnalysis`, `NoveltyDiscussion`, `ResearchArtifact` (immutable id/revision/contentHash, expiry, availability), `EvidenceRecord` (readState, coverage, provenance), `PrivateAttachment` (media allowlist, hash, disposition), `DraftRevision` (C00 kind spellings, CAS base, states), `NoveltyAssessment` (method scale). Trace: entities.md; FR14, FR15; NFR3.2, NFR5.1.
- [ ] **Step 4 — Data model / database behavior — write and run its tests after implementation.** Owner/context binding, tombstone dominance, monotonic sequences, immutable revision tuples, expiry sweep idempotence. Trace: NFR3.2–3.4, NFR5.3.
- [ ] **Step 5 — Repository / data access — implement.** Owner-scoped repositories for every entity, CAS save/consume/discard, tombstone-first deletion, evidence queries, atomic acceptance with recoverable dispatch obligation, single usage reconciliation. Trace: FR14, FR14.2, NFR10.4.
- [ ] **Step 6 — Repository / data access — write and run its tests after implementation.** Cross-owner and cross-context denial, CAS conflict returns current revision, exact-revision consumption with newer-edit survival, stale discard refusal. Trace: BR1.1–BR1.5, BR4.2, BR4.3, BR4.5.
- [ ] **Step 7 — Business logic — implement.** Grounded question flow with evidence/abstention and quotation verification; attachment permit/verify/extract with typed refusals; draft policy gate (`POLICY_UNRESOLVED`); novelty analysis and discussion lifecycles with cancellation CAS and no resurrection; export read with eligibility recheck; outbound retrieval target validation (scheme/host allowlist, private/loopback/link-local and redirect rejection). Trace: FR2.3, FR13.1–13.3, FR15.1–15.2, FR16.1–16.2; NFR1.4, NFR4.6, NFR5.2.
- [ ] **Step 8 — Business logic — write and run its tests after implementation.** Support/contradiction/insufficient fixtures, unread reference excluded, malformed model output, truncation disclosure, cancellation/completion race, policy-unresolved refusal, SSRF-target refusal. Trace: BR2.1–BR2.5, BR6.1–BR6.5, BR8.1–BR8.2.
- [ ] **Step 9 — API / endpoint — implement.** Mount the C07 operations on the existing host with the shared error vocabulary (`INVALID_ARGUMENT`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `POLICY_UNRESOLVED`, `DEPENDENCY_UNAVAILABLE`, `IDEMPOTENCY_CONFLICT`, `CAPACITY_EXHAUSTED`, `SOURCE_INELIGIBLE`, `OUTCOME_UNKNOWN`), plus the `C13` browser binding and the `C14` delivery hooks. Accepted-work dispatch stays **fail-closed** until the C14/C00 payload gate is closed (see Step 15). Trace: C07; NFR10.1, NFR10.2.
- [ ] **Step 10 — API / endpoint — write and run its tests after implementation.** Mounted-boundary contract conformance: state machines, error mapping, revoked/anonymous session refusal, private identity never resolving on a public route, idempotent retry. Trace: NFR1.3, NFR4.1–4.4, NFR10.1.
- [ ] **Step 11 — Frontend behavior — implement.** `frontend/src/u4-research/**` views in the shared shell: sessions, evidence with sources, attachments, drafts (acknowledged vs pending vs failed), novelty analysis/discussion and progress, with the inherited Korean responsive WCAG 2.2 AA interaction contract and confirmed destructive scopes; presentation reads create no work. Trace: NFR2.1, NFR6.1–6.3.
- [ ] **Step 12 — Frontend behavior — write and run its tests after implementation.** Vitest component tests plus browser journeys for the mounted flow, including pending/unknown states, account-switch clearing and keyboard/focus behaviour. Trace: NFR2.1, NFR6.1.
- [ ] **Step 13 — Environment/build configuration.** Scoped CI lane for this unit (lint, typecheck, unit, database, repository, integration, operations, frontend, contract-conformance, privacy/policy gates, coverage, evidence) per `infrastructure-design/cicd-pipeline.md`; coverage configuration with the 80% floor; refusal states never converted into skips. Trace: NFR8.1–8.2, NFR10.3.
- [ ] **Step 14 — Documentation and traceability.** `code-summary.md`, `source-manifest.json` (every created/modified/deleted application path), `traceability.json` for this stage, and the unit's `scripts/verify_docsuri_u4.py` phases used by the checkpoint. Trace: stage Step 5.
- [ ] **Step 15 — Execution payload codec (GATED — not enabled in this pass).** Registered only after the C00/C14 amendment adds a ResearchWorkspace accepted-input/payload type and `readExecutionPayload` accepts U4's kinds; then prove the mounted `acquireExecutionClaim` → payload-read → `recordCompletion` round trip. Until then acceptance refuses with the incompatibility outcome and this step stays unchecked. Trace: infrastructure-design "Execution payload enablement"; NFR10.3; open cross-unit gate.

## Requirement → step traceability

| Requirement | Steps |
|---|---|
| FR2.3 | 5, 7, 9 |
| FR13, FR13.1–13.3 | 3, 7, 8, 11 |
| FR14, FR14.1–14.2 | 3, 5, 6, 7, 11 |
| FR15, FR15.1–15.2 | 3, 5, 7, 8, 11 |
| FR16.1–16.2 | 7, 9 |
| FR17.2, FR19.x (contributor) | 5, 13 |
| NFR1–NFR3 | 4, 6, 8, 10, 12 |
| NFR4–NFR5 | 3, 6, 7, 10, 13 |
| NFR6–NFR9 | 11, 12, 13, 14 |
| NFR10 | 5, 9, 10, 15 |
