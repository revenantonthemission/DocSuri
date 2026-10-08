# Business Rules — IdempotencyService

**Unit:** IdempotencyService
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-IDS-001: Deterministic Key Generation
**Description:** Idempotency keys MUST be deterministically generated from input parameters.
**Algorithm:** SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)`
**Properties:**
- Same inputs → Same key (deterministic)
- Different inputs → Different key (collision-resistant)
- Cryptographically secure (SHA-256)

### BR-IDS-002: LocalStorage Persistence
**Description:** Idempotency keys MUST survive page reloads.
**Storage:** localStorage with key format `idempotency:{paperId}:{taskType}`
**Expiration:** 24 hours from creation (configurable via `IDEMPOTENCY_TTL_MS` env)
**Cleanup:** Expired keys removed on `getKey()` call

### BR-IDS-003: Key Uniqueness per Paper/Task
**Description:** Exactly one idempotency key per `paperId:taskType` combination.
**Behavior:**
- `generateKey()` with same inputs → returns existing key if not expired
- Different `params` → new key generated
- Manual clear via `clearKey(paperId, taskType)`

### BR-IDS-004: Key Retrieval for Retry
**Description:** Retry operations MUST retrieve stored key for deduplication.
**Behavior:**
- `getKey(paperId, taskType)` returns stored key or `null`
- On retry: retrieve key → pass to `ContentJobApi.submitJob()`
- Backend returns existing job on 409 Conflict (idempotent)

### BR-IDS-005: Key Expiration & Cleanup
**Description:** Expired keys MUST be automatically removed.
**Policy:** 
- TTL: 24 hours (configurable)
- Checked on `getKey()` call
- Expired entries deleted from localStorage
- Orphaned keys (no matching job) cleaned on next `generateKey()`

---

## Data Invariants

### Invariant: Key Determinism
**Statement:** `generateKey(userId, paperId, taskType, params)` with identical inputs ALWAYS returns identical key.
**Violation:** SHA-256 implementation bug.

### Invariant: Key Uniqueness per Paper/Task
**Statement:** At most one active key per `paperId:taskType` in localStorage.
**Violation:** Multiple keys for same paper/task → storage corruption.

### Invariant: Key Expiration
**Statement:** Keys older than TTL are not returned by `getKey()`.
**Violation:** Expired key used for retry → backend treats as new job.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| localStorage unavailable | `QuotaExceededError` / `SecurityError` | Fallback to in-memory Map; warn user |
| Corrupted localStorage data | JSON parse error | Clear corrupted entry, regenerate |
| Crypto.subtle unavailable | `crypto.subtle` undefined | Polyfill or fallback to non-crypto hash |
| Key collision (theoretical) | Duplicate key for different params | Extremely unlikely (2^256); log warning |