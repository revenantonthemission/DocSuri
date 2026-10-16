# U4 CI integration evidence

Repository: `revenantonthemission/DocSuri` (the configured `origin`), public.
PR: [#51](https://github.com/revenantonthemission/DocSuri/pull/51), targeting `develop`.
Integration follows CONVENTIONS.md; no release promotion or deployment is implied.

## Initial remote verification

Commit `6e6c05f5` produced 16 passing, 16 failing, four cancelled and three skipped
checks. A failed or cancelled check is not passing evidence.

- [U4 run 38841058509](https://github.com/revenantonthemission/DocSuri/actions/runs/38841058509): shared contracts, frontend and backend passed. Backend executed 181 tests. Browser setup and all 48 migrations succeeded, but the browser phase failed in 6.87 seconds without usable JUnit counts. Its private diagnostics were not uploaded, so this run alone does not establish the cause.
- [Whole-frontend job](https://github.com/revenantonthemission/DocSuri/actions/runs/38841058336/job/116780988197): new TS2352 in `frontend/test/u4-research-novelty/fixtures.ts:137`. The narrower U4 typecheck did not catch this regression.
- [U3 run 38841058224](https://github.com/revenantonthemission/DocSuri/actions/runs/38841058224): operations stopped at six tests with one failure. Source inspection establishes a new mismatch: the test expects every `PROBES` key, while the default observation set intentionally remains the original eight owners after adding the optional research probe. The private CI traceback was unavailable; the source mismatch is independently verifiable.
- The shared consumer inventory already drifted on the baseline, and U4 adds three missing consumers (`research/evidence.py`, `http.py`, `execution.py`). Regeneration and a passing inventory check are required; this is not an unchanged inherited failure.
- [U2 run 38841058334](https://github.com/revenantonthemission/DocSuri/actions/runs/38841058334) reports 59.94% coverage against an unchanged 80% threshold. Its ancestor [run 38814424728](https://github.com/revenantonthemission/DocSuri/actions/runs/38814424728) already failed at 76.86%. The configuration measures all frontend source while running only U2 tests; added U4 source expands the uncovered denominator. This is a mixed inherited/new contribution, not proof that the coverage requirement passes.

## Baseline comparison

Develop `72aeba5d`, [run 38815569163](https://github.com/revenantonthemission/DocSuri/actions/runs/38815569163), already exhibited legacy lint failures, a missing PostgreSQL service alias, macOS keychain refusal, Linux/macOS platform mismatch, editable dependency audit failures, and missing `psycopg`/`server` imports. The earlier U2 run also reported 24 tests with one database failure, although its private underlying traceback remains unknown.

CONVENTIONS.md permits completed work to integrate despite evidenced pre-existing
legacy failures during this interim period. It does not waive new regressions,
replace local verification, or permit failing runs to be described as passing.

## Diagnostic rerun

Commit `0c32f03e` adds only bounded failure classifications, report-presence flags
and numeric process-supervision metrics, with five focused checks. It preserves
private logs, fixtures and credentials. [Run 38841753531](https://github.com/revenantonthemission/DocSuri/actions/runs/38841753531)
completed with shared contracts and frontend passing, backend setup failing, and
browser skipped. Backend setup reached the published loopback PostgreSQL port,
but the connection closed unexpectedly before migrations. The source checks
readiness through the container's Unix socket while migrations use host TCP;
that mismatch is an evidenced readiness gap. A bootstrap transition is plausible
but unconfirmed because container lifecycle logs are unavailable. The repair is
a bounded, authenticated readiness check on the actual migration endpoint. This
run provides no browser failure classification or RSS evidence.

## Repair verification

Commit `5bf08fab`, [run 38842327842](https://github.com/revenantonthemission/DocSuri/actions/runs/38842327842), passed shared contracts, frontend, authenticated database startup and all 49 migrations. Its cumulative backend check failed and browser was skipped. Local execution of the same source identified the obsolete setup mock: 122 tests passed before one failure because the mocked setup did not intercept the new TCP-readiness boundary. Commit `3f9b4fe5` corrects that test and asserts readiness precedes migration; all 76 safe operations tests pass.

The consumer inventory drift check now passes. The legacy shared job then exposed
an E501 line-length failure at `shared/python/tools/export_workspace_contract.py:89`;
that source is unchanged from develop `72aeba5d`, so it is an inherited defect
previously masked by the inventory failure.

[Run 38842485487](https://github.com/revenantonthemission/DocSuri/actions/runs/38842485487)
checks commit `3f9b4fe5`. Shared contracts, frontend and backend passed. Browser
setup and 49 migrations passed, but the supervised browser process tree exceeded
the unchanged 1-GiB RSS limit after 4.069 seconds: 1,078,366,208 bytes, about
4.41 MiB above the limit. The safe summary records `rss-limit`, no test report,
and stopped processes. This establishes the CI browser failure cause; it does
not invalidate the separately recorded local six-journey pass. A footprint
repair remains required, preserving the bound and complete journey coverage.

Local commit `3f9b4fe5` passed six browser journeys followed by 191 backend tests
at 88.22% coverage on the same fresh realm `docsuri-u4-6242203c924051fe`. Both
evidence records bind source digest
`263138dac917df184b469b9886e694fe0ce28f6d0970f0185c50aa4665cae8fa`.
These are local results, separate from the failed remote browser phase.

Commit `83f6aa26` bounds both Playwright Node processes and Chromium renderer V8
heaps at 128 MiB old space plus 8 MiB semi-space, preserving the aggregate
1-GiB RSS limit, 300-second deadline, browser version and six journeys. All 78
operations checks pass, including actual coordinator/child heap measurements.
The local browser rerun passed all six journeys with peak RSS 928,759,808 bytes
and source digest
`f7e5fe9c8fbda21938deb339944d9aba9abcf51bfe1a9f46b1e6089fde5cf442`.
It reused the same realm only after confirming sufficient remaining quota;
previous reports were preserved and no accounts, allocations or usage were reset.
The previous 191-test local backend result belongs to `3f9b4fe5`.

[Final U4 run 38843024805](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805)
passed all four jobs at exact commit `83f6aa262e568eee2591f24418eda1ffe275518e`:

- [Backend](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805/job/116787190203): 193 tests, zero failures/errors/skips; 18.029 seconds; peak RSS 198,246,400 bytes; clean process stop. The configured 80% coverage gate passed. The precise remote percentage remains in a private log and is not claimed here. The retained 13+39 transport/recovery checks also passed.
- [Browser](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805/job/116787414888): all six journeys, zero failures/errors/skips; 13.508 seconds; peak RSS 1,012,883,456 bytes; clean stop after authenticated startup and 49 migrations. Both the 1-GiB RSS and 300-second bounds remain enforced.
- Shared-contract and frontend jobs passed their drift, contract, typing, lint, coverage and build checks.

This establishes final-source U4 CI success. It does not turn the broader legacy
PR checks green or establish full product parity, public capacity or real-model
quality.

On `3f9b4fe5`, U3 database, repository, component, integration and frontend jobs
passed. Operations advanced to eight tests with one failure, after previously
stopping at six. Its next secret-free-diagnostics test requires prior evidence
even in a fresh matrix realm; that test condition predates U4. The underlying
CI traceback is private, so this is a source-backed explanation to investigate,
not a claimed observed failure name or a passing operations suite.

The U4 workflow uses standard runners in this public repository with read-only
repository permissions. [GitHub's Actions billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
supports the free standard-runner choice. No paid model fallback, larger runner,
self-hosted execution, public private-data artifact or deployment is configured.

## Prepared-admission recovery repair

[Run 38846093453](https://github.com/revenantonthemission/DocSuri/actions/runs/38846093453)
checked `d1281014a446a297ff33f7a00103f39d5272675c`. Shared contracts and frontend
passed. Backend startup and all 50 migrations passed, but its cumulative suite
stopped after 76 executed tests with one failure, zero errors/skips, in 21.365
seconds at peak RSS 184,872,960 bytes. Browser was skipped. The public summary
does not expose the failing test name; the separate local run identified normal
owner-connection allocation preventing the new acceptance/recovery race check.
That failure requires a repaired-source run; the earlier green CI remains tied
to its earlier source and does not verify the new recovery change.

## Recovery-lane repair verified

[Run 38846639523](https://github.com/revenantonthemission/DocSuri/actions/runs/38846639523)
checked `bca67823bba0afed705f5967cd4c9d154d5c3ad3`. All four U4 jobs passed:
shared contracts, frontend, backend and browser. Both stateful jobs applied all
50 migrations and stopped their test/application processes cleanly.

| Phase | Tests passed | Failures/errors/skips | Seconds | Peak process-tree RSS |
|---|---:|---|---:|---:|
| Backend coverage | 216 | 0 / 0 / 0 | 24.993 | 184,848,384 bytes |
| Browser | 6 | 0 / 0 / 0 | 13.444 | 999,849,984 bytes |

The 1 GiB RSS, 300-second deadline and 80% coverage gates were unchanged. The
public summary does not expose the remote coverage percentage; 88.62% is the
separate local result. This successful U4 workflow does not change the broader
legacy-workflow dispositions above, prove full capability parity, select public
hosting, or replace the fresh review and completion-command decision.
