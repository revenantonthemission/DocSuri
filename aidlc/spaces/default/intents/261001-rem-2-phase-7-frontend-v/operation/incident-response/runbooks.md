# Runbooks — DocSuri mac-mini operations

Every runbook starts at `ops/server/docsurictl status` and ends with the verification step. Production remediations are owner-authorized actions; this document is the procedure, not an execution.

## RB-1 · Public site down (heartbeat alert or manual report)

1. `ops/server/docsurictl status` — read the launchd block and endpoints.
2. `tail -20 ~/Library/Logs/DocSuri/heartbeat.log` — the `FAILED probes:` list names the broken link (api/web/public).
3. Branch by the broken link:
   - **public only:** `rg -ni error ~/Library/Logs/DocSuri/tunnel.log | tail` → `docsurictl restart tunnel`; if ingress config is suspect, `ops/server/tunnel-setup.sh <hostname>` (preserve other routes).
   - **web only:** logs → `docsurictl restart web`; if the build is bad, rollback per `rollback-runbook.md`.
   - **api only:** see RB-2.
4. Verify: `curl -s -o /dev/null -w '%{http_code}' https://docsuri.rvnnt.dev/` → 200, then heartbeat log shows `all-ok` next tick.
5. Communicate to the owner; open the incident record per `incident-plan.md` (P1).

## RB-2 · API down / crash-loop

1. `tail -50 ~/Library/Logs/DocSuri/api.log` — classify:
   - `MigrationBlocked: … NEEDS_RECONCILIATION` → **operator reconciliation required** (the ENV-01 worked example); this is an owner-run schema action, not a restart fix. After reconciliation: `docsurictl restart api`, verify `/health` 200.
   - Any other traceback → fix cause on the trunk → CI green → deploy per `cd-config.md`.
2. Never disable the migration guard to force a start — the guard is the safeguard.
3. Verify: `curl -s http://127.0.0.1:8000/health` 200 + a BFF API round-trip.

## RB-3 · Disk pressure (ENV-02 live: 96%)

1. `df -h /`; `du -sh ~/Library/Logs/DocSuri`.
2. `cat ~/Library/Logs/DocSuri/logrotate.log` — fix the rotation fault first (exit 1).
3. Bounded cleanup under owner authorization (rotated `*.log.N` histories are the first candidates).
4. Set the disk alarm per `anomaly-config.md`; keep ≥ 15% free target (SLO).

## RB-4 · Tunnel / ingress failure

`docsurictl restart tunnel`; check `cloudflared` logs; if the ingress file is wrong, re-run `tunnel-setup.sh` preserving verified routes; verify public 200. Invariants: only `127.0.0.1:3000` is published.

## RB-5 · Data restore

Follow `deployment-pipeline/rollback-runbook.md` §Data restore (stop writers → restore the chosen pg_dump → restart → verify through the BFF).

## RB-6 · Bad rollout (regression after deploy)

Follow `deployment-pipeline/rollback-runbook.md` service-level rollback (previous revision + `docsurictl rebuild`/`restart`), then smoke per `deployment-execution/smoke-test-results.md` checks.
