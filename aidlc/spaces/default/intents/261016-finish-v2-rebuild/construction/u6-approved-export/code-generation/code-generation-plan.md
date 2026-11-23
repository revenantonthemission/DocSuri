# U6 — Approved export · Code generation plan

Unit `u6-approved-export` · branch `feature/u6-approved-export` · scope express base · methodology test-after per component · strategy standard · existing suites stay green.

## Summary

- Builds: Build and Test loop-back 3 for U6 (Steps 53–63). The four unlisted store doubles are replaced by real database faults and realm rows, and the remaining wrappers and stand-ins are named under Allowed doubles. New checks cover when the lane recorded its last outcome and three hostile provider-text surfaces in jsdom. U6 gets its own Ruff configurations (E,F,I,UP,B at line length 100), every finding they report is fixed, and a lint gate checks them. Twelve decisions (L3-1 to L3-12); three of them, L3-5, L3-8 and L3-10, are yours to make.
- Touches: U6's tests under `tests/u6_approved_export/`: `store_flows.py`, `component/test_lane_write_path.py`, `operations/test_u6_real_export_checks.py`, `test_u6_preservation.py`, `repository/test_status_counts.py`, `operations/test_u6_test_volume.py`, a new `operations/test_u6_lint_gate.py`, and import order and line wraps across the tree. Three Vitest files in `frontend/test/u6-export/`. U6's five scripts (layout only). `.github/workflows/u6-approved-export.yml` and new `scripts/u6-lint*.toml` files. Under L3-10's default, line wraps in two U2 accounts files plus a regenerated `shared/python-consumers.json`. U6's records, including new Allowed doubles entries in `unit-test-instructions.md`. Steps 1–52 stay as built, and no production behaviour changes.
- Tests: 4 new backend tests (1 repository, 3 lint gate) and 3 new Vitest cases. 3 tests rewritten, the archive tests' fixture moved onto the realm, and 2 tests changed by lint fixes. Each new or changed test is run once with its behaviour withheld. Coverage phase goes from 945 to 949 tests, U6 Vitest from 120 to 123, and U2's cumulative lane from 728 to 731. Existing suites and the 80% floors stay as they are.

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
    },
    {
      "layer": "project",
      "text": "- U5's component lane needs its own fresh realm: a coverage pass exhausts the realm's authentication-attempt allocation, so the runner refuses a later lane on that realm. Preserve the refused realm as a failed prerequisite and re-run on a fresh one; never relabel it. Ruff format drift in files no step touched is recorded, not fixed, when CI runs ruff check only and a file must keep pinned bytes. (learned 2026-10-28) \n\n- Tick a Code Generation plan box only after the run its own text asks for has passed, including when restoring ticks after a new Plan Approval clears them. A box whose run is owed to ci.yml's macos-filesystem job, an installation or a browser lane stays open, with the owed run named in the code summary, because editing the plan's text voids its approval. Before a checkpoint, check every verified and not-yet-verified line in the code summary against the runs' start times and source digest. (learned 2026-11-14) \n\n- Before U8's realm runs, keep free disk less the realm database above J09's 20 GiB guard and never lower the guard: with the person's approval remove only stopped docsuri-u8-<id> containers and volumes and run Colima's fstrim twice (the second pass releases what the first misses), and if swap still leaves too little, copy the preserved folders out of /tmp and ask the person to restart the Mac. Run realm B (setup, migrate, fixtures --corpus skip, verification-run) without the operations lane, which runs alone on a fresh realm, record that move as a deviation while the approved instructions still put the lane on realm B, and wait about 90 s after each archive before the next setup. (learned 2026-11-14) \n\n- For local runs on this Mac, give every DocSuri test-tool command DOCKER_HOST=unix://$HOME/.colima/default/docker.sock and DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config, and confirm the run's containers through Colima's socket before recording any run or measurement as evidence, because OrbStack holds the default Docker socket after restarts. A test tool or child process that builds its own environment keeps DOCKER_HOST whenever its caller set it, and changing another Unit's tool for that waits for the person's answer. (learned 2026-11-14) \n\n- Before a record says a new or changed test catches its defect, run it once against the old code or with the awaited event withheld (edit, run, restore exactly), outside any recorded verification run, confirm the restore by digest or diff, and record the failure it gave. A test checked only by reading the code is recorded as not run and is not claimed to catch the defect. (learned 2026-11-14) \n\n- In every timing or capacity measurement on synthetic papers, give each run and each paper texts of their own, drawn from a seed derived from the measurement's token, the size and the run number, because repeated text adds no new vector to the HNSW index and makes later runs look fast. Count every run, the first included, and treat a slow first run as a finding to explain, never as a cold start to set aside. (learned 2026-11-14) \n\n- Make a DocSuri test tool's setup wait for PostgreSQL over TCP, the way its bootstrap and migrate connect, not on docker exec pg_isready over the container's Unix socket, which can pass against the image's socket-only init server. Until the U1, U2, U3 and U7 setups wait that way, check a refusal at their bootstrap or base-only migrate against the stopped container's log for the init-server restart, keep it as a failed prerequisite and rerun on a fresh environment, never relabelled. (learned 2026-11-14)"
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
  "input_sha256": "sha256:3990a78e27a36dd2a57fdaaf230108e8f4333f968cfea16c978632bf38e20457",
  "contract_sha256": "sha256:0aa10a7c0f0951b1d7a42d30f48c9f9dc63f93eef1125959651d5c864e8e6eca"
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

## Build and Test loop-back 1 (2026-10-28)

Build and Test's target check (`construction/build-and-test/test-results.md`, Target Verification Matrix and Loop-Back Log) found 2 of U6's targets Not Met and 19 that no test in a passed lane checks in full. Every U6 suite passed. You chose "Retry with fix" on 2026-10-27. The six targets owned by later stages (the hosted key folder, the error reporter, U8's logger levels, `pip-audit` in CI, the CI gate, U8's metrics) are not part of this loop-back. Steps 1–28 stay as built; Steps 29–43 are new and start unchecked. Each new check was drawn from the design section the target cites and from what the code and tests do today, and each was checked once more by a second reader before it was written here.

**Decisions:**

- **L1-1, the preview's destination is chosen from the current listing.** `ExportService.prepare_preview` (`backend/modules/export/service.py`) takes the request's `destinationId`, or `parentPageId` when A1's optional field is absent, as the *identity* of a listing entry, never as a request path. The server re-lists inside the one gated operation (`NotionAdapter.locate_destination`, `backend/modules/export/notion_adapter.py`: search first, probe only an id that the search returned, using the id from the search result), and the recorded destination, its title, context and the `bindingHash` come from that listing entry. Outside a complete listing answers `CONFLICT` (field `destination`); outside a partial or unavailable listing answers `DEPENDENCY_UNAVAILABLE`, never a definite refusal (BR1.5); `destinationId` and `parentPageId` that differ after normalisation answer `CONFLICT` before any Notion call. `ExportService._read_destination` is deleted (its only caller was this path; `BindingCheck` reads through `adapter.read_destination`, which stays). This amends the plan's A1 line in Step 21 ("`destinationId` is derived from `parentPageId`") to "the request's `destinationId` (or `parentPageId` when absent) names an entry of the connection's current listing; the recorded destination is that entry"; the amendment is recorded in the code summary, not by editing the approved step. Re-listing was chosen over a persisted listing table because it needs no migration and reuses `list_destinations`' search-plus-probe body.
- **L1-2, integration rigs run U4's real export read.** `tests/u6_approved_export/service_flows.py` gains `real_research(transactions)` (the `ResearchService` the host builds, through `scripts.u6_browser_fixtures.research_ports`) and `Rig.ready(*, authority=None)`, which produces one ready novelty result per conftest owner per realm through `ready_novelty`, cached run-bound in `realm.root / 'integration-novelty.json'` (mode 0600, refused when `runId` differs, rebuilt only after U4's one-hour artifact expiry). `http_flows.mount` and the integration callers of `lane_flows.build` hand the service that real instance; `ResearchDouble` stays reachable only from component rigs, for the five component cases (absent, changed, ineligible, unreachable, policy unresolved). `tests/u6_approved_export/integration/test_export_assembly.py` drops the `ExportRepository.due_items` stub and freshens both conftest owners instead. U4's allocation is four jobs per account, never reset: `UsageQuotaExceeded` on a long-lived development realm is a failed prerequisite, never a skip.
- **L1-3, the one real export stays operator evidence.** The press to `api.notion.com` (`U6:NFR6.3/real-export-approval`) cannot run in this stage: the conftest guard replaces `network_transport` for the whole run and no real token exists. Its matrix row keeps the vocabulary "Not runnable in this stage", with the runbook's §6–§8 evidence path (`u6-real-export-runbook.md`) and the six tests of `tests/u6_approved_export/component/test_real_export_gates.py` listed as the covering checks of the gating chain (BR8.2's non-human half). If you decline to run it at Build and Test, it moves to deployment-execution, where U8's provider gate and maintainer-only window govern the first real effect. No new status label is introduced.
- **L1-4, the `pending` connection state is pinned as unwatched today and flagged.** `export.status_counts` (`backend/modules/export/u6_maintenance.sql`) counts four connection states and omits `pending`, so the connection counts do not sum to `count(*)`. The new test pins exactly today's behaviour (`sum(connections) == count(*) - count(state='pending')`) and the gate records the omission. Only if you want `pending` counted does a new migration `backend/modules/export/u6_status_counts.sql` follow (applied files are never edited), appended to `MIGRATIONS` with `test_migrations_are_u5s_chain_then_the_four_u6_files` extended to the five-file tail.
- **L1-5, the check schedule is pinned as the code reads the design row.** `next_check_time` (`backend/modules/export/store_support.py`) places checks at 3, 10 and 30 minutes after the deadline, then every hour counted from the previous check (1h30 … 5h30, up to `check_hourly_until_seconds = 21600`), then every three hours (8h30 … 23h30), fourteen checks in all, the last at 84,600 s. The tests derive every expected point from the policy fields, so the recorded sequence lets you confirm the cadence. If the design meant on-the-hour points, the change is confined to `store_support.py` (the hourly branch) and these tests' expected lists. `check_hourly_until_seconds = 21600` is a value this plan records for approval at the U6 checkpoint; `test_export_policy.py` now freezes it by name.
- **L1-6, the oldest-unknown age counts from the latest attempt's deadline.** `status_counts` measures the oldest unknown effect from its latest attempt's `deadline_at` (the §8.6 comment in `u6_maintenance.sql`), while logical-components §8 says only "the age of the oldest unknown effect". The code's reading is pinned; the gate records it for you to accept or redirect to time-since-unknown.
- **L1-7, the SDK write timeout through the lane is the remaining time to `deadlineAt`.** Tech-stack decisions list `timeout_ms = 90000` for the write; through the lane the SDK's `timeout_ms` is the remaining time to the attempt's `deadlineAt`, at most 90,000 and floored at `MIN_WRITE_SECONDS` (`lane.py`), which the tech stack itself calls the bound that counts. Exactly 90,000 is asserted on `create_page(deadline_seconds=policy.write_deadline_seconds)` and 30,000 on reads; the lane fact (`deadline_at - started_at == 90 s`) is already pinned by `test_lane_write_path.py`.
- **L1-8, test counts above eight are recorded and kept.** The standard strategy's "five to eight tests per component" is checked by a component → test-file map (`tests/u6_approved_export/operations/test_u6_test_volume.py`) that fails on an unmapped file or a component below five definitions, and by runtime counts per JUnit classname (`testsByClass`, a new key in each phase evidence file of `scripts/verify_docsuri_u6.py`). A component above eight is recorded as above the range and kept; no test is removed or merged, because that would weaken checks and break "existing suites stay green". A file may be mapped under two components when it exercises both (`integration/test_lifecycle_projection.py` under ExportLifecycleParticipant and AccountAccessA8). `shared/python/tests/test_export_contract.py` runs in the shared contract suite, not a runner phase, so its count comes from that suite.
- **L1-9, the reflow fixtures change is a fixture-identity change.** Adding `reflow` to `SPECS` in `scripts/u6_browser_fixtures.py` changes `SCENARIO_NAMES`, so every environment whose `browser-fixtures.json` predates it is refused ("browser fixture identity differs") in the browser and coverage phases; those environments are archived with `--phase archive-owned` first. `FIXTURE_VERSION` stays `u6-browser-v1`, because the scenario comparison already guards identity. The settle dialog is measured at 320 CSS px inside `accessibility.spec.ts`'s existing settle journey by toggling the viewport to 320×640 for the measurement and restoring it, as U8's `expectReflowMain` does, rather than by a fourth clock-advanced settle under the 300 s browser bound. The measurement helper returns `{width, page, surface, offscreen, nested}` and every call compares it with `toEqual` against `{width: 320, page: false, surface: false, offscreen: false, nested: []}`, so the viewport guard runs on every real measurement and needs no test of its own; the nested walk inspects only descendants whose computed `overflow-x`/`overflow-y` is `auto`, `scroll` or `hidden` (today `.export-rendered`), skipping the visually-hidden boxes.
- **L1-10, the coverage floor stays a single-source rule.** `backend/.coveragerc.u6` keeps `fail_under = 80` and the fourteen-pattern include list, and the runner keeps passing no `--cov-fail-under`; the new operations tests pin that pytest-cov adopts the rcfile floor and that a shortfall fails the run. No file leaves the list, no `exclude_lines` is added, and the scan that no U6 test or migration names U2-only schema (`control_receipt`, `control_proof`, `current_restriction`, `lifecycle_state`, `flow_id`, `u2_controls.sql`) pins the fact the plan's coverage decision relies on.
- **L1-11, targets that belong to a later stage are named, not tested here.** `U6:NFR3.9/u8-logger-levels` (the hosted service never lowering `httpx`/`httpcore`) and the hosted key folder and U8's backup exclusion of `profile/export-keys/` belong to `u8-service-operations-integration` and deployment-execution; turning `status_counts` into U8 health and error-rate metrics belongs to U8's Build and Test; the 5-vs-8 worker-connection wording between logical-components §5 and `backend/u8_policy.py` is recorded as a note for U8, not a U6 fault. Nothing in this loop-back invents a test for them.
- **L1-12, the operator fixture may read export tables for negative assertions only.** `operator` (schema owner, `conftest.py`) reads `export.connection` including the envelope columns in hex and base64, for the key-material and plaintext scans, because the runtime role's column grants exclude `sealed_token` and `token_key_version`. It never seeds rows or bypasses a runtime grant to make a behaviour pass.

**Readings you can change at Plan Approval** (each is built as the decision above says unless you say otherwise):

