# U1 code generation plan

## Summary

- Builds: a real local find → understand → save → revisit journey with guarded persistence and recoverable model work.
- Touches: existing backend, frontend, shared contracts, ingestion adapters, local operations and a dedicated U1 test suite.
- Tests: at least 45 focused component tests, 16 real-boundary cases and six mounted journey scenarios, plus coverage and accessibility checks.

## Scope and execution boundary

This plan implements U1's 29 assigned FR rows (eight parent rollups and 21
subrequirements), 39 business rules and 37 derived NFRs through the existing
component owners. The authoritative [functional specification](../functional-design/functional-spec.md),
[rules](../functional-design/rules.md), [entities](../functional-design/entities.md),
[NFR design](../nfr-design/logical-components.md) and [infrastructure specification](../infrastructure-design/infrastructure-specification.md)
constrain the implementation. User Stories was skipped; trace directly to FR,
BR, NFR and local acceptance IDs rather than inventing approved stories.

U1 is an isolated synthetic/local research assembly. All retained capabilities
remain required across the eight-unit release, including the later U2/U3/U8
completion of U1's partial contributions. U4 owns durable research drafts.
No existing users/data are reset, migrated or treated as disposable; no public
host, live deployment, paid provider, new billing or main promotion is included.

Python/FastAPI and a React static build remain candidates until the first
mounted build proves their required behavior. PostgreSQL is selected as the
common transaction facility, but real roles and persistent-volume conformance
are required. Cached local models have partial useful-output evidence and
known initial grounding failures. This plan must resolve the affected evidence
before calling the corresponding path ready; it cannot replace real normal
outputs with canned answers. The existing completed infrastructure branch still
needs its authorized PR/merge into develop before implementation starts.

## Source responsibility and integration

| Owner / concern | Existing or planned source boundary | U1 responsibility |
|---|---|---|
| Shared assembly | Existing backend/app.py, backend/wiring.py, backend/config.py, backend/db.py; new focused host/transaction helpers only where needed | Explicit local U1 profile, dependency/lifecycle manifest, safe startup, same-origin web serving; no implicit production database migrations |
| AccountAccess | Existing backend/modules/accounts/ | Synthetic public entry, verification sink, session/current authority, owner isolation and required revocation participants |
| CorpusContent | Existing ingestion/src/docsuri_ingestion/docmodel/ and backend/modules/user_docmodel/ plus a clearly named corpus facade where ownership is currently scattered | Eligible versioned fixtures, safe text/math/figure anchors, authoritative content/projection publication and withdrawal |
| Discovery | Existing backend/modules/discovery/src/discovery/ | Real bounded lexical/semantic candidate, filters/order/cursor, submitted-query identity and recoverable history fact |
| Library / Personalization | Existing backend/modules/library/ and backend/modules/personalization/; verify onboarding/default consumers during the impact inventory | Acknowledged saves/history/defaults under one owner each; no copied account, paper or job authority |
| UsageEntitlements | Existing backend/modules/plans/ | Finite reservation/acceptance/settlement protocol, current own usage and synthetic policy |
| PaperAssistance | Existing backend/modules/summarization/src/summarization/ and migrations | Canonical request/claim/result contracts, durable queue, real local model adapter, prepared-result/history reads |
| ServiceOperations | Existing ops/src/docsuri_ops/ and ops/local-stack/; planned scripts/verify_docsuri_u1.py | Finite supervision, readiness/incident evidence, backup/restore/repair and scoped verification orchestration |
| WebWorkspace | Existing frontend/components/, frontend/lib/, frontend/styles/ and route entrypoints; candidate frontend/index.html, frontend/src/main.tsx and frontend/vite.config.ts | Rework current components in place, implement approved Korean workspace; validate static-build route/session/stream parity before replacing a required runtime |
| Shared contracts | Existing shared/dtos/, shared/events/, shared/vector-spec/, shared/schema-catalog.json, shared/python/ and frontend/types/wire/; canonical contract document | Coordinated source schemas and generated producer/consumer bindings through existing generators, no parallel handwritten wire contract |
| Verification | New tests/u1_integrated_paper_journey/ and frontend/test/u1-integrated-paper-journey/ | Exact U1 fixtures, component/boundary/browser tests, negative controls and evidence |

Paths whose ownership is still scattered are investigated in Step 1 before edits;
the plan does not claim a complete impact inventory from one graph lookup.
Refactor current owners in place. A new helper is justified by a single clear
responsibility, not a second implementation suffixed v2/modified. Preserve
unmigrated later-unit capabilities and external compatibility evidence; remove
superseded code only after call sites and retained behavior have a verified
replacement. Source-manifest.json will list every created, modified or deleted
application/config/test path, including generated files.

