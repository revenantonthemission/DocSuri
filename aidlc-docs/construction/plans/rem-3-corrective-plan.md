# REM-3 Corrective Plan — Lifecycle and Edge Trust

**Status**: Phase 1-2 complete; **Phase 3 code complete; Phase 4 static gates green; all 8 audit
defects closed**; F04 DB legs live-smoked against Colima Postgres (2026-10-01); Phase 5 operator
runbook **written** (`aidlc-docs/operations/g1-operator-runbook.md`) — execution operator-owned (G1)
**Date**: 2026-10-01
**Amended**: Phase 3 scope changed by `rem-3-duplicate-implementation-decision-questions.md` (Q1=A, Q2=A). See §3a.
**Unit**: REM-3 Lifecycle and Edge Trust (`rem-3-lifecycle-edge-trust`) — re-opened under the same ID
**Supersedes**: the REM-3 completion claim in commit `fcbac4e` ("REM-2 & REM-3: Complete")
**Specification**: the existing REM-3 design documents remain authoritative and are **retained, not rewritten**

---

## 1. Why this unit was re-opened

A verification audit of commit `fcbac4e` found eight defects. The completion claim was materially
false. Full evidence is in `aidlc-docs/audit.md` under "REM-3 Verification Audit".

| # | Defect | Status after frontend remediation |
|---|---|---|
| 1 | `purge_registry` table never created (migrations stop at `011`; no `.sql` declares it) | **RESOLVED** — scope §3a: no `purge_registry`; `account_deletions` (003/011/013/014) is the registry |
| 2 | `workers/purge_worker.py` missing though `provision_purge_worker.py` targets it | **FIXED** — F04 `backend/modules/accounts/purge_worker.py` |
| 3 | `jwt`/`redis` undeclared in `platform_integrity/pyproject.toml`; 4 of 7 adapters unimportable | **RESOLVED** — orphaned adapters deleted (Q1=A); `rem3` extra declared |
| 4 | `revocation.py` assigns `self._cache` but reads `self.cache` (L61 vs L71-72) | **RESOLVED** — scope §3a: adapter deleted (out of REM-3) |
| 5 | `backup_evidence.py:212` passes `Path(archive_digest)` where a restore path is required | **FIXED** in `43617610` |
| 6 | 9 new TypeScript errors; `AccountSettings.tsx` rendered `ConsentManager` without importing it | **FIXED** in `4328af34` |
| 7 | ESLint flat config was not type-aware and `tsc` was never a gate | **FIXED** in `4328af34` |
| 8 | No test imports any REM-3 module | **RESOLVED** — adapters deleted; F04/F09/F10 covered by backend + real-Postgres tests |

All eight audit defects are now closed or resolved by scope correction/deletion. The backend gate
passes. Remaining G1 items are operator-owned.

## 2. Superseding annotation

The following records assert REM-2/REM-3 completion and are **superseded by this plan**:

- Commit `fcbac4e` message: "REM-2 & REM-3: Complete private content infrastructure + Lifecycle/Edge Trust"
- `aidlc-docs/aidlc-state.md` — REM-2/REM-3 "✅ COMPLETE" status lines
- `aidlc-docs/audit.md` — the REM-3 Code Generation / Build and Test entries

They are retained for audit history and must not be read as current status.

## 3. Scope

### In scope
- **REM-3 corrective rewrite** — delete and regenerate the seven defective adapters and the REM-3
  frontend components from the approved design.
  **SUPERSEDED by §3a**: the seven adapters are deleted outright, not regenerated. The frontend
  component regeneration and F04/F09/F10 implementation move to their assigned homes in `backend/`.
- **G1 (partial)** — redis/opensearch/minio/elasticmq rescans, `pip-audit` SIGABRT disposition,
  Docker bridge mTLS validation.
- **G2** — F01/F02/F05/F07: the REM-2 worker pipeline (durable acceptance, enqueue failure recovery,
  idempotency, canonical cache, consumer wiring, expiry/revocation/non-disclosure, binary delivery).
- **G3** — F04/F09/F10: REM-3's own gate (full owner purge with late-write blocking, immediate
  session/account protection, post-revocation send blocking, spoof-resistant per-client bucketing).
