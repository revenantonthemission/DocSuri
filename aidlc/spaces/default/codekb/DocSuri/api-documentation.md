# API Documentation — DocSuri Frontend

**Project:** DocSuri
**Date:** 2026-10-02

---

## Content Job API (Current vs Required)

### Current Implementation (`contentJobApi.ts`)

| Function | Current Endpoint | Method | Bypasses BFF? |
|----------|------------------|--------|---------------|
| `submitJob()` | `/api/content-jobs/submit` | POST | ❌ Yes |
| `getJobState()` | `/api/content-jobs/{jobId}/state` | GET | ❌ Yes |
| `subscribeJobEvents()` | `/api/content-jobs/{jobId}/events` | SSE | ❌ Yes |
| `translate()` | `/api/content-jobs/translate` | POST | ❌ Yes |
| `getAssetUrl()` | `/api/content-jobs/assets/{assetId}?token=` | GET (307) | ❌ Yes |
| `issueAssetToken()` | `/api/content-jobs/assets/{assetId}/token` | POST | ❌ Yes |

### Required Endpoints (Through BFF `/bff`)

| Function | Required Endpoint | Method | Notes |
|----------|-------------------|--------|-------|
| `submitJob()` | `/bff/api/content-jobs/submit` | POST | Add idempotencyKey |
| `getJobState()` | `/bff/api/content-jobs/{jobId}/state` | GET | For polling fallback |
| `subscribeJobEvents()` | `/bff/api/content-jobs/{jobId}/events` | SSE | Last-Event-ID support |
| `translate()` | `/bff/api/content-jobs/translate` | POST | Cache-aware |
| `getAssetUrl()` | **REMOVE** | — | Replace with same-origin pattern |
| Asset Delivery | `/bff/api/papers/{paperId}/assets/{assetId}` | GET | Direct `<img src>`, auth re-check |
| `issueAssetToken()` | `/bff/api/content-jobs/assets/{assetId}/token` | POST | Keep for token issuance |

---

## BFF Proxy Endpoints (`/bff/[...path]`)

### Content Jobs

| Path | Method | Upstream | Notes |
|------|--------|----------|-------|
| `/bff/api/content-jobs/submit` | POST | `/api/content-jobs/submit` | Cookie forwarded |
| `/bff/api/content-jobs/{jobId}/state` | GET | `/api/content-jobs/{jobId}/state` | Polling fallback |
| `/bff/api/content-jobs/{jobId}/events` | GET | `/api/content-jobs/{jobId}/events` | SSE proxy, Last-Event-ID |
| `/bff/api/content-jobs/translate` | POST | `/api/content-jobs/translate` | Cache-aware |
| `/bff/api/content-jobs/assets/{assetId}/token` | POST | `/api/content-jobs/assets/{assetId}/token` | Token issuance |
| `/bff/api/content-jobs/assets/{assetId}` | GET | `/api/content-jobs/assets/{assetId}` | **REMOVED** — use paper assets |

### Asset Delivery (Same-Origin)

| Path | Method | Upstream | Notes |
|------|--------|----------|-------|
| `/bff/api/papers/{paperId}/assets/{assetId}` | GET | `/api/papers/{paperId}/assets/{assetId}` | Auth re-check, streams bytes, `cache-control: private, max-age=60`, no 307 |

### SSE Endpoints

| Path | Method | Upstream | Notes |
|------|--------|----------|-------|
| `/bff/api/content-jobs/{jobId}/events` | GET | `/api/content-jobs/{jobId}/events` | Last-Event-ID, 15s timeout |
| `/bff/api/novelty/jobs/{jobId}/events` | GET | `/api/novelty/jobs/{jobId}/events` | Novelty SSE |
| `/bff/api/evidence/turns` | POST | `/api/evidence/turns` | Evidence turns SSE |
| `/bff/api/research/jobs` | POST | `/api/research/jobs` | Research jobs SSE |

### Search & Library

| Path | Method | Upstream | Notes |
|------|--------|----------|-------|
| `/bff/api/search` | GET/POST | `/api/search` | 30s timeout |
| `/bff/api/library/*` | GET/POST | `/api/library/*` | Auth required |

---

## Request/Response Schemas

### Submit Job Request
```typescript
interface SubmitJobRequest {
  taskType: 'translate' | 'summarize' | 'novelty' | 'evidence' | 'ingest_userdoc';
  input: Record<string, unknown>;
  idempotencyKey?: string;  // Should be required for Phase 7
}
```

### Submit Job Response
```typescript
interface SubmitJobResponse {
  jobId: string;
  state: 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABSTAINED';
}
```

### Job State
```typescript
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
```

### SSE Event
```typescript
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
```

### Asset Token Response
```typescript
interface AssetTokenResponse {
  token: string;
  expiresIn: number;
}
```

### Translate Response
```typescript
interface TranslateResponse {
  assetId?: string;
  jobId?: string;
  state: string;
  source: 'cache' | 'job';
}
```

