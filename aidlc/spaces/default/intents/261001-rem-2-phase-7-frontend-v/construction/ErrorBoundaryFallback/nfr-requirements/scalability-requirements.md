# Scalability Requirements — ErrorBoundaryFallback

## NFR3.1: Reusability
- **Target**: Single component used by all ErrorBoundary instances
- **Implementation**: Props-driven; no internal state
- **Variants**: `variant: 'inline' | 'page' | 'modal'` for different contexts

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR3.1 | OK |