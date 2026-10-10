# Q8 Remediation Investigation and Colima Launcher Handoff

Prepared under Q8 option A (`code-generation-questions.md`, line 250: `[Answer]: A. Investigate remediation and prepare the launcher handoff`). This document is **preparation for review**. It grants itself no authority: no image build or pull, no provisioning, no guest-rule application, no credential-channel application, and no vulnerability exception. Those remain separate concrete authorizations. `ops/server/u1_db_bootstrap.py` was not modified — its bytes are bound by `config.launcher_digest`.

Date of investigation and host observation: 2026-10-06.

---

## 1. Remediation investigation — CVE-2026-85091

### 1.1 Current recorded state

`ops/platform-integrity/sbom-targets.json` (read-only evidence, unchanged by this work):

- `images.postgres` / `derivedImages.postgres.digest` = `docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`
- `derivedImages.postgres`: 865 components, 4 findings, **1 blocking**
- `remaining`: "CVE-2026-85091 alpine zlib 1.3.2-r0 High with no fix state; needs an alpine base refresh or a documented time-boxed exception"
- `status`: `CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW`
- `verified`: 280 passed / 89% statement coverage / actual loopback mTLS against this image on 2026-09-26

### 1.2 Package-feed evidence (read-only checks, 2026-10-06)

| Source | Result |
|---|---|
| Alpine package feed `APKINDEX` (`v3.21`, `v3.22`, `v3.23`, `v3.24`, `edge`) | `zlib 1.3.2-r0` still the current package — no newer release |
| Alpine package feed `v3.25` | no `zlib` entry yet |
| Alpine secdb advisories (`https://secdb.alpinelinux.org/{v3.21,v3.24,edge}/main.json`) | no `zlib` advisory published — no fixed package to move to |
| Alpine vulnerability tracker tables | empty for this CVE — no vendor fix state |
| Ubuntu tracker | fix deferred across all releases |
| Debian tracker | unfixed |

**Conclusion: there is no fixed, pinned PostgreSQL/base closure available today.** A base refresh (runbook `ops/platform-integrity/runbooks/g1-operator-runbook-2026-10-01.md` §1.1 Option B) repulls `zlib 1.3.2-r0` and therefore **cannot clear this finding**.

### 1.3 Vulnerability mechanics

