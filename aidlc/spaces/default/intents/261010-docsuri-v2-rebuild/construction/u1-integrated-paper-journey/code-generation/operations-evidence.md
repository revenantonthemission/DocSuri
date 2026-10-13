# U1 operations, recovery and supervision evidence (Steps 13–14)

Date: 2026-10-13 (KST). Real bounded restart, restore, replacement, repair and
mixed-load evidence against the owned journey realm and its persistent
disposable volume. No external service, telemetry vendor or host reboot is used.

## Configuration and procedures

- Versioned supervisor: `scripts/supervise_docsuri_u1.py` (`status`, `start-api`,
  `stop-api`, `restart-api`, `restart-container`, `backup`, `restore`,
  `rollback`). Manifest-scoped; refuses unknown profiles, foreign containers,
  stale process files and missing transport material.
- Procedures and bounded limits: `ops/local-stack/u1-operations.md` (stop/replace,
  backup/restore/rollback, readiness/observation expiry, finite allocations).
- Targeted CI checks: `.github/workflows/u1-paper-journey.yml` (scoped frontend
  lint/typecheck/tests/build, scoped python lint, U1 test collection). The
  legacy pipeline keeps its own interim comparison; nothing deploys.

## Executed checks

```text
python3 scripts/verify_docsuri_u1.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

**5 passed**, zero failures (`operations-junit.xml`):

| Case | What it proves |
|---|---|
| container replacement | An acknowledged owner save survives a real container restart; `State.StartedAt` changed, so the container was genuinely replaced. |
| backup/restore round trip | `pg_dump -Fc` + drop/recreate/restore; acknowledged pre-dump state returns, post-dump effects are rolled back, the run identity and owner restrictions (foreign direct write denied) survive. |
| worker replacement | A replaced worker's closed fence cannot publish (`stale execution claim`); the new fence completes with exactly one retained result and one committed reservation. |
| controlled defect repair | A revocation injected after admission is diagnosed by owner recovery, terminalized with the explicit `execution-authority-revoked` failure and the reservation released; the account state is restored afterwards. |
| mixed load | 8 concurrent real candidate reads on the finite api-process gate completed in 0.245 s with no allocation error; recorded in `operations-mixed-load.json`. |

World-state changes are bounded to the disposable realm and the test-owned
fixture account; the attempt ledger, demo account and unrelated data are never
touched. Supervisor commands record `backup-<name>.json`,
`restore-<name>.json` and started-at evidence in the run root.

## Recorded but unexecuted (with reasons)

- **Host/VM restart**: rebooting the developer host is outside the owned
  boundary; container replacement plus the persistent volume and the restore
  round trip are the executed substitutes. A real cold-boot test remains a
  later-unit/operations obligation.
- **Optional telemetry outage**: the AI incident/telemetry worker path is not
  part of this unit's runtime (no model executor is selected while the
  source-rubric prerequisite is open); durable business obligations are proven
  by the settlement/repair cases instead.
- **Model-path mixed load**: the local model endpoint is not reachable during
  this phase, and assistance acceptance is truthfully refused while the
  reviewed-readiness marker is absent; no model-quality or capacity claim is
  made here.
- **Fresh-checkout defect reproduction effort**: the controlled defect is
  injected and repaired in-realm; a from-scratch setup/diagnosis/repair timing
  baseline awaits the human-agreed numeric targets.
