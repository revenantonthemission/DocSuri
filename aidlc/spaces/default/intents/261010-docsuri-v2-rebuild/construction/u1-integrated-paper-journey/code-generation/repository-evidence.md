# U1 repository evidence

Date: 2026-10-11. Steps 5–6; synthetic local environment only.

## Implemented boundary

Owner-specific lazy PostgreSQL pools share a process admission bound: API four,
worker two, observation one and maintenance one connections, leaving four slots
within the database's twelve. Transactions use SERIALIZABLE with at most two
retries and one ten-second deadline covering admission, acquisition, statements
and commit initiation. Lost commit replies produce an explicit unknown outcome;
callers reconcile their original operation identity.

Library receipts, corpus publication/withdrawal, read-only discovery projections,
durable search-history relay, assistance admission/claims/publication and separate
usage settlement now have owner adapters. Files are immutable, private, bounded,
hashed and opened without following symlinks or blocking on FIFOs. Model/network
execution is outside protected transactions. Current permission precedes receipt
replay and prepared-result reads.

## Executed verification

The approved repository phase command collected and passed **22 tests**, with
zero failures, errors or skips, in 28.56 seconds:

```bash
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Its private manifest binds HEAD `98b1062cbcea82d13f22681fce125a029eb0dc76`
and actual source/configuration bytes by aggregate SHA-256
`1761c0cb714f9a71649ea6835bbbcd27a5eed5ffe440358693ed72be09ee0ec8`.
This run preceded the shared fixture-lock addition below. It includes actual
owned-container replacement over the same persistent volume, acknowledged-save
rediscovery, failed/unknown commits, duplicate/conflicting intent, current owner
and source denial, malformed files, publication failures, replacement-worker
rejection and lost settlement reply reconciliation with one accounting effect.
The real three-statement delay test cancels at the aggregate deadline and proves
the earlier insert rolled back. A narrow fixture expiry advances only the named
diagnostic job's lease for worker replacement; it is not a wall-clock sleep test.

The final cumulative development measurement passed **87 tests** in 41.42
seconds: 18 component/harness checks, 47 database checks and 22 repository
checks. It includes a new shared session-scoped nonblocking fixture lock and a
second-process denial check. Both phase wrappers and direct cumulative pytest
runs enter this root fixture before behavior tests. Collection alone does not
mutate fixtures or claim a behavior pass.

```bash
DOCSURI_U1_ENVIRONMENT_FILE=/tmp/docsuri-u1-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u1-paper-journey.ini tests/u1_integrated_paper_journey/component tests/u1_integrated_paper_journey/database tests/u1_integrated_paper_journey/repository -q --tb=short -p no:cacheprovider --cov=backend --cov=scripts --cov=shared/python/tools --cov-report=json:/tmp/docsuri-u1-run/python-coverage.json
```

This is a scoped development measurement, not the separately approved Construction
completion command, which remains unset. Scoped Ruff formatting and lint passed.

## Coverage at this checkpoint

| Implementation module | Covered / executable lines |
|---|---:|
| backend/artifacts.py | 61 / 67 |
| backend/transactions.py | 87 / 96 |
| backend/local_host.py | 43 / 51 |
| backend/local_profile.py | 34 / 41 |
| backend/modules/corpus/repository.py | 37 / 41 |
| backend/modules/discovery/guarded_repository.py | 32 / 32 |
| backend/modules/library/repository/guarded.py | 30 / 33 |
| backend/modules/plans/guarded_repository.py | 39 / 44 |
| backend/modules/summarization/guarded_repository.py | 147 / 168 |
| backend/app.py (whole existing changed module) | 28 / 124 |
| scripts/verify_docsuri_u1.py | 134 / 271 |
| scripts/bootstrap_docsuri_u1.py | 0 / 126 |
| shared/python/tools/export_workspace_contract.py | 0 / 63 |

Bootstrap and exporter were executed as separate uninstrumented commands;
their zero here is an instrumentation gap, not coverage credit. The existing
application factory, wrapper, generated-binding facade and other changed modules
still need final inventory and cumulative coverage. The 80% per-file requirement
has not been waived or declared fulfilled. SQL has separate real-role behavioral
evidence; Python line coverage does not measure SQL coverage.

## Failed attempts and custody

- An initial repository fixture omitted the private-file dependency, producing
  15 setup errors. After correcting the fixture, subsequent runs exercised the
  actual repositories. A long fixture traceback exposed disposable runtime
  credentials in private tool output. All eight disposable runtime credentials
  were rotated; fixture representations now redact credentials, the runner
  redacts known private values, and pytest uses short tracebacks. No service
  credentials were involved and no raw trace was committed. This does not claim
  historical conversation output was erased.
- A repeated corpus test exposed a fixture that re-enabled eligibility after
  withdrawal without rebuilding its projection. The test now recreates only its
  exact diagnostic source after checking provenance and absence of jobs; product
  withdrawal still prevents implicit republication.
- One cumulative run was mistakenly started while the repository run was still
  active. Shared fixture writes produced seven failures and three setup errors
  after 57 passes; that run was interrupted and is invalid coverage evidence.
  A clean serial rerun passed 86 tests. The shared fixture lock then fixed the
  harness gap; the final serial rerun passed 87 tests. These overlap failures are
  not classified as product regressions.
- Phase cleanup handles only exact diagnostic identities. Database-only jobs
  require the known empty payload/hash and no usage reservation or model result.
  Repository jobs require `fixtureFamily=repository-boundary` and diagnostic
  result provenance. Unknown work/accounting refuses reset. No test in this
  phase executed a model, and fixture retirement is not production recovery.

## Remaining evidence

Business services, canonical mounted API/worker bindings, useful real-model
output, browser journeys, load, coherent restore and safe VM-restart behavior
remain later steps. Only the owned PostgreSQL container was replaced; the shared
Docker VM and unrelated services were not restarted. The saved-reference list
still needs U1 business/API/UI disposition handling so a withdrawn source remains
visible without hiding eligible saved work. Direct source content remains denied.
Infrastructure R-01 and contract R-03 require the remaining mounted evidence
before broader closure claims.