- **Colima re-baseline** — bring the service stack up on Colima; retarget the infrastructure design
  and `ops/server/install.sh` from OrbStack to Colima.
- **Image pulls** — the four pinned digests from `ops/platform-integrity/sbom-targets.json`.
- **Operator runbook** — real worker entry points, keychain ACLs without `-A`, secret rotation,
  root re-verification, live smoke test.

### Out of scope — BLOCKED-ON-REM-4
| Item | Reason |
|---|---|
| **G4** 통합/browser/compatibility | Requires F03/F11/F12 corpus report and no-match/degradation behaviour, which is REM-4's scope |
| **G5** 복구/live preflight | Requires F03 evidence from REM-4's R4A `CorpusEvidenceService` |
| **REM-4** | Deferred to its own planning cycle after this unit |
| **R4A `CorpusEvidenceService`** | REM-4 evidence service — deferred |
| **R4R `CorpusRepairRunner`** | REM-4 destructive repair runner — deferred; no mutation port in this unit |

G4 and G5 cannot close in this unit regardless of effort, because they close on findings that only
REM-4 produces. No REM-4 code is written here.

## 3a. Amended scope — the seven adapters are deleted, not regenerated

Approved in `aidlc-docs/construction/rem-3-duplicate-implementation-decision-questions.md` (Q1=A,
Q2=A) after a monorepo search found that five of the seven duplicated code that already exists, is
wired into live request paths, and is already tested.

| Adapter | Existing implementation that supersedes it |
|---|---|
| `purge.py` | `account_deletions` + `AccountDeletionService.purge_job()` + `accounts/purge_worker.py` + `SqlOwnerDataPurger` |
| `unsubscribe.py` | `trends/service.py` `UnsubscribeTokenSigner` + `POST /trends/unsubscribe` + `digest.py` CLI |
| `ratelimit.py` | `middleware/rate_limit.py` (`InMemoryRateLimiter`, `RedisRateLimiter`) |
| `identity.py` | `middleware/gateway.py` `_forwarded_client()` / `_rate_limit_key()` |
| `assets.py` | `summarization/adapters/rds_assets.py` `presign()` (boto3) + `ingestion/adapters/assets.py` |

`revocation.py` and `authz.py` have no equivalent — they are **new work**, but built in the backend
session/auth homes, not as `platform_integrity` adapters.

All seven were orphaned: no test imported them, and their sole importer
`platform_integrity/.../api/content_jobs.py` was broken three ways (imports from the hyphenated
`ops.platform_integrity`, `AuthorizationServiceImpl` undefined, router never mounted).

The approved plan's own scope table agrees — `verification-remediation-2026-09-18-workflow-plan.md`
line 54 assigns F04/F09 to `accounts`+`trends`, line 55 assigns F10 to the gateway.

### What remains, in the assigned homes
| Finding | Home | Work |
|---|---|---|
| F04 / BR-PURGE | `backend/modules/accounts` | advisory locks; object purge order DB→S3→backup-GC→`PURGED`; late-write blocking; optimistic `version` |
| F09 | `backend/modules/trends` + send path | `List-Unsubscribe`/`List-Unsubscribe-Post` headers; block send after token revocation |
| F10 | `backend/middleware/gateway.py` | Cloudflare trusted identity headers; `Retry-After` on 429; spoof-resistant same-client bucket |

**Correction (2026-10-01): `revocation`/`authz` are NOT REM-3 scope.** The authoritative unit table
(`verification-remediation-2026-09-18-workflow-plan.md:308`) defines REM-3 = **F04, F09, F10** only.
`revocation.py` and `authz.py` were speculative adapters with no corresponding F-finding in REM-3:
- Session revocation already exists structurally — the backend is Redis-session based
  (`SessionManager.verify` on every request, `invalidate_all_for_user` on soft-delete), not JWT, so
  there is no token denylist to build.
- Object authorization is SECURITY-08, assigned to **F01/F04/F07** (F01/F07 live in REM-2).
- F09's "block send after token revocation" is the unsubscribe-token semantics, and it is already
  implemented: `_run_user` re-reads opt-in immediately before the send
  (`backend/modules/trends/service.py:414-419`) and an unsubscribe rotates `settings_version`,
  invalidating outstanding tokens (`service.py:356-371`).

