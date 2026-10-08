# Logical Components — ErrorBoundary

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `ErrorBoundary` | Class Component | `componentDidCatch`, state, render fallback | Subtree errors |
| `ErrorBoundaryFallback` | Functional Component (separate unit) | UI for error + retry | None (leaf) |

## Failure Domains

```
ErrorBoundary
├── Caught Error
│   ├── Sets error state → renders fallback
│   ├── Sentry.captureException()
│   └── Blast Radius: Wrapped subtree only
├── Fallback Retry
│   ├── Parent increments key → remount
│   └── Blast Radius: Wrapped subtree (fresh mount)
└── Nested Boundaries
    ├── Inner catches → outer unaffected
    └── Blast Radius: Each boundary isolates its subtree
```

## Isolation Strategy
- Class component per boundary instance
- No shared state
- Fallback component stateless

## Shared Resources
| Resource | Owner | Consumers |
|----------|-------|-----------|
| Sentry | App | All ErrorBoundary instances |
| ErrorBoundaryFallback | Shared | All boundaries (via props) |

## Infrastructure Handoff
- None (client-only)

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.2 | ErrorBoundary class component |
| NFR2.1-2.2 | ErrorBoundary componentDidCatch |
| NFR3.1 | ErrorBoundary (per-instance) |
| NFR4.1-4.3 | ErrorBoundary + parent key remount |
| NFR5.1-5.3 | ErrorBoundary + ErrorBoundaryFallback |