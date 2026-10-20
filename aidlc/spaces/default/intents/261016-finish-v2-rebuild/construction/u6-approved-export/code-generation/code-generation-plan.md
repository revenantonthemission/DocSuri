# U6 — Approved export · Code generation plan

Unit `u6-approved-export` · branch `feature/u6-approved-export` · scope express base · methodology test-after per component · strategy standard · existing suites stay green.

## Summary

- Builds: the ApprovedExport module and everything it needs. That is schema `export`, the repository, sealed-token custody, the render policy, a Notion adapter (pinned `notion-client` SDK behind a guarded transport, with a fake Notion), the export service, the worker pass step and export lane, the lifecycle participant, operator key commands and the C09 routes. It also builds the synthetic composition and the operator-only real composition, the Korean export view and stepped flow, and U6's environment tool and CI lane.
- Touches: U2's keyring (moved onto a shared custody helper, behaviour unchanged) and its lifecycle projection (A8). The shared C09 contract (A1–A7, A9, A10, A6 extension, as an additive minor release), with regenerated bindings, wire types and both consumer inventories. The shared runtime allowlists and composition chain (including U3's topics gate), the application shell, U4's novelty result screen, `frontend/src/api.ts`, U2's cumulative frontend lane, and `notion-client==3.1.0` in `backend/pyproject.toml` and `backend/uv.lock`.
- Tests: five to eight tests per component across the database, repository, component, integration and operations layers. Shared contract tests, Vitest component tests, and browser journeys with keyboard, reflow and axe checks. Every item of security design §13 and cicd-pipeline §3.2. An 80% line-coverage floor, never lowered, for the backend total (which also measures `backend/u3_host.py`), for `scripts/u6_preservation.py` on its own, and for `frontend/src/u6-export`.

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

## Inputs and boundary

### Approved inputs

Links are relative to this folder.

- Functional design: [functional-spec.md](../functional-design/functional-spec.md), [rules.md](../functional-design/rules.md) (BR1.1–BR8.3), [entities.md](../functional-design/entities.md), [frontend-components.md](../functional-design/frontend-components.md), [functional-design-questions.md](../functional-design/functional-design-questions.md)
- NFR requirements: [security-requirements.md](../nfr-requirements/security-requirements.md) (NFR1.1–NFR6.4), [tech-stack-decisions.md](../nfr-requirements/tech-stack-decisions.md)
- NFR design: [security-design.md](../nfr-design/security-design.md) (D1–D16), [logical-components.md](../nfr-design/logical-components.md), [nfr-design-questions.md](../nfr-design/nfr-design-questions.md), [review-02.md](../nfr-design/reviews/review-02.md) (open points R-13–R-16)
- Infrastructure design: [cicd-pipeline.md](../infrastructure-design/cicd-pipeline.md), [infrastructure-design-questions.md](../infrastructure-design/infrastructure-design-questions.md) (Q1 A, Q2 A, Q3 B, Q4 A), [review-01.md](../infrastructure-design/reviews/review-01.md) (open points R-01–R-08)
- Inception: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md), [requirements.md](../../../inception/requirements-analysis/requirements.md) (FR2, NFR1–NFR6)
- Frozen contract C09 and the canonical binding rule: [contract-summary.md](../../../../261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md) (C09 at lines 4700–4945; canonical identity at 17531–17551)

### What U6 owns

All application code sits at the workspace root:

- **Backend:** `backend/modules/export/` (the Python module and its `u6_*.sql` migrations), `backend/key_custody.py`, `backend/u6_policy.py`, `backend/u6_host.py`, `backend/u6_real_export.py`.
- **Scripts:** `scripts/verify_docsuri_u6.py`, `scripts/serve_docsuri_u6.py`, `scripts/u6_browser_fixtures.py`, `scripts/u6_preservation.py`, `scripts/u6_real_export.py`.
- **Backend tests:** `tests/u6_approved_export/`, `backend/pytest.u6-approved-export.ini`, `backend/.coveragerc.u6`.
- **Frontend:** `frontend/src/u6-export/`, `frontend/test/u6-export/`, `frontend/e2e/u6-approved-export/`, `frontend/tsconfig.u6-export.json`, `frontend/vitest.u6-export.config.ts`, `frontend/playwright.u6-export.config.ts`.
- **Shared tests and data:** `shared/python/tests/test_export_contract.py` and the golden hash vectors `shared/export-hash-vectors.json`.
- **CI:** `.github/workflows/u6-approved-export.yml`.

### What U6 changes outside its module

| Change | Files | Kept safe by |
|---|---|---|
| U2 keyring extraction (D1) | `backend/modules/accounts/control_keys.py` becomes a thin setting of `backend/key_custody.py`. `control_key_recovery.py` does not change. | U2's three keyring test files pass unchanged (cicd §2.4) |
| A8 | `backend/modules/accounts/services/control_lifecycle.py` (the retained-reason rule at lines 341–346), plus a new accounts-owned migration `backend/modules/accounts/u6_lifecycle_guard.sql` | U2's suites stay green; U6's projection test covers the changed lines (Step 20) |
| Shared contract | Edited in the canonical source `aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`. The generated schemas fail `--check` if edited by hand, and precedent commit `ac55d423` edited this source. C09's `version` goes from 2.0.0 to 2.1.0 and the release from 3.0.0 to 3.1.0 (Step 3). Regenerated: `shared/dtos/workspace.schema.json`, `shared/events/execution.schema.json`, `shared/python/src/docsuri_shared/_binding_generations/` with `_binding_head.json`, `frontend/types/wire/dtos.ts`, `shared/python-consumers.json`, `shared/typescript-consumers.json` | drift checks; the additive-only contract test with its two named exceptions (Step 4) |
| Shell and entry points | `backend/local_host.py` (capability and navigation entry); `frontend/src/App.tsx` (minimal, R-04); `frontend/src/api.ts` (safe codes and Korean copy); `frontend/src/u4-research/research-workspace.tsx` and a new `frontend/src/u4-research/export-action.tsx` | U3 and U4 lanes keep `src/App.tsx` at or above 48%; U4's lane keeps `src/u4-research` at or above 80% |
| Composition chain | `backend/u3_host.py` (the topics gate also admits the U6 triple; a new export gate; the lane in the lifespan), `backend/u4_host.py`, `backend/u5_host.py` (a keyword pass-through) | U3–U5 assemblies behave as today when `export_factory` is absent; `backend/u3_host.py` is measured in `.coveragerc.u6` and its gates are tested (Step 22) |
| Allowlists and owner slots | the list in decision R-06 | the completeness test (R-06) |
| Frontend lanes | `frontend/vitest.u2-cumulative.config.ts` (one include glob); new shell tests in `frontend/test/u3-paper-corpus-capabilities/` and `frontend/test/u4-research-novelty/` | the lanes run locally before the pull request |
| Dependency | `backend/pyproject.toml`, `backend/uv.lock` | `pip-audit`; local environments re-created |

### What U6 must not change

- U4's records and its export read. U6 only calls `ResearchService.readNoveltyArtifactForExport`.
- The approved upstream design artifacts. Every wording difference is recorded for the U6 checkpoint instead.
- In U2: the keyring's behaviour, file names, version pattern, generation range of 1 to 3, exception types and messages, the `ControlKeyring.__new__` construction path, `control_key_recovery.py`, and U2's test files.
- Any applied migration of U1–U5, U5's tool, or U5's pinned constants. U6 has its own runner and its own migration tuple.
- The frozen connection states (no `pending` on the wire) and the frozen error lists of the nine operations.
- Any coverage floor, or the phase bound (except by the recorded R-08 path).
- The old v1 Notion export (`frontend/lib/api/apiClient.ts`, `components/agent/NotionExportPanel.tsx`).
- Anything in an owner's Notion workspace beyond creating one page per approved export: no edit, archive or delete.
- The $0 rule: no paid dependency or service, and no OAuth.

## Decisions carried into code

### Open review points

- **R-13 (NFR design: first-time connect).** Settled by infrastructure Q3 B and Q4 A.
  - When an owner with no record configures for the first time, one short transaction inserts an internal `pending` row in `export.connection`, plus its `export.connection_pace` row. The pending row has revision 0, the id of the check that holds it, and `pending_started_at`.
  - The token check is then paced and capped by that row's connection id, like any other call: the candidate target carries that id (R-14).
  - The rule "a missing pace record counts as could-not-check" can therefore never hit a first configure: the record exists before the check starts.
  - Proved by: a first configure with no connection succeeds, is paced, and advances that row's `connection_pace.next_slot_at` (Step 22).