- L1-1: the server re-lists at preview time inside the one gated operation (not a persisted per-connection listing table), and a `destinationId`/`parentPageId` mismatch answers `CONFLICT` rather than `INVALID_ARGUMENT` (both lie in prepare_preview's frozen list).
- L1-5: "then hourly, then every 3 h" is read as intervals counted from the previous check (1h30 … 5h30, then 8h30 … 23h30, fourteen checks), not on-the-hour points; `check_hourly_until_seconds = 21600` is frozen.
- L1-4: the short-lived `pending` reservation stays unwatched in `status_counts` (no new migration).
- L1-6: the oldest-unknown age is measured from the latest attempt's `deadline_at`.
- L1-3: the one real export is operator evidence under the runbook, at Build and Test if you run it then, else at deployment-execution; its matrix row stays "Not runnable in this stage".
- L1-8: a component with more than eight tests is recorded as above the range and never trimmed.
- L1-9: the settle dialog's 320 CSS px measurement happens inside the existing settle journey by toggling the viewport, not in a fourth clock-advanced settle; every existing U6 environment is archived before the coverage and browser phases because the fixture identity changes.
- The three optional cases (destination radios in Step 39a, erase during a scan in Step 36d, the `read_payload`-only source check in Step 36e) are built; say so if you want them dropped.

**Steps (test-after):**

- [x] **Step 29 — Record the decisions.** Write L1-1 to L1-12 into `code-summary.md` (deviations) and `traceability.json`, including the A1 restatement of L1-1 and the reading of Step 26's `reflow.spec.ts` bullet as "a 320 CSS px viewport across every U6 view, step state, the history and both dialogs, with a descendant walk for nested scroll containers and a viewport guard". The real-press target cites L1-3. No source changes, and no edit to the approved steps above. Trace: Build and Test loop-back 1.

- [x] **Step 30 — Repository — tests.** Add to `tests/u6_approved_export/repository/` (the realm is used; nothing is mocked):
  - (a) `test_owner_guard.py`, five tests: every one of the 19 owner-facing units (`read_connection` … `history`, `read_approval`) called with an ended session's `Authority` raises `InsufficientPrivilege` with the text `authority denied` and leaves `count(*)` of connection, preview_revision, approval, effect and replay_record unchanged (one test iterating closures, value objects built directly, snapshot taken once); an expired session and a session behind the account's `authority_revision` are refused and, restored, `transactions.guard` returns the account's revision; `local-research` consent set false refuses while a `personalization` consent granted true does not, and an inactive or unverified account refuses; another owner's session, a swapped pair and a `preauthentication` session never authorise this account while owner b still reads its own connection; a nonexistent account or session is refused with the same text. `store_flows.py` gains `expire_session` and `set_consent` beside `end_session`; rows are altered through `connect("accounts")` and restored in `finally`, the function-scoped `authority` fixture re-upserting them for the next test.
  - (b) `test_unknown_check_cadence.py`, three tests on a `flows.uncertain` effect (deadline = now + 90 s): `listing-incomplete` checks recorded at deadline+180, +600, +1800, +19800 move `next_check_at` to deadline+600, +1800, +5400, +30600 with the state `unknown` and `scanning_stopped_at` None, and `due_items(now, limit=100)` lists it by id at deadline+5400 but not at +5399; a `listing-incomplete` check at deadline+73800 sets `next_check_at` to deadline+84600, then a `not-found` check at deadline+84600 (no earlier `not-found` on that effect) stops scanning: `next_check_at` None, `scanning_stopped_at` set, `settlementOffered` True from the stop, no later due item, and a further check inserts a row but leaves `next_check_at` None; two `not-found` scans 120 s apart (under `settling_wait_seconds`) keep `unknown`, and a second `not-found` a settling interval later fails the export with `not-found-after-checks`, `settled_by == 'reconciliation'`, `ended_at` equal to that check time and `settlementOffered` False. `window_start` is any aware timestamp; the check time is the recorded `now`.
  - (c) `test_status_counts.py` (repository layer: every arrangement needs the repository's injected `now`), five tests with an injected clock `EPOCH` earlier than any other test's (1990-01-01) and baselines taken after `flows.connected` and before `bound`/`succeed`: a succeeded and a cancelled effect raise `succeededLast24h` and `cancelledLast24h` by exactly one at EPOCH+24h−1s and by zero at EPOCH+24h+1s; `oldestAcceptedSeconds == 1000` and `oldestUnknownSeconds == 910` at EPOCH+1000 (accepted at EPOCH; the unknown effect's attempt deadline at EPOCH+90); ages are None when no effect is in that state and `SELECT export.status_counts(NULL)` via `connect("export")` raises `InvalidParameterValue` (22023) naming the caller clock; connection counts follow connected → disconnected → revoked → unavailable one by one and `sum(connections.values()) == count(*) - count(state='pending')` with a `reserve_connection` row present (L1-4); the lane block is exactly `{outcome, observedAt}`, `record_lane_status` refuses an empty or 65-character outcome with `INVALID_ARGUMENT`, and the whole JSON holds no UUID, no `Synthetic` title and no account or connection id. Both owners are erased in `finally` so no 1990-dated due item survives.

  Trace: U6:NFR1.1; U6:NFR4.10/check-schedule; U6:logical-components:watch-counts.

- [x] **Step 31 — Business logic — implement.** The preview's destination comes from the listing (L1-1):
  - (a) `backend/modules/export/notion_adapter.py`: factor `list_destinations`' body into a private `_listing(...)` that runs the bounded search and the direct probe inside one gated `NotionSession.run` under `listing_budget_seconds`; `list_destinations` keeps its behaviour. Add `locate_destination(target, destination_id, *, creation_capability, gate_key) -> Listing`: search first, then probe only when the normalised id is among the search results, using `normalise_id(page["id"])` from the result; `last_destination_id`/`last_destination_readable` describe the chosen destination. No request path is built from the browser value.
  - (b) `backend/modules/export/service.py` `prepare_preview`: `_destination_identity(destination)` takes `destinationId`, else `parentPageId`, both through `normalise_id`; an unparsable value answers `invalid(<field>)`; both present and different answers `ExportError("CONFLICT", current={"field": "destination"})`. The real-activation `FORBIDDEN` check stays before any request. `_listed_destination` calls `locate_destination` with `StoredConnection(authority.account_id, row["id"])`, `creation_capability=row["creation_capability"]`, `gate_key=row["id"]` and maps: PROTECTION_UNAVAILABLE → `POLICY_UNRESOLVED` (field `credentialProtection`); TOKEN_INVALID or NOT_CONNECTED → `CONFLICT`; not listed and `listing.complete` → `CONFLICT`; not listed and incomplete → `DEPENDENCY_UNAVAILABLE`; listed but `readable is False` → `CONFLICT`; listed but readable None → `DEPENDENCY_UNAVAILABLE`; listed and readable → `destination_entry(...)` built from the listing item. Delete `ExportService._read_destination`. Every code stays inside `prepare_preview`'s frozen list.
  - (c) `tests/u6_approved_export/service_flows.py` `Rig.destination`: add `"destinationId": page_id`, so fixtures send what the browser's `destinationRequest` sends. No contract, migration or frontend change; the cancel destination's two counted page requests are unchanged because a search is not a page request.

  Trace: U6:security-design:browser-value-not-identifier; A1; BR1.5; BR2.2.

- [x] **Step 32 — Business logic — tests.** Add to `tests/u6_approved_export/component/`:
  - (a) `test_service_preview.py` (nine functions after the change): a page outside the current listing answers `CONFLICT` (field `destination`) when the listing is complete, with exactly one `/v1/search` entry after `configure()` and no `entry.path` carrying the id in 32-hex or hyphenated form, zero `preview_pair` rows and `fake.writes == []`, and answers `DEPENDENCY_UNAVAILABLE` when `set_search("partial", page_size=1)` or `set_search("unavailable")` hides it; `destinationId=A, parentPageId=B` is `CONFLICT` with no new request, `destinationId=A, parentPageId=A` previews, and the one `parentPageId`-only case previews with the same `previewId` at revision 2; the recorded destination comes from the listing entry (child of `rig.page("연구 노트")`, hyphenated ids and a browser title sent): 32-hex id, `title == "내보낼 곳"`, `context == "상위 페이지: 연구 노트"` (a direct read could only answer `상위 페이지 · <8 hex>`), every `/v1/pages/` and `/v1/blocks/` path in 32-hex form, `binding_hash` recomputed equal to `preview["bindingHash"]`. Extend `test_destination_refusals_and_the_real_allowance`: `rig.gate.asked` grows by exactly `[UUID(connection_id)]` per preview, hidden → `CONFLICT`, busy → `DEPENDENCY_UNAVAILABLE`, the successful preview's log holds `/blocks/<P>/children`, the real arm still `FORBIDDEN` with no request.
  - (b) `test_export_policy.py` (ten functions): replace the body of `test_the_synthetic_policy_holds_the_approved_operating_values` with a table keyed by the 13 NFR4.10 row names → field(s) and approved value (`len(table) == 13`, every field in `fields(ExportPolicy)`, `pending_takeover_seconds == 120`, `synthetic_only`, `reference()` kept); add the §9.1 budgets (30, 30, 30, 60, 300), D15 caps (2, 1), `key_lock_retry_ms`/`key_lock_wait_ms` (100, 5000), `token_max_length == 512 == TOKEN_MAX_LENGTH`, `pass_batch 10`, `housekeeping_batch 50`, `history_page_max 20`, `read_timeout_seconds <= page_read_budget_seconds`, and the `read budget`/`waiting lock` refusals; a fresh `ExportPolicy()` raises `FrozenInstanceError` on three assignments, `reference()` returns a fresh copy, `hash(SYNTHETIC_EXPORT) == hash(ExportPolicy())`; `real_activation_export(...)` differs from `SYNTHETIC_EXPORT` in exactly `{policy_id, activation_destination_id, free_terms_reference}` and `REAL_ACTIVATION_EXPORT is real_activation_export`; extend `test_inconsistent_values_are_refused` with the `match` text per row and add the positive small schedule `(1, 2, 3) / 4 / 5`.
  - (c) `test_check_schedule.py` (new, pure): the synthetic walk of `next_check_time` yields exactly `[180, 600, 1800, 5400, 9000, 12600, 16200, 19800, 30600, 41400, 52200, 63000, 73800, 84600]` then None, with gaps 3600 up to `check_hourly_until_seconds` and 10800 after; a late scan skips to the first point strictly after `now` (700 → 1800, 1800 → 5400, 19800 → 30600, 84600 → None, before the deadline → 180); a policy `(60, 120) / 300 / 900 / 600 / 2400` yields `[60, 120, 420, 720, 1320, 1920]` and a `check_total_seconds` equal to the last point still yields it.

  Trace: U6:security-design:browser-value-not-identifier; U6:NFR4.10/policy; U6:NFR4.10/check-schedule.

- [x] **Step 33 — Business logic — tests.** The Notion boundary, SDK settings and logging, in `tests/u6_approved_export/component/`:
  - (a) `test_guarded_transport.py`: the three spellings of the one origin pass (`https://api.notion.com`, `:443`, uppercase host) with one recorded request whose `url.host == 'api.notion.com'` and `url.port is None`; hosts that only contain or extend the origin (`api.notion.com.evil.example`, `evil.example/api.notion.com/...`, `api.notion.com.`, `1.2.3.4`, `[::1]`) raise `RequestRefused` with `fake.requests == []`; an inner `AsyncBaseTransport` that raises `AssertionError('connected')` is never reached for `http`, a foreign host, a malformed page id and an unexpected query parameter.
  - (b) `test_notion_session.py`: a malformed destination (`../v1/users`, `'0'*31`) answers `DestinationRead(NOT_READABLE, readable=False)` and a malformed `read_back` page answers `ReadBack(COULD_NOT_CHECK)` with no request and no pace slot; `sdk.users.list()` (GET `/v1/users`, outside `ALLOWED_PATHS`) gives `COULD_NOT_CHECK` with `CAUSE_TRANSPORT`, no request and a plain `Verdict` (walk: no `BaseException`, no token); every client's `sdk.logger is SDK_LOGGER` named `docsuri.export.notion_sdk` at WARNING, `propagate False`, handlers exactly `[NullHandler]` before and after two runs, and `logging.getLogger('notion_client').handlers == []`; a capturing handler attached directly to `SDK_LOGGER` (level untouched) captures nothing across one success and one 500 while the root is at DEBUG, no record named `docsuri.export.notion_sdk` or `notion_client` reaches `caplog`, and `api.notion.com` is absent from `caplog.text`; a `SDK_LOGGER` lowered to DEBUG is reset to WARNING by the next client; every client carries `notion_version == '2026-03-11'`, `retry is False`, `timeout_ms == 30_000`, header `Notion-Version`, `client.timeout == httpx.Timeout(30.0)`, `follow_redirects False`, `trust_env False`.
  - (c) `test_export_composition.py`: under `contribution(transactions, fake=fake)` one `identify` emits no record whose name starts with `httpx` or `httpcore`, `api.notion.com` is absent from `caplog.text`, `logging.getLogger('httpx').level >= WARNING`, and the fake recorded `/v1/users/me`.
  - (d) `test_notion_adapter.py`, with a recording transport (an `AsyncBaseTransport` that stores `Notion-Version`, `request.extensions['timeout']` and the JSON body, then delegates to the fake inside `GuardedTransport`): every header is `2026-03-11`, GET `/v1/users/me` carries `{'connect': 30.0, 'read': 30.0, 'write': 30.0, 'pool': 30.0}` and POST `/v1/pages` under `deadline_seconds=policy.write_deadline_seconds` carries 90.0 in all four (L1-7); the create body's top-level keys are exactly `{parent, properties, children}` with `parent == {'page_id': destination}` and the bound content's blocks; with `set_search('complete', page_size=2)` and three pages, each `/v1/search` body has `page_size == 100`, the first no `start_cursor`, each later one the previous `next_cursor`, and `listing.complete is True`.
  - (e) Lift `walk` and `assert_clean` from `test_token_exposure.py` into `tests/u6_approved_export/notion_flows.py` (the exposure test imports them from there; no `test_*` module is imported). New `test_provider_text.py`, four tests: a hostile title (`<img src=x onerror=alert(1)>{0}{token} ` + 5000 chars) lists as `hostile.strip()[:2000]` unchanged, the child's context is the literal `상위 페이지: {secret}`, the direct read's context `상위 페이지 · <8 hex>`, a non-string title gives `page_title(...) is None`, and the entry validates on the wire through `ExportService.list_destinations`; titles shaped like an id, a URL or a path appear only in `entry.title` and in no request path; `_page_url` returns None for `javascript:`, `http://www.notion.so/x`, `https://notion.so.evil.example/x`, `https://x.notion.site/abc`, `https://www.notion.so/` and `7`, and the string for the four valid hosts, and a successful `create_page`'s `remote_url` fullmatches `_NOTION_URL`; a 500 whose body message is `<script>sentinel</script>` leaves `Verdict`'s fields exactly `{category, refusal, retry_after, request_id, committed_page_id, cause}` with no `sentinel` in `repr`, and after a 403 create `synthetic answer` appears nowhere in `walk(result)`, the provider result, the provider outcome or `to_jsonb(row)::text` of the owner's effect and attempt rows.
  - (f) New `test_log_content.py`, three tests: a `Faulty(OwnDue)` store whose `sweep_orphans` raises `OperationalError('store down: synthetic-secret-detail')` produces exactly one `docsuri.export.worker` record `export pass step orphans failed (OperationalError)`, no `exc_info`, no exception in `record.args`, and no `synthetic-secret-detail` in `caplog.text`; a rig with `write_deadline_seconds=1, read_timeout_seconds=1, page_read_budget_seconds=1, read_back_budget_seconds=1, in_flight_per_owner=len(FAILURES)` pressing one effect per `test_token_exposure.FAILURES` answer (queued on `pages.create` and four times on `pages.retrieve`) emits no record named `docsuri.export*`, with the token, `synthetic answer`, `api.notion.com` and every fake page id absent from `caplog.text`; the sweep of `export.effect`, `export.attempt JOIN export.effect` and `export.lane_status` by the owner's account holds none of those strings, every `provider_request_id` fullmatches `classification._REQUEST_ID` and every `remote_url` fullmatches `_NOTION_URL`.

  Trace: U6:NFR3.8/origin-and-identifiers; U6:NFR3.8/provider-text; U6:NFR3.9; U6:tech-stack-decisions:sdk-configuration; U6:security-design:log-content.

- [x] **Step 34 — Business logic — tests.** Token custody and the real-export gating chain, in `tests/u6_approved_export/component/`:
  - (a) New `test_plaintext_lifetime.py`, five tests: after `rig.configure()` and `gc.collect()`, a walk from `rig.service`, `rig.repo`, the adapter, session, vault and keyring that descends only into builtin containers, dataclasses and objects whose type's `__module__` starts with `backend.modules.export` or `backend.u6`, stopping at `FakeNotion`, `OwnerTransactions`, modules and types, finds no string equal to or containing the token, and `view`/`rig.connection()` carry none; one `session.run` records `Authorization == 'Bearer ' + token` while running, the one `httpx.AsyncClient` seen by a wrapped `aclose` is closed afterwards, `assert_clean([result], token)` holds, the session holds no client, and after `replace_token` the next run sends only the new bearer; the stored row's `sealed_token` holds the token in no encoding (`operator` fixture, L1-12), `token_key_version == envelope_version(...)`, the vault opens it with `(account_id, connection_id, revision)` and refuses `revision+1` with `envelope-unopenable`; two refused configures (500 → `DEPENDENCY_UNAVAILABLE`, 401 → `INVALID_TOKEN`) leave no token in the errors, their `__cause__`/`__context__` None, in `export.connection` (operator), `export.replay_record`, `export.connection_pace`, `caplog` or the composition walk; `CandidateToken` and `StoredConnection` omit the value from `repr`/`str` while `asdict` carries it, and an empty value or a non-UUID id raises with a message naming no value.
  - (b) New `test_free_terms_evidence.py`, four tests: `free_terms_reference` is `notion-free:<checkedOn>:` + sha256 of the canonical JSON, changes with the date, a changed or added limit, is stable under key order, and `real_activation_export(activation_destination_id=..., free_terms_reference=reference)` accepts it (public constructor); `real_export_factory(activation, transport_factory=lambda: fake)(...)` assembled over the realm (never configured; its keyring points at the realm's folder) carries `policy.free_terms_reference == activation.free_terms_reference`, `policy_id == 'u6-real-activation'`, capabilities `modeIds == ['real-bounded']` and `policy == policy.reference()`, and `activation.free_terms` equals the normalised four-key record exactly; a `RealExportActivation` with reference `''`, `'with space'`, `'x'*257` or `'notion-free:2026-10-19:é'` is refused `POLICY_UNRESOLVED` (field `policy`) by `real_policy` and by `assemble_u6_real(stub_profile(tmp_path), ...)` before a monkeypatched `assemble_u5` runs, and `tmp_path` gains no file; `load_activation` reads only the 0600 settings file (a `DOCSURI_FREE_TERMS` decoy is ignored), a deleted file is `settings-absent`, a symlink named `real-export.json` is `settings-custody`.
  - (c) New `test_real_export_gates.py`, six tests over `lf.build(..., keys='real-keys', policy=real_policy(parse_activation(settings(runId=realm.run_id, activationDestinationId=page), realm, today=TODAY)))` (keys under `tmp_path`, never the realm's folder; each test uses the fewest requests because `REAL_MINIMA` paces at 500 ms): the factory's `keywords['policy'] == lr.rig.policy` and its assembled capabilities equal `[{'modeIds': ['real-bounded'], 'policy': policy.reference(), ...}]`; under the real policy only the activation entry is writable, `destinationScopeIds == [page]`, a preview on another page is `FORBIDDEN` with no request, `fake.writes == []` after listing, preview and approval, and an own-step pass with nothing bound writes nothing; one approved export run through `lr.lane.run_item(lf.item(effect))` writes exactly one page under the activation page (`pages_under(page)` has one entry, `pages_under(other)` none), `writes[0].content_hash == preview['renderedContentHash']`, the attempt row has `path_kind == 'real'` and `response_class == 'created'`, the effect `succeeded`; an execute with a random approvalId is `NOT_FOUND`, with another preview's bindingHash `CONFLICT`, an approve with `explicitApproval False` `INVALID_ARGUMENT`, and approval/effect counts and `fake.writes` are unchanged; a replayed execute returns the original effect, a second approve is `CONFLICT`, a second `run_item` is `skipped`, one write and one attempt remain; `scripts.u6_real_export.outcome(...)` reports `pathKind 'real'`, `outcomeClass 'created'`, `effectState 'succeeded'`, 64-hex digests and no plaintext `remote_url`, request id or token.

  Trace: U6:security-design:plaintext-lifetime; U6:NFR6.2/free-terms-evidence; U6:NFR6.3/real-export-approval (gating chain; the press itself per L1-3).

- [x] **Step 35 — API / endpoint — implement.** Test support only; no file under `backend/` changes (L1-2):
  - (a) `tests/u6_approved_export/service_flows.py`: `build(..., research=None)` keeps `ResearchDouble` when None; `real_research(transactions)` returns `scripts.u6_browser_fixtures.research_ports(transactions)[0]`; `Rig` gains `transactions` and `ready(*, authority=None)` (double → `self.research.ready()`; real → `ready_novelty(transactions, authority or self.authority, known)` with `known` read from and written to `realm.root / 'integration-novelty.json'`, mode 0600, `{runId, accounts: {accountId: reference}}`, refused on a foreign `runId`); `preview_value(page, source, *, authority=None)` uses it.
  - (b) `tests/u6_approved_export/http_flows.py` `mount` defaults `options['research']` to `real_research(transactions)`; `lane_flows.build(..., research=...)` passes it through; `integration/test_lane_transactions.py`, `test_session_housekeeping.py` and `test_account_purpose.py` pass `research=sf.real_research(transactions)`; component callers are unchanged.
  - (c) `integration/test_interactive_admission.py`: `preview_body(m, page, connection, authority)` builds its source with `m.rig.ready(authority=authority)`; B's preview passes `m.other_authority`, A's `m.authority`.
  - (d) `integration/test_export_assembly.py`: drop the `due_items` monkeypatch and the `ExportRepository` import; take `connect`, `authority`, `authority_b` and run `store_flows.fresh` for both before `assemble_u6`.
  - (e) `tests/u6_approved_export/export_rows.py`: `participant_tickets(connect, account, action, scopes)` returning the per-scope dicts `ExportLifecycleParticipant.apply` takes (lifted from `component/test_export_lifecycle.py` `seed`; the existing `lifecycle_ticket` is left alone). `lane_flows.py`: `on_write(fake, callback, *, method='POST', path='/v1/pages')`; `RunDepth` (a delegating wrapper around `transactions.run` recording entry/exit depth and thread name); `ConnectionSampler` (a thread polling `pg_stat_activity` for `application_name LIKE 'docsuri-approved-export-%-export'` through a raw `connect('export')` session).

  Trace: U6:unit-test-instructions:never-mocked; L1-2.

- [x] **Step 36 — API / endpoint — tests.** Add to `tests/u6_approved_export/integration/`:
  - (a) New `test_real_research_rig.py`, five tests: `m.rig.research`, `m.rig.service.research` and the lane rig's pass hold the same `ResearchService` instance, `ready()` yields a reference that `readNoveltyArtifactForExport` answers `ready` with `ownerId == str(m.authority.account_id)`, and a second `ready()` returns the same reference; a press on that result is written by the lane from U4's output (one write, `source_content_hash`/`source_revision` equal to the reference's, `rendered_text` containing text from the prepared output, whose field name is confirmed once against the provider's output before the assertion is written); B posting A's reference is `NOT_FOUND` with no page read afterwards and A's own preview still succeeds; a housekeeping pass reaches the real service for this account's approval (a delegating recorder records `(Authority(account, approving_session), reference)`) and leaves it `approved`, `invalidation_reason` None, its revision untrimmed; the known reference is reused by a second rig without a new job, a stale entry is rebuilt, and a foreign `runId` file is refused. `test_export_assembly.py` keeps its assertions and adds: `export.lane_status.outcome`, when a row exists, is one of the lane's categories, and no connection, preview_pair, approval, effect or replay_record row of either conftest owner remains.
  - (b) `test_export_http.py`: an unlisted destination (`destinationId == parentPageId == uuid4().hex`) through `prepare-export-preview` is HTTP 409 `CONFLICT`, `current.field == "destination"`, in `OPERATION_ERRORS["prepare_preview"]`, with no fake path carrying the id, a following listed preview answering 200 (slot released) and `fake.writes == []` (source prepared through `Rig.ready()`, never the double). Extend `test_no_token_appears_in_any_response_or_stored_record_after_failures`: a configure body with an unexpected field holding a sentinel (422) and a foreign `effectId` (404) leave no record named `docsuri.export*`, no record with `exc_info`, and the sentinel absent from `caplog.text`.
  - (c) `test_lane_transactions.py`: with `Answer.slow(1)` on `pages.create`, `max(samples) <= 1` from the sampler and `RunDepth.max_depth == 1` with at least four calls from the thread `docsuri-export-lane`, one write; the same bound during a scan (`blocks.children` slow 0.5 s) with exactly one `reconciliation_check` row and an outcome starting `scan-`; `transactions.run('export', lambda conn: conn.remaining()) <= 5.0`, `<= 0.5` under `work_budget(0.5)`, and `lane.UNIT_SECONDS == 5.0`.
  - (d) New `test_lifecycle_in_flight.py`, four tests: an erase (`live_records` then `external_copies`) applied from `on_write` while the create is in flight leaves the page in Notion, no effect or attempt row, zero rows in the five account tables, `exports_in_flight == 1` and `pages_possibly_created == 1` in the counts, the status row `skipped` with `observed_at` later than the pre-start baseline, no `ended early` record, the lane `running` and `idle` (wait on `len(fake.writes) == 1 and lr.lane.idle`, never on the singleton status row alone); a `SAVED_BUSY` create with a `withdraw` ticket applied in flight gives one `uncertain` attempt, no read-back request after the ticket (the envelope cannot open), a `disconnected` connection with `open_token_envelope` None, the effect `unknown` with `settlementOffered False`; a plain create with a `withdraw` in flight finishes `succeeded`, `settled_by == 'provider'`, the connection `disconnected` at the withdrawn revision with `creation_capability` unchanged (`last_destination_id` may be set), the approval `consumed`; an erase during an in-flight scan records no check.
  - (e) New `test_export_body_bounds.py`, four tests: a 65,536-byte body to `read_connection` passes (`NOT_FOUND` before a connection, 200 after) and 65,537 bytes is 422 `INVALID_ARGUMENT` with the frozen `wire.Error` shape and `Cache-Control: no-store`, the fake untouched; on `assemble_u6(realm)` under `TestClient`, 65,537 bytes is 413 `INVALID_ARGUMENT` with `messageKey == 'request.tooLarge'` before routing and 65,536 bytes is 401 `UNAUTHENTICATED`; a raw-ASGI `receive` that waits 5.3 s mid-body is 504 `DEADLINE_EXCEEDED`, no connection is created and `fake.requests == []` (the one real wait this stage allows); `read_payload(` appears once in `backend/modules/export/http.py` and no `request.json/body/stream/form(`.

  Trace: U6:unit-test-instructions:never-mocked; U6:security-design:browser-value-not-identifier; U6:security-design:log-content; U6:logical-components:lane-connection-bound; U6:security-design:lifecycle-in-flight; U6:NFR1.3.

- [x] **Step 37 — Environment/build configuration — implement.**
  - (a) `scripts/verify_docsuri_u6.py` `junit_counts`: add one evidence key `testsByClass`, a dict sorted by key of `<testcase classname>` → count built with `collections.Counter` over the same cases, in every phase evidence file. `safe_phase_summary`, the exit-code rules and `MAX_LOG` are unchanged.
  - (b) `scripts/u6_browser_fixtures.py`: add `"reflow": "재배치"` to `SPECS`, so `reflow.spec.ts` gets its own cancel and settle destinations; update the docstring. This is a fixture-identity change (L1-9): existing environments are archived before the coverage or browser phase; `FIXTURE_VERSION` stays `u6-browser-v1`.

  Trace: U6:code-generation-plan:testing-contract-test-volume; U6:NFR5.1/reflow.

- [x] **Step 38 — Environment/build configuration — tests.** Add to `tests/u6_approved_export/operations/`:
  - (a) New `test_key_never_elsewhere.py`, five tests: after `rig.configure()` and a rotate under `holding()`, no encoding (stored base64, unpadded, urlsafe, hex) of any retained key from the test's own `tmp_path` key file appears in `to_jsonb(t)::text` of any `export` table or in `encode(sealed_token, 'hex'/'base64')` (operator fixture, L1-12), and `token_key_version` values match `token_keyring.VERSION`; across first start, seal, open, two rotates, a retire, a refused rotate and a 0644 key file, no encoding appears in `caplog.text` (every logger at DEBUG), `str(vars(record))`, the rotate/retire dicts, `KeyOperationRefused.counts`, `repr(error)` or `str(vars(error))`, and `str(error)` equals its category (a local two-line witness stub); a key file rewritten to its own text minus the final brace refuses `key-custody-broken` with `__cause__` and `__context__` None, no key encoding in any `tb_frame.f_locals` or `repr(error)`, and the folder listing unchanged; `git ls-files -z` at the repository root lists no path with basename `KEY_FILE`, `LOCK_FILE`, `MARKER_FILE`, matching `STAGING_NAME` or containing `export-keys/`, `RUN.is_relative_to(RUN_PARENT.resolve())` and not `REPOSITORY`, and `(RUN / KEY_FOLDER)` under `RUN_PARENT.resolve()`; after load, four rotates, a retire and `create_after_loss`, the folder lists exactly `[KEY_FILE, LOCK_FILE, MARKER_FILE]`, `st_nlink == 1`, no staging file, and `tmp_path` holds only `export-keys`.
  - (b) New `test_coverage_contract.py`, five tests, no realm: `coverage.Coverage(config_file='backend/.coveragerc.u6').config` has `fail_under == 80.0`, `source == ['backend', 'scripts']`, `report_include` equal to the fourteen patterns, `report_omit == ['scripts/verify_docsuri_u6.py']`, `show_missing` and default `exclude_lines`; a `tmp_path` package with one uncovered function under an rcfile `fail_under=100` makes `python -m pytest --cov=pkg --cov-config=<rc>` (no `--cov-fail-under`) exit nonzero with `Coverage failure: total of` and `fail_under=1` exits 0; `phase_command('coverage', ...)` carries `--cov`, `--cov-config=backend/.coveragerc.u6`, `--maxfail=1`, the single `TEST_ROOT` and no `--cov-fail-under`, and `preservation_report(time.monotonic())` with `bounded_process` monkeypatched to capture args and `RUN` pointed at a 0o700 `tmp_path` folder passes `--rcfile=backend/.coveragerc.u6`, `--include=scripts/u6_preservation.py`, `--fail-under=80` and reports `linePercent` None without a log; no file under `tests/u6_approved_export` or `backend/pytest.u6-approved-export.ini` names the U2-only identifiers (built from parts), `MIGRATIONS` has no path ending `u2_controls.sql` and every entry is a U5-chain or U6 file; `execute_phase('coverage', ...)` with `exitCode 1` records `coverageTotalPercent` and no `preservationReport`, with `exitCode 0` includes it. A local `owned_root` fixture is defined.
  - (c) `test_u6_real_export_checks.py` (seven tests after): `operator.outcome(...)['freeTermsReference']` equals `free_terms_reference(json.loads(file)['freeTerms'])` recomputed from the settings file on disk, starts with `notion-free:2026-10-19:`, and `json.dumps(record)` carries no `publishedLimits` string, no `memberCount` and no `plan` key.
  - (d) `test_u6_runner.py`: `junit_counts` on a 0o600 JUnit file with four cases over two classnames (one failure, one skipped) reports `tests 4, failures 1, skipped 1, errors 0`, `testsByClass == {classA: 3, classB: 1}`, `exitCode 1`, and `safe_phase_summary` carries the totals but not `testsByClass`; an empty `<testsuites/>` gives `tests 0`, `{}`, `exitCode 1`; a missing report sets `missingTestReport`; a malformed one `invalidTestReport`. `test_u6_browser_fixtures.py`: add `reflow` to the spec tuple and `len(seen) == 8`; a record carrying the previous three-spec `scenario` is refused with `identity differs`.

  Trace: U6:NFR3.2/key-never-elsewhere; U6:code-generation-plan:testing-contract-coverage-backend; U6:NFR6.2/free-terms-evidence; U6:code-generation-plan:testing-contract-test-volume; U6:NFR5.1/reflow.

- [x] **Step 39 — Frontend — tests.** In `frontend/test/u6-export/` and `frontend/e2e/u6-approved-export/` (strict TypeScript, no `any`, Korean copy):
  - (a) One hostile-text case each: `destination-step.test.tsx` renders `entry({ title: '<img src=x onerror="x">', context: '<b>{{x}}</b>' })` as text (`textContent` contains both literals, `queryByRole('img')` and `container.querySelector('img, b')` null); `preview-step.test.tsx` renders `destination = entry({ title: '<svg onload=x>제목</svg>', context: '<i>위치</i>' })` as text under `preview-destination`; `export-view.test.tsx` renders `connection({ workspaceName: '<svg onload=x>팀</svg>' })` as text under `connection-workspace`. `status-accessibility.test.tsx` gains its fifth case: `refusalText` prefers the operation table, then `dispositionCopy('CAPACITY_EXHAUSTED')`, then `문제가 발생했어요`, and `refusalCode` returns `CAPACITY_EXHAUSTED` for the `ApiError` and null for a plain `Error`. `destination-step.test.tsx` also asserts no `textbox` is rendered and every `destination-radio` value is a listing entry's `destinationId`.
  - (b) `helpers.ts`: widen the `specs` union with `'reflow'`; move `expectReflow` here as `expectReflowAt320(page, testId)` returning `{width, page, surface, offscreen, nested}`, where `nested` names (by `data-testid`, else tag and className, never content) every descendant whose computed `overflow-x`/`overflow-y` is `auto`, `scroll` or `hidden` and whose `scrollWidth > clientWidth + 1`, skipping `.export-visually-hidden`, `.visually-hidden` and `clientWidth === 0`; every caller compares with `toEqual({width: 320, page: false, surface: false, offscreen: false, nested: []})`. Add `withViewport320(page, fn)` (320×640, `try/finally` restore to 1280×720).
  - (c) `reflow.spec.ts`, three tests at 320×640: the export view disconnected with the connect form, after a field error (`connect-token` = `' '`), connected, and with the disconnect dialog open; the flow at the destination list, the ready preview (`preview-rendered` containing `docsuri-export:v1:`; the `.export-rendered` nested scroller is inspected) and a succeeded outcome with its page link; an accepted outcome on `scenario.specs.reflow.cancel` with `outcome-signout-note` and `outcome-cancel` visible, its cancellation, and the history row (`export-view` and `history`). Only the state needed to reach each surface is asserted; fixture facts are not. `accessibility.spec.ts`'s third test additionally measures, inside `withViewport320`, `export-flow` in `확인 중` with `outcome-next-check`, `export-view` once `history-settle` is offered, and `settle-dialog` with no choice, with `settle-link` holding the invalid link and `settle-link-error` visible, and after `settle-not-delivered` with `settle-assumption` visible, asserting focus stays inside the dialog across the resize.
  - (d) `frontend/src/u6-export/export.css` changes only if the walk names a sideways scroller, and then by wrapping (`overflow-wrap`, `white-space`), never by hiding overflow.

  Trace: U6:NFR3.8/provider-text; U6:NFR5.1/reflow; U6:code-generation-plan:testing-contract-test-volume; U6:security-design:browser-value-not-identifier.

- [x] **Step 40 — Environment/build configuration — tests.** The last code step: new `tests/u6_approved_export/operations/test_u6_test_volume.py`, no realm, four tests over module-level `COMPONENT_FILES` (the 20 components of logical-components §1 plus an `EnvironmentTool` group → files under `tests/u6_approved_export/<layer>/`, a file allowed under two components when it exercises both), `EXTERNAL_FILES = {'SharedContractAmendments': ['shared/python/tests/test_export_contract.py']}` and `FRONTEND_FILES` (each `src/u6-export` module → its `frontend/test/u6-export/*.test.ts(x)` files; `copy.ts` and `export.css` excluded): every walked `test_*.py` is mapped at least once, every mapped and external path exists, and the shared files are exactly the declared set; every component's `ast` count of `test_` definitions (external included) is `>= 5`, InteractiveGate and ExportWorker asserted by name; the six named key boundaries and the two further integration files exist with `>= 1` test; every frontend module counts `>= 5` `it(`/`test(` lines, every Vitest file is mapped, and the four Playwright specs exist with `>= 1 test(` and no per-component floor. Every file Steps 30–39 added is listed here. Trace: U6:code-generation-plan:testing-contract-test-volume; L1-8.

- [x] **Step 41 — Configuration and measurement.** Confirm the additions already written into `unit-test-instructions.md` (its section "Build and Test loop-back 1") match what Steps 30–40 built, and record any difference in `code-summary.md` rather than editing the approved instructions. Archive every existing U6 environment (`--phase archive-owned`; the fixture identity changed in Step 37). On a fresh realm run `setup`, `migrate`, `coverage` (with the second report) and `frontend`; Steps 30–40's tests keep the backend total, `scripts/u6_preservation.py` and `src/u6-export` at or above 80%. No floor changes, no file leaves `.coveragerc.u6`; record the total and each measured U2 file's percentage beside it. Trace: U6:code-generation-plan:testing-contract-coverage-backend; L1-10.

- [x] **Step 42 — Process evidence.** Record in `code-summary.md`:
  - each component's test count, file by file, from the collect-only run and from the phase evidence files' `testsByClass` joined with `COMPONENT_FILES`/`FRONTEND_FILES`, against the standard strategy's five to eight, counts above eight marked "above range, kept" (L1-8); `SharedContractAmendments` from the shared suite; Playwright's junit classname confirmed from a real `browser.xml`, with the static count as the fallback for that phase only;
  - the 19 Unverified and 2 Not Met targets mapped to the tests that close them (the traceability rows of this loop-back), the real press recorded as operator evidence per L1-3;
  - the collect-only total;
  - the readings the gate must weigh: the `pending` connection count (L1-4), the check-schedule cadence (L1-5), the oldest-unknown age (L1-6);
  - the layer order, as the plan's ticked steps show it.

  Trace: Testing Contract (strategy volume, runner step, scope floor, methodology).

- [x] **Step 43 — Run, record and review.** Run U6's lanes on fresh realms:
  - `coverage` and `frontend` on realm A, then `archive-owned`;
  - `browser` on its own fresh realm B, every spec passing, as the Construction Verification Command;
  - `tsc --project tsconfig.u6-export.json --noEmit`, U6's ESLint command (including `e2e/u6-approved-export`), and Ruff on the cicd §2.3 targets plus every U6 script;
  - the earlier units' regressions and U2's cumulative lane, since `test/u6-export` is registered in it.

  Then update `code-summary.md`, `traceability.json` and `source-manifest.json`, get a fresh architecture review of this attempt, and run U6's checkpoint. Trace: stage Steps 5 and 6.

**Loop-back traceability** (target → the file that closes it → step):

| Target | Closed by | Steps |
|---|---|---|
| U6:NFR1.1 | `tests/u6_approved_export/repository/test_owner_guard.py` | 30 |
| U6:NFR4.10/check-schedule | `tests/u6_approved_export/component/test_check_schedule.py`; `tests/u6_approved_export/repository/test_unknown_check_cadence.py` | 30, 32 |
| U6:logical-components:watch-counts | `tests/u6_approved_export/repository/test_status_counts.py` | 30 |
| U6:security-design:browser-value-not-identifier | `backend/modules/export/service.py`; `backend/modules/export/notion_adapter.py`; `tests/u6_approved_export/component/test_service_preview.py`; `tests/u6_approved_export/integration/test_export_http.py` | 31, 32, 36 |
| U6:NFR4.10/policy | `tests/u6_approved_export/component/test_export_policy.py` | 32 |
| U6:NFR3.8/origin-and-identifiers | `tests/u6_approved_export/component/test_guarded_transport.py`; `tests/u6_approved_export/component/test_notion_session.py` | 33 |
| U6:NFR3.8/provider-text | `tests/u6_approved_export/component/test_provider_text.py`; `frontend/test/u6-export/destination-step.test.tsx`; `preview-step.test.tsx`; `export-view.test.tsx` | 33, 39 |
| U6:NFR3.9 | `tests/u6_approved_export/component/test_notion_session.py`; `tests/u6_approved_export/component/test_export_composition.py` | 33 |
| U6:tech-stack-decisions:sdk-configuration | `tests/u6_approved_export/component/test_notion_session.py`; `tests/u6_approved_export/component/test_notion_adapter.py` | 33 |
| U6:security-design:log-content | `tests/u6_approved_export/component/test_log_content.py`; `tests/u6_approved_export/integration/test_export_http.py` | 33, 36 |
| U6:security-design:plaintext-lifetime | `tests/u6_approved_export/component/test_plaintext_lifetime.py` | 34 |
| U6:NFR6.2/free-terms-evidence | `tests/u6_approved_export/component/test_free_terms_evidence.py`; `tests/u6_approved_export/operations/test_u6_real_export_checks.py` | 34, 38 |
| U6:NFR6.3/real-export-approval | `tests/u6_approved_export/component/test_real_export_gates.py` (gating chain); the press itself: operator evidence per `u6-real-export-runbook.md` §6–§8 (L1-3) | 34 |
| U6:unit-test-instructions:never-mocked | `tests/u6_approved_export/service_flows.py`; `http_flows.py`; `lane_flows.py`; `tests/u6_approved_export/integration/test_real_research_rig.py`; `test_export_assembly.py` | 35, 36 |
| U6:logical-components:lane-connection-bound | `tests/u6_approved_export/integration/test_lane_transactions.py` | 36 |
| U6:security-design:lifecycle-in-flight | `tests/u6_approved_export/integration/test_lifecycle_in_flight.py` | 36 |
| U6:NFR1.3 | `tests/u6_approved_export/integration/test_export_body_bounds.py` | 36 |
| U6:NFR3.2/key-never-elsewhere | `tests/u6_approved_export/operations/test_key_never_elsewhere.py` | 38 |
| U6:code-generation-plan:testing-contract-coverage-backend | `tests/u6_approved_export/operations/test_coverage_contract.py`; `backend/.coveragerc.u6` (unchanged, pinned) | 38, 41 |
| U6:NFR5.1/reflow | `frontend/e2e/u6-approved-export/reflow.spec.ts`; `helpers.ts`; `accessibility.spec.ts`; `scripts/u6_browser_fixtures.py`; `tests/u6_approved_export/operations/test_u6_browser_fixtures.py` | 37, 38, 39 |
| U6:code-generation-plan:testing-contract-test-volume | `scripts/verify_docsuri_u6.py` (`testsByClass`); `tests/u6_approved_export/operations/test_u6_runner.py`; `test_u6_test_volume.py`; `frontend/test/u6-export/status-accessibility.test.tsx` | 37, 38, 39, 40, 42 |

## Build and Test loop-back 2 (2026-11-15)

Build and Test's re-run of 2026-11-15 (`construction/build-and-test/test-results.md`, Target Verification Matrix and Loop-Back Log) passed every U6 lane but found one U6 target Not Met, the never-mocked rule, and ten clauses that no test checks. You chose "Retry with fix" on 2026-11-15. Steps 1–43 stay as built; Steps 44–52 are new and start unchecked. Each test below was designed from the clause it checks and from the code as it is today, and a second reader checked every design against the code before it was written here. One clause cannot pass without a production change (L2-2); every other step adds or changes tests only.

**Decisions (proposed with this plan):**

- **L2-1, the guard's could-not-check case fails for real.** The two stand-ins (`FaultySessions` in `component/test_binding_check.py`, and the patched `housekeeping_store.session_current` in `component/test_worker_pass.py`) test one path: a session guard that cannot be evaluated leaves the work alone (could-not-check, with the approval kept for the next pass) and is never read as a revocation. A revoked or expired session cannot reach that path: it is the guard's definite "no", already tested beside both stand-ins. A `REVOKE` on `accounts.guard_session` cannot either: it raises SQLSTATE 42501, which `session_current` (`backend/modules/export/store_support.py:204-218`) reads as "no longer current", so the approval would be invalidated. The realm's own lock bound can. The realm's PostgreSQL runs with `lock_timeout=1000` (`scripts/verify_docsuri_u6.py:420`) and the guard locks the session row `FOR SHARE` (`backend/modules/accounts/u3_session_authority.sql:19`), so while a second connection holds that row `FOR UPDATE`, the real guard's statement ends after 1 s with 55P03 (`LockNotAvailable`, a psycopg `OperationalError`, not 42501). Each held guard call costs about 1 s of real time, so the Clock rule names the realm's 1 s lock bound beside the 5 s body read; the existing pace-row test (`repository/test_pace_store.py`) already reaches that bound. The alternatives were (B) cancelling the waiting backend from a raw connection with `pg_cancel_backend`, which needs no wait but adds a watcher thread, and (C) keeping the two stand-ins and listing them under Allowed doubles.
  - The two `Faulty(OwnDue).sweep_orphans` stubs (`component/test_worker_pass.py:283-287` and `component/test_log_content.py:38-42`) replace one pass step with a raising psycopg fault, to show that a failing step does not stop the others and that its log line carries no error text. Build and Test did not flag them, but the never-mocked rule, read strictly, covers them. They stay, and are listed under Allowed doubles: the log-content test needs a recognisable secret in the error text, which no real database fault carries.
  - Recorded, not changed: a 42501 from a lost EXECUTE grant also reads as a revoked session, so a deployment that lost the grant would invalidate every open approval. That fails safe (nothing unapproved is written); changing it is a production decision outside this loop-back.
- **L2-2, the key-file read never blocks (one production change).** `read_record` (`backend/key_custody.py:135`) opens the key file with `O_RDONLY | O_NOFOLLOW`. A FIFO at the key path therefore blocks the open until a writer appears, before the `S_ISREG` check at line 139 can refuse it, so NFR3.2's "a non-regular file" cannot pass today: its test would hang. The fix adds `os.O_NONBLOCK` to that one open; nothing else changes. It brings the shared helper in line with security design §4.2's "a regular file", and departs from §4.2's "moved with no change to U2's behaviour" in one case: U2's keyring, and U8's composed and production keyrings, which read through the same helper, now refuse a FIFO instead of hanging. U2's keyring regression is re-run, and U8's checkpoint verification, the last of loop-back 2, runs over the change. The alternative is to stay tests only: test the directory and socket cases, record the FIFO hang as an open defect, and leave NFR3.2 unverified for a FIFO.
- **L2-3, the hosted logger levels are checked in U8's lane.** `U6:NFR3.9/u8-logger-levels` asks that U8 never lower the `httpx` and `httpcore` loggers once the hosted service is composed. U6's realm cannot compose the production assembly, and the edit that withholds the behaviour belongs in `backend/u8_host.py`. So, as L1-11 placed it, the check is written and run in U8's reopen, which follows U6's in loop-back 2: `tests/u8_service_operations_integration/integration/test_production_composition.py::test_the_composed_production_roles_keep_the_transport_loggers_at_warning`, parametrized over `backend.u8_main.ROLES`. It configures logging before composing, in `u8_main.main`'s order, runs each role's first use, and asserts in one comparison that every contribution is active, that no `httpx` or `httpcore` logger or child is below WARNING, that one request through `httpx.MockTransport` logs nothing, and that the role's log holds no transport line. U6's matrix row stays open at U6's checkpoint and closes at the Build and Test re-run. The alternative is to write the same test into U8's file during U6's reopen, with one U8 realm run.
- **L2-4, the connection step is measured after a disconnect.** The flow shows its connection step whenever the owner has no usable connection. No fixture account can open the flow without ever having connected (memberB has no novelty result), so the new reflow test disconnects memberA through the view's dialog and then opens the flow. That needs no fixture change, so the fixture identity and every existing environment stay as they are. Measuring a never-connected owner would need a novelty result for memberB, a fixture-identity change and a U4 job.

**Readings you can change at Plan Approval** (each is built as stated unless you say otherwise):

- L2-1 to L2-4 as above: the could-not-check case through a held session row (A), the two `sweep_orphans` stubs listed as allowed doubles, the FIFO fix made, the hosted logger check built in U8's reopen, and the connection step measured after a disconnect.
- `export.status_counts` keeps its window edges: an effect that ended exactly 24 h before the caller's clock is outside the window (a strict `>`, `backend/modules/export/u6_maintenance.sql:122-125`), and a terminal effect whose end lies after the caller's clock still counts (no upper bound). Changing either needs a new migration, outside this loop-back.
- The due order is pinned on a fresh pass: the older of two accepted exports first, the younger once the older is no longer due. The pass's round robin (`backend/modules/export/worker.py:157-184`) may hand over a younger export while an older one, already handed at its current revision, stays due; strict oldest-first on every pass would be a production change in `worker.py`.
- "Consumed" means an environment holding any `*-evidence-*.json` file, which the browser phase refuses (`scripts/verify_docsuri_u6.py:1255-1258`), or a realm whose 20-account synthetic allocation is spent, which the conftest refuses (`tests/u6_approved_export/conftest.py:151-156`). The coverage phase does not refuse an environment holding evidence; refusing it would be a production change.
- Phase validity covers the verification phases `run_phase` runs. `serve` records its starting source but never compares it and writes no JUnit report, so it is outside the clause.
- NFR3.1's AAD fields are read as hyphenated lowercase UUID text and a decimal revision (`backend/modules/export/token_vault.py:41`): the code's reading of §4.1, which names the fields without a format.
- Recorded, not changed: after a cancellation from outside, the `CancelledError`'s traceback keeps the closed HTTP client and the SDK client, whose options hold the token, reachable until the caller drops the exception. No production path cancels an operation from outside today (`backend/modules/export/service.py:188-191`, `lane.py:138-155`); closing the gap would mean clearing both in `NotionSession._operate`'s `finally`.

**Steps (test-after):**

- [x] **Step 44 — Record the decisions.** Write L2-1 to L2-4 and the readings above into `code-summary.md` (deviations) and `traceability.json`, naming L2-3's test for U8's reopen. No source changes, and no edit to the approved steps above. Trace: Build and Test loop-back 2.

- [x] **Step 45 — Repository — tests.** On the realm, with nothing mocked:
  - (a) `tests/u6_approved_export/repository/test_status_counts.py`, two tests, using the file's 1990 `EPOCH`, the clocks `INSIDE`, `EDGE` and `OUTSIDE` (`EPOCH + DAY` less one second, exactly, and plus one second) and a `changes(after, before)` helper that asserts both hold exactly the seven effect keys (`accepted`, `executing`, `unknown`, `succeededLast24h`, `failedLast24h`, `cancelledLast24h`, `invalidatedLast24h`) and returns only the keys that moved. `test_executing_and_unknown_move_by_exactly_one_through_a_claim_and_an_uncertain_answer` takes its baseline after `flows.connected`: a bind moves only `accepted`; `repo.claim` (a `Claimed`) moves only `executing`; and `record_write_outcome(..., WriteOutcome('uncertain'))`, after which the effect reads `unknown`, moves only `unknown`. `test_failed_and_invalidated_effects_count_once_inside_24h_and_not_from_the_edge_on` takes one baseline per clock after `flows.connected` and before any bind. It ends one bound effect `failed` (`end_unwritten(..., 'dependency-unavailable')`) and a second, bound after the first ended, `invalidated` (`'authority-revoked'`), and invalidates one open approval (`invalidate_open_approval(..., 'source-changed')` is True). The rows read back as (`failed`, `dependency-unavailable`, `EPOCH`) and (`invalidated`, `authority-revoked`, `EPOCH`), and the approval as (`invalidated`, `source-changed`). At `INSIDE` exactly `{'failedLast24h': 1, 'invalidatedLast24h': 1}` moved, so the invalidated approval counts in no effect key; at `EDGE` and `OUTSIDE` nothing moved. Each test erases its owner in `finally`.
  - (b) `tests/u6_approved_export/repository/test_lane_store.py`, after `test_due_items_follow_the_hand_over_order`: `test_the_older_of_two_accepted_effects_is_due_first_and_the_younger_once_it_is_claimed`, with both conftest owners on the file's `EPOCH`. Owner b's effect is bound first, at `EPOCH` + 20 s, then owner a's at `EPOCH` + 10 s. At `EPOCH` + 30 s, `due_items(now, limit=100)` lists the two as `[('execute', older, EPOCH+10s), ('execute', younger, EPOCH+20s)]`; over the whole batch the kinds keep the order resume, execute, scan, and the accepted effects' due times ascend (the id tie-breaker and the order inside resume and inside scan, which the clause leaves open, are not asserted). After `repo.claim(older)` (a `Claimed`), only the younger of the two is listed. Both owners are erased in `finally`.

  Trace: U6:logical-components:watch-counts; U6:security-design:due-order.

- [x] **Step 46 — Business logic — implement.** The key-file read never blocks (L2-2). In `backend/key_custody.py`, `read_record`'s open at line 135 becomes `os.open(root / settings.filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)`, and its docstring says the open never blocks, so the `S_ISREG` check refuses a FIFO. Nothing else changes. Then run U2's keyring regression (the command under "Runnable before the first test step" in `unit-test-instructions.md`), which must pass unchanged, and record its count beside the last one (75 passed, 1 deselected). Trace: U6:NFR3.2; security design §4.2.

- [x] **Step 47 — Business logic — tests: key custody, the vault and the key commands.** In `tests/u6_approved_export/operations/` (`tmp_path` key folders as these files already use; the key commands on the realm):
  - (a) `test_token_vault.py`: `test_an_envelope_opens_independently_under_aes_256_gcm_and_the_design_aad`. Seal the token at revision 12; read the key for the envelope's version from the test's own `tmp_path` key file; slice the envelope by §4.1's literal layout (`b'DSE1'`, a one-byte version length, the version, a 12-byte nonce, then the sealed bytes), never by the module's constants or its `_aad`. Assert the magic, a version length of 35 and the version equal to the key file's active one; then `(len(key), len(nonce), len(envelope)) == (32, 12, 4 + 1 + 35 + 12 + len(TOKEN.encode()) + 16)` before any decrypt; then `cryptography`'s `AESGCM(key).decrypt(nonce, sealed, aad)`, with the AAD rebuilt as `u6-notion-token:{version}:{accountId}:{connectionId}:{revision}`, returns the token; and the list of single changes under which it still opens (another version, the prefix `u2-notion-token:`, another account, another connection, revision 13) is empty. No assertion takes key bytes as an operand.
  - (b) `test_key_custody.py`: `test_guarded_read_refuses_a_fifo_a_directory_and_a_socket_without_blocking`. Each read runs in a daemon thread joined for at most 5 s (`bounded`, as `tests/u8_service_operations_integration/operations/test_drivers.py:135-152` does), and a stalled FIFO read is released through the FIFO's write end before the test fails. A FIFO at the key path (mode 0600, the test's own owner, size within bounds, so only its type is wrong) is refused as `CustodyFault('probe custody unavailable')` caused by `ValueError('private key custody mismatch')`, and stays in place; a directory is refused with the same category (caused by `IsADirectoryError`); a local AF_UNIX socket, bound by relative name inside the key folder and never listened on, is refused with the same category (caused by an `OSError`). The folder listing is unchanged after each.
  - (c) `test_token_keyring.py::test_broken_key_file_is_unavailable_and_nothing_is_created` gains the case `directory`: the key file replaced by an empty directory after a first load gives `ProtectionUnavailable('key-custody-broken')` with no cause or context, the listing unchanged and the directory still empty.
  - (d) `test_key_commands.py`. `test_create_key_after_loss_refuses_unless_the_state_is_loss` also asserts that the folder starts empty and that the command creates the marker: the listing is exactly `export-token-keyring.initialized`, `export-token-keyring.json` and `export-token-keyring.lock`, and the marker is a regular file, mode 0600, owned by the test's user, with one link and the run id as its content; after the not-a-loss refusal its content and inode are unchanged. `test_after_a_loss_rotation_skips_and_reports_tokens_under_the_missing_version` rewrites the marker in place with sentinel bytes before the loss (U6 reads only whether the marker exists, and a re-created marker would hold the run id again) and asserts that `create_key_after_loss` and the later rotation leave its bytes, inode and mode unchanged, with one link, a new active version, and a listing of exactly the key, lock and marker files.

  Trace: U6:NFR3.1; U6:NFR3.2; U6:NFR3.3/operator-commands.

- [x] **Step 48 — Business logic — tests: the session guard, the Notion session and the pass.**
  - (a) `tests/u6_approved_export/store_flows.py` gains `held_session(connect, authority)`, a context manager beside `end_session`: a `connect('accounts')` connection selects the session row `FOR UPDATE` and asserts it exists, then yields; in `finally` it rolls back before closing, so the row is free before the test's next check. Its docstring says that the real guard's own `FOR SHARE` then waits until the realm's 1 s lock bound ends its statement with 55P03, which is not the guard's 42501 answer.
  - (b) `component/test_binding_check.py::test_the_session_fact` (L2-1): `FaultySessions` is deleted and the ended-session half stays. In the second half, a fresh rig's preview is bound with a second session as its approving session; inside `flows.held_session` on that session, the real repository's `session_is_current` raises `psycopg.errors.LockNotAvailable` and the binding check answers `('could-not-check', 'dependency-unavailable', 'DEPENDENCY_UNAVAILABLE')`; once the hold ends, the same check answers unchanged.
  - (c) `component/test_worker_pass.py::test_a_session_check_that_could_not_complete_leaves_the_approval_for_the_next_pass` (L2-1): no monkeypatch. One pass inside `flows.held_session(connect, approver)` gives `(sessionInvalidated, sessionUnchecked) == (0, 1)`, leaves the approval `('approved', None)` and keeps its tree; the next pass, with the hold ended, invalidates it as `authority-revoked` and its tree is gone. The `housekeeping_store` import goes.
  - (d) `component/test_worker_pass.py`, after `test_hand_over_follows_the_due_order_and_never_duplicates_a_scan`: `test_the_pass_hands_over_the_older_of_two_accepted_exports_first`. Owner b, on its own rig with a clock one second later, presses its export first; owner a presses at the earlier time. With both inside one due batch (asserted as a precondition), a fresh own step hands over owner a's export first, and once that export is claimed a second fresh own step hands over owner b's. Each hand-over uses a fresh own step, so the round robin's memory cannot decide it.
  - (e) `component/test_plaintext_lifetime.py`, two tests, with a module-local `closed_clients` fixture: a delegating wrapper on `httpx.AsyncClient.aclose`, set on the class by monkeypatch, that records each client and awaits the original close. `test_a_failed_operation_still_closes_its_client` is parametrized over a provider 500, a transport error (an oversized streamed answer), a per-request timeout (a hanging answer with `request_timeout=0.2`) and the operation's deadline (a hanging answer under a 1 s budget). Each answers could-not-check with its cause and no value, sends only its own bearer, makes exactly one `/v1/users/me` request, closes its one client, leaves no token in the result, and leaves the session holding no client; a following operation then succeeds on a new client that is closed afterwards. `test_a_cancelled_operation_closes_its_client_before_the_cancellation_passes` runs an operation under a 10 s budget against a hanging answer. Once the request has reached the fake (polled inside `asyncio.timeout(5)` as a hang guard), its client is open and the gate is held; cancelling the task closes that client before the `CancelledError` reaches the caller, releases the gate, and leaves the session holding no client. The cancel and its await sit in `finally`, so a failed assertion never leaves a hanging task.

  Trace: U6:unit-test-instructions:never-mocked; U6:security-design:due-order; U6:NFR3.5.

- [x] **Step 49 — Environment/build configuration — tests: the runner.** In `tests/u6_approved_export/operations/` (no realm, except (c)):
  - (a) `test_u6_runner.py` gains a `phase_rig` fixture over `owned_root`: a real key folder and manifest file, the policy and the lock digests; the manifest read, resource check, preflight, port check, source identity, a report-writing `bounded_process` and the fixtures setup are stood in and recorded; `require_key_folder`, `require_test_paths`, `preserve_prior_reports`, `junit_counts` and `private_json` stay real. `test_browser_refuses_an_environment_holding_evidence_before_any_child`, parametrized over a development, a coverage, a serve and an earlier browser evidence file: `dispatch('browser', ...)` raises `browser verification requires a fresh realm; preserve this realm before replacement` before any child, host, fixture setup or source read; the evidence file is kept unchanged at mode 0600; a database phase on the same environment still prepares; and with the evidence file gone, the browser phase prepares and sets up its fixtures.
  - (b) `test_u6_runner.py`, phase validity. `test_a_phase_fails_when_its_source_changes_during_the_run`, parametrized over an unchanged and a changed source after the child: the source is read before and after the one child, and one evidence file at mode 0600 records the starting source and the passing report. The changed case raises `U6 phase failed; evidence preserved`, with `sourceChangedDuringRun` true and exit code 1 in both the evidence and the printed summary; the unchanged case passes with neither. `test_source_identity_sees_a_changed_or_added_listed_file_only` builds a temporary git repository under `tmp_path`, as U8's `git_repository` helper does, with `runner.ROOT` and `runner.command` redirected to it: the inventory lists only the tracked file; changing it changes the digest but not the head; an untracked test file under `tests/u6_approved_export` joins the inventory and changes the digest; an ignored file and a file outside the listed folders change nothing. `test_each_junit_verdict_alone_fails_the_phase` has one case each for a skip, an error and a failure beside a passing case, and one for a passing report at mode 0644: each of the first three sets exit code 1 with its own counts, and the wrongly moded report sets `invalidTestReport`. The existing combined test stays.
  - (c) `test_u6_profile_binding.py`: `test_a_new_owner_past_the_realm_allocation_is_a_failed_prerequisite`, on the realm. With `MAX_SYNTHETIC_ACCOUNTS` lowered, on the conftest module only, to the realm's current account count, making a new owner fails with `Synthetic account allocation exhausted; a fresh owned realm is required` and writes no account, session, consent or settings row; the existing owner `a` is still returned and the count is unchanged.

  Trace: U6:unit-test-instructions:environment-lifetime; U6:unit-test-instructions:phase-validity.

- [x] **Step 50 — Frontend — tests: the connection step at 320 CSS px (L2-4).** `frontend/e2e/u6-approved-export/reflow.spec.ts` gains a fourth test, last in the file (the browser phase also runs this file last). memberA signs in, is disconnected through the view's dialog (`ensureDisconnected`), opens its ready novelty result and starts the export. With `connection-step`, its `connect-form` and `flow-connection-state` visible and the flow on the connection step, `export-flow` measures `{width: 320, page: false, surface: false, offscreen: false, nested: []}`; after a blank token (`' '`) is submitted and `connect-field-error` shows, it measures the same again. The token field is empty at both measurements, and the test does not connect, export or close the flow. `helpers.ts`: `expectStep` also accepts `'connection'`. No fixture or `SPECS` change, so the fixture identity stays. Each other spec file reaches a connected state in its first test, so leaving memberA disconnected affects no other test. After both edits, run U6's `tsc` command (with `--incremental false`) and its ESLint command, which cover `e2e/u6-approved-export`; the browser phase neither type-checks nor lints. Trace: U6:NFR5.1/reflow.

- [x] **Step 51 — Withheld-behaviour checks.** Before the recorded runs and outside them, run each new or changed test once with the behaviour it awaits withheld. Use development environments set up for this and archived afterwards (`setup` and `migrate`, with `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` and `DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config`, containers confirmed through Colima's socket), and the direct form scoped to the test's file: `DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini <file> -k <name> -q --tb=short` (the runner tests need no environment). Record each file's sha256 before its edit, make one edit at a time, record the failure the test gave, then restore the exact bytes and confirm the sha256 before anything else runs. The temporary edits, all reverted:
  - never-mocked: `backend/modules/export/binding.py:234` answers a revocation (`_changed(AUTHORITY_REVOKED, 'UNAUTHENTICATED')`); `housekeeping_store.py:110-112` treats the fault as not current; `store_support.py:216` catches every `psycopg.Error`; and, as a check of the arrangement, each test runs once without its `held_session` line;
  - NFR3.1: `token_vault.py` builds the AAD without the version (line 41), seals and opens with a 16-byte key (`key[:16]`, lines 90 and 115), and uses a 16-byte nonce (`NONCE_BYTES = 16`, line 29);
  - NFR3.2: the new test runs on the code before Step 46, where it stalls; then, after Step 46, without `O_NONBLOCK`, without the `S_ISREG` test, and with the `except` at `backend/key_custody.py:148` narrowed to `(ValueError, TypeError, KeyError)`;
  - NFR3.3: `token_keyring.py`'s `ensure_marker` returns at once, and, separately, always unlinks and re-creates the marker;
  - NFR3.5: `notion_session.py:557` `finally:` becomes `else:`;
  - watch counts: `lane_store.py:600` masks `executing`, `unknown`, `failedLast24h` and `invalidatedLast24h` one at a time with `jsonb_set(..., '0')`, and passes `now` less one microsecond (an inclusive edge);
  - due order: `lane_store.py:193` orders by `due_at DESC`;
  - runner: `scripts/verify_docsuri_u6.py` without the evidence refusal (lines 1255-1258), without the after-phase source comparison (lines 1312-1314), with a listed file's digest recorded as None (line 728), with `TEST_ROOT` dropped from the inventory (line 722), with each of the three verdict terms dropped from line 1139, and with the report read without its custody check (line 1125); `tests/u6_approved_export/conftest.py` without the allocation refusal (lines 151-156), on a development realm, because that run commits one synthetic owner;
  - reflow: on its own fresh environment (`setup`, `migrate`, `browser`), `frontend/src/u6-export/export.css` gains `.export-step .export-connect { min-width: 400px; }` before the phase starts; the new test fails at its first measurement while the other 13 pass, and the rule is removed after the phase ends.

  No withheld edit touches an applied migration or the guard's SQL: the difference between a held and a released session stands in for the guard itself. Files that already differ from the last commit are confirmed restored by sha256, never by `git diff`. Trace: the project's rule on withheld checks.

- [x] **Step 52 — Run and record.** Archive every development environment. Then, on fresh realms:
  - `setup`, `migrate`, `coverage` (with the second report) and `frontend` on realm A, then `archive-owned`; the backend total, `scripts/u6_preservation.py` and `src/u6-export` stay at or above 80%;
  - `browser` on its own fresh realm B, all 14 journeys passing;
  - U6's `tsc` command (with `--incremental false`), its ESLint command (including `e2e/u6-approved-export`), and Ruff on the cicd §2.3 targets plus every U6 script;
  - U2's keyring regression (after Step 46), the earlier Units' regressions, and U2's cumulative lane, since `test/u6-export` is registered in it.

  Then update `code-summary.md` (L2-1 to L2-4; the eleven targets mapped to the tests that close them, with L2-3's row open until U8's reopen; each component's test count, file by file, against the standard strategy's five to eight, counts above eight marked "above range, kept"; the collect-only total; each withheld run's failure and digests), `traceability.json` and `source-manifest.json`. Trace: stage Step 5.

After Step 52, the stage's own review and U6's checkpoint follow (stage Steps 5 and 6). They are not plan steps, so each box above can be ticked on its own run before the review starts. When this attempt's approval clears the boxes of Steps 1–43, their work stands: each is ticked again only after Step 52's runs, which exercise it again, have passed, as the project's rule asks.

**Loop-back 2 traceability** (target → the file that closes it → step):

| Target | Closed by | Steps |
|---|---|---|
| U6:unit-test-instructions:never-mocked | `tests/u6_approved_export/store_flows.py` (`held_session`); `component/test_binding_check.py`; `component/test_worker_pass.py` | 48, 51 |
| U6:NFR3.1 | `tests/u6_approved_export/operations/test_token_vault.py` | 47 |
| U6:NFR3.2 | `backend/key_custody.py`; `tests/u6_approved_export/operations/test_key_custody.py`; `test_token_keyring.py` | 46, 47 |
| U6:NFR3.3/operator-commands | `tests/u6_approved_export/operations/test_key_commands.py` | 47 |
| U6:NFR3.5 | `tests/u6_approved_export/component/test_plaintext_lifetime.py` | 48 |
| U6:NFR3.9/u8-logger-levels | U8's reopen: `tests/u8_service_operations_integration/integration/test_production_composition.py` (L2-3) | 44 |
| U6:NFR5.1/reflow | `frontend/e2e/u6-approved-export/reflow.spec.ts`; `helpers.ts` | 50 |
| U6:logical-components:watch-counts | `tests/u6_approved_export/repository/test_status_counts.py` | 45 |
| U6:security-design:due-order | `tests/u6_approved_export/repository/test_lane_store.py`; `component/test_worker_pass.py` | 45, 48 |
| U6:unit-test-instructions:environment-lifetime | `tests/u6_approved_export/operations/test_u6_runner.py`; `test_u6_profile_binding.py` | 49 |
| U6:unit-test-instructions:phase-validity | `tests/u6_approved_export/operations/test_u6_runner.py` | 49 |

## Build and Test loop-back 3 (2026-11-17)

Build and Test ran a fourth time on 2026-11-17, with its rung-1 fixes (`construction/build-and-test/test-results.md`: the Not Met table, Outcome items 3 to 5, and the Loop-Back Log entry "Loop-back 3 — 2026-11-17T16:07:16Z"). That run found two U6 targets Not Met, the never-mocked rule and the static checks. It also found two clauses that no test checks: when the lane recorded the outcome that the watch counts report, and NFR3.8's provider text on the history rows and the settle dialog. You chose "Retry with fix" on 2026-11-17. Steps 1–52 stay as built; Steps 53–63 are new and start unchecked. Each test below was designed from the clause it checks and from the code as it is today, and a second reader checked every design against the code before it was written here. No step changes production behaviour. Every step adds or changes tests, or, for the static checks, changes lint configuration, import order and line layout; Step 60 shows those changes leave the code's syntax tree as it was, except for two test lines (B007 and UP031). This is loop-back 3 of 3.

**Decisions (proposed with this plan):**

- **L3-1, the lane's store faults are real.** Two stand-ins in `component/test_lane_write_path.py` are replaced by real database faults: `Broken` (lines 402-411) and `Interleaved(pace=False)` (lines 21-41, used at 374).
  - How the fault arises. A new helper holds named rows `FOR UPDATE` from a raw administrative session. The realm's lock bound (`lock_timeout=1000`, `scripts/verify_docsuri_u6.py:420`) then ends the code's own locking or updating statement with 55P03. psycopg 3.3.6 raises that as `psycopg.errors.LockNotAvailable`, an `OperationalError` (`errors.py:1543-1544`). `OwnerTransactions.run` retries only `SerializationFailure` and `DeadlockDetected` (`backend/transactions.py:363-366`), so the fault reaches the lane.
  - The unreservable pace slot. The hold runs only around the lane's own reservation, through `Interleaved`, which already runs another actor's step around the claim.
    - While the pace row is held, the real `reserve_pace_slot` meets the row, ends at the bound and answers None (`backend/modules/export/lane_store.py:586-589`; `repository/test_pace_store.py:52-67` already shows this). The lane then takes its could-not-check path at `lane.py:265`.
    - A hold over the whole run would not reach that line. The binding check first reads the destination through the adapter (`binding.py:263-276`), and the adapter's pacer reserves a slot on the same row before its request (`notion_session.py:395-405`). The run would end at `lane.py:258-259` instead, and the lane's own reservation would go untested. The adapter's pacer uses the rig's own store, not the `Interleaved` wrapper (`interleaved_lane`, `test_lane_write_path.py:44-51`), so a hold given to the wrapper reaches only the lane's reservation.
  - The store fault. The effect row and the `export.lane_status` singleton are held from the claim on: `Interleaved`'s step before the claim starts the hold, and the hold ends after `run_item` returns.
    - The claim's `SELECT … FOR UPDATE` (`lane_store.py:136-143`) and then the status upsert (`:604-613`) each end at the bound. Both of `run_item`'s fault branches (`lane.py:208-213` and `:224-231`) are therefore reached through the real store and the real transaction wrapper.
    - `effect_binding` only reads (`:213-256`), and a held row blocks no plain read. The fault therefore arrives at the claim, not at the first store call as it did with `Broken`.
    - The fault's own text is captured from a direct `record_lane_status` call under a short hold of the singleton, and that is the text that must never be logged. L2-1 listed `Faulty` because its test needed a recognisable secret in the error text; that reason does not apply here.
  - Where the holders connect. Holders open through the conftest's `connect_raw`, the realm's administrative login (`tests/u6_approved_export/conftest.py:82-111`), not through a runtime role. The runtime roles carry `CONNECTION LIMIT 2` (`verify_docsuri_u6.py:581`), and every lane unit opens a fresh `docsuri_export` connection (`NullConnectionPool`, `transactions.py:248-266`). A holder on that role would leave the lane no spare connection.
  - Every hold stays well inside the realm's `idle_in_transaction_session_timeout=5000` (`verify_docsuri_u6.py:421`): about 1 s for the pace hold and for the capture, and about 2 s for the store fault.
  - Alternatives:
    - (B) `LOCK TABLE export.effect IN ACCESS EXCLUSIVE MODE`. It fails `effect_binding` first, as `Broken` did, but blocks every reader of the table.
    - (C) Keep both stand-ins and list them under Allowed doubles.
- **L3-2, the operator's outcome reads realm rows.** `Rows` in `operations/test_u6_real_export_checks.py` (lines 187-195) is replaced by two real exports of one owner.
  - The schema allows one export in flight per owner: the `effect_in_flight` index (`backend/modules/export/u6_schema.sql:163`; BR5.1), refused as `CAPACITY_EXHAUSTED` (`approval_store.py:333-335`).
  - So the first press is settled with `rig.succeed` before the second press. The second export is claimed with `path_kind="real"` and recorded as refused `no-access` through the store's own units (`lane_store.py:260-312` and `:387-392`). Nothing is left in flight.
  - The real `operator.outcome` then runs `OUTCOME_QUERY` (`scripts/u6_real_export.py:141-147`). The query's id filter and its `LIMIT 2`, which the double skipped, are now tested too.
  - Alternative: list `Rows` beside the runner stand-ins.
- **L3-3, the archive's database check reads the realm.** `Database` in `operations/test_u6_preservation.py` (lines 36-57) is replaced by a `connect_raw` session with tuple rows, which is how the runner's own `connect_admin` returns them (`verify_docsuri_u6.py:491-502`). `check_database` (`scripts/u6_preservation.py:105-117`) therefore reads the realm's real identity and client backends.
  - The run id. The `tmp_path` manifest carries the realm's own run id (`realm.run_id`), and every name built from the run id follows it, including the destination case's pre-created folder.
  - Waiting for other clients. Before it hands the session over, the fixture's `connect_admin` waits until no other client backend remains, for at most 5 s. It rolls back after each read, because PostgreSQL keeps one activity snapshot per transaction.
  - The active-client case opens one more real session.
  - Zero other clients can be reached. The runner holds no database client while the pytest child runs: it calls `connect_admin` at `:514`, `:663` and `:1401`, in setup, migrate and the key phases, and at `:1453` hands it to the archive context of `archive-owned`, which runs outside any pytest child. A connection that an earlier test leaks shows as a failed prerequisite, never as a pass.
  - The Docker, port, open-file and stop stand-ins stay recording only, because the runner's real `stop_database` would stop the phase's own database.
  - Alternative: list `Database`.
- **L3-4, the remaining wrappers and stand-ins are named under Allowed doubles, by two narrow rules.** None of them replaces anything on the never-mocked list, so no target is relaxed. Alternative: leave them unlisted, as Build and Test judged them.
  - Delegating wrappers, which call the original or open the real realm session, record the call or run another actor's real step around it, and never answer in its place:
    - `Interleaved`, with its claim steps and its pace hold;
    - the `reserve_pace_slot` spy in `integration/test_pending_connect.py:88-96`;
    - `racing_page` in `operations/test_key_commands.py:165-178`;
    - `spy_method` in `integration/test_export_assembly.py:22-30`;
    - the archive fixture's `connect_admin` (L3-3), which opens the realm's administrative login through `connect_raw` with tuple rows, waits for other clients by a bounded poll and counts its reads. Every answer comes from the realm.
  - Recording stand-ins for what lies outside the database, which answer in place but stand for nothing on the never-mocked list: the archive context's `resources`, `idle_port`, `open_files` and `stop_database` in `operations/test_u6_preservation.py:100-121` (Docker, the port, `lsof` and the database stop).
- **L3-5, `FakeResearch` (your call; proposed default: list it).** `FakeResearch` in `operations/test_u6_browser_fixtures.py:122-148` stands in for U4's service and execution in `test_a_missing_result_is_produced_through_the_research_service` (line 150), which tests the fixture script's own branches: a missing result is produced in one execution step, and a failed job refuses.
  - What it stands in for. The test calls `ready_novelty(None, …, None)`. With no known result, `_ready` returns before any export read (`scripts/u6_browser_fixtures.py:263-264`), so `FakeResearch.readNoveltyArtifactForExport` (test lines 130-131) is never called. What it replaces is U4's policy reference, entitlement check, context creation, accept, job read and execution step. The never-mocked list names U4's export read in integration tests and fixtures (`unit-test-instructions.md:204`), not those calls. U4's real service, real execution and real export read run in `test_fixture_setup_is_idempotent_and_its_result_is_exportable` (line 20), in the integration rigs' `Rig.ready` and in the fixtures phase.
  - (a, proposed) List it under Allowed doubles as a stand-in for U4's service and execution in that one test only, with the reading above written beside it, so a later re-check finds it named. Cost: one bullet in the instructions. Build and Test's Outcome item 3 accepts listing a double by a plan decision you approve.
  - (b) Reach the produced-result branch through U4's real service and execution on a conftest owner. Cost: one U4 job from that owner's four per realm (`unit-test-instructions.md:276`). No real way was found here to make U4's synthetic execution end a job as failed (`ResearchService` refuses work when execution is disabled, `backend/modules/research/service.py:212`), so the failed-job branch would need its own design, which would come back to you before any build step.
- **L3-6, the watch counts' time is checked through the lane's real record against the database clock.**
  - The status record takes no time. On the first insert the row takes the column default, `clock_timestamp()` (`backend/modules/export/u6_schema.sql:244`); every later record updates it with `observed_at=clock_timestamp()` (`lane_store.py:610`). The lane passes it no clock (`lane.py:224-229`).
  - `export.status_counts` returns that row's time as `lane.observedAt` (`backend/modules/export/u6_maintenance.sql:141-142`). It uses the caller's clock only for the windows and the ages.
  - The new test therefore records two outcomes through the real repository and brackets the second between two reads of the database clock. It then reads the lane block under two caller clocks, both different from the record time.
  - `integration/test_lifecycle_in_flight.py:89-92` already shows, through the lane, that the lane's own record moves the row's time.
  - Alternatives:
    - (B) Write the row directly with a fixed `observed_at`. That skips the record path.
    - (C) Give `record_lane_status` the lane's injected clock. That is a production change no clause needs.
- **L3-7, NFR3.8's remaining jsdom surfaces get one hostile-text case each (U6-C at its minimal scope).**
  - The history row (`frontend/src/u6-export/history.tsx:137`) and the settle dialog (`dialogs.tsx:183`) show the Notion destination title. The server passes that title through unchanged (`backend/modules/export/views.py:206`), and `api.ts:250-270` checks only that it is non-empty text.
  - The matrix row missed a third surface. After a configure, `ConnectForm` announces the Notion workspace name (`connect-form.tsx:103-106`), which is provider text (`notion_adapter.py:530`). The announcement renders in the view's `export-live` region (`export-view.tsx:123` and `:241`; `status.tsx:36-41`). The one existing hostile workspace-name case covers only the panel (`export-view.test.tsx:125-139`).
  - Each surface gets one Vitest case in its existing file. No Vitest file is added, so `FRONTEND_FILES` is unchanged.
  - Counts: history goes from 17 to 18 cases, dialogs from 8 to 9 and export-view from 15 to 16. Each is recorded as above range, kept (L1-8).
  - Afterwards NFR3.8 stays Unverified, browser-only: no Chromium run shows hostile provider text, because the browser fixtures' titles are plain. Unless L3-8 is chosen, Build and Test says so at the gate under its Step 12.
- **L3-8, U6-C in full: the optional Chromium checks (your call; proposed default: not built).** The Loop-Back Log leaves to you whether the browser-only targets' Chromium checks join this loop-back.
  - What they would be for U6, in `frontend/e2e/u6-approved-export/`:
    - the connect help: exactly two items, and none of update content, comment access or user information, in Korean and English (`journeys.spec.ts:51` checks only "Insert content");
    - the token field: its type, autocomplete and spellcheck attributes, its clearing after a refused configure, and the token's absence from storage, the URL, cookies, the console and the page;
    - the statuses: each badge's words beside its hidden icon, one polite region per surface, and each change announced once;
    - hostile provider text on all six surfaces.
  - Cost: half a day to one day (`~/.docsuri-u8/lead-scripts/l2-records/bt4-rung2.json`, U6-C), at $0. The work involves:
    - New hostile fixture entries. These change `SCENARIO_NAMES` (`scripts/u6_browser_fixtures.py:77-87`), a fixture-identity change that archives every existing environment (L1-9).
    - A hostile settle destination for the history row and the settle dialog, and possibly a fourth clock-advanced settle journey. That journey must fit under the 300 s phase bound (`verify_docsuri_u6.py:60`); run 4's 14 journeys took 95.8 s.
    - For a hostile workspace name, a change to `helpers.ts:147`'s `expectConnected`, or a second synthetic bot and token.
    - A fresh browser environment for each Chromium withheld check.
  - Gain: D7, NFR3.4/connect-field, NFR5.1/component-checks and NFR3.8/provider-text would become Met. Without these checks, those four are said at the gate as browser-only.
  - If you choose it, this plan comes back to you with its steps before any build step. As written, no step builds it.
- **L3-9, U6's own lint configurations, passed with `--config`.**
  - `scripts/u6-lint.toml`, for the tests:
    - `select = ["E", "F", "I", "UP", "B"]`, `line-length = 100` and `target-version = "py313"`;
    - `src = [".", "ingestion/src", "ops/src"]`, which is U6's pytest `pythonpath` (`unit-test-instructions.md:20`; `backend/pytest.u6-approved-export.ini:3`).
  - `scripts/u6-lint-scripts.toml`, for the five scripts:
    - `extend-select` with the same rules, added to Ruff's default selection, so the default rules that apply to the scripts today stay, as in `scripts/u8-lint-scripts.toml`;
    - `src = [".", "scripts", "ops/src"]`, the paths the scripts set up for themselves.
  - Nothing is ignored, and neither file has per-file ignores or fix settings.
  - No other lint changes: Ruff discovers only `ruff.toml`, `.ruff.toml` and `pyproject.toml`, and these files are passed only with `--config`.
  - What stays as it is. U6's own backend files, the shared runtime files and `ops/src/docsuri_ops/local_transport.py` stay under their own configurations, `backend/pyproject.toml` and `ops/pyproject.toml`. Those already select E,F,I,UP,B at 100 with nothing ignored (`backend/pyproject.toml:95-103`, `ops/pyproject.toml:45-49`), and the files pass there today. No folder `ruff.toml` sits between those files and their settings (`ruff check --show-settings` names `backend/pyproject.toml` or `ops/pyproject.toml` for each).
  - This is U8's L1-34 shape (`scripts/u8-lint.toml`, `u8-lint-scripts.toml`), kept in U6's own files so that U6's CI does not depend on files that U8's gate pins.
  - Findings under these rules today, with U8's files: tests 113 (70 I001, 41 E501, 1 UP031, 1 B007), in `~/.docsuri-u8/lead-scripts/final-lanes/records-check-20261117-210319-6257/01-u6-tests-u8-lint-config.log`; scripts 38 (19 E501, 16 E402, 3 I001), in `records-check-20261117-220053-52710/11-u6-scripts-u8-lint-scripts-config.log`. Both counts were read again here with the same result.
  - Alternatives:
    - (B) Reuse U8's files.
    - (C) Add a `tests/u6_approved_export/ruff.toml`, which `ci.yml`'s root-suites lint would also pick up.
- **L3-10, the four U2 accounts files on U6's CI list (your call; proposed default: count them).** The files are `backend/modules/accounts/control_keys.py`, `services/control_lifecycle.py`, `local_http.py` and `services/guarded_entry.py`.
  - Today they pass under their folder's `ruff.toml`, which ignores B008, E501 and UP042. Under E,F,I,UP,B at 100 they give 30 E501: 29 SQL literals in `control_lifecycle.py` and one call at `local_http.py:129`.
  - All 30 lines come from U2's commit `a62bb26e`, which predates U6's commit (`records-check-20261117-220053-52710/05-u2-accounts-e-f-i-up-b-100.log` to `10-git-commit-dates.log`).
  - All four files, and `shared/python-consumers.json`, already carry U8's uncommitted edits.
  - (A, proposed) Count them.
    - Why: U6's own design names them as U6's Ruff targets (`infrastructure-design/cicd-pipeline.md` §2.3). This is the last loop-back, so a narrower reading that a later re-check called a relaxation would leave the row Not Met with no loop-back left to repair it.
    - What it does: wrap the 30 lines in the two files that have them, each wrap leaving the syntax tree unchanged. Lint all four files from `backend/modules/accounts` under a new `scripts/u6-lint-accounts.toml`: the folder's file, with E,F,I,UP,B and `ignore = []`, the shape of `scripts/u8-lint-accounts.toml`. B008 and UP042 add no finding.
    - Cost: under an hour, plus one regeneration. `shared/python-consumers.json` pins the SHA-256 of `local_http.py` and `control_lifecycle.py` (both match today's bytes), and `ci.yml`'s `shared` job fails on drift (`shared/python/tools/inventory_consumers.py:118-133`, `.github/workflows/ci.yml:73-74`; cicd-pipeline §2.2). Step 59 therefore checks the inventory before the wraps and regenerates it after them, keeping U8's part apart from U6's.
    - U8's checkpoint verification, which runs last in this loop-back, runs over all four files.
  - (B) Do not count them.
    - They stay under the folder's configuration, as U8 kept the U2 file it edited (`local_http.py`) there.
    - Cost: none in the build. But the row's Met would rest on reading "U6's targets" more narrowly than cicd §2.3 does, and the stage file says relaxing a defined target is never an acceptable fix.
    - What is not built under (B): `scripts/u6-lint-accounts.toml`, the U2 wraps and the regeneration. The four paths join invocation 3 below.
- **L3-11, the static-check fixes change no behaviour.**
  - E402. All 16 findings come from one line, `ROOT = Path(__file__).resolve().parents[1]`, standing above the scripts' imports (`verify_docsuri_u6.py:36`, `serve_docsuri_u6.py:15`, `u6_browser_fixtures.py:38`, `u6_real_export.py:28`).
    - Ruff allows `sys.path.insert` calls before imports, so `ROOT` moves to right after the import block and each insert writes the path inline.
    - `sys.path` and `ROOT` end up exactly as before.
    - No `noqa` is added. A per-file ignore would switch off a rule the target names; U8 used bare line markers instead.
  - I001. Import order is fixed by the `ruff check --fix --select I` commands named in Step 59.
    - This plan approves those commands, so they are not a shell edit to record as a deviation, as `code-summary.md:156` once recorded one.
    - Safe fixes only; never `--unsafe-fixes` or `ruff format`.
  - Every other finding is fixed by hand:
    - long literals are split into implicitly joined parts;
    - calls and conditions are wrapped;
    - two docstrings are re-wrapped;
    - B007: the unused loop name is dropped (`repository/test_owner_guard.py:97`);
    - UP031: the `%` formatting becomes an f-string (`integration/test_export_http.py:236`).
  - Step 60 compares each changed file's syntax tree with a snapshot taken just before Step 59.
- **L3-12, a lint gate in U6's own lanes.**
  - A new `operations/test_u6_lint_gate.py` holds three tests on real Ruff and real files, as U8's `test_lint_gate.py` checks U8's files.
  - The coverage phase then checks the rules, the no-ignore discipline and the exact CI invocations on every run.
  - It is mapped under EnvironmentTool, which goes from 72 to 75 definitions, above range, kept. As a component of its own, three tests would fail the five-test floor (`test_u6_test_volume.py:192-204`).

**Readings you can change at Plan Approval** (each is built as stated unless you say otherwise):

- L3-1 to L3-12 as above, with L3-5 (a), L3-8 not built and L3-10 (A).
- `store_flows.held_session` stays byte-identical, so L2-1's two tests and their withheld runs stand. The new `held_rows` sits beside it.
- One `path_kind='real'` attempt is written into the synthetic realm through the store's own claim (L3-2). `component/test_real_export_gates.py:127-147` already writes real attempts there.
- L2-1's listed `Faulty(OwnDue).sweep_orphans` is not reopened.
- "When it happened" (logical-components §8) is the database clock at the lane's last status write. It is not the lane's injected clock, the caller's clock or the read time.
  - In production these agree, because the lane's clock is real time (`backend/u6_host.py:131`).
  - Under the browser realm's fixture clock, the lane status keeps database time. Recorded, not changed.
- The instructions' Clock line "Only the pace reservation uses the database clock" (`unit-test-instructions.md:213`) is amended to speak only of behaviours a test checks against time:
  - Two checked behaviours take the database clock: the pace reservation (`lane_store.py:567-593`) and the lane status record (`u6_schema.sql:244`, `lane_store.py:610`), whose test brackets the record with `clock_timestamp()` reads.
  - Every other checked behaviour takes the injected `now`.
  - `database/test_export_functions.py:12-18` already reads `clock_timestamp()` as a caller clock.
- The watch-counts check is a new test, not an extension of `test_the_lane_block_is_a_category_and_the_whole_json_holds_no_identifiers`. ExportStore goes from 91 to 92 definitions; extending the existing test would keep 91.
- NFR3.8's payloads are shaped as markup and as links only.
  - NFR3.8 asks that provider text be "escaped wherever it is shown and never interpreted" (`nfr-requirements/security-requirements.md:54`) and names no bidi or control characters. Isolating bidi text would be a production change.
  - `sourceTitle` stays plain: it is DocSuri's own result title (`views.py:205`).
  - The settle dialog is rendered directly, as its file's helpers do.
- The flow's connection step announces through the same `ConnectForm` and the same `LiveRegion` component, into `flow-live` (`export-flow.tsx:100-106`, `:167`). One case through the view is taken to cover both regions; a fourth case in `export-flow.test.tsx` can be added if you ask.
- L1-8 applies to every count this loop-back raises: dialogs 9 (until now in range), history 18, export-view 16, ExportStore 92 and EnvironmentTool 75.
- The withheld runs of the Vitest cases and of the lint gate touch no environment, because `vitest run` and the gate need none. The instructions' "on a development environment archived afterwards" (`unit-test-instructions.md:301`) therefore has nothing to set up for them.
- The existing `# noqa: E731` (`repository/test_connection_store.py:65`) and `# noqa: E402` (`operations/test_u6_profile_binding.py:18`) stay.
- The scripts' `src` moves three imports.
  - In the runner, `backend.local_profile` moves ahead of `bootstrap_docsuri_u1`, which imports it too (`scripts/bootstrap_docsuri_u1.py:27-28`).
  - `docsuri_ops` moves into the first-party block.
  - Ruff never moves an import across a statement.
- The two docstring re-wraps change whitespace only.
  - `database/test_export_schema.py:215`.
  - `scripts/u6_browser_fixtures.py:12`: this one is the argparse description (`:452`), which argparse re-wraps, so `--help` is unchanged.
- U6's CI lint step drops its duplicate `scripts/u6_real_export.py` and gains `--no-cache`.
- The static-check sweep (Steps 58–60) follows the test steps.
  - One sweep therefore also lints the test steps' new code, and Step 60's snapshot isolates the sweep's own changes.
  - The withheld runs (Step 62) follow the sweep, so they restore the exact bytes the recorded runs use.

**Steps (test-after):**

- [x] **Step 53 — Record the decisions.** Write L3-1 to L3-12, your answers to L3-5, L3-8 and L3-10, and the readings above into `code-summary.md` (deviations) and `traceability.json`. No source changes, and no edit to the approved steps above. Trace: Build and Test loop-back 3.

- [x] **Step 54 — Repository — tests: when the lane recorded its last outcome (L3-6).** On the realm, with nothing mocked, in `tests/u6_approved_export/repository/test_status_counts.py`:
  - Imports and helper.
    - `from tests.u6_approved_export import lane_flows as lf` joins the import block, between `export_rows` and `store_flows`.
    - A module-local `database_now(connect)` returns `SELECT clock_timestamp() AS now` through `connect("export")`. That is the realm's own clock, the one the status record stamps. No test module imports `database/test_export_functions.py`'s `now`.
  - The new test, `test_the_lane_block_reports_when_the_lane_recorded_its_last_outcome(transactions, connect)`, goes after `test_the_lane_block_is_a_category_and_the_whole_json_holds_no_identifiers`. It takes no owner, so no synthetic account is allocated.
    - Arrange:
      - `repo.record_lane_status("stopped")` makes sure the singleton row exists, so the next record takes the update path;
      - `first = lf.latest_lane_status(connect)`;
      - `before = database_now(connect)`;
      - `repo.record_lane_status("skipped")`;
      - `after = database_now(connect)`;
      - `recorded = lf.latest_lane_status(connect)`.
    - Assert on the row:
      - it reads `skipped`;
      - `first["observed_at"] < recorded["observed_at"]`;
      - `before <= recorded["observed_at"] <= after`.
    - Assert on the lane block. For each caller clock, the file's `EPOCH` and `after` plus 90 s, `repo.status_counts(clock)["lane"]` has the outcome `skipped`, and `dt.datetime.fromisoformat(lane["observedAt"]) == recorded["observed_at"]`. That is the time the lane recorded: neither caller clock is ever inside `[before, after]`, and the read time falls after `after`.
  - The module docstring gains one sentence: the lane block's time is the database clock at the status write, and never follows the caller's clock.
  - Every new line stays within 100 columns.
  - Run it once on a development environment, in the direct form scoped with `-k`; it passes.

  Trace: U6:logical-components:watch-counts; logical-components §8.

- [x] **Step 55 — Business logic — tests: the lane's store faults are real (L3-1).** On the realm, in the component layer:
  - (a) `tests/u6_approved_export/store_flows.py` gains `held_rows(connect_raw, *locks)` beside `held_session`, which stays byte-identical. `held_rows` is a context manager:
    - It opens one administrative session through `connect_raw()`.
    - For each `(sql, params)` in `locks`, it asserts that the statement is a `SELECT … FOR UPDATE` and that it returns a row. Then it yields.
    - After the block it runs `SELECT 1`, which shows the holder stayed alive throughout.
    - In `finally` it rolls back, then closes.
    - Three constants name the locks:
      - `PACE_ROW`: `SELECT next_slot_at FROM export.connection_pace WHERE connection_id=%s FOR UPDATE`;
      - `EFFECT_ROW`: `SELECT id FROM export.effect WHERE id=%s FOR UPDATE`;
      - `LANE_STATUS_ROW`: `SELECT outcome FROM export.lane_status WHERE singleton FOR UPDATE`.
    - Its docstring says three things. A locking or updating statement of the code under test then waits until the realm's 1 s lock bound ends it with 55P03, a real fault. Plain reads are not blocked. Each hold must stay under the realm's 5 s idle-in-transaction bound.
  - (b) `component/test_lane_write_path.py`, the `Interleaved` wrapper:
    - It loses its `pace` argument and its answering `reserve_pace_slot`.
    - It gains `pace_hold=None`: a zero-argument callable returning a context manager. When it is given, the real `reserve_pace_slot` runs inside it, and its answer is passed back unchanged.
    - It keeps the claim's before and after steps.
    - Its docstring changes to match.
  - (c) The pace test, `test_an_unopenable_token_at_the_claim_and_an_unreservable_pace_slot_both_wait`, takes `connect_raw`.
    - Its first run goes through `interleaved_lane(lr, pace_hold=lambda: flows.held_rows(connect_raw, (flows.PACE_ROW, (UUID(connection["connectionId"]),))))`.
    - The binding check's destination read reserves its slot unheld, through the rig's own store. The lane's own reservation then meets the held row and answers None. The run answers `"waiting"`, and the effect is `accepted` with `waiting_since` set.
    - The unopenable-token half is unchanged. No attempt and no fake write exist at the end.
  - (d) The store-fault test, `test_a_store_fault_is_reduced_to_a_category_and_its_text_never_logged`, takes `connect_raw`. `Broken` is deleted.
    - Arrange:
      - The test presses one export.
      - `LaneItem("execute", uuid4(), 1)` runs through the real lane and answers `"skipped"`, which leaves a status row.
      - `before = lf.latest_lane_status(connect)`.
    - Capture the fault. Inside `held_rows(connect_raw, (LANE_STATUS_ROW, ()))`, a direct `lr.repo.record_lane_status("error")` raises `psycopg.errors.LockNotAvailable`.
      - The fault's `sqlstate` is `55P03`.
      - Its `diag.message_primary` is non-empty and contained in its `str()`.
      - Both strings are kept.
    - Act. After `caplog.clear()`, with caplog at DEBUG, the export runs once through an `Interleaved` lane.
      - Its step before the claim enters `held_rows(connect_raw, (EFFECT_ROW, (effect,)), (LANE_STATUS_ROW, ()))` on a `contextlib.ExitStack`.
      - The stack closes after `run_item` returns, so the hold lasts about 2 s.
      - The run answers `"error"`.
    - Assert:
      - The `docsuri.export.lane` messages are exactly `export lane execute item ended early (LockNotAvailable)` and `export lane status not recorded (LockNotAvailable)`.
      - Neither kept string appears in `caplog.text`.
      - No record has `exc_info` or an exception argument.
      - The lane status equals `before`, with the same outcome and the same `observed_at`.
      - The effect is `accepted` at its pressed revision, with no attempt and no fake write.
    - Recovery. With the hold ended, the same item runs to `"succeeded"`, with one write and the status `succeeded`.
  - The file keeps its 20 tests.
  - Run both tests once on a development environment, in the direct form scoped with `-k`; they pass.

  Trace: U6:unit-test-instructions:never-mocked.

- [x] **Step 56 — Frontend — tests: hostile provider text in the history row, the settle dialog and the connect announcement (L3-7).** In `frontend/test/u6-export/`, in strict TypeScript with no `any`. `history.test.tsx` and `dialogs.test.tsx` each gain a `describe('provider text stays text')` block; `export-view.test.tsx`'s case joins its existing block of that name (`export-view.test.tsx:125-139`).
  - (a) `history.test.tsx`, a new block after `describe('actions by state')`: `renders a hostile destination title in a row as text, making no element or link from it`.
    - Setup: one `historyEntry` mounted through the file's `history()` helper, with:
      - `destinationTitle: '<img src=x onerror="x"><a href="javascript:alert(1)">{{x}}</a>'`;
      - `state: 'consumed'`;
      - a succeeded effect with `remoteUrl: PAGE_URL`, which gives the row its one real link (`history.tsx:67-76`).
    - In the row:
      - `querySelector('img')` and `screen.queryByRole('img')` are null;
      - the row's link hrefs are exactly `[PAGE_URL]`;
      - `within(row).getByText(<payload>)` is a `SPAN` with no element children.
  - (b) `dialogs.test.tsx`: `within` joins the import, and a new block goes after `describe('settle dialog')`. The case is `renders a hostile destination title as text, keeping its name and its first stop`.
    - Setup: `SettleDialog` rendered with `historyEntry({ destinationTitle: '<svg onload=x>노트</svg><a href="javascript:alert(1)">{{x}}</a>' })`.
    - Assert:
      - the dialog is still named `Notion에서 직접 확인`;
      - `dialog.querySelector('svg, a')` is null;
      - `document.activeElement` is `settle-delivered`, the dialog's own first stop (`dialogs.tsx:9-10` and `:68`);
      - `within(dialog).getByText(<payload>)` is a `STRONG` with no element children.
  - (c) `export-view.test.tsx`, in the existing `describe('provider text stays text')`, after the panel's hostile workspace-name case: `announces a hostile workspace name after a connect as text`.
    - Setup: `read-notion-connection` answers with the file's `notConnected`, `list-export-history` with `historyPage([])`, and `configure-notion-connection` with `connection({ workspaceName: '<svg onload=x>팀</svg><a href="javascript:alert(1)">{{x}}</a>' })`.
    - Act: the fixtures' synthetic `TOKEN` is typed into `connect-token` and submitted with `connect-submit`, through the view's real `ConnectForm`.
    - Assert:
      - `export-live` contains the payload literally and holds no `svg` or `a`;
      - once saved, `connection-workspace` holds no `svg` or `a` either.
  - Run each file:
    - `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts test/u6-export/<file>`;
    - then U6's `tsc` command with `--incremental false`;
    - then U6's ESLint command.
  - No production file, fixture, Playwright spec or volume map changes.

  Trace: U6:NFR3.8/provider-text.

- [x] **Step 57 — Environment/build configuration — tests: the operator's outcome and the archive read the realm (L3-2, L3-3).** In `tests/u6_approved_export/operations/`, on the realm:
  - (a) `test_u6_real_export_checks.py`: `Rows` is deleted. `test_the_outcome_names_exactly_one_export` takes `realm, transactions, connect, authority, tmp_path`, and `uuid4` and `WriteOutcome` (from `backend.modules.export.repository`) join the imports.
    - Arrange:
      - The test builds the synthetic rig over the research double, so no U4 job is spent and no account is added, and configures it.
      - It presses export B on a fresh `rig.page()` and settles it with `rig.succeed`. One export in flight per owner (BR5.1, `effect_in_flight`) refuses a second press while the first is accepted.
      - It then presses export A on another fresh page.
      - `rig.repo.claim(..., path_kind="real")` returns an attempt with `path_kind` `real`.
      - `record_write_outcome(..., WriteOutcome("refused", reason="no-access"), now=rig.clock.now)` records the refusal.
    - Through the real `operator.outcome(transactions, realm, activation, ...)`:
      - an unknown id and `effect_id=None` each raise `OutcomeRefused` matching `exactly-one`; with at least two exports in the realm, `LIMIT 2` returns two rows;
      - A's id gives `(requestIdSha256, pageLinkSha256) == (None, None)`, `pathKind` `real`, `outcomeReason` `no-access`, and `(effectState, settledBy, outcomeClass, creatorConfirmed) == ("failed", "provider", "refused", None)`;
      - an activation for another run id raises `run-differs`.
    - Nothing is left in flight. The file keeps its 7 tests.
  - (b) `test_u6_preservation.py`: `Database` and the constant `RUN_ID` are deleted. The `owned` fixture also takes `realm` and `connect_raw`.
    - The manifest. `write_manifest` takes `run_id`, by default `realm.run_id`, and the fixture returns it as `owned["run_id"]`.
    - The fixture's `connect_admin`:
      - opens a `connect_raw()` session and sets `row_factory = tuple_row`;
      - polls `SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND backend_type='client backend'` until it reads 0, for at most 5 s, rolling back after each read; past the bound it fails with "another database client stayed connected to the realm";
      - opens one more raw session when `state["extra_client"]` is set;
      - counts `state["admin_reads"]` and returns the polled session idle.
    - The cases:
      - `database-identity` writes the manifest with `docsuri-u6-fedcba9876543210`, asserted to differ from the realm's run id, and must refuse with `preservation database identity differs`;
      - `active-client` sets `extra_client` and must refuse with `other database clients prevent safe preservation`;
      - `destination` pre-creates `docsuri-u6-preserved-{owned["run_id"]}-deadbeef`;
      - the other ten cases are unchanged.
    - `test_a_completed_archive_leaves_no_key_file` asserts `admin_reads == 1`, and that `runId` and `volumePreserved` equal `owned["run_id"]` and `owned["run_id"] + "-pgdata"`.
    - The Docker, port, open-file and stop stand-ins stay recording only.
    - The module docstring says that the database reads run against the realm.
    - The file keeps its 10 tests (23 cases).
  - Run both files once on a development environment, in the direct form; they pass.

  Trace: U6:unit-test-instructions:never-mocked.

- [x] **Step 58 — Environment/build configuration — implement: U6's lint configurations and its CI step (L3-9, L3-10).**
  - (a) Create `scripts/u6-lint.toml` and `scripts/u6-lint-scripts.toml`, and under L3-10 (A) `scripts/u6-lint-accounts.toml`, as L3-9 and L3-10 give them. Each has a header comment naming its use.
  - (b) `.github/workflows/u6-approved-export.yml`:
    - add `- 'scripts/u6-lint*.toml'` under `on.pull_request.paths`;
    - replace the step at lines 105-115 (its name at 105, its folded command at 106-115) with:
    ```yaml
          - name: Lint export and shared runtime changes
            run: |
              set -eu
              ruff="$PWD/backend/.venv/bin/ruff"
              # 1. U6's tests: E, F, I, UP and B at 100, nothing ignored.
              "$ruff" check --no-cache --config scripts/u6-lint.toml tests/u6_approved_export
              # 2. U6's scripts: Ruff's default selection, extended with the same rules.
              "$ruff" check --no-cache --config scripts/u6-lint-scripts.toml \
                scripts/verify_docsuri_u6.py scripts/serve_docsuri_u6.py scripts/u6_*.py
              # 3. U6's backend files and the shared runtime files, under their own configurations.
              "$ruff" check --no-cache backend/modules/export backend/u6_*.py backend/key_custody.py \
                backend/local_profile.py backend/transactions.py backend/local_browser.py \
                backend/artifacts.py backend/local_host.py backend/u3_host.py \
                backend/modules/personalization/guarded_service.py ops/src/docsuri_ops/local_transport.py
              # 4. The U2 files U6 changes (cicd-pipeline §2.3), with nothing ignored.
              (cd backend/modules/accounts && "$ruff" check --no-cache \
                --config ../../../scripts/u6-lint-accounts.toml \
                control_keys.py services/control_lifecycle.py local_http.py services/guarded_entry.py)
    ```
    - Under (B), invocation 4 goes and its four paths join invocation 3.
  - (c) The snapshot. Before any fix, copy the five scripts, every `tests/u6_approved_export/**/*.py` and, under (A), the two U2 files that are wrapped and `shared/python-consumers.json` to `~/.docsuri-u8/lead-scripts/l3-records/u6-d-before/`, with a sha256 manifest. That folder is outside the repository and outside `/tmp`, which a restart empties.
  - (d) The baseline. Record each invocation's findings under the new files: tests 113, scripts 38, and under (A) the U2 files 30. Any finding beyond these, in a line Steps 54–57 wrote, is recorded beside them and fixed in Step 59.

  Trace: U6:unit-test-instructions:static-checks.

- [x] **Step 59 — Environment/build configuration — implement: fix what the configurations report (L3-11).**
  - (a) E402, in `verify_docsuri_u6.py`, `serve_docsuri_u6.py`, `u6_browser_fixtures.py` and `u6_real_export.py`:
    - each `sys.path.insert` writes `Path(__file__).resolve().parents[1]` inline, in the same order;
    - `ROOT` is defined once, right after the import block.
  - (b) I001:
    - `backend/.venv/bin/ruff check --no-cache --config scripts/u6-lint-scripts.toml --select I --fix scripts/verify_docsuri_u6.py scripts/serve_docsuri_u6.py scripts/u6_*.py`;
    - then `backend/.venv/bin/ruff check --no-cache --config scripts/u6-lint.toml --select I --fix tests/u6_approved_export`.
  - (c) E501, by hand. Fix every line the two record logs name (`records-check-20261117-210319-6257/01-u6-tests-u8-lint-config.log` for the tests, `records-check-20261117-220053-52710/11-u6-scripts-u8-lint-scripts-config.log` for the scripts), plus any line Step 58(d) added. Under (A), also the 30 U2 lines in `records-check-20261117-220053-52710/05-u2-accounts-e-f-i-up-b-100.log`.
    - Literals split at existing spaces or commas into implicitly joined parts.
    - Arguments, conditions and tuples are wrapped in parentheses.
    - The two docstrings are re-wrapped.
  - (d) B007: `repository/test_owner_guard.py:97` becomes `for call in units.values():`.
  - (e) UP031: `integration/test_export_http.py:236` becomes `content=f'{{"token":"{secret}","token":"{secret}"}}'.encode(),`.
  - (f) Under (A), the consumer inventory, with the local equivalent of `ci.yml:73-74`:
    - before the U2 wraps, `(cd shared/python && .venv/bin/python tools/inventory_consumers.py)`, and record what it prints, "ok" or the drift U8's uncommitted edits left;
    - after the U2 wraps, the same command with `--write`, then once more without it, which prints "ok: actual Python shared-contract consumers";
    - compare the new file with Step 58(c)'s copy. Only the `sourceDigests` entries of `backend/modules/accounts/local_http.py` and `services/control_lifecycle.py` may differ. Any other difference is U8's: record it as U8's and bring it to you before the step goes on.
  - Done when all of these hold:
    - the workflow step's invocations, run from the repository root exactly as written, all exit 0;
    - the root-suites lint still exits 0, run as the local equivalent of `ci.yml:202` (which runs `uv run --project backend ruff check backend/modules/accounts backend/modules/library backend/modules/ops tests`): `backend/.venv/bin/ruff check --no-cache backend/modules/accounts backend/modules/library backend/modules/ops tests`;
    - U8's folder-level lint of `backend/modules/accounts` under its own configuration still exits 0;
    - under (A), the inventory check prints "ok".

  Trace: U6:unit-test-instructions:static-checks.

- [x] **Step 60 — Environment/build configuration — check: the fixes leave the syntax tree unchanged (L3-11).** This is a check, not a test. A comparator outside the repository, `~/.docsuri-u8/lead-scripts/l3-records/u6-d-ast-compare.py`, parses each changed file and its Step 58(c) snapshot with `ast` and compares `ast.dump` without positions.
  - Normalisations:
    - each run of consecutive imports is compared as a multiset of (module, level, name, asname);
    - docstrings are compared with whitespace collapsed;
    - in the four restructured scripts, the earlier tree's `ROOT` assignment is removed, and `ROOT` inside the insert arguments is replaced by `Path(__file__).resolve().parents[1]`; the later tree must hold exactly one `ROOT` assignment, directly after the import block.
  - Expected differences: exactly two, B007's loop and UP031's expression, each printed. For UP031 it also asserts value equality for `secret` values containing `%`, `{`, `}` and quotes.
  - Everything else:
    - every other changed Python file, including the U2 files under (A), must compare equal, including its set of test function names;
    - any file that changed and is not in the snapshot manifest is a failure, except `shared/python-consumers.json`, which Step 59(f) compared.
  - Record each file's result and its sha256 before and after.

  Trace: U6:unit-test-instructions:static-checks; no production change.

- [x] **Step 61 — Environment/build configuration — tests: the lint gate (L3-12).** `tests/u6_approved_export/operations/test_u6_lint_gate.py`, with real Ruff 0.16.8 (`backend/uv.lock:1567-1568`), real files and nothing mocked:
  - `test_u6s_lint_configurations_hold_e_f_i_up_b_at_100_and_ignore_nothing`.
    - Reads the configurations with `tomllib`:
      - each has line length 100 and `py313`;
      - the tests file's `lint.select == ["E", "F", "I", "UP", "B"]`;
      - the scripts file's `lint.extend-select` is the same list, with no `select`;
      - under (A), the accounts file has `extend == "../backend/modules/accounts/ruff.toml"`, the same `select` and `ignore == []`;
      - no `ignore` (except that empty list), `extend-ignore`, `per-file-ignores`, `extend-per-file-ignores`, `fix` or `unsafe-fixes` appears at either level;
      - `backend/pyproject.toml` and `ops/pyproject.toml` select the same rules at 100 with no ignore.
    - Through `--show-settings`:
      - the tests' resolved rules equal those of `--isolated --select E,F,I,UP,B`;
      - the scripts' resolved rules contain the `--isolated` defaults plus E,F,I,UP,B;
      - every path of invocation 3 resolves to `backend/pyproject.toml` or `ops/pyproject.toml`.
    - Planted files in `tmp_path`, run from the repository root. Each planted file uses every name it imports, so F401 never fires and only the named codes do:
      - under `scripts/u6-lint.toml`, `import sys`, `import os`, a 101-character line (`VALUE = ` and 24 ones joined by ` + `, as U8's gate builds it) and `print(os.sep, sys.argv, VALUE)` give exactly {E501, I001};
      - under the same file, `import pytest` directly followed by `from docsuri_ops.local_transport import inspect_transport`, then `PAIR = (pytest, inspect_transport)`, gives exactly {I001}. `docsuri_ops` is third-party under Ruff's default `src` and first-party only through `ops/src`, so this finding holds only while the file's `src` is in force;
      - under `scripts/u6-lint-scripts.toml`, a function with a swallowed `except Exception: pass` gives exactly {S110, BLE001}.
  - `test_ruff_passes_on_u6s_files_and_writes_nothing`.
    - `backend/.venv/bin/ruff --version` is `ruff 0.16.8`.
    - Before and after, it records the sha256 of every linted file and the file listings of `.ruff_cache` under the root, `scripts/`, `tests/`, `backend/`, `ops/` and `backend/modules/accounts`.
    - Invocations 1–3, and 4 under (A), exit 0, run from their folders with globs expanded as bash expands them. `scripts/u6_*.py` must expand to exactly `u6_browser_fixtures.py`, `u6_preservation.py` and `u6_real_export.py`.
    - The snapshot is unchanged afterwards.
  - `test_the_workflow_step_runs_exactly_u6s_lint_invocations`.
    - `yaml.safe_load` of the workflow has exactly one step named "Lint export and shared runtime changes".
    - That step's one binary line is `ruff="$PWD/backend/.venv/bin/ruff"`.
    - Its `"$ruff" check --no-cache` invocations equal the expected list, with folder and argument words parsed as U8's gate parses its own.
    - `on.pull_request.paths` holds `scripts/u6-lint*.toml`.
  - `operations/test_u6_test_volume.py`: `"operations/test_u6_lint_gate.py"` joins `COMPONENT_FILES["EnvironmentTool"]`.
  - Run as exploration, with no environment needed: `backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/operations/test_u6_lint_gate.py tests/u6_approved_export/operations/test_u6_test_volume.py -q --tb=short`. The box is ticked on Step 63's coverage phase, which writes the evidence.

  Trace: U6:unit-test-instructions:static-checks; U6:code-generation-plan:testing-contract-test-volume.

- [x] **Step 62 — Withheld-behaviour checks.** Before the recorded runs and outside them, run each new or changed test once with the behaviour it awaits withheld.
  - Environment. The database-backed checks run on a development environment set up for this: `setup` and `migrate`, with `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` and `DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config`, its containers confirmed through Colima's socket. It is archived afterwards.
  - Command. The direct form scoped to the test's file: `DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini <file> -k <name> -q --tb=short`. The Vitest cases use the Step 56 command with `-t`, and the lint gate the Step 61 command; neither needs an environment.
  - Procedure. One shell command per edit:
    - copy the file to `~/.docsuri-u8/lead-scripts/l3-records/withheld/` and record its sha256;
    - make the one edit;
    - run the test and keep its exit code (`; rc=$?`);
    - copy the file back whatever the result;
    - confirm an equal sha256 before anything else runs.
    Keeping all of this in one command means no turn-end formatter or first-edit refusal can leave a temporary edit in place.
  - Record each run's failure and exit code. Files that already differ from the last commit (`lane.py`, `store_flows.py`, `test_u6_real_export_checks.py`, `history.tsx`, `verify_docsuri_u6.py` and `conftest.py` among them) are confirmed by sha256, never by `git diff`. Test files' digests are recorded only after any formatting.
  - The temporary edits, all reverted (line numbers are today's):
    - watch counts (Step 54), in `backend/modules/export/lane_store.py`, never by `CREATE OR REPLACE` in a realm:
      - (W1) line 600 returns the caller's clock: `SELECT jsonb_set(export.status_counts(%s),'{lane,observedAt}',to_jsonb(%s::timestamptz)) AS status` with `(now, now)`;
      - (W2) the same line returns the read time, `to_jsonb(clock_timestamp())` with `(now,)`;
      - (W3) line 610 drops `,observed_at=clock_timestamp()`;
      - (W4) line 610 stamps `clock_timestamp()+interval '1 second'`.
      Expected: W1 and W2 fail at the `observedAt` equality, W3 at `first < recorded`, and W4 at the bracket's upper end;
    - never-mocked, the pace hold (Step 55(c)):
      - `lane_store.py:588` catches only `Busy`;
      - `lane.py:265` becomes `if slot is not None and not slot.within_budget:`;
      - the test once without its `pace_hold`;
    - never-mocked, the store fault (Step 55(d)):
      - `lane.py:211` keeps the error's text (`failure = f"{type(error).__name__}: {error}"`);
      - `lane.py:213` adds `exc_info=True`;
      - `lane.py:229` keeps the error object (`failure = error`), so line 231 logs it as an argument;
      - `lane.py:210` catches only `(ValueError, TypeError)`;
      - the test once without its hold, and once with only the effect row held;
    - never-mocked, the outcome (Step 57(a)):
      - `scripts/u6_real_export.py:165` becomes `if not rows:`;
      - `:146` ends with `LIMIT 1`;
      - `:146` compares `e.id<>%s::uuid`;
      - `:138` hashes a missing value as the empty string;
    - never-mocked, the archive (Step 57(b)):
      - `scripts/u6_preservation.py:110` compares only the database name;
      - `:116` becomes `if active > 1:`;
      - `:114` loses `AND backend_type='client backend'`;
      - `:113` loses `pid<>pg_backend_pid()`;
      - the active-client case once without its extra session;
      - the destination case once with its folder named from the old constant;
      - the fixture's rollback: `test_a_completed_archive_leaves_no_key_file` with a temporary extra raw session that a `threading.Timer` closes 0.5 s into the poll. With the rollback in place it passes, because the poll sees the session leave. With the rollback removed it must fail with "another database client stayed connected to the realm", because the poll keeps reading its first snapshot;
    - NFR3.8 (Step 56):
      - `frontend/src/u6-export/history.tsx:137` renders the title through `dangerouslySetInnerHTML`;
      - `dialogs.tsx:183`'s first `<strong>` does the same;
      - `status.tsx:39`'s announcement `<span>` does the same;
    - static checks (Step 61):
      - `extend-ignore = ["E501"]`, then separately `line-length = 120`, in `scripts/u6-lint.toml`;
      - `src` removed from the same file; the `docsuri_ops` planted file then passes, and the test fails;
      - `select` in place of `extend-select` in `scripts/u6-lint-scripts.toml`;
      - under (A), `ignore = []` removed from `scripts/u6-lint-accounts.toml`;
      - one wrapped line of `tests/u6_approved_export/conftest.py` back on one line;
      - the `ROOT`-first header back in `scripts/serve_docsuri_u6.py`;
      - under (A), one SQL line in `control_lifecycle.py` back on one line;
      - `--no-cache` dropped from the gate's Ruff helper; afterwards the cache files that run created are deleted, and the deletion is recorded;
      - the old folded step back in the workflow;
      - the `scripts/u6-lint*.toml` path line removed;
      - the gate's mapping line removed from `test_u6_test_volume.py`;
    - the two tests the lint fixes change (Step 59(d) and (e)):
      - `repository/test_owner_guard.py::test_every_owner_unit_refuses_an_ended_session_and_leaves_rows_untouched` once without its `flows.end_session` line. It must fail at its `pytest.raises`. That run may commit rows for the owner on the development realm, which is archived afterwards;
      - `integration/test_export_http.py::test_a_configure_body_that_fails_validation_is_not_echoed` with the duplicate-key refusal at `backend/local_browser.py:198` answering 400 instead of 422. Only the rewritten duplicated body reaches that refusal, so the test must fail at its status assertion.
  - No withheld edit touches an applied migration.

  Trace: the project's rule on withheld checks.

- [x] **Step 63 — Run and record.** Archive every development environment. Then, on fresh realms, with Docker only through Colima (`DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`, `DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config`) and containers confirmed through Colima's socket:
  - Realm A: `setup`, `migrate`, `coverage` (with the second report) and `frontend`, then `archive-owned`.
    - Coverage: 949 passed (945 plus Step 54's 1 and Step 61's 3).
    - The backend total, `scripts/u6_preservation.py` and `src/u6-export` each stay at or above 80%.
    - Frontend: 123 passed.
  - Realm B: `browser` on its own fresh realm, all 14 journeys passing. Step 59 changes the fixture and serve scripts' layout, so the browser phase runs again.
  - Static checks:
    - U6's `tsc` command with `--incremental false`;
    - its ESLint command, including `e2e/u6-approved-export`;
    - the CI lint step's invocations exactly as written, from the repository root, each with its own log;
    - the shared contract's lint, from `shared/python` with its own `.venv/bin/ruff check --no-cache .`, as run 4's step 90 ran it.
  - Regressions:
    - the earlier Units' regressions as U6's workflow runs them: U1's two files, U2's two files, and U2's keyring trio, last 75 passed and 1 deselected;
    - U2's cumulative lane, which has `test/u6-export` registered: 728 becomes 731.
  - Drift checks, because Step 62's withheld edits touched files both inventories pin (`backend/local_browser.py`; `history.tsx` and `dialogs.tsx`):
    - `(cd shared/python && .venv/bin/python tools/inventory_consumers.py)` prints "ok", in either case, and under (A) after Step 59's regeneration;
    - from `frontend`, `node scripts/inventory-consumers.mjs` (`pnpm run check:consumers`).
  - Then update the records:
    - `code-summary.md`:
      - L3-1 to L3-12 with your answers;
      - the four targets mapped to the tests that close them, with NFR3.8's remaining browser-only gap stated unless L3-8 is built;
      - each component's test count, file by file, against the standard strategy's five to eight, counts above eight marked "above range, kept": ExportStore 92, ExportLane 35, EnvironmentTool 75, history.tsx 18 (correcting the stale 15 at line 236), dialogs.tsx 9, export-view.tsx 16;
      - the collect-only total, 949;
      - each withheld run's failure, exit code and digests;
      - Step 59(f)'s inventory results under (A), and Step 60's comparator result.
    - `unit-test-instructions.md`, a new "Build and Test loop-back 3 (2026-11-17)" section:
      - New files: `operations/test_u6_lint_gate.py`.
      - New helpers: `store_flows.held_rows` with `PACE_ROW`, `EFFECT_ROW` and `LANE_STATUS_ROW`; `Interleaved`'s pace hold; `database_now` in `repository/test_status_counts.py`.
      - Lint: a bullet naming the configurations and the rules, and a "Static checks: Ruff" command block identical to the CI step.
      - Commands: `operations/test_u6_preservation.py` now needs the realm, for reads only, through `connect_raw`; the lint gate needs none.
      - Never mocked: the lane's store faults, the operator's outcome and the archive's database check are reached only through the realm.
      - Allowed doubles: L3-4's two rules, the delegating wrappers (`connect_admin` among them) and the recording stand-ins; under L3-5 (a), `FakeResearch` with its reading.
      - Clock: the 1 s lock-bound waits listed again, adding the one in the pace test and the three in the store-fault test (the capture, the claim and the status record); each hold under the realm's 5 s idle-in-transaction bound; the archive fixture's bounded 5 s poll; the amended database-clock line.
      - Frontend: the three hostile cases.
      - Withheld checks: Vitest and gate runs need no environment, and every restore is unconditional.
    - `traceability.json`:
      - the never-mocked row gains `component/test_lane_write_path.py`, `operations/test_u6_real_export_checks.py`, `operations/test_u6_preservation.py` and steps 55, 57 and 62;
      - the watch-counts row's steps string becomes "45, 54, 62";
      - add rows for NFR3.8/provider-text and the static checks.
    - `source-manifest.json`: add `scripts/u6-lint.toml`, `scripts/u6-lint-scripts.toml`, under (A) `scripts/u6-lint-accounts.toml`, and `tests/u6_approved_export/operations/test_u6_lint_gate.py`. Every other path is already listed, `shared/python-consumers.json` included.
  - Tick each box only after the run its own text asks for has passed.

  Trace: stage Step 5.

After Step 63, the architecture review and U6's checkpoint follow through AI-DLC (stage Steps 5 and 6). They are not plan steps, so each box above can be ticked on its own run before the review starts. When this attempt's approval clears the boxes of Steps 1–52, their work stands: each is ticked again only after Step 63's runs, which exercise it again, have passed, as the project's rule asks. U8's reopen follows U6's in this loop-back, and its checkpoint verification runs last, over every Unit's final code, including any U2 lines wrapped under L3-10 (A).

**Loop-back 3 traceability** (target → the file that closes it → step):

| Target | Closed by | Steps |
|---|---|---|
| U6:unit-test-instructions:never-mocked | `tests/u6_approved_export/store_flows.py` (`held_rows`); `component/test_lane_write_path.py`; `operations/test_u6_real_export_checks.py`; `operations/test_u6_preservation.py`; Allowed doubles in `unit-test-instructions.md` (L3-4, L3-5) | 55, 57, 62, 63 |
| U6:logical-components:watch-counts | `tests/u6_approved_export/repository/test_status_counts.py` | 54, 62 |
| U6:NFR3.8/provider-text | `frontend/test/u6-export/history.test.tsx`; `dialogs.test.tsx`; `export-view.test.tsx` (the jsdom side; the browser side stays open unless L3-8 is built) | 56, 62 |
| U6:unit-test-instructions:static-checks | `scripts/u6-lint.toml`; `scripts/u6-lint-scripts.toml`; under L3-10 (A) `scripts/u6-lint-accounts.toml` and `shared/python-consumers.json`; `.github/workflows/u6-approved-export.yml`; the fixed tests and scripts; `tests/u6_approved_export/operations/test_u6_lint_gate.py` | 58–61, 62, 63 |
| U6:code-generation-plan:testing-contract-test-volume | `tests/u6_approved_export/operations/test_u6_test_volume.py` (the gate's mapping) | 61 |

## Traceability

| ID | Steps |
|---|---|
| Build and Test loop-back 1: the 2 Not Met and 19 not fully checked U6 targets; decisions L1-1 to L1-12 | 29–43 |
| Build and Test loop-back 2: U6's never-mocked rule (Not Met) and its ten unchecked clauses; decisions L2-1 to L2-4 | 44–52 |
| Build and Test loop-back 3: U6's never-mocked rule and static checks (Not Met), and its two clauses with no test, the watch counts' time and NFR3.8's provider text; decisions L3-1 to L3-12 | 53–63 |
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
