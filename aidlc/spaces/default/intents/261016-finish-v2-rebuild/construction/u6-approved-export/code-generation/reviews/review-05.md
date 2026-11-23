## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-22T05:52:00Z
**Iteration:** 5

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
| R-10 | Minor | backend/local_profile.py > `PUBLIC_ORIGINS` and the profile loader's `return cls(...)` | U6's origin is unchanged: `PUBLIC_ORIGINS.get("u6", ...)` falls back to `https://127.0.0.1:<applicationPort>`, which is 18099 for u6, and only `"u8"` is in the map. The risk is structural: any later entry added to this map for another unit changes that unit's origin silently, and the existing per-unit origin bindings in `ops/src/docsuri_ops/local_transport.py` `_transport_prefix` would then fail closed for it. No test pins that the map contains only u8. | Add one test (U8's) that asserts `PUBLIC_ORIGINS` has exactly the key `u8`, and that u1 to u6 resolve to `https://127.0.0.1:<applicationPort>`. Not blocking for U6. | New |

> R-01 Reviewer note: backend/modules/export/lane.py is unchanged by U8 (git status shows no U6 export file modified); the post-claim could-not-open handling is as before.

> R-02 Reviewer note: backend/u3_host.py is unchanged; the looser topics-gate acceptance of the U6 realm triple remains.

> R-03 Reviewer note: .github/workflows/u6-approved-export.yml is unchanged; the path filter still omits frontend/types/** and tsconfig files. Note that U8's regeneration of frontend/types/wire/dtos.ts is a case this gap could hit.

> R-04 Reviewer note: backend/pyproject.toml now declares rfc8785==0.1.4 directly, and backend/uv.lock gains the matching dependency and requires-dist lines with no version change. The exact pin follows the file's existing notion-client==3.1.0 convention and equals the locked version, so it meets the intent: the approval binding hash no longer rests on an undeclared dependency.

> R-05 Reviewer note: frontend/src/u6-export/connect-form.tsx is unchanged; the token is still shown in clear text while typed.

> R-06 Reviewer note: frontend/src/u6-export/dialogs.tsx is unchanged; Tab chords with Ctrl, Alt or Meta are still swallowed.

> R-07 Reviewer note: scripts/verify_docsuri_u6.py and the U6 runner tests are unchanged; startup memory enforcement is still unpinned by a test.

> R-08 Reviewer note: process_tree_rss still has no production caller.

> R-09 Reviewer note: Deviation 40 and build-log section 11.10 are unchanged and still carry the U5 clock change in U6's record.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| ruff check on the 9 changed backend and ops files | PASS | No lint regression in the allowlist files. |
| tsc --project tsconfig.u6-export.json --noEmit | PASS | U6's frontend types still compile against the regenerated frontend/types/wire/dtos.ts. |
| vitest run --config vitest.u6-export.config.ts | PASS: 11 files, 113 tests | U6's frontend behaviour is intact on the new bytes. |
| C09 block comparison (HEAD vs working tree, text of `id: C09` section) | IDENTICAL (16803 characters each) | C09 stays at 2.1.0 with the same operations, frozen errors, two browser operations and headers under release 4.0.0. |
| Deletions in regenerated outputs (git diff -U0) | Only the release or SHA header comment line in dtos.ts, workspace.schema.json and execution.schema.json | The regeneration is additive; no existing type or property U6 uses changed shape. |
| shared/python/tests/test_export_contract.py diff (read, not run) | Two edits only: release number 3.1.0 to 4.0.0, and the test rename | The C09 2.1.0 assertion and the frozen-error and header assertions are untouched; nothing is weakened. |
| pytest suites | Not run, by instruction | Backend and shared suites stay unrecorded on these bytes; U6's verification command runs after this review. |

### Summary

U8's 16 changes to U6-claimed files are additive allowlist entries for the `u8` or `service-operations` realm plus the `production` realm, one direct `rfc8785==0.1.4` dependency, and regenerated outputs that only add types. They leave U6's realm admission, origin (18099), ports, purposes, export gate, C09 block (byte-identical) and the frontend lanes (tsc and 113 Vitest tests) intact. R-04 is fixed; the other eight prior Minor findings still apply, none blocking, with one new Minor.
