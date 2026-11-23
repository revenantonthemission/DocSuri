## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-22
**Iteration:** 7

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | backend/modules/export/lane.py > `_unsent_outcome` and `_send` (code-summary.md deviation 12) | When the stored token cannot be opened after the claim, the attempt is recorded as `refused` and the effect ends `failed` (`connection-changed` or `policy-unresolved`). Before the claim, the same condition is could-not-check, and the effect waits up to 24 h. A momentary key-protection fault after the claim, such as the 5 s key-lock wait running out, therefore ends the owner's accepted export for good. The owner has to prepare and approve again. Nothing is sent, so this is safe, but it is inconsistent with BR1.6 and with the claim guard's `connection-unavailable` handling. | Either record a post-claim `policy-unresolved` as a resumable could-not-check, or keep the failure and record it as an owner-visible decision at the checkpoint, together with the retry cost. | Unresolved |
| R-02 | Minor | backend/u3_host.py > `_contribution_gates` (topics branch) | The topics gate now admits the U6 realm triple for a topics-only composition with no export factory. The code comment says U6 reaches the topics gate through `assemble_u5`, but a direct `assemble_u3(topics_factory=..., research_factory=...)` in the U6 realm also passes. The only strict gate is the export one. This loosens U5's "exact owned realm" rule. | Tighten the topics branch so the U6 triple is accepted only when `export` is set, or add a test that pins and justifies the looser behaviour. | Unresolved |
| R-03 | Minor | .github/workflows/u6-approved-export.yml > `on.pull_request.paths` | U6 changes `frontend/types/wire/dtos.ts`, and the U6 `tsc` and Vitest lanes depend on it, but the path filter lists neither `frontend/types/**` nor `frontend/vitest*.ts`. A change that touches only those files skips the lane that checks them. `shared/**` covers regeneration but not a hand edit of the generated file. | Add `frontend/types/**` and `frontend/tsconfig*.json` to the path filters. | Unresolved |
| R-04 | Minor | backend/modules/export/rendering.py:27 (`import rfc8785`) and backend/pyproject.toml | The module imports `rfc8785` directly, but the backend declares it only transitively through `docsuri-ops`. It is present in `uv.lock` and in the venv, so nothing breaks today. The binding hash, which approval depends on, rests on an undeclared direct dependency. code-summary.md already records this as open. | Declare `rfc8785>=0.1.4,<1` in backend/pyproject.toml and refresh uv.lock. | Resolved (reviewer) |
| R-05 | Minor | frontend/src/u6-export/connect-form.tsx > token input (`type="text"`) | The plan chose "not a password field" so password managers stay out. The side effect is that the Notion integration token shows in clear text on screen while it is typed or pasted. The value is cleared on submit and never stored, so this is only screen-exposure risk. | Mask the display without making it a password field, for example with `-webkit-text-security` or a reveal toggle that defaults to hidden. Keep `autocomplete="off"`. | Unresolved |
| R-06 | Minor | frontend/src/u6-export/dialogs.tsx > `DialogShell` `onKeyDown` | The new handler calls `preventDefault()` and moves focus on every Tab keydown, including Tab with Ctrl, Alt or Meta held. Those chords are not dialog navigation (assistive-technology and browser shortcuts use some of them), and the handler now swallows them. The new tests cover plain Tab and Shift+Tab, a Tab after focus fell to the body, and a refocus after the page moved focus. None presses an arrow key inside the radio group and then Tab, which is the case the checked-radio stop rule exists for. | Return early from `onKeyDown` when `event.ctrlKey`, `event.altKey` or `event.metaKey` is set. Add one test that moves between the two settle radios with an arrow key and then presses Tab and Shift+Tab. | Unresolved |
| R-07 | Minor | tests/u6_approved_export/operations/test_u6_runner.py (new tests) and scripts/verify_docsuri_u6.py > `start_server` | The new tests cover the supervision loop (`bounded_process`) and `process_tree_memory`. None covers the startup check in `start_server`, which now calls `enforced_bytes(*process_tree_memory(...))`. The claim that startup and supervision enforce the same figure is true in the code, but nothing pins it. A later edit could revert startup to plain RSS without a test failing. | Add one test that patches `process_tree_memory` to return an RSS above the budget with a PSS below it, and one the other way round, and asserts `start_server` refuses only when the enforced figure is over budget. | Unresolved |
| R-08 | Minor | scripts/verify_docsuri_u6.py > `process_tree_rss` | After this change `process_tree_rss` has no production caller. Only a test assertion (`test_process_tree_memory_enforces_pss_only_on_linux`) uses it. | Remove it and the assertion, or note it as a kept helper. | Unresolved |
| R-09 | Minor | code-summary.md deviation 40 and u6-build-verification-log.md §11.10 (commit 992862a4) | U6's approval records now carry a change to U5's runner and fixture clock (scripts/verify_docsuri_u5.py, scripts/u5_browser_fixtures.py, U5's test_runner.py). The change was disclosed and the person asked for it. It is not U6 behaviour, so a reader of U6's record may take it for U6 scope. | Keep the U5 clock fix recorded as a U5 follow-up, or state in deviation 40 that it is outside U6's behaviour and sources. | Unresolved |
| R-10 | Minor | backend/local_profile.py > `PUBLIC_ORIGINS` and the profile loader's `return cls(...)` | U6's origin is unchanged: `PUBLIC_ORIGINS.get("u6", ...)` falls back to `https://127.0.0.1:<applicationPort>`, which is 18099 for u6, and only `"u8"` is in the map. The risk is structural: any later entry added to this map for another unit changes that unit's origin silently, and the existing per-unit origin bindings in `ops/src/docsuri_ops/local_transport.py` `_transport_prefix` would then fail closed for it. No test pins that the map contains only u8. | Add one test (U8's) that asserts `PUBLIC_ORIGINS` has exactly the key `u8`, and that u1 to u6 resolve to `https://127.0.0.1:<applicationPort>`. Not blocking for U6. | Resolved (reviewer) |
| R-11 | Minor | backend/local_profile.py > `LocalProfile.listen_port` | The new property infers the listening port by looping over `PORTS` and matching on database port and `public_origin(unit)`, falling back to parsing the origin. For U6 it resolves to 18099 and the result is correct. But the answer depends on two tables staying consistent (`PORTS` and `PUBLIC_ORIGINS`). U8's pinning test covers only the origin side, not that `listen_port` returns the application port for each unit. | Have U8 add one assertion that `listen_port` equals the application port for the synthetic profiles u2 to u6. Not blocking for U6. | Unresolved |
| R-12 | Minor | frontend/types/wire/dtos.ts (regenerated, header SHA a8e288c4...) | The regenerated file carries a new SHA header and many added U8 types. `retainedUntil` appears in both schema files but not in the TypeScript output. The diff removes only the header line, so every type U6's frontend uses is unchanged in shape. U6's `tsc` lane and 113 Vitest tests pass, so this is informational only. | None for U6. U8 should confirm that omitting `retainedUntil` from the TypeScript output is intended (it is not part of the browser-facing closure). | New |

