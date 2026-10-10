# Rollback Runbook — DocSuri (mac-mini production)

Revised per the human decision (2026-10-09): production runs on this mac mini; there is no AWS/ECS/CDK path to roll back. Grounded in `ops/server/README.md` and `ops/server/docsurictl`. **This stage has not executed a rollback drill**; the procedure documents configured seams.

## First response

1. Check what is actually wrong:
   ```bash
   ops/server/docsurictl status          # agents + containers + endpoints + tunnel + disk
   ops/server/docsurictl logs web -f     # or api / worker-*
   ```
2. Decide scope: frontend-only regression, backend regression, data-plane/config regression, or tunnel/ingress regression.

## Service-level rollback (the normal case)

```bash
cd <workspace>
git log --oneline -5                    # identify the previous good revision
git checkout <previous-good-sha>
ops/server/docsurictl rebuild           # frontend rebuild + reload web agent
ops/server/docsurictl restart all       # or a narrower target: web | api | worker-<name> | tunnel
ops/server/docsurictl status            # confirm agents + endpoints healthy
```

- launchd agents are keepalive and reload on restart; workers handle SIGTERM gracefully.
- Data-plane containers only need attention if the compose/config changed:
  ```bash
  docker compose -f backend/docker-compose.yml up -d   # from the rolled-back revision
  ```
- Return the workspace to the trunk once the forward fix is ready (the trunk is the source of truth).

## Data restore (only if data was affected)

- Daily `dev.docsuri.backup` produces a pre-existing `pg_dump` → iCloud. Restore procedure:
  1. Stop writers (`ops/server/docsurictl restart api` after stopping workers if needed) — never restore into a live writer set.
  2. Restore the dump into Postgres (compose service) from the chosen backup timestamp.
  3. Restart `api` and workers; run `docsurictl status` and verify job/result reads through the BFF.
- MinIO/OpenSearch/Redis have no separate backup agent recorded; treat them as rebuildable from source documents and the database of record. Record affected-scope honestly in the incident notes.

## Ingress / tunnel regression

```bash
ops/server/docsurictl restart tunnel
ops/server/tunnel-setup.sh <hostname>   # only if the ingress config itself is wrong (rewrites the ingress file — preserve other verified routes)
```
- Preserve the runbook's invariant: only `127.0.0.1:3000` is published; the API, datastores and Ollama stay loopback-only.

## Frontend post-rollback smoke checks

- `curl -I http://127.0.0.1:3000/paper/<id>` → 200 through the BFF.
- Asset path `/bff/api/papers/<id>/assets/<assetId>` returns an image with `cache-control: private, max-age=60` and `x-content-type-options: nosniff`; denied/missing → empty no-store 404 (never a redirect).
- Job stream `/bff/api/content-jobs/<id>/events` reconnects with `Last-Event-ID`; the 2 s fallback engages when the stream drops.

## Verification and escalation

- Post-rollback: `docsurictl status` healthy + smoke checks above; the rolled-back revision previously passed CI.
- If rollback does not stabilize the host, escalate per the incident path; capture the timeline and cause for the post-incident record. The forward fix re-enters the normal flow: trunk commit → CI green → mac-mini update + `docsurictl rebuild`.
