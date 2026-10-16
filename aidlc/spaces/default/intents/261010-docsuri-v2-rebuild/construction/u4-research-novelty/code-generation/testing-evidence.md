# U4 implementation evidence

## Runner bootstrap (2026-10-16)

Before any test was written, `backend/.venv/bin/python -m pytest tests/u4_research_novelty -q`
exited 4 because the test directory did not exist. After the package skeleton
was created, the exact command exited 5 with zero collected tests in 0.08 seconds.
Neither invocation is passing-test evidence. The runner executed; test-after
implementation then proceeded by layer. Approved test instructions are unchanged.

## Layer checks to date

The owned U4 environment is `/tmp/docsuri-u4-run/environment.json`, database
`docsuri_u4`, realm `research-workspace`, local ports 15479 and 18079. Credentials
and private fixture contents are excluded from this record.

- Database: `env DOCSURI_U4_ENVIRONMENT_FILE=/tmp/docsuri-u4-run/environment.json backend/.venv/bin/python -m pytest tests/u4_research_novelty/database -q` — 7 passed.
- Repository: the corresponding `tests/u4_research_novelty/repository` command — 20 passed before subsequent receipt/pagination refinements; cumulative revalidation remains required.
- Component: the corresponding `tests/u4_research_novelty/component` command — 27 passed before six additional policy tests. The six policy tests and fourteen pure evidence/retrieval tests passed separately.
- Research production files, host and policy passed Ruff after formatting. Later edits still require final lint and coverage checks.

The first owned-environment setup failed its memory admission prerequisite.
No unrelated container or data was adopted. The runtime owner subsequently
provisioned an owned, bounded realm; database checks above used that realm.

This is an incremental implementation record, not a completed unit verification
report. Mounted integration, supervised worker/browser checks, coverage and
cumulative regression evidence must be recorded before completion.

## Cumulative verification and corrections

An earlier direct cumulative run was interrupted at the environment freeze after
48 passing tests (exit 2); it is not completion evidence. The old owned realm was
preserved and replaced with a fresh bounded realm, without resetting spent quota.

The sole bounded runner coverage phase on run `docsuri-u4-229e5c81fee863dc` passed
161 tests with zero failures, errors or skips and 87.28% line coverage. Every new
production file measured at least 82%. Evidence:
`/tmp/docsuri-u4-run/coverage-evidence-1792115403158519000.json`.
Its source digest was `eda7e3904ce453fc6457c0e6dcecfe990bbf27ed0843ca5c43eb4be7a4268b95`.

The first real browser run then failed before research acceptance: the C01
navigation omitted the installed research/novelty surfaces and the shell treated
degraded capabilities as absent. It reported one failure and five skipped journeys;
that is failed verification, not partial browser success. Backend navigation and
frontend degraded-state handling were corrected. A separate source check found
research missing from owner-store readiness, which was also corrected while
preserving the original eight-owner assemblies. Targeted checks and renewed
cumulative/browser evidence are required after these source changes.

After those corrections, the fresh realm `docsuri-u4-4f95cffd10ea8759` passed the
sole cumulative coverage phase: **164 tests, zero failures/errors/skips, 87.28%**
line coverage, every new production file at least 82%. It includes the three new
navigation/readiness regressions and the real denied-store/recovery check.
Evidence: `/tmp/docsuri-u4-run/coverage-evidence-1792115801495996000.json`;
log: `/tmp/docsuri-u4-run/u4-phase-coverage-1792115791674718000.log`.
The runtime confirmed no source drift during this phase. Browser verification
continues against the same owned realm without resetting accounts or usage.

The second browser run passed two journeys, then received `CONFLICT` when the UI
selected sources for a new turn after creating an empty-scope session. The initial
diagnosis incorrectly treated session scope as immutable for every future turn.
Canonical C07 and Functional Design W3 instead freeze each accepted turn's own
scope. The backend's unsupported full-scope equality was removed; current owner,
context and independent source eligibility checks remain. A real-store regression
passed proving different scopes on successive turns without changing the earlier
accepted snapshot or session default. Per-turn source selection is preserved.
This run remains failed browser verification; renewed coverage/browser checks
must include the correction.
The runtime's subsequent read-only budget check found member A with zero jobs,
one closed admission and one released reservation; member B had no work. Both
retained all four units without any quota reset. The corrected browser may reuse
this realm; backend coverage is unaffected by the UI-only correction.

