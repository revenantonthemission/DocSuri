# U1 Isolated PostgreSQL Bootstrap Plan

## Authority and Purpose

The human selected `B. Prepare an isolated-bootstrap plan` in `../construction/u1-job-skeleton/code-generation/code-generation-questions.md` Q4, with the exact response `Q3: 1, Q4: 2.`. The concrete proposal was then confirmed in `../inception/contract-design/contract-design-questions.md` on 2026-10-05. This is the planning handoff for a disposable real PostgreSQL test realm, not authorization to create resources, apply guest rules or run destructive fixtures.

**Accountable operator:** `revenantonthemission`.

Inputs: the U1 code-generation plan and test instructions, `../construction/u1-job-skeleton/code-generation/recovery-impact.md`, U1 infrastructure/security/performance designs, corrected `../inception/contract-design/contract-summary.md`, and actual `backend/modules/summarization/tests/u1_integration/{realm.py,conftest.py,test_migrations.py,test_owner_lifecycle.py,test_realm_preflight.py}`. The retained `tests/accounts/test_purge_real_postgres.py` remains separate, pending its Steps 15–16 guard/bridge adaptation.

The realm supplies schema/owner-lifecycle proof now and a distinct minimal-schema target for the later purge lane. It does not supply the broker/storage/provider/browser/diagnostic qualification needed by the real walking skeleton. Production `.env`, database, credentials, volumes and running releases are outside its resource scope.

## Observed Availability and Pending Qualification

Read-only observations on 2026-10-05 found Docker context `colima`, Docker server 29.5.2 on Linux arm64, and locally present `docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`, configured to run as `postgres`. These observations establish availability, not isolation or operational admission.

`ops/platform-integrity/sbom-targets.json` labels that image `CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW`, with unresolved High `CVE-2026-85091` in zlib. Its previous qualification evidence is not a U1 realm receipt. The PostgreSQL pin in `backend/docker-compose.yml` is separately superseded/rejected. The exact image/runtime closure must satisfy the existing qualification policy before application; this plan grants no exception. Do not launch the production compose stack to create test dependencies.

The database-only phase needs no broker, MinIO, inference, browser or HTTPS egress helper. Their unresolved artifact/control requirements remain on the later integrated journey. Docker context availability does not establish that modifying its guest rules is safe for existing workloads.

## Ordered Bootstrap and Qualification

| Step | Action | Required evidence or stop condition |
|---|---|---|
| P1 | Review and authorize the concrete launcher, admitted image/dependency digests, exact guest/context, resource limits, source snapshot, named network/volumes, credential channel and teardown scope | Supply actual values before application. Unresolved blocking artifact findings or placeholder commands do not authorize application |
| P2 | Inventory existing guest workloads and effective IPv4/IPv6 filtering read-only; select a non-overlapping private CIDR and fresh run-specific realm token | Record collision-free resource identities and available capacity; context/network naming alone is not isolation |
| P3 | Create a fresh internal-only database network, dedicated PostgreSQL cluster/volume and unprivileged test workload with no published ports | No host networking, production mounts/home/credentials, container socket or workload NET_ADMIN. Mount an isolated source copy read-only and keep test output separate |
| P4 | Apply reviewed forwarding/host-input rules scoped to the exact U1 identities before admitting test workloads | Preserve existing rules/workloads. Deny direct external, host, LAN, production and link-local paths; deny unsupported address families rather than claiming parity |
| P5 | Generate independent bootstrap credentials through the protected operator channel; create `docsuri_u1_authority_<realm_token>` and distinct `docsuri_u1_purge_<realm_token>` databases with separate bounded roles | Fresh cluster only. Test roles lack SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS and cross-database connection/administration authority. Credentials never enter source/public evidence/chat |
| P6 | Install an operator-owned singleton `public.u1_test_realm` marker in each database; grant test-role read access, not marker mutation | Authority database initially has no other public tables, matching the current fixture. The minimal purge schema does not share the authority/race database |
| P7 | Independently measure allowed workload → exact database access and denied direct external/host/LAN/production/unsupported-family paths; inspect mounts, rules and privileges | Retain raw safe observations and identity/hash binding. Every asserted `verified` flag must have an actual passing probe; failure keeps the realm unadmitted |
| P8 | The protected launcher derives bounded public manifest/receipt files from measured observations and supplies trusted digests through a channel the workload cannot replace | Bind workload hostname, network, image/rules, endpoint, realm and source. Expire by the authorized run's end. Any relevant configuration/identity change requires renewed qualification |
| P9 | Validate trust documents and separately probe database identity read-only before opening a mutation-capable connection; recheck identity on that connection | Match database/user/server address/port/marker/role flags. Missing, expired, writable, wrong-target or mismatched trust/identity fails before DDL/delete |
| P10 | After current C2 and narrow migration-admission repair approval, execute only implemented U1 schema/owner-lifecycle tests in the isolated frozen development closure | Preserve registered-script identity/digest/current-authority protections. Do not run raw 003 SQL around failed admission or convert missing prerequisites to skips |
| P11 | Record exact source/artifact/realm identity, command, exit code, counts, zero-skips status and scrubbed diagnostics | Distinguish real schema acceptance from guard-unit tests. The retained root purge fixture waits for its guard/bridge adaptation and separate target admission |
| P12 | Stop workloads, revoke run credentials, remove only recorded U1 containers/network/volumes/rule entries, and check original workload/rule inventory | Identity-check each removal. No global prune, production compose shutdown, shared-broker restart or unrelated-rule deletion. Preserve scrubbed evidence and supersede the receipt |

## Resource and Role Boundaries

