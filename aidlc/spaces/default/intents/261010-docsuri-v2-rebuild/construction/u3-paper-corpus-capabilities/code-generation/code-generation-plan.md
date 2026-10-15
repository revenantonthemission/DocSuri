# U3 paper and corpus capabilities — code generation plan

## Summary

- Builds: Complete corpus ingestion/publication, source-change and withdrawal propagation, discovery and citations, content reading, assistance work and the owner glossary in the shared local application.
- Touches: Existing corpus/discovery/summarization modules, the shared host and transactions facility, the worker control loop, shared contracts C04–C06, the React workspace, U3 test harness and scoped CI.
- Tests: At least 40 component cases across eight groups, 32 real-store/API cases, 12 browser journeys and the U3 operational/fault families, plus cumulative U1/U2 regressions.

## Scope and inputs

This plan implements U3's approved contribution, using [functional workflows W1–W11](../functional-design/functional-spec.md), [entities](../functional-design/entities.md), [rules BR1.1–BR9.2](../functional-design/rules.md), [frontend specification](../functional-design/frontend-components.md), [security requirements](../nfr-requirements/security-requirements.md), [technology decisions](../nfr-requirements/tech-stack-decisions.md), [security design](../nfr-design/security-design.md), [logical components](../nfr-design/logical-components.md) and the [pipeline/operations design](../infrastructure-design/cicd-pipeline.md). The [unit definition](../../../inception/units-generation/unit-of-work.md), [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md), [requirements](../../../inception/requirements-analysis/requirements.md), [domain ownership](../../../inception/domain-design/components.md) and [canonical contracts](../../../inception/contract-design/contract-summary.md) remain authoritative.

User Stories was skipped; map to stable requirement IDs (FR1–FR4, FR9, FR18 lead; supporting rows as assigned) instead of inventing stories. U3 extends the same application; no parallel corpus, search or job service is introduced. The $0 limit prohibits paid fallback: unresolved source permissions, model readiness, provider terms or capacity yield explicit `POLICY_UNRESOLVED`/degraded/unavailable states, never fabricated output. U1's recorded normal-assistance, semantic-search and figure limitations must be reconciled with real evidence, and the four recorded job defects (Q-01–Q-04) close through the real mounted transport. Carried design-stage review findings (functional design, NFR requirements, NFR design, infrastructure design) are tracked for their gates and must not be masked by green tests.

## Current implementation evidence and intended source boundary

