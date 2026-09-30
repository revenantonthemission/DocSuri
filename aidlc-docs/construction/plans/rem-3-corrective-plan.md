# REM-3 Corrective Plan — Lifecycle and Edge Trust

**Status**: APPROVED SCOPE — execution not yet started
**Date**: 2026-10-01
**Unit**: REM-3 Lifecycle and Edge Trust (`rem-3-lifecycle-edge-trust`) — re-opened under the same ID
**Supersedes**: the REM-3 completion claim in commit `fcbac4e` ("REM-2 & REM-3: Complete")
**Specification**: the existing REM-3 design documents remain authoritative and are **retained, not rewritten**

---

## 1. Why this unit was re-opened

A verification audit of commit `fcbac4e` found eight defects. The completion claim was materially
false. Full evidence is in `aidlc-docs/audit.md` under "REM-3 Verification Audit".

| # | Defect | Status after frontend remediation |
|---|---|---|
| 1 | `purge_registry` table never created (migrations stop at `011`; no `.sql` declares it) | OPEN |
| 2 | `workers/purge_worker.py` missing though `provision_purge_worker.py` targets it | OPEN |
| 3 | `jwt`/`redis` undeclared in `platform_integrity/pyproject.toml`; 4 of 7 adapters unimportable | OPEN |
| 4 | `revocation.py` assigns `self._cache` but reads `self.cache` (L61 vs L71-72) | OPEN |
| 5 | `backup_evidence.py:212` passes `Path(archive_digest)` where a restore path is required | OPEN |
| 6 | 9 new TypeScript errors; `AccountSettings.tsx` rendered `ConsentManager` without importing it | **FIXED** in `4328af34` |
| 7 | ESLint flat config was not type-aware and `tsc` was never a gate | **FIXED** in `4328af34` |
| 8 | No test imports any REM-3 module | OPEN |

The frontend half of the gate now passes. The backend half fails.

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

### Phase 3 — REM-3 code rewrite
8. Write the missing `purge_registry` migration (defect 1).
9. Declare `jwt`/`redis` in `platform_integrity/pyproject.toml` (defect 3).
10. Rewrite the seven adapters: `purge`, `unsubscribe`, `identity`, `ratelimit`, `revocation`,
    `authz`, `assets`. Delete first; the approved design is the specification.
11. Write `workers/purge_worker.py` with a real runnable entry point (defect 2).
12. Fix `backup_evidence.py` to pass the archive path, not the digest (defect 5).
13. Rewrite `ops/platform-integrity/content_job_service.py` and the worker/provision scripts so each
    worker has a genuine CLI entry point and no placeholder job-state digests.

### Phase 4 — Static gates
14. Add the import-level test for every new module.
15. Add the migration-existence check for every queried table.
16. Add the clean-environment install test.
17. Run all static gates until every one passes.

### Phase 5 — Operator runbook
18. Write one consolidated runbook: keychain ACLs without `-A`, secret rotation, worker entry-point
    verification, launchd bootstrap/verify as root, Docker bridge mTLS, live smoke test, and the
    three outstanding sign-offs.

### Phase 6 — Completion
19. Record actual gate results. Mark G1/G2/G3 by evidence. Leave G4/G5 marked BLOCKED-ON-REM-4.
20. Begin REM-4's own planning cycle.

## 6. Security invariants

These must hold at completion and are verified by the gates, not by assertion:

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

- [ ] All 8 audit defects closed, with evidence
- [ ] `tsc --noEmit` 0 errors (baseline-diff enforced)
- [ ] Import-level test for every new module
- [ ] Migration-existence check passing for every queried table
- [ ] Clean-environment install test passing
- [ ] `ruff check` clean on both Python packages
- [ ] ESLint 0 errors, 0 warnings
- [ ] `pytest` green: `platform_integrity`, `ops`, frontend
- [ ] Live smoke test passed against real Postgres/Redis/OpenSearch on Colima
- [ ] Operator runbook executed: keychain ACLs, secret rotation, root re-verification
- [ ] G1/G2/G3 marked by evidence; G4/G5 marked `BLOCKED-ON-REM-4`
- [ ] Superseded completion claims corrected in `aidlc-state.md`
