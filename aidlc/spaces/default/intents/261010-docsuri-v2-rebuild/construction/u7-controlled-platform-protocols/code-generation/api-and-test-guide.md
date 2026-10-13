# U7 operator API, installation and recovery guide

The controlled operator is an independent local executable. Its transport is the
C10 local stdin/stdout JSON envelope; there is no network admin surface.

## The envelope

One JSON document on stdin, one JSON document on stdout:

```json
{ "op": "executeControlled", "request": { "...": "..." } }
```

Response (success):

```json
{ "ok": true, "op": "executeControlled", "result": { "...": "..." } }
```

Response (refusal):

```json
{ "ok": false, "op": "executeControlled", "error": { "code": "FORBIDDEN", "requestId": "…", "retryable": false, "messageKey": "…", "details": { "fieldNames": [] } } }
```

Exit code `0` = success, `1` = a C10 refusal, `2` = malformed envelope or
unavailable synthetic environment.

### C10 operations

| `op` | Input (C10 type) | Output | Auth |
|---|---|---|---|
| `inspectEvidence` | `OperatorEvidenceRequest` | `OperatorEvidence` | operator authority or bounded evidence-reader for the exact target |
| `executeControlled` | `OperatorExecuteRequest` | `OperatorReceipt` | current, independent operator authority of the matching class |
| `readReceipt` | `OperatorReceiptRequest` | `OperatorReceipt` | same target-scoped authority; reconciles an unknown anonymously |

### Local operator commands (not C10 operations)

| `op` | Purpose |
|---|---|
| `provisionAuthority` | provision a local, target-scoped grant for the verified local OS user |
| `revokeAuthority` | revoke a grant immediately |
| `provisionTarget` | register a synthetic target |
| `recordEvidence` | compute and persist a bound, finite-lived evidence generation |
| `reconcile` | reconcile an `unknown` receipt from the target without re-executing |
| `status` | local receipt-derived status view (counts + unresolved unknowns) |

The actor is always derived from the local OS user (`authority.local_actor()`);
a request that claims a different `actorId` is refused. Internal state projects
onto the C10 wire enums (`enums.py`): `current→compatible`,
`stale/mismatched→incompatible`, `missing→unknown`;
`authorized→accepted`, `executing→running`, `completed→succeeded`,
`failed→failed`, `unknown→unknown`.

## Installation

From the repository root, with the pinned backend environment and Docker:

```bash
python3 scripts/verify_docsuri_u7.py --phase setup --profile local --environment-file /tmp/docsuri-u7-run/environment.json
```

`setup` creates an owned disposable PostgreSQL (labelled `dev.docsuri.u7.run`),
installs the `platform_control` schema and roles via
`scripts/bootstrap_docsuri_u7.py`, seeds the retained-inventory vocabulary and
synthetic targets, and writes the private runtime/provisioner credentials under
`/tmp/docsuri-u7-run/` (mode `0600`, owned by the operator). The runtime never
inherits production credentials.

## Operations and recovery

```bash
backend/.venv/bin/python scripts/supervise_docsuri_u7.py status
backend/.venv/bin/python scripts/supervise_docsuri_u7.py start|stop|restart
backend/.venv/bin/python scripts/supervise_docsuri_u7.py backup
backend/.venv/bin/python scripts/supervise_docsuri_u7.py restore
backend/.venv/bin/python scripts/supervise_docsuri_u7.py rollback
```

- `backup` runs `pg_dump` inside the owned container to `/tmp/docsuri-u7-run/`.
- `restore` loads the latest backup into a fresh `docsuri_u7_restore` database and
  proves the receipts survived; it never destroys the live database.
- `rollback` verifies the migration marker and that receipts are intact across a
  restart (the schema is additive-only, so a rollback never destroys receipts).

## Development test commands

```bash
python3 scripts/verify_docsuri_u7.py --phase runner-readiness --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase component   --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase database    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase repository  --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase integration --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase operations  --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase coverage    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
python3 scripts/verify_docsuri_u7.py --phase teardown    --profile local --environment-file /tmp/docsuri-u7-run/environment.json
```

The exact Construction Verification Command remains **UNSET**; none of these
commands records a completion or a checkpoint.
