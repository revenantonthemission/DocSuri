# U6 — Approved export · Code summary

Unit `u6-approved-export` · branch `feature/u6-approved-export` · built from the approved [code-generation-plan.md](code-generation-plan.md) and [unit-test-instructions.md](unit-test-instructions.md) · 2026-10-20.

## Summary

U6 lets an owner send one prepared novelty-analysis result to their own Notion workspace as a new page, only after an explicit approval of the exact preview.

- **Connect.** The owner pastes an internal-integration token. DocSuri checks it with Notion first, then stores it sealed with AES-256-GCM. The seal is bound to the account, the connection and its revision, under U6's own key folder. The token never leaves that path: it is not in logs, responses, errors or the browser's storage.
- **Choose, preview, approve.** The owner picks a page shared with the integration. DocSuri renders the page body from U4's export read, freezes it as a preview revision with a hidden marker, and shows exactly what will be written. One press of "승인하고 내보내기" approves that revision and starts the export.
- **Write once, reconcile unknowns.** A single background lane writes outside any database transaction. It re-checks the binding before every write, and reads the page back afterwards. An unclear outcome is never written again: the lane scans the destination for the marker, and the owner can settle it when checks cannot decide.
- **History, cancel, settle, lifecycle.** The owner sees every export with its state and next step. Cancel works until the write starts. Withdrawal and erasure end pending work and delete U6's records, keeping count-only evidence.
- **Synthetic by default.** Every test and CI run uses a local fake Notion behind the real SDK client. The one real export runs later, only after the owner approves its exact content ([u6-real-export-runbook.md](u6-real-export-runbook.md)).

## What was built

### Backend module `backend/modules/export/`

| File | Role |
|---|---|
| `errors.py` | `ExportError` (code, `current`, `retry_after`) and `ProtectionUnavailable` |
| `u6_schema.sql`, `u6_custody.sql`, `u6_maintenance.sql` | Schema `export`, its triggers and grants; the token-envelope functions; holder-guarded pending deletes, purge, erase and status counts |
| `repository.py` with `store_support.py`, `connection_store.py`, `preview_store.py`, `approval_store.py`, `effect_reads.py`, `lane_store.py`, `housekeeping_store.py` | `ExportRepository`: the owner-guarded and service units, split by concern |
| `token_keyring.py`, `token_vault.py`, `key_commands.py` | U6's key folder, the sealed-token envelope, and the operator key commands |
| `rendering.py` | Title, marker, page body, limits, rendered text, content and binding hashes |
| `notion_session.py`, `classification.py`, `notion_adapter.py`, `fake_notion.py` | Guarded transport and interactive gate; fixed error categories; identify, listing, page read, write, read-back and scan; the local fake Notion |
| `service.py`, `views.py`, `binding.py` | `ExportService` (the eleven operations), wire projections, and the one shared binding check |
| `lane.py`, `worker.py` | The single write lane, and the worker pass step (housekeeping, orphan sweep, hand-over) |
| `control_lifecycle.py` | `ExportLifecycleParticipant` (withdraw, reactivate, erase) |
| `http.py` | The eleven C09 routes under `/api/v2/c09/` |

### Outside the module

- **Shared custody and U2:** `backend/key_custody.py` is the shared keyring helper. `backend/modules/accounts/control_keys.py` became a thin setting of it, with U2's behaviour unchanged. `backend/modules/accounts/u6_lifecycle_guard.sql` maps ApprovedExport to its role (A8). `backend/modules/accounts/services/control_lifecycle.py` gained the retained-reason rule (A8).
- **Policy and composition:** `backend/u6_policy.py` holds `ExportPolicy`, `SYNTHETIC_EXPORT` and the real activation policy. `backend/u6_host.py` provides `export_contribution` and `assemble_u6`. `backend/u6_real_export.py` provides the operator-only `assemble_u6_real`. In `backend/u3_host.py`, the topics gate also admits U6, a new export gate is added, and the lane joins the lifespan. `backend/u4_host.py` and `backend/u5_host.py` pass the export factory through.
- **Registrations (R-06 rows 1–12):** `backend/local_profile.py`, `backend/transactions.py`, `backend/local_browser.py`, `backend/artifacts.py`, `backend/local_host.py`, `backend/local_observation.py`, `backend/lifecycle_effects.py`, `backend/modules/accounts/local_http.py`, `backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py`, `ops/src/docsuri_ops/local_transport.py`.
- **Dependency:** `notion-client==3.1.0` in `backend/pyproject.toml` and `backend/uv.lock`.
- **Environment tool and scripts:** `scripts/verify_docsuri_u6.py` (every phase), `scripts/u6_preservation.py`, `scripts/u6_browser_fixtures.py`, `scripts/serve_docsuri_u6.py`, `scripts/u6_real_export.py`.
- **Frontend:**
  - `frontend/src/u6-export/` (the view, connect form, stepped flow, history, dialogs, status and copy, styles);
  - `frontend/src/u4-research/export-action.tsx` and `research-workspace.tsx` (the entry on the novelty result);
  - the R-04 additions in `frontend/src/App.tsx`;
  - safe codes and Korean copy in `frontend/src/api.ts`.
- **Shared contract:**
  - edited in the canonical source, `aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`, raising C09 from 2.0.0 to 2.1.0 and the release from 3.0.0 to 3.1.0;
  - regenerated: `shared/dtos/workspace.schema.json`, `shared/events/execution.schema.json`, the binding generation `8f48d3dd…` with `_binding_head.json`, and `frontend/types/wire/dtos.ts`;
  - golden hash vectors in `shared/export-hash-vectors.json`;
  - both consumer inventories refreshed.
- **Tests and configuration:**
  - backend: `tests/u6_approved_export/` across five layers, `backend/pytest.u6-approved-export.ini`, `backend/.coveragerc.u6`;
  - shared: `shared/python/tests/test_export_contract.py`;
  - frontend: `frontend/test/u6-export/`, the U4 entry and shell tests, `frontend/e2e/u6-approved-export/`, the U6 tsconfig, Vitest and Playwright configs, and one glob in `frontend/vitest.u2-cumulative.config.ts`.
- **CI:** `.github/workflows/u6-approved-export.yml`, with four jobs: shared contracts, frontend, backend, browser.

- **U4's tool (the person's choice):** `scripts/verify_docsuri_u4.py` (expired-environment archive), with `tests/u4_research_novelty/operations/test_archive_expiry.py` (new) and `test_runner_transport.py` (one stub) — deviation 37.

- **U4's research job panel (deviation 38):** `frontend/src/u4-research/jobs.tsx` keeps keyboard focus on its buttons while they load.

[source-manifest.json](source-manifest.json) lists all 191 application paths.

## Test and verification results

Every command and its result, as it happened, is in [u6-build-verification-log.md](u6-build-verification-log.md).