Parent graph evidence: Tier 2, project Users-revenantonthemission-Projects-DocSuri,
generation 2026-10-11T09:53:33Z. Exact create_app source in backend/app.py:85–124
calls startup migrations, sets observations/rate limiting and mounts modules;
outbound trace depth 1 returned ten nodes without truncation. Backend wiring
mount functions and frontend RootLayout/PaperDetailIsland/JobStatus symbols
were found; five candidate files plus configuration/package and functional
documents returned metadata_match/no_recorded_issue. This is bounded planning
evidence, not a complete consumer graph. Step 1 checks exact changed paths and
fallback ranges before relying on them.

A subsequent bounded file-tree lookup and source read verified the existing
personalization directory and shared schema/generator layout at generation
2026-10-11T09:58:42Z. Backend/frontend manifests and the TypeScript generator
returned metadata_match/no_recorded_issue. Shared-scope exclusions were caches,
virtual environments and operating-system metadata. No claim about those
excluded trees or exhaustive consumer coverage is made.

## Ordered implementation steps

- [x] Step 1 — Integrate the completed Infrastructure Design branch through a PR into develop using CONVENTIONS.md and exact base/head legacy CI comparison, then create feature/docsuri-v2-u1-paper-journey from develop. Before the first application-code change, record that exact baseline commit and the commands, environment, collected/passing/failing/unexecuted results for affected existing regression suites; compare the same scopes after implementation and investigate every new regression. Inventory every affected owner, wire schema, route, caller, consumer and test with current graph coverage plus direct fallback; record compatibility and retained-parity boundaries. Resolve the new infrastructure Major finding before repository code: use owner-scoped PostgreSQL transaction principals and narrowly scoped owner-controlled guard functions on the same connection, as specified below. Coordinate canonical C00/C02/C03/C06/C13/C14 amendments and generated consumer policy through the supported artifact-change path before affected implementation. Do not edit frozen artifacts or disable guards to force the amendment. Trace: BR7.1–BR7.5, BR4.2, BR5.5–BR5.9; NFR7.3, NFR10.1–NFR10.4; LC06/12/14.
- [ ] Step 2 — Establish the explicit isolated local profile, pinned dependency/build manifests, test runner configuration and the exact U1 command wrappers. Verify runner collection before the first executable behavior test; do not call an empty collection a passing suite. Prove a minimal mounted framework/static-build route and session/stream slice, then lock the actual versions/licenses or resolve an evidenced incompatibility before depending on that choice. Add finite install/build allocation from current measured sizes; the earlier 512 MiB probe cap is not presumed sufficient for a clean build. Trace: BR7.1/7.4/7.5; NFR7.3, NFR8.1/8.3/8.5, NFR10.3; LC12/14.
- [ ] Step 3 — Implement data-model/database behavior: owner schemas, typed revisions/unique keys, authority barriers, operation receipts, immutable acceptance time/input/result bindings, claims/leases/fences, PA empty-glossary token/snapshot, history-clear cutoff and separate reservation/settlement obligations. Implement owner-only guard functions and migration/runtime privilege separation; persistence goes only to the named disposable environment. Trace: BR1.2–BR1.4, BR2.1/2.4, BR3.5, BR4.1–BR4.5, BR5.2–BR5.8; NFR3.1–NFR3.4, NFR4.2/4.4/4.5, NFR10.1/10.2; LC05/07–10.
- [ ] Step 4 — After Step 3, write and run database/role tests using PostgreSQL 16.15 on the intended persistent volume: CAS/absent create, direct foreign mutation denial, allowed target commit plus current guard locks, both revocation/effect orders, replay after later mutation, stale fence denial, original timestamp and empty token, history clear versus delayed fact. Include positive controls and two real concurrent connections. Trace: same obligations as Step 3; infrastructure review R-01 closure evidence.
- [ ] Step 5 — Implement repository/data-access adapters: bounded transactional unit of work, current authorization then exact receipt replay then fresh CAS, owner-specific pools, immutable file staging/publication, projection read/write boundaries, durable relay and bounded reconciliation queries. Keep expensive model/network work outside guard transactions. Trace: BR1.2/1.4, BR2.2–BR2.4, BR4.1–BR4.5, BR5.2–BR5.9; NFR3.1–NFR3.5, NFR4.2–NFR4.5, NFR8.2–NFR8.4; LC03/05/07/09/10.
- [ ] Step 6 — After Step 5, write and run repository tests for failed/unknown commit, duplicate/different intent, missing/denied/corrupt/partial file, crash before/after publication and settlement, current permission on read, worker replacement and durable recovery after container replacement. A tmpfs or SQLite pass cannot substitute for the selected store. Trace: Step 5 obligations; LC05/07/09/10/14.
- [ ] Step 7 — Implement business components: verified synthetic entry and safe defaults, purpose-bound corpus loader, real bounded lexical/semantic research-query search, saved paper/query/history/default behavior, finite usage reservation, durable assistance admission/claim/payload/progress/completion and retained-result discovery. Implement real local Qwen/BGE adapters with cloud-disabled verified routing, context/output/deadline limits, faithful section/math extraction, source-referenced output validation and explicit insufficient-result states. Resolve P1/P2 grounding failures and supported translation before normal readiness. Trace: BR1.1–BR5.10, BR7.4; FR1–FR3/FR5/FR6/FR10/FR17 U1 contributions; NFR1.2, NFR4/NFR5 applicable derived rows; LC01–10.
- [ ] Step 8 — After each Step 7 component is implemented, write and run its focused tests before moving to the next component. Cover happy behavior plus denial and recovery; reserve fakes for deliberate faults. Run separate real-model source-rubric and embedding/retrieval checks; retain wrong, incomplete, truncated and failed outputs as evidence. Test literal mathematical meaning, current source/version, permission and language pair. Trace: all Step 7 obligations; LC01–10/14.
- [ ] Step 9 — Implement API/endpoint adapters and assembly for canonical browser and worker contracts: server-derived principal, exact preconditions/errors, owner-bound history/results/assets, Host/origin/CSRF controls, finite validation, correctly framed ordered progress with replay/snapshot/polling, lifecycle/readiness registration and safe diagnostics. Keep compatibility decisions explicit and new execution separate from reads. Trace: BR1.1–BR1.5, BR4.2/4.3, BR5.3/5.5–BR5.10, BR6.4, BR7.1/7.2; NFR4.1–NFR4.6, NFR10.1/10.3; LC01/05–10/12.
- [ ] Step 10 — After Step 9, write and run mounted API/worker boundary tests: malformed/missing/stale revision, current-permission receipt replay, changed-intent conflict, session/claim substitution, owner-B direct/list/event/result/asset denial, lost reply, lease renewal/replacement, byte-level SSE framing/order/reconnect and read-no-new-job/no-debit assertions. Cover the four discovered legacy paper-job defects with regressions through the actual U1 bindings. Trace: Step 9 obligations; LC05–10/12.
- [ ] Step 11 — Implement the approved Korean web experience in the current component lineage: integrated search/reader/library flow, visible query/filter controls through failure states, exact paper/version and source anchors, explicit work submission, truthful job/save/recovery states, durable acknowledged saved work after reauthentication, account-switch isolation and read-only prepared result opening. Preserve inherited colors/HIG adaptations, light/dark/system, responsive reflow and accessible focus/status behavior; add stable data-testid attributes. Trace: BR3.1–BR3.4, BR4.1–BR4.6, BR5.7/5.9/5.10, BR6.1–BR6.4; NFR2.1/2.2, NFR6.1–NFR6.3; LC02/03/06–09/11.
- [ ] Step 12 — After Step 11, write and run frontend component tests and mounted browser scenarios: slow stale response, unknown save and conflict, stream break/sleep/restart, fresh authenticated return without transient IDs, read-only result navigation, A→B switch, preference-storage failure, keyboard/focus/live announcements, 320px reflow, 200% text and appearance modes. Automatic accessibility checks require rendered/manual confirmation. Trace: Step 11 obligations; LC06/07/09/11/14.
- [ ] Step 13 — Implement environment/build/delivery configuration and operations: versioned local supervisor/Compose, bounded owner queue and model permit, actual protected native/container transport, finite observation/required incident storage, policy/readiness expiry, coherent backup/restore and stop/replace/rollback procedures. Add targeted U1 CI checks while preserving the interim comparison for unrelated legacy failures; do not rebuild the entire later U8 pipeline or deploy on develop merge. Trace: BR5.4, BR7.1–BR7.5; all NFR3/NFR7/NFR8/NFR9 derived rows; LC10/12–14.
- [ ] Step 14 — After Step 13, write and run real mixed-load/fault/restore/repair tests under measured finite limits. Prove preserved acknowledgements, one result/accounting effect and current restrictions across process/container/VM restart, loss of optional telemetry, full isolated allocations, source withdrawal and controlled defect repair. Record all planned/attempted/unexecuted cases, times, memory/disk and quality outcomes; no fabricated baseline target or deletion of unrelated data. Trace: BR1.4, BR5.2/5.4/5.8, BR7.2–BR7.5; NFR1–NFR10 applicable derived rows; LC09/10/12–14.
- [ ] Step 15 — Produce API/installation/recovery documentation, actual unit test commands, code-summary.md, source-manifest.json and workspace-file traceability for every assigned FR/acceptance/BR/detailed NFR. Reconcile remaining later-unit parity and evidence obligations. Obtain the independent finished-work architecture review, fix permitted findings, and supply a real cumulative completion invocation for separate human approval. Run the approved completion checkpoint only after that approval; merge the fulfilled implementation branch through PR into develop under CONVENTIONS.md. Trace: BR7.5; NFR7.1–NFR7.3, NFR10.1–NFR10.4; LC14.

