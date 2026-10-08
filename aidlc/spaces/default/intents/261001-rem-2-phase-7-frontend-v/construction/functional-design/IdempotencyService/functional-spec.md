# Functional Specification — IdempotencyService

**Unit:** IdempotencyService
**Phase:** Construction — Functional Design
**Date:** 2026-10-02
**Kind:** library

---

## Overview

IdempotencyService provides deterministic SHA-256 idempotency key generation and localStorage persistence for job deduplication. Keys survive page reloads and enable safe retries.

---

## Public API

### Types

```typescript
interface IdempotencyKey {
  key: string;           // SHA-256 hex
  paperId: string;
  taskType: string;      // 'summarize' | 'translate' | 'novelty' | 'evidence' | 'ingest_userdoc'
  paramsHash: string;    // SHA-256 of JSON.stringify(params)
  createdAt: number;     // Unix ms
  expiresAt: number;     // Unix ms
}
```

### Functions

#### generateKey
Generates deterministic SHA-256 idempotency key.

```typescript
async function generateKey(
  userId: string,
  paperId: string,
  taskType: string,
  params: Record<string, unknown>
): Promise<string>
```

**Behavior:**
1. Constructs input: `${userId}:${paperId}:${taskType}:${JSON.stringify(params)}`
2. Computes SHA-256 via `crypto.subtle.digest('SHA-256', ...)`
3. Returns hex string (lowercase)
3. Does NOT store — caller must call `storeKey()`

**Returns:** Promise resolving to 64-char hex string

---

#### storeKey
Persists idempotency key to localStorage.

```typescript
function storeKey(paperId: string, taskType: string, key: string): void
```

**Behavior:**
1. Constructs storage key: `idempotency:${paperId}:${taskType}`
2. Creates payload with key, metadata, timestamps
3. Stores JSON string in localStorage
4. Overwrites existing entry for same paperId:taskType

**Storage Format:**
```json
{
  "key": "sha256hex...",
  "paperId": "paper123",
  "taskType": "summarize",
  "paramsHash": "sha256hex...",
  "createdAt": 1696200000000,
  "expiresAt": 1696286400000
}
```

---

#### getKey
Retrieves stored idempotency key if valid.

```typescript
function getKey(paperId: string, taskType: string): string | null
```

**Behavior:**
1. Reads localStorage key `idempotency:${paperId}:${taskType}`
2. Parses JSON, validates schema
3. Checks `expiresAt > Date.now()`
5. Returns `key` string or `null` if missing/expired/invalid
6. On expiration/invalid: removes entry, returns `null`

---

#### clearKey
Removes stored idempotency key.

```typescript
function clearKey(paperId: string, taskType: string): void
```

**Behavior:**
- Removes localStorage entry `idempotency:${paperId}:${taskType}`
- No-op if key doesn't exist

---

#### clearAllKeys (Optional)
Clears all idempotency keys (for testing/debug).

```typescript
function clearAllKeys(): void
```

---

## Configuration

```typescript
const CONFIG = {
  TTL_MS: 24 * 60 * 60 * 1000, // 24 hours
  STORAGE_PREFIX: 'idempotency:',
  HASH_ALGORITHM: 'SHA-256',
} as const;
```

**Environment Overrides:**
- `IDEMPOTENCY_TTL_MS` — override TTL in ms
- `IDEMPOTENCY_STORAGE_PREFIX` — override prefix

---

## Integration Points

### With ContentJobApi (Submit)
```typescript
// In ContentJobApi.submitJob()
const idempotencyKey = await IdempotencyService.generateKey(
  userId, paperId, taskType, params
);
IdempotencyService.storeKey(paperId, taskType, idempotencyKey);

const response = await fetch('/bff/api/content-jobs/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ...request, idempotencyKey }),
  credentials: 'include'
});
```

### With JobStatus (Retry)
```typescript
// In JobStatus onRetry()
const key = IdempotencyService.getKey(paperId, taskType);
if (key) {
  await submitJob({ taskType, input: params, idempotencyKey: key });
}
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `crypto.subtle` unavailable | Throw `CryptoUnavailableError`; fallback to non-crypto hash (warn) |
| localStorage full | Clear oldest entries, retry; if still fails, throw `StorageQuotaExceededError` |
| Corrupted localStorage data | Clear corrupted entry, return `null` |
| `crypto.subtle.digest` fails | Throw `CryptoOperationError` |

---

## Testing Requirements

### Unit Tests
| Function | Test Cases |
|----------|------------|
| `generateKey` | Deterministic output, different inputs → different hashes |
| `storeKey` / `getKey` | Round-trip storage, expiration handling |
| `clearKey` / `clearAllKeys` | Removal verified |

### Integration Tests
- Generate → Store → Retrieve → Clear cycle
- Expired key returns `null` and cleans up
- Concurrent calls to `generateKey` with same inputs return same key

---

## Security Considerations

- Keys never logged (use `key.slice(0, 8) + '...'` for debug)
- localStorage only accessible on same origin
- No sensitive data in key (only hash of params)
- TTL limits exposure window