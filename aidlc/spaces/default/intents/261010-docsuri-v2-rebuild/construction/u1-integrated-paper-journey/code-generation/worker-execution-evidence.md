# Worker supervision checkpoint

This is a Step 7/8 component checkpoint, not completed U1 or normal model
readiness. The worker uses the existing canonical claim facade and PA/Usage
owners. Full canonical payload assembly, native model process stop evidence,
mounted worker transport and useful source-grounded output remain outstanding.

## Implemented boundary

- Worker identity is fixed by trusted coordinator construction. Submitted work
  supplies immutable binding and, for replacement, the exact previous fence.
- One active execution per coordinator; executor computation is separate from
  lease supervision. Heartbeats run every 10 seconds. The deadline uses the
  owner's remaining minimum of original execution/recovery windows and
  conservatively includes the entire payload-read call time.
- An independent timer requests owned abort even when a renewal reply is slow.
  Before publication the computation thread must finish and the executor must
  acknowledge stopped. Missing acknowledgement or failed abort quarantines the
  coordinator; it cannot acquire another item. Diagnostic tests compress timing
  only in their worker instance, without changing production constants.
- Explicit insufficient-result/dependency/source failure can produce a guarded
  failure fact. Lost authority/deadline cannot grant a late failure privilege;
  owner recovery remains responsible. Terminal commit or settlement uncertainty
  propagates without compensating failure or timeout-only usage release.
- Stable terminal fact identity binds operation, lease and fence. Existing
  repository guards remain authoritative at publication. A terminal duplicate
  delivery does not run the diagnostic executor again.
- Executor/watchdog startup is inside cleanup. A failed watchdog start after
  computation starts still requires owned abort/stop. If the abort supervisor
  itself cannot start, the coordinator latches unavailable rather than calling
  a potentially unbounded abort inline or permitting another execution.

## Executed evidence

Commands run from the repository root:

```bash
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

| Attempt | Actual result | Boundary |
|---|---|---|
| Initial component | 119 passed, 3.22 seconds | Eight new deliberate executor/transport fault cases |
| Corrected component | 119 passed, 3.22 seconds | Cleanup tightened to require stopped acknowledgement even after run returns; native descendant tests remain pending |
| Initial repository | 76 passed, 2 setup errors, 264.09 seconds | New diagnostic provenance differed from the fixture's exact old marker; refusal retained |
| Corrected repository | 78 passed, 296.34 seconds | Real-role success, explicit refusal and commit-then-lost-reply settlement recovery |
| Bulk fixture first | 78 passed, 21.10 seconds | Bounded bulk reads replaced connection-per-historical-record setup |
| Bulk fixture second | 78 passed, 21.28 seconds | Known-ID lookup retained visibility of unexpected related owners |
| Bulk fixture final | 78 passed, 21.23 seconds | Explicit unexpected reservation/result owner rejection before fixture mutation |
| Watchdog startup component | 120 passed, 3.16 seconds | Deliberate watchdog start failure after executor begins |
| Final component | 121 passed, 5.06 seconds | Also covers abort-supervisor start failure and quarantine |
| Final repository | 78 passed, 21.02 seconds | Real-role regression after supervised startup correction |

Final repository collection/execution counts both 78, with zero errors, failures
or skips. Source remained unchanged during the run. Baseline HEAD was
`4a6d6fe6ff30d8cf8cacf2b1524080394b021d49`; the complete tested source inventory
SHA-256 was `49b534f8d37d222a97c45262f188e730a7c0271cb2b2f1886e688e0a74e8bb54`.
Scoped Ruff and `git diff --check` passed. No new coverage measurement is claimed;
the completed-U1 per-module 80% obligation remains in force.

Private result/source-inventory and JUnit pairs are retained under
`/tmp/docsuri-u1-run/`, with prefixes `worker-first-component-`,
`worker-provenance-failure-`, `worker-corrected-`, `worker-bulk-first-` and
`worker-bulk-second-`, `worker-bulk-final-` and `worker-watchdog-first-`.
The final run currently occupies `repository-result.json`
and `repository-junit.xml`. The previous recovery checkpoint is preserved as
`recovery-final-repository-*`. These records do not contain normal model success.

## Diagnostic fixture repair

The first new worker case succeeded, then the fixture correctly refused its
unrecognized diagnostic result before the following cases. The original failure
record and JUnit were preserved before retry. Recognition now requires the exact
`repository-boundary` payload family, exact `normalModelReadiness: false`
diagnostic provenance, and SHA-256 of the literal diagnostic-only output bytes.
Immutable published results were not rewritten.

A read-only measurement found 319 retained diagnostic jobs. The old fixture
opened two new database connections per historical job, explaining growth in
setup cost. Bulk reads now remain within at most 1,024 known job/admission IDs;
overflow refuses before mutation. Reads use the existing separate owner roles,
and unexpected reservation/result ownership is rejected, not filtered away.
The existing verified disposable database/run identity and shared fixture lock
remain mandatory. Historical jobs/results are retained. Only already-authorized
diagnostic phase transitions and exact diagnostic reservation cleanup occur;
this is not a production recovery or normal-data retention policy.

## Remaining limits

The executors here are explicitly diagnostic and fault adapters. They establish
supervision and transactional integration only. Actual native runner descendants
must be proven stopped even when their server parent has already exited, and
ownership must be established before signalling any process group. Process/VM
restart, protected transport, mounted full-payload execution, final coverage and
the complete browser journey remain required. The latest real-model experiment
still fails the original semantic rubric; no normal profile was promoted.