## Database privilege closure before repository implementation

The runtime API/worker does not use a superuser, migration role or general
cross-owner table-writing identity. Each owner repository opens a transaction
with its own bounded role/pool (accounts, corpus, library, personalization,
assistance, usage, operations; discovery uses projection reads plus its own
execution facts). Direct DML is limited to that owner's schema.

AccountAccess/CorpusContent provide narrowly scoped SECURITY DEFINER guard
functions owned by their non-login schema roles. Functions validate fixed typed
purpose/session/source inputs against current authoritative rows and lock the
appropriate barriers on the **caller's existing transaction connection**. Only
explicit consumer roles receive EXECUTE; PUBLIC execution/schema creation are
revoked. Use schema-qualified objects, fixed safe search_path, no dynamic SQL,
no arbitrary predicate/table/role parameter, no ownership transfer and no
SET ROLE escape for consumers. Functions do not expose account credentials or
allow consumer mutation of authority fields. Lock order stays account/session/
consent → source/version → target. Missing or invalid authority rejects.

The target owner then writes only its own row/receipt and commits the same
transaction. Account/source revocation locks and changes the same owner barriers.
A worker claim grants execution, not general account or data access. The API
process's possession of multiple owner credentials remains an application trust
boundary; per-owner database grants protect repository misuse, not a claim that
a fully compromised API process cannot use another loaded credential. Narrower
process isolation is evaluated separately if required.

