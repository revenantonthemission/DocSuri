# Performance Requirements — ErrorBoundary

## NFR1.1: Render Overhead
- **Target**: Zero overhead when no error (React 18 bailout)
- **Implementation**: Class component with `componentDidCatch`; no state when healthy
- **Validation**: React DevTools Profiler — no renders during normal operation

## NFR1.2: Fallback Mount Time
- **Target**: Fallback renders within 16ms (1 frame) of error
- **Implementation**: Synchronous `setState` in `componentDidCatch`
- **Rationale**: Immediate visual feedback prevents perceived freeze

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR1.1, NFR1.2 | OK |