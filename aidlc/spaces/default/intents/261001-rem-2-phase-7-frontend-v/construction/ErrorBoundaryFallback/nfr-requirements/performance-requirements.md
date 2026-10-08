# Performance Requirements — ErrorBoundaryFallback

## NFR1.1: Render Speed
- **Target**: Fallback renders ≤5ms
- **Implementation**: Pure functional component; no hooks, no state
- **Props**: `error: Error`, `reset: () => void`, `boundaryName?: string`

## NFR1.2: Bundle Size
- **Target**: ≤3KB gzipped (with styles)
- **Rationale**: Tiny presentational component

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR1.1, NFR1.2 | OK |