# Logical Components — ErrorBoundaryFallback

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `ErrorBoundaryFallback` | Functional Component | Render error UI, call reset | None (leaf) |

## Failure Domains
- Leaf component; no error propagation
- Reset callback delegated to parent ErrorBoundary

## Isolation
- Pure props-driven; no internal state
- Testable in isolation

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.2 | ErrorBoundaryFallback |
| NFR2.1-2.2 | ErrorBoundaryFallback |
| NFR3.1 | ErrorBoundaryFallback (variants) |
| NFR4.1-4.2 | ErrorBoundaryFallback + parent ErrorBoundary |
| NFR5.1 | ErrorBoundaryFallback |