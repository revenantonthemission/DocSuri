# Reliability Requirements — ErrorBoundary

## NFR4.1: Error Containment (NFR6)
- **Target**: Errors in wrapped subtree never crash ancestors or siblings
- **Mechanism**: React 16+ error boundary semantics — errors bubble to nearest boundary
- **Validation**: Inject error in deep child; verify only that boundary's fallback shows

## NFR4.2: Recovery via Retry
- **Target**: Fallback provides retry action that remounts subtree
- **Implementation**: `ErrorBoundaryFallback` renders retry button → `key` prop change on parent → remount
- **Behavior**: Fresh component tree = fresh SSE connection / fresh state

## NFR4.3: Nested Boundary Priority
- **Target**: Innermost boundary catches; outer boundaries unaffected
- **Implementation**: Standard React error boundary hierarchy
- **Validation**: Nested boundaries test — inner catches, outer doesn't see error

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR4.1, NFR4.2, NFR4.3 | OK |