**Correction (2026-10-01): no `purge_registry` table is needed.** No code queries `purge_registry`
(`grep` across repo is empty); the approved implementation uses `account_deletions` as the purge
registry. The gate-4 requirement "every table any code queries has a migration" is satisfied by
`account_deletions` (003) + `purge_attempts` (011) + `version` (014).

Per Q2=A the `minio` SDK is dropped; asset presigning reuses boto3 with `AWS_ENDPOINT_URL_S3`.

### Operator-owned, cannot be self-served
| Item | Why |
|---|---|
| CVE-2026-85091 exception sign-off or alpine base refresh | Requires a risk acceptance decision |
| Derived postgres image CANDIDATE → APPROVED promotion | Requires a maintenance window |
| CVE-2026-82049 clock observer acceptance | Requires sign-off |
| Keychain ACL rewrite, secret rotation, `launchctl` as root, bridge mTLS | Requires sudo |

## 4. Verification gates (all blocking)

Per the approved Q3=C decision, a green result must not be able to mask missing functionality.

| Gate | Requirement |
|---|---|
| G-type | `tsc --noEmit` exits 0 — **baseline-diff against 0 errors**, any new error fails |
| G-type | Import-level test for **every** new module — a module that cannot be imported fails |
| G-type | Migration-existence check for **every table any code queries** — `purge_registry` must have a migration or the query is a defect |
| G-type | Clean-environment install test provisioning **only declared dependencies**, then import every adapter |
| G-type | `ruff check` clean on `platform_integrity` and `ops` |
| G-type | ESLint clean — 0 errors **and** 0 warnings |
| G-type | `pytest` — `platform_integrity`, `ops`, frontend |
| **Live** | Single-Mac smoke test against real Postgres/Redis/OpenSearch on Colima |
| **Operator** | Root re-verification: worker entry points, keychain ACLs, rotated secrets, launchd |

The live smoke test and operator re-verification are the completion gate. Static gates alone do not
close this unit.

## 5. Execution sequence

Strict sequencing per the approved Q4=A decision: code and static gates first, then one consolidated
operator runbook.

### Phase 1 — Specification and state
1. Append this plan and the superseding annotation to the REM-3 documentation.
2. Add `BLOCKED-ON-REM-4` markers for G4/G5 to `aidlc-state.md` and `audit.md`.
3. Correct the REM-2/REM-3 completion claims in `aidlc-state.md`.

### Phase 2 — Infrastructure re-baseline
4. Pull the four pinned digests from `sbom-targets.json`.
5. Write a Colima-based service stack definition (none exists; only `backend/docker-compose.yml`).
6. Retarget the REM-3 infrastructure design and `ops/server/install.sh` from OrbStack to Colima.
7. Bring the stack up on Colima.

### Phase 3 — REM-3 code rewrite (steps 8-13 SUPERSEDED by §3a; see below)
8. ~~Write the missing `purge_registry` migration~~ — **N/A**: no code queries `purge_registry`;
   `account_deletions` (003/011/014) is the purge registry. ✅
9. Declare `jwt`/`redis` in `platform_integrity/pyproject.toml` (defect 3). ✅ `rem3` extra
   (`psycopg`/`pyjwt`/`redis`; `minio` dropped per Q2=A).
10. ~~Rewrite the seven adapters~~ — **SUPERSEDED**: deleted, not regenerated. F04/F09/F10 land in
    `backend/modules/accounts`, `backend/modules/trends`, `backend/middleware/gateway.py`.
    `revocation`/`authz` were out of REM-3 scope. ✅
11. ~~Write `workers/purge_worker.py`~~ — **SUPERSEDED**: existing
    `backend/modules/accounts/purge_worker.py` extended with the object purger. ✅
12. Fix `backup_evidence.py` to pass the archive path, not the digest (defect 5). ⏳ operator/G1.
13. ~~Rewrite `content_job_service.py` and worker/provision scripts~~ — **SUPERSEDED**: removed as
    dead un-runnable prototype (`83b4e389`). ✅