Step 4 must prove direct foreign UPDATE/DELETE and function abuse are denied,
legitimate guarded target commits work under real runtime grants, revocation
ordering holds, and failure rolls the whole protected transaction back. Do not
record infrastructure R-01 as closed until those executable checks pass.

## Required test allocation and acceptance mapping

| Family | Planned test evidence | Design coverage |
|---|---|---|
| AccountAccess | 5–8 component tests plus real session/verification/authority boundary cases | BR1.1–BR1.5; LC01/09 |
| CorpusContent | 5–8 component tests plus exact source/asset/withdrawal cases | BR2.1–BR2.4; LC03/09 |
| Discovery | 5–8 component tests plus real projection/embedding/filter/cursor cases | BR3.1–BR3.5; LC02/08 |
| Library | 5–8 component tests plus concurrent/unknown save and history-clear cases | BR4.1–BR4.5; LC07/08 |
| Personalization | 5–8 component tests for defaults/manual entry/current consent | BR4.6; LC08/09 |
| UsageEntitlements | 5–8 component tests plus reservation/unknown/settlement cases | BR5.2/5.4/5.8; LC10 |
| PaperAssistance | 5–8 component tests plus actual claim/result/model/fault cases | BR5.1–BR5.10; LC04–06 |
| ServiceOperations/host | 5–8 component tests plus registration/observation/restore/repair cases | BR7.1–BR7.5; LC12–14 |
| WebWorkspace | 5–8 component tests plus six mounted scenarios and accessibility | BR6.1–BR6.4; LC11/14 |

At least sixteen real-boundary cases span these families in addition to the
45-component-test floor. Six mounted scenarios cover P1, P2, supported
translation, fresh saved return, interrupted accepted-work recovery and
cross-account denial with positive controls. Counts are planning floors, not
substitutes for requirement coverage; add meaningful cases when needed.

Every new/changed U1 implementation module must reach at least 80% measured
line coverage, without excluding difficult behavior or lowering configuration
thresholds. Historical passing counts are not current evidence. Appropriate
existing tests must pass or show exact unchanged baseline failures under the
user's CONVENTIONS.md interim policy; investigate every new regression.

The generated Testing Contract's scope_floor array adds no new coverage floor,
but its applicable organization note explicitly retains 80% line coverage and
CI execution for classic scope. Apply that note additively as stated above;
the shorter array does not cancel it. Preserve the generated contract unchanged.

## Constraints and completion

No schedule or success promise is inferred from this plan's size. The first
bounded experiments may revise technical details within the accepted interfaces;
a material plan change follows the existing approval policy. A resource/quality
conflict stops the affected work with evidence, without spending or feature cuts.

The exact Construction Verification Command remains UNSET. Commands in
[unit-test-instructions.md](unit-test-instructions.md) are planned scoped
development checks, not an approved completion invocation. Source/role checks,
real local model quality, persistent recovery and complete journey evidence
remain required before U1 completion. Ordinary continuation stays automatic;
enabled plan/summary, verification-command decisions and failures still stop.

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
