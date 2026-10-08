# Entities — ContentJobApi

**Unit:** ContentJobApi
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Entity Definitions

### IdempotencyKey
**Owner:** ContentJobApi
**Identifier:** `key` (string, SHA-256 hex)

| Attribute | Type | Description |
|-----------|------|-------------|
| key | string | SHA-256 hex string, primary identifier |
| paperId | string | Paper identifier |
| taskType | string | Task type: 'summarize' | 'translate' | 'novelty' | 'evidence' | 'ingest_userdoc' |
| paramsHash | string | SHA-256 hash of JSON.stringify(params) |
| createdAt | number | Unix timestamp (ms) when key was generated |
| expiresAt | number | Unix timestamp (ms) when key expires (24h default) |

**References:** None (owned entirely by ContentJobApi)

---

### JobSubmission
**Owner:** ContentJobApi
**Identifier:** `jobId` (string, UUID v4)

| Attribute | Type | Description |
|-----------|------|-------------|
| jobId | string | UUID v4, primary identifier |
| taskType | string | Task type: 'summarize' | 'translate' | 'novelty' | 'evidence' | 'ingest_userdoc' |
| input | object | Task-specific input parameters |
| idempotencyKey | string | Reference to IdempotencyKey.key |
| submittedAt | number | Unix timestamp (ms) |
| status | string | 'pending' | 'submitted' | 'failed' |

**References:**
- IdempotencyKey (via idempotencyKey)

---

### JobState (Reference)
**Owner:** JobStatus (external)
**Identifier:** `jobId` (string)

| Attribute | Type | Description |
|-----------|------|-------------|
| jobId | string | UUID v4 |
| state | string | 'SUBMITTED' \| 'ACCEPTED' \| 'QUEUED' \| 'RUNNING' \| 'COMPLETED' \| 'FAILED' \| 'ABSTAINED' |
| assetId | string | Optional, set on COMPLETED |
| error | object | Optional, set on FAILED |
| progress | number | 0-100, set on RUNNING |

**References:** None (owned by JobStatus)