The later browser attempt reached a real source-bound result but failed on a
same-document navigation link. Two jobs observed afterwards had
`SOURCE_INELIGIBLE`, zero claim attempts and revoked (not expired) originating
sessions. Read-only checks confirmed active verified accounts and matching
authority revisions. The worker denied access before payload/provider execution
and released reservations; empty-source generation was not the cause. The
novelty journey is being strengthened to await a terminal cancellation/completion
before logout cleanup, while the account-switch journey deliberately revokes its
originating session. Private text and identities are omitted from this evidence.

After the frontend corrections, 73 U4 component tests passed. New frontend source
coverage is 99.69% lines, 94.81% branches and 98.48% functions; the combined scope
including the inherited App is 80.01% lines. Retained frontend suites passed
18 U1, 92 U2 and 31 U3 tests. Strict TypeScript, scoped lint and the shared Vite
build passed. The runner's automatic preservation of prior browser reports also
passed eight focused tests; final cumulative verification includes that change.

Another fresh browser run failed during context/session creation before accepted
work. PostgreSQL recorded `too many connections for role docsuri_research` in
that interval. Normal and recovery pools each allowed two connections against
the same role's limit of two. This is a real shared admission defect, not a reason
to waive capacity limits or retry until green. Its correction and regression
evidence are required before final verification.

The shared transaction admission now enforces U4's per-owner physical limit of
two across normal/recovery pools and API/worker/observation/maintenance instances.
One normal slot preserves room for recovery; process budgets and SQL limits are
unchanged. Seven deterministic event-controlled transaction tests passed, proving
overlap never exceeds two, recovery progresses while normal work holds its slot,
timeouts are finite and exceptions release every gate. No database or accounts
were mutated by these tests. Retained U1/U2 runtime suites again passed 13/39.
One additional real PostgreSQL overlap regression passed in 0.20 seconds with
normal plus recovery operations, the unchanged role limit of two and third-worker
gating across transaction instances. It changed no account, job or usage state.

Review of the C07 router also found that session deletion omitted the operation
identity when delegating to its durable receipt. The router now forwards the
original identity; the mounted regression verifies identical replay and changed
intent conflict. Final cumulative checks must include this correction.

Before those corrections, the real supervised assembly test had independently
proved mounted acceptance → claim → payload → prepared result → one usage effect,
followed by a fresh assembly and unchanged read-only recovery. Canonical shared
contract checks passed 161 tests. Retained U1 and U2 shared-runtime regressions
passed 13 and 39 tests respectively. At the local verification cutoff, remote CI had not run.

## Final browser result

The corrected frozen source passed **all six real browser journeys**, zero
failures/errors/skips, in 10.54 seconds. These exercise actual C04/C07, the
supervised worker, source-bound result and read-only recovery, terminal novelty
cancellation/completion, owner-switch isolation and responsive keyboard controls.
Evidence: `/tmp/docsuri-u4-run/browser-evidence-1792117515025370000.json` and
the run's `browser.xml`. Earlier failures above remain part of the repair record.

## Final cumulative backend result

After all corrections, the single fresh-realm cumulative coverage run passed
**181 tests**, zero failures/errors/skips, **87.66%** line coverage. Every measured
authored file is at least 82%, above the unchanged 80% floor. It includes all
database/repository/component/runtime/integration/operations cases, the deletion
receipt replay and eight owner-capacity regressions.

Evidence: `/tmp/docsuri-u4-run/coverage-evidence-1792117581494612000.json`;
log: `/tmp/docsuri-u4-run/u4-phase-coverage-1792117570746135000.log`.
This run and the successful six-case browser run share frozen source SHA-256
`c171d721ffd83b8636511925e5c747f2fafd14fed47d0b778d5ec8611423e26a`.
Both successful runs used the same owned realm, `docsuri-u4-62afa0fbd17a0584`:
browser first, then cumulative backend coverage, without quota resets or weakening
capacity/admission/coverage rules. Earlier failed-run realms were preserved and
replaced; they are distinct from this final shared-realm pair. At the local verification cutoff, remote CI had not run; it and the separately
approved construction completion command remain subsequent obligations.

Final evidence file SHA-256 values, independently reported by the runtime owner:

- Browser: `c3df845de49f27db9eaf94eb609f8e490842b25d30c8f19af44e37256085abcc`.
- Coverage: `40462f4ed1640b8f6459bbfe80794ace2367487e185a3ec2dcc29b8287e81969`.

