# Entities — JobStatus

**Unit:** JobStatus
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Entity Definitions

### JobState
**Owner:** JobStatus
**Identifier:** `jobId` (string, UUID v4)

| Attribute | Type | Description |
|-----------|------|-------------|
| jobId | string | UUID v4, primary identifier |
| state | string | 'SUBMITTED' \| 'ACCEPTED' \| 'QUEUED' \| 'RUNNING' \| 'COMPLETED' \| 'FAILED' \| 'ABSTAINED' |
| assetId | string | Optional, set on COMPLETED |
| error | object | Optional, set on FAILED |
| progress | number | 0-100, set on RUNNING |
| connectionState | string | 'connecting' \| 'connected' \| 'reconnecting' \| 'polling' \| 'disconnected' |
| eventHistory | array | Array of `{ state, timestamp, payload }` |

**References:** None (owned by JobStatus)

---

### JobEvent
**Owner:** JobStatus
**Identifier:** `eventId` (string)

| Attribute | Type | Description |
|-----------|------|-------------|
| eventId | string | UUID v4 |
| jobId | string | Job identifier |
| state | string | Current job state |
| timestampUs | number | Microsecond timestamp |
| payload | object | Optional: `{ assetId?, error?, abstainReason? }` |

**References:**
- JobState (owned by JobStatus)

---

### IdempotencyKey (Reference)
**Owner:** IdempotencyService (external)
**Identifier:** `key` (string)

| Attribute | Type | Description |
|-----------|------|-------------|
| key | string | SHA-256 hex |
| paperId | string | Paper identifier |
| taskType | string | Task type |
| paramsHash | string | SHA-256 of params |

**References:** Owned by IdempotencyService