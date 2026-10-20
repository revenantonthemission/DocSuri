## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-20T12:27:21Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | backend/modules/export/lane.py > `_unsent_outcome` and `_send` (code-summary.md deviation 12) | When the stored token cannot be opened after the claim, the attempt is recorded as `refused` and the effect ends `failed` (`connection-changed` or `policy-unresolved`). Before the claim, the same condition is could-not-check, and the effect waits up to 24 h. A momentary key-protection fault after the claim, such as the 5 s key-lock wait running out, therefore ends the owner's accepted export for good. The owner has to prepare and approve again. Nothing is sent, so this is safe, but it is inconsistent with BR1.6 and with the claim guard's `connection-unavailable` handling. | Either record a post-claim `policy-unresolved` as a resumable could-not-check, or keep the failure and record it as an owner-visible decision at the checkpoint, together with the retry cost. | New |
| R-02 | Minor | backend/u3_host.py > `_contribution_gates` (topics branch) | The topics gate now admits the U6 realm triple for a topics-only composition with no export factory. The code comment says U6 reaches the topics gate through `assemble_u5`, but a direct `assemble_u3(topics_factory=..., research_factory=...)` in the U6 realm also passes. The only strict gate is the export one. This loosens U5's "exact owned realm" rule. | Tighten the topics branch so the U6 triple is accepted only when `export` is set, or add a test that pins and justifies the looser behaviour. | New |
| R-03 | Minor | .github/workflows/u6-approved-export.yml > `on.pull_request.paths` | U6 changes `frontend/types/wire/dtos.ts`, and the U6 `tsc` and Vitest lanes depend on it, but the path filter lists neither `frontend/types/**` nor `frontend/vitest*.ts`. A change that touches only those files skips the lane that checks them. `shared/**` covers regeneration but not a hand edit of the generated file. | Add `frontend/types/**` and `frontend/tsconfig*.json` to the path filters. | New |
| R-04 | Minor | backend/modules/export/rendering.py:27 (`import rfc8785`) and backend/pyproject.toml | The module imports `rfc8785` directly, but the backend declares it only transitively through `docsuri-ops`. It is present in `uv.lock` and in the venv, so nothing breaks today. The binding hash, which approval depends on, rests on an undeclared direct dependency. code-summary.md already records this as open. | Declare `rfc8785>=0.1.4,<1` in backend/pyproject.toml and refresh uv.lock. | New |
| R-05 | Minor | frontend/src/u6-export/connect-form.tsx > token input (`type="text"`) | The plan chose "not a password field" so password managers stay out. The side effect is that the Notion integration token shows in clear text on screen while it is typed or pasted. The value is cleared on submit and never stored, so this is only screen-exposure risk. | Mask the display without making it a password field, for example with `-webkit-text-security` or a reveal toggle that defaults to hidden. Keep `autocomplete="off"`. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| aidlc engine sensor-traceability | PASS: gaps, orphans and invalid entries all empty | Traceability is complete. |
| Manifest check: `source-manifest.json` against `git status --porcelain --untracked-files=all` (ignoring `.claude/`, `aidlc/`, `.458a0cbf845a6699-00000000.bun-build`) | Match: 187 paths, no unlisted application path, no unrelated claimed path | The manifest is accurate. |
| ruff on the CI target list (`backend/modules/export`, `backend/u6_*.py`, `key_custody.py`, `control_keys.py` and the other U6-touched files) | No finding in any U6-owned file. The 33 findings are in U2 files (`control_lifecycle.py` 30, `local_http.py` 2, `guarded_entry.py` 1) and are already recorded as pre-existing debt. | Acceptable. The finding count depends on which ruff config is used; CI results are recorded in the verification log. |
| ruff with `tests/ruff.toml` on `tests/u6_approved_export` | PASS | Clean. |
| vitest U6 lane (`vitest.u6-export.config.ts`) | 109 passed, 11 files | Matches the summary. |
| Shared contract suite (shared/python) | 205 passed | Matches the summary. |
| U2 keyring regression (cicd §2.4) | 67 passed, 1 deselected | The extraction into `key_custody.py` leaves U2 behaviour unchanged. |
| Diff of the C09 amendments (`workspace.schema.json`, `execution.schema.json`, contract-summary.md) | Additive except two documented changes: `ExportDestinations.destinations` and `ExportPreview.destination` move to the superset `ExportDestinationEntry`, and `ExportConnectionReadHttp.connectionId` becomes optional. | Both are recorded in the contract text as the named exceptions. |

### Summary

I found no Critical or Major defects. I traced the token path, the write lane, the compare-and-set guards and the lifecycle participant end to end and they hold. The token is sealed with AAD bound to account, connection and revision. Custody faults are raised with no cause or context. No transaction is held across a Notion call. Claim and attempt are one atomic compare-and-set. An unknown outcome is never rewritten, and orphans are swept into scanning. The five Minor findings are a post-claim token-open failure treated as terminal, a loosened topics gate, CI path filters, an undeclared direct dependency, and a token field shown in clear text. The Step 27 "Earlier units" task stays open only because U4's local coverage run is blocked by an expired U4 environment. The summary records this openly, and the U4 workflow on the pull request remains the merge gate.
