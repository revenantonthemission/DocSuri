# Logical Components — ContentJobApi

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `contentJobApi` | Library | submitJob, getJobStatus, cancelJob | Network, validation |
| `Transport` | Interface | fetch wrapper, retry, headers | Network |
| `IdempotencyService` | Library (separate unit) | Key generation, storage, retrieval | localStorage, crypto |
| `BFF Proxy` | Next.js Route | `/bff/api/content-jobs/*` → Gateway | Network, gateway |

## Failure Domains & Blast Radius

```
ContentJobApi
├── submitJob()
│   ├── Validation Error (Zod)
│   │   ├── Impact: Immediate 400 to caller
│   │   └── Blast Radius: Single call
│   ├── Network Error (fetch)
│   │   ├── Impact: Retry once with same key
│   │   └── Blast Radius: Single call
│   ├── BFF Proxy Error (5xx)
│   │   ├── Impact: Retry → ErrorBoundary
│   │   └── Blast Radius: Single call
│   └── Gateway Error (4xx/5xx)
│       ├── Impact: Sanitized error to caller
│       └── Blast Radius: Single call
└── getJobStatus()
    ├── Network Error
    │   └── Blast Radius: Single call
    └── Gateway Error
        └── Blast Radius: Single call
```

## Component Isolation

- **Stateless**: All functions pure; no internal state
- **IdempotencyService**: Separate unit; own failure domain
- **Transport**: Swappable interface (testable with mock)

## Shared Resources

| Resource | Owner | Consumers |
|----------|-------|-----------|
| `CONTENT_JOB_API_BASE` constant | ContentJobApi | All API calls |
| Idempotency keys | IdempotencyService | ContentJobApi |
| Sentry | App | Transport, contentJobApi |

## Infrastructure Design Handoff

| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| BFF Proxy Route | Next.js `app/bff/api/content-jobs/[...path]/route.ts` |
| Gateway Endpoint | `POST /api/content-jobs` (submit), `GET /api/content-jobs/{id}` (status) |
| Idempotency Store | Gateway Redis (24h TTL) + Client localStorage |

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.4 | contentJobApi, Transport, BFF Proxy |
| NFR2.1-2.5 | contentJobApi, Transport, IdempotencyService, BFF Proxy |
| NFR3.1-3.2 | contentJobApi, IdempotencyService |
| NFR4.1-4.3 | Transport, contentJobApi |
| NFR5.1-5.3 | Transport, contentJobApi |