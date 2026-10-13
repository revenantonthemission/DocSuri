# DocSuri v2 — U7 Infrastructure Design questions

Date: 2026-10-13 (Asia/Seoul). Basis: the U7 NFR design
([performance](../nfr-design/performance-design.md), [security](../nfr-design/security-design.md),
[scalability](../nfr-design/scalability-design.md), [reliability](../nfr-design/reliability-design.md),
[observability](../nfr-design/observability-design.md), [logical components](../nfr-design/logical-components.md)),
the [functional specification](../functional-design/functional-spec.md) and contract C10
([contract-summary.md](../../../inception/contract-design/contract-summary.md)).

## Context and established answers

| Topic | Established | Infrastructure consequence |
|---|---|---|
| Budget | $0/local only; no AWS runtime (project memory; NFR8.5) | No cloud provisioning/IaC; local host + local PostgreSQL only |
| Runtime | Python operator executable; local stdin/stdout JSON (tech stack) | A local process, not a deployed service |
| Store | Shared local PostgreSQL with a dedicated `PlatformControl` schema + role (NFR tech stack; nfr-design Q2) | One local instance, owner-isolated schema, U7-owned migrations |
| Executor | Bounded child process per effect (nfr-design Q1) | Host process supervision; resource caps via the OS |
| CI | U1 added a scoped workflow; interim policy tolerates pre-existing legacy CI failures | A scoped U7 workflow, no deploy-on-merge |

## Proposed design work

Produce `infrastructure-specification.md` (deployment + services + shared,
tabular), `monitoring-design.md` (tabular), `cicd-pipeline.md` and
`traceability.json`.

## Q1 — Packaging and deployment shape

U7 must be independently executable with no application prerequisite.

- A. A standalone local executable (the operator CLI plus a small local supervisor for start/stop/backup), runnable on the same host as the application; no container required, an optional local container is not a dependency.
- B. Package U7 as a container in the local compose stack like the application.
- C. Decide at implementation; record only the standalone-executable requirement.
- X. Other (please specify)

[Answer]: A

## Q2 — Shared PostgreSQL boundary

U7 shares the local PostgreSQL instance with the application (nfr-design Q5/Q2).

- A. Same local instance, separate `PlatformControl` schema and its own non-login role; U7 owns and applies its schema migrations through its own setup; the application's roles cannot touch the schema and U7's role touches nothing else.
- B. A dedicated PostgreSQL instance/volume just for U7.
- C. Same schema as the application; rely on table-level grants.
- X. Other (please specify)

[Answer]: A

## Q3 — CI/CD scope

The interim v2 CI policy tolerates pre-existing legacy failures; U7 has no cloud deploy.

- A. A scoped `.github/workflows/u7-controlled-platform-protocols.yml` (lint/typecheck/U7 tests; database/service-dependent phases documented as unexecuted required evidence in CI); no deploy-on-merge, no cloud release.
- B. Full U7 integration (spin up local PostgreSQL in CI) for every push.
- C. No CI for U7; local checks only.
- X. Other (please specify)

[Answer]: A

## Q4 — Monitoring and alerting

U7 is a local operator CLI with no telemetry vendor (observability design).

- A. Local structured receipts are the primary evidence; a small bounded local metrics/status view (receipt counts, unresolved unknowns) plus the operator-visible unresolved list; no hosted metrics, no paging alerts (a CLI has no always-on alert target).
- B. Ship metrics to a hosted (free-tier) service.
- C. Local log file only; no metrics view.
- X. Other (please specify)

[Answer]: A

## Q5 — Secrets and credential handling

Native filesystem/keyring semantics must be preserved (NFR4.9) and no secrets in CI/logs (NFR5.3).

- A. Operator-native credentials come from the OS (keyring/files the operator already controls); the U7 database role's credential comes from a local, non-committed config/env file; nothing secret enters CI, receipts or logs.
- B. Store operator credentials in the `PlatformControl` schema encrypted.
- C. Use environment variables for everything including operator credentials.
- X. Other (please specify)

[Answer]: A

## Assumptions & Open Questions

- Assumption: no cloud resources, no IaC beyond local compose/supervisor scripts; the CDK-era artifacts remain recorded cloud-dependent dispositions.
- Assumption: the `PlatformControl` schema migrations are U7-owned and idempotent on a fresh local setup.
- Open: concrete resource caps (child-process memory/CPU, queue depth) are filled with the retained-inventory reconciliation and a measured baseline.

## Sources

- NFR design files under `../nfr-design/`
- [functional-spec.md](../functional-design/functional-spec.md)
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10
- [project memory](../../../../../memory/project.md) — $0 budget

## Consolidated Summary Confirmation

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
