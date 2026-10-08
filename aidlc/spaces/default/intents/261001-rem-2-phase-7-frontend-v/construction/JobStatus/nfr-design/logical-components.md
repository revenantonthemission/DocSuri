# Logical Components — JobStatus

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `JobStatus` | UI | SSE consumption, status display, polling fallback | SSE connection, render |
| `ErrorBoundary` | UI | Error containment, Sentry reporting, retry trigger | Subtree crashes |
| `ErrorBoundaryFallback` | UI | User-friendly error display, retry action | None (leaf) |
| `useSSE` | Hook | EventSource lifecycle, reconnection, event parsing | Network, parsing |
| `usePollingFallback` | Hook | SWR polling, fallback data, mode switching | Network, cache |
| `useIdempotencyKey` | Hook | Key retrieval from ContentJobApi | localStorage |

## Failure Domains & Blast Radius

```
JobStatus (UI)
├── SSE Connection Failure
│   ├── Impact: Single job status stale
│   ├── Mitigation: Auto-reconnect + polling fallback
│   └── Blast Radius: This JobStatus instance only
├── Render Error
│   ├── Impact: JobStatus unmounts
│   ├── Mitigation: ErrorBoundary catches → fallback UI
│   └── Blast Radius: This JobStatus instance only
├── Polling Failure
│   ├── Impact: No updates during SSE outage
│   ├── Mitigation: Retry button in fallback
│   └── Blast Radius: This JobStatus instance only
└── Idempotency Key Missing
    ├── Impact: Cannot resume job on refresh
    ├── Mitigation: ContentJobApi generates new key
    └── Blast Radius: New job submission only
```

## Component Isolation Strategy

- **Each JobStatus = Independent Failure Domain**: Own `EventSource`, own SWR cache, own ErrorBoundary
- **No Shared State**: No global stores, no context providers for job status
- **Parent Coordination Only**: Parent passes `jobId` + `idempotencyKey` props

## Shared Resources

| Resource | Owner | Consumers | Isolation |
|----------|-------|-----------|-----------|
| SSE Connection | JobStatus instance | Self | Per-instance |
| SWR Cache | JobStatus instance | Self | Per-job key |
| localStorage (idempotency) | IdempotencyService | ContentJobApi | Namespaced by paperId:taskType |
| Sentry | App-level | All boundaries | Shared DSN, scoped by component |

## Infrastructure Design Handoff

| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| SSE Endpoint | BFF `/bff/api/content-jobs/{jobId}/events` → Gateway WebSocket/SSE |
| Polling Endpoint | BFF `/bff/api/content-jobs/{jobId}` → Gateway REST |
| Idempotency Store | localStorage (client) + Gateway Redis (server TTL) |
| Sentry | DSN in env, source maps uploaded at build |

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.6 | JobStatus, useSSE, usePollingFallback |
| NFR2.1-2.5 | JobStatus, ErrorBoundary, useSSE |
| NFR3.1-3.3 | JobStatus (per-instance) |
| NFR4.1-4.5 | JobStatus, useSSE, usePollingFallback, ErrorBoundary |
| NFR5.1-5.4 | ErrorBoundary, useSSE, JobStatus |