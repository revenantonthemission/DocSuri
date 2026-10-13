# U1 local operations procedures

Owned, disposable synthetic environment. Every command runs from the repository
root and takes the explicit manifest path; nothing here touches a production
database, a trust store, another run's container or unrelated data.

Supervisor: `python3 scripts/supervise_docsuri_u1.py <command> --environment-file /tmp/docsuri-u1-run/environment.json`
(use the locked backend interpreter: `backend/.venv/bin/python` if the system
python is older than 3.11). The supervisor refuses unknown profiles, foreign
containers, stale process files and missing transport material.

## Status and bounded evidence

```bash
backend/.venv/bin/python scripts/supervise_docsuri_u1.py status --environment-file /tmp/docsuri-u1-run/environment.json
```

Reports the owned container state/ownership, retention window, API process and
liveness, `/health/ready` (derived from recorded owner observations with finite
expiry), model endpoint reachability and transport presence. A missing or stale
observation can never pass as ready.

## Start / stop / replace

```bash
backend/.venv/bin/python scripts/supervise_docsuri_u1.py start-api --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/supervise_docsuri_u1.py stop-api  --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/supervise_docsuri_u1.py restart-api --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/supervise_docsuri_u1.py restart-container --environment-file /tmp/docsuri-u1-run/environment.json
```

- The API process is recorded in `api.pid` (owned, 0600, run-bound); stop sends
  SIGTERM and refuses a forced kill if the process does not stop within the bound.
- The database container is restarted only when its ownership label matches the
  current run id. Durable state lives on the named persistent volume, so an
  acknowledged save/job survives replacement; the API is not started implicitly.
- The assistance queue stays bounded because acceptance is refused while the
  reviewed model-readiness marker is absent, and model calls are serialized by
  the bounded local model permit; no worker is supervised in that state.

## Backup, restore and rollback

```bash
backend/.venv/bin/python scripts/supervise_docsuri_u1.py backup  --name pre-change --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/supervise_docsuri_u1.py restore --from pre-change --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/supervise_docsuri_u1.py rollback --to pre-change --environment-file /tmp/docsuri-u1-run/environment.json
```

- `backup` runs `pg_dump -Fc` inside the owned container into a private dump
  (`<name>.dump`, 0600) and records the sha256/byte length in
  `backup-<name>.json`. It refuses to overwrite an existing dump.
- `restore`/`rollback` verify dump custody, drop and recreate **only** the
  owned realm with its owner role, restore with the recorded owner, and record
  `restore-<name>.json` / `rollback.json`. Cluster-level roles and the applied
  migrations survive because only the database is recreated.
- Restoring during active writes is not supported: stop the API first. Reads
  and effects that were acknowledged after the dump are rolled back by design;
  the operations suite proves the restored state, the preserved owner
  restrictions and the one-result/one-accounting-effect invariant.

## Readiness and policy expiry

- Observation expiry is finite (300 s). `/health/ready` re-probes and re-records
  within one bounded call; a stale or missing observation never passes.
- The environment retention window governs the whole profile: the TLS record,
  the API's `OwnerTransactions` and the synthetic usage period all refuse once
  `retentionExpiresAt` has passed. Renew explicitly with the setup phase
  (`scripts/verify_docsuri_u1.py --phase setup ...`), which also re-mints the
  bound TLS material.
- Required incident storage is the operations owner's `operations.incident`
  table with bounded evidence; optional telemetry never gates a durable
  business obligation.

## Limits and refusals

- Build allocation is 2 GiB and the host keeps 8 GiB free; the supervisor never
  prunes Docker or deletes unrelated data to free capacity.
- No command here deploys, promotes, migrates a real environment or modifies a
  trust store. The exact Construction Verification Command remains unset until
  the human approves it separately.
