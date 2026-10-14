# U2 account and personal controls — code generation plan

## Summary

- Builds: Complete account and personal controls in the shared local application, with durable recovery, owner isolation and truthful readiness.
- Touches: Existing account/library/personalization/usage modules, shared contracts, local host/profile, React workspace, U2 test harness and scoped CI.
- Tests: At least 64 component cases, 32 real-store/API cases, 12 browser journeys and 9 operational/fault scenarios, plus cumulative regressions.

## Scope and inputs

This plan implements U2's contribution to the approved rebuild, using [functional workflows W1–W14](../functional-design/functional-spec.md), [entities](../functional-design/entities.md), [rules BR1.1–BR7.3](../functional-design/rules.md), [frontend specification](../functional-design/frontend-components.md), [NFR requirements](../nfr-requirements/security-requirements.md), [technology decisions](../nfr-requirements/tech-stack-decisions.md), [security design](../nfr-design/security-design.md), [logical components](../nfr-design/logical-components.md) and the merged [pipeline/integration design](../infrastructure-design/cicd-pipeline.md). The [unit definition](../../../inception/units-generation/unit-of-work.md), [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md), [requirements](../../../inception/requirements-analysis/requirements.md), [domain ownership](../../../inception/domain-design/components.md) and [canonical contracts](../../../inception/contract-design/contract-summary.md) remain authoritative.

User Stories was skipped; map to stable requirement IDs and the actual U2 contribution instead of inventing stories. All 62 assigned functional rows and ten inception NFRs remain in scope for U2's lead or support contribution; all 39 derived NFRs constrain implementation. Full feature parity owned by other units is not transferred to U2. Keep the Korean responsive interface, inherited blue/neutral colors, Apple HIG web adaptations, Light/Dark/System and accessibility target.

The $0 limit prohibits paid fallback. Implement generic policy-bound behavior with the explicitly labelled finite synthetic profile for local proof. Real provider activation, current-user migration, destructive real-data processing, retention/reactivation, MFA recovery, production quota policy and public capacity stay gated by G1–G8. Do not reinterpret fixture values as human-approved operating policy or mark required external evidence passed. Preserve all capabilities visibly even when unavailable. No new public host, billing, service split or U4 research-draft implementation is included.

## Current implementation evidence and intended source boundary

Base: develop merge `295a3d19`; application unchanged by infrastructure PR #49. Working branch `feature/docsuri-v2-u2-account-personal-controls`.

Tier 2 graph/source inspection found the existing `backend/local_host.py::assemble_journey` mounting account, library, settings, usage and paper-journey routers over one OwnerTransactions facility. `account_router` currently supplies U1 registration/verification/login/logout; this is an extension point, not evidence of all U2 flows. `GuardedSettingsService` supplies defaults/onboarding and `GuardedUsageRepository` supplies the bounded U1 ledger/rejection-proof path. Reuse and strengthen these owners; do not create a second source of authority.

Material regression cases from exact source: settings-update currently rebuilds the stored defaults object without onboarding/interest fields, and onboarding skip computes an empty interest list. U2 must preserve acknowledged onboarding/interests through unrelated defaults/appearance changes and through skip, as BR5.1/BR5.2 require. The existing four-operation U1 quota and profile bindings remain U1-specific; a new U2 policy cannot silently rewrite them.

| Boundary | Planned changes and ownership |
|---|---|
| Contracts | Owning C02/C03/C13 sections and coordinated schemas in `shared/dtos/workspace.schema.json`, `shared/events/execution.schema.json`; generated Python/TypeScript outputs through existing generators only. Include actual affected consumer inventory and version evidence. |
| AccountAccess | Extend `backend/modules/accounts/local_http.py`, `services/guarded_entry.py` and owner-local repository/services; add focused identity/MFA/profile/consent/lifecycle modules and ordered migrations as needed, with single authoritative account state. |
| Library | Extend `backend/modules/library/repository/guarded.py`, local HTTP/schema and focused history/reference behavior; no corpus writer or automatic query rerun. |
| Personalization | Extend `backend/modules/personalization/guarded_service.py`, local HTTP/schema; add reset responsibilities, bounded recovery reads and permitted behavior/projection processing under this owner. |
| Usage | Extend `backend/modules/plans/guarded_repository.py`, local HTTP/schema and accepting-owner integration; preserve original-operation admission/settlement identity. |
| Shared application | Coordinate `backend/local_host.py`, `backend/local_profile.py`, `backend/local_browser.py`, `backend/transactions.py` and existing readiness/participant registration; no cross-owner SQL hidden in host glue. |
| Frontend | Extend `frontend/src/App.tsx` and `frontend/src/api.ts`; extract focused account/personal-control components beneath `frontend/src/` and update existing styles/tokens. Keep the paper journey working. |
| Verification | New `tests/u2_account_personal_controls/`, `backend/pytest.u2-account-personal-controls.ini`, focused frontend test/E2E paths and configuration, `scripts/verify_docsuri_u2.py`; share proven U1 runner primitives without copying its fixture-reset semantics into recovery tests. |
| Pipeline/docs | Scoped U2 workflow and developer/local operations instructions; update lock/config only for justified required dependencies and record identity/security/license evidence. No broad legacy CI rewrite bundled into this unit. |