| Check | Result | Floor or bound |
|---|---|---|
| Backend coverage, fresh environment A (`docsuri-u6-fe9655874b563cd8`), all five layers | 802 passed; 90% total | 80% |
| `scripts/u6_preservation.py`, second report | 99% | 80% |
| Frontend U6 lane | 109 passed; 98.5% lines of `src/u6-export` | 80% |
| U4 lane / U3 lane | `src/App.tsx` 61.1% / 53.63%; `src/u4-research` 99.7% | App.tsx ≥ 48%; u4-research ≥ 80% |
| U2 cumulative lane | 371 passed; `src/` 96.24% | — |
| Shared contract suite | 205 passed; all six drift checks clean | — |
| Construction Verification Command, fresh environment B (`docsuri-u6-94b0d78dfa7fd641`) | 11 passed, 0 failed, 77.3 s; peak memory 990,494,720 bytes | 300 s; 1 GiB |
| The same command at the checkpoint (`docsuri-u6-d3523e3b93863867`) | **Failed:** 9 passed, 1 failed, 1 not run (keyboard focus; deviation 38) | — |
| After the fix: three consecutive runs, each on a fresh environment (`docsuri-u6-a455df9104d89b88`, `-632fd442a3636af4`, `-97f644676be419a0`) | 11/11 each; 80.6 s, 80.9 s, 75.9 s; peak memory 1,035,042,816 / 1,003,864,064 / 1,001,144,320 bytes | 300 s; 1 GiB |
| U4 lane after the fix | 83 passed; `src/u4-research` 99.78%, `src/App.tsx` 61.1% | ≥ 80%; ≥ 48% |
| The same command at U5's checkpoint, after the Mac's restart (`docsuri-u6-9422a43afe2291e1`) | **Failed:** 9 passed, 1 failed, 1 not run (the settle dialog's focus trap; deviation 39) | — |
| After the focus-trap fix: U6 lane / U2 cumulative lane | 113 passed, 98.53% lines (`dialogs.tsx` 100%) / 377 passed | 80% / — |
| After the fix: U5's checkpoint run (`docsuri-u6-8dec1b7265c28b43`) | 11/11; 76.5 s; peak memory 947,650,560 bytes | 300 s; 1 GiB |
| U2 keyring regression (cicd §2.4) | 67 passed, 1 deselected, unchanged before and after the extraction | — |
| U5's U1 and U2 regression files | 13 and 39 passed | — |
| Next-app checks | `tsc --noEmit` and `tsc -p tsconfig.e2e.json` pass; full `vitest run` 865 passed | — |
| U2 environment phases (new `docsuri-u2-dbffdb35aaa868db`) | component 112, integration 38, operations 194, all passed | — |
| U5 coverage (new `docsuri-u5-e41cf4e7d2bf5160`) | 255 passed, 85% | 80% |
| U4 coverage (new `docsuri-u4-5e615b9cb245ce9e`, after archiving the expired `docsuri-u4-8da1d88967785045`) | 236 passed, 0 failed; 88.74% | 80% |
| U4 tool tests (after the expired-environment archive fix) | 98 passed (78 before, plus 20 new) | — |

Measured U2 files in U6's coverage: `control_keys.py` 95%, `control_lifecycle.py` 32%, `guarded_entry.py` 56%, `guarded_service.py` 59%. `backend/u3_host.py` is at 86%. The low U2 figures are the lines that need U2-only schema, as the plan's "Coverage scope" decision expected. The total still clears 80% without any exclusion.

## Decisions and deviations from the plan

### Product behaviour

1. **Cancel race (outcome step).** When the lane marks an accepted export as waiting, the effect's revision advances. A cancel pressed before the next 3 s poll carried the old revision and got "취소할 수 없습니다", although the export was still cancellable. On that conflict the outcome step now re-reads the effect. If it is still accepted at a newer revision, the step sends the cancel once more at that revision. The compare-and-set still refuses an export that has started. Covered by Vitest.
2. **Cancel race (history panel).** The history row's cancel got the same fix and two Vitest cases.
3. **Owner-settled delivery.** Settling as delivered stores only the owner's own link (`remoteUrl`), never a reference. The link is shown labelled "직접 확인됨" only when the owner supplied one.
4. **History "미리보기 다시 만들기".** History entries carry no result reference, so the history row shows guidance to reopen the result from 참신성 분석. The outcome step's own button prepares a fresh preview directly.
5. **Oversized results.** A malformed or oversized U4 result answers `SOURCE_INELIGIBLE` with `current={"field": "size"}`, because prepare's frozen list has no size code. A result that breaks a limit is refused, never truncated. BR2.4's "every result fits" holds for realistic results; a pathological one with dozens of tiny assessments is refused.
6. **Listing on an unusable connection.** A disconnected or revoked connection answers `NOT_FOUND`; an unavailable one answers `POLICY_UNRESOLVED`. A stored-token 401 during a listing revokes the connection and answers `NOT_FOUND`.
7. **Destination identity.** `formatRevision` is a fixed server value, "1". The server derives every destination identity fact, and a mismatching `connectionId`, `workspaceId` or `formatRevision` answers `CONFLICT`.
8. **Synthetic limitation.** The synthetic composition adds `"synthetic-only"` to `ExportConnection.limitations`.
9. **Configure details.**
   - Only a definite `INVALID_TOKEN` keeps a configure replay record.
   - Configure sends the record's current revision for every visible record, and `null` only for a first connect.
   - The token field is cleared the moment a submit starts.
   - Response validators accept only `https:` links.
10. **Settle assumptions.** These are stored as fixed keys: `owner-confirmed-page-present` and `owner-accepts-possible-second-copy`.
11. **Press retries.** A press keeps its idempotency key for a retry after `UNKNOWN_OUTCOME`, `CAPACITY_EXHAUSTED` or `OUTCOME_UNKNOWN`.

### Lane, worker and lifecycle

12. **Token cannot be opened after the claim.** Nothing is sent. The attempt is recorded as refused, and the effect fails as `connection-changed` (token missing) or `policy-unresolved` (key protection unavailable), following §8.4's content-rejected precedent.
13. **Fair hand-over.** An item already handed over at its current revision goes behind the rest of the batch until every due item has had a turn. This is held in memory only.
14. **Waiting checks.** A waiting effect is checked again on every pass; BR3.3 sets no interval.
15. **Partial pass failures.** A pass step that fails lets the remaining steps run, then raises `ExportPassIncomplete` with fixed step names only.
16. **Resumed exports.** A resumed export that hits could-not-check stays executing and fails as `dependency-unavailable` once its rate-limit window is spent (functional spec, row 232).
17. **Orphan sweep.** It closes the outstanding attempt as uncertain and adds `"orphaned-attempt"` to the effect's limitations.
18. **Paged checks.** The session and source checks page with `after`/`resumeAfter`, so old approvals cannot starve newer ones.
19. **Withdrawal.**
    - Withdrawal also trims the rendered copies of what it invalidates, in the same transaction.
    - A revoked connection stays revoked.
    - Both `live_records` and `pending_work` run the withdraw step; only the `live_records` ticket erases.
    - `export.lifecycle_release_pending` exists because a pending row cannot become disconnected.

### Contract, policy and rendering

20. **Rate-limit wait.** A rate-limited write uses the frozen C12 `retry_later.retryAfterSeconds`. The plan's "retry_later adds the stated wait" therefore adds no new field.
21. **Named enums.** Every new enum is its own named def, because the generator numbers inline enums by position, so the release adds more public defs than the plan lists.
22. **Small contract additions.** A header sentence records release 3.1.0, and `ExportConnectionRead` has a description.
23. **Hourly checks.** The policy value `check_hourly_until_seconds = 21600` (6 h) fixes when hourly checks stop; the approved wording does not say.
24. **Real policy.** `REAL_ACTIVATION_EXPORT` is a builder function, because it needs the activation destination and the free-terms reference. Extra policy values: `key_lock_retry_ms` 100, `key_lock_wait_ms` 5000, `token_max_length` 512, batch sizes 10 and 50, history page 20.
25. **Rendering choices.**
    - The Korean section headings (요약, 평가, 근거, 한계) and the stance, coverage and source labels are the builder's choice; changing them bumps the render policy revision.
    - Limits are read conservatively: UTF-16 code units, and 500 KB as 500,000 bytes of ASCII-escaped JSON.
26. **Notion boundary.**
    - Requests are restricted to five paths with `page_size`/`start_cursor`.
    - `Accept-Encoding: identity` is forced.
    - New bounds: `MAX_SEARCH_PAGES` 10, `MAX_SCAN_BLOCKS` 5000, `MAX_CHILD_PAGES` 20.
    - The workspace identifier is pinned to `bot.workspace_id` of `GET /v1/users/me` (Notion API reference, version 2026-03-11).

### Structure and tooling

27. **Extra files beyond the plan's names:** the store modules, `views.py`, `status.tsx`, `export-flow.test.tsx`, and the test helpers `export_rows.py`, `store_flows.py`, `notion_flows.py`, `service_flows.py`, `lane_flows.py`, `http_flows.py`.
28. **Size guideline.** `scripts/verify_docsuri_u6.py` is 1,463 lines, over the 800-line guideline, to mirror U5's single tool (1,421 lines).
29. **Shared helper settings.** `CustodySettings` carries no folder, because U2's folder is per-instance; it is passed per call.
30. **Key rotation.** Rotation with three versions retires the oldest and adds a new one in one publish, so the generation advances by 2.
31. **Archive and coverage records.**
    - The archive also reports `keyFileFound` and `keyFolderRemoved`.
    - The coverage phase records the total and the preservation-only report.
32. **Delegated clock.** `advance-clock` moves the clock to one hour past the later of the delegated instant and real time.
33. **Startup order.** The lane starts before the control loop. `assemble_u6` also refuses an environment holding `real-export.json`; a missing `fake-notion.json` gives an empty fake.
34. **Test fixtures.**
    - Owner B in the persistent realm gets a synthetic password and an `@u6.fixture.example.com` address.
    - The assembly test filters due items to its own, because database- and repository-layer tests leave account-less rows in a persistent realm. Every test also passes on a fresh environment.
35. **Fragile test fixed.** An operations test that assumed no clock file now checks what the refused call did, so it holds on a used environment too.
36. **Process.** Twice a builder changed a file through the shell: one heredoc edit of a test and one `ruff --fix` that removed an unused import. Both results were checked and kept.
37. **U4's archive handles an expired environment (the person's choice, 2026-10-20).** Step 27's U4 coverage run first could not start: U4's local environment had passed its 24-hour retention, and U4's `archive-owned` refused it.
    - The person chose to give U4's tool the expired-environment handling U5 already has. In `scripts/verify_docsuri_u4.py`, `archive-owned` now reads the environment file through `preservation_manifest()`. That function uses U5's existing `LocalProfile.preservation_identity`, which accepts an expired environment for preservation without making it runnable. It also requires U4's own path, unit, realm and database. The shared identity check moved into `require_manifest_identity()`, and `manifest()` behaves as before. Every other check stays, nothing is deleted, and no expiry changes.
    - Tests: `tests/u4_research_novelty/operations/test_archive_expiry.py` is new, with 20 tests. The existing archive test in `test_runner_transport.py` stubs the new function, and its assertions are unchanged.
    - The old database container had been stopped since 2026-10-17. It was started once so that `archive-owned` could run all its checks, then stopped and preserved by the tool.
