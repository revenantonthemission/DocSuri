# U7 code generation plan

## Summary

- Builds: the local controlled operator (`PlatformControl`) — guard-function store, authority provisioning, on-demand evidence, bounded native executor, durable receipts with reconciliation, and the local JSON CLI.
- Touches: a new U7 Python package under `ops/`, the shared contract bindings, a dedicated U7 test suite and a scoped U7 CI workflow.
- Tests: component + database/role + repository + mounted CLI boundary tests (no UI layer — U7 is a CLI).

## Scope and execution boundary

This plan implements U7's assigned rows — FR20, FR20.1 and FR20.2 — through the
`PlatformControl` owner, constrained by the
[functional specification](../functional-design/functional-spec.md),
[rules](../functional-design/rules.md),
[entities](../functional-design/entities.md), the
[NFR design](../nfr-design/logical-components.md) and the
[infrastructure specification](../infrastructure-design/infrastructure-specification.md).
Contract C10
([contract-summary.md](../../../inception/contract-design/contract-summary.md))
is the wire contract; the internal→wire mapping is recorded in the NFR tech-stack
decisions.

U7 is an independent local executable under the $0/local budget: a single
operator process, one bounded child process per native effect, and the shared
local PostgreSQL with a dedicated `PlatformControl` schema and its own roles. No
cloud resources, no AWS runtime, no paid telemetry. **This plan does not
authorize running real destructive or release operations**; every effect test uses
synthetic targets.

## Source responsibility and integration

| Owner / concern | Source boundary | U7 responsibility |
|---|---|---|
| Shared assembly | existing `ops/src/docsuri_ops/`, `backend/transactions.py` patterns; new `ops/src/docsuri_ops/platform_control/` | The operator CLI, provisioning, evidence, executor, reconciler, observation bridge |
| Guarded store | new `PlatformControl` schema SQL + guard functions | Owner-isolated persistence with `SECURITY DEFINER` guards and bounded roles |
| Native adapter | the operator executable's child process | Real local filesystem/credential semantics through a bounded, allowlist-only adapter |
| Shared contracts | `shared/python/`, `shared/schema-catalog.json`, generated bindings | Use C10 request/response types through existing generators; no parallel wire contract |
| Verification | new `tests/u7_controlled_platform_protocols/` + `scripts/verify_docsuri_u7.py` | Component/database/repository/integration/operations tests and evidence |

## Ordered implementation steps