Graph coverage was current with no recorded gap for inspected Python/TS paths; SQL accounts/local_schema (36–76), accounts/local_entry (13,17–20) and plans/local_schema (3–4) were partially parsed and read directly in full. These are bounded positive findings, not an exhaustive source audit. New implementation paths and further discovered consumers must be read/covered before changes and included in the final source manifest.

## Ordered implementation steps

Each layer is implemented, then its tests are written and run, before moving to the next layer. Runner readiness precedes the first executable test. Keep every checkbox unticked until its work and evidence actually exist.

### Step 1 — Establish source/configuration and canonical prerequisites

- [x] Inventory actual mounted U1/U2 consumers, policy/role/vocabulary boundaries and required participant scopes; distinguish current v2 owners from legacy routes. Confirm rollback/source boundaries and carry known U1 assistance/search/figure limitations.
- [x] Coordinate C02 authority guard, scoped session/proof/admin/lifecycle detail and C03/C13 exact revisions/errors. Formalize SD2-05 resetId/listResets/inspectReset, accepted vs live status and owner-bound cursor semantics. Formalize PIPE2-05 accepting-owner open→accepted versus open→closed and terminal closure evidence before accounting implementation.
- [x] Amend canonical contracts and schemas together, regenerate bindings, validate actual consumers, and explicitly handle required-field/version compatibility. Never treat an extra required resetId as automatically nonbreaking.
- [x] Add minimal U2 module/configuration skeleton and finite test-policy schema. Missing required policy/key/participant/provider evidence yields explicit unavailability; there is no successful placeholder.
- [x] Record planned source paths and changed ownership in the code record. Do not edit the AI-DLC installation or unrelated legacy features.

Trace: BR1.*, BR2.3–2.6, BR3.3, BR5.3, BR6.*, BR7.3; NFR7.1/NFR10.1–10.3; supporting contracts for all U2 assignments.

### Step 2 — Make the exact U2 runners ready

- [x] Create the U2 pytest markers/configuration, frontend unit configuration and Playwright configuration described in [test instructions](unit-test-instructions.md); preserve existing U1/U7 paths.
- [x] Implement only the bootstrap/preflight needed to run later database tests: explicit U2 synthetic profile/root/realm, validated environment ownership/expiry, private files/keys, port checks and deterministic fixtures. Keep full workload/restore/package phases for Step 13.
- [x] Verify toolchain/frozen dependencies and test collection. Fail zero or accidentally skipped suites; initial collection is runner evidence, not behavior success. Verify each exact command before its first execution step.

Trace: NFR7.2–7.3/NFR8.1–8.2; PIPE2-02–04. The fixture reset must not erase the state under an interruption/restart test.

### Step 3 — Implement persistent data models and migrations

- [x] Add compatible owner migrations for profile/authority controls, purpose-bound proofs/continuations, provider-subject uniqueness, encrypted inactive/active MFA records and one-time delivery, consent and complete lifecycle tickets/evidence.
- [x] Add Library reference/history controls and Personalization explicit settings, behavior boundaries, reset responsibilities, scope status, stable discovery indexes and immutable acceptance fields. Keep per-reset monotonic statusRevision separate from settings revision.
- [x] Add Usage assignment controls, bounded period/quantity, reservation identity, settlement and accepting-owner admission/closure evidence. Existing U1 data/contract behavior has an explicit compatibility path.
- [x] Apply least-privileged owner roles, finite constraints/indexes and migration identity/compatibility checks only to the owned synthetic realm. Record current restriction evidence needed for restore.