---

## Error Responses

| Status | Scenario | Response Format |
|--------|----------|-----------------|
| 400 | Invalid request body | `{ message: "잘못된 요청 형식입니다." }` |
| 401 | Unauthorized (no session) | Redirect to login |
| 403 | Forbidden (owner check failed) | `{ message: "접근 권한이 없습니다." }` |
| 404 | Job/Asset not found | `{ message: "리소스를 찾을 수 없습니다." }` |
| 409 | Idempotency conflict | Returns existing job |
| 410 | Result expired (TTL) | `{ message: "결과가 만료되었습니다." }` |
| 500 | Internal server error | `{ message: "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요." }` |
| 502 | Bad gateway | `{ message: "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요." }` |
| 503 | Service unavailable | `{ message: "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요." }` |
| 504 | Gateway timeout | `{ message: "요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요." }` |

---

## SSE Event Stream Format

```
event: message
data: {"eventId":"evt_123","jobId":"job_456","state":"RUNNING","timestampUs":1234567890123,"payload":{}}

event: message
data: {"eventId":"evt_124","jobId":"job_456","state":"COMPLETED","timestampUs":1234567890124,"payload":{"assetId":"asset_789"}}
```

**Reconnection:** Client sends `Last-Event-ID: evt_124` on reconnect; server replays missed events.

---

## BFF-Specific Headers

### Request Headers (BFF → Gateway)
| Header | Source | Purpose |
|--------|--------|---------|
| `Cookie` | Browser request | Session auth |
| `X-Recaptcha-Token` | Client (if present) | reCAPTCHA verification |
| `X-Amz-Content-SHA256` | BFF (POST body) | Lambda Function URL requirement |

### Response Headers (Gateway → BFF → Browser)
| Header | Purpose |
|--------|---------|
| `Set-Cookie` | Session refresh/rotation |
| `Content-Type` | `application/json` or `text/event-stream` |
| `Cache-Control` | `no-store` (SSE), `private, max-age=60` (assets) |
| `X-Content-Type-Options` | `nosniff` (assets) |

---

## Idempotency Key Specification

### Generation (Client-Side)
```typescript
// SHA-256 hash of: userId + paperId + taskType + JSON.stringify(params)
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
```typescript
// localStorage key format
const STORAGE_KEY = `idempotency:${paperId}:${taskType}`;

// On submit: check localStorage first, reuse if exists
// On explicit clear: localStorage.removeItem(STORAGE_KEY)
```

### Usage
```typescript
// Include in submitJob request
const response = await submitJob({
  taskType: 'summarize',
  input: { paperId, version },
  idempotencyKey: storedKey || await generateIdempotencyKey(...)
});
```

---

## Polling Fallback Specification

```typescript
// SWR configuration for /state polling
useSWR(`/bff/api/content-jobs/${jobId}/state`, fetcher, {
  refreshInterval: 2000,        // 2s fixed interval
  revalidateOnFocus: true,
  dedupingInterval: 1000,
  fallbackData: lastSSEState,   // Preserve last known state
  onSuccess: (data) => {
    if (data.state !== lastState) updateUI(data);
    if (isTerminalState(data.state)) stopPolling();
  }
});
```

**Activation:** When SSE `EventSource` enters error state (after max reconnect attempts).
**Deactivation:** When SSE reconnects successfully or job reaches terminal state.

---

## Asset Delivery Headers

### Request (Browser → BFF)
```
GET /bff/api/papers/{paperId}/assets/{assetId} HTTP/1.1
Cookie: session=...
Accept: image/*
```

### Response (BFF → Browser)
```
HTTP/1.1 200 OK
Content-Type: image/webp
Cache-Control: private, max-age=60
X-Content-Type-Options: nosniff
Content-Length: 12345
Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax
```

**Error Cases:**
- 401/403: Auth failed (owner check) → `{ message: "접근 권한이 없습니다." }`
- 404: Asset not found → 404 with `cache-control: no-store`
- 5xx: Gateway error → 404 degrade (no error UI for images)

---

## Rate Limits & Timeouts (BFF Layer)

| Path Pattern | Timeout | Retry |
|--------------|---------|-------|
| `/api/content-jobs/*` | Default (HttpTransport) | GET: once after 1.5s (SQ3) |
| `/api/content-jobs/{jobId}/events` | 15s (SSE_PROXY_TIMEOUT_MS) | No (streaming) |
| `/api/papers/{id}/assets/{assetId}` | 10s (ASSET_IMAGE_TIMEOUT_MS) | No (degrade to 404) |
| `/api/evidence/turns` | 90s (EVIDENCE_GATEWAY_TIMEOUT_MS) | No |
| `/api/search` | 30s (SEARCH_GATEWAY_TIMEOUT_MS) | No |
| `/api/novelty/jobs/{jobId}/events` | 15s | No |