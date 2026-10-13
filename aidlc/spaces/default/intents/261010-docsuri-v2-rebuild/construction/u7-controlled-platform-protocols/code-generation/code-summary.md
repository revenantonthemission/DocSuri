# U7 code summary

Unit `u7-controlled-platform-protocols` — the actual implemented operator, the
commands run, their measured results and the remaining limitations. The
independent architecture review, the Construction Verification Command and every
completion checkpoint remain with the conductor and the human; nothing here
approves them.

## What is implemented

- **Operator package** `ops/src/docsuri_ops/platform_control/`: the retained
  inventory (`inventory.py`/`inventory.json`), internal→wire state projection
  (`enums.py`), the C10 error vocabulary (`errors.py`), the guarded store
  (`store.py`), the owner-scoped `PlatformControl` schema with `SECURITY DEFINER`
  guard functions (`schema.sql`), independent authority (`authority.py`),
  bound finite-lived evidence (`evidence.py`), the bounded executor
  (`executor.py`) and its native adapter (`native_adapter.py`), reconciliation
  (`reconciler.py`), the observations bridge (`observations.py`), the local
  stdin/stdout JSON CLI (`cli.py`) and the owned environment profile
  (`profile.py`).
- **Scripts**: `scripts/bootstrap_docsuri_u7.py` (schema/roles/vocabulary),
  `scripts/verify_docsuri_u7.py` (bounded phase runner),
  `scripts/supervise_docsuri_u7.py` (status/start/stop/restart/backup/restore/
  rollback).
- **Configuration**: `backend/pytest.u7-platform-control.ini` and the scoped CI
  workflow `.github/workflows/u7-controlled-platform-protocols.yml`.
- **Tests**: `tests/u7_controlled_platform_protocols/{component,database,repository,integration,operations}`.
- **Records**: `inventory-evidence.md`, `api-and-test-guide.md`,
  `source-manifest.json`, `traceability.json`.

## Actual commands and results (this environment)

```text
python3 scripts/verify_docsuri_u7.py --phase component   ... # 94 passed
python3 scripts/verify_docsuri_u7.py --phase database    ... # 28 passed
python3 scripts/verify_docsuri_u7.py --phase repository  ... # 22 passed
python3 scripts/verify_docsuri_u7.py --phase integration ... # 26 passed
python3 scripts/verify_docsuri_u7.py --phase operations  ... #  7 passed
python3 scripts/verify_docsuri_u7.py --phase coverage    ... # belowFloor {} , 14 modules measured
```

177 behaviour tests pass in total. Every phase's runner rejects an empty
collection before executing (an empty collection is a configuration error, never
a pass).

## Measured coverage (real numbers, no threshold change)

One instrumented run over the whole U7 suite (`--cov=docsuri_ops.platform_control`):

- **14 measured modules; every one at or above the 80% line floor** (aggregate
  **92%**). The runner applies the floor to **every** module — there is **no
  name-based exclusion** and no module is classified "subprocess-only".
- `native_adapter.py` **97%** and `__main__.py` **100%**, both measured
  in-process: `component/test_native_adapter.py` exercises every adapter branch
  (write/probe/credential-presence, path and token refusal, injected faults,
  error classification, the `main` entrypoint) and
  `component/test_entrypoint.py` runs the package entrypoint through `runpy` as
  `__main__`. No threshold was lowered.
- Per-module: `__init__.py` 100, `__main__.py` 100, `observations.py` 100,
  `errors.py` 98, `native_adapter.py` 97, `enums.py` 96, `store.py` 95,
  `inventory.py` 92, `authority.py` 91, `evidence.py` 91, `executor.py` 91,
  `reconciler.py` 89, `cli.py` 89, `profile.py` 85.

## Verified behaviours (evidence highlights)

- Four-state evidence classification (`current`/`stale`/`mismatched`/`missing`)
  with the honest wire projection; only `current` authorises.
- Wrong actor/target, app-admin-without-grant and reader-execution attempts are
  refused before any effect; revocation takes effect immediately; the
  destructive-release class is separate from routine.
- A durable target lease enforces one in-flight effect per target; the
  actor/target/input/evidence/policy binding is committed before the effect and
  survives a restart; a stale in-flight operation promotes to `unknown` (never
  `succeeded`), and reconciliation resolves applied/not-applied without a second
  effect.
- Stale in-flight promotion is **wired**, not just available: the supervisor
  promotes on its startup path (`start`/`restart` report `promotedOnStartup`) and
  every `readReceipt`/`reconcile` call promotes before reading, so an
  over-deadline `executing` operation is surfaced as `unknown` and appears in the
  unresolved list. Exercised by a mounted CLI receipt read and a supervisor
  restart test.
- Reads are **target-scope bounded in the store layer**, not only at the CLI:
  `read_receipt`, `latest_evidence`, `list_unresolved` and `status_counts` take
  the caller's actor + authority and refuse a foreign target inside the
  `SECURITY DEFINER` function. A denial fixture proves a foreign-scope read is
  `FORBIDDEN`.
- `platform.credential.presence` performs a **real native check** (the target
  credential must be a non-empty, owner-only `0600` regular file; only presence
  and mode are observed), so its `nativeVerified: true` is true; a protocol whose
  adapter cannot establish its semantics would fail closed.
- The read-only `file-probe` **never creates** the target directory; only a
  genuine write effect does.
- A non-numeric `evidenceGeneration` returns `INVALID_INPUT`, never a store
  dependency error.
- Permission → `failed`, disk/connectivity → `unknown`, deadline → `unknown`;
  `completed` requires observed effect evidence and is never claimed on liveness
  alone.
- The mounted CLI emits C10-conforming `OperatorEvidence`/`OperatorReceipt`
  (validated against the shared generated bindings), one JSON document, with the
  stable error vocabulary; reads create no operation.
- Operations: restart preserves receipts; backup/restore round-trips;
  rollback keeps receipts; unresolved unknowns stay visible; no paid/cloud
  dependency is configured.

## Limitations carried

- No real destructive or release operation is exercised; every fixture uses
  synthetic targets (`BR3.7`).
- The numeric per-protocol deadlines and evidence windows are finite declared
  values from the retained inventory, not a measured baseline; numeric
  latency/throughput targets remain baseline-deferred.
- The C11 `recordObservation` push is a recorded coordination item, not
  implemented; U8 consumes outcomes through the C10 pull interface.
- The scoped CI workflow records the database/repository/integration/operations
  phases as unexecuted required evidence (they need the owned Docker fixture);
  the database/executor phases were executed on this host.
- No dedicated type checker (mypy/pyright) is installed in the repository; U7
  modules are fully annotated and lint-clean, and the typecheck stage is recorded
  as unexecuted required evidence.
- The exact Construction Verification Command remains **UNSET**.