38. **Keyboard focus on the novelty result (found by the checkpoint's verification, 2026-10-20).** The checkpoint's first run of the Construction Verification Command failed one journey, `keyboard.spec.ts` "settle by keyboard": Tab never reached `novelty-export-open`. There were two causes.
    - **Product.** In U4's `frontend/src/u4-research/jobs.tsx`, pressing "준비된 결과 열기" or "진행 상태 새로고침" set the focused button to `disabled` while it loaded. A focused button that becomes disabled drops keyboard focus to the page body, so the next Tab restarts at the top of the page. Both buttons now use `aria-disabled`: they stay focusable, presses are ignored while unavailable, and the existing `button[aria-disabled='true']` style shows the state.
    - **Test.** `keyboardPreview` started tabbing without waiting for the result to load. It now waits for the opened result and `novelty-export-open`, and checks that focus stayed on the pressed button. No sleeps were added, and no limit, bound or check changed.
    - Two new Vitest cases in `frontend/test/u4-research-novelty/export-action.test.tsx` failed before the fix and pass after it.
    - `jobs.tsx` is U4-owned and is not in the plan's "What U6 changes outside its module" table, so it is recorded here for approval.
    - The other "1 error was not a part of any test" in that run was Playwright's own early-stop notice under `--max-failures=1`, not a separate fault.
39. **The dialogs keep keyboard focus on every route (found by U5's checkpoint run, 2026-10-20; the person chose the fix).** After the Mac restarted, U5's checkpoint run on a fresh environment failed one journey, `keyboard.spec.ts` "settle by keyboard": a Shift+Tab left the open settle dialog for the history link just before it. Four earlier fresh runs had passed, and a quiet copy of the dialog in the same Chromium stays trapped, so the escape depends on timing; the run was under very heavy load.
    - **Cause.** `DialogShell` caught Tab only on its first and last focusable elements, left every other move to the browser, and did nothing when focus left by another route.
    - **Fix (`frontend/src/u6-export/dialogs.tsx`).** The shell now moves every Tab and Shift+Tab itself between the dialog's stops, wrapping both ways; a radio group is one stop (its checked radio, or its first while none is checked). While the dialog is open, focus that lands outside goes back to where it was inside, or to the first stop. Open, Escape, focus return, the arrow keys, markup and copy are unchanged, for both dialogs.
    - **Proof.** Four new tests in `frontend/test/u6-export/dialogs.test.tsx` fail on the old trap and pass with the fix. U5's checkpoint run then passed 11/11 (verification log, section 11).
40. **The browser runners measure proportional memory on Linux (PR #54's CI; the person asked for the fix).** GitHub's Linux runner stopped U6's browser phase on the 1 GiB budget at 1,075,593,216 bytes, because summing `ps` RSS counts every page Chromium's processes share once per process. U6's and U5's runners now enforce the same 1 GiB budget on Linux on the sum of each process's proportional set size from `/proc/<pid>/smaps_rollup`, with a process that cannot be read counting its full RSS. macOS keeps the stricter RSS sum, and records carry both peaks. The same change fixed U5's browser fixture clock, which made a nightly (00:00–09:00 KST) run of U5's digest journey fail (verification log, section 11.10).

### Build and Test loop-back 1 (2026-10-28)

The plan's "Build and Test loop-back 1" section holds the decisions L1-1 to L1-12 and the readings; these are their records for the U6 checkpoint, written before any of Steps 29–43 changed a file (Step 29). The same list is carried in [traceability.json](traceability.json) under `loop_back`.

- **L1-1 — the preview's destination is chosen from the connection's current listing.** `ExportService.prepare_preview` treats the request's `destinationId` (or `parentPageId` when that optional field is absent) as the *identity* of a listing entry, never as a request path: the server re-lists inside the one gated operation (`NotionAdapter.locate_destination`), and the recorded destination, its title, its context and the `bindingHash` come from that listing entry. Outside a complete listing answers `CONFLICT` (field `destination`); outside a partial or unavailable listing answers `DEPENDENCY_UNAVAILABLE`; a `destinationId`/`parentPageId` mismatch answers `CONFLICT` before any Notion call. **A1 restatement:** "the request's `destinationId` (or `parentPageId` when absent) names an entry of the connection's current listing; the recorded destination is that entry." `ExportService._read_destination` is deleted; `BindingCheck` keeps reading through `adapter.read_destination`.
- **L1-2 — integration rigs run U4's real export read.** `service_flows.real_research` and `Rig.ready` produce one ready novelty result per conftest owner per realm through `ready_novelty` (cached run-bound in `integration-novelty.json`); `http_flows.mount` and the integration lane rigs hand the service that instance; `ResearchDouble` stays reachable only from component rigs. The `due_items` stub is dropped and both conftest owners are freshened instead; `UsageQuotaExceeded` is a failed prerequisite, never a skip.
- **L1-3 — the one real export stays operator evidence.** The real-press target (`U6:NFR6.3/real-export-approval`) cites L1-3: its matrix row stays "Not runnable in this stage", with the gating chain covered by `tests/u6_approved_export/component/test_real_export_gates.py` and the press itself left to `u6-real-export-runbook.md` §6–§8 operator evidence (at Build and Test if run there, else deployment-execution under U8's provider gate).
- **L1-4 — the `pending` connection state is pinned as unwatched.** `export.status_counts` counts four connection states and omits `pending`; the new test pins exactly that (`sum(connections) == count(*) - count(state='pending')`) and the gate records the omission. A new migration follows only if the person wants `pending` counted.
- **L1-5 — the check schedule is pinned as the code reads the design row.** Checks at 3, 10 and 30 minutes after the deadline, then hourly counted from the previous check (1h30 … 5h30, up to `check_hourly_until_seconds = 21600`), then every three hours (8h30 … 23h30): fourteen checks, the last at 84,600 s. The tests derive every point from the policy fields, so the cadence can be redirected by changing `store_support.py` and the expected lists.
- **L1-6 — the oldest-unknown age counts from the latest attempt's `deadline_at`** (the §8.6 comment in `u6_maintenance.sql`); logical-components §8 says only "the age of the oldest unknown effect". Pinned; the gate records it for accept-or-redirect.
- **L1-7 — the SDK write timeout through the lane is the remaining time to `deadlineAt`**, at most 90,000 ms and floored at `MIN_WRITE_SECONDS`; reads assert 30,000 ms.
- **L1-8 — test counts above eight are recorded and kept.** The five-to-eight range is checked by the component map in `operations/test_u6_test_volume.py` and by runtime counts per JUnit classname (`testsByClass`); a component above eight is recorded as above the range and kept, never trimmed.
- **L1-9 — the reflow fixtures change is a fixture-identity change.** Adding `reflow` to `SPECS` changes `SCENARIO_NAMES`, so every earlier environment is archived (`--phase archive-owned`) before the coverage or browser phases; `FIXTURE_VERSION` stays `u6-browser-v1`. **The reading of Step 26's `reflow.spec.ts` bullet:** "a 320 CSS px viewport across every U6 view, step state, the history and both dialogs, with a descendant walk for nested scroll containers and a viewport guard". The settle dialog is measured in the existing settle journey by toggling the viewport to 320×640 and restoring it.
- **L1-10 — the coverage floor stays a single-source rule.** `.coveragerc.u6` keeps `fail_under = 80` and its fourteen patterns; the runner passes no `--cov-fail-under`; new tests pin that pytest-cov adopts the rcfile floor and that no U6 test or migration names U2-only schema. No file leaves the list.
- **L1-11 — targets that belong to a later stage are named, not tested here** (the hosted key folder, the error reporter, U8's logger levels, `pip-audit` in CI, the CI gate, U8's metrics; the worker-connection wording is a note for U8).
- **L1-12 — the operator fixture may read export tables for negative assertions only** (the envelope columns in hex and base64 for the key-material and plaintext scans); it never seeds rows or bypasses a runtime grant to make a behaviour pass.

#### Step 41 — configuration and measurement (2026-10-30)

The loop-back additions in `unit-test-instructions.md` were checked against Steps 30–40 as built; the wording matches. The first real runs on a fresh realm surfaced test-code corrections, recorded here instead of editing the instruction file (no production file changed beyond Step 31's recorded service/adapter edits):

- the Step 33 log tests vs pytest's capture: `caplog` attaches its handler to every non-propagating logger, so the dedicated SDK logger's own token-free warning records always land in `caplog.records`; the tests now assert the design's real promise instead — nothing from `docsuri.export*` beyond that one logger, and nothing at all reaches the root, proven with a root-attached probe handler.
- `test_log_content.attempt` re-connects the same token after a token-invalid revocation; its stored-row scan reads `e.remote_url` (the column lives on `effect`) and counts `preview_revision` through its pair.
- the NFR3.9 no-emission case queues the 500 after the healthy call; the SDK-settings case filters pytest's ambient handlers off the logger's handler list.
- the cadence test's `due_items` look-ups move to the 1800→5400 next-check point, when the effect is actually due.
- the assembled-app body-bound test refreshes `control_capacity` and sends the browser's Origin + 64-hex CSRF envelope; below the bound the route answers 401 (the boundary's 403 without CSRF is its own step).
- the browser-fixtures literal is `scenarioPages: 15` (the reflow spec's two destinations); the key-material version scan excludes NULL `token_key_version`.
- every routed preview body sends the three-field wire source (`reference_of`); the raw U4 result's `jobId`/`contextId` are refused by `ResearchArtifactRef.additionalProperties`.
- the in-flight lifecycle test asserts `lane.running` before `stop()`; `preview_revision` counts join `preview_pair`; the no-read-back check counts the in-flight create itself (the hook fires before the fake logs the request).
- the real-research rig tests give lane rigs `keys="lane-keys"`, and the lane that writes runs over the mounted rig (`lane_over`) so the write reaches the shared fake.
- `ConnectionSampler` polls through a raw administrative session (`connect_raw`): the runtime roles hold `CONNECTION LIMIT 2`, so a sampler may not borrow one.

Measurements (fresh realm `docsuri-u6-39415d79bad07d97`; every number below is from that realm's phase evidence files):

- `coverage`: 920 tests, 0 failures, 0 skipped; **total 90.0%** (5829 statements, 603 missed) under `.coveragerc.u6`'s floor; the second report measures `scripts/u6_preservation.py` at **99.0%** (115 statements, 1 missed, line 102).
- The measured U2 files beside the total: `accounts/control_keys.py` 93%, `accounts/services/control_lifecycle.py` 33%, `accounts/services/guarded_entry.py` 56%, `personalization/guarded_service.py` 59%, `u3_host.py` 84% — the floor is on the total only, and no file left the include list.
- `frontend`: 118 tests, 0 failures; `src/u6-export` coverage **98.53%** lines (branch 94.28%), every module at or above 80%.

#### Step 42 — process evidence (2026-10-30)

**Component counts (L1-8).** Definitions are what `operations/test_u6_test_volume.py` floors at five; the runtime counts below are parametrize-expanded, from the phase evidence files' `testsByClass` joined with `COMPONENT_FILES`/`FRONTEND_FILES` (the coverage phase re-ran the whole tree on the frozen code). Counts above eight are recorded as **above range, kept**; none is below five.

- **ExportRoutes** — export_http=9, export_body_bounds=4, pending_connect=10, account_purpose=2, interactive_admission=3 → **28** (above range, kept).
- **ExportService** — service_connection=9, service_destinations=6, service_preview=14, service_approval=6, service_outcomes=17, binding_check=14, export_lifecycle=9 → **75** (above range, kept).
- **RenderPolicy** — rendering=18 → **18** (above range, kept).
- **ExportStore** — export_schema=13, export_functions=9, export_grants=8, pace_at_fake=1, approval_effect_store=9, connection_store=11, housekeeping_store=6, lane_store=8, owner_guard=5, pace_store=3, preview_store=3, replay_records=5, status_counts=5, unknown_check_cadence=3 → **89** (above range, kept).
- **TokenVault** — token_vault=13, token_exposure=42 → **55** (above range, kept).
- **TokenKeyring** — token_keyring=35 → **35** (above range, kept).
- **KeyCustody** — key_custody=29, control_keys_parity=13, key_never_elsewhere=5 → **47** (above range, kept).
- **NotionAdapter** — notion_adapter=27, classification=34, provider_text=4 → **65** (above range, kept).
- **NotionSession** — notion_session=16, log_content=3, plaintext_lifetime=5 → **24** (above range, kept).
- **GuardedTransport** — guarded_transport=29 → **29** (above range, kept).
- **InteractiveGate** — interactive_gate=10, interactive_admission=3 → **13** (above range, kept).
- **FakeNotion** — fake_notion=11 → **11** (above range, kept).
- **ExportWorker** — worker_pass=12, check_schedule=7, session_housekeeping=2 → **21** (above range, kept).
- **ExportLane** — lane_write_path=21, reconciliation=6, lane_transactions=5, lifecycle_in_flight=4 → **36** (above range, kept).
- **ExportLifecycleParticipant** — export_lifecycle=9, lifecycle_projection=3, lifecycle_in_flight=4 → **16** (above range, kept).
- **KeyCommands** — key_commands=11 → **11** (above range, kept).
- **ExportComposition** — export_composition=8, real_export_composition=25, free_terms_evidence=7, real_export_gates=6, export_policy=207, u3_export_gate=11, export_assembly=1, real_research_rig=5 → **270** (above range, kept).
- **AccountAccessA8** — lifecycle_projection=3, account_purpose=2, owner_guard=5 → **10** (above range, kept).
- **EnvironmentTool** — u6_runner=22, u6_serve=7, u6_preservation=23, u6_profile_binding=11, u6_browser_fixtures=8, u6_real_export_checks=13, coverage_contract=5, u6_test_volume=4 → **93** (above range, kept).
- **SharedContractAmendments** — `shared/python/tests/test_export_contract.py` = **44**, from the shared suite (`shared/python/.venv`) → (above range, kept).

Frontend modules (Vitest runtime, same join): api.ts=15; connect-form.tsx=13; destination-step.tsx=15; dialogs.tsx=8; export-flow.tsx=13 (export-flow.test 6 + approve-export.test 7); export-view.tsx=15; history.tsx=15; outcome-step.tsx=10; preview-step.tsx=9; status.tsx=5 — every module above the floor, the eight-plus ones recorded as above range, kept. Playwright's junit classname is confirmed from the real `browser.xml` of realm B: the spec filename (`journeys.spec.ts` 4, `keyboard.spec.ts` 3, `accessibility.spec.ts` 3, `reflow.spec.ts` 3 → 13, 0 failures); the static count needed no fallback.

**The 19 Unverified and 2 Not Met targets** are mapped by the plan's "Loop-back traceability" table; the rows, by target: `NFR1.1` → `test_owner_guard.py` (30); `NFR4.10/check-schedule` → `test_check_schedule.py`, `test_unknown_check_cadence.py` (30, 32); `watch-counts` → `test_status_counts.py` (30); `browser-value-not-identifier` → `service.py`, `notion_adapter.py`, `test_service_preview.py`, `test_export_http.py` (31, 32, 36); `NFR4.10/policy` → `test_export_policy.py` (32); `NFR3.8/origin-and-identifiers` → `test_guarded_transport.py`, `test_notion_session.py` (33); `NFR3.8/provider-text` → `test_provider_text.py`, the three hostile-text Vitest cases (33, 39); `NFR3.9` → `test_notion_session.py`, `test_export_composition.py` (33); `sdk-configuration` → `test_notion_session.py`, `test_notion_adapter.py` (33); `log-content` → `test_log_content.py`, `test_export_http.py` (33, 36); `plaintext-lifetime` → `test_plaintext_lifetime.py` (34); `free-terms-evidence` → `test_free_terms_evidence.py`, `test_u6_real_export_checks.py` (34, 38); `real-export-approval` → `test_real_export_gates.py` (34); `never-mocked` → `service_flows.py`, `http_flows.py`, `lane_flows.py`, `test_real_research_rig.py`, `test_export_assembly.py` (35, 36); `lane-connection-bound` → `test_lane_transactions.py` (36); `lifecycle-in-flight` → `test_lifecycle_in_flight.py` (36); `NFR1.3` → `test_export_body_bounds.py` (36); `key-never-elsewhere` → `test_key_never_elsewhere.py` (38); `coverage-backend` → `test_coverage_contract.py`, `.coveragerc.u6` pinned (38, 41); `NFR5.1/reflow` → `reflow.spec.ts`, `helpers.ts`, `accessibility.spec.ts`, `u6_browser_fixtures.py`, `test_u6_browser_fixtures.py` (37–39); `testing-contract-test-volume` → `testsByClass`, `test_u6_runner.py`, `test_u6_test_volume.py`, `status-accessibility.test.tsx` (37–40, 42). The real press itself stays operator evidence per L1-3 (runbook §6–§8; matrix row "Not runnable in this stage"; the gating chain is covered, never claimed as a passing test).

**Collect-only total:** 920 — exactly the count the coverage phase ran (0 failures, 0 skipped).

**The readings the gate must weigh:** the `pending` connection count (L1-4): **4** pending rows on realm A at the reading, beside connected 93, disconnected 2, revoked 2, unavailable 1 — `status_counts` omits `pending` by design. The check-schedule cadence (L1-5): fourteen checks at 3, 10 and 30 minutes, then hourly counted from the previous check up to `check_hourly_until_seconds = 21600`, then every three hours, the last at 84,600 s — pinned by `test_check_schedule.py` and `test_unknown_check_cadence.py`. The oldest-unknown age (L1-6): counts from the latest attempt's `deadline_at`; on realm A the oldest unknown's latest attempt deadline was 2026-10-29 17:36:59 UTC, about **2.2 h** at the reading.

**Layer order, as the plan's ticked steps show it:** 29 records → 30 repository/store tests → 31 service/adapter identity → 32–34 component tests → 35–36 integration flows and tests → 37 runner and fixtures → 38 operations tests → 39 frontend tests → 40 the volume map → 41 configuration and measurement → 42 this record → 43 the lanes, records, review and checkpoint.

#### Step 43 — run, record and review (2026-10-30)

All lanes on fresh realms. Realm A (`docsuri-u6-39415d79bad07d97`): `setup`, `migrate` (69 migrations), `coverage` (920 tests, 0 failures, 0 skipped; total **90.0%**; the second report **99.0%** for `scripts/u6_preservation.py`) and `frontend` (118 tests; `src/u6-export` **98.53%** lines) — the same numbers as Step 41, re-read from this realm's evidence; then `archive-owned` (preserved; container stopped; keys removed). Realm B (`docsuri-u6-aecbdb68d4c461b0`): `setup`, `migrate`, then `browser` — the Construction Verification Command — **13 tests, 0 failures** (journeys 4, keyboard 3, accessibility 3, reflow 3; every spec file its own junit classname). The reflow walk named no sideways scroller in any surface, so `export.css` needed no change (Step 39's condition did not fire).

Static checks on the frozen tree: `tsc --project tsconfig.u6-export.json --noEmit` clean; U6's ESLint command (including `e2e/u6-approved-export`) clean; Ruff over the cicd §2.3 target list plus every U6 script and `tests/u6_approved_export` clean.

Earlier units' regressions, exactly as `cicd-pipeline.md` §2.4 and the workflow define them: U1 `test_private_records.py` + `test_local_transport.py` **13 passed**; U2 `test_transport.py` + `test_control_runtime.py` **39 passed**; U2's keyring trio (`test_control_keys.py`, `test_control_key_recovery.py`, `test_recovery_restore.py`) **75 passed, 1 deselected** (`-k 'not test_actual_'`, no environment). U2's cumulative frontend lane (which registers `test/u6-export`) **51 files, 522 tests passed, All files 97.12% lines**. The shared contract suite: **44 passed**.

Records: this summary gained Steps 41–43; `traceability.json`'s loop-back block points at them and re-passes the traceability sensor (`pass: true`); `source-manifest.json` gained the loop-back's fifteen new test files, formatting untouched. A fresh architecture review of this attempt follows, then U6's checkpoint.

### Build and Test loop-back 2 (2026-11-15)

Build and Test's re-run of 2026-11-15 passed every U6 lane but found the never-mocked rule Not Met and ten U6 clauses that no test checks; the person chose "Retry with fix" and then approved the repaired plan ("Approve Plan"). The plan's "Build and Test loop-back 2" section holds decisions L2-1 to L2-4 and the readings; these are their records for the U6 checkpoint, written before any of Steps 45–52 changed a file (Step 44). Each is a deviation from the plan as first approved, recorded here rather than by editing Steps 1–43. The same list is carried in [traceability.json](traceability.json) under `loopback_2`.

- **L2-1 — the session guard's could-not-check case fails for real.** The two stand-ins (`FaultySessions` in `component/test_binding_check.py`, and the patched `housekeeping_store.session_current` in `component/test_worker_pass.py`) are replaced by a real failure of `accounts.guard_session`: the new `store_flows.held_session(connect, authority)` holds the session row `FOR UPDATE` from a second `accounts` connection, so the guard's own `FOR SHARE` waits until the realm's 1 s lock bound (`lock_timeout=1000`) ends its statement with 55P03 (`LockNotAvailable`), which is not the guard's 42501 answer. A `REVOKE` on the guard is never used, because its 42501 reads as a revocation and would invalidate the approval. The Clock rule names two real time bounds: the shared boundary's 5 s body read and the realm's 1 s lock bound. Alternatives not taken: (B) cancelling the waiting backend with `pg_cancel_backend` from a watcher thread; (C) keeping the stand-ins as allowed doubles.
  - The two `Faulty(OwnDue).sweep_orphans` stubs (`component/test_worker_pass.py` and `component/test_log_content.py`) stay and are listed under Allowed doubles: the log-content test needs a recognisable secret in the error text, which no real database fault carries.
  - Recorded, not changed: a 42501 from a lost EXECUTE grant also reads as a revoked session, so a deployment that lost the grant would invalidate every open approval. That fails safe (nothing unapproved is written); changing it is a production decision outside this loop-back.
- **L2-2 — the key-file read never blocks (the one production change).** `read_record` in `backend/key_custody.py` opened the key file with `O_RDONLY | O_NOFOLLOW`, so a FIFO at the key path blocked the open before the `S_ISREG` check could refuse it, and NFR3.2's "a non-regular file" could not pass. Step 46 adds `os.O_NONBLOCK` to that one open. This brings the shared helper in line with security design §4.2's "a regular file" and departs from §4.2's "moved with no change to U2's behaviour" in one case: U2's keyring, and U8's composed and production keyrings, which read through the same helper, now refuse a FIFO instead of hanging. U2's keyring regression is re-run after the change (last recorded: 75 passed, 1 deselected), and U8's checkpoint verification, the last of loop-back 2, runs over it. `source-manifest.json` already claims `backend/key_custody.py`. Alternative not taken: stay tests only and record the FIFO hang as an open defect.
- **L2-3 — the hosted logger levels are checked in U8's lane.** `U6:NFR3.9/u8-logger-levels` asks that U8 never lower the `httpx` and `httpcore` loggers once the hosted service is composed. U6's realm cannot compose the production assembly, and the edit that withholds the behaviour belongs in `backend/u8_host.py`, so (as L1-11 placed it) the check is written and run in U8's reopen, which follows U6's in loop-back 2: `tests/u8_service_operations_integration/integration/test_production_composition.py::test_the_composed_production_roles_keep_the_transport_loggers_at_warning`, parametrized over `backend.u8_main.ROLES`. It is **not built in U6's reopen**. U6's matrix row stays open at U6's checkpoint and closes at the Build and Test re-run. Alternative not taken: write the same test into U8's file during U6's reopen, with one U8 realm run.
- **L2-4 — the connection step is measured after a disconnect.** No fixture account can open the flow without ever having connected (memberB has no novelty result), so the new fourth test in `frontend/e2e/u6-approved-export/reflow.spec.ts` disconnects memberA through the view's dialog (`ensureDisconnected`) and then opens the flow. No fixture or `SPECS` change, so the fixture identity and every existing environment stay as they are. Alternative not taken: a novelty result for memberB, a fixture-identity change and a U4 job.

**Readings built as stated** (the person could change each at Plan Approval and did not):

- `export.status_counts` keeps its window edges: an effect that ended exactly 24 h before the caller's clock is outside the window (a strict `>`, `u6_maintenance.sql`), and a terminal effect whose end lies after the caller's clock still counts (no upper bound). Changing either needs a new migration.
- The due order is pinned on a fresh pass: the older of two accepted exports first, the younger once the older is no longer due. The pass's round robin (`worker.py`) may hand over a younger export while an older one, already handed at its current revision, stays due; strict oldest-first on every pass would be a production change.
- "Consumed" means an environment holding any `*-evidence-*.json` file, which the browser phase refuses, or a realm whose 20-account synthetic allocation is spent, which the conftest refuses. The coverage phase does not refuse an environment holding evidence; refusing it would be a production change.
- Phase validity covers the verification phases `run_phase` runs. `serve` records its starting source but never compares it and writes no JUnit report, so it is outside the clause.
- NFR3.1's AAD fields are read as hyphenated lowercase UUID text and a decimal revision (`token_vault.py`): the code's reading of §4.1, which names the fields without a format.
- Recorded, not changed: after a cancellation from outside, the `CancelledError`'s traceback keeps the closed HTTP client and the SDK client, whose options hold the token, reachable until the caller drops the exception. No production path cancels an operation from outside today; closing the gap would mean clearing both in `NotionSession._operate`'s `finally`.

**The eleven targets and the steps that close them** (plan table "Loop-back 2 traceability"): never-mocked → `store_flows.py`, `test_binding_check.py`, `test_worker_pass.py` (48, 51); NFR3.1 → `test_token_vault.py` (47); NFR3.2 → `key_custody.py`, `test_key_custody.py`, `test_token_keyring.py` (46, 47); NFR3.3/operator-commands → `test_key_commands.py` (47); NFR3.5 → `test_plaintext_lifetime.py` (48); NFR3.9/u8-logger-levels → U8's reopen (L2-3; open at U6's checkpoint); NFR5.1/reflow → `reflow.spec.ts`, `helpers.ts` (50); watch-counts → `test_status_counts.py` (45); due-order → `test_lane_store.py`, `test_worker_pass.py` (45, 48); environment-lifetime → `test_u6_runner.py`, `test_u6_profile_binding.py` (49); phase-validity → `test_u6_runner.py` (49). Counts, withheld runs and lane results are added by Step 52.

#### Step 51 — withheld-behaviour checks (2026-11-15, 10:15–10:31 UTC)

Each new or changed test ran once with the behaviour it awaits withheld, outside any recorded run, in the direct form scoped to its file (`-k`). The database-backed checks used development realm `docsuri-u6-df5b163f5c47314c` (archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-df5b163f5c47314c-d2a4bb23`); the reflow check used its own fresh realm `docsuri-u6-0f0baa94d0bb595f` (archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-0f0baa94d0bb595f-17db2e2e`). Baselines first: the seven database-backed files passed on the unmodified code (76 passed), and the FIFO test passed on the fixed code. Each file's SHA-256 was taken before its first edit; one edit was made at a time; every file was restored and confirmed equal to its baseline before anything else ran.

| Target | Temporary edit | The test's failure |
|---|---|---|
| NFR3.1 | `token_vault.py`: AAD without the version | `InvalidTag` at `test_token_vault.py:89` |
| NFR3.1 | seal and open with `key[:16]` | `InvalidTag` at `:89`; the file's other 13 tests passed |
| NFR3.1 | `NONCE_BYTES = 16` | `(32, 12, 126) == (32, 12, 122)` |
| NFR3.2 | `key_custody.py` open without `O_NONBLOCK` (the code before Step 46) | `('stalled', None)` after the 5 s bound; no hang |
| NFR3.2 | no `S_ISREG` test | cause `JSONDecodeError`, not `ValueError` |
| NFR3.2 | `except` narrowed to `(ValueError, TypeError, KeyError)` | an unmapped `IsADirectoryError` in the custody test and in the keyring's `directory` case |
| never-mocked | `binding.py` `_session` answers a revocation | `('changed', …, 'UNAUTHENTICATED')` instead of could-not-check |
| never-mocked | `housekeeping_store.py` treats the fault as not current | `(1, 0) == (0, 1)` |
| never-mocked | `store_support.py` catches every `psycopg.Error` | binding: `DID NOT RAISE LockNotAvailable`; worker: `(1, 0)` |
| never-mocked | arrangement: each test without its `held_session` line | the same two failures |
| NFR3.3 | `token_keyring.py` `ensure_marker` returns at once | `FileNotFoundError` on `export-token-keyring.initialized`; the design predicted the listing assertion, and the marker read comes first |
| NFR3.3 | `ensure_marker` always unlinks and re-creates | the sentinel became the run id: `b'u6-key-commands-test' != b'marker-before-loss:…'` |
| NFR3.5 | `notion_session.py:557` `finally:` → `else:` | all four failure cases and the cancellation case: `[] == [<httpx.AsyncClient …>]`; the five older tests passed |
| watch counts | `lane_store.py:600` masks `executing`, then `unknown`, then `failedLast24h`, then `invalidatedLast24h` | each masked key missing from its delta (`{} == {'executing': 1}`, `{} == {'unknown': 1}`, and at INSIDE the other key alone) |
| watch counts | `now` less one microsecond (an inclusive edge) | at EDGE: `{'failedLast24h': 1, 'invalidatedLast24h': 1} == {}` |
| due order | `ORDER BY priority,due_at DESC,id` | repository: the younger effect listed first; component: the younger export offered first |
| environment lifetime | runner without the browser evidence refusal | all four cases: `no child starts` |
| environment lifetime | `conftest.py` without the allocation refusal | `DID NOT RAISE Failed` (that run committed one synthetic owner on the development realm, since archived) |
| phase validity | runner without the after-phase source comparison | changed: `DID NOT RAISE Refused`; unchanged: `[0] == [0, 1]` |
| phase validity | a listed file's digest recorded as None; `TEST_ROOT` dropped from the inventory | equal digests; `test_added.py` missing from the inventory |
| phase validity | each JUnit verdict term dropped in turn; the report read without its custody check | exactly the matching case failed each time (`skip-alone`, `error-alone`, `failure-alone`, `wrongly-moded`), the other three passing |
| reflow | `export.css` gains `.export-step .export-connect { min-width: 400px; }` before the browser phase | 13 journeys passed; the new test failed at "the connection step reflows at 320 px" with `{width: 320, page: true, surface: true, offscreen: false, nested: []}`, the predicted object |

Restored digests: `token_vault.py` `138953f8…`, `key_custody.py` `ad8fac34…`, `verify_docsuri_u6.py` `9f581d83…`, `binding.py` `43528314…`, `housekeeping_store.py` `4a7aa5da…`, `store_support.py` `939c74bf…`, `token_keyring.py` `36c03315…`, `notion_session.py` `9217dc28…`, `lane_store.py` `98838d16…`, `conftest.py` `055a9d09…`, `test_binding_check.py` `04d0f0c3…`, `test_worker_pass.py` `1a0725ec…`, `export.css` `4a4f37cf…`. The full record, with every failure text and the full digests, is the evidence file `~/.docsuri-u8/final-evidence/u6-l2-failchecks.json`, outside the repository.

The reflow run also reported `sourceChangedDuringRun`. The cause was not the CSS rule: the ECC plugin's turn-end hook (`stop:format-typecheck`) ran while the phase was running and rewrote `frontend/e2e/u6-approved-export/reflow.spec.ts` with the repository's Prettier at 10:29:26 UTC. It rewrapped loop-back 1's `expect(...)` calls and left the new test as written; nothing changed in behaviour. A per-file comparison against the phase's starting inventory differs only in that file and the restored `export.css`. The reformat is kept, because the same hook would apply it again, and it is disclosed here. The hook acts only on JS/TS files edited in a response; the recorded runs below started with nothing queued and ran in the foreground.

#### Step 52 — run and record (2026-11-15, 10:38–10:47 UTC)

- **Realm A** `docsuri-u6-c585aab3e91b8fd5`, fresh (archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-c585aab3e91b8fd5-7636029e`), containers confirmed through Colima's socket:
  - `coverage`: 945 passed, 0 failed, 0 errors, 0 skipped; total **89.72%** (floor 80; the evidence rounds it to 90.0); `scripts/u6_preservation.py` **99%** in the second report; 157.6 s of the 300 s bound; source digest `23b544af…`, the identity of the tree after Step 51's last restore.
  - Measured beside the total: `backend/key_custody.py` 100%; U2's `control_keys.py` 93%, `control_lifecycle.py` 33% (its other paths need U2-only tables, as the coverage targets record), `guarded_entry.py` 56%, `guarded_service.py` 59%; `backend/u3_host.py` 86%.
  - `frontend`: 120 passed; `src/u6-export` **98.53%** lines; 7.9 s.
- **Realm B** `docsuri-u6-db604e7245242307`, fresh (archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-db604e7245242307-69881b14`): `browser` **14 passed**, 99.6 s, no source change. U6's checkpoint itself verifies with the intent's recorded Construction Verification Command (U8's `verification-run`), which supersedes item 14's browser command below.
- **Static checks:** `tsc --project tsconfig.u6-export.json --noEmit --incremental false` exit 0; U6's ESLint command (including `e2e/u6-approved-export`) exit 0; Ruff on the CI list (`--no-cache`): all checks passed.
- **Earlier Units' regressions, as U6's workflow runs them:** U1 `test_private_records.py` + `test_local_transport.py` 13 passed; U2 `test_transport.py` + `test_control_runtime.py` 39 passed; U2's keyring trio 75 passed, 1 deselected (`-k 'not test_actual_'`), the same count as before Step 46; the shared contract checks (`export_workspace_contract.py --check`, `generate.py --check`) clean and the shared suite 258 passed; U2's cumulative frontend lane 59 files, 711 tests passed, All files 97.4% lines.
- **The runs Steps 24 and 27 also ask for**, made again so their boxes could be re-ticked:
  - U4's lane with coverage: 10 files, 107 tests passed; `src/App.tsx` 72.94% (floor 48), `src/u4-research` 99.29% (floor 80);
  - U3's lane (`vitest.u3-corpus.config.ts`, the lane U3's workflow runs) with coverage: 8 files, 70 tests passed; `src/App.tsx` 68.52% (floor 48), `src/u3-corpus` 88.09%;
  - the type lanes: `tsconfig.u4-research.json` and `tsconfig.u5-topics.json` exit 0 (`--incremental false`, as U6's above);
  - the drift checks: `inventory_consumers.py` ("ok: actual Python shared-contract consumers"), `check:types` ("generated wire matches every public DTO schema"), `check:consumers` ("ok: actual TypeScript imports…"), `test:contracts` 33 passed. Both consumer inventories already match the code, so Step 27's refresh would write no change; it was not run;
  - the frontend-wide checks: whole-program `typecheck` (`tsc --noEmit --incremental false`) exit 0, `tsc -p tsconfig.e2e.json --noEmit --incremental false` exit 0, the full `vitest run` 145 files, 1,205 tests passed.
  - Step 27's last clause (U2's, U4's and U5's phases on environments re-created after the lock change) does not apply: no lock changed in this attempt.
  - The per-layer phase runs of Steps 6–26 are covered by the `coverage` phase above, which runs every layer in one pass, as U6's workflow does (repeating them would spend the realm's bounded fixture quotas).
  - Step 43's text also names a review and the checkpoint; those were loop-back 1's, which had both. This attempt's review and checkpoint follow Step 52, whose text leaves them out.
- **Collect-only:** 945 tests (loop-back 1's 920 plus this loop-back's 25 runtime cases).
- **Test volume** (definitions from the component → test-file map in `operations/test_u6_test_volume.py`; runtime cases from the coverage run's `testsByClass`):

  | Component | Definitions | Changed files: definitions / runtime cases |
  |---|---|---|
  | NotionSession | 25 | `component/test_plaintext_lifetime.py` 7 / 10 |
  | ExportStore | 91 | `repository/test_status_counts.py` 7 / 7; `repository/test_lane_store.py` 9 / 9 |
  | ExportWorker | 15 | `component/test_worker_pass.py` 10 / 13 |
  | ExportService | 59 | `component/test_binding_check.py` 8 / 14 (count unchanged; the stand-in removed) |
  | TokenVault | 13 | `operations/test_token_vault.py` 9 / 14 |
  | KeyCustody | 28 | `operations/test_key_custody.py` 12 / 30 |
  | TokenKeyring | 21 | `operations/test_token_keyring.py` 21 / 36 |
  | KeyCommands | 8 | `operations/test_key_commands.py` 8 / 11 (two tests extended) |
  | EnvironmentTool | 72 | `operations/test_u6_runner.py` 25 / 33; `operations/test_u6_profile_binding.py` 6 / 12 |

  KeyCommands sits at the top of the standard strategy's five to eight; every other count is above the range, recorded and kept (L1-8).
- **L2-2 reaches one more reader:** U8's verifier key reads through the same `read_record` (`backend/modules/accounts/u8_verifier_key.py:503`), so it too now refuses a FIFO instead of hanging. U8's reopen and its checkpoint verification run over it.
- **Formatting:** `ruff format --check` still flags lines in five of the changed test files (`test_plaintext_lifetime.py`, `test_key_commands.py`, `test_key_custody.py`, `test_u6_runner.py`, `test_status_counts.py`); every flagged line predates this loop-back, and the lines it wrote are formatted. CI runs `ruff check`, which passes.
- **Environments:** the four realms this loop-back used are archived; none is left running. The "Running" line under Open items describes an earlier environment, archived since.
- **Plan boxes:** Steps 44 and 46 were ticked at the build (Step 46 after U2's keyring regression: 75 passed, 1 deselected); Steps 1–43, 45 and 47–52 were ticked after the runs above, which exercise them again. The stage's own review and U6's checkpoint follow; they are not plan steps.

### Build and Test loop-back 3 (2026-11-17)

Build and Test's fourth run (2026-11-17, `construction/build-and-test/test-results.md`, Loop-Back Log entry "Loop-back 3 — 2026-11-17T16:07:16Z") found U6's never-mocked rule and its static checks Not Met, and two clauses with no test: when the lane recorded the outcome the watch counts report, and NFR3.8's provider text on the history rows and the settle dialog. The person chose "Retry with fix" on 2026-11-17 and approved the repaired plan on 2026-11-18 with "Approve Plan", taking the proposed defaults: **L3-5 (a)**, `FakeResearch` listed under Allowed doubles; **L3-8 not built** (no optional Chromium checks); **L3-10 (A)**, the four U2 accounts files counted. The plan's "Build and Test loop-back 3" section holds the decisions and readings; these are their records, written before any of Steps 54–62 changed a file (Step 53). Each is a deviation from the plan as first approved, recorded here rather than by editing Steps 1–52. The same list is carried in [traceability.json](traceability.json) under `loopback_3`. No step changes production behaviour.

- **L3-1 — the lane's store faults are real.** `Broken` and `Interleaved(pace=False)` in `component/test_lane_write_path.py` are replaced by real database faults: a new `store_flows.held_rows(connect_raw, *locks)` holds named rows `FOR UPDATE` from the realm's administrative login, and the realm's 1 s lock bound ends the code's own locking or updating statement with 55P03 (`psycopg.errors.LockNotAvailable`), which `OwnerTransactions.run` does not retry. The pace row is held only around the lane's own reservation (through `Interleaved`'s new `pace_hold`), so the binding check's adapter reservation stays unheld and the lane reaches its could-not-check path at `lane.py:265`. The effect row and the `export.lane_status` singleton are held from the claim on, so the claim's `SELECT … FOR UPDATE` and the status upsert each end at the bound, reaching both of `run_item`'s fault branches through the real store. Holders connect through `connect_raw`, never a runtime role (which carries `CONNECTION LIMIT 2`). Each hold stays inside the realm's 5 s idle-in-transaction bound. Alternatives not taken: (B) `LOCK TABLE export.effect IN ACCESS EXCLUSIVE MODE`; (C) keep both stand-ins as allowed doubles.
- **L3-2 — the operator's outcome reads realm rows.** `Rows` in `operations/test_u6_real_export_checks.py` is replaced by two real exports of one owner: the first press is settled with `rig.succeed` (one export in flight per owner, BR5.1), the second is claimed with `path_kind="real"` and recorded as refused `no-access` through the store's own units, so the real `OUTCOME_QUERY`, its id filter and its `LIMIT 2` are tested. Alternative not taken: list `Rows` beside the runner stand-ins.
- **L3-3 — the archive's database check reads the realm.** `Database` in `operations/test_u6_preservation.py` is replaced by a `connect_raw` session with tuple rows, the way the runner's own `connect_admin` returns them. The manifest carries the realm's own run id; the fixture's `connect_admin` waits up to 5 s for no other client backend, rolling back after each read; the active-client case opens one more real session. The Docker, port, open-file and stop stand-ins stay recording only. Alternative not taken: list `Database`.
- **L3-4 — the remaining wrappers and stand-ins are named under Allowed doubles**, by two narrow rules: delegating wrappers (`Interleaved` with its claim steps and pace hold; the `reserve_pace_slot` spy in `integration/test_pending_connect.py`; `racing_page` in `operations/test_key_commands.py`; `spy_method` in `integration/test_export_assembly.py`; the archive fixture's `connect_admin`), and recording stand-ins for what lies outside the database (the archive context's `resources`, `idle_port`, `open_files` and `stop_database`). None replaces anything on the never-mocked list. Alternative not taken: leave them unlisted.
- **L3-5 — `FakeResearch`, the person's answer (a): listed.** `FakeResearch` in `operations/test_u6_browser_fixtures.py` stands in for U4's service and execution in `test_a_missing_result_is_produced_through_the_research_service` only. With no known result, `_ready` returns before any export read (`scripts/u6_browser_fixtures.py:263-264`), so `FakeResearch.readNoveltyArtifactForExport` is never called; what it replaces is U4's policy reference, entitlement check, context creation, accept, job read and execution step, none of which the never-mocked list names. U4's real service, execution and export read run in `test_fixture_setup_is_idempotent_and_its_result_is_exportable`, the integration rigs' `Rig.ready` and the fixtures phase. Alternative not taken: (b) reach the branch through U4's real service on a conftest owner.
- **L3-6 — the watch counts' time is checked through the lane's real record against the database clock.** The status record takes no time: the first insert takes the column default `clock_timestamp()` and every later record sets `observed_at=clock_timestamp()`; `export.status_counts` returns that row's time as `lane.observedAt`. A new repository test records two outcomes and brackets the second between two reads of the database clock, then reads the lane block under two caller clocks that differ from the record time. Alternatives not taken: (B) write the row directly with a fixed `observed_at`; (C) give `record_lane_status` the lane's injected clock (a production change).
- **L3-7 — NFR3.8's remaining jsdom surfaces get one hostile-text case each:** the history row's destination title, the settle dialog's destination title, and the connect announcement of the Notion workspace name in `export-live`. No Vitest file is added. NFR3.8 stays Unverified, browser-only, because no Chromium run shows hostile provider text.
- **L3-8 — the optional Chromium checks, the person's answer: not built.** D7, NFR3.4/connect-field, NFR5.1/component-checks and NFR3.8/provider-text are said at the gate as browser-only.
- **L3-9 — U6's own lint configurations, passed with `--config`:** `scripts/u6-lint.toml` for the tests (`select = ["E", "F", "I", "UP", "B"]`, line length 100, `py313`, `src = [".", "ingestion/src", "ops/src"]`) and `scripts/u6-lint-scripts.toml` for the five scripts (`extend-select` with the same rules, `src = [".", "scripts", "ops/src"]`). Nothing is ignored. U6's backend files, the shared runtime files and `ops/src/docsuri_ops/local_transport.py` stay under `backend/pyproject.toml` and `ops/pyproject.toml`. Alternatives not taken: (B) reuse U8's files; (C) a `tests/u6_approved_export/ruff.toml`.
- **L3-10 — the four U2 accounts files, the person's answer (A): counted.** `control_keys.py`, `services/control_lifecycle.py`, `local_http.py` and `services/guarded_entry.py` are linted from `backend/modules/accounts` under a new `scripts/u6-lint-accounts.toml` (the folder's file extended, E,F,I,UP,B, `ignore = []`); the 30 E501 lines (29 SQL literals in `control_lifecycle.py`, one call in `local_http.py`, all from U2's commit `a62bb26e`) are wrapped, and `shared/python-consumers.json`, which pins both files' SHA-256, is regenerated (Step 59(f)), keeping U8's uncommitted part apart from U6's. Alternative not taken: (B) leave them under the folder's configuration.
- **L3-11 — the static-check fixes change no behaviour.** E402: `ROOT` moves after the import block and each `sys.path.insert` writes its path inline. I001: the two approved `ruff check --select I --fix` commands (safe fixes only). Every other finding by hand: literals split, calls and conditions wrapped, two docstrings re-wrapped, B007's unused loop name dropped, UP031's `%` formatting made an f-string. Step 60 compares each changed file's syntax tree with a snapshot taken just before Step 59.
- **L3-12 — a lint gate in U6's own lanes:** `operations/test_u6_lint_gate.py`, three tests on real Ruff and real files, mapped under EnvironmentTool (72 → 75 definitions, above range, kept).

**Readings built as stated** (the person could change each at Plan Approval and did not):

- `store_flows.held_session` stays byte-identical, so L2-1's two tests and their withheld runs stand; `held_rows` sits beside it.
- One `path_kind='real'` attempt is written into the synthetic realm through the store's own claim (L3-2), as `component/test_real_export_gates.py` already does.
- L2-1's listed `Faulty(OwnDue).sweep_orphans` is not reopened.
- "When it happened" (logical-components §8) is the database clock at the lane's last status write, not the lane's injected clock, the caller's clock or the read time. In production these agree (the lane's clock is real time, `backend/u6_host.py:131`); under the browser realm's fixture clock the lane status keeps database time. Recorded, not changed.
- The instructions' Clock line "Only the pace reservation uses the database clock" is amended: two checked behaviours take the database clock, the pace reservation and the lane status record; every other checked behaviour takes the injected `now`.
- The watch-counts check is a new test, not an extension of an existing one: ExportStore goes from 91 to 92 definitions.
- NFR3.8's payloads are shaped as markup and links only; bidi isolation would be a production change. `sourceTitle` stays plain (DocSuri's own result title). The settle dialog is rendered directly.
- One case through the view covers both live regions the `ConnectForm` announcement reaches (`export-live` and the flow's `flow-live`); no fourth case in `export-flow.test.tsx`.
- L1-8 applies to every count this loop-back raises: dialogs 9, history 18, export-view 16, ExportStore 92, EnvironmentTool 75.
- The Vitest and lint-gate withheld runs touch no environment, because `vitest run` and the gate need none.
- The existing `# noqa: E731` (`repository/test_connection_store.py`) and `# noqa: E402` (`operations/test_u6_profile_binding.py`) stay.
- The scripts' `src` moves three imports (`backend.local_profile` ahead of `bootstrap_docsuri_u1` in the runner; `docsuri_ops` into the first-party block); Ruff never moves an import across a statement.
- The two docstring re-wraps change whitespace only (`database/test_export_schema.py`; `scripts/u6_browser_fixtures.py`'s argparse description, which argparse re-wraps).
- U6's CI lint step drops its duplicate `scripts/u6_real_export.py` and gains `--no-cache`.
- The static-check sweep (Steps 58–60) follows the test steps, and the withheld runs (Step 62) follow the sweep.

**The five targets and the steps that close them** (plan table "Loop-back 3 traceability"): never-mocked → `store_flows.py` (`held_rows`), `component/test_lane_write_path.py`, `operations/test_u6_real_export_checks.py`, `operations/test_u6_preservation.py`, Allowed doubles (55, 57, 62, 63); watch-counts → `repository/test_status_counts.py` (54, 62); NFR3.8/provider-text → `history.test.tsx`, `dialogs.test.tsx`, `export-view.test.tsx`, the jsdom side only (56, 62); static-checks → the three `scripts/u6-lint*.toml`, `shared/python-consumers.json`, the workflow, the fixed tests and scripts, `operations/test_u6_lint_gate.py` (58–61, 62, 63); testing-contract-test-volume → `operations/test_u6_test_volume.py` (61). Build results, counts and withheld runs follow below.

#### Steps 54–62 — build and withheld checks (2026-11-18)

All database-backed runs below used development realm `docsuri-u6-fe4ff79e96a27ee3` (set up and migrated on 2026-11-18 on Colima, its container confirmed through Colima's socket), in the direct form with `DOCKER_HOST` and `DOCKER_CONFIG` pointing at Colima, under `umask 077`. They are exploration runs and write no evidence; the recorded lanes are Step 63's.

- **Step 54** (L3-6): `repository/test_status_counts.py` gains `database_now` and `test_the_lane_block_reports_when_the_lane_recorded_its_last_outcome` (the file goes from 7 to 8 definitions; ExportStore 91 → 92). Run with `-k`: 1 passed, exit 0.
- **Step 55** (L3-1): `store_flows.held_rows` with `PACE_ROW`, `EFFECT_ROW` and `LANE_STATUS_ROW` (`held_session` byte-identical); `Interleaved` takes `pace_hold`; the pace test and the store-fault test take `connect_raw`; `Broken` and `pace=False` are gone. The file keeps its 20 definitions. Both tests run with `-k`: 2 passed, exit 0.
- **Step 56** (L3-7): one hostile case each in `history.test.tsx` (18 cases), `dialogs.test.tsx` (9) and `export-view.test.tsx` (16), each run file by file with U6's Vitest config: 18, 9 and 16 passed. `tsc --project tsconfig.u6-export.json --noEmit --incremental false` exit 0; U6's ESLint command exit 0. `prettier --check` flags only `export-view.test.tsx` lines 128–130, loop-back 1's existing case, not the new lines; the turn-end formatter will rewrap them, so test-file digests are taken after formatting.
- **Step 57** (L3-2, L3-3): `Rows` and `Database` are gone. `test_u6_real_export_checks.py` (7 definitions, 13 cases) and `test_u6_preservation.py` (10 definitions, 23 cases) run in full: 36 passed, exit 0.
- **Step 58** (L3-9, L3-10): `scripts/u6-lint.toml`, `scripts/u6-lint-scripts.toml`, `scripts/u6-lint-accounts.toml`; the workflow step replaced as the plan gives it and `scripts/u6-lint*.toml` added to the path filter (the YAML parses). Snapshot `~/.docsuri-u8/lead-scripts/l3-records/u6-d-before/`, 83 files with `SHA256SUMS`. Baseline under the new files: tests **113** (70 I001, 41 E501, 1 UP031, 1 B007), scripts **38** (19 E501, 16 E402, 3 I001), U2 files **30** (E501), invocation 3 clean: exactly the plan's counts. The record logs hold statistics only, not line lists; the four flagged lines in files Steps 54–57 touched (`test_u6_preservation.py`'s `ownership.json` line, `test_u6_real_export_checks.py`'s bad-date and refused-outcome lines, `test_status_counts.py`'s `flows.configure` line) all predate this loop-back, so Steps 54–57 added no finding.
- **Step 59** (L3-11): E402 by hand in the four scripts; the two approved `--select I --fix` commands (3 and 70 fixed); every E501 by hand, plus B007 (`for call in units.values():`) and UP031 (the f-string); under (A) the 30 U2 lines wrapped (29 in `control_lifecycle.py`, counting both copies of the scope insert, and `local_http.py:129`). Afterwards: invocations 1–4 each exit 0 ("All checks passed!"); the root-suites lint (`backend/.venv/bin/ruff check --no-cache backend/modules/accounts backend/modules/library backend/modules/ops tests`) exit 0; `backend/modules/accounts`' own lint (`ruff check --no-cache .` from that folder) exit 0; U8's accounts invocation under `scripts/u8-lint-accounts.toml` exit 0.
  - Step 59(f): before the U2 wraps the inventory printed "ok: actual Python shared-contract consumers"; after them it printed "actual Python consumer inventory drift" (exit 1); `--write` then printed "ok", and the check without `--write` printed "ok: actual Python shared-contract consumers". Against the snapshot copy, exactly two `sourceDigests` entries changed: `backend/modules/accounts/local_http.py` `fb42e22f…` → `afb1b059…` and `services/control_lifecycle.py` `42e2ca90…` → `80170166…`, each the file's new SHA-256. Nothing of U8's differs.
  - **Deviation:** the workflow step's invocations were run with the binary's literal path, not through `ruff="$PWD/backend/.venv/bin/ruff"` and `"$ruff"` exactly as written: in this delegated session a guard hook refuses a variable used as the executable (and `bash -c`). The arguments, folders and globs are identical. Step 59's box stays open until Step 63 runs the step exactly as written.
- **Step 60**: the comparator `~/.docsuri-u8/lead-scripts/l3-records/u6-d-ast-compare.py` exits 0. 83 manifest files, 80 changed; 79 compare equal after the plan's normalisations (import runs as multisets, docstrings whitespace-collapsed, the four scripts' `ROOT` restructuring with exactly one later `ROOT` directly after the imports); `shared/python-consumers.json` compared in Step 59(f). Exactly two expected differences: B007 (`for name, call in units.items():` → `for call in units.values():`) and UP031, value-equal for 10 secrets holding `%`, braces and quotes. No changed file outside the manifest (records under `aidlc/` excluded). Each file's before and after SHA-256 come from the snapshot's `SHA256SUMS` and the comparator's own output, which re-runs the same way; the full per-file list was read from that output and is not repeated here. Step 61's gate file and mapping line came after Step 60 by the plan's order, so they are outside this comparison.
- **Step 61** (L3-12): `operations/test_u6_lint_gate.py` (3 tests: the configurations through `tomllib` and `--show-settings`, with every path of invocation 3 resolving to `backend/pyproject.toml` or `ops/pyproject.toml` and the three planted files giving exactly {E501, I001}, {I001} and {S110, BLE001}; the four invocations exiting 0 with linted-file digests and `.ruff_cache` listings unchanged; the workflow step's binary line, invocations and path filter). `operations/test_u6_test_volume.py` maps it under EnvironmentTool (72 → 75). Exploration run of the two files: 7 passed, exit 0; invocation 1 over the new file exit 0. The box is ticked on Step 63's coverage phase, as its text says.
- **Collect-only:** 949 tests.
- **Step 62** — each new or changed test run once with its behaviour withheld, outside any recorded run. Baseline first on the swept tree: the seven targets' files, 41 passed. Each check copied the file to `~/.docsuri-u8/lead-scripts/l3-records/withheld/`, made one exact edit (refused unless its target occurred once), ran the test keeping `rc`, copied the file back and compared the SHA-256, in one shell command. Every check exited 1 with the failure below, and every restore matched.

  | Check | Temporary edit | The test's failure |
  |---|---|---|
  | W1 | `lane_store.py` status read returns the caller's clock as `observedAt` | `observedAt` equality: 1990-01-01 ≠ the recorded time (`test_status_counts.py:270`) |
  | W2 | the same read returns `clock_timestamp()` (the read time) | `observedAt` equality: the read time ≠ the recorded time (`:270`) |
  | W3 | the upsert drops `,observed_at=clock_timestamp()` | `first < recorded` (`:265`) |
  | W4 | the upsert stamps `clock_timestamp()+interval '1 second'` | the bracket's upper end (`:266`) |
  | P1 | `lane_store.py` pace reservation catches only `Busy` | `'error' == 'waiting'` (`test_lane_write_path.py:386`) |
  | P2 | `lane.py` `if slot is not None and not slot.within_budget:` | `'error' == 'waiting'` (`:386`) |
  | P3 | the pace test without its `pace_hold` | `'succeeded' == 'waiting'` (`:386`) |
  | S1 | `lane.py` `run_item` keeps the error's text | the message list (`:436`) |
  | S2 | the early-end warning adds `exc_info=True` | `(None, None, None) is None` (`:442`): logged after the `except` block, the record still carries an `exc_info` tuple |
  | S3 | `_record_status` keeps the error object | the message list (`:436`) |
  | S4 | `run_item` catches only `(ValueError, TypeError)` | `LockNotAvailable` escapes `run_item` |
  | S5 | the store-fault test without its hold | `'succeeded' == 'error'` (`:432`) |
  | S6 | only the effect row held | the message list (`:436`): the status record goes through |
  | O1 | `u6_real_export.py` `if not rows:` | `DID NOT RAISE OutcomeRefused` (`test_u6_real_export_checks.py:214`) |
  | O2 | the query ends `LIMIT 1` | `DID NOT RAISE OutcomeRefused` (`:214`) |
  | O3 | the query compares `e.id<>%s::uuid` | `(…digests…) == (None, None)` (`:217`): with only A and B in the realm, A's id named B |
  | O4 | a missing value hashed as the empty string | `('e3b0c442…', …) == (None, None)` (`:217`) |
  | A1 | `u6_preservation.py` identity compares only the database | `DID NOT RAISE` in the `database-identity` case (`test_u6_preservation.py:224`) |
  | A2 | `if active > 1:` | `DID NOT RAISE` in the `active-client` case (`:224`) |
  | A3 | the count loses `backend_type='client backend'` | the completed archive refuses: "other database clients prevent safe preservation" |
  | A4 | the count loses `pid<>pg_backend_pid()` | the same refusal |
  | A5 | the `active-client` case without its extra session | `DID NOT RAISE` (`:224`) |
  | A6 | the `destination` case's folder named from the old constant | `DID NOT RAISE` (`:224`) |
  | A7 | an extra raw session closed by a `threading.Timer` 0.5 s into the poll: with the rollback kept (control) | passed, exit 0, 0.58 s |
  | A7 | the same with the fixture's rollback removed | "another database client stayed connected to the realm" after 5.14 s (`:71`) |
  | V1 | `history.tsx` title through `dangerouslySetInnerHTML` | `expected <img src="x" onerror="x"></img> to be null` |
  | V2 | `dialogs.tsx` first `<strong>` through `dangerouslySetInnerHTML` | `expected SVGSVGElement{ …(1) } to be null` |
  | V3 | `status.tsx` announcement `<span>` through `dangerouslySetInnerHTML` | `export-live` text lost the markup: `'Notion 워크스페이스 ‘팀{{x}}’에 연결했습니다'` |
  | G1 | `extend-ignore = ["E501"]` in `scripts/u6-lint.toml` | `('scripts/u6-lint.toml', 'extend-ignore')` (`test_u6_lint_gate.py:215`) |
  | G2 | `line-length = 120` there | `scripts/u6-lint.toml` (`:209`) |
  | G3 | `src` removed there | the `docsuri_ops` planted file passed: `assert (0 == 1)` (`:263`) |
  | G4 | `select` for `extend-select` in `scripts/u6-lint-scripts.toml` | `KeyError: 'extend-select'` (`:218`) |
  | G5 | `ignore = []` removed from `scripts/u6-lint-accounts.toml` | `KeyError: 'ignore'` (`:213`) |
  | G6 | the consent insert in `conftest.py` back on one line | invocation 1: `E501 Line too long (163 > 100)` (`:283`) |
  | G7 | the `ROOT`-first header back in `serve_docsuri_u6.py` | invocation 2: `E402` (`:283`) |
  | G8 | the consent select in `control_lifecycle.py` back on one line | invocation 4: `E501` (`:283`) |
  | G9 | `--no-cache` dropped from the gate's Ruff helper | the `.ruff_cache` comparison (`:292`); the 8 cache files that run created (7 under `.ruff_cache/0.16.8/`, 1 under `backend/modules/accounts/.ruff_cache/0.16.8/`) were deleted by name afterwards |
  | G10 | the old folded step back in the workflow | `assert 0 == 1`, no `ruff=` line (`:198`) |
  | G11 | the `scripts/u6-lint*.toml` path line removed | `'scripts/u6-lint*.toml' in [...]` (`:301`) |
  | G12 | the gate's mapping line removed from `test_u6_test_volume.py` | the unmapped file (`test_u6_test_volume.py:182`) |
  | L1 | `test_owner_guard.py` test without `flows.end_session` | `DID NOT RAISE InsufficientPrivilege` (`:97`); that run may have committed rows for the owner on the development realm |
  | L2 | `backend/local_browser.py` duplicate-key refusal answers 400 | `(400, 'INVALID_ARGUMENT') == (422, 'INVALID_ARGUMENT')` (`test_export_http.py:246`) |

  Restored digests (each equal to its baseline): `lane_store.py` `98838d16…`, `lane.py` `51c7ed37…`, `local_browser.py` `6a2903dc…`, `control_lifecycle.py` `80170166…`, `u6_real_export.py` `aa350c35…`, `u6_preservation.py` `84ef0e94…`, `serve_docsuri_u6.py` `f58a0212…`, `u6-lint.toml` `dec621d4…`, `u6-lint-scripts.toml` `155f2cae…`, `u6-lint-accounts.toml` `748cb066…`, the workflow `88f461bd…`, `conftest.py` `d649ef1c…`, `test_lane_write_path.py` `85f2ed5a…`, `test_u6_preservation.py` `6a6d6d64…`, `test_u6_lint_gate.py` `ad04a3f4…`, `test_u6_test_volume.py` `ae228362…`, `test_owner_guard.py` `a78f5903…`, `history.tsx` `374bd6b5…`, `dialogs.tsx` `06451bef…`, `status.tsx` `c3daa7f1…`. After the restores the Python consumer inventory prints "ok". `frontend`'s `check:consumers` (which pins `history.tsx` and `dialogs.tsx`) was not run here; it is in Step 63's drift checks.
- **Deviation, `unit-test-instructions.md`:** the loop-back 3 section was written there and then removed again, because once the file differed from its approved text the code-generation guard refused every further command for U6 ("the plan, test instructions, or Testing Contract changed since the person approved them"). The file is back at its approved bytes and the guard cleared. The section's full text is kept at `~/.docsuri-u8/lead-scripts/l3-records/u6-uti-loopback3-section.md`, to be written by the coordinator when the workflow allows it.
- **Not run here (Step 63's):** the fresh-realm coverage and frontend lanes, the browser lane, the regressions, U2's cumulative lane, the drift checks and the exact-form CI lint step. Step 61's coverage-phase evidence is also Step 63's.
- **Plan boxes:** Steps 53–58, 60 and 62 are ticked after their runs. Step 59 stays open (its exact-form run, above). Step 61 stays open until Step 63's coverage phase, as its text says. Steps 1–52 and 63 are untouched.

#### Step 63 — run and record (2026-11-18, the coordinator)

- **`unit-test-instructions.md` and a second Plan Approval.** The coordinator wrote the loop-back 3 section into the instructions on 2026-11-18, byte for byte the developer's kept draft (`~/.docsuri-u8/lead-scripts/l3-records/u6-uti-loopback3-section.md`). Because the instructions changed after the build started, the engine asked for Plan Approval again, with the plan text unchanged; the person approved it ("Approve Plan", 2026-11-18). That approval started a new attempt and cleared every box of the plan, so each box is ticked again only after the runs below passed.
- **U5 re-checked and re-verified on the way.** L3-10 (A)'s wrap of `backend/modules/accounts/local_http.py` (one call, at about line 129, syntax tree unchanged) changed a file U5's `source-manifest.json` claims, so U5's terminal review no longer covered its bytes. Before U6's second Plan Approval the engine routed to U5: a recovery re-check (iteration 2, READY, no new finding), a fresh checkpoint verification (VerificationRun `339aec71-7bc2-46e6-949d-4e084155f809`, J01–J14, A11Y and SEC passed, 2026-11-18 12:15–12:31 UTC, on U8 realm `docsuri-u8-1eb22dced7190fa4`) and the person's re-approval of U5. The realm's evidence is kept at `~/.docsuri-u8/final-evidence/docsuri-u8-preserved-docsuri-u8-1eb22dced7190fa4-750bd76b`. Making room for that run, with the person's approval, the archived U8 realm `docsuri-u8-8958a883e9a63bf2` (its evidence kept) was removed and the person deleted two unused simulator runtimes.
- **Development realm archived:** `docsuri-u6-fe4ff79e96a27ee3`, kept at `~/.docsuri-u8/final-evidence/docsuri-u6-preserved-docsuri-u6-fe4ff79e96a27ee3-a366c21b`. The turn-end formatter, run once before the recorded runs, rewrapped only `frontend/test/u6-export/export-view.test.tsx`'s loop-back 1 lines 128–130 (SHA-256 `e24963f8…` → `645260d9…`); no other listed file changed.
- **Fresh-realm lanes** (`~/.docsuri-u8/lead-scripts/final_other_lanes.py --lanes u6`, log folder `~/.docsuri-u8/lead-scripts/final-lanes/run-20261118-214238-93212`, 2026-11-18 21:42:39–21:49:53 KST (12:42–12:50 UTC); Docker only through Colima, `umask 077`; every step exit 0):
  - realm A `docsuri-u6-184aee4a136ca171` (setup, migrate; source SHA-256 `2227fd85…` for every phase):

    | Phase | Result |
    |---|---|
    | `component` | 591 tests, 0 failures |
    | `integration` | 48 tests, 0 failures |
    | `coverage` | 949 tests, 0 failures; backend total 90.0%, `scripts/u6_preservation.py` report 99.0% (floors 80) |
    | `frontend` | 123 tests, 0 failures; `src/u6-export` 98.53% of lines (floor 80) |
    | `tsc --project tsconfig.u6-export.json --noEmit --incremental false` | exit 0 |
    | U6's ESLint command (including `e2e/u6-approved-export`) | exit 0 |

    archived and kept at `~/.docsuri-u8/final-evidence/docsuri-u6-preserved-docsuri-u6-184aee4a136ca171-64f7ebf2`;
  - realm B `docsuri-u6-c97739227a0f260c`: `browser` 14 journeys, 0 failures; archived and kept at `~/.docsuri-u8/final-evidence/docsuri-u6-preserved-docsuri-u6-c97739227a0f260c-2488981a`.
- **Checks without a realm** (`~/.docsuri-u8/lead-scripts/u6_step63_extra.py`, logs in `~/.docsuri-u8/lead-scripts/final-lanes/u6-step63-extra-20261118-123557`, every step exit 0):
  - the workflow step "Lint export and shared runtime changes", its `run:` block taken from `.github/workflows/u6-approved-export.yml` and run the way GitHub runs a bash step (`bash --noprofile --norc -eo pipefail`), from the repository root: invocations 1–4 each "All checks passed!". This is the exact-form run Step 59 waited for;
  - the workflow step "Prior-unit transport, recovery and keyring regressions", the same way: 75 passed, 1 deselected;
  - the shared contract's lint (`shared/python`, `.venv/bin/ruff check --no-cache .`): all checks passed;
  - drift: `tools/inventory_consumers.py` printed "ok: actual Python shared-contract consumers"; `node scripts/inventory-consumers.mjs` printed "ok: actual TypeScript imports, wire casts and view-adapter inventory";
  - U2's cumulative Vitest lane (`vitest.u2-cumulative.config.ts --coverage`): 718 passed in 59 files, 97.45% of lines. The plan expected 731 from a baseline of 728; that baseline predates U5's loop-back 3, whose merges took `test/u5-topics` (registered in the same lane) from 49 tests to 36, so 728 − 13 + U6's 3 new cases = 718.
- **Counts per changed component** (the standard strategy's five to eight; counts above eight kept under L1-8): ExportStore 92, ExportLane 35, EnvironmentTool 75, `history.tsx` 18, `dialogs.tsx` 9, `export-view.tsx` 16, each above range, kept. `history.tsx`'s count is 18; the earlier 15 in this file's test table (loop-back 1) is superseded. Collect-only: 949.
- **Plan boxes:** after the runs above passed, every box of Steps 1–63 is ticked again: Steps 1–52, whose work these runs exercise again; Steps 53–58, 60 and 62, whose own runs passed earlier in this attempt; Step 59, on the exact-form lint run; Step 61, on the coverage phase; and Step 63. The architecture review and U6's checkpoint follow through AI-DLC.

## Records for approval at the U6 checkpoint

1. **R-01 entity settlement.** ExportConnection's revision minimum of 1 and its four states describe every record visible outside the store. Inside the store there is also:
   - an internal pre-connection reservation (state `pending`, revision 0, holder, start time) that never reaches the wire;
   - internal columns: the connection's `workspace_id`, the attempt's `deadline_at` and `creator_confirmed`, the effect's `ended_at` and `accepted_at`.
2. **R-15.** The approved logical-components source line "decisions D1–D14" should read "D1–D16". The file is not edited.
3. **Settlement S2.** `ExportDestinationEntry` carries optional `readable`, `creationCapability` and `writable`, and ExportDestinations carries optional `listingComplete` and `lastDestinationId`. The destination step derives `empty`, `partial` and `unavailable` from them.
4. **ExportConnection state machine amendment.** The pending reservation is promoted, released, taken over and swept, each by compare-and-set on its holder (R-02's guard). A check whose row was taken over neither stores nor deletes.
5. **The hash rule.** `renderedContentHash` is the SHA-256 of the page-creation body in U4's digest form, superseding the frozen prose that hashed `renderedText`. `bindingHash` keeps the frozen prefix plus JCS, with the destination limited to its five identity fields.
6. **A6's reading of "currently permitted destinations".** Pages shared with the connection that are readable and not known to be refused. `lastDestinationId` is only a preselection hint.
7. **A2 and A3.** `listExportHistory` at `/api/v2/c09/list-export-history` uses the six base codes. `settleExportEffect` at `/api/v2/c09/settle-export-effect` uses the base codes plus `CONFLICT` and `IDEMPOTENCY_CONFLICT`.
8. **BR2.6 reading.** A revision whose approval is still approved and unconsumed keeps its rendered tree until that approval ends. The current never-approved revision keeps it until the 7-day purge.
9. **The test-path check.** cicd §4.3's "tracked in git" is read as "listed by `git ls-files --cached --others --exclude-standard`", which equals "tracked" in CI.
10. **Extra CI path filters.** The workflow also triggers on the earlier tool scripts U6's tool imports (`verify_docsuri_u1/u3/u4/u5.py`, `bootstrap_docsuri_u1.py`) and on the regression folders it runs (`tests/u1_integrated_paper_journey/**`, `tests/u2_account_personal_controls/**`). cicd §2.1 says the workflow mirrors U5's line for line, and these only add triggers.
11. **`backend/u3_host.py` in `.coveragerc.u6`,** beyond cicd §2.5's list, because its new gates and lane lifecycle are more than one value (86% measured).
12. **The two cancel-race fixes** (deviations 1 and 2), **the U4 tool's expired-environment archive** (deviation 37, the person's choice), and **the keyboard-focus fix in U4's `jobs.tsx`** (deviation 38). These are the changes in U4-owned files beyond the plan's table.
13. **The check schedule's 6 h hourly limit,** the rate-limit wait field, and the named enum defs (deviations 20, 21 and 23).
14. **The Construction Verification Command:**

    ```bash
    backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    ```

    It needs a fresh U6 environment (`setup`, then `migrate`), because the browser phase refuses an environment that already holds evidence.

15. **The dialog focus-trap rework** (deviation 39): both export dialogs now control Tab and Shift+Tab themselves and pull focus back inside while open. The shell still does what the plan's `dialogs.tsx` line describes (focus moves in, Tab is trapped, Escape closes, focus returns), but its trap no longer copies U5's `ConfirmationDialog`, which the plan named as its model.

## Open items and handoffs

- **Memory headroom.** The browser phase peaked at 92–96% of its 1 GiB budget across runs; the highest was 1,035,042,816 bytes. A future `rss-limit` failure would come from that budget, which stays as approved.
- **U4's cancel button.** U4's "분석 취소 요청" still uses `disabled` and disappears after a successful cancel, so keyboard focus can fall to the page body there too. It is outside the export path and was left unchanged.
- **U6 `serve` phase.** When used for diagnosis, it ended at its 300 s bound as "process deadline reached" rather than a normal bounded stop, and wrote no serve evidence. The browser phase is unaffected.
- **Preserved environments.** The Mac's restart at 23:44 KST on 2026-10-20 cleared `/tmp`. It took every unit's run folder and the archive folders kept until then: twelve U6 archives, the U5 archives `docsuri-u5-1b0a6a84b76b03d4` and `docsuri-u5-e41cf4e7d2bf5160`, and the U4 archives `docsuri-u4-8da1d88967785045` and `docsuri-u4-5e615b9cb245ce9e`. Their stopped containers and volumes remain in Colima. Removing them is the person's decision.
  - Archived since: `docsuri-u6-9422a43afe2291e1` (`/private/tmp/docsuri-u6-preserved-docsuri-u6-9422a43afe2291e1-e731e63d`).
  - Running: U6 `docsuri-u6-8dec1b7265c28b43`, holding U5's checkpoint run; U6's own checkpoint needs another fresh environment.
  - Stopped by the restart, run folders lost, not touched: U1, U2 and U7's environments and U6 `docsuri-u6-3c61c9fc0ee6a26b`. Each unit's own tool recreates its environment when it is next needed.
- **For U8:**
  - register `"ApprovedExport": ExportLifecycleParticipant(self.transactions, clock=…)` in `backend/control_worker.py`'s participant table;
  - add the three scope pairs to the lifecycle manifest;
  - choose the hosted key folder (infrastructure Q2 A);
  - the inherited capacity amendment `ops/src/docsuri_ops/u4_capacity.sql` still binds its WAL term to `docsuri_u4`, so the U6 realm measures database bytes only.
- **Undeclared dependency.** `rfc8785` is used directly by `rendering.py` but reaches the backend only through `docsuri-ops`. Declaring it in `backend/pyproject.toml` is a decision for this checkpoint.
- **Safe-codes side effect.** Adding `OUTCOME_UNKNOWN` to `SAFE_CODES` makes U4's existing retry path reachable for that code; U4's tests stay green.
- **Formatting debt.** `ruff format --check` flags `key_commands.py`, `token_vault.py` and the U2 file `control_lifecycle.py` (re-checked 2026-11-18); that is layout only. The U2 file's 30 long lines were wrapped in loop-back 3 (L3-10 (A)), and it passes `ruff check` under E,F,I,UP,B at line length 100. CI runs `ruff check`, which passes.
- **The one real Notion export** happens at Build and Test, following [u6-real-export-runbook.md](u6-real-export-runbook.md), only after the owner approves its exact content. Before that run, its Notion UI wording should be checked against Notion's current screens.
