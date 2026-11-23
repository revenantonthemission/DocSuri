## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-22T09:47:01Z
**Iteration:** 6

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
| R-11 | Minor | backend/local_profile.py > `LocalProfile.listen_port` | The new property infers the listening port by looping over `PORTS` and matching on database port and `public_origin(unit)`, falling back to parsing the origin. For U6 it resolves to 18099 and the result is correct. But the answer depends on two tables staying consistent (`PORTS` and `PUBLIC_ORIGINS`). U8's pinning test covers only the origin side, not that `listen_port` returns the application port for each unit. | Have U8 add one assertion that `listen_port` equals the application port for the synthetic profiles u2 to u6. Not blocking for U6. | New |

> R-01 Reviewer note: backend/modules/export/lane.py has no diff against HEAD; the post-claim `refused` outcome is unchanged.

> R-02 Reviewer note: backend/u3_host.py has no diff against HEAD; the topics branch still admits the U6 triple without an export factory.

> R-03 Reviewer note: The CI path filter is untouched.

> R-05 Reviewer note: connect-form.tsx is unchanged; the token input is still `type="text"`.

> R-06 Reviewer note: dialogs.tsx is unchanged; Tab with Ctrl, Alt or Meta is still swallowed.

> R-07 Reviewer note: No test for the `start_server` startup memory check was added.

> R-08 Reviewer note: `process_tree_rss` is still unused in production.

> R-09 Reviewer note: Deviation 40 is unchanged.

> R-10 Reviewer note: U8's `test_the_public_origins_hold_only_the_composed_realm` pins `PUBLIC_ORIGINS == {"u8": "https://127.0.0.1:18110"}`. It also pins the u2 to u6 origins, including u6 at `https://127.0.0.1:18099`. U1 is not in the pinned list, which does not matter for U6.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `git diff HEAD` on the listed U8 files | Reviewed in full | See the Summary for what each change does to U6. |
| ruff on the changed backend files | PASS | No lint regressions. |
| U6 `tsc` (tsconfig.u6-export.json) | PASS | The regenerated `dtos.ts` still type-checks against U6's front end. |
| U6 Vitest, no coverage | PASS, 11 files, 113 tests | U6's front-end behaviour holds. |
| sensor-traceability | PASS, 0 gaps and 0 orphans | U6's traceability is intact. |
| pytest | Not run, as instructed | The backend claims below rest on reading the code and the diffs. They are not backed by a U6 suite run on these bytes. The checkpoint verification must carry that. |

### Summary

U6's reviewed behaviour holds under U8's changes.

- **Synthetic loader:** `LocalProfile.load` keeps the same owner, mode and link checks through `custody_failure`. U6 still resolves to its 18099 and 15499 ports and the `approved-export` realm. Its origin is still `https://127.0.0.1:18099` (R-10 is now pinned by a test). The production loader is a separate subclass and cannot be reached from the U6 path.
- **Database logins:** `require_auth=scram-sha-256` is added to every connection. U6's environment initialises PostgreSQL with `--auth-host=scram-sha-256` (verify_docsuri_u6.py:413), and the connections are TCP, so the requirement is satisfied. The U6 limits and owner set are unchanged, because `complete` is false for `docsuri_u6`.
- **Key folders:** `key_folder` returns the run root for `approved-export`, so synthetic profiles keep their layout. U6's `export-keys/` folder is untouched (`KEY_FOLDER` in u6_host.py is unchanged). The cursor key stays at `search-cursor.key`, and `u3_host.py` has no diff.
- **Error answers:** `request_identifier()` returns the old fallbacks (`boundary`, `assembly`) or a fresh uuid4 when no context is set, so earlier assemblies are unchanged. `assemble` without a boundary keeps the `127.0.0.1` host list and the old stack.
- **Lifecycle:** ApprovedExport's participant mapping is unchanged. The new `research` entry adds a row and changes no existing one. Nothing under `backend/modules/export` has a diff, so the external-copies reason key and its retained-by-policy report are unchanged.

There are no Critical or Major findings. The open Minor items are unchanged and non-blocking.