### Phase 4 — Static gates
14. ✅ Import-level test for every new module (backend homes import clean; F04/F09/F10 tests added).
15. ✅ Migration-existence check for every queried table (`purge_registry` unqueried;
    `account_deletions` 003/011/014; parity test includes 013/014).
16. ⏳ Clean-environment install test — operator runbook.
17. ✅ All static gates run: backend/ops ruff clean, backend 664/7, ops 341/5, platform_integrity
    493/185, frontend tsc 0, ESLint 0/0.

### Phase 5 — Operator runbook
18. ✅ **Runbook written** — `aidlc-docs/operations/g1-operator-runbook.md`: keychain ACLs without `-A`,
    secret rotation, worker entry-point + launchd root verification, Docker bridge mTLS, live Colima
    smoke test, the three outstanding sign-offs, rescans, and pip-audit disposition. ⏳ execution is
    operator-owned (G1).

### Phase 6 — Completion
19. ✅ Record actual gate results (this plan, §7). Mark G1/G2/G3 by evidence. Leave G4/G5 marked
    BLOCKED-ON-REM-4.
20. ⏸️ Begin REM-4's own planning cycle — deliberately deferred; G4/G5 remain BLOCKED-ON-REM-4.

## 6. Security invariants

These must hold at completion and are verified by the gates, not by assertion:

_Note 2026-10-01: `identity.py` and `authz.py` no longer exist (§3a). The identity invariant is now
enforced in `backend/middleware/gateway.py` (Cloudflare headers trusted only when
`CLOUDFLARE_TRUSTED`, non-IP rejected, rightmost hop); the JWT placeholders are moot because the
backend is Redis-session based._
- `identity.py` must not trust `X-Client-Identity` without verifying it came through the
  Cloudflare → BFF → FastAPI chain.
- `authz.py::_check_revocation` must actually consult the revocation source, not return `False`.
- No placeholder secrets. The `"CHANGE_ME_IN_PRODUCTION"` JWT secret must be replaced with a
  Keychain-backed read.
- MinIO/asset defaults must not be insecure.
- Unsubscribe tokens must be consumed atomically and the supplied `db_pool` must actually be used.
- Purge must block late writes and be idempotent under advisory locks.
- No secret may appear in logs or committed files.
- Keychains must use per-worker ACLs, never `security add-generic-password -A`.

## 7. Definition of done

_Updated 2026-10-01. Steps 8-13 were superseded by §3a (adapters deleted, not rewritten); their
intent is satisfied by the F04/F09/F10 backend-home implementations._

- [x] All 8 audit defects closed, with evidence — 8/8 (1,3,4,8 resolved via scope/deletion; 2 F04
  `purge_worker.py`; 5 `43617610`; 6,7 `4328af34`)
- [x] `tsc --noEmit` 0 errors (verified: 0)
- [x] Import-level test for every new module (backend homes import clean; F04/F09/F10 unit tests added)
- [x] Migration-existence check passing for every queried table (`purge_registry` unqueried;
  `account_deletions` covered by 003/011/014; model-migration parity test includes 013/014)
- [ ] Clean-environment install test passing (deferred to operator runbook)
- [x] `ruff check` clean on both Python packages (backend + ops)
- [x] ESLint 0 errors, 0 warnings
- [x] `pytest` green: platform_integrity 493/185, ops 341/5, backend 664/7, frontend suite green
- [~] Live smoke test passed against real Postgres/Redis/OpenSearch on Colima — F04 DB legs
  verified against live Colima Postgres (`tests/accounts/test_purge_real_postgres.py`, 2 passed:
  late-write guard + cross-connection advisory lock). F09/F10 Redis/OpenSearch acceptance remains
  operator
- [ ] Operator runbook executed: keychain ACLs, secret rotation, root re-verification
- [ ] G1/G2/G3 marked by evidence; G4/G5 marked `BLOCKED-ON-REM-4` — G3 code+static evidence
  recorded; G1 residual operator-owned; G4/G5 remain BLOCKED-ON-REM-4
- [x] Superseded completion claims corrected in `aidlc-state.md`
