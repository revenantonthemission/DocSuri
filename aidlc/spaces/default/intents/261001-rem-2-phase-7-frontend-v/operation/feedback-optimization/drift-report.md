# Drift Report — DocSuri (closing stage)

Configuration/schema/documentation drift observed on 2026-10-10, with owner and remedy. Nothing here is repaired by this stage.

| ID | Drift | Evidence | Owner / remedy |
|---|---|---|---|
| ENV-01 | **Schema drift (live)**: database schema behind the API's expectation — `MigrationBlocked: NEEDS_RECONCILIATION` blocks API startup | `api.log`; service down in all checks | Owner executes the explicit reconciliation (RB-2), then restart api |
| ENV-02 | **Disk/log drift**: 96% full; `logrotate` exit 1; multi-GB rotated logs | `docsurictl status`; logrotate log | Owner fixes rotation, bounded cleanup (RB-3); disk alarm proposed |
| ENV-03 | `worker-purge` last exit 1 (one-shot) | launchd status | Owner inspects next run |
| ENV-04 | `docsurictl status` docker probe false-negative (Colima actually running) | colima status vs docsurictl output | Fix the probe script |
| OBS-01 | **Mandate drift**: "integrate Sentry" vs no Sentry init in code (dependency present) | `rg Sentry.init frontend` → nothing | Owner decision: integrate or revise the mandated rule |
| U3-SEC-02 | **Generated-artifact wording drift**: wire schema text still describes presigned URLs (backend delivers same-origin) | `types/wire/dtos.ts` (generated), shared schema | Regenerate bindings after a schema-description update (stage/release task) |
| — | **AWS configuration drift**: none remaining in workflows; no `infra/` CDK tree | `.github/workflows/` holds ci/codeql/release/branch-name/sync-stories | None — retired cleanly |
| — | **Type-drift guards**: generated types vs schema run in CI (`check:types`, `test:contracts`) | `ci.yml` frontend job | Keep green |
| — | **Traceability drift**: unit acceptance rows remain all-GAP advisory (by design) | unit `traceability.json` files | Upgrade only with executed acceptance evidence (future intents) |

## Reading

The three live operational drifts (ENV-01, ENV-02, ENV-04) are the actionable set; ENV-01 is the P2 incident already tracked. Documentation drift (OBS-01, U3-SEC-02) needs an owner decision or a regeneration pass, not code changes here.