## Review-iteration repairs — superseding local evidence

The results above describe the pre-review implementation. Review iteration 1
found five issues; `review-repairs.md` records their fixes and the intervening
failed checks without replacing the independent verdict.

Final repaired source at commit `3f9b4fe5` passed **191 backend tests**, zero
failures/errors/skips, **88.22%** line coverage, with every measured authored file
at least 82%. Its **six real browser journeys** also passed with zero failures,
errors or skips, including the new two-view tombstone/result-clearing check.
The frontend passed **74 tests**, root and U4 TypeScript checks, scoped lint and
Vite build; new source line coverage is 99.70% and combined inherited App coverage
is 80.03%. Coverage thresholds and resource limits remain unchanged.

Both final repaired runs used the same realm `docsuri-u4-6242203c924051fe`, in the
order browser → cumulative coverage, and the same source SHA-256
`263138dac917df184b469b9886e694fe0ce28f6d0970f0185c50aa4665cae8fa`.
Earlier failed-run realms were preserved, not reset or silently reused.

| Evidence | Result | File SHA-256 |
|---|---|---|
| `/tmp/docsuri-u4-run/browser-evidence-1792119106660405000.json` | 6 passed; supervised 11.2136 s; peak RSS 1,020,248,064 bytes | `8659f7b6d3308874795b119bf5eda654ce64ec8a16ab14cd298afddca3ee35bf` |
| `/tmp/docsuri-u4-run/coverage-evidence-1792119129859501000.json` | 191 passed; supervised 11.2948 s; peak RSS 207,994,880 bytes | `6dc411f0ac54fe355e5075b6faca16d9190a52bcf2a8c599814ff2738d70e4b1` |

Remote CI run 38842485487 subsequently passed backend/shared/frontend but failed
the browser RSS guard at 1,078,366,208 bytes, with no test report and a stopped
process. The browser allocation correction and its actual results follow.

## Final allocation repair and remote result

Historical `/tmp/docsuri-u4-run` paths above record their original locations.
Preservation moved the successful pre-review 62afa realm's files to
`/private/tmp/docsuri-u4-preserved-docsuri-u4-62afa0fbd17a0584-5deea9fe`
and the first repaired 4195 realm's files to
`/private/tmp/docsuri-u4-preserved-docsuri-u4-4195e6320c8873f7-526af6ff`.
The 6242 realm's evidence remains in `/tmp/docsuri-u4-run`; its previous browser
XML/report directories were preserved in place before the later browser rerun.

At `83f6aa262e568eee2591f24418eda1ffe275518e`, browser-only Node and renderer V8
allocations were bounded without changing the 1 GiB process-tree RSS guard,
300-second deadline or six journeys. All 78 operations tests passed.
The final local browser run passed six tests, zero failures/errors/skips, in
10.4965 supervised seconds, peak RSS 928,759,808 bytes. It safely reused the
6242 realm after a read-only remaining-allocation check; no quota was reset,
and previous reports were preserved.

- Evidence: `/tmp/docsuri-u4-run/browser-evidence-1792119445909347000.json`.
- Evidence SHA-256: `2c0ac9c033f760f29984f1570ea8fb72d4947117ca5810a2b802da61d635b4c3`.
- Source SHA-256: `f7e5fe9c8fbda21938deb339944d9aba9abcf51bfe1a9f46b1e6089fde5cf442`.

The local 191-test/88.22% result remains tied to `3f9b4fe5`; it is not relabelled
as verification of these changed runtime bytes. Final-source cumulative evidence
comes from successful
[U4 CI run 38843024805](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805),
at exact commit `83f6aa262e568eee2591f24418eda1ffe275518e`:

| Job | Actual result | Supervised time | Peak RSS |
|---|---|---|---|
| Backend `116787190203` | 193 passed; zero failures/errors/skips; unchanged 80% coverage gate passed | 18.029 s | 198,246,400 bytes |
| Browser `116787414888` | 6 passed; zero failures/errors/skips; 49 migrations; clean stops | 13.508 s | 1,012,883,456 bytes |

Shared-contract and frontend jobs also passed. The exact remote coverage
percentage is not exposed in the public summary; no percentage is inferred.
The parent-owned maintenance CI report records broader legacy-workflow outcomes
separately. Conditional capability gaps and completion-command approval remain.