Trace: W1–W13, ENT ownership in entities.md; BR1.2–1.5/BR2.2–2.5/BR3.1–3.6/BR4.*/BR5.*/BR6.*.

### Step 4 — Write and run data-model/database tests

- [x] Create `tests/u2_account_personal_controls/database/` checks for uniqueness, owner role denial, proof consumption, session/authority serialization, reset acceptance/status revisions and ledger constraints.
- [x] Test migration/restart identity and both admission race orders with real PostgreSQL locks; include crash boundaries and stale closure/generation evidence. Verify current restrictions defeat older restore state.
- [x] Run the database phase under finite profile limits; preserve failures and inspect authoritative rows, not just HTTP or mock call counts.

Trace: V2/V4/V5/V6; NFR3.1–3.6/NFR4.1–4.7.

### Step 5 — Implement repositories and read projections

- [x] Extend existing owner repositories with parameterized owner-first queries, stable bounded keyset pages/cursors, exact receipt/intent replay and immutable original acknowledgements.
- [x] Implement fresh reset outstanding/history/inspect reads, complete bounded required-scope projections and monotonic per-ID status. Reads never enqueue, allocate, settle, clear or update a boundary.
- [x] Implement assignment inspection with non-null initial revision and no implicit allocation; maintain original-period ledger reads and evidence-based reconciliation.
- [x] Implement participant claim/evidence and restore restriction access under purpose-bound authority; no unrestricted cross-owner writers or stale cache authority.

Trace: W5–W13; BR1.1–1.5/BR3.4–3.6/BR4.*/BR5.3–5.4/BR6.*.

### Step 6 — Write and run repository tests

- [x] Create `tests/u2_account_personal_controls/repository/` checks for foreign/absent isolation, bounded pagination, lost acknowledgement, changed-intent conflict, stale revision and read-only recovery.
- [x] Check no writes from all list/inspect operations; reset restart discovery needs no prior browser storage. Test two resets, stale status/cursor, missing store and original-period reads.
- [x] Run against actual owner roles and transaction facility; fail missing required store instead of substituting in-memory success.

Trace: V3/V4/V6 and NFR2.3/NFR3.1–3.6/NFR4.1/NFR10.2.

### Step 7 — Implement owner business behavior

- [x] Complete registration/verification/login/logout, password reset/change, email replacement and full/limited session transitions with neutral initiation, bounded hashing/proofs and current authority.
- [x] Implement distinct Google/ORCID ports, bound single-use flows, collision-safe linking/unlinking and attributed optional profile data. Protocol fixtures remain labelled; real activation needs G2 evidence.
- [x] Implement MFA enrollment, single protected material delivery, factor confirmation/replay prevention and policy-bound recovery without bypass. Render QR locally.
- [x] Implement profile/consent and withdrawal/erasure/reactivation as separate policy-bound actions with complete manifest, generation-fenced owner tickets and truthful blocked/complete status. Destructive tests use only synthetic data; unresolved real policy blocks affected execution.
- [x] Complete saved references/searches/history, trusted clear checkpoints and source dispositions. Preserve saved work across profile/settings/credential changes.
- [x] Complete defaults/onboarding, manual/skip fallback, recent/derived views and consent/reset boundaries. Fix the inspected defaults/skip data-loss paths and prevent delayed activity from restoring prohibited records.
- [x] Complete mock plan and admin assignment control, finite reservation, atomic owner acceptance/closure, idempotent settlement and original-period reconciliation. No release from a negative read or lease timeout.
- [x] Integrate safe observations and current installed participants; no future-module placeholder claims cleanup success.

Trace: W1–W14; all BR1.1–BR7.3; full-scope FR5/FR6/FR7/FR8/FR10/FR11/FR17 and their child rows.

### Step 8 — Write and run component/business tests

- [x] Add eight owner/boundary component files with at least eight meaningful cases each: credentials/proofs, external identities, MFA, profile/consent/lifecycle, library/history, personalization/reset, usage/admission and transport/isolation.
- [x] Include success plus at least two error/edge cases per component; cover conflicting tabs, expiry/replay, missing participants/policy, changed consent, duplicate/unknown external outcome and repeated recovery.
- [x] Keep provider/network fakes at adapter boundaries and use the same canonical types. Cover bounded cryptographic libraries and side-effect invariants; tests cannot always pass or mirror implementation mechanically.