> R-01 Reviewer note: backend/modules/export/lane.py is untouched by U8 round 6; the post-claim refused/failed behaviour is unchanged.

> R-02 Reviewer note: backend/u3_host.py topics branch is unchanged in what this round touched; not tightened.

> R-03 Reviewer note: The U6 workflow path filters were not changed.

> R-05 Reviewer note: The connect form was not changed.

> R-06 Reviewer note: DialogShell was not changed.

> R-07 Reviewer note: No start_server test was added.

> R-08 Reviewer note: process_tree_rss is still without a production caller.

> R-09 Reviewer note: Deviation 40 is unchanged.

> R-11 Reviewer note: U8's profile code still adds `listen_port` (two definitions in the diff). The check is U8's, not blocking for U6.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `git diff HEAD` on control_lifecycle.py | `RETAINED_BY_POLICY` is a tuple whose first two entries are U2's bounded-audit key and ApprovedExport's `external-copies-retained-by-owner`, plus the new backups key. `retained_until` is optional and checked only when given. | U6's reason key is still reported as retained by policy. Without a date, the statement is exactly as before. |
| Export lifecycle participant (backend/modules/export/control_lifecycle.py:86, :223) | Still returns `reasonKey = external-copies-retained-by-owner` and never sets `retainedUntil`. Only backend/modules/operations/lifecycle.py:224 sets it. | The `control_worker.py` pass-through is conditional on the key being present, so U6 acknowledges with no date. This holds. |
| Contract diff | The only removed lines are the 3.1.0 to 4.0.0 `$comment` in the two schema files and the dtos.ts header. The rest is additions. `test_export_contract.py` pins C09 at 2.1.0 and its frozen errors, operations and headers. | C09 is untouched. The change is additive. |
| ruff on control_lifecycle.py, control_worker.py and backend/modules/export | All checks passed | Clean |
| tsc `--project tsconfig.u6-export.json --noEmit --incremental false` | No output (clean) | U6's types still compile against the regenerated dtos.ts. |
| Vitest U6 lane | 11 files, 113 tests passed | U6's frontend behaviour is unchanged. |
| sensor-traceability | pass: true, no gaps, orphans or invalid entries | Traceability holds. |

### Summary

U8's round 6 change is additive for U6. The lifecycle participant still reports `external-copies-retained-by-owner` as retained by policy with no date, C09 is unchanged at 2.1.0, and U6's frontend and backend types are unchanged in shape. All open prior findings are Minor and still apply, so the verdict is READY.