Base: the completed U1/U2 assembly on the working branch (U1 PR #44 `1c2cbd5c`, U7 PR #45 `5fbccc1f`, U2 checkpoint approved 2026-10-15). Existing extension points: the shared host (`backend/local_host.py`), owner transactions (`backend/transactions.py`), the worker control loop (`backend/control_worker.py`, `backend/control_runtime.py`), and the corpus/discovery/summarization modules under `backend/modules/` that U1 sliced and U2 touched. Reuse and strengthen these owners; verify current adapters and consumers before changes.

| Boundary | Planned changes and ownership |
|---|---|
| Contracts | Implement against C04–C06/C13/C14 as recorded (R-01 single projection writer; eligibility dominance; snapshot windows; change facts; claim/fence/progress/result bindings). Coordinate any schema/binding change through the existing generators and consumers first. |
| CorpusContent | Extend `backend/modules/corpus/` (and owner-local structured modules) with canonical identity/version/dedup, eligibility revisions, change facts, run/stage effects, watermarks, projection batches/publication CAS and content/asset reads. |
| Discovery | Extend `backend/modules/discovery/` with the query vocabulary, snapshot-bound windows, lexical/semantic retrieval and disclosed degradation, citation traversal bounds and completed-search facts/checkpoint. |
| PaperAssistance | Extend `backend/modules/summarization/` (owner module) with acceptance binding, dispatch responsibility, claim/fence execution, ordered progress, prepared results and the owner glossary. |
| Shared application | Coordinate `backend/local_host.py`, worker control loop and transaction facility; no cross-owner SQL hidden in host glue. |
| Frontend | Extend `frontend/src/` with query/filters/results, reading surface, citation explorer, assistance panel/progress/results and glossary surfaces on the existing shell and Transport. |
| Verification | New `tests/u3_paper_corpus_capabilities/`, `backend/pytest.u3-paper-corpus.ini`, frontend unit/E2E paths and configs, `scripts/verify_docsuri_u3.py`; share proven runner primitives without copying fixture-reset semantics. |
| Pipeline/docs | Scoped U3 workflow and operations instructions; lock/config changes only for justified dependencies with identity/security/license evidence. |

## Ordered implementation steps

Each layer is implemented, then its tests are written and run, before moving to the next layer. Runner readiness precedes the first executable test. Keep every checkbox unticked until its work and evidence actually exist.

### Step 1 — Establish source/configuration and canonical prerequisites

- [x] Inventory the actual mounted corpus/discovery/assistance consumers, routes, stores and worker participants; distinguish current owners from legacy slices. Confirm rollback/source boundaries and carry U1's recorded limitations.
- [x] Coordinate C04–C06/C13/C14 exact revisions/errors where U3 completes behavior: projection-writer closure (R-01), eligibility/change facts, snapshot windows, claim/fence/progress framing and prepared-result semantics. No undocumented contract divergence.
- [x] Amend canonical contracts/schemas together where required, regenerate bindings, validate actual consumers, and handle required-field/version compatibility explicitly.
- [x] Add the minimal U3 module/configuration skeleton: finite limit/policy schema (batches, queues, retries, pages, traversal, model concurrency). Missing required policy/permission/model/provider evidence yields explicit unavailability; no successful placeholder.
- [x] Record planned source paths and changed ownership in the code record. Do not edit the AI-DLC installation or unrelated legacy features.

Trace: BR1.1–1.3, BR3.1–3.2, BR7.1–7.2; C04–C06/C13/C14; NFR4.1/NFR5.1/NFR7.1/NFR10.1–10.2.

### Step 2 — Make the exact U3 runners ready

- [x] Create the U3 pytest markers/configuration and the frontend unit/browser configurations described in [test instructions](unit-test-instructions.md); preserve existing U1/U2 paths.
- [x] Implement the bootstrap/preflight needed by later phases: validated synthetic profile/root/realm ownership/expiry, private files/permissions, port checks, deterministic fixtures for corpus/search/assistance. Keep full workload/restore/package phases for Step 13.
- [x] Verify toolchain/frozen dependencies and test collection. Fail zero or accidentally skipped suites; initial collection is runner evidence, not behavior success. Verify each exact command before its first execution step.

Trace: NFR7.2–7.3/NFR8.1–8.2; BR2.4. The fixture reset must not erase the state under an interruption/restart test.

### Step 3 — Implement corpus identity, eligibility and publication data models

- [x] Add compatible owner migrations for Paper/PaperVersion/PublicContent canonical identity, version labels, provenance, eligibility decisions and revisions; CorpusProcessingRun stage effects, watermarks and recovery evidence; CorpusChangeFact ordering.
- [x] Add projection batch receipts, publication generations with CAS state, manifest identity and compatibility fields; quarantine/restore-related tables needed by the operations phase.
- [x] Apply least-privileged owner roles, finite constraints/indexes and migration identity/compatibility checks to the owned synthetic realm; record restriction evidence.

Trace: W1–W3; ENT ownership in entities.md; BR2.1–2.4/BR3.1–3.2.

### Step 4 — Write and run data-model/database tests

- [x] Create `tests/u3_paper_corpus_capabilities/database/` checks for canonical identity/dedup, eligibility revisions, change-fact ordering, stage-effect/watermark discipline and publication CAS.
- [x] Test migration/restart identity, competing publication, duplicate/reordered batches and crash boundaries with real PostgreSQL locks; verify no false publication or watermark advance.
- [x] Run the database phase under finite profile limits; preserve failures and inspect authoritative rows, not just HTTP or mock call counts.

Trace: V2/V4/V5/V6; NFR3.3/NFR3.4/NFR10.2.

### Step 5 — Implement repositories and read projections

- [x] Extend owner repositories with parameterized owner-first queries, stable bounded keyset pages/cursors, exact receipt/intent replay and immutable acknowledgements for runs, search executions, jobs and results.
- [x] Implement content/asset reads with opaque authorized handles under current eligibility, source-only/unavailable dispositions, and side-effect-free semantics (reads never enqueue, allocate or advance boundaries).
- [x] Implement citation snapshot storage with bounded traversal, provenance/freshness/coverage fields and the search-fact/checkpoint handoff to Library.
- [x] Implement claim/fence repository operations (acquire/renew/reclaim) with owner time, lease revisions and expected business revision checks.

Trace: W4–W11; BR4.3–4.4/BR5.1/BR6.1–6.3/BR7.2–7.5.

### Step 6 — Write and run repository tests

- [x] Create `tests/u3_paper_corpus_capabilities/repository/` checks for foreign/absent isolation, bounded pagination, lost acknowledgement, changed-intent conflict, stale revision, read-only recovery and claim/fence ordering.
- [x] Check no writes from all list/inspect/result reads; snapshot expiry and stable windows; two-owner and cross-owner denial.
- [x] Run against actual owner roles and the transaction facility; fail a missing required store instead of substituting in-memory success.

Trace: V3/V4/V6 and NFR2.3/NFR3.2/NFR4.1/NFR8.2.

### Step 7 — Implement owner business behavior

- [x] Complete ingestion/refresh/rebuild/retry with staged effects, per-effect dispositions, watermark discipline and repeatable non-corrupting recovery (W1–W2).
- [x] Implement source-change/withdrawal propagation: eligibility revisions enforced immediately, ordered change facts and the saved-reference disposition handoff; restore replays withdrawal boundaries (W3).
- [x] Complete search: validated vocabulary, snapshot-bound stable windows, lexical/semantic modes with disclosed degradation, truthful error/empty states and completed-search facts with the clear-fence boundary (W4).
- [x] Complete citation exploration: bounded distinct nodes/depth/requests, labelled freshness/coverage, no fabricated edges, saves through Library (W5).
- [x] Complete reading: exact-version resolution, sections/figures/anchors/source links, bounded malformed-content states, no endless loading (W6).
- [x] Complete assistance acceptance: reconciled options, immutable binding with reservation and dispatch responsibility, idempotency semantics (W7).
- [x] Complete assistance execution/progress/results/glossary: claim/fence, ordered monotonic progress through the real transport, prepared-result binding with pending/ready/expired/failed/unauthorized, idempotent settlement obligation, glossary normalization/CAS and use (W8–W11). Close Q-01–Q-04 with real execution evidence.
- [x] Integrate safe observations and truthful readiness (observed/estimated/unknown/stale); no placeholder claims success.

Trace: W1–W11; all BR1.1–BR9.2; full-scope FR1–FR4, FR9, FR18 and their child rows.

### Step 8 — Write and run component/business tests

- [x] Add eight owner/boundary component files with at least five to eight meaningful cases each: corpus maintenance/publication, content reading/dispositions, discovery/degradation, citations, assistance jobs, progress/transport, glossary, isolation/redaction.
- [x] Include success plus at least two error/edge cases per component; cover conflicting tabs/windows, expiry/replay, missing participants/policy, duplicate/unknown external outcome and repeated recovery.
- [x] Keep provider/network fakes at adapter boundaries with canonical types; cover bounded cryptographic/parsing libraries and side-effect invariants; tests cannot always pass or mirror implementation mechanically.

Trace: V1–V7; all functional lead rows and relevant support-boundary behavior.

### Step 9 — Implement API and mounted integration

- [x] Extend typed C04–C06 routes within the existing host; derive authority/eligibility from trusted context; validate limits before expensive work; carry exact control revisions.
- [x] Implement session bootstrap/CSRF/origin and cache protections for the new surfaces; safe error envelopes; no secrets or private identifiers in browser JSON or URLs.
- [x] Mount corpus-run, search/refinement, reading, citation, assistance and glossary routes with current owner/maintenance checks; unknown writes and dependency outages never become empty/success responses.
- [x] Bind the real installed worker/execution participants and expose capability-specific readiness with synthetic/actual evidence distinguished.

Trace: C04–C06/C13/C14; W1–W11; NFR4.*, NFR9.*, NFR10.*.

### Step 10 — Write and run API/integration tests

- [x] Create `tests/u3_paper_corpus_capabilities/integration/` tests through the actual mounted host and owner stores; combine with Steps 4/6 for at least 32 real-store/API cases.
- [x] Exercise lost responses before/after commit, competing publication, withdrawal racing reads, expired snapshots, forged owner/scope, replay, redaction and dependent-owner outage; assertions against persisted effects/receipts.
- [x] Run cumulative U1/U2 host compatibility at the dedicated cumulative layer; do not relabel isolated tests as cumulative proof.

Trace: V1–V7/V9; closes canonical publication/revision/job-findings only with reproducible passing evidence.

### Step 11 — Implement the integrated Korean frontend

- [x] Extend the shell/Transport with authority-generation scoping, safe route restoration and owner-isolated cache/late-response handling for the new surfaces; clear private state on switch/logout/expiry.
- [x] Implement query/filters/results, reading (sections/figures/anchors/states), citation explorer, assistance panel with ordered progress/reconnect/polling and prepared-result states, and the glossary editor.
- [x] Preserve query/reader context and appearance modes; surface degradation/partial/expired states truthfully; no infinite loading; deliberate confirmations for effectful actions.
- [x] Add labels/focus/live announcements, reduced motion/reflow and data-testid hooks; never persist credentials/private forms or promise unsupported recovery.

Trace: frontend-components.md entire hierarchy; BR9.1–9.2; FR1–FR4/FR9 UI and NFR2/NFR4/NFR6.

### Step 12 — Write and run frontend/browser verification

- [x] Add focused frontend unit suites for the U3 surfaces: discovery/results states, reading states, assistance progress/result states, glossary conflicts and isolation.
- [x] Add at least 12 real browser journeys covering search/refine/reopen, source-only/withdrawn content, citation exploration + save, assistance accept→progress→result (reconnect/sleep/restart), expired result, glossary conflict, degradation notices and account switch.
- [x] Include desktop/tablet/phone and Light/Dark/System, Korean long text, zoom/reflow, visible focus/keyboard order; record actual keyboard/screen-reader checks and limitations; automated results alone do not claim WCAG conformance.

Trace: V8 plus user-visible V1–V6 outcomes; Q-01–Q-04 through the real transport.

### Step 13 — Complete environment, packaging, bounded operations and CI

- [x] Finish `scripts/verify_docsuri_u3.py` and owned profile phases (setup/database/repository/component/integration/operations/browser/coverage/teardown); retain current U1/U2 invocations.
- [ ] Enforce finite limits and measure ingestion/projection/worker/model footprint before load; respect reserves; timeout cannot spawn replacement work while old capacity remains charged.
- [x] Add the U3 operational/fault scenario families with resumable evidence: partial writes/crash boundaries, index/model incompatibility, provider limits, saturation, key/permission failure, isolated restore replaying withdrawal boundaries, seeded defect repair.
- [x] Build immutable manifests/artifacts, compatible ordered migrations and stop-migrate-start verification/rollback instructions. Do not deploy publicly or run real-data migrations.
- [x] Add scoped U3 actual-execution CI with frozen inputs, content hashes, read-only permissions and no private-host secrets on untrusted PRs; record dependency/advisory/license checks.
- [x] Prepare (and present at its recorded decision point before checkpoint verification) the runnable cumulative completion check covering U1/U2/U3 composition, without claiming fixture-only provider/public parity.

Trace: PIPE2-aligned pipeline design; V5–V9; NFR7.*, NFR8.*, NFR9.*, NFR10.3. Numeric service targets remain baseline-dependent.

### Step 14 — Complete evidence, review and Git handoff

- [x] Write code-summary.md, exact requirement-to-source/test traceability and source-manifest.json containing every created/modified/deleted application/config/test/generated path. Capture checks, failures and real-policy/provider gates honestly.
- [x] Cover all assigned functional rows with lead/support attribution and all ten inception/derived NFR constraints; no support contribution is reported as another unit's completed feature.
- [x] Verify meaningful new-code coverage of at least 80% as retained additive guidance; never lower a configured target to pass.
- [ ] Obtain the required independent review of completed implementation and evidence; repair actionable findings through the recorded process.
- [ ] Merge fulfilled work through a PR into develop under CONVENTIONS.md and its interim CI policy. No main promotion or public deployment. Do not mark U3/full release ready while required closure evidence is absent.

## Requirement-to-step map

| Requirement contribution | Implementation / verification steps |
|---|---|
| FR1, FR1.1–FR1.3: find and refine | 1,3–10,11–12; snapshot windows, degradation, pagination |
| FR2, FR2.1–FR2.2 (public reading) | 1,3–10,11–12; exact-version reading, dispositions, assets |
| FR3, FR3.1–FR3.4: assistance | 1–10,11–13; dispatch/progress/result integrity, Q-01–Q-04 |
| FR4, FR4.1–FR4.2: glossary | 1,3–10,11–12; normalization/CAS/output binding |
| FR9, FR9.1–FR9.2: citations | 1,3–10,11–12; bounded traversal, provider freshness, saves |
| FR18, FR18.1–FR18.3: corpus maintenance | 1,3–10,13; identity/dedup, withdrawal, rebuild/recovery |
| Supporting FR5.3, FR6.3, FR8.x, FR10.x, FR12.2, FR13–FR15, FR17.2, FR19 | 1,3–10,13–14; change facts/dispositions, current-authority rechecks, eligible-source contracts, accounting reconciliation, safe observations |
| NFR1–NFR10 / derived NFRx.y | All relevant steps; final traceability gives concrete source/test evidence with local vs external proof separated |

## Completion evidence and stop conditions

A synthetic-profile pass may establish isolated implementation behavior only. Source permissions, model readiness, citation-provider terms, finite accounting/capacity policy and public fit must remain explicit and may require the maintainer's decision before affected operation. Preserve unresolved responsibilities on exhaustion; no automatic "complete" based on a healthy shell, collected tests or an unavailable capability.

New test failure, unsafe resource fit, contradictory canonical behavior or unreviewed source-boundary expansion is investigated with evidence. Implementation waits for the recorded Plan Approval. The cumulative verification invocation remains a separate decision point before checkpoint verification.

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