Trace: V1–V7; all functional lead rows and relevant support-boundary behavior.

### Step 9 — Implement API and mounted integration

- [x] Extend typed C02/C03/C13 routes within the existing host. Derive identity/quantity/role from trusted context, validate limits before expensive work and carry exact control revisions.
- [x] Implement safe session bootstrap, scoped cookies, CSRF/origin/CORS, CSP/no-store and single-use callback exceptions; browser JSON and URLs never expose ordinary session or proof secrets.
- [x] Mount reset discovery/status and personal-control routes with current owner checks and safe error envelopes. Unknown writes and dependency outages never become empty/success responses.
- [x] Bind real installed lifecycle/accounting participants, separate app-admin from U7, and expose safe capability-specific readiness with synthetic/actual evidence distinguished.

Trace: C02/C03/C13; W1–W14; NFR4.*, NFR9.*, NFR10.*.

### Step 10 — Write and run API/integration tests

- [x] Create `tests/u2_account_personal_controls/integration/` tests through the actual mounted host and owner stores; combine with Steps 4/6 for at least 32 real-store/API cases.
- [x] Exercise lost responses before/after commit, both race orders, stale claim, revoked sessions/admin role, forged owner/quantity, proof/callback replay, callback uncertainty, response redaction and dependent-owner outage.
- [ ] Verify boundary assertions against persisted effects/receipts/tickets/ledger and run cumulative U1/U2 host compatibility plus separate U7 isolation tests at the dedicated cumulative layer. Do not relabel isolated tests as cumulative proof.

Trace: V1–V7/V9; closes canonical-reset/revision/accounting findings only with reproducible passing evidence.

### Step 11 — Implement the integrated Korean frontend

- [x] Extend the existing shell and Transport with current authority-generation scoping, safe route restoration and owner-isolated cache/late-response handling. Clear private state on switch/logout/expiry and recheck focus/pageshow.
- [x] Implement account/recovery/identity/MFA/profile/consent/lifecycle panels; settings/onboarding/reset status; library/saved queries/history/recent views; mock plans/usage and administrator assignment.
- [x] Preserve query/reader context, inherited tokens and appearance modes. Mark temporary appearance changes unsaved on failed persistence; do not silently discard acknowledged interests/onboarding.
- [x] Provide explicit confirmation, precise revision conflicts, truthful accepted/pending/blocked/unknown states, manual fallback, bounded pages/polling, labels/focus/live announcements, reduced motion/reflow and data-testid hooks.
- [x] Never persist credentials/MFA/private forms or promise durable research-draft recovery in U2. Safe return restores views, never queues mutations.

Trace: frontend-components.md entire hierarchy; BR7.1–7.2; FR5–FR8/FR10/FR11/FR17 UI and NFR2/NFR4/NFR5/NFR6.

### Step 12 — Write and run frontend/browser verification

- [x] Add focused frontend unit suites for account flows, personal controls and authority isolation. Exercise loading/empty/error/conflict/unknown/pending/blocked/completed states.
- [x] Add at least 12 real browser journeys covering registration/recovery, MFA, links, profile/consent, lifecycle, library/history, onboarding/reset, usage/admin, restart discovery and account switch.
- [x] Include desktop/tablet/phone and Light/Dark/System, Korean long text, zoom/reflow, visible focus/keyboard order and protected-material clearing. Record actual keyboard/screen-reader checks and limitations; automated results alone do not claim WCAG conformance.

Trace: V8 plus user-visible V1–V6 outcomes.

### Step 13 — Complete environment, packaging, bounded operations and CI

