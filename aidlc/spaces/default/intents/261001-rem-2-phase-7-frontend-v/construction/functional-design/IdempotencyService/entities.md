# Entities — IdempotencyService

**Unit:** IdempotencyService
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Entity Definitions

### IdempotencyKey
**Owner:** IdempotencyService
**Identifier:** `key` (string, SHA-256 hex)

| Attribute | Type | Description |
|-----------|------|-------------|
| key | string | SHA-256 hex string, primary identifier |
| paperId | string | Paper identifier |
| taskType | string | Task type: 'summarize' \| 'translate' \| 'novelty' \| 'evidence' \| 'ingest_userdoc' |
| paramsHash | string | SHA-256 hash of JSON.stringify(params) |
| createdAt | number | Unix timestamp (ms) when key was generated |
| expiresAt | number | Unix timestamp (ms) when key expires (24h default) |

**References:** None (owned entirely by IdempotencyService)