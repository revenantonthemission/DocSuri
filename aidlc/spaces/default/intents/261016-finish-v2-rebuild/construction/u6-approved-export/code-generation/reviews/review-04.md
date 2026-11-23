## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-21T03:49:29Z
**Iteration:** 4

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | backend/modules/export/lane.py > `_unsent_outcome` and `_send` (code-summary.md deviation 12) | When the stored token cannot be opened after the claim, the attempt is recorded as `refused` and the effect ends `failed` (`connection-changed` or `policy-unresolved`). Before the claim, the same condition is could-not-check, and the effect waits up to 24 h. A momentary key-protection fault after the claim, such as the 5 s key-lock wait running out, therefore ends the owner's accepted export for good. The owner has to prepare and approve again. Nothing is sent, so this is safe, but it is inconsistent with BR1.6 and with the claim guard's `connection-unavailable` handling. | Either record a post-claim `policy-unresolved` as a resumable could-not-check, or keep the failure and record it as an owner-visible decision at the checkpoint, together with the retry cost. | Unresolved |
| R-02 | Minor | backend/u3_host.py > `_contribution_gates` (topics branch) | The topics gate now admits the U6 realm triple for a topics-only composition with no export factory. The code comment says U6 reaches the topics gate through `assemble_u5`, but a direct `assemble_u3(topics_factory=..., research_factory=...)` in the U6 realm also passes. The only strict gate is the export one. This loosens U5's "exact owned realm" rule. | Tighten the topics branch so the U6 triple is accepted only when `export` is set, or add a test that pins and justifies the looser behaviour. | Unresolved |
| R-03 | Minor | .github/workflows/u6-approved-export.yml > `on.pull_request.paths` | U6 changes `frontend/types/wire/dtos.ts`, and the U6 `tsc` and Vitest lanes depend on it, but the path filter lists neither `frontend/types/**` nor `frontend/vitest*.ts`. A change that touches only those files skips the lane that checks them. `shared/**` covers regeneration but not a hand edit of the generated file. | Add `frontend/types/**` and `frontend/tsconfig*.json` to the path filters. | Unresolved |
| R-04 | Minor | backend/modules/export/rendering.py:27 (`import rfc8785`) and backend/pyproject.toml | The module imports `rfc8785` directly, but the backend declares it only transitively through `docsuri-ops`. It is present in `uv.lock` and in the venv, so nothing breaks today. The binding hash, which approval depends on, rests on an undeclared direct dependency. code-summary.md already records this as open. | Declare `rfc8785>=0.1.4,<1` in backend/pyproject.toml and refresh uv.lock. | Unresolved |
| R-05 | Minor | frontend/src/u6-export/connect-form.tsx > token input (`type="text"`) | The plan chose "not a password field" so password managers stay out. The side effect is that the Notion integration token shows in clear text on screen while it is typed or pasted. The value is cleared on submit and never stored, so this is only screen-exposure risk. | Mask the display without making it a password field, for example with `-webkit-text-security` or a reveal toggle that defaults to hidden. Keep `autocomplete="off"`. | Unresolved |
| R-06 | Minor | frontend/src/u6-export/dialogs.tsx > `DialogShell` `onKeyDown` | The new handler calls `preventDefault()` and moves focus on every Tab keydown, including Tab with Ctrl, Alt or Meta held. Those chords are not dialog navigation (assistive-technology and browser shortcuts use some of them), and the handler now swallows them. The new tests cover plain Tab and Shift+Tab, a Tab after focus fell to the body, and a refocus after the page moved focus. None presses an arrow key inside the radio group and then Tab, which is the case the checked-radio stop rule exists for. | Return early from `onKeyDown` when `event.ctrlKey`, `event.altKey` or `event.metaKey` is set. Add one test that moves between the two settle radios with an arrow key and then presses Tab and Shift+Tab. | Unresolved |
| R-07 | Minor | tests/u6_approved_export/operations/test_u6_runner.py (new tests) and scripts/verify_docsuri_u6.py > `start_server` | The new tests cover the supervision loop (`bounded_process`) and `process_tree_memory`. None covers the startup check in `start_server`, which now calls `enforced_bytes(*process_tree_memory(...))`. The claim that startup and supervision enforce the same figure is true in the code, but nothing pins it. A later edit could revert startup to plain RSS without a test failing. | Add one test that patches `process_tree_memory` to return an RSS above the budget with a PSS below it, and one the other way round, and asserts `start_server` refuses only when the enforced figure is over budget. | New |
| R-08 | Minor | scripts/verify_docsuri_u6.py > `process_tree_rss` | After this change `process_tree_rss` has no production caller. Only a test assertion (`test_process_tree_memory_enforces_pss_only_on_linux`) uses it. | Remove it and the assertion, or note it as a kept helper. | New |
| R-09 | Minor | code-summary.md deviation 40 and u6-build-verification-log.md §11.10 (commit 992862a4) | U6's approval records now carry a change to U5's runner and fixture clock (scripts/verify_docsuri_u5.py, scripts/u5_browser_fixtures.py, U5's test_runner.py). The change was disclosed and the person asked for it. It is not U6 behaviour, so a reader of U6's record may take it for U6 scope. | Keep the U5 clock fix recorded as a U5 follow-up, or state in deviation 40 that it is outside U6's behaviour and sources. | New |

> R-01 Reviewer note: backend/modules/export/lane.py is unchanged since U6's feature commit 938312b7. A post-claim key-protection fault still ends the effect as failed instead of resumable. Nothing is sent.

> R-02 Reviewer note: backend/u3_host.py is unchanged since U6's feature commit. The topics branch still admits the U6 realm triple without an export factory.

> R-03 Reviewer note: The path filter in .github/workflows/u6-approved-export.yml still lists neither frontend/types/** nor frontend/tsconfig*.json. It lists frontend/src/**, frontend/*u6*, frontend/package.json and frontend/pnpm-lock.yaml.

> R-04 Reviewer note: backend/pyproject.toml still has no direct rfc8785 declaration (grep finds none), while rendering.py imports it.

> R-05 Reviewer note: frontend/src/u6-export/connect-form.tsx still has the token input as type="text" with autoComplete="off" and no display masking.

> R-06 Reviewer note: frontend/src/u6-export/dialogs.tsx still has no ctrlKey, altKey or metaKey guard in the Tab handler.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| sensor-traceability | PASS: 0 gaps, orphans, invalid entries | traceability.json is consistent. |
| sensor-required-sections (plan, unit-test-instructions, code-summary) | PASS, 6 H2 headings each | Required sections are present. |
| gh run view 39528978363 --log --job 118991218911 | headSha 992862a4, all four jobs succeeded; peakRssBytes 1093373952, peakPssBytes 839457792 | Matches §11.10. The old RSS rule would have stopped this run. The PSS figure is within the 1 GiB budget, with about 22% margin. |

### Differential check of 992862a4 on U6's paths

- **Over-budget runs are not hidden.** On Linux a process whose smaps_rollup cannot be opened or parsed counts its full RSS, and the line match is `startswith("Pss:")`, so `Pss_Anon:` and similar lines are not picked up. On other platforms `process_tree_memory` returns `pss=None` and `enforced_bytes` falls back to the RSS sum. The macOS RSS rule is kept, and the local macOS re-run at 801 MB RSS agrees with that.
- **Same figure at both checks.** `supervise` calls `enforced_bytes(totals["peak"], totals["peakPss"])` and `start_server` calls `enforced_bytes(*process_tree_memory(...))`, both against `MAX_RSS = GIB`. The 1 GiB budget is unchanged. The `rss-limit` reason name is kept, with a comment saying it is the proportional budget on Linux.
- **Both PSS and RSS overruns are tested.** The `over` parametrization shows a PSS over budget stops the run and an RSS-only excess passes. The peaks are recorded in the supervision record and in `safe_phase_summary`.
- **The process-tree snapshot is unchanged.** It is still one `ps` snapshot with the same tree expansion and deadline handling.
- **Nothing else in U6 changed.** The commit touches only the runner, its test file and U6's records on U6's side. The working-tree diff of the verification log adds only the CI and local re-run lines for §11.10, and they match the CI evidence.

### Summary

The Linux PSS rule is a bounded, disclosed change. It cannot hide an over-budget run: unreadable processes count full RSS, macOS keeps RSS, and the startup check and supervision loop enforce the same figure. CI evidence matches the records. Open findings are all Minor (R-01 to R-06, unchanged, plus three new Minor items), so the verdict is READY.