- **R-14.** `NotionSession.run` takes one of two targets:
  - `StoredConnection(account_id, connection_id)`: the token is opened inside the reduced region;
  - `CandidateToken(connection_id, value)`: a token the caller holds for that one operation, with the connection row it is checked for (the pending row on a first configure, the owner's row on a replace or reconnect).

  Both obey the same rules: the pace slot and, for a browser request, the interactive gate are keyed by the target's connection id; nothing logs the value; no field holds it after the call; and it is dropped together with the clients. Proved in Steps 14 and 22.
- **R-15.** The approved `logical-components.md` is not edited. Its source line "decisions D1–D14" should read "D1–D16". The code summary records this as a wording settlement for approval at the U6 checkpoint. No test.
- **R-16.** A failed `export.token_key_counts()` call raises `ProtectionUnavailable`. That covers a database error, Busy, a timeout and a malformed result. Creating a first key needs a successful count of zero sealed tokens, so a failure can never create a key. Proved by an operations test with the count failing (Step 10).
- **R-01 (infrastructure: revision 0).** In the store:
  - The `state` CHECK of `export.connection` admits `pending` beside the four wire states.
  - `revision integer NOT NULL CHECK (revision >= 0)`.
  - `CHECK ((state = 'pending') = (revision = 0))`.
  - `CHECK ((state = 'pending') = (pending_holder IS NOT NULL))` and `CHECK ((pending_holder IS NULL) = (pending_started_at IS NULL))`.
  - A pending row holds no envelope.

  Every read filters out pending rows, so no response ever carries `pending` or revision 0. The contract keeps the frozen four states, and a shared test proves it. The approved `entities.md` stays unchanged. The code summary records an entity wording settlement for approval at the U6 checkpoint:
  - ExportConnection's `revision` minimum of 1 and its four states describe every record visible outside the store;
  - the store also keeps an internal pre-connection reservation (state `pending`, revision 0, holder, start time) that never reaches the wire;
  - the store keeps four more internal columns that frozen shapes or the design need: `workspace_id` (for ExportDestination.workspaceId), the attempt's `deadline_at`, the attempt's `creator_confirmed`, and the effect's `ended_at` (decision "Newer succeeded export").
- **R-02.** Every change to a pending row is a compare-and-set on its holder:
  - **Promote:** the configure store function updates only `WHERE account_id = $1 AND state = 'pending' AND pending_holder = $2`, moving revision 0 to 1.
  - **Release after a failed check:** `export.release_pending(p_account, p_holder)` deletes only the row held by `p_holder`. The pace row goes with it by cascade.
  - **Takeover:** `UPDATE … SET pending_holder = $new, pending_started_at = $now WHERE account_id = $1 AND state = 'pending' AND pending_holder = $observed AND pending_started_at <= $now - takeover`.
  - **Housekeeping:** `export.sweep_stale_pending(…)` deletes only rows whose holder and start time still equal the observed pair and are past the takeover time.

  Zero affected rows means the row moved on: nothing else is written, and configure answers CONFLICT. The state-machine row "pending | the holding check ends any other way" therefore carries the guard "still pending and held by this check". Proved by a repository test (Step 8): a check whose row was taken over or deleted neither stores nor deletes, and the new holder's row and pace row stay intact.
- **R-03 (which code a second connect gets).** The code is **CONFLICT** (HTTP 409).
  - **Where the list is:** `shared/dtos/workspace.schema.json` holds only the global `Error.code` enum (INVALID_TOKEN at line 62) and no per-operation lists. Configure's frozen list is in the canonical contract, `contract-summary.md` lines 4725–4738: INVALID_ARGUMENT, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE, INVALID_TOKEN, CONFLICT, IDEMPOTENCY_CONFLICT.
  - **Why CONFLICT:** a second configure racing a held check is a concurrent change to the owner's single connection (BR1.3), and nothing about Notion is unavailable.
  - **How the frontend shows "확인 중":** the shared boundary fixes the message key by code (`backend/local_browser.py:52`), so the connect form tells the two CONFLICT cases apart by re-reading the connection. Still not connected: "다른 창에서 연결을 확인하고 있습니다. 잠시 후 다시 시도하세요". Connected at a newer revision: "다른 곳에서 연결이 바뀌었습니다", with the reloaded state.
  - Proved in Steps 22 and 24.
- **R-04.** `App.tsx` gains only:
  - `export: '내보내기'` in NAV_COPY;
  - `'export'` in OWNER_BOUND and in the view union;
  - one capability lookup through `findExportCapability` from `src/u6-export`;
  - one click branch and one render branch;
  - the capability prop passed to the novelty `ResearchWorkspace`.

  Everything else lives in `src/u6-export` and `src/u4-research/export-action.tsx`. New shell tests `test/u3-paper-corpus-capabilities/export-shell.test.tsx` and `test/u4-research-novelty/export-shell.test.tsx` exercise every added App.tsx line. Before the pull request, both lanes run locally with coverage and must keep `src/App.tsx` at or above 48% lines (Steps 24 and 27).
- **R-05.** `scripts/u6_preservation.py` exposes `archive(path, context)`.
  - `context` is a frozen dataclass of the runner's helpers, built and passed in by `verify_docsuri_u6.py`: identity and manifest checks, resources, idle port, `lsof`, file inventory, admin connection, docker stop, folder sync. The module never imports the runner, so there is no cycle.
  - The key-folder names (`export-token-keyring.json`, `.lock`, `.initialized`) and the staging-name pattern are module constants in `backend/modules/export/token_keyring.py`. The pattern is `STAGING_PREFIX = ".export-key-"` plus a regex of that prefix followed by 32 lowercase hex characters. Both the keyring and the archive import them, and nothing else defines them.
- **R-06.** Every realm-exact check that must admit the U6 environment:

  | # | Where | U6 entry | Step |
  |---|---|---|---|
  | 1 | `backend/local_profile.py:76`, `:113`, `:122` | `"u6"` in the unit tuple; ports `(18099, 15499)`; realm `("u6-approved-export", "approved-export")` | 1 |
  | 2 | `backend/transactions.py:96–98`, `:99–104`, `:122–130`, `:150–153` | the managed realm; owners `OWNERS ∪ {research, topics, export}`; `("docsuri_u6", "approved-export")` in the explicit realm set and in the per-owner gate set | 1 |
  | 3 | `backend/local_browser.py:30–35`, `:84–87`, `:152–158` | `EXPORT_ORIGIN = "https://127.0.0.1:18099"`; the `boundary_route` origins; host `127.0.0.1:18099` in `read_payload`'s 64 KB list | 1 |
  | 4 | `backend/artifacts.py:29–35` | root `/tmp/docsuri-u6-run` | 1 |
  | 5 | `backend/local_host.py:340–342` | the realm in readiness's managed list | 1 |
  | 6 | `backend/modules/accounts/local_http.py:16`, `:54` | `EXPORT_ORIGIN` in the account routes' origins | 1 |
  | 7 | `backend/modules/accounts/services/guarded_entry.py:436`, `:483` | `approved-export` joins `topics-digests` for the `account-control` purpose | 1 |
  | 8 | `backend/modules/personalization/guarded_service.py:42` | the same purpose rule | 1 |
  | 9 | `ops/src/docsuri_ops/local_transport.py:44` | `("approved-export", "https://127.0.0.1:18099", "docsuri_u6")` → `approved-export-tls` | 1 |
  | 10 | `backend/u3_host.py:229`, `:250–266`, `:365–369` | the topics gate at `:252–256` also admits (`docsuri_u6`, `approved-export`, `EXPORT_ORIGIN`); a new export gate admits `export_factory` only for that triple, with research and topics; required capability `export` | 21 |
  | 11 | `backend/local_observation.py:42–94`, `:140` | `PROBES["export"]`; excluded from the default observed set | 21 |
  | 12 | `backend/lifecycle_effects.py:12–20` | `"export": "ApprovedExport"` | 19 |
  | 13 | `frontend/playwright.u6-export.config.ts` (new) | U6's environment values | 25 |

  An operations test keeps this list complete (Step 26). It scans every Python file in `backend/` and `ops/src/`, excluding `backend/modules/topics/` and `backend/u5_*.py`. Any file that names the U5 environment (`topics-digests`, `docsuri_u5`, `127.0.0.1:18089`, `/tmp/docsuri-u5-run`, or the unit key `"u5"`) must also name its U6 counterpart, or the test fails. The scan cannot see a gate that still refuses the U6 triple in a file that names `docsuri_u6` elsewhere, so the topics gate of row 10 is also tested directly (Step 22).
- **R-07.** A database test asserts that `has_column_privilege('docsuri_export', 'export.connection', <column>, <privilege>)` is false for SELECT, INSERT, UPDATE and REFERENCES on `sealed_token` and on `token_key_version`. It is true for SELECT, INSERT and UPDATE on every other column (Step 6).
- **R-08.** What happens if the suite outgrows the phase bound:
  - The bound stays 300 s, as a named constant `PHASE_SECONDS` in `verify_docsuri_u6.py`.
  - An overrun fails the coverage phase like any other failure, and its partial output never counts.
  - The remedy comes in order. First make the tests faster: reduced policy values, injected clocks, module-scoped mounted apps, fewer round trips. Only then raise the bound, as a recorded change: name it with its measured duration in the code summary and get it approved at the U6 checkpoint.
  - The bound is never escaped by splitting the coverage pass, excluding tests or lowering a floor.

  An operations test also checks that every layer folder (`database`, `repository`, `component`, `integration`, `operations`) collects at least one test, beside the runner's own refusal of zero tests (Step 26).

### Further rules found while planning

- **Composition chain.**
  - `assemble_u5` and `assemble_u4` gain a keyword-only `export_factory=None`, passed through to `assemble_u3`.
  - In `assemble_u3`, the topics gate (`backend/u3_host.py:252–256`) admits (`docsuri_u6`, `approved-export`, `EXPORT_ORIGIN`) as well as U5's triple, because `assemble_u6` reaches it through `assemble_u5`, which always passes a topics factory. A new export gate admits `export_factory` only for that U6 triple, and only together with the research and topics contributions. The research gate is unchanged: it is reached only without topics.
  - `assemble_u3` calls `export_factory(transactions, entry, corpus_repository, worker, research=<the research contribution's service>)` and adds `export` to `required_capabilities`. In its existing lifespan it starts the export lane, and stops it after the control loop closes and before the transactions close.
  - `assemble_u6(profile)` is `assemble_u5(profile, export_factory=…)`, which logical-components §7 requires. As built, `assemble_u5` has no factory pass-through and the realm triple and capability set are literals, so it cannot be wrapped without these changes.
  - These branches are more than the "one value in an existing list" that cicd §2.5 assumed for `backend/u3_host.py`, so the file joins `.coveragerc.u6` (decision "Coverage scope") and its gates and lifespan order are tested (Step 22).
- **One clock.** Every due-time decision compares against one `now` that the caller passes in from the composition's clock, and SQL receives it as a parameter. That covers the pending takeover, settling wait, check schedule, scan budget, orphan threshold, rate-limit window, could-not-check bound, retention and the rolling hour. Only the pace reservation uses the database clock (D6). Tests inject the clock. The synthetic composition reads a delegated, run-bound `export-fixture-clock.json`, like U5's digest clock.
- **Press or continue.**
  - One press sends the same key on approve and execute. Execute therefore treats a key equal to the approval's own request key as the press's second call.
  - Any other execute on an approved, unconsumed approval is a continue, and re-derives the binding first (BR3.7).
  - On a continue:
    - a stale session or a changed binding invalidates the approval and answers APPROVAL_REQUIRED;
    - if U4 says the source is no longer exportable, the answer is SOURCE_INELIGIBLE;
    - could-not-check answers DEPENDENCY_UNAVAILABLE and leaves the approval approved.
  - Either way, the lane's pre-write check guards every write (BR3.3).
- **Newer succeeded export (BR3.1; functional spec, Execute call and the approved → consumed guard).** An effect records `ended_at` when it reaches succeeded, failed, cancelled or invalidated. Approve answers CONFLICT and records nothing, and the bind answers CONFLICT and leaves the approval approved, when an effect of the same export pair is succeeded with `ended_at` later than the `prepared_at` of the approval's preview revision. This covers continuing an older approval after a newer export of the same pair succeeded.
- **Interactive gate (D15).** Every Notion operation that a browser request runs passes the InteractiveGate, keyed by the connection id:
  - configure and replace (the candidate check);
  - a destination listing, with its `lastDestinationId` read, as one operation;
  - the preview's destination read;
  - the binding check's destination read when approve or a continue runs it.

  The lane never takes a slot. Over either cap the operation answers at once: DEPENDENCY_UNAVAILABLE, or for a listing a listing with no destinations and `listingComplete: false`, which the destination step shows as unavailable with refresh. A configure refused by the gate releases its pending row (cicd §8.1).
- **Policy references.** The only value accepted as `credentialPolicy` and as `renderPolicy` is the `export` capability's policy reference, `ExportPolicy.reference()`. Anything else answers POLICY_UNRESOLVED (BR8.3). That reference is the render policy recorded on a preview, and a change to rendering bumps its revision.
- **Hashes.**
  - **`renderedContentHash`** is the SHA-256 of the page body tree `{"properties": {"title": …}, "children": […]}`, in the form of U4's `digest` (NFR4.2; security design §8.4). The frozen prose that hashes `renderedText` (`contract-summary.md` 17540–17543) is superseded by that approved requirement. The Step 3 amendment text says so, for approval at the checkpoint.
  - **`bindingHash`** follows the frozen canonical rule (17543–17547): SHA-256 of `docsuri:export-binding:v1\n` plus the JCS bytes of {ownerId, previewId, revision, source, sourceEligibilityRevision, connectionRevision, destination, renderedContentHash, renderPolicy}.
  - In that preimage, `destination` holds only the destination's identity fields: destinationId, connectionId, workspaceId, parentPageId, formatRevision. It never holds the display-only title or context, so renaming a page does not void an approval.
  - **Golden byte vectors** for both hashes live in one data file outside any test module, `shared/export-hash-vectors.json`: each case holds the input value, its canonical bytes as hex and the expected digest. The shared contract test, the backend rendering test and the fake Notion's test all read that file. No test imports another suite's test module (the shared suite runs from `shared/python` with its own `conftest`; the backend suite runs under `backend/pytest.u6-approved-export.ini`), and `fake_notion.py` hashes with the backend's own function, never with test data. The shared catalog checks read only `*.schema.json` files, so the data file trips none of them.
- **Settlement S2 (listing facts on the wire).** The approved frontend data sources read completeness and, per destination, `readable`, `creationCapability` and `writable`; A1 and A6 name these only on the provider inspection. BR1.5's preselection also needs the connection's `lastDestinationId`, which no frozen field carries. Code generation carries them on the public listing: optional `readable`, `creationCapability` and `writable` on the A1 response record, and optional `listingComplete` and `lastDestinationId` on ExportDestinations.
  - The destination step derives its state: complete with entries; complete with none (`empty`); incomplete with entries (`partial`); incomplete with none (`unavailable`).
  - It preselects `lastDestinationId` only when that page is in the listing and readable; otherwise it drops it with a notice (BR1.5).
  - This is recorded as an A1/A6 wording settlement for approval at the U6 checkpoint.
- **Connection facts from outcomes (BR1.5, BR4.2; entities.md ExportConnection).** Every transition of an effect to succeeded (a created page, a verified read-back, a marker found, or an owner settlement as delivered) sets the connection's `last_destination_id` to the bound destination. A created page or a marker found sets `creation_capability = confirmed`, and a no-access refusal sets `refused`, each only while the connection is still at the attempt's connection revision, so an outcome from an older token never marks a replaced connection. These updates leave the revision unchanged. A replace or reconnect resets the capability to `unknown`.
- **Rendered copies (BR2.6, NFR1.5).** Housekeeping trims, in bounded batches, every preview revision that can no longer lead to a write:
  - one never approved and superseded by a newer revision of its pair;
  - one whose approval is consumed, cancelled or invalidated, and whose bound effect, if any, is succeeded, failed, cancelled or invalidated.

  Both housekeeping invalidations (authority-revoked and source-changed) trim in their own transaction. A revision whose approval is still approved and unconsumed keeps its tree even when superseded, because continuing it writes that tree (NFR1.5 keeps a copy while "its export is unsettled"); D4 bounds this by the approving session. The current never-approved revision keeps its tree until the 7-day purge removes it. This reading of BR2.6 is recorded for approval at the U6 checkpoint.
- **Revocation (D16, BR1.4).** A stored-token 401 revokes by compare-and-set on the revision the operation opened. One transaction clears the envelope, sets revoked, advances the revision and invalidates approved approvals and accepted effects bound to an earlier revision (connection-changed); an executing effect finishes and an unknown one stays unknown. A revision that has moved on discards the revocation, and nothing changes.
- **Read retries (NFR4.6; security design §9.3).** The adapter retries a read, never a write, after a 429 that is not marked `public_api_request_blocked` or a 529:
  - at most `ExportPolicy.read_retries` (3) times, all inside the operation's budget;
  - before each retry it waits for the later of Notion's stated wait and the next pace slot;
  - when the stated wait would end past the remaining budget, the read stops at once with that budget's outcome;
  - a blocked 429 is never retried.

  A scan whose retries are spent records listing-incomplete; a listing whose retries are spent is returned with `listingComplete: false`; every other read reports could-not-check.
- **Error reduction (NFR3.6; security design §7).** `NotionSession.run` returns a fixed category value. No exception object is stored on a record, result or attribute, logged or returned. Where a reduced error has to be raised, it is raised after the `except` block has ended, with `from None`, so both its `__cause__` and its `__context__` are None. Inside an `except` block, `raise … from None` would still leave the original exception, with its request and `Authorization` header, in `__context__`.
- **Key folder custody (security design §4.3).** At every `TokenKeyring` load, and before every key command, the key folder is checked with `lstat`, as `LocalProfile` checks the environment folder (`backend/local_profile.py:84–91`): it must be a directory, not a symbolic link, owned by `os.getuid()`, with no group or other permission bits. Anything else raises `ProtectionUnavailable` and creates nothing. The built keyring checks only its files (`control_keys.py:53–107`), so the shared helper cannot supply this check. `u6_host` passes `profile.root / "export-keys"`.
- **Configure from `unavailable`.** The approved state machine offers only disconnect from `unavailable`. Configure there answers CONFLICT, and the panel offers "연결 해제" first, following security design §4.5's unavailable → disconnected → connected path.
- **Deletes.** The runtime role holds no DELETE on any export table, as with U5's topics role. Deletes run only through SECURITY DEFINER functions owned by `docsuri_export_owner`, with owner and compare-and-set predicates: `release_pending`, `sweep_stale_pending`, `purge_unapproved_previews`, and the lifecycle functions guarded by `accounts.lifecycle_effect_action`.
- **Foreign keys and erase order (BR6.2).**
  - These foreign keys cascade: `export.effect.approval_id`, `export.attempt.effect_id`, `export.reconciliation_check.effect_id`, `export.preview_revision.preview_id` (from its pair) and `export.connection_pace.connection_id`.
  - The approval's foreign key to its preview revision does not cascade, so no approved revision can ever be removed.
  - `export.erase_account_records` deletes, in order: the account's approvals (with their effects, attempts and reconciliation checks), its preview pairs (with their revisions), its replay records, then its connection (with its pace row).
- **Error codes.** Each operation's domain refusals use only its frozen list, or the A2/A3 lists set in Step 3. The shared boundary's platform answers stay exactly as it produces them for every C0x surface:
  - UNKNOWN_OUTCOME for a lost DocSuri commit (distinct from OUTCOME_UNKNOWN);
  - RATE_LIMITED for an exhausted gate;
  - DEADLINE_EXCEEDED;
  - admission's 503 NOT_READY.

  The 20-per-hour refusal carries its wait in whole seconds: `ExportError("CAPACITY_EXHAUSTED", retry_after=n)` becomes `BrowserDenied(429, "CAPACITY_EXHAUSTED", retry_after=n)`, which the shared boundary writes as the body field `retryAfterSeconds` (`backend/local_browser.py:41–55`, `:111–112`). The browser reads only that field (`frontend/src/api.ts:132–134`). No `Retry-After` header is set or read. The in-flight refusal carries no wait.
- **Replay records.**
  - Approve and execute keep their key on the approval and effect rows, with `UNIQUE (account_id, request_key)`.
  - Configure and settle keep theirs in `export.replay_record (account_id, operation, operation_key, input_hash, response)`. Its input hash covers the request without the token field. Its response holds only identifiers, state, revision, or the refusal code.
  - Cancel and disconnect are idempotent by state.
- **Erasure order.** Erase counts exported and possibly-created pages before deleting anything. The external_copies scope reports from the account's rows. If live_records has already erased them for the same request, it reports from that request's recorded counts. The report therefore never depends on the order of scopes.
- **Coverage scope.**
  - `.coveragerc.u6` measures cicd §2.5's include list plus `backend/u3_host.py`. U3's coverage has no floor (`backend/.coveragerc.u3` has no `fail_under`, and `scripts/verify_docsuri_u3.py:837–850` passes no `--cov-fail-under`), and `.coveragerc.u5` does not list the file. Without this, the new gates and lane lifecycle in `assemble_u3` would sit under no floor. The widened list is recorded for approval at the U6 checkpoint.
  - `control_lifecycle.py` (620 lines) can be reached in U6's realm only through `__init__`, `claim`, `acknowledge` without its reactivate branch, and `_status`: about a third of the file.
    - `request`, `prepare_confirmation`, `request_confirmed`, `request_browser`, `status_transport`, `inspect_limited`, `evaluate_restore` and `reactivate` need U2-only schema: `accounts.control_receipt`, `accounts.control_proof`, `accounts.current_restriction`, `accounts.account.lifecycle_state` or `accounts.session.flow_id`.
    - Only `backend/modules/accounts/u2_controls.sql` creates those, and U6's inherited chain (`verify_docsuri_u3.py:56–72`, `verify_docsuri_u4.py:59–66`, `verify_docsuri_u5.py:60–77`) does not apply it. The real entry also refuses any realm but `account-controls` (`control_policy.py:55–57`).
    - Those lines stay unreached and count as missed in the total. `guarded_entry.py` reached 79% in U5's realm, and a similar figure is expected here.
  - The 80% total floor stays, and no file leaves the list. U6's own module and scripts, which are several times larger than the unreachable remainder, must be covered well above 80% to carry it. Build and Test records the total and each U2 file's percentage. If the total falls short, the coverage phase fails. The remedy is more legitimate tests of reachable lines, never an exclusion, a lowered floor, or a test-only path into U2's tables.
  - `control_keys.py` is earned by the U2 keyring parity test (Step 10). The session and settings flows in the U6 realm cover `guarded_entry.py` and `guarded_service.py` (Step 22).
- **Inherited defect, recorded and not changed.** The chain's last capacity amendment, `ops/src/docsuri_ops/u4_capacity.sql`, binds its WAL term to `docsuri_u4`. The U6 realm, like U5's, therefore measures database bytes only. No approved design asks U6 to change this, so the code summary records it for U8.
- **Safe-codes side effect.** Adding OUTCOME_UNKNOWN to `SAFE_CODES` makes U4's existing retry path (`frontend/src/u4-research/action.tsx:37`) reachable for the server's OUTCOME_UNKNOWN. U4's tests must stay green, and the code summary records the change.
- **Speed without real waits.** Where time matters, tests build `ExportPolicy` values smaller than production: pace interval, budgets, windows. `REAL_ACTIVATION_EXPORT` refuses any value faster or larger than the documented free limits.
- **CI path filters.** U6's workflow also lists the earlier tool scripts that U6's tool imports (`scripts/verify_docsuri_u1.py`, `scripts/bootstrap_docsuri_u1.py`, `scripts/verify_docsuri_u3.py`, `scripts/verify_docsuri_u4.py`, `scripts/verify_docsuri_u5.py`) and the regression folders it runs (`tests/u1_integrated_paper_journey/**`, `tests/u2_account_personal_controls/**`). Ruff covers every U6 script, including `scripts/u6_real_export.py`. This closes the gaps the survey found in U5's lane, and only adds triggers. cicd §2.1 says the workflow mirrors U5's line for line, so the extra filters and this rationale are recorded for approval at the U6 checkpoint (Step 28).

## Steps

### Step 1 — Project structure and configuration skeleton

- [x] Create `backend/modules/export/__init__.py`, with a docstring naming this plan.
- [x] Create `backend/modules/export/errors.py`:
  - `ExportError(code, *, current=None, retry_after=None)`, in the `TopicsError` shape. `retry_after` is the whole number of seconds until exporting is possible again, and only the 20-per-hour bind refusal sets it;
  - `ProtectionUnavailable(RuntimeError)` for every custody fault, carrying no secret text.
- [x] Create `backend/u6_policy.py` with a frozen `ExportPolicy`. It holds every operating value of NFR4.10 and every budget of security design §9.1:
  - **Deadlines and budgets:** write deadline 90 s; read request timeout 30 s; token check, listing and page read budgets 30 s; read-back 60 s; scan 300 s.
  - **Reconciliation timing:** settling wait 180 s counted from `deadlineAt`; check schedule at 3, 10 and 30 min, then hourly, then every 3 h, for 24 h in total.
  - **Retries and pace:** rate-limit window 600 s with at most 4 attempts; 3 read retries; 500 ms pace interval.
  - **Waits and thresholds:** 24 h could-not-check wait; 900 s orphan threshold; 300 s clock margin.
  - **Per-owner limits:** 1 export in flight; 20 bound per rolling hour.
  - **Retention and caps:** 7-day unapproved-preview retention; a 2 MB response cap (2,000,000 bytes, as NFR4.10 states); interactive caps of 2 per process and 1 per connection; 120 s pending takeover.
  - **Bounds:** a generous token length bound; bounded per-pass batches; a bounded history page size.

  `__post_init__` refuses any value that is not a finite positive integer. `reference()` returns `{policyId, revision}`. `SYNTHETIC_EXPORT` composes only the fake Notion. `REAL_ACTIVATION_EXPORT` can be built only with an activation destination (32 lowercase hex) and a free-terms evidence reference, and it refuses values faster or larger than the documented free limits.
- [x] Add the dependency:
  - put `notion-client==3.1.0` in `[project].dependencies` of `backend/pyproject.toml`;
  - refresh `backend/uv.lock` with `uv lock --project backend`;
  - install with `uv sync --project backend --frozen --python 3.13.7`.
- [x] Create the backend test configuration:
  - `backend/pytest.u6-approved-export.ini`: U5's settings, with `testpaths = ../tests/u6_approved_export`;
  - `backend/.coveragerc.u6`: the cicd §2.5 include list plus `backend/u3_host.py` (decision "Coverage scope"), `fail_under = 80`, the runner excluded;
  - `tests/u6_approved_export/__init__.py`;
  - `tests/u6_approved_export/conftest.py`: a session `realm` loaded from `DOCSURI_U6_ENVIRONMENT_FILE` (asserting realm `approved-export` and database `docsuri_u6`); `transactions`; `connect(owner)`; and `authority` and `authority_b` as in U5's conftest, capped at 20 accounts.

  Layer folders arrive with their first test files. They carry no `__init__.py`, and test-file basenames stay unique across layers.
- [x] Create the frontend lane configuration:
  - `frontend/tsconfig.u6-export.json`: U5's stricter flags; includes `src/**`, `test/setup.ts`, `test/u6-export/**`, `e2e/u6-approved-export/**` and both U6 configs;
  - `frontend/vitest.u6-export.config.ts`: jsdom; `test/u6-export/**/*.test.{ts,tsx}`; `passWithNoTests: false`; one worker; v8 coverage of `src/u6-export/**/*.{ts,tsx}` with a lines threshold of 80.
- [x] Register the U6 environment in rows 1–9 of the R-06 table, one value per site. Use ports 18099 and 15499, never 18069, which U4's tests keep unowned.
- [x] Create the runner core `scripts/verify_docsuri_u6.py`, mirroring U5's tool with U6's identity:
  - **Constants:**
    - `RUN = /tmp/docsuri-u6-run`, `UNIT = "u6-approved-export"`, `REALM = "approved-export"`, `DATABASE = "docsuri_u6"`;
    - `DATABASE_PORT = 15499`, `APPLICATION_PORT = 18099`;
    - `LABEL = "dev.docsuri.u6.run"`, `POLICY = "u6-synthetic-v1"`, `PHASE_SECONDS = 300`;
    - `OWNERS = frozenset(SCHEMAS) | {"research", "topics", "export"}`;
    - `MIGRATIONS = (*U5_MIGRATIONS,)` until Step 5.
  - **Helpers:** the runner lock `/tmp/.docsuri-u6-runner.lock`, and the manifest, resource, preflight, port and database-container helpers.
  - **`setup`:** also creates `export-keys/` at mode 0700 and checks it. It creates no key.
  - **`migrate`:** uses U6's own base install, which creates roles for the eleven owners and adds `export` to the logins granted `accounts.guard_session`.
  - **Test phases:** `database`, `repository`, `component`, `integration`, `operations` and `coverage`, with U5's supervision, JUnit checks and evidence records. Zero tests, a skip, an error or a failure fails the phase.
  - **Imports:** only identity-free helpers. `command`, `digest`, `Refused`, `headroom`, `IMAGE`, `GIB` and `LOCKS` come from `verify_docsuri_u1`; `stop` from `verify_docsuri_u3`; `SCHEMAS` and `amend` from `bootstrap_docsuri_u1`; `MIGRATIONS` from `verify_docsuri_u5`.
  - **Test paths:** every path a phase names must resolve to at least one file that `git ls-files --cached --others --exclude-standard` lists. That is the listing U5's source inventory uses (`scripts/verify_docsuri_u5.py:777–800`): a tracked file, or an untracked file that is not ignored. An ignored or empty folder, such as U5's untracked `runtime` folder, fails. In CI, where a fresh checkout holds only tracked files, this equals cicd §4.3's "tracked in git", and the reading is recorded in Step 28. U5's `runtime` path is not copied.
- Files:
  - module and policy: `backend/modules/export/__init__.py`, `backend/modules/export/errors.py`, `backend/u6_policy.py`;
  - dependency: `backend/pyproject.toml`, `backend/uv.lock`;
  - backend tests: `backend/pytest.u6-approved-export.ini`, `backend/.coveragerc.u6`, `tests/u6_approved_export/__init__.py`, `tests/u6_approved_export/conftest.py`;
  - frontend lane: `frontend/tsconfig.u6-export.json`, `frontend/vitest.u6-export.config.ts`;
  - runner: `scripts/verify_docsuri_u6.py`;
  - allowlists: `backend/local_profile.py`, `backend/transactions.py`, `backend/local_browser.py`, `backend/artifacts.py`, `backend/local_host.py`, `backend/modules/accounts/local_http.py`, `backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py`, `ops/src/docsuri_ops/local_transport.py`.
- Traces: NFR1.3, NFR3.2, NFR4.10, NFR6.1, NFR6.3; D2, D5, D15; R-06, R-08; cicd §1.2, §2.5, §4.1–§4.3.

### Step 2 — Verify the test runner and record the exact unit-scoped command

- [x] Run `backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini --collect-only -q tests/u6_approved_export`. Before any test exists it reports "no tests collected" (exit code 5) with no configuration error, which proves the strict ini and the conftest load. Record it as the unit-scoped command that is runnable before the first test step.
- [x] Run the U2 keyring regression of cicd-pipeline §2.4 against the unchanged keyring, and record the baseline. The infrastructure review measured 67 passed and 1 deselected; record what this run actually reports.
- [x] On a fresh environment run `setup` and then `migrate`. Confirm that:
  - `export-keys/` exists at 0700 and is empty;
  - `owner-credentials.json` names the eleven owners;
  - U5's migration chain was applied.
- [x] Run `corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u6-export.json --noEmit`. It must pass now.
- [x] Record in the unit test instructions: the tool's phase form, the direct pytest form for one layer, the shared contract commands, and the Vitest command.
- Files: none beyond Step 1.
- Traces: Testing Contract runner step; cicd §2.4, §3.1.

### Step 3 — Data model (wire contract): C09 amendments — implement

- [x] In the canonical source, add the amendments to the shared-schema `$defs` and, for public defs, to the openapi `components.schemas`.
  - **Versions.** Raise C09's `version` from 2.0.0 to 2.1.0, and the release (`info.version` of the application openapi block, read by `export_workspace_contract.py`) from 3.0.0 to 3.1.0. The approved design ships these amendments as an additive minor release (tech-stack-decisions "Contract changes"; logical-components §1; cicd §1.1). The per-contract step follows commit `83239304`, which raised C14 from 2.1.0 to 2.2.0 for an additive change. Nothing pins 3.0.0 except the two generated schemas' `$comment` lines, which regeneration rewrites.
  - **Frozen shapes.** Every frozen property keeps its name, type and requiredness, with exactly two named deviations:
    1. A7 changes `connectionId` from required to optional on `ExportConnectionReadHttp` and on its internal variant `ExportConnectionRead`, the request of read, listDestinations and disconnect. The canonical source defines each separately, so both are edited.
    2. A1 changes `ExportDestinations.destinations` items and `ExportPreview.destination` from `ExportDestination` to `ExportDestinationEntry`. That def keeps every frozen `ExportDestination` field with its type and requiredness, and adds required `destinationId` and `title`.
  - **A1.**
    - The request-side `ExportDestination` gains optional `destinationId`, `title` and `context`.
    - A new public def, `ExportDestinationEntry`, carries the frozen fields plus required `destinationId` and `title`, an optional `context`, and the S2 optional fields `readable`, `creationCapability` and `writable`.
    - `ExportDestinationEntry` becomes the item type of `ExportDestinations.destinations` and the type of `ExportPreview.destination`.
    - `ExportDestinations` gains optional `listingComplete` and `lastDestinationId` (S2).
  - **A2.** A new operation `listExportHistory` at `POST /api/v2/c09/list-export-history`.
    - Request `ExportHistoryListHttp`: `limit` from 1 to 20; `cursor`, an opaque string or null.
    - Response `ExportHistoryPage`: `entries` and `nextCursor`, a string or null.
    - Each `ExportHistoryEntry` carries:
      - the approval state, an optional `invalidationReason`, and timestamps;
      - `sourceTitle` and `destinationTitle`;
      - `approvalId`, `previewId`, `previewRevision` and `bindingHash`;
      - `continuable`;
      - when an effect is bound, an effect summary: `effectId`, state, revision, optional `remoteUrl`, `outcomeReason`, `settledBy` and `nextCheckAt`, a bounded `possibleDuplicates`, and `settlementOffered`.
    - Errors: the six base codes.
  - **A3.** A new operation `settleExportEffect` at `POST /api/v2/c09/settle-export-effect`.
    - Request `ExportSettleHttp`: `effectId`, `expectedRevision`, `disposition` (`delivered` or `not-delivered`), `assumptionAccepted` (const true), and an optional `remoteUrl`.
    - Response: `ExportEffect`.
    - Errors: the base codes plus CONFLICT and IDEMPOTENCY_CONFLICT.
  - **Both new operations** get internal variants carrying `context`, the X-CSRF-Token and Idempotency-Key headers, and the standard responses, as the frozen operations do.
  - **A4.** `ExportEffect` gains optional `outcomeReason` (the 18 values in entities.md), `settledBy`, `nextCheckAt` and `settlementOffered`.
  - **A5.** `ExportPreview` gains an optional bounded `earlierExports`, plus optional `marker` and `sourceTitle`.
  - **A6 and its extension:**
    - `ProviderNotionInspection` adds `workspaceName`, the integration identity, and per destination optional `readable` and `creationCapability`;
    - `ProviderNotionRequest` adds `contentHash` and `marker`;
    - the write result adds Notion's request id and a refusal class, and `retry_later` adds the stated wait in seconds;
    - `ProviderEffectReconcile` adds `marker`, the destination, the first attempt's start and the writer identity;
    - the scan evidence adds a scan-complete flag. Marker found maps to committed; every other result maps to unknown, never to definitely-not-committed.
  - **A7.** `connectionId` becomes optional as in deviation 1. `ExportConnection` gains an optional `workspaceName`. `destinationScopeIds` holds the activation destination in the real composition and is empty otherwise.
  - **A9.** `ExportApproval` gains an optional `invalidationReason` (the five values).
  - **A10.** Cancel's semantics: `expectedRevision` is the preview revision for an unconsumed approval and the effect revision for an accepted effect, and cancel returns the approval.
  - The semantics text also records, for approval at the U6 checkpoint, the hash rule (decision "Hashes") and A6's reading of "currently permitted destinations".
- [x] Use only keyword forms the canonical schema already uses: no object-valued `additionalProperties` and no tuple `items`. That keeps U4's schema test helper type-checking.
- [x] Regenerate the derived files:
  1. `shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py`;
  2. with `shared/python/.venv/bin` on PATH, `shared/python/.venv/bin/python shared/python/tools/generate.py`;
  3. `corepack pnpm@9.15.9 --dir frontend run gen:types`.

  Both consumer inventories are refreshed later, in Step 27, after every other edit.
- Files:
  - canonical contract source (not application code): `aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`;
  - generated schemas: `shared/dtos/workspace.schema.json`, `shared/events/execution.schema.json`;
  - generated Python binding: `shared/python/src/docsuri_shared/_binding_generations/<new generation>/`, `shared/python/src/docsuri_shared/_binding_head.json`;
  - generated wire types: `frontend/types/wire/dtos.ts`.
- Traces: A1–A7, A6 extension, A9, A10; FR2.1–FR2.5; BR1.3, BR1.5, BR2.5, BR3.6, BR4.5, BR4.7; NFR4.2.

### Step 4 — Data model (wire contract): write and run its tests

- [x] Write `shared/python/tests/test_export_contract.py`. Give it a one-line docstring naming the property, register validators by `$id`, and use Draft 2020-12. It checks that:
  - every frozen C09 def keeps each frozen property's name, type and requiredness, against expectations written into the test from the release before the amendment, with exactly the two named exceptions of Step 3:
    - `connectionId` is optional on both `ExportConnectionReadHttp` and `ExportConnectionRead`;
    - `ExportDestinations.destinations` items and `ExportPreview.destination` name `ExportDestinationEntry`, and that def holds every frozen `ExportDestination` field with its frozen type and requiredness, plus required `destinationId` and `title`;
  - new request properties are optional, and new response properties are optional except `destinationId` and `title` on `ExportDestinationEntry`;
  - `ExportConnection.state` is exactly `connected`, `disconnected`, `revoked`, `unavailable`, with no `pending` (cicd §8.1);
  - both new operations exist, with both required headers and their error lists;
  - the regenerated schemas name release 3.1.0 in their `$comment`;
  - every new def round-trips through its generated model: `model_validate`, then `model_dump(mode="json", by_alias=True, exclude_unset=True)` equals the input;
  - negative mutations are rejected: an extra field, an unknown enum value, a missing required field;
  - every case in `shared/export-hash-vectors.json` recomputes from the canonical rules: the `renderedContentHash` cases in U4's `digest` form, and the `bindingHash` cases as the frozen prefix plus JCS.
- [x] Write `shared/export-hash-vectors.json`: the golden byte vectors for both hashes (input value, canonical bytes as hex, expected SHA-256), read later by the backend rendering test and the fake Notion's test (decision "Hashes").
- [x] Run, and require all green:
  - the export drift check, `--check`;
  - the binding drift check, `--check`;
  - the shared suite, from working directory `shared/python`: `.venv/bin/python -m pytest -o addopts='' -q --tb=short`;
  - `corepack pnpm@9.15.9 --dir frontend run check:types`;
  - `corepack pnpm@9.15.9 --dir frontend run test:contracts`;
  - U4's type lane, `corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u4-research.json --noEmit`.
- Files: `shared/python/tests/test_export_contract.py`, `shared/export-hash-vectors.json`.
- Traces: same as Step 3; cicd §2.2 (shared-contracts), §8.1 (frozen states).

### Step 5 — Data model (database): schema `export` and the A8 guard — implement

These migrations follow U5's SQL idioms:

- schema-qualified names;
- `CHECK (… IN (…))` enums, and `octet_length` bounds on text;
- `timestamptz` defaults from `clock_timestamp()`;
- trigger functions with `SET search_path = pg_catalog` that raise ERRCODE 23514;
- definer functions with `SET search_path = pg_catalog`.

Each file is applied as the owner of the schema it changes, append-only.

- [x] `backend/modules/accounts/u6_lifecycle_guard.sql`, applied as `docsuri_accounts_owner`:
  - replace `accounts.guard_lifecycle_effect` with the same mapping plus `ApprovedExport` → `docsuri_export`;
  - keep `REVOKE ALL … FROM PUBLIC`;
  - grant EXECUTE on the guard to `docsuri_export`;
  - grant USAGE on schema `accounts` and EXECUTE on `accounts.lifecycle_effect_action` to `docsuri_export` and `docsuri_export_owner`, as `u5_lifecycle_guard.sql` does for the topics roles.
- [x] `backend/modules/export/u6_schema.sql`, applied as `docsuri_export_owner`. Tables:
  - **`export.connection`:**
    - columns: `id uuid PRIMARY KEY`, `account_id uuid NOT NULL UNIQUE`, `revision`, `provider` (`notion`), `state`, `pending_holder`, `pending_started_at`, `sealed_token bytea`, `token_key_version` (`^u6-[0-9a-f]{32}$`), `validated_at`, bounded `workspace_name`, `workspace_id` and `connection_user_id`, `creation_capability` (`unknown`, `confirmed` or `refused`, default `unknown`), `last_destination_id` (32 hex), `limitations jsonb` (an array), and timestamps;
    - the R-01 checks;
    - `CHECK ((state IN ('connected','unavailable')) = (sealed_token IS NOT NULL))`;
    - `CHECK ((sealed_token IS NULL) = (token_key_version IS NULL))`;
    - a check that the envelope starts with `DSE1` and carries `token_key_version` as its version field.
  - **`export.connection_pace`:** `connection_id uuid PRIMARY KEY REFERENCES export.connection ON DELETE CASCADE`, `next_slot_at timestamptz NOT NULL`.
  - **`export.preview_pair`:** `preview_id` primary key; `account_id`, `artifact_id`, `destination_id`; `current_revision`; `UNIQUE (account_id, artifact_id, destination_id)`.
  - **`export.preview_revision`:**
    - keys: `preview_id` cascading from the pair, `revision > 0`, primary key `(preview_id, revision)`;
    - source and binding facts: the source revision and content hash, `source_eligibility_revision`, `source_title`, `connection_id`, `connection_revision`, a `destination` snapshot, `render_policy`;
    - rendered facts: `marker` (UNIQUE), `rendered_blocks`, `rendered_text`, `rendered_content_hash` and `binding_hash` (64 hex), `earlier_exports`;
    - timestamps: `prepared_at`, `trimmed_at`;
    - a check that `rendered_blocks`, `rendered_text` and `trimmed_at` stay consistent: the two rendered columns are present together, and exactly when `trimmed_at` is null.
  - **`export.approval`:**
    - the approval id; `account_id`; a foreign key on `(preview_id, preview_revision)` to `export.preview_revision`, also `UNIQUE` and deliberately not cascading; `binding_hash`; `policy`; `approved_at`;
    - `expires_at` with `CHECK (expires_at IS NULL)`;
    - `state IN ('approved','consumed','cancelled','invalidated')`. The frozen `expired` is never entered (BR3.5);
    - `invalidation_reason` (the five values), with `CHECK ((state = 'invalidated') = (invalidation_reason IS NOT NULL))`;
    - `approving_session`; `request_key` with `UNIQUE (account_id, request_key)`.
  - **`export.effect`:**
    - identity and binding: the effect id; `approval_id` (UNIQUE, `ON DELETE CASCADE`); `account_id`; the export pair (`artifact_id`, `destination_id`); `revision`; `binding_hash`; `state` (the seven values); `marker` (UNIQUE); `request_key` with `UNIQUE (account_id, request_key)`;
    - timing: `waiting_since`, `next_attempt_at`, `rate_limit_started_at`, `next_check_at`, `scanning_stopped_at`, and `ended_at`, with `CHECK ((state IN ('succeeded','failed','cancelled','invalidated')) = (ended_at IS NOT NULL))`;
    - outcome: `remote_reference`, `remote_url`, `reconciliation_evidence_hash`, `outcome_reason` (the 18 values), `settled_by`, a bounded `owner_assumption`, `limitations`;
    - `CREATE UNIQUE INDEX effect_in_flight ON export.effect (account_id) WHERE state IN ('accepted','executing')` (BR5.1);
    - checks that `remote_reference` exists only when succeeded, and that failed, invalidated and cancelled effects carry a reason.
  - **`export.attempt`:**
    - columns: the attempt id; `effect_id REFERENCES export.effect ON DELETE CASCADE`; `attempt_number` with `UNIQUE (effect_id, attempt_number)`; `started_at`, `deadline_at`; `writer_identity`; `connection_revision`; `ended_at`; `response_class` (four values); `provider_request_id`; `path_kind` (`synthetic` or `real`); `creator_confirmed`;
    - `CHECK ((response_class IS NULL) = (ended_at IS NULL))`;
    - a partial unique index allowing one outstanding attempt per effect.
  - **`export.reconciliation_check`:** the check id, `effect_id REFERENCES export.effect ON DELETE CASCADE`, `checked_at`, `window_start`, `result` (four values), `remote_reference`, a bounded `other_marked_pages`, `evidence_hash`.
  - **`export.replay_record`:** `(account_id, operation IN ('configure','settle'), operation_key)` as the primary key; `input_hash`; `response`.
  - **`export.lifecycle_evidence`:** exactly the columns that `apply_owner_effect` writes.
  - **`export.lifecycle_counts`:** keyed by `(request_id, scope)`, with action, reason key and numbers only. It has no account column, so it survives erasure as count-only evidence.
  - **`export.lane_status`:** a singleton holding the last outcome category and its time.
- [x] Triggers in `u6_schema.sql`:
  - **Connection update:**
    - identity is immutable and the revision never decreases;
    - pending → connected sets revision 1;
    - replace, reconnect, disconnect, revocation and withdrawal each advance the revision by exactly one, and a replace or reconnect resets `creation_capability` to `unknown` in the same update;
    - connected ↔ unavailable keeps the revision (BR1.6);
    - `creation_capability` and `last_destination_id` may change at an unchanged revision (decision "Connection facts from outcomes");
    - an operator re-seal changes only the envelope and the key version;
    - holder fields change only while the row is pending.
  - **Preview revision:** immutable except for one trim, which clears the rendered tree and text and sets `trimmed_at` (D12).
  - **Approval update:** the binding is immutable; only approved → consumed, cancelled or invalidated is allowed; terminal rows are frozen.
  - **Effect update:**
    - transitions follow the ExportEffect state machine exactly: unknown never goes to executing, and failed never goes back to accepted;
    - the revision advances by one on every update, and `ended_at` is set once, on the transition to a terminal state;
    - terminal rows are frozen;
    - a deferred constraint trigger refuses a commit that leaves an executing effect without an attempt (NFR4.8).
  - **Attempt:** an insert is allowed only while the effect is executing, with consecutive numbers, and only after a rate-limited attempt. Outcome facts are set once.
  - **Check:** checks are insert-only.
- [x] Grants at the end of `u6_schema.sql`:
  - `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC`;
  - then `GRANT SELECT, INSERT, UPDATE` to `docsuri_export` on every export table except `export.connection`;
  - column-level SELECT, INSERT and UPDATE on every column of `export.connection` except `sealed_token` and `token_key_version`;
  - no DELETE on any table (D13).
- [x] `backend/modules/export/u6_custody.sql`. Every function here is SECURITY DEFINER.
  - **`export.store_token_envelope(…)`:** for a first configure, writes only while the owner's row is pending and held by this check, moving revision 0 to 1 (R-02). For a replace or reconnect, writes only at the expected revision, moving it up by one. Sets connected, the workspace facts and `validated_at`, and resets the creation capability to unknown. Returns the new revision, or NULL.
  - **`export.open_token_envelope(p_account, p_connection)`:** returns the envelope, revision, key version and state, and only for that owner's connected or unavailable row.
  - **`export.clear_token_envelope(p_account, p_connection, p_expected_revision, p_next_state)`:** sets disconnected or revoked, advances the revision by one and clears the envelope. Returns NULL if the revision moved.
  - **`export.token_key_counts()`:** one row per key version with its count of sealed tokens, and no identifiers.
  - **Operator-only `export.token_envelopes_for_reseal(p_version, p_limit)` and `export.reseal_token(p_connection, p_expected_envelope_sha256, p_new_envelope, p_new_version)`:** the re-seal is a compare-and-set on the current envelope's digest, and keeps the revision.
  - **At the end:** `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC`; then EXECUTE for `docsuri_export` on the three envelope functions and `token_key_counts`; nothing on the operator functions.
- [x] `backend/modules/export/u6_maintenance.sql`. Every function here is SECURITY DEFINER.
  - **`export.release_pending(p_account, p_holder)` and `export.sweep_stale_pending(p_now, p_older_than_seconds, p_limit)`:** holder compare-and-set deletes (R-02).
  - **`export.purge_unapproved_previews(p_now, p_retention_days, p_limit)`:** removes revisions that were never approved and are past retention, and an empty pair. The non-cascading approval foreign key means it can never remove an approved revision.
  - **`export.lifecycle_release_pending(…)` and `export.erase_account_records(…)`:** each refuses with 42501 unless `accounts.lifecycle_effect_action(…, 'ApprovedExport', …)` returns the matching action, as `topics.erase_private_controls` does. Erase deletes, in this order, the account's approvals (cascading to effects, then attempts and reconciliation checks), its preview pairs (cascading to revisions), its replay records, and its connection (cascading to its pace row).
  - **`export.status_counts(p_now)`:** counts and ages only (logical-components §8).
  - **At the end:** `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC`; then EXECUTE on these functions for `docsuri_export`.
- [x] Append to `MIGRATIONS`, in this order:
  1. `("accounts", "backend/modules/accounts/u6_lifecycle_guard.sql")`;
  2. `("export", "backend/modules/export/u6_schema.sql")`;
  3. `("export", "backend/modules/export/u6_custody.sql")`;
  4. `("export", "backend/modules/export/u6_maintenance.sql")`.
- Files: `backend/modules/accounts/u6_lifecycle_guard.sql`, `backend/modules/export/u6_schema.sql`, `backend/modules/export/u6_custody.sql`, `backend/modules/export/u6_maintenance.sql`, `scripts/verify_docsuri_u6.py`.
- Traces: FR2.1, FR2.3–FR2.5; BR1.3–BR1.6, BR2.3, BR2.6, BR3.1, BR3.2, BR3.5, BR4.1–BR4.3, BR4.6, BR5.1, BR6.2, BR7.2; NFR1.4, NFR3.4, NFR3.7, NFR4.1, NFR4.8; D6, D12, D13; A8; R-01, R-02.

### Step 6 — Data model (database): write and run its tests

- [x] `tests/u6_approved_export/database/test_export_schema.py`:
  - the R-01 checks: pending ⇔ revision 0; a pending row holds no envelope; an envelope exists exactly while connected or unavailable; the envelope's version field equals the column;
  - connection transitions outside the state machine are refused;
  - `creation_capability` and `last_destination_id` change at an unchanged revision, and a replace resets the capability to unknown;
  - a preview revision is immutable except for one trim;
  - one approval per preview revision; never `expired`; `expires_at` always null;
  - effect transitions follow the state machine and unknown never goes to executing; `ended_at` is set exactly when the effect is terminal;
  - one in-flight effect per owner, and a unique marker;
  - a commit that leaves an executing effect without an attempt is refused;
  - attempt numbering is consecutive and attempt facts are set once;
  - reconciliation checks are insert-only.
- [x] `tests/u6_approved_export/database/test_export_grants.py`:
  - D13 and R-07: no SELECT, INSERT, UPDATE or REFERENCES for `docsuri_export` on the two envelope columns;
  - the two operator functions are not executable by `docsuri_export`;
  - PUBLIC can execute no function in schema `export`;
  - `docsuri_export` has no DELETE on any export table (InsufficientPrivilege);
  - `docsuri_export` can run `accounts.guard_session` and `accounts.guard_lifecycle_effect`;
  - the lifecycle guard refuses `ApprovedExport` under another login role, for example `docsuri_topics`, with 42501;
  - another owner's login cannot read export tables.
- [x] `tests/u6_approved_export/database/test_export_functions.py`:
  - the store function writes a first configure only while the row is pending and held, and a replace only at the expected revision;
  - the clear function is a compare-and-set;
  - `release_pending` and `sweep_stale_pending` are compare-and-sets on the holder;
  - the purge touches only unapproved, expired revisions, and never a revision that has an approval;
  - erase refuses without an erase ticket; with a valid erase ticket it removes every export row of the account, reconciliation checks included, keeps another account's rows and leaves the count-only evidence;
  - the re-seal compare-and-set keeps the revision;
  - `token_key_counts` and `status_counts` carry no identifiers.
- [x] Run `--phase database`.
- Files: the three test files above.
- Traces: same as Step 5; cicd §3.2 rows "Token exposure (D13)" and "Grants in the accounts schema"; R-07.

### Step 7 — Repository: ExportStore — implement

- [x] `backend/modules/export/repository.py` defines `ExportRepository(transactions)`, shaped like `TopicsRepository`:
  - `run(authority, action)` runs `transactions.guard` with purpose `local-research`, then the owner unit, inside `transactions.run("export", …)`;
  - `system(action)` runs worker and lane units.

  Rules for every unit:
  - closures can be re-run (serializable retries) and never call Notion;
  - argument checks before the transaction raise `ExportError("INVALID_ARGUMENT", current={"field": …})`;
  - savepoints translate `UniqueViolation` and `CheckViolation`;
  - a foreign record and an absent one raise the same `LookupError`;
  - worker units return `None` when the record moved on.
- [x] Owner units, connection:
  - read the owner's connection; pending and absent both read as not connected;
  - reserve a first-configure pending row with its pace row; take over a stale one; or lock an existing row at the expected revision. CONFLICT otherwise, while a fresh pending row exists (R-03), or from `unavailable`;
  - store the configured envelope through `export.store_token_envelope`. In the same transaction, invalidate approved approvals and accepted effects bound to older revisions (connection-changed), and write the configure replay record;
  - release a pending row by its holder;
  - disconnect through `export.clear_token_envelope`, with the same invalidation.
- [x] Owner units, previews and approvals:
  - **previews:** lock the pair; add the next revision with its frozen tree, text, hashes, marker and earlier-export summaries;
  - **approvals:** check for a replay (by request key, or by the preview revision) before anything else; record only on the pair's current revision, and only if no export of the pair succeeded after that revision was prepared (decision "Newer succeeded export").
- [x] Owner units, effects:
  - check for a replay (by request key, or by the approval's existing effect) before anything else;
  - bind in one guarded statement that also consumes the approval;
  - the bind refuses:
    - with CAPACITY_EXHAUSTED when another export is in flight (the partial index, caught as UniqueViolation);
    - with OUTCOME_UNKNOWN when an unknown effect exists for the pair;
    - with CAPACITY_EXHAUSTED and `retry_after` (the seconds until the oldest bind of the rolling hour leaves it) when 20 effects were bound in the rolling hour;
    - with CONFLICT when an export of the pair succeeded after this approval's preview revision was prepared.

    Each refusal leaves the approval approved;
  - cancel by compare-and-set on the preview revision or on the effect revision;
  - settle by compare-and-set on the effect revision, only while settlement is offered, with its replay record. A settlement as delivered also sets the connection's `last_destination_id`;
  - read an effect, and read a history page keyset-ordered by `(approved_at, approval_id)`.
- [x] Service units, run through `system`:
  - **Lane and pass units:**
    - due items, in security design §8.1's order, and the push of `next_check_at` at hand-over;
    - claim by compare-and-set, with the attempt insert in the same transaction (NFR4.8);
    - record attempt outcomes and effect transitions, setting `ended_at` on a terminal one, and mark waiting and could-not-check;
    - connection facts from outcomes: every success sets `last_destination_id`. A created page or a marker found sets `creation_capability = confirmed`, and a no-access refusal sets `refused`, each only while the connection is still at the attempt's connection revision. Neither changes the revision;
    - revocation by compare-and-set on the opened revision through `export.clear_token_envelope(…, 'revoked')`. In the same transaction, and only when that compare-and-set succeeds, approved approvals and accepted effects bound to an earlier revision become invalidated (connection-changed), an executing effect is left to finish and an unknown one stays unknown (D16, BR1.4). A discarded revocation changes nothing. Unavailability and recovery keep the revision (BR1.6);
    - reconciliation checks and orphan selection;
    - housekeeping batches: the session-ended and the source-changed invalidation, each with its trim in the same transaction; the trim of every revision that can no longer lead to a write (decision "Rendered copies"); the purge; the stale-pending sweep.
  - **Store wrappers:**
    - pace slot reservation: security design §9.2's statement, with the interval passed as a parameter;
    - `token_key_counts`, `open_token_envelope` and `status_counts`;
    - the lane status record.
- [x] Split files by concern before one nears 800 lines, for example worker and lane units into `backend/modules/export/lane_store.py`.
- Files: `backend/modules/export/repository.py` (and `lane_store.py` if split).
- Traces: FR2.1, FR2.3–FR2.5; BR1.3–BR1.6, BR2.5, BR2.6, BR3.1–BR3.4, BR3.6, BR4.2, BR4.5, BR5.1, BR5.2, BR7.1; A2, A3; NFR1.1, NFR1.5, NFR3.7, NFR4.1, NFR4.6, NFR4.8, NFR4.11, NFR6.4; D4, D6, D8, D16; R-02, R-03.

### Step 8 — Repository: write and run its tests

- [x] `tests/u6_approved_export/repository/test_connection_store.py`:
  - a first-configure reservation creates the pending row and its pace row;
  - a fresh pending row refuses a second configure with CONFLICT;
  - takeover works once the takeover time has passed, using a passed `now`;
  - R-02: a check whose row was taken over or deleted stores nothing and deletes nothing, and the new holder's row and pace row stay intact;
  - BR1.3: the expected-revision compare-and-set;
  - configure from `unavailable` is refused;
  - D16: a revocation by compare-and-set on the opened revision is discarded after a replace, and changes nothing;
  - a successful revocation clears the envelope, sets revoked, advances the revision and, in the same transaction, invalidates approved approvals and accepted effects (connection-changed), while an executing effect keeps executing and an unknown one stays unknown;
  - disconnect runs the same invalidation;
  - BR1.6: unavailable and available keep the revision;
  - foreign records give the same not-found as absent ones.
- [x] `tests/u6_approved_export/repository/test_replay_records.py` (security design §3):
  - the configure replay record holds no token, no token digest and no salted digest. Its input hash equals the digest of the request without the token field, and its response holds only identifiers, state, revision or a code;
  - a replay returns the original;
  - a different expected revision under the same key is IDEMPOTENCY_CONFLICT;
  - a different token under the same key returns the original.
- [x] `tests/u6_approved_export/repository/test_preview_store.py`:
  - each preparation adds the next revision; there is one previewId per pair;
  - earlier-export summaries are frozen at preparation;
  - a trim keeps the summary.
- [x] `tests/u6_approved_export/repository/test_approval_effect_store.py`:
  - approval replay works by key and by preview revision; a changed payload is IDEMPOTENCY_CONFLICT;
  - an approval is refused with CONFLICT when an export of the pair succeeded after the revision was prepared;
  - binding consumes the approval atomically;
  - the in-flight, unknown-pair, 20-per-hour and newer-succeeded refusals each leave the approval unconsumed; continuing an older approval after a newer export of the same pair succeeded is refused with CONFLICT;
  - the 20-per-hour refusal carries `retry_after`;
  - cancel's two compare-and-sets work, and settle's compare-and-set works; a settlement as delivered sets `last_destination_id`.
- [x] `tests/u6_approved_export/repository/test_lane_store.py`:
  - due items come in order;
  - the claim and its attempt land in one transaction;
  - the claim is refused when the connection revision moved, when the session ended, or when the owner already has an export executing;
  - outcomes are recorded, and a terminal transition sets `ended_at`; orphans are selected; `next_check_at` is pushed at hand-over;
  - on created, `last_destination_id` names the bound destination and `creation_capability` becomes confirmed; on no-access it becomes refused; neither changes the connection revision; an outcome recorded after a replace leaves the new connection's capability unknown.
- [x] `tests/u6_approved_export/repository/test_housekeeping_store.py`:
  - an approval whose session ended is invalidated and trimmed in one transaction, and a source-changed invalidation trims in its own transaction;
  - the revision of a cancelled approval, of an approval invalidated by a connection change, and a superseded never-approved revision are trimmed;
  - a revision whose approval is approved and unconsumed, or whose effect is accepted, executing or unknown, keeps its tree, and so does the current never-approved revision;
  - unapproved previews are purged after 7 days;
  - stale pending rows are swept by compare-and-set.
- [x] `tests/u6_approved_export/repository/test_pace_store.py`:
  - two transaction pools on one connection get slots at least 500 ms apart on the database clock;
  - a slot beyond the remaining budget is reported, and left used;
  - a busy reservation reports could-not-check.
- [x] Run `--phase repository`.
- Files: the seven test files above.
- Traces: same as Step 7; cicd §3.2 row "configure replay record"; cicd §8.1 rows "store only while pending and held"; R-02.

### Step 9 — Business logic: key custody, token vault and key commands — implement

- [x] `backend/key_custody.py` holds the shared helper (D1). It contains only mechanics the built keyring already has:
  - the guarded read;
  - the non-blocking exclusive lock;
  - the staged write;
  - publishing by atomic replace, with a folder sync;
  - exclusive creation of the marker.

  It is configured by a frozen `CustodySettings`: folder, file names, staging prefix, version pattern, `generation` range, at most three versions, a 4096-byte size, and the exception type and messages to raise. It offers no first key, no re-sealing and no retirement.
- [x] `backend/modules/accounts/control_keys.py` becomes a thin setting of the helper, with exactly today's behaviour:
  - U2's configuration stays at class level;
  - `root`, `run_id` and `legacy_key` remain the only state of each instance, so `ControlKeyring.__new__` still works;
  - `_lock`, `read`, `_write`, `key`, `active_version` and `rotate` keep their names and behaviour;
  - the read path creates no files;
  - rotation writes the marker before calling `_write` once;
  - `PolicyUnavailable` and its messages, the version pattern `u2-(v1|<32 hex>)` and the generation range of 1 to 3 all stay.
- [x] `backend/modules/export/token_keyring.py` defines `TokenKeyring(root, run_id, store)` and owns the R-05 constants.
  - **Folder check:** at every load, the key folder passes the check of decision "Key folder custody" (a directory, not a symbolic link, owned by `os.getuid()`, no group or other permission bits), or the load raises `ProtectionUnavailable` and creates nothing.
  - **Versions:** `u6-<32 hex>`, with a generation from 1 to 2,147,483,647.
  - **First key:** published by linking a synced staging file into place. The loser of a race reads the winner's file, and the staging name is always removed.
  - **Order:** the key file first, then the marker. A missing marker is repaired.
  - **Waiting lock:** retries every 100 ms for up to 5 s, then fails closed as protection unavailable.
  - **Cleanup:** leftover staging files are removed under the lock at the next creation or rotation.
  - **No cache:** every read goes to the file.
  - **Decisions:** the §4.4 table, with `store.token_key_counts()` as the second witness. A failed count means protection unavailable (R-16).
  - **Operations:** rotation and retirement, as security design §4.5 and cicd §4.5 describe.
- [x] `backend/modules/export/token_vault.py`:
  - seals and opens the envelope `DSE1 | len(version) | version | nonce (12) | AES-256-GCM(token)`;
  - AAD is `u6-notion-token:<version>:<accountId>:<connectionId>:<connectionRevision>`;
  - a fresh nonce from the operating system's random source on every seal;
  - every fault raises `ProtectionUnavailable` with no secret text.
- [x] `backend/modules/export/key_commands.py` holds the operator commands. They act through an administrative connection that has done `SET ROLE docsuri_export_owner` and call only the three functions of §4.5. Every command runs the key-folder check first and prints counts only.
  - **`create_key_after_loss`:** refuses unless the state is loss; creates the marker only if it is absent; reports tokens left under missing versions.
  - **`rotate_key`:** with three versions present, first retires the oldest, but only at a count of zero; then adds a new version and re-seals row by row through `export.reseal_token`. Tokens under a missing version are skipped and reported.
  - **`retire_key(version)`:** refuses for the active version or for a count above zero.
  - **`key_counts`:** prints the count per key version.
- Files: `backend/key_custody.py`, `backend/modules/accounts/control_keys.py`, `backend/modules/export/token_keyring.py`, `backend/modules/export/token_vault.py`, `backend/modules/export/key_commands.py`.
- Traces: FR2.1; BR1.1, BR1.6, BR8.3; NFR3.1–NFR3.3, NFR3.7; D1–D3, D13; R-05, R-16.

### Step 10 — Business logic: key custody — write and run its tests

- [x] Run U2's keyring regression (cicd §2.4). It must pass unchanged, including the recovery module building a keyring through `ControlKeyring.__new__`.
- [x] `tests/u6_approved_export/operations/test_key_custody.py`:
  - every guarded-read refusal: symlink, owner, mode, size, duplicate field, run id, version pattern, generation range;
  - the non-blocking lock refusal;
  - staged write, publish and folder sync;
  - exclusive creation of the marker;
  - the read path creates nothing.
- [x] `tests/u6_approved_export/operations/test_control_keys_parity.py` runs U2's setting through the helper, using `__new__` over temporary folders:
  - the legacy in-memory record;
  - rotation up to three keys, then refusal;
  - the marker written before the key file;
  - the generation range of 1 to 3, and U2's exception types.

  These are the measured coverage of `control_keys.py` in U6's floor.
- [x] `tests/u6_approved_export/operations/test_token_keyring.py`:
  - two processes starting together create one key, and it keeps a single link;
  - every row of the §4.4 table gives its result;
  - a deleted key folder with sealed tokens left gives unavailable and creates no key (D3);
  - a failing count gives unavailable and creates no key (R-16);
  - a symbolic link in place of the key folder, a folder owned by another user (simulated by patching the uid the check compares against), and a folder at 0750 or 0777 each give protection unavailable and create nothing;
  - a missing marker is repaired;
  - the waiting lock gives up as protection unavailable;
  - leftover staging files are cleaned up;
  - rotate and retire, repeated more than three times, still leave a file that reads, with the generation past 3 while U2's range stays 1 to 3.
- [x] `tests/u6_approved_export/operations/test_token_vault.py`:
  - seal and open round-trip;
  - an envelope copied to another account, connection or revision fails to open;
  - every seal gets a fresh nonce;
  - the version column equals the envelope's version;
  - the next open sees a rotation;
  - faults carry no secret text.
- [x] `tests/u6_approved_export/operations/test_key_commands.py`:
  - rotation re-seals by compare-and-set and reports counts;
  - with three versions and a token under the oldest, rotation refuses and shows the counts;
  - retirement refuses for a count above zero, and for the active version;
  - after a loss, rotation skips and reports tokens under the missing version;
  - `create-key-after-loss` refuses unless the state is loss;
  - a command refuses when the key-folder check fails;
  - output holds counts only;
  - the commands run through the administrative path as `docsuri_export_owner`.
- [x] Run the U2 regression and `--phase operations`.
- Files: the five test files above.
- Traces: same as Step 9; security design §4.3 and §13 "Key custody"; cicd §3.2 key custody rows.

### Step 11 — Business logic: render policy and hashes — implement

- [x] `backend/modules/export/rendering.py` holds pure functions only:
  - **`derive_title`:** the summary's first sentence, cut at a word boundary near 60 characters, prefixed `신규성 분석 — `. The fallback is `신규성 분석 결과` plus the artifact's short identifier.
  - **`marker_for(preview_id, revision)`:** `docsuri-export:v1:<previewId as 32 hex>:<revision>`, with no personal data.
  - **`build_page_body`:** returns `{"properties": {"title": …}, "children": […]}`. The children are, in order: the summary, assessments, evidence items (each one top-level block with its quote, claim and source nested under it), coverage, limitations, method, and the marker as the last top-level block.
  - **Text runs:** plain text only, never markup, at most 2,000 characters each, split at sentence or word boundaries.
  - **`check_limits`:** at most 100 top-level blocks and 100 items in any list; at most two nested levels below a top-level block; at most 1,000 blocks and 500 KB. A breach returns a plain refusal category, and the content is never truncated.
  - **`project_text`:** the read-only `renderedText`, with the marker line last.
  - **`content_hash`:** U4's `digest` form over the page body.
  - **`binding_hash`:** the frozen prefix plus JCS, over the identity fields (decision "Hashes").
- Files: `backend/modules/export/rendering.py`.
- Traces: FR2.2, FR2.3; BR2.3, BR2.4, BR4.1; NFR4.2; D12.

### Step 12 — Business logic: render policy — write and run its tests

- [x] `tests/u6_approved_export/component/test_rendering.py`:
  - both hashes match every case in `shared/export-hash-vectors.json`;
  - `content_hash` equals `backend.modules.research.repository.digest` on the same value;
  - the title is cut, prefixed and falls back correctly: empty summary, Korean text, long words;
  - blocks come in order, with the marker last;
  - every limit refuses at its bound and accepts just below it;
  - text splits at boundaries;
  - rendering is deterministic;
  - U4's maximum result (32 KB, 32 evidence items) fits.
- [x] Run `--phase component`.
- Files: `tests/u6_approved_export/component/test_rendering.py`.
- Traces: same as Step 11.

### Step 13 — Business logic: Notion boundary — implement

- [x] `backend/modules/export/notion_session.py`:
  - **`network_transport()`:** the single place that builds the network transport. It is called once per operation, and callers reach it only as a module attribute.
  - **`GuardedTransport`:**
    - pins requests to `https://api.notion.com:443`;
    - repeats the path identifier check;
    - streams every body and aborts past 2 MB (2,000,000 bytes, NFR4.10), or at once when the declared length is larger, with `ResponseTooLarge`;
    - adds no retries.
  - **`InteractiveGate`:** at most 2 operations per process and 1 per connection, refusing at once beyond either cap. A slot is released in a `finally` step on success, error or cancellation (D15).
  - **`NotionSession.run(target, budget, work, *, gate_key=None)`:**
    - the target is `StoredConnection` or `CandidateToken` (R-14);
    - a browser-driven operation passes its connection id as `gate_key`, and the gate slot is taken before anything else; a refusal returns the could-not-check category at once. The lane never passes a gate key (decision "Interactive gate");
    - opening the token and building both clients happen inside the reduced region;
    - one `httpx.AsyncClient(transport=GuardedTransport(…), follow_redirects=False, trust_env=False)` and one `notion_client.AsyncClient(client=…, auth=…, notion_version="2026-03-11", retry=False, timeout_ms=…, logger=SDK_LOGGER)` per operation;
    - the SDK client is never entered with `with` or `async with`;
    - the whole operation runs under `asyncio.timeout(budget)`;
    - only `Exception` is reduced to a fixed category; cancellation, `KeyboardInterrupt` and `SystemExit` pass through;
    - the result is a fixed category value. No exception object is stored on a record, result or attribute, logged or returned. A reduced error that must be raised is raised after the `except` block has ended, `from None`, so its `__cause__` and `__context__` are both None (decision "Error reduction");
    - `aclose` runs in a `finally` step;
    - the pace slot is reserved through the store on the target's connection id before every request, and the wait happens outside any transaction.
  - **Logging:** `SDK_LOGGER` is `docsuri.export.notion_sdk`, with a `NullHandler`, propagation off, at WARNING.
- [x] `backend/modules/export/classification.py` implements the write and read tables of security design §7 as pure functions:
  - the body's `code` comes from `json.loads(error.body)` for codes the SDK does not know, such as 529;
  - `block_limit` comes from `additional_data` or from the parsed body;
  - message text is never read.
- [x] `backend/modules/export/notion_adapter.py` provides these operations:
  - **`identify`:** candidate or stored token. It returns the workspace name, the integration identity and the workspace identifier for `ExportDestination.workspaceId`. Before coding, check against the 2026-03-11 API reference which field of the bot-user answer supplies that identifier, and pin it in the adapter tests.
  - **`list_destinations`:** a search for pages, paged manually with `page_size=100` and bounded. `listingComplete` is false when the pages or the retries run out. Each entry carries `destinationId`, `title` (absent for an untitled page), `context`, `readable` and `creationCapability` as far as known, and `writable`, which is false when the page is unreadable or the capability is refused. The operation also makes a direct read of `lastDestinationId`, inside the same gated operation.
  - **`read_destination`:** one page request and its first children request, which confirms the connection can read the page's children (BR1.5).
  - **Read retries:** every read follows decision "Read retries", with `ExportPolicy.read_retries`.
  - **`create_page`:**
    - takes the tree through the content port keyed by the effect;
    - before sending, recomputes the hash and checks that the marker is last and the parent is the bound destination. A mismatch sends nothing and is refused as content-rejected;
    - the request carries `contentHash` and `marker` (A6).
  - **`read_back`:** the three checks of BR4.2.
  - **`scan`:** pages manually and descends into every block that has children except child pages and child databases. Candidates are pages by the recorded writer identity, at or after the first attempt's start minute less the clock margin. It reads each candidate to its last top-level block, compares the marker, and ends in one of four results.
  - **Connection side effects:** a stored-token 401 calls the store's revocation unit (Step 7). That unit revokes by compare-and-set on the opened revision, and ends older pending work only when the compare-and-set succeeds (D16, BR1.4). Custody faults and recovery move between unavailable and connected (BR1.6).
  - **Boundary types:** the amended A6 execution models.
- [x] `backend/modules/export/fake_notion.py` defines `FakeNotion`, an `httpx.AsyncBaseTransport`:
  - **Scenarios:**
    - tokens mapped to bot identities;
    - page trees, including toggles and columns;
    - search listings that are complete, partial or unavailable;
    - create answers: created; 401; 404; 403 with and without `block_limit`; 400 `validation_error`; 429 blocked and unblocked with a stated wait; 529; 503 saved-but-busy with and without a page; 409, 500, 502 and 504;
    - timeouts after success, lost responses, over-cap answers, slow and hanging answers;
    - an expected content hash, with a mismatch answered as Notion's validation refusal;
    - stateful answers per page:
      - a page that answers its first N page requests (`GET /v1/pages/{id}`), with their children requests, normally, and answers every later request for that page with 503;
      - a page whose children requests answer 503 once the fake has answered a create under it.
  - **Hashing:** computes the content hash with the backend's own function from `rendering.py`.
  - **Request log:** kept in memory only, never logged: method, path, the Authorization value, and the body hash.
  - **Synthetic compositions:** load a private, run-bound `fake-notion.json`.
- Files: `backend/modules/export/notion_session.py`, `backend/modules/export/classification.py`, `backend/modules/export/notion_adapter.py`, `backend/modules/export/fake_notion.py`.
- Traces: FR2.1, FR2.4; BR1.1, BR1.2, BR1.4–BR1.6, BR4.1–BR4.4, BR4.7, BR7.2, BR8.1; NFR3.4–NFR3.6, NFR3.8, NFR3.9, NFR4.2–NFR4.4, NFR4.6, NFR4.7, NFR6.3; A1, A6, A6 extension; D5, D7, D10, D11, D12, D15, D16; R-14.

### Step 14 — Business logic: Notion boundary — write and run its tests

- [x] Add to `tests/u6_approved_export/conftest.py` an automatic, session-wide guard. It replaces `backend.modules.export.notion_session.network_transport` with a stub that fails, for the whole run.
- [x] `tests/u6_approved_export/component/test_guarded_transport.py`:
  - a request to another origin is refused before it leaves;
  - a malformed identifier is refused before it leaves;
  - an answer past 2,000,000 bytes is aborted, both while streaming and from the declared length;
  - a redirect is treated as an unexpected answer.
- [x] `tests/u6_approved_export/component/test_interactive_gate.py` (D15):
  - the per-process cap of 2: a third operation is refused at once;
  - the per-connection cap of 1: a second operation on the same connection is refused at once while one on another connection is admitted;
  - a slot is released after success, after an exception and after cancellation;
  - a refusal maps to DEPENDENCY_UNAVAILABLE, and for a listing to an unavailable listing (`listingComplete: false`, no destinations);
  - an operation without a gate key (the lane) takes no slot.
- [x] `tests/u6_approved_export/component/test_notion_session.py`:
  - two consecutive operations with different tokens never send each other's `Authorization` header;
  - `retry=False` makes exactly one attempt;
  - a spy shows the SDK client is never entered with `with`, and the SDK's pagination helpers are never used;
  - every spent budget gives its stated outcome (D5);
  - the reduced write deadline makes an attempt uncertain;
  - cancellation passes through;
  - with a gate key the slot is taken before the token is opened, and without one no slot is taken;
  - the candidate path reserves its pace slot on the candidate's connection id and leaves no token in logs or results (R-14).
- [x] `tests/u6_approved_export/component/test_classification.py` covers every row of the §7 tables:
  - a 529 counts as rate-limited;
  - a blocked 429 counts as provider-blocked;
  - a 403 with `block_limit: block_creation` counts as workspace-block-limit, and any other 403 as no-access;
  - everything else counts as uncertain.
- [x] `tests/u6_approved_export/component/test_notion_adapter.py`:
  - the written body hashes to the bound value, and a mismatch sends nothing;
  - a response lost after the page was created gives unknown, never a second page;
  - read-back passes only with all three checks;
  - scan results: marker found, possible duplicates, complete with none, partial, unavailable;
  - read retries: a 429 that is not blocked, then success, is retried and succeeds; three retries spent give could-not-check, and for a scan listing-incomplete; a stated wait past the remaining budget stops at once; a blocked 429 is never retried; each retry waits for the later of the stated wait and the next pace slot;
  - `list_destinations`: two search pages are joined; a page cap or spent retries give `listingComplete: false`; each entry carries `readable`, `creationCapability` and `writable` as derived; an untitled page carries no title; `lastDestinationId` is read directly;
  - D16: a 401 from a scan holding the old token, after a replace, does not revoke the new connection;
  - the pending row holds no envelope, and the candidate token is never stored (cicd §8.1, component row).
- [x] `tests/u6_approved_export/component/test_token_exposure.py`:
  - after forced failures of every kind, with every logger captured at DEBUG, no token appears in any log record or in any exception text;
  - every reduced error has `__cause__` None and `__context__` None, and no record, result or attribute holds an exception object.
- [x] `tests/u6_approved_export/component/test_fake_notion.py`:
  - each scenario answers as the real API documents;
  - a counting page answers its first N page requests normally and 503 afterwards;
  - a page's children requests answer 503 only after a create under it.
- [x] `tests/u6_approved_export/database/test_pace_at_fake.py` (D6): two transaction pools sharing one connection stay at or below 2 requests per second, measured at the fake.
- [x] Run `--phase component` and `--phase database`.
- Files: `tests/u6_approved_export/conftest.py` and the eight test files above.
- Traces: same as Step 13; security design §13 "Token exposure", "Revocation", "Transport and SDK", "Write path" and "Reads and pace"; cicd §3.2 component rows and the D6 row.

### Step 15 — Business logic: export service — implement

- [x] `backend/modules/export/service.py` defines `ExportService(transactions, repository, adapter, vault, research, policy, clock)`. It is synchronous: routes call it through `run_in_threadpool`. Every method takes `Authority` first.
  - **configure** (Workflows 1–2; BR1.1–BR1.3; cicd §8.1):
    1. Check the shape: not blank after trimming, printable, within the length bound. Otherwise answer INVALID_ARGUMENT without contacting Notion.
    2. `credentialPolicy` must equal the policy reference.
    3. Check the replay record.
    4. Reserve, take over, or lock the connection row.
    5. Pass the interactive gate, keyed by that row's connection id.
    6. Identify the candidate token as `CandidateToken(connection_id, value)`, paced on that row.
    7. On acceptance, seal with the revision about to be created and store by compare-and-set.

    INVALID_TOKEN, DEPENDENCY_UNAVAILABLE (including a spent budget or a gate refusal) and POLICY_UNRESOLVED (protection unavailable) each release the pending row by holder and store nothing. The token lives only in the call's locals.
  - **disconnect** (BR1.4): clears the envelope and advances the revision, with invalidation. A repeat returns the disconnected connection.
  - **read connection** (A7): an absent or pending record answers NOT_FOUND, which the frontend shows as not connected. A supplied `connectionId` that is not the owner's also answers NOT_FOUND.
  - **list destinations** (BR1.5, BR8.2, A1, S2):
    - requires a connected connection;
    - runs as one gated operation (the search pages plus the `lastDestinationId` read). A gate refusal answers a listing with no destinations and `listingComplete: false`;
    - a partial listing is flagged with `listingComplete: false`;
    - `writable` derives from `readable` and the connection's creation capability;
    - the listing carries the connection's `lastDestinationId`, with that entry's `readable` taken from its direct read, so the step can preselect it only when it is listed and readable;
    - in the real composition only the activation destination is usable (`destinationScopeIds`).
  - **prepare preview** (BR2.1–BR2.5):
    - `renderPolicy` must equal the policy reference;
    - `destinationId` is derived from `parentPageId`, and any client-sent title is ignored;
    - the destination is read directly, through the gate: unreadable answers CONFLICT, could-not-check answers DEPENDENCY_UNAVAILABLE, and in the real composition another destination answers FORBIDDEN;
    - U4's answers map as BR2.1: absent → NOT_FOUND; changed → CONFLICT; ineligible → SOURCE_INELIGIBLE; unreachable → DEPENDENCY_UNAVAILABLE; policy → POLICY_UNRESOLVED;
    - render, check the limits and freeze the revision;
    - no Notion write.
  - **approve** (BR3.1, BR3.2):
    - check for a replay first;
    - a missing `explicitApproval` answers INVALID_ARGUMENT;
    - an approval of a preview revision other than the current one answers CONFLICT;
    - the binding is re-derived through the shared binding check, which takes a gate slot;
    - an export of the pair that succeeded after this revision was prepared answers CONFLICT;
    - any mismatch records nothing. The approval is recorded with the approval-validity policy and `expiresAt` empty (BR3.5).
  - **execute** (BR3.2, BR3.7, BR5.1, BR5.2):
    - check for a replay first, by key or by the approval's existing effect. The same key on another approval answers CONFLICT;
    - an approval that is no longer approved answers APPROVAL_REQUIRED;
    - press or continue, per the decision above. A continue's binding check takes a gate slot;
    - bind. The refusals leave the approval approved:
      - CAPACITY_EXHAUSTED, carrying `retry_after` for the 20-per-hour limit;
      - OUTCOME_UNKNOWN;
      - CONFLICT when an export of the pair succeeded after this approval's preview revision was prepared.
  - **cancel** (BR3.6, A10):
    - an unconsumed approval is cancelled by its preview revision;
    - an accepted effect is cancelled by its effect revision, and the approval stays consumed;
    - an executing effect answers CONFLICT;
    - an unknown effect answers OUTCOME_UNKNOWN.
  - **settle** (BR4.5, A3):
    - check the replay record;
    - only while settlement is offered;
    - requires `assumptionAccepted`;
    - an optional link is accepted only as a Notion page link: an `https` URL on a Notion host that carries a 32-hex page id (BR4.7).
  - **read effect** (A4): `outcomeReason`, `settledBy`, `nextCheckAt` and `settlementOffered`, derived from the effect, its latest check and the passed `now`.
  - **history** (A2):
    - newest first, by keyset;
    - `continuable` comes from the approving session's guard, run in a savepoint for each approved, unconsumed entry;
    - possible duplicates come from the latest marker-found check.
- [x] `backend/modules/export/binding.py` holds one binding check, shared by approve, continue and the lane's pre-write check (BR3.1, BR3.3, BR3.7). It takes a gate key when approve or a continue calls it, and none when the lane calls it. It looks at:
  - the source, re-read with the same tuple and eligibility revision;
  - a direct read of the destination;
  - the connection revision;
  - the session, where a 42501 is a definite authority-revoked;
  - the real-composition allowance.

  It returns unchanged, a definite change with its reason, or could-not-check with its category.
- [x] Domain refusals stay inside each operation's list. No path other than the lane writes to Notion (BR2.2).
- Files: `backend/modules/export/service.py`, `backend/modules/export/binding.py`.
- Traces: FR2.1–FR2.5; BR1.1–BR1.5, BR2.1–BR2.5, BR3.1–BR3.3, BR3.5–BR3.7, BR4.5, BR4.7, BR5.1, BR5.2, BR7.1, BR8.2, BR8.3; A1–A5, A7, A9, A10; NFR1.1, NFR4.1, NFR4.6, NFR4.11, NFR6.4; D15, D16.

### Step 16 — Business logic: export service — write and run its tests

- [x] `tests/u6_approved_export/component/test_service_connection.py`:
  - a first connect stores the token and reads as connected, with the workspace name;
  - a replace advances the revision, invalidates older pending work, and resets the creation capability;
  - disconnect invalidates approved approvals and accepted effects (connection-changed), lets an executing effect finish and keeps an unknown one unknown;
  - a stored-token 401 during a listing revokes the connection with the same consequences;
  - shape refusals never contact Notion;
  - a stale pending row is taken over, with an injected clock (cicd §8.1);
  - configure from `unavailable` answers CONFLICT;
  - disconnect is idempotent.
- [x] `tests/u6_approved_export/component/test_service_destinations.py` (BR1.5, BR8.2):
  - `writable` is false for an unreadable page and for a refused capability, and true otherwise;
  - after a succeeded export, the listing carries its destination as `lastDestinationId`, with `readable` from the direct read;
  - a `lastDestinationId` that is not listed, or whose direct read fails, is carried with `readable` false, so the step drops it;
  - a partial search keeps `listingComplete: false`;
  - a gate refusal answers an unavailable listing at once;
  - in the real composition `destinationScopeIds` holds the activation destination and other pages are not usable.
- [x] `tests/u6_approved_export/component/test_service_preview.py`:
  - U4's answers, driven through a research-port double: absent, changed, ineligible, unreachable, policy;
  - an unreadable destination; FORBIDDEN in the real composition;
  - earlier-export notices: succeeded exports with their link; not-found-after-checks and owner-settled-not-delivered marked as possibly in Notion;
  - an oversized result is refused;
  - the fake's log shows zero provider writes.
- [x] `tests/u6_approved_export/component/test_service_approval.py`:
  - a replay returns the original before any check;
  - a changed payload is IDEMPOTENCY_CONFLICT;
  - a missing `explicitApproval` is INVALID_ARGUMENT;
  - a stale revision, or an export of the pair that succeeded after the revision was prepared, is CONFLICT;
  - a refusal records nothing;
  - two tabs on the same revision get the same approval.
- [x] `tests/u6_approved_export/component/test_service_outcomes.py`:
  - **execute:** a replay returns the original effect; press and continue are told apart; a continue under a stale session invalidates the approval (authority-revoked) and answers APPROVAL_REQUIRED; bind refusals leave the approval unconsumed; continuing an older approval after a newer export of the same pair has succeeded answers CONFLICT and leaves the approval approved; the 20-per-hour refusal carries `retry_after` equal to the seconds until the oldest bind of the rolling hour leaves it;
  - **cancel:** both paths work, and the refusals answer correctly;
  - **settle:** offered only in the three cases and only after the settling wait; never settled twice; the link is validated;
  - **reads:** read-effect derived fields; history `continuable` and possible duplicates.
- [x] `tests/u6_approved_export/component/test_binding_check.py`:
  - definite versus could-not-check for each fact;
  - a 42501 maps to authority-revoked;
  - U4's policy-unresolved answer maps to could-not-check (policy);
  - called from approve or a continue it takes a gate slot; called from the lane it takes none.
- [x] Add an error-code matrix: for every operation, its refusals are a subset of its own list.
- [x] Add a zero-writes check: every operation except the lane makes zero provider writes (BR2.2).
- [x] Run `--phase component`.
- Files: the six test files above.
- Traces: same as Step 15; cicd §8.1 component rows.

### Step 17 — Business logic: worker pass step and export lane — implement

- [x] `backend/modules/export/worker.py` defines `ExportWorker(inherited, export_pass)`, shaped like `TopicsWorker`. Its pass step touches only the database, on bounded batches.
  - **Housekeeping:**
    - D4: an approval whose approving session ended is invalidated (authority-revoked) and trimmed in the same transaction;
    - while the session is current, an approval whose source U4 definitely reports absent, changed or not exportable is invalidated (source-changed) and trimmed in the same transaction. U4 unreachable or policy unresolved, or a session check that could not complete, leaves it approved, to be checked again on the next pass (NFR4.9);
    - every preview revision that can no longer lead to a write is trimmed (decision "Rendered copies");
    - unapproved previews are purged after 7 days;
    - stale pending rows are swept.
  - **Orphan sweep:** an attempt still outstanding 15 minutes after its start turns its effect unknown, and the evidence gap is recorded.
  - **Hand-over:** when the lane is idle, hand it the next due item in security design §8.1's order. For a scan, move `next_check_at` forward by the scan budget plus one minute.
- [x] `backend/modules/export/lane.py` defines `ExportLane`: one background thread per process, a one-item queue, and its own work budget on each short transaction. For each item:
  1. **Pre-write check** (BR3.3): definite change versus could-not-check, `waiting_since`, and the 24 h bound. The binding check runs without a gate key.
  2. **Pace:** reserve the pace slot and wait for it.
  3. **Claim:** a compare-and-set, with the attempt and its `deadline_at` recorded in the same transaction.
  4. **Write:** outside any transaction, under `asyncio.timeout` until `deadlineAt`.
  5. **Record:** the outcome, with the provider's request id and `creator_confirmed`, and the connection facts of decision "Connection facts from outcomes": on created, `last_destination_id` and, while the connection is still at the attempt's revision, creation capability confirmed; on no-access, refused under the same guard.
  6. **Read-back:** within its own 60 s budget.

  The lane also handles:
  - the rate-limit window of NFR4.5;
  - scans, recorded with their evidence hash and BR4.4's results. A marker found makes the effect succeeded and sets the connection facts the same way. Two complete clean scans at least one settling interval apart fail the effect as not-found-after-checks. `next_check_at` follows the schedule, and `scanning_stopped_at` is set when the budget is spent;
  - the lane status record.

  It starts and stops with the lifespan. On shutdown it stops taking items and waits for the one in hand, up to its deadline. It never logs an exception object.
- Files: `backend/modules/export/worker.py`, `backend/modules/export/lane.py`.
- Traces: FR2.4, FR2.5; BR1.4–BR1.6, BR2.1, BR2.6, BR3.3, BR3.4, BR4.2–BR4.4, BR4.6, BR4.7, BR7.2, BR8.2; NFR1.2, NFR1.5, NFR4.4, NFR4.5, NFR4.7–NFR4.9; D4, D8, D9.

### Step 18 — Business logic: worker and lane — write and run its tests

- [x] `tests/u6_approved_export/component/test_lane_write_path.py`:
  - the claim is atomic;
  - definite change versus could-not-check, and the 24 h bound;
  - the rate-limit window: up to 4 attempts in 10 minutes; a stated wait past the window fails at once; a could-not-check during a resume fails as dependency-unavailable;
  - an unknown export is never written again;
  - the settling wait counts from `deadlineAt`;
  - on created, the connection's `last_destination_id` names the destination and its creation capability becomes confirmed; on no-access it becomes refused; after a replace, an old attempt's outcome leaves the new connection's capability unknown; neither update changes the connection revision.
- [x] `tests/u6_approved_export/component/test_reconciliation.py`:
  - every scan result, and possible duplicates;
  - a marker found sets `last_destination_id`;
  - the second clean scan must be at least one settling interval after the first;
  - scanning stops when the budget is spent;
  - after a disconnect, scans record listing-unavailable;
  - the writer identity comes from the attempts, not from the current connection.
- [x] `tests/u6_approved_export/component/test_worker_pass.py`:
  - the orphan sweep;
  - hand-over order, and no duplicate scans;
  - housekeeping batches stay bounded;
  - NFR4.9: with the session current, U4 definitely reporting the source absent, changed or not exportable invalidates the approval (source-changed) and trims it in one transaction;
  - NFR4.9: U4 unreachable, U4 policy unresolved, or a session check that could not complete leaves the approval approved, and the next pass checks it again;
  - the revision of a cancelled approval, of an approval invalidated by a connection change, and a superseded never-approved revision are trimmed;
  - the revision of an approved, unconsumed approval keeps its tree even when superseded.
- [x] `tests/u6_approved_export/integration/test_lane_transactions.py`:
  - D8: no database transaction is open while the fake Notion answers a write;
  - D9: a worker pass returns within its deadline while the lane runs a slow write.
- [x] `tests/u6_approved_export/integration/test_session_housekeeping.py` (D4): an approval whose session ended is invalidated and trimmed on the next pass.
- [x] Run `--phase component` and `--phase integration`.
- Files: the five test files above.
- Traces: same as Step 17; security design §13 "Write path" and "Approvals"; cicd §3.2 integration rows.

### Step 19 — Business logic: lifecycle participant and A8 projection — implement

- [x] `backend/modules/export/control_lifecycle.py` defines `ExportLifecycleParticipant`, with scopes `live_records`, `pending_work` and `external_copies`. It goes through `apply_owner_effect` and never defers.
  - **Withdraw:** in one transaction:
    - invalidate approved approvals and accepted effects (account-withdrawn);
    - clear the envelope;
    - set the connection disconnected;
    - delete the pending row through `export.lifecycle_release_pending`;
    - record counts.
  - **Reactivate:** records evidence and changes nothing.
  - **Erase:** the withdraw step, then count-only evidence, then `export.erase_account_records`.
  - **external_copies:** its counts never depend on scope order, and it overrides the reason key with `external-copies-retained-by-owner`, following the precedent of `UsageLifecycleParticipant`.
- [x] Add `"export": "ApprovedExport"` to the participant map in `backend/lifecycle_effects.py`.
- [x] In `backend/modules/accounts/services/control_lifecycle.py`, lines 341–346, report a completed erase scope as `retained_by_policy` when its reason key is one of `bounded-audit-identifiers-retained` and `external-copies-retained-by-owner`, and as `erased` otherwise. Registration in the shared manifest stays with U8.
- Files: `backend/modules/export/control_lifecycle.py`, `backend/lifecycle_effects.py`, `backend/modules/accounts/services/control_lifecycle.py`.
- Traces: FR2.5; BR6.1–BR6.5, BR7.2; NFR1.4, NFR1.5, NFR3.7; A8.

### Step 20 — Business logic: lifecycle — write and run its tests

- [x] `tests/u6_approved_export/component/test_export_lifecycle.py`:
  - every action and scope gives its effect;
  - a repeated ticket returns the recorded evidence;
  - counts are numbers only;
  - the pending row is deleted;
  - an executing export is left to finish, and an unknown one is kept;
  - erase removes every row and keeps the counts;
  - external copies carry the retained reason key;
  - the report is the same in any scope order.
- [x] `tests/u6_approved_export/integration/test_lifecycle_projection.py` follows U5's pattern (`tests/u5_topics_digests/component/test_topics_logic.py:593–637`):
  - it seeds an erase `accounts.lifecycle_request` and its `accounts.lifecycle_scope` rows through `connect("accounts")`: the three ApprovedExport scopes plus one further manifest scope;
  - it builds `ControlLifecycleService` with a stub entry that exposes only `control_policy=SYNTHETIC_POLICY` and the realm's `transactions`;
  - for each ApprovedExport scope it drives `claim()`, the participant's `apply()` and `acknowledge()`. It acknowledges the further scope directly with `bounded-audit-identifiers-retained`;
  - `_status()` then reports `retained_by_policy` for `external-copies-retained-by-owner` and for `bounded-audit-identifiers-retained`, and `erased` for `owner-scope-complete`.

  It never calls `request()`, `status_transport()` or `inspect_limited()`, and it never drives the reactivate branch of `acknowledge()`: they need U2-only schema that U6's realm does not have (decision "Coverage scope"). This reaches about a third of `control_lifecycle.py`, including every changed line.
- [x] Run `--phase component` and `--phase integration`.
- Files: the two test files above.
- Traces: same as Step 19.

### Step 21 — API / endpoint: C09 routes and composition — implement

- [x] `backend/modules/export/http.py` defines `export_router(transactions, *, entry, service)`, table-driven like `research_router`:
  - routes use `boundary_route(origin, missing=(404, "NOT_FOUND"))`;
  - eleven POST routes at `/api/v2/c09/<operation>`: the nine frozen operations plus A2 and A3;
  - each route runs `post_context`, then `read_payload` with the generated `*Http` model, then a check of private identifiers (422 on failure), then `run_in_threadpool`;
  - `ExportError` maps through `ERROR_STATUS`:
    - 422: INVALID_ARGUMENT, INVALID_TOKEN;
    - 401: UNAUTHENTICATED;
    - 403: FORBIDDEN, SOURCE_INELIGIBLE;
    - 404: NOT_FOUND;
    - 409: CONFLICT, IDEMPOTENCY_CONFLICT, APPROVAL_REQUIRED, OUTCOME_UNKNOWN;
    - 429: CAPACITY_EXHAUSTED, raised as `BrowserDenied(429, "CAPACITY_EXHAUSTED", retry_after=exc.retry_after)` so that the body carries `retryAfterSeconds`. No `Retry-After` header is set;
    - 503: POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE;
    - anything unmapped: 500;
  - output goes through `wire.<Model>.model_validate(result).model_dump(mode="json", exclude_unset=True)`, and a `ValidationError` there answers 500;
  - nothing logs a request body, and FastAPI's echoing validation response is never used.
- [x] `backend/u6_host.py`:
  - **`export_contribution(transactions, entry, corpus, inherited_worker, *, research, policy=None, transport_factory=None, clock=None)`** returns the service, router, worker, lane and an `export` capability row derived from the bound transport:
    - the row: id `export`, state `degraded`, `modeIds` `synthetic-only` or `real-bounded`, `languageIds` `["ko"]`, `levelIds` `[]` (as U4's rows, `backend/u4_host.py:36`; the frozen catalog requires the field, `shared/dtos/workspace.schema.json:5206–5214`), `formatIds` `["notion"]`, and the policy reference;
    - it raises if the policy and the transport disagree;
    - a synthetic policy builds only the fake Notion;
    - it builds the token keyring on `profile.root / "export-keys"`;
    - it keeps the `httpx` and `httpcore` loggers at WARNING or above.
  - **`assemble_u6(profile)`:** `assemble_u5(profile, export_factory=…)`, with the delegated fixture clock and the scenario file `fake-notion.json`.
- [x] `backend/u6_real_export.py`:
  - reads `real-export.json` through `private_bytes`, requiring exactly its fields, a matching `runId`, a 32-hex destination and the free-terms shape. Any gap is a POLICY_UNRESOLVED refusal;
  - defines `assemble_u6_real(profile, activation, *, transport_factory=None)`. The parameter is the test-only seam; without it, the network transport comes from `notion_session.network_transport()`;
  - refuses an environment that holds any evidence file.
- [x] Composition chain:
  - `backend/u3_host.py`:
    - the topics gate at lines 252–256 admits (`docsuri_u6`, `approved-export`, `EXPORT_ORIGIN`) as well as U5's triple;
    - a new export gate admits `export_factory` only for that U6 triple, and only with research and topics;
    - the research service hand-over;
    - the lane in the lifespan, stopped after the control loop closes and before the transactions close;
    - `export` in the required capabilities, and `app.state.export`;
  - `backend/u4_host.py` and `backend/u5_host.py`: the `export_factory` keyword pass-through.
- [x] Shell and observation:
  - `backend/local_host.py`: `"export"` in `SYNTHETIC_CAPABILITIES`, and a navigation entry `{routeId "export", titleKey "nav.export", path "/export", capabilityId "export", ownerBound true}`;
  - `backend/local_observation.py`: `PROBES["export"]` (counts plus the presence of a guard function), excluded from `observe_all`'s default set.
- Files: `backend/modules/export/http.py`, `backend/u6_host.py`, `backend/u6_real_export.py`, `backend/u3_host.py`, `backend/u4_host.py`, `backend/u5_host.py`, `backend/local_host.py`, `backend/local_observation.py`.
- Traces: FR2.1–FR2.5; BR1.1, BR1.2, BR2.2, BR3.1, BR3.2, BR5.2, BR7.1, BR8.1–BR8.3; NFR1.1, NFR1.3, NFR3.4, NFR3.9, NFR4.10, NFR6.2, NFR6.3; A2, A3; D15; R-06 (rows 10 and 11).

### Step 22 — API / endpoint: write and run its tests

- [x] `tests/u6_approved_export/integration/test_export_http.py` mounts the app as U5's `test_http.py` does, with session cookie, Origin, CSRF and Idempotency-Key. It checks:
  - every operation's happy path;
  - each refusal code lies in its operation's list;
  - owner isolation gives not-found;
  - replays return the original;
  - a configure body that fails validation answers `INVALID_ARGUMENT` without echoing it;
  - after forced failures, no token appears in any response or stored record;
  - D16: a bad candidate token while connected answers INVALID_TOKEN and leaves the connection unchanged;
  - a 20-per-hour refusal answers 429 `CAPACITY_EXHAUSTED` with `retryAfterSeconds` in the body and no `Retry-After` header.
- [x] `tests/u6_approved_export/integration/test_pending_connect.py`:
  - a first configure with no connection succeeds, is paced, and advances the pending row's `connection_pace.next_slot_at` (R-13, R-14);
  - every other outcome of the holding check deletes the pending row;
  - a second connect during a fresh pending check answers 409 `CONFLICT` (R-03);
  - a stale pending row older than 2 minutes is taken over;
  - housekeeping removes leftovers;
  - no read ever shows the pending state;
  - withdrawal and erasure delete the pending row.
- [x] `tests/u6_approved_export/integration/test_interactive_admission.py` (D15): with the fake Notion hanging,
  - a listing and a preview read from two different owners hold the two process slots;
  - a third interactive request of either kind answers at once: a listing as an unavailable listing, a preview with DEPENDENCY_UNAVAILABLE, a configure with DEPENDENCY_UNAVAILABLE and its pending row released;
  - a second listing on the same connection is refused at once even while a process slot is free;
  - other routes still get admission slots;
  - the lane still takes its item.
- [x] `tests/u6_approved_export/integration/test_account_purpose.py`: sign-in, session read, logout and the settings read and save through the mounted routes in the U6 realm, under the `account-control` purpose.
- [x] `tests/u6_approved_export/integration/test_export_assembly.py`: `assemble_u6` mounts the routes, the capability row, the navigation entry, and readiness with the export probe. Under a `TestClient` context, as U5's `test_email_unsubscribe.py` does:
  - `/api/v2/capabilities` answers 200, so the whole catalog validates with the export row;
  - one control worker pass runs through the inherited chain;
  - on exit, spies show the order: the control loop closes, then the export lane stops, then the transactions close.
- [x] `tests/u6_approved_export/component/test_u3_export_gate.py` uses stub profiles, refused before any connection is made:
  - `assemble_u3` refuses `export_factory` outside (`docsuri_u6`, `approved-export`, `EXPORT_ORIGIN`);
  - it refuses `export_factory` without both the research and the topics factories;
  - the topics gate admits the U6 triple and still refuses any other realm;
  - the U3, U4 and U5 gates still refuse exactly as today.
- [x] `tests/u6_approved_export/component/test_export_policy.py`: the policy's bounds and the real-policy refusals.
- [x] `tests/u6_approved_export/component/test_export_composition.py`:
  - capability derivation, and the raise on disagreement;
  - the export row, `levelIds` included, validates against `wire.CapabilityCatalog`;
  - a synthetic composition cannot build the network transport.
- [x] `tests/u6_approved_export/component/test_real_export_composition.py`:
  - every activation-file refusal (activation files are written only into `tmp_path`);
  - injection through the seam works;
  - with no fake injected, the real composition fails at the test-wide guard before any network transport exists;
  - an environment holding evidence is refused.
- [x] Run `--phase integration` and `--phase component`.
- Files: the nine test files above.
- Traces: same as Step 21; BR6.1, BR6.2 (the pending row on withdrawal and erasure); security design §13 "Token exposure", "Revocation" and "Reads and pace"; cicd §3.2 integration rows and the real-composition row; cicd §8.1; R-03, R-13.

### Step 23 — Frontend behavior — implement

- [x] `frontend/src/u6-export/api.ts`:
  - type aliases from `frontend/types/wire/dtos.ts`;
  - `exportCall<K>(client, operation, body, key?)` over `Transport.post` to `/api/v2/c09/<operation>`;
  - response validators that throw `ApiError(502, 'INVALID_CONTENT')`;
  - `findExportCapability`.

  Never import JSON in `src`, and name no function `classify*`, `map*` or `cardFromMeta*` unless it is registered in `shared/view-adapters.json`.
- [x] `frontend/src/u6-export/copy.ts` holds the Korean text:
  - states, the 18 outcome reasons and the 5 invalidation reasons;
  - limitation keys;
  - refusal hints: share the page, enable content insertion, the block limit;
  - the connect help: read content and insert content only; no update, no comments, no user information (D7).
- [x] `frontend/src/u6-export/export-view.tsx`:
  - `ExportView`, with h1 "내보내기";
  - `ConnectionPanel`, with h2 "Notion 연결";
  - `ExportHistory`, with h2 "내보내기 기록";
  - five view states, and SWR keys bound to `client.generation`, as in U5.
- [x] `frontend/src/u6-export/connect-form.tsx`:
  - the token lives in component state only;
  - the field is not a password field, and sets `autocomplete="off"` and `spellcheck="false"`;
  - the field is cleared after every submit;
  - the token never goes into storage, a URL or a log;
  - while the call runs, the form shows "확인 중";
  - on CONFLICT, the form re-reads the connection (R-03).
- [x] The stepped flow:
  - **`frontend/src/u6-export/export-flow.tsx`:** a step indicator exposing the current step as state; closing never exports.
  - **`frontend/src/u6-export/destination-step.tsx`:**
    - a listing with a refresh action;
    - the listing state derived as decision S2 says, with notices for partial, unavailable and empty listings, the empty one with how to share a page;
    - a placeholder for untitled pages, and location context;
    - an unusable page shown with its reason;
    - readability and creation capability as far as known ("확인 전" until the first write, then confirmed or refused);
    - in the real composition, only `destinationScopeIds` destinations are usable, and other pages are shown as not allowed;
    - `lastDestinationId` is preselected only when listed and readable; a stale one is dropped with a notice.
  - **`frontend/src/u6-export/preview-step.tsx`:**
    - the source and destination summaries, the earlier-export notice, and the read-only rendered page including the marker line;
    - "승인하고 내보내기", a native button and the only publishing control. When disabled it shows a textual reason;
    - one press key per press, reused when retrying after UNKNOWN_OUTCOME;
    - a changed binding shows a notice that takes focus and offers "미리보기 다시 만들기";
    - CAPACITY_EXHAUSTED with `retryAfterSeconds` shows when exporting is possible again; without it, the step says another export is in flight.
  - **`frontend/src/u6-export/outcome-step.tsx`:**
    - polls read-effect through SWR while the effect has not ended;
    - one polite live region announces each change once;
    - every status shows text and an icon;
    - the success link is named by the page title. When the owner settled the effect as delivered, the link is shown only if the owner supplied one, labelled "직접 확인됨" (BR4.7);
    - "취소" is offered while the export is accepted;
    - an unknown export shows the next check time;
    - before the export starts, it notes that signing out stops it.
- [x] `frontend/src/u6-export/history.tsx`:
  - rows with actions by state: continue only when continuable; cancel; settle only when offered; fresh preview;
  - possible duplicates, the next-check note, and paging;
  - an owner-settled row labelled "직접 확인됨", with the owner's link only when one was supplied.
- [x] `frontend/src/u6-export/dialogs.tsx`:
  - a dialog shell following U5's `ConfirmationDialog`: focus moves into it, Tab is trapped, Escape closes it, and focus returns to the trigger;
  - `DisconnectDialog` names the consequences;
  - `SettleDialog` names the destination and title, shows the assumption, and accepts an optional Notion page link.
- [x] `frontend/src/u6-export/export.css` uses the semantic tokens of `frontend/app/globals.css` for both themes, never U5's undefined fallbacks. Targets are at least 24×24 px, and the layout reflows at 320 px.
- [x] `frontend/src/u4-research/export-action.tsx` adds "Notion으로 내보내기". It opens `ExportFlow` with `novelty.artifact`, and opening or closing never exports. `research-workspace.tsx` renders it beside `NoveltyDiscussion` when the export capability is present.
- [x] `frontend/src/App.tsx`: only the R-04 additions.
- [x] `frontend/src/api.ts`:
  - `SAFE_CODES` gains OUTCOME_UNKNOWN, INVALID_TOKEN and CAPACITY_EXHAUSTED. SOURCE_INELIGIBLE, APPROVAL_REQUIRED and POLICY_UNRESOLVED are already present;
  - `dispositionCopy` gains Korean copy for OUTCOME_UNKNOWN, INVALID_TOKEN, CAPACITY_EXHAUSTED, SOURCE_INELIGIBLE and APPROVAL_REQUIRED.
- Files:
  - `frontend/src/u6-export/`: `api.ts`, `copy.ts`, `export-view.tsx`, `connect-form.tsx`, `export-flow.tsx`, `destination-step.tsx`, `preview-step.tsx`, `outcome-step.tsx`, `history.tsx`, `dialogs.tsx`, `export.css`;
  - `frontend/src/u4-research/`: `export-action.tsx`, `research-workspace.tsx`;
  - shell: `frontend/src/App.tsx`, `frontend/src/api.ts`.
- Traces: FR2.1–FR2.5; BR1.1, BR1.3, BR1.5, BR2.2, BR2.5, BR3.1, BR3.2, BR3.6, BR3.7, BR4.4, BR4.5, BR4.7, BR5.1, BR5.2, BR8.2; NFR1.3, NFR3.4, NFR5.1; A1–A5, A7, A9, A10; D7; R-03, R-04.

### Step 24 — Frontend behavior — write and run its tests

- [x] `frontend/test/u6-export/fixtures.ts` defines a schema-validated double, as in U4: every request and response is checked against the canonical C09 defs. It also provides an `envelope` factory and a per-mount SWR provider.
- [x] Vitest files in `frontend/test/u6-export/`:
  - **`connect-form.test.tsx`:**
    - the token field is not a password field, sets `autocomplete="off"` and `spellcheck="false"`, and is cleared after every submit, on success and on failure;
    - field errors name the problem without echoing the token;
    - the token never reaches storage;
    - the form shows "확인 중" while configure is in flight (cicd §8.1);
    - the connect help names read content and insert content only, and names none of update content, comment access or user information (D7);
    - the R-03 re-read logic;
    - a stale revision reloads.
  - **`export-view.test.tsx`:** the five states; a pending record reads as "not connected" (cicd §8.1).
  - **`destination-step.test.tsx`** (BR1.5):
    - the partial, unavailable and empty notices, the empty one with how to share a page;
    - the untitled placeholder, and same-titled pages told apart by context;
    - an unusable page with its reason;
    - creation capability shown as far as known;
    - a stale preselection dropped with its notice, and a listed, readable one preselected;
    - in the real composition, pages other than the activation destination shown as not allowed.
  - **`preview-step.test.tsx`:**
    - a changed binding leads to a fresh preview;
    - a CAPACITY_EXHAUSTED refusal with `retryAfterSeconds` shows when exporting is possible again, and one without it says another export is in flight.
  - **`approve-export.test.tsx`:** a retried press reuses its key; bind refusals show plain notices.
  - **`outcome-step.test.tsx`:** polling announces each change once; an owner-settled success shows the link only when the owner supplied one, labelled "직접 확인됨".
  - **`history.test.tsx`:** actions appear by state; an owner-settled row shows "직접 확인됨", with the link only when supplied.
  - **`dialogs.test.tsx`:** focus trap, Escape, focus return, the assumption shown, and link validation.
  - **`status-accessibility.test.tsx`:** text and icon on every status; one polite live region.
  - **`api.test.ts`:** paths, validators, and the new safe-code copy.
- [x] U4's lane: `frontend/test/u4-research-novelty/export-action.test.tsx` checks that the action is offered only with the capability and a ready novelty result, and passes the exact `ResearchArtifactRef`. It also checks that opening or closing makes zero C09 mutations.
- [x] Shell tests: `frontend/test/u3-paper-corpus-capabilities/export-shell.test.tsx` and `frontend/test/u4-research-novelty/export-shell.test.tsx`:
  - the "내보내기" entry appears only with the capability, and only when signed in;
  - clicking it opens the view heading.
- [x] Add `'test/u6-export/**/*.test.{ts,tsx}'` to `frontend/vitest.u2-cumulative.config.ts`.
- [x] Run:
  - `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts --coverage` (80% lines);
  - U4's and U3's lanes with coverage (`src/App.tsx` at or above 48%, and `src/u4-research` at or above 80%);
  - U2's cumulative lane;
  - the U6, U5 and U4 type lanes;
  - U6's ESLint command.
- Files: `frontend/test/u6-export/` (fixtures and the test files above), `frontend/test/u4-research-novelty/export-action.test.tsx`, the two shell tests, `frontend/vitest.u2-cumulative.config.ts`.
- Traces: same as Step 23; cicd §3.2 "NFR5.1 component checks"; R-04.

### Step 25 — Environment/build configuration: environment tool phases and helper scripts — implement

- [x] Complete `scripts/verify_docsuri_u6.py` (cicd §4.3):
  - **`fixtures`.**
  - **`coverage`:** runs the fixtures first, then the whole tree with `--cov-config=backend/.coveragerc.u6`, then a second report, `coverage report --rcfile=backend/.coveragerc.u6 --include=scripts/u6_preservation.py --fail-under=80`.
  - **`frontend`:** Vitest with JUnit output and `--coverage`.
  - **`browser`:**
    - refuses an environment that holds any evidence file;
    - prepares the fixtures and builds the assets;
    - starts the synthetic host on 18099;
    - runs Playwright with the delegated clock under one `PHASE_SECONDS` bound.
  - **`serve`:** never passes `--real-export`.
  - **`teardown`:** reports and disposes of nothing. It refuses while `export-keys/` holds a key file, and names `archive-owned`.
  - **`archive-owned`:** calls `u6_preservation.archive` with its context.
  - **Key phases:** `create-key-after-loss`, `rotate-key`, `retire-key --version <v>` and `key-counts`. Each goes through `connect_admin` and `SET ROLE docsuri_export_owner` into `key_commands`, under the runner lock and the keyring's waiting lock.
  - **Real-export isolation:** every synthetic phase refuses while `real-export.json` exists.
  - **Clock delegation:** the browser clock delegation and the child authorisation, as in U5.
- [x] `scripts/u6_preservation.py` implements the destructive archive of cicd §4.4 and D14:
  1. every check first, accepting only the first-key staging pair;
  2. leftover staging files removed. If any removal fails, the archive refuses before the key unlink;
  3. one unlink of the key file, then a folder sync;
  4. the rest of the key folder;
  5. the rename.

  Its result adds `keyDeleted: true`.
- [x] `scripts/u6_browser_fixtures.py`, with version `u6-browser-v1`, prepares:
  - two synthetic accounts and two eligible papers;
  - a ready novelty result for each exporting account, produced through U4's service and synthetic execution, never by writing research tables;
  - `fake-notion.json`, the fake's scenario:
    - shared pages, including an untitled one and two same-titled ones with distinct context;
    - an unreadable page;
    - for each browser spec that cancels or settles (`journeys.spec.ts`, `keyboard.spec.ts`, and the dialogs `accessibility.spec.ts` opens), its own cancel destination and settle destination, so no spec depends on another's leftovers;
    - each cancel destination answers its first two page requests normally: the preview's destination read and the approve call's binding read. It answers every later request for that page with 503, so the lane's pre-write check cannot complete and the export waits as accepted until it is cancelled. Cancelled exports never set `lastDestinationId`, so no listing reads these pages directly;
    - each settle destination answers normally until the fake has answered a create under it with 504. From then on its children requests answer 503, so every scan records listing-unavailable and settlement is offered once the advanced clock passes the settling wait;
  - a synthetic token that only the fake accepts;
  - an `advance-clock` action.
- [x] `scripts/serve_docsuri_u6.py` assembles `assemble_u6`, or `assemble_u6_real` with `--real-export`, and serves uvicorn on `127.0.0.1:18099` with the environment's TLS.
- [x] `scripts/u6_real_export.py` provides two operator actions:
  - `check` names every gap in the settings;
  - `outcome` records digests only: the SHA-256 of the request id and of the page link, the final state and reason, the outcome class and `creator_confirmed`.
- [x] `frontend/playwright.u6-export.config.ts` applies U5's checks with U6's values: `DOCSURI_U6_ENVIRONMENT_FILE`, the run-id pattern, unit, realm, database, ports, the `approved-export-tls` files and the SPKI pin.
- Files: `scripts/verify_docsuri_u6.py`, `scripts/u6_preservation.py`, `scripts/u6_browser_fixtures.py`, `scripts/serve_docsuri_u6.py`, `scripts/u6_real_export.py`, `frontend/playwright.u6-export.config.ts`.
- Traces: NFR3.2, NFR3.3, NFR5.1, NFR6.2, NFR6.3; BR8.1, BR8.2; D14; R-05, R-06 (row 13), R-08; cicd §4–§5, §9.

### Step 26 — Environment/build configuration: write and run tool tests and browser journeys

- [x] `tests/u6_approved_export/operations/test_u6_runner.py`:
  - the phase list and the constants;
  - `MIGRATIONS` equals U5's chain followed by the four U6 files, each with its owner;
  - `setup` creates the key folder at mode 0700;
  - teardown refuses while a key file exists;
  - `serve` never passes `--real-export`;
  - every test path a phase names resolves to at least one file that `git ls-files --cached --others --exclude-standard` lists, and an ignored or empty folder fails;
  - every synthetic phase refuses while `real-export.json` exists;
  - every layer folder collects at least one test (R-08);
  - the R-06 completeness scan.
- [x] `tests/u6_approved_export/operations/test_u6_preservation.py`, against `scripts/u6_preservation.py` with a controlled context:
  - a completed archive leaves no key file;
  - a refusal at any check of the first step leaves the key folder intact;
  - a key still linked by its first-key staging name is archived with no key left, on a live and on an expired environment;
  - a staging file that cannot be removed refuses before the key unlink, with the key in place.
- [x] `tests/u6_approved_export/operations/test_u6_profile_binding.py`:
  - a U6 manifest loads with its ports and realm;
  - 18069 is still refused as an unowned origin;
  - an expired environment keeps its preservation identity.
- [x] `tests/u6_approved_export/operations/test_u6_browser_fixtures.py`, `test_u6_real_export_checks.py` and `test_u6_serve.py`:
  - fixture setup is idempotent;
  - the scenario gives each spec its own cancel and settle destinations, with the stateful answers of Step 25;
  - every settings gap is named;
  - the digests-only evidence holds no token;
  - the wrong realm and an evidence-holding real export are refused.
- [x] Browser journeys in `frontend/e2e/u6-approved-export/`:
  - `helpers.ts`: failure-only diagnostics; strict custody of the fixture file;
  - `journeys.spec.ts`: connect, export, cancel, and settle an unclear export after advancing the delegated clock;
  - `keyboard.spec.ts`: keyboard only through the same four, checking 2.1.1, 2.4.3, 2.4.7 and 2.4.11, focus trapped in dialogs and returned to the trigger;
  - `reflow.spec.ts`: a 320 CSS px viewport, with no scrolling in two dimensions;
  - `accessibility.spec.ts`: `AxeBuilder` with the tags `wcag2a`, `wcag2aa`, `wcag21aa` and `wcag22aa` on every U6 view and dialog. Any violation fails.
- [x] Run `--phase operations`. Then, on a fresh environment, run `--phase browser`.
- Files: the six operations test files above, and `frontend/e2e/u6-approved-export/` (`helpers.ts` and the four specs).
- Traces: same as Step 25; FR2.1–FR2.4 (the browser journeys); security design §13 "Key custody (preservation)"; cicd §3.2 rows for preservation, real-export isolation and WCAG; R-06, R-08.

### Step 27 — Environment/build configuration: CI lane, drift refresh and full verification

- [x] Write `.github/workflows/u6-approved-export.yml` from cicd §2:
  - **Settings:** name `U6 approved export`; pull requests into `develop` and manual runs; `contents: read`; concurrency group `u6-export-…`; the same pinned actions, uv 0.9.0, Node 24.14.0 and pnpm 9.15.9; the same database image digest; `DOCSURI_U6_ENVIRONMENT_FILE`; no secrets, caches or artifacts; U5's header and closing comments, adapted.
  - **Path filters:** the shared entries, U6's own names, and the extra filters in decision "CI path filters", which Step 28 records for approval.
  - **Jobs:**
    - `shared-contracts`: the drift checks and the shared suite;
    - `frontend`: types, ESLint, Vitest with coverage, `vite build`;
    - `backend`: Ruff on the cicd §2.3 targets plus `scripts/u6_real_export.py`; the earlier units' regressions (U5's two U1 and two U2 files, plus the cicd §2.4 keyring command); then `setup`, `migrate` and `coverage`;
    - `browser`: depends on the other three; `setup`, `migrate` and `browser`.
- [x] Refresh both consumer inventories last, after every other edit:
  - `shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py --write`;
  - from working directory `frontend`, `node scripts/inventory-consumers.mjs --write`.

  Then run every drift check: export `--check`, binding `--check`, `inventory_consumers.py`, `check:types`, `check:consumers`, `test:contracts`.
- [x] Run lint: Ruff on the cicd §2.3 targets, and U6's ESLint command.
- [x] On fresh environment A, run `setup`, `migrate`, `coverage` (with the second report) and `frontend`. Record the totals, and each measured U2 file's percentage beside the total.
- [x] Run `archive-owned` on A; it deletes the key file. Then, on fresh environment B, run `setup`, `migrate` and `browser`. That last command is the Construction Verification Command: `backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json`.
- [x] Earlier units:
  - run the cicd §2.4 keyring regression and U5's U1 and U2 regression files;
  - run U2's cumulative lane, and U3's and U4's lanes, locally;
  - run the next-app checks locally: whole-program `tsc --noEmit`, `tsc -p tsconfig.e2e.json`, and the full `vitest run`;
  - on environments re-created after the lock change, run U2's `operations`, `component` and `integration` phases, U4's `coverage` and U5's `coverage`.

  The U1–U5 workflows on the pull request remain the merge gate.
- [x] Record every command and its result as it happened. No failure is described as passing, and a failure that already exists on `develop` is shown to exist there and is reported.
- Files: `.github/workflows/u6-approved-export.yml`, `shared/python-consumers.json`, `shared/typescript-consumers.json`.
- Traces: NFR6.1, NFR6.3; the 80% floors; cicd §1.3, §2, §3.1, §6, §9; R-04, R-08.

### Step 28 — Documentation and traceability

- [x] Record for approval at the U6 checkpoint:
  - the R-01 entity settlement, including the internal store columns (the connection's `workspace_id`, the attempt's `deadline_at` and `creator_confirmed`, the effect's `ended_at`);
  - the R-15 source line;
  - settlement S2, including `listingComplete` and `lastDestinationId` on ExportDestinations;
  - the ExportConnection state machine amendment with R-02's holder guard;
  - the hash rule;
  - A6's reading of "currently permitted destinations";
  - the A2 and A3 operation names and error lists;
  - the BR2.6 reading: a revision whose approval is still approved and unconsumed keeps its tree until that approval ends;
  - the test-path check: cicd §4.3's "tracked in git" read as "listed by `git ls-files --cached --others --exclude-standard`", which equals "tracked" in CI;
  - the extra CI path filters and their rationale, because cicd §2.1 says the workflow mirrors U5's line for line;
  - `backend/u3_host.py` added to `.coveragerc.u6` beyond cicd §2.5's list, because its new gates and lane lifecycle are more than one value;
  - the Construction Verification Command.
- [x] Write the operator runbook for the one real export (cicd §5) in this record folder, beside the code summary. The export itself runs at Build and Test, and only after the owner explicitly approves the exact content.
- [x] The code summary, source manifest and traceability follow, written by the lead after generation.
- Files: none at the workspace root.
- Traces: R-01, R-02, R-15; A1, A2, A3, A6; BR2.6; cicd §2.1, §2.5, §4.3, §5, §9.

## Traceability

| ID | Steps |
|---|---|
| FR2.1 | 3–4, 5–6, 7–8, 9–10, 13–14, 15–16, 21–22, 23–24, 26 |
| FR2.2 | 3–4, 11–12, 15–16, 21–22, 23–24, 26 |
| FR2.3 | 3–4, 5–6, 7–8, 11–12, 15–16, 21–22, 23–24, 26 |
| FR2.4 | 3–4, 5–6, 7–8, 13–14, 15–16, 17–18, 21–22, 23–24, 26 |
| FR2.5 | 3–4, 5–6, 7–8, 15–16, 17–18, 19–20, 21–22, 23–24 |
| BR1.1 | 9–10, 13–14, 15–16, 21–22, 23–24 |
| BR1.2 | 13–14, 15–16, 21–22 |
| BR1.3 | 3–4, 5–6, 7–8, 15–16, 23–24 |
| BR1.4 | 5–6, 7–8, 13–14, 15–16, 17–18 |
| BR1.5 | 3–4, 5–6, 7–8, 13–14, 15–16, 17–18, 23–24 |
| BR1.6 | 5–6, 7–8, 9–10, 13–14, 17–18 |
| BR2.1 | 15–16, 17–18 |
| BR2.2 | 15–16, 21–22, 23–24 |
| BR2.3 | 5–6, 11–12, 15–16 |
| BR2.4 | 11–12, 15–16 |
| BR2.5 | 3–4, 7–8, 15–16, 23–24 |
| BR2.6 | 5–6, 7–8, 17–18, 28 |
| BR3.1–BR3.2 | 5–6, 7–8, 15–16, 21–22, 23–24 |
| BR3.3 | 7–8, 15–16, 17–18 |
| BR3.4 | 7–8, 17–18 |
| BR3.5 | 5–6, 15–16 |
| BR3.6 | 3–4, 7–8, 15–16, 23–24 |
| BR3.7 | 15–16, 23–24 |
| BR4.1 | 5–6, 11–12, 13–14 |
| BR4.2 | 5–6, 7–8, 13–14, 17–18 |
| BR4.3 | 5–6, 13–14, 17–18 |
| BR4.4 | 13–14, 17–18, 23–24 |
| BR4.5 | 3–4, 7–8, 15–16, 23–24 |
| BR4.6 | 5–6, 17–18 |
| BR4.7 | 3–4, 13–14, 15–16, 17–18, 23–24 |
| BR5.1 | 5–6, 7–8, 15–16, 23–24 |
| BR5.2 | 7–8, 15–16, 21–22, 23–24 |
| BR6.1 | 19–20, 22 |
| BR6.2 | 5–6, 19–20, 22 |
| BR6.3–BR6.5 | 19–20 |
| BR7.1 | 7–8, 15–16, 21–22 |
| BR7.2 | 5–6, 13–14, 17–18, 19–20 |
| BR8.1 | 13–14, 21–22, 25–26 |
| BR8.2 | 15–16, 17–18, 21–22, 23–24, 25–26 |
| BR8.3 | 9–10, 15–16, 21–22 |
| NFR1.1 | 7–8, 15–16, 21–22 |
| NFR1.2 | 17–18 |
| NFR1.3 | 1, 21–22, 23–24 |
| NFR1.4 | 5–6, 19–20 |
| NFR1.5 | 7–8, 17–18, 19–20 |
| NFR2 | N/A: U6 sends no digests |
| NFR3.1 | 9–10 |
| NFR3.2 | 1, 9–10, 25–26 |
| NFR3.3 | 9–10, 25–26 |
| NFR3.4 | 5–6, 13–14, 21–22, 23–24 |
| NFR3.5–NFR3.6 | 13–14 |
| NFR3.7 | 5–6, 7–8, 9–10, 19–20 |
| NFR3.8 | 13–14 |
| NFR3.9 | 13–14, 21–22 |
| NFR4.1 | 5–6, 7–8, 15–16 |
| NFR4.2 | 3–4, 11–12, 13–14 |
| NFR4.3 | 13–14 |
| NFR4.4 | 13–14, 17–18 |
| NFR4.5 | 17–18 |
| NFR4.6 | 7–8, 13–14, 15–16 |
| NFR4.7 | 13–14, 17–18 |
| NFR4.8 | 5–6, 7–8, 17–18 |
| NFR4.9 | 17–18 |
| NFR4.10 | 1, 21–22 |
| NFR4.11 | 7–8, 15–16 |
| NFR5.1 | 23–24, 25–26 |
| NFR6.1 | 1, 27 |
| NFR6.2 | 21–22, 25–26 |
| NFR6.3 | 1, 13–14, 21–22, 25–26, 27 |
| NFR6.4 | 7–8, 15–16 |
| A1 | 3–4, 13–14, 15–16, 23–24, 28 |
| A2 | 3–4, 7–8, 15–16, 21–22, 23–24, 28 |
| A3 | 3–4, 7–8, 15–16, 21–22, 23–24, 28 |
| A4–A5 | 3–4, 15–16, 23–24 |
| A6 and A6 extension | 3–4, 13–14, 28 |
| A7 | 3–4, 15–16, 23–24 |
| A8 | 5–6, 19–20 |
| A9 | 3–4, 15–16, 23–24 |
| A10 | 3–4, 15–16, 23–24 |
