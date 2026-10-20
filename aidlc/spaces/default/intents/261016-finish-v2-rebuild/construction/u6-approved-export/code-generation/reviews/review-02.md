## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-20T12:43:53Z
**Iteration:** 2

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | backend/modules/export/lane.py > `_unsent_outcome` and `_send` (code-summary.md deviation 12) | When the stored token cannot be opened after the claim, the attempt is recorded as `refused` and the effect ends `failed` (`connection-changed` or `policy-unresolved`). Before the claim, the same condition is could-not-check, and the effect waits up to 24 h. A momentary key-protection fault after the claim, such as the 5 s key-lock wait running out, therefore ends the owner's accepted export for good. The owner has to prepare and approve again. Nothing is sent, so this is safe, but it is inconsistent with BR1.6 and with the claim guard's `connection-unavailable` handling. | Either record a post-claim `policy-unresolved` as a resumable could-not-check, or keep the failure and record it as an owner-visible decision at the checkpoint, together with the retry cost. | Unresolved |
| R-02 | Minor | backend/u3_host.py > `_contribution_gates` (topics branch) | The topics gate now admits the U6 realm triple for a topics-only composition with no export factory. The code comment says U6 reaches the topics gate through `assemble_u5`, but a direct `assemble_u3(topics_factory=..., research_factory=...)` in the U6 realm also passes. The only strict gate is the export one. This loosens U5's "exact owned realm" rule. | Tighten the topics branch so the U6 triple is accepted only when `export` is set, or add a test that pins and justifies the looser behaviour. | Unresolved |
| R-03 | Minor | .github/workflows/u6-approved-export.yml > `on.pull_request.paths` | U6 changes `frontend/types/wire/dtos.ts`, and the U6 `tsc` and Vitest lanes depend on it, but the path filter lists neither `frontend/types/**` nor `frontend/vitest*.ts`. A change that touches only those files skips the lane that checks them. `shared/**` covers regeneration but not a hand edit of the generated file. | Add `frontend/types/**` and `frontend/tsconfig*.json` to the path filters. | Unresolved |
| R-04 | Minor | backend/modules/export/rendering.py:27 (`import rfc8785`) and backend/pyproject.toml | The module imports `rfc8785` directly, but the backend declares it only transitively through `docsuri-ops`. It is present in `uv.lock` and in the venv, so nothing breaks today. The binding hash, which approval depends on, rests on an undeclared direct dependency. code-summary.md already records this as open. | Declare `rfc8785>=0.1.4,<1` in backend/pyproject.toml and refresh uv.lock. | Unresolved |
| R-05 | Minor | frontend/src/u6-export/connect-form.tsx > token input (`type="text"`) | The plan chose "not a password field" so password managers stay out. The side effect is that the Notion integration token shows in clear text on screen while it is typed or pasted. The value is cleared on submit and never stored, so this is only screen-exposure risk. | Mask the display without making it a password field, for example with `-webkit-text-security` or a reveal toggle that defaults to hidden. Keep `autocomplete="off"`. | Unresolved |

> R-01 Reviewer note: A post-claim failure to open the token still ends the effect as `failed`, unchanged. Nothing is sent, so it is safe.

> R-02 Reviewer note: The topics branch of `_contribution_gates` in backend/u3_host.py is unchanged and still admits the U6 realm triple without an export factory.

> R-03 Reviewer note: The workflow path filter still omits `frontend/types/**` and `frontend/tsconfig*.json`. The lanes that depend on them are at workflow lines 77-87.

> R-04 Reviewer note: backend/pyproject.toml still has no `rfc8785` entry. The module imports it directly.

> R-05 Reviewer note: The token input in frontend/src/u6-export/connect-form.tsx:138 is still `type="text"` with no display mask.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| sensor-traceability | pass, 0 gaps, 0 orphans, 0 invalid | Traceability is intact after the Step 27 change. |
| ruff on verify_docsuri_u4.py, test_archive_expiry.py and test_runner_transport.py | All checks passed | No lint defects in the changed U4 files. |
| source-manifest vs `git status --porcelain --untracked-files=all` | 190 paths, none unmanifested, none claimed but unchanged | The manifest matches the workspace. |
| `git diff scripts/verify_docsuri_u4.py` | Matches the claim | `manifest()` is unchanged except that its identity check moved into `require_manifest_identity()`. `archive_owned` now calls `preservation_manifest()`. Every later check remains, including resources, stopped state, lsof, client count, custody, and the database identity check. It deletes nothing and never changes the expiry. |
| pytest suites | Not run, as instructed | I read the 20 new U4 tests. They cover the expired-but-owned happy path with byte-identical preservation and an unchanged expiry. They also cover 17 tamper, foreign and busy defects that must never stop or move the realm, and a foreign unit's valid expired manifest being refused. |

### Summary

The U4 change is sound. The expired-realm path reuses U5's `LocalProfile.preservation_identity`, adds U4's own unit, realm, database and path binding, and keeps every ownership and idleness check. It renews nothing and cannot yield a runtime profile. No new defect found; the five open Minor findings are unchanged and do not block.
