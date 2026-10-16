# U4 review iteration 1 — repair record

The independent verdict remains in `reviews/review-01.md`. This document records
repairs for a new review; it does not overwrite that verdict or certify readiness.

| Finding | Repair | Verification |
|---|---|---|
| R-01 | Append-only migration adds a durable unreconciled-release obligation to closed admissions. The worker discovers no-job closures, replays the same usage proof without the browser session and acknowledges only after release. Closed retries still cannot accept work. | Real-store fault schedules passed for failure before release, lost release acknowledgement, lost closure acknowledgement, restart/revocation, one accounting effect and late-acceptance refusal, in the final 191-test cumulative run. |
| R-02 | Server rejects manuscript mode under the current unresolved private-attachment policy before admission/reservation, including an empty attachment scope. | Mounted direct HTTP requests for empty and ineligible attachments, with unchanged admission count, passed in the final cumulative run. |
| R-03 | Structural fixture schema typing permits inferred optional properties and explicitly rejects an undefined property schema when present, without weakening either compiler configuration. | Root frontend TypeScript and U4 TypeScript pass; 74 U4 tests pass. |
| R-04 | Tombstoned context/session reads return NOT_FOUND, while revision conflicts remain distinct. A late artifact response cannot overwrite a newer refresh. | Frontend NOT_FOUND test clears result and novelty discussion source; the real two-view delete/refresh journey passed in the final six-case browser run. |
| R-05 | Corrected the previous final evidence description: browser and coverage both used realm docsuri-u4-62afa0fbd17a0584, in that order. | Exact recorded identities checked by the reviewer; earlier preserved realms are described separately. |

## Integration and CI corrections

- The runner prints only safe failure classifications, report/source flags and
  bounded supervision metrics. Raw logs, commands, credentials and private text
  remain private. Five diagnostic tests pass, including RSS/log/deadline failures.
- Setup now waits for the authenticated loopback TCP endpoint used by migrations
  and verifies `current_database()`. It preserves the previous 30-attempt/105-second
  bound. Three focused tests pass. A socket-ready temporary bootstrap server is
  no longer sufficient evidence; the historical CI failure cause is not inferred
  beyond its observed connection closure.
- The U3 observation test now asserts its original eight installed owners rather
  than every registered optional probe. U4's explicit nine-owner checks remain.
- The Python consumer inventory was regenerated with its existing generator and
  its drift check passes. No inventory tool or contract validation was weakened.

The U2 coverage workflow's global-source denominator and pre-existing below-floor
baseline remain explicit CI issues; this repair does not lower any threshold.
U4 still requires its own unchanged 80% floor and truthful conditional parity gaps.

## Current verification cutoff

Frontend: 74 tests, 99.70% new-source lines, 94.59% branches, 98.48% functions;
combined inherited App scope 80.03% lines. Root/U4 typechecks, scoped lint and Vite
build pass. Backend focused diagnostics/readiness tests: eight passed; repaired
backend paths pass Ruff. Final repaired-source browser and backend evidence is
recorded below; it supersedes the earlier c171d721 source digest.

The fresh owned verification realm is docsuri-u4-4195e6320c8873f7 with 49 immutable
migration records. Its setup passed the new authenticated TCP readiness check;
the runtime owner reported two fixture accounts, two papers and zero accepted
jobs before verification. No existing accounts, reservations or spent quota were
reset.

The first repaired-source browser run passed all six cases, including two-view
deletion and refresh. The subsequent cumulative run stopped with 122 passes and
one failure: an existing mocked setup test had not intercepted the newly required
TCP readiness boundary. Its replacement now asserts readiness occurs before
migration and that a preserved realm is not reseeded. All 76 operations tests
pass. The first sandbox-only attempt had three process-observation permission
failures; the approved run with `ps` access passed all 76, without database use.
The refreshed frozen-source browser and cumulative evidence after this correction
is recorded below.

## Final repaired-source local result

