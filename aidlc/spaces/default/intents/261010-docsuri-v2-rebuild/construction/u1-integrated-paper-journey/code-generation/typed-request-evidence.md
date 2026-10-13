# U1 typed options, preparation and real canonical payload

## Implemented

PaperAssistance owns a bounded server-defined option catalogue. Each revision
binds source content, eligibility, exact selections, operation/language/
presentation, processing policy and readiness. The default unready catalogue
offers no runnable options and explains the limitation in Korean. This does not
select a successful model profile: useful-output readiness is still false.

The request adapter validates generated AssistanceRequestHttp, then checks
current account/session/consent/source authority before looking up a prior
preparation. Same owner and same normalized request recover the original
preparation before mutable catalogue or glossary inspection; changed requests
conflict. The canonical body excludes tracing metadata and rejects extra fields.

Fresh preparation checks source eligibility and glossary revision under the PA
owner transaction and captures the actual owner glossary snapshot. The full
frozen intent is hashed for usage/acceptance/execution. Later glossary changes
cannot alter acceptance: the job consumes the prepared snapshot. Existing
unmounted diagnostic helpers retain their separate compatibility behavior.

## Actual boundary

The owned journey realm now contains one synthetic account, intended journey A.
It was enrolled through real registration, private local verification delivery,
verification and authenticated login. Private credentials remain only in
`/tmp/docsuri-u1-run/journey-account-a.json`; they are not committed. Account B's
slot remains available. No existing account/source/job was reset or rewritten.

A fresh operation on each invocation uses actual P1 source s3.5.p1 at Unicode
offsets 227:343, its original/selected byte hashes, CorpusContent revision and
the generated canonical payload. It exercises real preparation, reservation,
acceptance, trusted execution claim, source retrieval and worker-identity denial.
The test-only catalogue explicitly injects readiness for transport binding; no
normal model is enabled and no inference or useful-output claim is made.

Each diagnostic operation ends with a live guarded dependency-unavailable
failure because no executor is supplied, then releases usage from that conclusive
owner proof. It retains the job and reservation; later runs use a fresh operation
instead of treating terminal replay as a current payload test. A 64-job history
bound and outstanding-work refusal prevent unbounded diagnostic accumulation.
After both attempts: one account, two failed jobs, two released reservations,
zero prepared results. The corrected run logs out even if an assertion fails.

## Verification

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

- Initial typed component: 163 passed in 3.17 seconds.
- Initial typed repository, before the actual journey case: 83 passed in 22.15 seconds.
- First actual payload run: 83 passed, one failed in 22.91 seconds. The assertion
  incorrectly compared a generated Hash RootModel to a string; payload retrieval
  had succeeded. Corrected to compare its root value. Guarded failure/release ran
  even on this failed attempt. Original result/source inventory/JUnit retained as
  `/tmp/docsuri-u1-run/canonical-payload-hash-assert-repository-{result.json,junit.xml}`.
- Final repository: 84 collected/executed/passed in 22.74 seconds.
- Final component: 163 collected/executed/passed in 3.31 seconds.

Final runs have zero failures/errors/skips and unchanged tested source digest
e57daa9b9713583e37fe8a5fb45153144e6781768eeecc4e149ca4e172887a46.
Their reports, full inventories and JUnit are protected under
`/tmp/docsuri-u1-run/typed-request-final-{component,repository}-{result.json,junit.xml}`.
Scoped Ruff formatting and lint passed. The real-role cases additionally prove
glossary/source revision rejection without preparation, same-intent snapshot
replay, source withdrawal before replay and valid account-B isolation with
authorized positive controls.

The worker loop still needs to consume this canonical payload, followed by
mounted HTTP/session/progress boundaries. Actual native stop proof, complete
journeys, useful model output, cumulative per-module coverage and the remaining
U1 obligations remain open. This is not the separately approved completion check.