- [x] Step 1 — Reconcile the retained protocol inventory and consumer matrix from the reference; record every protocol with an explicit disposition (retained-local / compatibility-dependent / not-implemented-under-$0) as a machine-readable inventory plus a short evidence note; confirm the U7 working branch (`feature/docsuri-v2-u7-controlled-platform-protocols`). Trace: BR5.1/5.2/5.3.
- [x] Step 2 — Establish the isolated local U7 profile, pinned dependency/build manifests, test-runner configuration and the exact U7 command wrappers (`scripts/verify_docsuri_u7.py` phases; `backend/pytest.u7-platform-control.ini`). Verify runner collection before the first test; an empty collection is a configuration error, never a pass. Trace: NFR7.1/7.2.
- [x] Step 3 — Implement the data model / database behavior: the `PlatformControl` schema (authority, evidence, operation + durable target lease, append-only receipt), owner-scoped `SECURITY DEFINER` guard functions and bounded non-login roles, and U7-owned idempotent migrations. Trace: BR1.*, BR2.*, BR3.3/3.4, BR4.1; NFR3.5, NFR4.1/4.6/4.8.
- [x] Step 4 — After Step 3, write and run database/role tests on a real local PostgreSQL: direct foreign DML denied; guard-function abuse denied; legitimate guarded target write works under real runtime grants; one-in-flight target lease refuses a second same-target operation; binding-before-effect survives restart; revocation ordering holds; failure rolls the protected transaction back. Include positive controls. Trace: same obligations as Step 3.
- [x] Step 5 — Implement repository/data-access adapters: bounded transactional unit of work; authority check → lease acquire → binding + receipt stub → effect → settle + release; evidence persistence; reconciliation queries. Trace: BR3.5/3.6, BR4.1–4.7; NFR3.1–3.7.
- [x] Step 6 — After Step 5, write and run repository tests: failed/unknown commit, duplicate/changed-input replay, missing/denied/corrupt target, crash before/after binding and settlement, stale in-flight promotion to `unknown`, restart durability. Trace: Step 5 obligations.
- [x] Step 7 — Implement business components: `authority-provisioner` (local OS-user-verified subcommand), `evidence-producer` (on-demand bound generation with finite validity), `bounded-executor` + `native-adapter` (allowlist-only, deadline, resource cap, typed settlement channel), `receipt-reconciler` (on-demand + `reconcile` subcommand), `observations-bridge` (C10 pull; C11 provider coordination item recorded). Trace: BR1.*, BR3.1/3.2/3.7, BR5.*, BR6.*; NFR1–NFR9 applicable rows.
- [x] Step 8 — After each Step 7 component, write and run its focused tests before the next: four-state evidence classification; wrong actor/target rejected before effect; changed-input conflict; interrupted/duplicate reconciliation without re-execution; permission/disk/connectivity → `failed`/`unknown` (never `completed`); destructive-release requires its own grant. Keep wrong/failed outputs as evidence; reserve fakes for injected faults. Trace: Step 7 obligations.
- [x] Step 9 — Implement the CLI/endpoint adapters: the local stdin/stdout JSON envelope (`inspectEvidence`/`executeControlled`/`readReceipt`), server-derived actor, exact error vocabulary (`INVALID_INPUT`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `POLICY_UNRESOLVED`, `DEPENDENCY_UNAVAILABLE`, `UNKNOWN_OUTCOME`), and the internal→wire mapping to C10's `OperatorEvidence`/`OperatorReceipt`. Keep reads separate from execution. Trace: BR3.1/3.2, BR6.1/6.2, BR5.4; NFR4.10, NFR10.1–10.4.
- [x] Step 10 — After Step 9, write and run mounted CLI boundary tests: wire shape conformance; stale/mismatched/missing evidence; session/actor substitution; bounded/authenticated restricted reads; byte-level JSON framing; read-no-effect assertions. Trace: Step 9 obligations.
- [x] Step 11 — Implement environment/build/ops configuration: the local supervisor (start/stop/restart/backup/restore/rollback), the scoped `u7-controlled-platform-protocols` CI workflow (DB/executor phases recorded as unexecuted required evidence), and the U7-owned schema migration runner. Trace: NFR7, NFR8.5, infrastructure spec.
- [x] Step 12 — After Step 11, write and run operations/recovery tests: process restart preserves receipts; backup/restore round-trip; rollback keeps receipts; unresolved-unknown list stays visible; local-only assertion (no paid dependency). Trace: Steps 3–7; NFR3, NFR8.
- [x] Step 13 — Produce documentation and records: API/installation/recovery documentation, the actual unit-test commands, `code-summary.md`, `source-manifest.json` (strict schema, every created/modified/deleted path), and `traceability.json` (every assigned FR/NFR/BR row to an existing implementation/test file). Measure ≥80% line coverage per changed module without lowering thresholds. Trace: NFR7, NFR10, LC.
- [x] Step 14 — Hand the finished work to the conductor: no review dispatch, no verification-command selection and no completion checkpoint here; the conductor owns the architecture review, the Construction Verification Command and the completion gate.

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

The plan_profile's "Frontend behavior" layer is **inapplicable** to U7 (a CLI —
no UI); the contract permits omitting a genuinely inapplicable layer. All other
layers are implemented and tested.

## Constraints and completion

The exact Construction Verification Command remains **UNSET**; the commands in
[unit-test-instructions.md](unit-test-instructions.md) are development checks
and none records a completion. No schedule or success promise is inferred.
Measurable targets from the NFR requirements are inputs, not suggestions and must
never be weakened to make a step pass: bounded execution, one-in-flight lease,
truthful outcomes, fail-closed admission, and ≥80% line coverage per changed
module. A resource/quality conflict stops the affected work with evidence rather
than relaxing a target.
