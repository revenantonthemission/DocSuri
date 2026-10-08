# Frontend Components — IdempotencyService

**Unit:** IdempotencyService
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Overview

IdempotencyService is a **library** unit with no UI components. It provides pure functions for idempotency key management.

---

## API Summary

### Exports

```typescript
export interface IdempotencyKey {
  key: string;
  paperId: string;
  taskType: string;
  paramsHash: string;
  createdAt: number;
  expiresAt: number;
}

export interface IdempotencyService {
  generateKey(userId: string, paperId: string, taskType: string, params: Record<string, unknown>): Promise<string>;
  storeKey(paperId: string, taskType: string, key: string): void;
  getKey(paperId: string, taskType: string): string | null;
  clearKey(paperId: string, taskType: string): void;
  clearAllKeys(): void;
}
```

---

## Integration Points

### ContentJobApi (Consumer)
```typescript
// Submit job with idempotency key
const key = await IdempotencyService.generateKey(userId, paperId, taskType, params);
IdempotencyService.storeKey(paperId, taskType, key);

const response = await fetch('/bff/api/content-jobs/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ...request, idempotencyKey: key }),
  credentials: 'include'
});
```

### JobStatus (Retry Flow)
```typescript
// Retry with same idempotency key
const handleRetry = async () => {
  const key = IdempotencyService.getKey(paperId, taskType);
  if (key) {
    await submitJob({ taskType, input: params, idempotencyKey: key });
  }
};
```

### SummaryModal (Submit)
```typescript
const handleSubmit = async (taskType: TaskType) => {
  const key = await IdempotencyService.generateKey(userId, paperId, taskType, params);
  IdempotencyService.storeKey(paperId, taskType, key);
  
  const response = await ContentJobApi.submitJob({
    taskType,
    input: params,
    idempotencyKey: key
  });
  
  onSubmit(response.jobId);
};
```

---

## Storage Schema

**localStorage Key Format:** `idempotency:{paperId}:{taskType}`

**Stored Value:**
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

## UI Components (None)

IdempotencyService has **no UI components**. It is a pure library module.

---

## Test Points

### Unit Tests
- `generateKey()` deterministic output
- `storeKey`/`getKey` round-trip
- Expiration handling
- `clearKey`/`clearAllKeys` removal

### Integration Tests
- Full cycle: generate → store → get → clear
- Expiration handling
- Concurrent access safety