- Heap overflow in `gz_vacate()`, reachable through non-blocking `gzwrite()` / `gzprintf()` on the deflate side; affected range zlib 1.3.1.2 – 1.3.2 (the image's `1.3.2-r0` is in range).
- Upstream fix commit `df84af25...` (truncated in the tracker record reviewed here) requires zlib ≥ 1.3.3; no distro has shipped an equivalent backport.

### 1.4 Reachability — explicitly unverified

Whether PostgreSQL (or anything else invoked in this image) ever reaches the `gz*` call path with a non-blocking stream **has not been verified**. This is stated as unverified rather than "not exploitable": any future exception rationale must first prove reachability (or its absence) from this image's actual code path, and no such proof exists yet.

### 1.5 Options that remain (each needs its own authorization)

1. **Time-boxed exception with compensating controls** — document the CVE, the unverified reachability, the compensating controls (no untrusted gzip input into the container; network egress denied by the owned `DOCKER-USER` rules below; read-only rootfs; `no-new-privileges`; cap-drop ALL) and an expiry. Q8 option A explicitly does **not** grant a vulnerability exception; that is a separate human decision.
2. **Self-built patched zlib in the derived image** — build the `df84af25...` fix on top of the pinned base. Precedent warns us: the clock-runtime candidate carries a real backport of CVE-2026-82049 and Grype **still** reports it unfixed, so the scanner finding will most likely persist and require its own documented disposition (`sbom-targets.json` → `nativeRuntimes.clockObserver.notes`).

Neither option is executed here. Until one is chosen and authorized, `CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW` stands.

---

## 2. Prepared launcher package

| File | Role |
|---|---|
| `ops/server/u1_colima_executor.py` | Concrete `ColimaExecutor` implementing the `bootstrap.OperatorExecutor.execute` port for all 17 plan actions, plus `CommandRunner`, `ColimaGuest`, `RefusingGuest`, `CredentialChannel`, `RuntimeBindings`, `tree_digest`, `rule_spec`/`rule_spec_digest`/`rule_argv`, `_normalize_iptables`, `_trusted_owner`, `_protected_bytes`, `_protected_file_sha`, `_write_secret`, and a digest-only CLI. |
| `ops/tests/test_u1_colima_executor.py` | 12 local negative tests: prepared-executor refusals, unknown-op/identity/weakened-flag refusals, ownership + digest tampering, refusing-guest default, comment-scoped rule apply/remove, label-gated deletion, credential lifecycle (deliver → withdraw → revoke → remove), channel scope/completeness, full 9-action bootstrap and 8-action owned reversal via fake runner/guest, postgres/workload argv pinning, source-digest/protected-binding gating, read-only digest CLI. |
| `ops/server/u1_db_bootstrap.py` | **Unchanged** inspect-only plan/admission authority (byte-stable). |

The executor refuses rather than applies: unknown operations, wrong identities, weakened plan flags, wrong context/executable/digests, foreign channel files, untrusted ownership, missing/weak guest authorization, present-but-unowned resources, label mismatches, source-digest mismatches and absent hook chain all raise `ExecutorRefused` with a specific category before any command runs.

### 2.1 Verification commands and results (from `ops/`, 2026-10-06)

```
uv run --frozen --no-sync ruff check server tests          -> All checks passed!   (ruff 0.16.8, line-length 100, select E,F,I,UP,B)
uv run --frozen --no-sync python -m pytest tests/ -q        -> exit 0; 394 collected across 23 files, 5 root-only skips
uv run --frozen --no-sync python -m pytest tests/test_u1_colima_executor.py tests/test_u1_db_bootstrap.py -q
                                                           -> exit 0; 12 + 35 passed
```

No live docker/colima invocation, no root-owned file, no guest mutation and no operator receipt is produced by these tests: fake channels stand in for host and guest.

### 2.2 Digest CLI (read-only, `applied: false` always)

```
uv run --frozen --no-sync python -m server.u1_colima_executor self-digest
uv run --frozen --no-sync python -m server.u1_colima_executor tree-digest <read-only source root>
uv run --frozen --no-sync python -m server.u1_colima_executor rule-spec --config <public.json> --sha256 <sha256 of those bytes>
```

Observed values on this host (they change if the bound files change — re-derive, never paste):

- `executor_sha256` (`self-digest`): `3fa6d14dfd244278fd63a41a9837dc193cb756d409bfe76d502dd1094803e489`
- `launcher_digest` (`sha256(ops/server/u1_db_bootstrap.py)`): `d97fb57229d30f1ee4a5e1d3af556f5bd7a5124bbda5be19965f4bed6636e9e0`

Inspect-only plan report (never applies anything):

```
uv run --frozen --no-sync python -m server.u1_db_bootstrap --config <public.json> --sha256 <sha256 of those bytes>
```

---

## 3. Public configuration — field-by-field derivation

The configuration is a public, digest-pinned JSON document validated by `BootstrapConfig` (`ops/server/u1_db_bootstrap.py`). Every digest below is **derived from a real source**, never chosen:

| Field | Derivation | State |
|---|---|---|
| `version` | literal `1` (type-checked strictly) | ready |
| `unit` | literal `u1-job-skeleton` | ready |
| `environment` | literal `u1-staging` | ready |
| `realm_id` | fresh `^[a-f0-9]{16}$` token, one per isolated realm; prefixes all resource names `docsuri-u1-<realm_id>-{net,data,pg,test,credentials}` | operator-generated at run time |
| `context` | active docker context name; observed `colima *` (`docker context ls`, 2026-10-06) and must equal the runner's context or construction refuses `context_mismatch` | observed |
| `guest_id` | SHA-256 of the canonical pre-bootstrap inventory snapshot payload — the exact JSON `{"containers","networks","volumes","rules_v4","rules_v6"}` read by `verify_original_inventory` before any mutation | **not yet measured** (no live measurement authorized) |
| `runtime_digest` | SHA-256 of the recorded runtime evidence the operator relies on (`colima status` + `docker version`: observed `linux arm64`, dockerd `29.5.2`, colima running on macOS Virtualization.Framework, aarch64, 2026-10-06); bound into every admission document as `runtime_sha256`, so a changed runtime invalidates admission | **not yet measured** |
| `source_digest` | `tree-digest <root>` over the read-only source copy (relative path + mode + bytes) | ready (command verified) |
| `launcher_digest` | `sha256(ops/server/u1_db_bootstrap.py)` — the file is byte-stable; editing it breaks every admission binding | ready (`d97fb572...` observed) |
| `rules_digest` | `rule-spec --config <public.json> --sha256 <bytes>` — canonical SHA-256 of the owned rule specification in §4 | ready (command verified) |
| `postgres_image` | pinned `docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`, present locally with `Config.User=postgres` (verified 2026-10-06) | qualified-candidate only — see §1 |
| `workload_image` | pinned `docsuri/u1-tests@sha256:<digest>` of the u1 test workload image | **qualification still open** |
| `postgres_uid` | uid of the `postgres` user **inside** the pinned image (`id -u postgres`), not a host uid | derive at build/qualification |
| `workload_uid` | uid of the unprivileged user inside the workload image | derive at build/qualification |
| `operator_uid` | the human operator's uid running the executor | run-time |
| `workload_hostname` | fixed name `u1-test` | ready |
| `internal_network_cidr` | private IPv4 `/24`–`/28`, strict, non-overlapping with any existing network; admission re-checks `nonoverlapping_cidr` and `fresh_resources_absent` | operator-chosen, re-checked |
| `authority_database` | `{host:"postgres-u1", address:<fresh subnet .2>, port:5432, database/role:"docsuri_u1_authority_<realm_id>", connection_limit:4}` | per-realm |
| `purge_database` | same shape with `docsuri_u1_purge_<realm_id>`, `connection_limit:2` | per-realm |
| `memory_bytes` | ≥ 134217728 (128 MiB) | operator-chosen within bound |
| `cpus` | 1–64 | operator-chosen within bound |
| `disk_reserve_bytes` | ≥ 134217728 | operator-chosen within bound |
| `max_connections` | 16–100 | operator-chosen within bound |
| `credential_channel_digest` | `sha256` of the prepared channel file bytes (§5) | derived at channel preparation |
| `valid_until` | RFC3339 UTC inside the operator's window; equal to the channel's `valid_until`; admission rejects expired documents | operator-chosen |

---

## 4. Resource limits, identities and scoped network rules

### 4.1 Cluster and workload boundaries (as enforced by the executor)

`start_private_postgres` pins, from the plan and refused on any deviation: `--ip <address>` on the fresh internal network, `--user <postgres_uid>`, `--read-only` rootfs, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit`, memory/cpus from config, `--restart` policy, explicit labels `unit=`, `realm_id=`, `environment=`. Refused outright: `--privileged`, `--network host`, any published port (`published_ports` must be `()`), any extra capability, `read_only_root` not `True`, `ipv6` not `False` on the owned network (it stays v4-only), and `image` not exactly the pinned digest (`image_identity_mismatch`).

`start_unadmitted_probe_workload` additionally pins: `--hostname u1-test`, `--user <workload_uid>`, `source_read_only`, `output_separate`, `host_home_socket_mounts = ()`, `external_networks = ()` (no egress escape hatches), `--env-file` for the DSN (§5), and `source_digest` equality with the measured read-only source copy.

Provisioning runs as `provisioning_sql(config)`: marker role `NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`, per-purpose roles with `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 4|2`, `TEMPLATE template0` databases, `REVOKE ... FROM PUBLIC`, marker-owned `u1_test_realm` table with `GRANT SELECT` only, and password-free SQL (passwords are channel-owned and delivered on stdin only).

### 4.2 Owned `DOCKER-USER` rules (`config.rules_digest` binds this spec)

Canonical spec from `rule_spec(config)` — allow the realm CIDR to itself first, then drop everything else:

| # | Match (all carry `-m comment --comment docsuri-u1-<realm_id>`) | Target |
|---|---|---|
| 1 | `-s <cidr> -d <cidr>` | `RETURN` |
| 2 | `-d 127.0.0.0/8` | `DROP` |
| 3 | `-d 169.254.0.0/16` | `DROP` |
| 4 | `-d 10.0.0.0/8` | `DROP` |
| 5 | `-d 172.16.0.0/12` | `DROP` |
| 6 | `-d 192.168.0.0/16` | `DROP` |
| 7 | `-d 0.0.0.0/0` | `DROP` |
| v6 | single `ip6tables` DROP for the realm (unsupported IPv6 denied by rule, not by config) | `DROP` |

Properties: appended with `-A` (safe because the fresh realm CIDR cannot already match any pre-existing rule), removed only by **exact-argument** `-D` with the identical argv (`rule_argv` is shared by add and delete), `preserve_original_rules` = `True` (nothing pre-existing is ever deleted), `deny_ipv4_external_host_lan_production` = `True`, `deny_unsupported_ipv6` = `True`. The executor refuses to apply when the measured hook chain is absent (`ipv6_hook_unavailable`) and refuses double-apply (`owned_rules_already_present`) / removal when absent (`owned_rules_absent`).

---

## 5. Protected credential channel and secret delivery

- **Channel file** (operator-prepared): JSON `{version:1, realm_id, valid_until, postgres_superuser_password, authority_password, purge_password}`, canonical encoding, ≤ 64 KiB. Read requirements enforced by `_protected_bytes`: absolute path, no symlink anywhere in the parent chain, **owner uid 0** for the file *and every parent*, **no group/other write** on parents (`& 0o022`), regular file, **no write bit at all** on the file itself (`& 0o222` — i.e. `0444`-style immutability), size ≤ 65536, SHA-256 equal to `config.credential_channel_digest`. Passwords must match `^[A-Za-z0-9._~+=/-]{16,128}$`; `realm_id` must equal the config's `^[a-f0-9]{16}$`.
- **Scope order**: registered digest → parse → `realm_id` → `valid_until` → completeness. A foreign file refuses with `credential_channel_digest_mismatch` before it is ever parsed; a right-digest/wrong-realm or expired channel refuses `credential_channel_scope_mismatch`; a missing key refuses `credential_channel_incomplete`.
- **Delivery**: `deliver_protected_credentials` re-checks the plan's `channel_digest`, `postgres_uid`, `workload_uid`, `read_only_workload` and writes `secrets_dir/{u1_superuser_password,u1_authority_password,u1_purge_password,u1_authority_dsn.env}` with `os.open(..., 0o600)`; `secrets_dir` must be absolute and mode `0700` exactly (`secrets_dir_invalid`), and any `OSError` surfaces as `credential_write_failed`.
- **No argv leakage**: the provisioner password reaches `psql` **on stdin only**. The workload DSN reaches the container only via `--env-file <secrets_dir>/u1_authority_dsn.env` (`DOCSURI_U1_AUTHORITY_DSN=<dsn>`), never as an argv value (invisible to `ps`), and never in the launcher process environment (`inspect_file` refuses a DSN there).
- **Withdrawal**: `withdraw_provisioner_credentials` deletes the superuser file only when its bytes still equal the channel value (`provisioner_credential_missing` otherwise).
- **Revocation**: `revoke_run_credentials` validates identity/digest **before** unlinking anything, deletes all remaining secret files plus the channel itself, and clears the cached secrets; a second revoke refuses `run_credentials_absent`. `remove_identity_verified_credentials` removes the empty `0700` secret directory only after confirming every file inside is already gone.
- **Manifest/receipt binding**: `RuntimeBindings.from_channel` re-derives `manifest_sha256` / `receipt_sha256` from the protected files and builds the authority DSN; an untrusted owner or symlink in that chain refuses at once.

---

## 6. Owned reversal

The plan's reversal executes in order and only under label/comment identity checks:

1. `stop_identity_verified_workload` (labels)
2. `revoke_run_credentials` (channel + secrets removed, cache cleared)
3. `stop_identity_verified_cluster` (labels)
4. `remove_identity_verified_volume` (labels)
5. `remove_identity_verified_credentials` (empty `0700` dir only)
6. `remove_owned_guest_rules` (exact-args `-D`, comment-scoped, `owned_rules_absent` if already gone)
7. `remove_identity_verified_network` (labels; refuses `owned_resource_label_mismatch` if relabelled)
8. `reconcile_original_inventory` (re-measure; must match `guest_id`)

Reversal is idempotent-refusing, not destructive-blind: each step refuses on absence, wrong owner/label, or identity mismatch rather than deleting anything that is not provably the owned resource.

---

## 7. Operator review checklist before any authorization (P1–P12 preamble)

- [ ] Q8 option A scope observed: this record is preparation only; nothing below has been applied.
- [ ] `sha256(ops/server/u1_db_bootstrap.py)` still equals `config.launcher_digest` (observed `d97fb572...`); the file was not edited.
- [ ] `self-digest` equals the reviewed `executor_sha256` (observed `3fa6d14d...`); re-derive after any edit.
- [ ] `source_digest` re-derived with `tree-digest` against the actual read-only copy that will be mounted.
- [ ] `rules_digest` re-derived with `rule-spec` against the final `public.json` bytes.
- [ ] `postgres_image` is still exactly the pinned `@sha256:` ref; no floating tags.
- [ ] CVE-2026-85091 disposition decision made **explicitly** (§1.5: time-boxed exception or patched-zlib rebuild) — never implied by proceeding.
- [ ] Workload image qualification completed (§3, `workload_image` row).
- [ ] `guest_id` / `runtime_digest` measured on the guest before mutation (§3 rows marked not yet measured).
- [ ] Admission documents (auth/qualification/inventory) bound to every field of the config digest, valid at run time, `operation` matching the attempted purpose.
- [ ] Channel file prepared root-owned, immutable, digest-pinned; secrets directory `0700`.
- [ ] Hook chain (`DOCKER-USER`) measured read-only first; owned CIDR confirmed non-overlapping and fresh.
- [ ] Separate concrete authorizations obtained for: image build/pull, provisioning, guest-rule application, credential application.

---

## 8. Unavailable fixes and remaining qualifications

- **No fixed zlib package exists** in the Alpine feed or secdb; Ubuntu and Debian are unfixed; upstream fix needs zlib ≥ 1.3.3 (§1.2–1.3). The base-refresh remedy cannot clear the finding.
- **Reachability of `gz*` in this image is unverified** (§1.4) — required input for any exception rationale.
- **Self-built patched zlib** will likely keep the scanner finding alive (CVE-2026-82049 precedent) and needs its own disposition.
- **No vulnerability exception is granted here.** Q8 option A explicitly excludes it.
- **Workload image qualification is open**; `workload_image` has no qualified digest in this record.
- **`guest_id` and `runtime_digest` are unmeasured**; both must be measured live before admission.
- **No live execution occurred**: no image build/pull, no container/network/volume creation, no iptables change, no credential write, no root-owned file, no operator receipt.
- Unrelated but unchanged blockers remain visible in `sbom-targets.json`: redis/opensearch/elasticmq `SCANNED_BLOCKING_FINDINGS_PENDING_DISPOSITION`, `minio` `UNOBTAINABLE`.

---

## 9. Sources

- `ops/platform-integrity/sbom-targets.json` (read, unchanged)
- Alpine `APKINDEX` feeds for `v3.21`–`v3.24` and `edge`; `https://secdb.alpinelinux.org/{v3.21,v3.24,edge}/main.json` (read-only, 2026-10-06)
- Alpine/Ubuntu/Debian vulnerability tracker records for CVE-2026-85091 (read-only, 2026-10-06)
- `ops/platform-integrity/runbooks/g1-operator-runbook-2026-10-01.md` §1.1, §2
- `ops/server/u1_db_bootstrap.py` (read, unmodified), `ops/tests/test_u1_db_bootstrap.py`
- `ops/server/u1_colima_executor.py`, `ops/tests/test_u1_colima_executor.py` (written under Q8-A)
- Host observations 2026-10-06: `docker context ls`, `docker image inspect`, `colima status`, `docker version`
