# U7 unit test instructions

## Status and test ordering

These instructions accompany the approved-on-approval [plan](code-generation-plan.md).
The U7 suite, configuration and wrapper below are **planned, not yet executed**.
Use the plan's unchanged Testing Contract (test-after): implement each applicable
component fully, then write and run its tests. Verify runner readiness before the
first behavior test. Build and Test later verifies and extends this evidence.

Every command targets only `u7-controlled-platform-protocols`. The Construction
Verification Command remains unset until the human approves its exact runnable
invocation; none of these commands records that approval or completes a checkpoint.

## Runner setup and configuration

Run from the DocSuri repository root. The wrapper `scripts/verify_docsuri_u7.py`
orchestrates only the bounded paths below, uses argument arrays (no shell
interpolation), propagates every child failure, and records collection totals
separately from executed tests. It must reject unknown phases, escaping paths,
missing dependencies, an unavailable required service and an empty behavior-test
collection; its phase selector never falls back to a repository-wide test run.

| Purpose | Configuration and exact scope |
|---|---|
| Python component tests | `tests/u7_controlled_platform_protocols/component/`; `backend/pytest.u7-platform-control.ini` |
| PostgreSQL behavior | `tests/u7_controlled_platform_protocols/database/`; real local PostgreSQL, dedicated `PlatformControl` schema + roles |
| Repository behavior | `tests/u7_controlled_platform_protocols/repository/`; guarded transactional adapters |
| Mounted CLI boundary | `tests/u7_controlled_platform_protocols/integration/`; the real stdin/stdout JSON envelope |
| Operations/recovery | `tests/u7_controlled_platform_protocols/operations/`; supervisor restart/backup/restore/rollback |
| Coverage | the U7 tests plus an explicit inventory of new/changed U7 modules |

## Isolated fixture setup

The setup phase creates a uniquely named U7 synthetic environment and writes its
private manifest to `/tmp/docsuri-u7-run/environment.json` (ownership marker +
exact manifest; refuse a mismatched existing directory). It provisions the
`PlatformControl` schema and roles in the **local** PostgreSQL, synthetic grants,
and private fixture targets. The runtime never inherits production credentials.

```bash
python3 scripts/verify_docsuri_u7.py --phase setup --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase runner-readiness --profile local --environment-file /tmp/docsuri-u7-run/environment.json
```

Runner readiness validates imports/config/versions and exact collection roots; it
may report that test files are not yet authored but must not claim behavior passed.

## Exact U7 development commands

```bash
python3 scripts/verify_docsuri_u7.py --phase database    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase repository  --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase component   --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase integration --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase operations  --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase coverage    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase teardown    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
```

## Required behavior and volume

Five to eight focused tests per component family, plus real-boundary cases:

| Boundary | Required checks and positive controls |
|---|---|
| Real runtime database grants | Owner-only DML; denied foreign DML and guard-function abuse; legitimate guarded target write; rollback on failure |
| One-in-flight + binding | A durable target lease refuses a second same-target operation; the actor/target/input/evidence/policy binding is committed before the effect and survives restart |
| Evidence states | current / stale / mismatched / missing are distinguished; only `current` authorizes |
| Authority | wrong actor/target, app-admin-only and routine-vs-destructive-refused before any effect; revocation immediate; `evidence-reader` read-only |
| Replay/reconciliation | same-key same-input returns the receipt; changed input conflicts; an interrupted/unknown outcome reconciles without re-execution; stale in-flight promotes to `unknown` (never `succeeded`) |
| Failure handling | permission/disk/connectivity → `failed`/`unknown`, never `completed`; disk exhaustion is truthful |
| Wire contract | request/response conform to C10 with the internal→wire mapping; stable error vocabulary; reads create no effect |
| Operations | restart preserves receipts; backup/restore and rollback keep receipts; unresolved-unknown list stays visible; no paid dependency |

Use fakes only for narrow unit isolation and explicitly injected faults. Pair each
denial with an authorized positive control. Keep credentials, private text and
secrets out of committed evidence. **No real destructive/release effect runs.**

## Coverage and measurement

Measure ≥80% line coverage for every new/changed U7 module; report per-file and
aggregate denominators without hiding low-coverage code or lowering thresholds.
Operator scripts that run only as subprocesses are classified as unmeasurable
in-process, with their exercise evidenced by the phases that invoke them.

## Mocks, fixture custody and cleanup

Each run manifest records source SHA, lock/model/image hashes, commands, test IDs,
timestamps, results and owned resource identifiers. A teardown phase removes only
resources proven to belong to that exact manifest and refuses unknown directories,
shared services and any uncertain resource.

Before completion, `code-summary.md` records the implemented runner, expanded
invocations, results and remaining limitations; the conductor runs the independent
review and the completion checkpoint.
