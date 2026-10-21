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
- **Formatting debt.** `ruff format --check` flags `key_commands.py` and `token_vault.py`, and the U2 file `control_lifecycle.py` keeps its 30 pre-existing findings. CI runs `ruff check`, which passes.
- **The one real Notion export** happens at Build and Test, following [u6-real-export-runbook.md](u6-real-export-runbook.md), only after the owner approves its exact content. Before that run, its Notion UI wording should be checked against Notion's current screens.
