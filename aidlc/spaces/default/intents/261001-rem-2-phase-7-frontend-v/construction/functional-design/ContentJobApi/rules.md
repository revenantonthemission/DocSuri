# Business Rules — ContentJobApi

**Unit:** ContentJobApi
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-CJA-001: BFF Routing Mandatory
**Description:** All content-job API calls MUST route through the BFF proxy at `/bff/api/content-jobs/*`.
**Rationale:** SEC-8 compliance — gateway injects principal header for authentication.
**Enforcement:** 
- `API_BASE` constant MUST be `/bff/api/content-jobs`
- Direct calls to `/api/content-jobs/*` are forbidden (ESLint rule `no-restricted-imports`)

### BR-CJA-002: Idempotency Key Generation
**Description:** Every job submission MUST include a deterministic idempotency key.
**Algorithm:** SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)`
**Storage:** localStorage with key format `idempotency:{paperId}:{taskType}`
**Expiration:** 24 hours from creation (configurable)
**Collision Handling:** If key exists in localStorage, reuse existing key (deterministic)

### BR-CJA-003: Idempotency Key Reuse on Retry
**Description:** When retrying a failed job, the SAME idempotency key MUST be used.
**Implementation:** 
- Retrieve key from localStorage using `idempotency:{paperId}:{taskType}`
- Include key in `submitJob` request as `idempotencyKey` field
- Backend returns existing job on 409 Conflict

### BR-CJA-004: BFF Routing for All Calls
**Description:** All content-job API calls MUST route through BFF proxy.
**Endpoints:**
- `POST /bff/api/content-jobs/submit` — Submit new job
- `GET /bff/api/content-jobs/{jobId}/state` — Poll job state
- `GET /bff/api/content-jobs/{jobId}/events` — SSE event stream
- `POST /bff/api/content-jobs/translate` — Translate with cache support

### BR-CJA-005: Session Cookie Forwarding
**Description:** All requests through BFF MUST forward the session cookie.
**Implementation:**
- Read `cookie` header from incoming request
- Forward as `cookie` header to gateway
- Relay `set-cookie` headers from gateway response back to browser

### BR-CJA-006: SSE Event Subscription
**Description:** JobStatus subscribes to SSE events via ContentJobApi.
**Implementation:**
- `subscribeJobEvents(jobId, onEvent, lastEventId?)` returns unsubscribe function
- Uses `EventSource` with `Last-Event-ID` header for resume
- Connection state: `connecting` → `connected` → `reconnecting` → `polling`

### BR-CJA-007: Polling Fallback
**Description:** When SSE fails after 3 reconnection attempts, activate polling fallback.
**Configuration:**
- SWR `refreshInterval: 2000` (2s fixed interval)
- Endpoint: `/bff/api/content-jobs/{jobId}/state`
- Fallback data: last known SSE state
- Deactivation: SSE reconnects OR job reaches terminal state

### BR-CJA-008: Error Handling
**Description:** Standardized error responses across all endpoints.
**Format:**
```json
{
  "message": "Human-readable error message",
  "code": "ERROR_CODE",
  "retryable": boolean,
  "retryAfterSeconds": number
}
```
**Common Codes:**
- `AUTH_REQUIRED` (401) — Session expired, redirect to login
- `FORBIDDEN` (403) — Owner check failed
- `NOT_FOUND` (404) — Job/asset not found
- `CONFLICT` (409) — Idempotency key exists
- `GONE` (410) — Result expired
- `TIMEOUT` (504) — Gateway timeout
- `SERVER_ERROR` (500) — Internal error

### BR-CJA-009: SQ3 Mitigation — GET Retry
**Description:** GET requests retry ONCE after 1.5s delay on 502/503/504.
**Rationale:** Aurora Serverless v2 cold start mitigation.
**Scope:** Only GET requests; non-GET never retry automatically.

### BR-CJA-010: AssetViewer Migration — Same-Origin Delivery
**Description:** AssetViewer MUST use same-origin delivery, NO presigned URLs.
**Implementation:**
- Direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- BFF `proxyAssetImage` handles auth re-check, streams bytes
- Response headers: `cache-control: private, max-age=60`
- Content-Type validation: must start with `image/`

---

## Data Invariants

### Invariant: Idempotency Key Uniqueness
**Statement:** `idempotency:{paperId}:{taskType}` maps to exactly one `IdempotencyKey` at any time.
**Violation:** Overwrite only if paramsHash differs (new job submission).

### Invariant: JobId Uniqueness
**Statement:** Each `jobId` is a UUID v4, globally unique.
**Violation:** Never generated twice; backend enforces uniqueness.

### Invariant: Job State Machine
**Statement:** Job state transitions follow strict order:
```
SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED
                                    ↓
                                FAILED
                                    ↓
                                ABSTAINED
```
**Violation:** Invalid transition = backend bug.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Network error on submit | `fetch` throws | Show error, enable retry with same idempotency key |
| 409 Conflict on submit | Response status 409 | Fetch existing job, mount JobStatus |
| 401/403 on any call | Response status 401/403 | Redirect to login |
| SSE connection lost | `EventSource.onerror` | Reconnect (max 3) → polling fallback |
| Polling fetch fails | SWR `onError` | Retry on next interval |
| Asset fetch fails | `img.onError` | Show error state + retry button |