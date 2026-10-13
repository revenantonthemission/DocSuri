# U7 retained protocol inventory and consumer matrix — reconciliation evidence

Step 1 reconciled the retained controlled-operator protocol set from the
reference and recorded every protocol with an explicit disposition in the
machine-readable inventory at
`ops/src/docsuri_ops/platform_control/inventory.json`. It is loaded and
validated by `ops/src/docsuri_ops/platform_control/inventory.py` and seeded into
`platform_control.protocol` by `scripts/bootstrap_docsuri_u7.py`.

## Reference surfaces inspected

- `ops/server/docsurictl` — the launchd/compose operator control surface
  (`status`/`logs`/`restart`/`rebuild`/`tunnel`).
- `ops/server/README.md`, `ops/server/run.sh`, `ops/server/heartbeat.sh` — the
  single-host runbook and its health/heartbeat loop.
- `ops/runbooks/reembed-fast-rebuild.md` — a bounded local maintenance runbook.
- `ops/cdk/stacks/*.py` — the CDK-era cloud deployment stacks (recorded
  cloud-dependent dispositions, not runtime dependencies).
- `ops/local-stack/*` — the local compose stack (Postgres/Redis/OpenSearch/
  MinIO/ElasticMQ).

## Disposition summary (from `inventory.dispositions_summary`)

| Disposition | Count | Examples | Implemented here |
|---|---|---|---|
| `retained-local` | 4 | `platform.file.write`, `platform.file.probe`, `platform.credential.presence`, `platform.target.release` | yes — allowlist vocabulary, finite window/deadline, real bounded native adapter |
| `compatibility-dependent` | 1 | `evidence.http.read` | no — recorded; an authenticated HTTP binding is never a public admin bypass |
| `not-implemented-under-0` | 3 | `platform.cdk.deploy`, `platform.cloudwatch.publish`, `platform.ses.notify` | no — recorded cloud/paid dispositions, no paid fallback added |

## Consumer matrix

| Consumer | Legacy surface | Compatibility | Note |
|---|---|---|---|
| `ops-runbook` | `ops/server/docsurictl status` | recorded-only | no external CLI contract; the canonical v2 envelope replaces it |
| `ops-console` | authenticated evidence HTTP binding | compatibility-dependent | kept authenticated and bounded |
| `legacy-deploy-cli` | `ops/cdk` + CloudWatch + SES | recorded-only | no real external consumer evidenced; no legacy parity invented |

## Admission consequence

Only `retained-local` and `native-verified` protocols are admissible
(`BR3.1`/`BR3.5`). A protocol not recorded here is not callable; an unverified
native semantics fails closed. No generic command, path or shell is admitted
(`BR3.2`). No real destructive or release operation is authorised by this design
(`BR3.7`); every fixture uses synthetic targets under
`/tmp/docsuri-u7-run/targets/`.
