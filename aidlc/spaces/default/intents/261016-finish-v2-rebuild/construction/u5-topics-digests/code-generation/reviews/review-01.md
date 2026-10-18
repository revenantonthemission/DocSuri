## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-18T06:44:08Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u5-topics-digests/code-generation/unit-test-instructions.md > "Exact unit-scoped commands" (the collect-only command; the same command is claimed to collect cleanly in code-generation-plan.md Step 2) | The recorded collect-only command is not scoped to this unit when run from the repository root as the file directs. `backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q` resolves the config's `testpaths = ../tests/u5_topics_digests` above the workspace root, so the scope silently falls through to the whole workspace: I measured 2,161 tests collected with 111 collection errors (import failures in modules/discovery and backend/tests suites), and without a `--collect-only` flag appended the command would execute that entire set. Adding the explicit path (`... --collect-only tests/u5_topics_digests`) collects exactly the unit's 50 tests cleanly. The unit's own runner passes the explicit path, so the recorded phase evidence stands; the standalone command a later stage runs as written does not. | Add the explicit `tests/u5_topics_digests` path (or an equivalent exact unit filter) to the recorded collect-only command, re-run it from the repository root to confirm the 50 unit tests collect cleanly, and align plan Step 2's wording with the verified command. | New |
| R-02 | Minor | aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u5-topics-digests/code-generation/code-generation-plan.md > Step 12 | The plan promises mounted browser journeys "(follow → settings → unsubscribe; resolve control; empty digest state)", but the shipped suite (frontend/e2e/u5-topics-digests/journey.spec.ts) runs follow → settings → unsubscribe, follow → scheduler → local-sink delivery, and the resolve control; the empty-digest journey is absent and the substitution (delivery journey instead) is not recorded among the code summary's deviations. | Either add the empty-digest journey or record the substitution in code-summary.md's deviations with its rationale. | New |
| R-03 | Minor | backend/modules/corpus/u5_digest_read.sql > header comment | The comment states "Every candidate is re-checked through corpus.guard_version at selection time", but no U5 code path calls corpus.guard_version — selection filters `v.eligible` / `v.purpose` / `p.withdrawn` directly under the unit's serializable transactions, and the grant to docsuri_topics is unused. The eligibility guarantee holds, but the stated mechanism is not the shipped one. | Correct the comment to describe the actual mechanism, or call corpus.guard_version at selection so the comment is true. | New |
| R-04 | Minor | backend/modules/topics/preparation.py > module docstring (also the DigestSettings note in the unit's entities.md and the inherited note in frontend/src/u5-topics/digest-settings.tsx) | The docstring says "Language/level are read from the account's preferences at preparation time", but no code reads any account preference: the digest email renders fixed Korean, no preference store exists in the accounts schema, the capability row declares languageIds ["ko"] and levelIds [], and the settings form tells users their language/difficulty follows account preferences. The stated inheritance is not implemented anywhere. | Either implement the preference read, or record in code-summary.md's known limits that language/level inheritance is display-only under the current single-language product and correct the docstring. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| pytest collect-only, recorded command, repository root | FAIL: 2,161 collected, 111 errors | Confirms the Major finding: the recorded command silently widens to the whole workspace instead of this unit's tests. |
| pytest collect-only with explicit `tests/u5_topics_digests` | PASS: 50 collected | The unit's tests exist and collect cleanly; matches the claimed phase total (10+9+11+5+15). |
| pytest collect-only per phase directory | PASS: database 10 / repository 9 / component 11 / integration 5 / operations 15 | Every claimed phase count reproduces exactly. |
| vitest run --config vitest.u5-topics.config.ts | PASS: 14 tests | Matches the claimed frontend count and the 14 test names in the suite. |
| Stateful realm phases (setup/migrate/fixtures/database…browser/coverage) | NOT RE-RUN | Each stateful pass consumes finite fixture capacity, so their claimed counts/results were verified through collection, code and test inspection instead of re-execution; the runner's fail-closed zero-skip enforcement and evidence capture were read and match the claims. |
| Engine sensors (required-sections, traceability) | PASS (ran on current bytes) | Re-checked independently: all 57 source-manifest paths exist, every traceability OK target resolves to a real file, and no claimed path looks unrelated to this unit. |

### Summary

The unit's implementation, evidence and honesty claims hold up under spot-checking: all 57 manifest paths exist, every claimed test count reproduces (50 backend, 14 frontend), no send claims `pathKind: real`, the runner is fail-closed with zero-skip enforcement, and the rules (single-flight, unreconciled-unknown pause, chronological windows, unsubscribe/consent, owner isolation, lifecycle participation) are enforced in code and exercised by named tests. The one concern worth acting on before handoff is the recorded collect-only command, which silently runs against the whole repository; the other three findings are documentation/claim drifts the person may want corrected at the gate.
