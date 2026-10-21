## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-20T01:49:04Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 8.1 "Wording settled here" and the ExportConnection state machine amendment | The pending record is stored at revision 0 in an internal pending state. The entity definition (functional-design/entities.md, ExportConnection) fixes `revision` at min 1 and `state` at connected, disconnected, revoked or unavailable. The "wording settled here" table amends only the security design 4.1 wording and the functional spec state machine, so the migration's column constraints stay in conflict with the pending row. | Add the entity amendment to the settled-wording table: the `revision` minimum, the internal state value, and the holder and start-time columns. Say that none of them reach the wire contract. | New |
| R-02 | Major | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 8.1 rules table and state machine row "the holding check ends any other way" | The transition "holding check ends any other way, guard —, next state (none)" has no holder condition. After a takeover at 2 minutes, a stale check that later fails would delete the new holder's pending record and its pace record. The new holder's store would then write nothing even though its token was valid. Only the success path is guarded by "still pending and held by this check". | Make the delete conditional on the pending record still being held by this check, in the rule, the state machine guard and the matching repository test. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 8.1 "A second connect while a fresh pending record exists" | The answer uses "a code from configure's frozen list" and does not name it. A developer must guess between DEPENDENCY_UNAVAILABLE, a conflict code and others, and the frontend needs one fixed code to show "확인 중". | Name the exact code and add it to the integration test. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 2.5 and 3.1 (U3 and U4 frontend lanes holding `src/App.tsx` at 48%) | The U3 lane measured App.tsx at 48.62% against a 48 floor (frontend/vitest.u3-corpus.config.ts). That lane counts only U3's tests. U6's shell additions, the nav entry and the catalog capability, will probably push it under the floor. The design makes these lanes a merge gate but gives no way to keep them green. | Keep U6's App.tsx change minimal, by moving logic into `src/u6-export`. Also state that the shell test must be added in U3's and U4's test folders, and check both lanes locally before the pull request. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 4.4 (destructive archive) and 2.5 (`scripts/u6_preservation.py` as its own measured module) | The archive depends on the helpers of the tool's runner (manifest, resources, admin connection, the staging-file naming). The runner stays outside coverage and would import the module, so the dependency cycle and the staging-name pattern that identifies "leftover staging files" are not defined. | Say how the helpers reach the module (parameters or a shared helper) and where the staging-name pattern is defined. | New |
| R-06 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 4.2 row "Checks on inherited contributions" | The row says "for example" and names only `u3_host.py` and `local_http.py`. The built hosts check the exact U5 realm at several points (`backend/u3_host.py` lines 254 and 260, `transactions.py` owner and gate branches, `local_browser.py`). The list of places to change is open-ended. | Enumerate every realm-exact check that the U6 environment must admit, or require a test that asserts the list is complete. | New |
| R-07 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 3.2 and 4.3 grants (D13 database test) | The database test checks only that `docsuri_export` cannot select the two envelope columns and cannot execute the operator functions. It does not check INSERT or UPDATE on those columns. Only SELECT is tested. | Also assert no INSERT or UPDATE privilege on `sealed_token` and `token_key_version` for the runtime role. | New |
| R-08 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/infrastructure-design/cicd-pipeline.md > 2.6 timing | The whole U6 suite must fit one 300-second coverage pass, and the design says no tests can be repeated or split. No contingency is given if the suite outgrows it, and CI does not check that each layer holds at least one test. | Record what happens at overrun, for example a documented raise of the bound. Also add an operations check that every layer directory collects at least one test. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| sensor-traceability | PASS, no gaps, orphans or invalid entries | Every OK or N/A status is backed by the markdown. |
| sensor-upstream-coverage | PASS, nothing unreferenced | All three consumed artifacts are referenced. |

Repository claims checked against the files and found accurate:

- U5 workflow settings: actions, timeouts, filters and the environment variable.
- Path filters of U1 to U5 and U7.
- Root CI jobs.
- `fail_under` in `.coveragerc.u5`.
- U5 tool behaviour: archive checks, teardown, evidence files and the untracked `runtime` folder.
- The U2 keyring regression command: run here, 67 passed and 1 deselected.
- Base-install grants and role counts (10 owners, 11 with export).
- Unused ports 18099 and 15499.
- Release and CONVENTIONS statements.

### Summary

The pipeline design is accurate against the repository and keeps the token, the key and the evidence out of CI and every committed file. The destructive archive order matches security design 4.2 and 4.6. The two Major findings are both in the pending-connection amendment: it conflicts with the entity constraints, and the failure delete is unguarded against a stale holder. Both are fixable at the design level. With two Major findings, no Critical finding and the rest Minor, the artifact is implementable.