Commit `3f9b4fe5` passed all six browser journeys and all 191 cumulative backend
tests, with zero failures/errors/skips. Backend line coverage is 88.22%; every
measured authored file is at least 82%. Both runs share source SHA-256
`263138dac917df184b469b9886e694fe0ce28f6d0970f0185c50aa4665cae8fa`
and realm `docsuri-u4-6242203c924051fe`, browser first then coverage.

- Browser evidence: `/tmp/docsuri-u4-run/browser-evidence-1792119106660405000.json`;
  SHA-256 `8659f7b6d3308874795b119bf5eda654ce64ec8a16ab14cd298afddca3ee35bf`.
- Coverage evidence: `/tmp/docsuri-u4-run/coverage-evidence-1792119129859501000.json`;
  SHA-256 `6dc411f0ac54fe355e5075b6faca16d9190a52bcf2a8c599814ff2738d70e4b1`.

Remote CI run 38842485487 passed backend/shared/frontend but its browser phase
failed the unchanged 1 GiB RSS bound at 1,078,366,208 bytes after 4.069 seconds.
No test report was produced; the supervisor stopped the process. This actual CI
result supersedes the earlier pending status and does not invalidate the recorded
local passes. It requires a repaired-source verification run.

## Browser allocation repair

The installed Playwright shim already executes Node directly; no redundant pnpm
or corepack browser wrapper was found. Browser coordinator/worker and renderer
V8 allocations are now bounded at 128 MiB old space and 8 MiB semi-space. An
actual Node/child probe showed that old-space alone still allowed a 320 MiB total
heap locally; the additional semi-space bound reduces the measured heap limit
to the tested 128–176 MiB range. These are allocation limits, not an alternative
RSS measurement. The same full process-tree 1 GiB RSS guard, 300-second deadline,
browser version, rendering behavior and six journeys remain.

The options and their garbage-collection tradeoff are documented in the
[Node command-line reference](https://nodejs.org/api/cli.html#--max-old-space-sizesize-in-mib).
All 78 operations tests, including the real Node/child allocation probe, passed;
Ruff, TypeScript and Playwright-config lint passed. Actual local and remote browser
fit initially remained pending for this allocation change. Conditional parity gaps and the
separately approved completion-command requirement remain unchanged.

At commit `83f6aa26`, the final local browser rerun passed all six cases with
zero failures/errors/skips, in 10.4965 supervised seconds and peak RSS
928,759,808 bytes. It reused the owned 6242 realm only after a read-only check
confirmed exactly the needed three remaining allocations; no quota was reset.
The prior XML/report directory was automatically preserved.

Evidence: `/tmp/docsuri-u4-run/browser-evidence-1792119445909347000.json`, SHA-256
`2c0ac9c033f760f29984f1570ea8fb72d4947117ca5810a2b802da61d635b4c3`;
source SHA-256 `f7e5fe9c8fbda21938deb339944d9aba9abcf51bfe1a9f46b1e6089fde5cf442`.
The earlier 191-test local coverage result remains tied to 3f9b4fe5/source263138;
it is not relabelled as a final-source full run. Changed runtime behavior passed
78 operations tests.

## Final remote verification

[U4 CI run 38843024805](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805)
succeeded at exact commit `83f6aa262e568eee2591f24418eda1ffe275518e`.
Backend job `116787190203` passed 193 tests, zero failures/errors/skips, in
18.029 supervised seconds with peak RSS 198,246,400 bytes. The unchanged 80%
coverage gate passed; the exact remote percentage is not exposed in the public
summary and is not inferred from the earlier local 88.22% result.
Browser job `116787414888` passed all six journeys, zero failures/errors/skips,
in 13.508 supervised seconds with peak RSS 1,012,883,456 bytes, 49 migrations
and clean stops. Shared-contract and frontend jobs passed. The 1 GiB process-tree
RSS guard, 300-second deadline, coverage threshold and complete journey scope
were retained. This establishes readiness for independent review iteration 2;
it does not replace that review or the separately approved completion command.