- [x] Finish `scripts/verify_docsuri_u2.py` and owned U2 profile phases for repository/integration/browser/operations. Retain current U1 invocation and share helpers only with regression proof.
- [x] Enforce PIPE2-04 limits and measure admitted-commit/WAL/backup/restore footprint before load. Respect global process and recovery reserves; timeout cannot spawn replacement work while old capacity remains charged.
- [x] Add the nine V1–V9 operational/fault scenario families with resumable evidence, role separation, key rotation/missing-key, isolated restore against current restrictions, truthful readiness, saturation and seeded defect repair.
- [x] Build immutable manifests/artifacts, compatible ordered migrations and stop-migrate-start verification/rollback instructions. Do not deploy publicly or run real-data migrations.
- [x] Add scoped U2 actual-execution CI with frozen inputs, content hashes, read-only permissions and no private-host secrets on untrusted PRs. Record actual dependency/advisory/license checks and new-vs-base legacy failures.
- [ ] Prepare a runnable cumulative completion check covering U1/U7/U2 and their installed composition, without claiming fixture-only provider/public parity. Present the exact invocation at its separate human decision point before checkpoint verification.

Trace: PIPE2-01–09; V5–V9; NFR7.*, NFR8.*, NFR9.*, NFR10.3. Numeric service targets remain baseline-dependent.

### Step 14 — Complete evidence, review and Git handoff

- [x] Write code-summary.md, exact requirement-to-source/test traceability and source-manifest.json containing every created/modified/deleted application/config/test/generated path. Capture checks, failures and real-policy/provider gates honestly.
- [x] Cover all 62 assigned functional rows with lead/support attribution and all ten inception/39 derived NFR constraints; no support contribution is reported as another unit's completed feature.
- [x] Verify meaningful new-code coverage of at least 80% as retained additive testing guidance; never lower a configured target to pass. Current legacy test counts in memory are historical, not the verified baseline.
- [ ] Obtain the required independent review of completed implementation and evidence; repair actionable findings through the recorded process.
- [ ] Merge fulfilled work through a PR into develop under CONVENTIONS.md and its interim CI policy. No main promotion or public deployment. Do not mark U2/full release ready while required closure evidence is absent.

## Requirement-to-step map

| Requirement contribution | Implementation / verification steps |
|---|---|
| FR5, FR5.1–FR5.3: full Library scope | 1,3–10,11–12; reference/history durability and source-disposition integration |
| FR6, FR6.1–FR6.4: accounts/credential/lifecycle | 1–10,11–13; current authority, recovery and participant obligations |
| FR7, FR7.1–FR7.2: identity/MFA/admin | 1–10,11–13; real provider activation and controlled recovery remain gated |
| FR8, FR8.1–FR8.2: profile/consent/mock plan | 1,3–12; purpose boundaries and truthful nonbilling presentation |
| FR10, FR10.1–FR10.2: personalization/reset | 1,3–12; stored defaults, delayed-event fences and fresh reset discovery |
| FR11, FR11.1–FR11.2: onboarding/ORCID suggestions | 1,3–12; optional/manual/resumable and provenance-preserving |
| FR17, FR17.1–FR17.2: assignment/accounting | 1,3–10,11–13; exact revision, terminal admission and original-period evidence |
| Supporting FR1/FR1.1–1.3, FR2.3, FR3/FR3.1–3.2, FR4/FR4.1–4.2, FR9/FR9.1–9.2 | 1,5–10,11–13; authority/defaults/library/accounting integration only; feature owners retain full parity work |
| Supporting FR12/FR12.1–12.2, FR13/FR13.1–13.3, FR14/FR14.1–14.2, FR15/FR15.1–15.2, FR16/FR16.1–16.2 | 1,3–10,13–14; consent, lifecycle, quotas and owner contracts; no premature U4/U5/U6 feature claim |
| Supporting FR18/FR18.1–18.3, FR19/FR19.1–19.3 | 1,3–10,13–14; source disposition, restoration, safe operations and readiness |
| NFR1–NFR10 / all 39 derived IDs | All relevant steps; final traceability gives concrete source/test evidence, with local vs external proof separated |

## Completion evidence and stop conditions

A synthetic-profile pass may establish isolated implementation behavior only. Missing real provider permissions, retention/continuity, MFA recovery decisions, quota policy or public fit must remain explicit and may require the maintainer's decision before affected operation. Preserve unresolved responsibilities on exhaustion; no automatic “complete” based on a healthy shell, collected tests or an unavailable capability.

New test failure, unsafe resource fit, contradictory canonical behavior or unreviewed source-boundary expansion is investigated with evidence. Existing session approval authorizes this plan's preparation; implementation still waits for the recorded Plan Approval. The separately approved cumulative verification invocation remains a later decision once it actually runs.

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