The operational authorization must identify the exact guest/context, admitted image digest, source revision, network CIDR/name, workload hostname, database endpoint, resource limits, distinct database/role names, owned volume names and protected launcher/configuration paths. `<realm_token>` is a proposed naming parameter to materialize before authorization, not an executable placeholder.

Bootstrap privileges remain with the protected provisioner and are revoked/withdrawn from the test runtime. Each test role connects only to its own database and can perform the approved fixture DDL/data work there; it cannot modify the operator-owned realm marker or administer another database. Revoke default PUBLIC cross-database connection authority and verify actual role denials. Later real-race fixtures retain this realm ownership rather than adopting arbitrary configured DSNs.

The current authority fixture creates its schema within a forced-rollback transaction and refuses a database with other public tables. Provision only the protected marker before that lane. The minimal-schema purge database is reserved for the later adapted destructive fixture; do not install the full authority schema there or invoke its current unguarded setup.

## Public Manifest, Receipt and Secret Handoff

`backend/modules/summarization/tests/u1_integration/realm.py` consumes a manifest with `version: 1`, `unit: u1-job-skeleton`, `environment: u1-staging`, `realm_id`, `workload_hostname`, `internal_network_cidr`, `isolation_receipt_sha256`, `authority_database` and `purge_database`. Authority identity includes `host`, fixed internal `address`, integer `port`, `database` and `role`. Host aliases `localhost`, `host.docker.internal` and `host-gateway` are inadmissible.

The receipt identifies the same realm/unit/environment, timezone-aware `valid_until` and measured `verified` values `direct_egress_denied`, `host_lan_production_denied` and `unqualified_address_families_denied`. The protected launcher also binds underlying measurement output and exact workload/network/rule/image/source identities; passing the fixture's three boolean checks alone is not independent provenance.

Public trust documents are absolute regular nonsymlink files, at most 65,536 bytes, not group/other writable, with exact-byte SHA-256 hashes. The workload cannot replace their trusted digests, marker, launcher or effective filtering. Credentials and raw driver/connection errors are excluded from public output.

| Launcher variable | Required binding |
|---|---|
| `DOCSURI_U1_TEST_REALM_MANIFEST` | Absolute protected manifest path |
| `DOCSURI_U1_TEST_REALM_SHA256` | Trusted lowercase hexadecimal SHA-256 without a prefix |
| `DOCSURI_U1_ISOLATION_RECEIPT` | Absolute protected isolation-receipt path |
| `DOCSURI_U1_ISOLATION_RECEIPT_SHA256` | Trusted exact receipt hash, also referenced by manifest |
| `DOCSURI_U1_AUTHORITY_DSN` | Operator-channel secret matching exact host/database/role/port; no production/default DSN or libpq service/options/hostaddr/passfile indirection |
| `DOCSURI_U1_EVIDENCE_DIR` | Owned isolated destination for source-bound scrubbed evidence |

The separate purge connection/runner binding must be implemented and reviewed with the retained fixture adaptation. No guessed purge-DSN variable or current safe-purge claim is made by this plan.

## Schema-Only Verification Command and Evidence

From `backend/modules/summarization` inside the admitted workload and already prepared isolated frozen development environment:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest tests/u1_integration/test_migrations.py tests/u1_integration/test_owner_lifecycle.py tests/u1_integration/test_realm_preflight.py -q -rs
```

The paths exist. This command is proposed, not executed by the planning handoff. Required missing-prerequisite tests must fail, not skip. Run it only after actual isolation proof and the currently rejected registered migration's approved admission repair. The later integrated skeleton invocation remains separately human-authorized.

Evidence must identify operator authorization, actual artifacts/runtime/source hashes, context/workload/database identities, effective rule/mount inventory, paired allow/deny and role/marker-write probe results, trust-document hashes/validity, preflight results, test command/results and teardown reconciliation. Retain failed probes as failed evidence rather than emitting a successful receipt. This schema-only lane does not claim complete new-code coverage, worker/browser acceptance or release readiness.

## Alternatives and Security Implications

- **Selected:** Fresh dedicated PostgreSQL cluster in the qualified private Linux boundary with two separately scoped databases. It permits actual PostgreSQL constraint/deletion proof and protects the existing minimal purge fixture from full-schema coupling, at the cost of artifact/runtime qualification, guest enforcement and provisioner ownership.
- **Rejected:** Production loopback database or copied production credentials/schema. A name/DSN does not grant disposal authority, and the retained purge setup is destructive.
- **Rejected:** Fakes, SQLite or self-authored isolation flags as real acceptance. They do not prove PostgreSQL triggers/commit constraints or server/role/network identity.
- **Shared-host risk:** Filter/resource changes can affect existing guest workloads. Bound application to the exact reviewed identities, retain original inventory, enforce resource limits and stop testing on unexpected impact.
- **Privilege/credential risk:** Separate provisioner/test roles and protected credentials/trust documents prevent a test from authorizing its own destructive target. Marker-write, cross-database access and privilege negatives are admission requirements.

## Rollback and Pending Operational Decisions

Prepare P12 reversal before applying P3/P4. Stop only the identified U1 workload, revoke its credentials, close/remove its scoped network/rule paths, then remove identity-verified U1 containers and disposable volumes. Confirm original workloads/rules and production-facing resources match the pre-application inventory. If that cannot be established, retain the unexpected state/evidence for the accountable operator rather than guessing further cleanup.

Before any resource/rule application, `revenantonthemission` must approve the concrete admitted image/runtime/launcher, resource identities/limits, filtering, secret channel and reversal. The unresolved PostgreSQL image finding requires its existing qualification resolution; this document grants no risk disposition. No resource, guest rule, credential or database has been created or changed by the plan.
