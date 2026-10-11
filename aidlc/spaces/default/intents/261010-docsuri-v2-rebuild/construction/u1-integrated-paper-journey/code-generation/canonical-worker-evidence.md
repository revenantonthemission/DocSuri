# U1 canonical worker handoff

PaperWorker now consumes ExecutionPayloads through its trusted worker identity.
The generated AssistanceExecutionPayload is validated and its binding compared
with the acquired execution before passing it to the executor. A canonical
accepted input cannot use the older unbound diagnostic path without a reader.

Payload assembly occurs inside the existing execution thread, deadline watchdog
and independent lease heartbeat. Its elapsed time consumes the original job
budget; assembly does not grant another 90 seconds. Authority denial, changed
binding or an exhausted original budget starts no executor and emits no new
terminal fact. Owner recovery retains responsibility for unresolved work.

The actual journey boundary now performs two fresh diagnostic operations per
invocation: direct generated payload retrieval, then the full PaperWorker handoff
using actual account, source, preparation, usage and execution owners. The second
executor validates the canonical payload and deliberately refuses with
dependency-unavailable without running a model. The owner records failure and
releases usage. No prepared result or normal useful-output claim is produced.
Both operations remain in history. Admission reserves two remaining slots in
the existing finite 64-job diagnostic history; no prior records are erased.

Executed commands:

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

- Component: 169 collected/executed/passed in 3.36 seconds.
- Repository: 84 collected/executed/passed in 22.63 seconds.
- Zero errors, failures or skips. Both runs report unchanged source digest
  ac9e7c17f30f7db916dcb5297953a63c2a83c3a466f33c6ec860fc10e6baa125.
- Protected result/source inventories/JUnit:
  `/tmp/docsuri-u1-run/canonical-worker-final-{component,repository}-{result.json,junit.xml}`.
- Scoped Ruff formatting/lint passed.

New fault cases cover trusted identity handoff, missing canonical reader,
authority loss, a heartbeat while payload assembly waits, original deadline
exhaustion before execution and changed payload binding. The real boundary
also verifies the selected P1 Korean sentence and released usage.

The real native model executor, protected transport/process-group stop proof,
mounted browser/worker APIs, cumulative per-file coverage and useful-output
quality remain outstanding. Normal inference readiness remains false. This
does not run or approve the separate Construction completion command.
