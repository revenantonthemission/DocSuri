## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-20T16:19:45Z
**Iteration:** 3

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | backend/modules/export/lane.py > `_unsent_outcome` and `_send` (code-summary.md deviation 12) | When the stored token cannot be opened after the claim, the attempt is recorded as `refused` and the effect ends `failed` (`connection-changed` or `policy-unresolved`). Before the claim, the same condition is could-not-check, and the effect waits up to 24 h. A momentary key-protection fault after the claim, such as the 5 s key-lock wait running out, therefore ends the owner's accepted export for good. The owner has to prepare and approve again. Nothing is sent, so this is safe, but it is inconsistent with BR1.6 and with the claim guard's `connection-unavailable` handling. | Either record a post-claim `policy-unresolved` as a resumable could-not-check, or keep the failure and record it as an owner-visible decision at the checkpoint, together with the retry cost. | Unresolved |
| R-02 | Minor | backend/u3_host.py > `_contribution_gates` (topics branch) | The topics gate now admits the U6 realm triple for a topics-only composition with no export factory. The code comment says U6 reaches the topics gate through `assemble_u5`, but a direct `assemble_u3(topics_factory=..., research_factory=...)` in the U6 realm also passes. The only strict gate is the export one. This loosens U5's "exact owned realm" rule. | Tighten the topics branch so the U6 triple is accepted only when `export` is set, or add a test that pins and justifies the looser behaviour. | Unresolved |
| R-03 | Minor | .github/workflows/u6-approved-export.yml > `on.pull_request.paths` | U6 changes `frontend/types/wire/dtos.ts`, and the U6 `tsc` and Vitest lanes depend on it, but the path filter lists neither `frontend/types/**` nor `frontend/vitest*.ts`. A change that touches only those files skips the lane that checks them. `shared/**` covers regeneration but not a hand edit of the generated file. | Add `frontend/types/**` and `frontend/tsconfig*.json` to the path filters. | Unresolved |
| R-04 | Minor | backend/modules/export/rendering.py:27 (`import rfc8785`) and backend/pyproject.toml | The module imports `rfc8785` directly, but the backend declares it only transitively through `docsuri-ops`. It is present in `uv.lock` and in the venv, so nothing breaks today. The binding hash, which approval depends on, rests on an undeclared direct dependency. code-summary.md already records this as open. | Declare `rfc8785>=0.1.4,<1` in backend/pyproject.toml and refresh uv.lock. | Unresolved |
| R-05 | Minor | frontend/src/u6-export/connect-form.tsx > token input (`type="text"`) | The plan chose "not a password field" so password managers stay out. The side effect is that the Notion integration token shows in clear text on screen while it is typed or pasted. The value is cleared on submit and never stored, so this is only screen-exposure risk. | Mask the display without making it a password field, for example with `-webkit-text-security` or a reveal toggle that defaults to hidden. Keep `autocomplete="off"`. | Unresolved |
| R-06 | Minor | frontend/src/u6-export/dialogs.tsx > `DialogShell` `onKeyDown` | The new handler calls `preventDefault()` and moves focus on every Tab keydown, including Tab with Ctrl, Alt or Meta held. Those chords are not dialog navigation (assistive-technology and browser shortcuts use some of them), and the handler now swallows them. The new tests cover plain Tab and Shift+Tab, a Tab after focus fell to the body, and a refocus after the page moved focus. None presses an arrow key inside the radio group and then Tab, which is the case the checked-radio stop rule exists for. | Return early from `onKeyDown` when `event.ctrlKey`, `event.altKey` or `event.metaKey` is set. Add one test that moves between the two settle radios with an arrow key and then presses Tab and Shift+Tab. | New |

> R-01 Reviewer note: backend/modules/export/lane.py is unchanged by this iteration. A post-claim token-open failure still ends the effect `failed`, and the retry cost is still not recorded as an owner-visible decision.

> R-02 Reviewer note: backend/u3_host.py is unchanged in this respect. The topics branch still admits the U6 realm triple without requiring `export`.

> R-03 Reviewer note: The workflow's `paths` still list `frontend/src/**`, `frontend/*u6*`, the U6 e2e and test folders, `package.json` and the lockfile. They still omit `frontend/types/**` and `frontend/tsconfig*.json`.

> R-04 Reviewer note: backend/pyproject.toml still has no `rfc8785` entry (grep returned nothing), while rendering.py imports it directly.

> R-05 Reviewer note: frontend/src/u6-export/connect-form.tsx:138 still has `type="text"` on the token input.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `tsc --project tsconfig.u6-export.json --noEmit` | PASS (no output) | The U6 type lane is clean with the dialog and jobs changes. |
| U6 Vitest lane (`vitest.u6-export.config.ts`) | PASS: 11 files, 113 tests | This includes the 8 dialog tests. The count matches log section 11.6. |
| U4 Vitest lane (`vitest.u4-research.config.ts`) | PASS: 9 files, 83 tests | The `aria-disabled` change in jobs.tsx does not break U4's own tests. The `value` without `onChange` warning on stderr predates this work and comes from a U4 test. |
| U6 ESLint command (no `--fix`, no cache) | PASS (no output) | No lint or accessibility-lint errors. |
| Manifest versus `git status --porcelain --untracked-files=all` (ignoring `.claude/`, `aidlc/` and the bun-build file) | 191 changed paths, 191 manifest paths, no difference either way | There are no unmanifested application changes. jobs.tsx is listed, and every path belongs to the Unit or to its declared U4/U3 integration points. |

### Review of the two changes

**Deviation 38: jobs.tsx and keyboard.spec.ts**

- The `aria-disabled` swap is sound. Both handlers return early while unavailable (`refreshUnavailable`, `openUnavailable`), so an "unavailable" press cannot start a second read. A pressed button now keeps focus. `button[aria-disabled='true']` is already styled in workspace.css:162, so the visual state is unchanged.
- The e2e change only adds waits for the opened result region and the export entry, plus `expect(open).toBeFocused()`. `tabTo`, its 40-step bound and every timeout are unchanged, and no sleep was added.

**Deviation 39: DialogShell**

- Stop computation is correct. A radio group collapses to its checked radio, or to its first radio while none is checked. `onStop` matches any radio of the same group, so an arrow key inside the group does not lose the position.
- Wraparound is correct both ways: `(current + step) % length` with `step = length - 1` for Shift+Tab, a single stop stays put, and a position that is not a stop goes to the first stop (Tab) or the last (Shift+Tab). Zero stops fall through to the browser.
- The document `focusin` listener returns outside focus to the last element focused inside. When that element is gone or no longer matches `FOCUSABLE`, for example a button that became disabled, it goes to the first stop. This also covers the focus-dropped-to-body case, where the next Tab lands outside and is pulled back.
- The listener is removed in the effect cleanup before the opener's `focus()` runs, so focus can return to the opener. The existing Escape test pins that return.
- WCAG 2.1.2 holds: Escape closes the dialog, and the trap is the intended modal one. 2.4.3 holds: focus order is document order over the dialog's own stops.
- Both dialogs use the shell and no markup or ARIA changed.
- The cause analysis in log section 11.3 says plainly that the exact browser trigger was not pinned and that the fix does not depend on it. That is honest. The claim the tests make is also honest: four tests fail on the old trap and pass on the fix (`4 failed | 4 passed`).

### Summary

Both fixes are correct and bounded. The three lanes pass, the manifest matches the working tree, and the verification log is candid about what it pinned and what it did not. The five open Minor findings are unchanged, and I raised one new Minor on modifier-key Tabs and an untested arrow-key path. No Critical or Major finding stands, so this is READY.
