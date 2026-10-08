# Functional Specification — ContentJobApi

**Unit:** ContentJobApi
**Phase:** Construction — Functional Design
**Date:** 2026-10-02
**Kind:** library

---

## Overview

ContentJobApi is the central API client for all content job operations. It routes all calls through the BFF proxy (`/bff/api/content-jobs/*`) for SEC-8 compliance, manages idempotency keys via IdempotencyService, and provides SSE subscription and polling fallback capabilities.

---

## Public API

### Types

```typescript
type TaskType = 'summarize' | 'translate' | 'novelty' | 'evidence' | 'ingest_userdoc';

interface JobState {
  jobId: string;
  state: 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABSTAINED';
  assetId?: string;
  error?: {
    errorType: string;
    message: string;
    retryable: boolean;
    retryAfterSeconds?: number;
  };
  abstainReason?: string;
}

interface JobEvent {
  eventId: string;
  jobId: string;
  state: string;
  timestampUs: number;
  payload?: {
    assetId?: string;
    error?: { errorType: string; message: string; retryable: boolean };
    abstainReason?: string;
  };
}

interface SubmitJobRequest {
  taskType: TaskType;
  input: Record<string, unknown>;
  idempotencyKey?: string; // Required for Phase 7
}

interface SubmitJobResponse {
  jobId: string;
  state: string;
}

interface TranslateResponse {
  assetId?: string;
  jobId?: string;
  state: string;
  source: 'cache' | 'job';
}

interface AssetTokenResponse {
  token: string;
  expiresIn: number;
}
```

### Constants

```typescript
const API_BASE = '/bff/api/content-jobs'; // BFF proxy path
```

---

## Functions

### submitJob

Submits a new content job with idempotency key.

```typescript
async function submitJob(request: SubmitJobRequest): Promise<SubmitJobResponse>
```

**Behavior:**
1. If `idempotencyKey` not provided, generates one via `IdempotencyService.generateKey()`
2. Stores key in localStorage via `IdempotencyService.storeKey()`
2. POSTs to `/bff/api/content-jobs/submit` with `idempotencyKey` in body
3. Forwards session cookie via BFF proxy
3. Returns `{ jobId, state }` on 202 Accepted
4. On 409 Conflict: returns existing jobId (idempotent)

**Error Handling:**
- 401/403 → throw `AuthError` (redirect to login)
- 409 Conflict → return existing job (idempotent)
- 5xx → throw `ServerError` (retryable)

---

### getJobState

Polls current job state via BFF.

```typescript
async function getJobState(jobId: string): Promise<JobState>
```

**Behavior:**
1. GET `/bff/api/content-jobs/{jobId}/state`
3. Forwards session cookie
3. Returns `JobState` object

**Used by:** Polling fallback (SWR)

---

### subscribeJobEvents

Subscribes to real-time job events via SSE.

```typescript
function subscribeJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  lastEventId?: string
): () => void
```

**Behavior:**
1. Creates `EventSource` to `/bff/api/content-jobs/{jobId}/events`
2. Appends `lastEventId` as query param if provided
4. Sets `withCredentials: true` for cookie forwarding
5. Parses `message` events as JSON
6. Calls `onEvent(parsedEvent)` for each event
6. On `error`: closes connection, triggers reconnection logic
7. Returns unsubscribe function

**Reconnection Logic:**
- Max 3 attempts with exponential backoff (1s, 2s, 4s)
- Sends `Last-Event-ID` header on reconnect
- After 3 failures → activates polling fallback

---

### translate

Translates paper abstract with cache support.

```typescript
async function translate(input: {
  paperId: string;
  version?: number;
  targetLang?: string;
  persona?: Record<string, unknown>;
}): Promise<TranslateResponse>
```

**Behavior:**
1. POST to `/bff/api/content-jobs/translate`
2. Returns `{ assetId?, jobId?, state, source: 'cache' | 'job' }`

---

### Asset Functions (Deprecated for Phase 7)

> **Note:** `getAssetUrl` and `issueAssetToken` are deprecated in Phase 7. Use same-origin delivery via AssetViewer instead.

```typescript
// DEPRECATED — Use AssetViewer same-origin delivery instead
async function getAssetUrl(assetId: string, token: string): Promise<string>
async function issueAssetToken(assetId: string, action: 'view' = 'view'): Promise<AssetTokenResponse>
```

---

## Idempotency Key Management

### Key Format
```
idempotency:{paperId}:{taskType}
```

### Generation Algorithm
```typescript
async function generateIdempotencyKey(
  userId: string,
  paperId: string,
  taskType: string,
  params: Record<string, unknown>
): Promise<string> {
  const input = `${userId}:${paperId}:${taskType}:${JSON.stringify(params)}`;
  const buffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}
```

### Storage
- **Key:** `idempotency:${paperId}:${taskType}`
- **Value:** SHA-256 hex string
- **Expiration:** 24 hours (configurable)
- **Clear:** On explicit user action (e.g., "Clear retry state")

---

## Integration Points

### With IdempotencyService
- `generateKey(userId, paperId, taskType, params)` → `Promise<string>`
- `storeKey(paperId, taskType, key)` → `void`
- `getKey(paperId, taskType)` → `string | null`
- `clearKey(paperId, taskType)` → `void`

### With JobStatus
- `subscribeJobEvents(jobId, onEvent, lastEventId?)` → `() => void`
- Called by JobStatus on mount
- Returns unsubscribe function for cleanup

### With SummaryModal
- `submitJob({ taskType, input, idempotencyKey })` → `Promise<SubmitJobResponse>`
- Called when user clicks "Summarize" or "Translate"
- Returns `jobId` for JobStatus mounting

### With AssetViewer (Deprecated)
- `getAssetUrl(assetId, token)` → DEPRECATED
- `issueAssetToken(assetId, action)` → DEPRECATED

---

## Error Handling

### Network Errors
- All `fetch` calls wrapped in try/catch
- Network errors → `NetworkError` (retryable)
- AbortController for cleanup on unmount

### HTTP Error Mapping
| Status | Error Class | Retryable |
|--------|-------------|-----------|
| 400 | `ValidationError` | No |
| 401 | `AuthError` | No (redirect login) |
| 403 | `ForbiddenError` | No |
| 404 | `NotFoundError` | No |
| 409 | `ConflictError` | No (idempotent) |
| 410 | `GoneError` | No |
| 500 | `ServerError` | Yes |
| 502/503/504 | `GatewayError` | Yes (GET retry once) |

---

## Testing Requirements

### Unit Tests
- `generateIdempotencyKey` deterministic output
- `submitJob` includes idempotencyKey in body
- `subscribeJobEvents` sends Last-Event-ID on reconnect
- Error mapping for all HTTP status codes

### Integration Tests
- Submit job → SSE events → COMPLETED → result fetch
- 409 Conflict → existing job returned
- SSE disconnect → reconnect with Last-Event-ID
- SSE failure → polling fallback activates
- Polling stops on SSE reconnect or terminal state

### E2E Tests
- Submit summarize → SSE progress → COMPLETED → view result
- Submit translate → SSE progress → FAILED → retry → COMPLETED
- Page reload during job → idempotency key reused → same job returned

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| `submitJob` latency | < 500ms (P95) |
| SSE connection time | < 500ms |
| First SSE event | < 1s |
| Polling interval | 2000ms ± 100ms |
| Idempotency key generation | < 10ms |

---

## Security

- All calls via BFF (`/bff/api/content-jobs/*`)
- Session cookie forwarded automatically
- No tokens in client code
- Idempotency keys never logged
- CSP nonce on all script tags (middleware)