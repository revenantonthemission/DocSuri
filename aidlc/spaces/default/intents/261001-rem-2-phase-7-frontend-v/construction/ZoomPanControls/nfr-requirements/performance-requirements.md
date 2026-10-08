# Performance Requirements — ZoomPanControls

## NFR1.1: Interaction Latency
- **Target**: Zoom/pan response ≤16ms (60fps)
- **Implementation**: CSS `transform` (GPU); no layout thrashing
- **Validation**: Chrome DevTools Performance — no long tasks during interaction

## NFR1.2: Transform Accuracy
- **Target**: Sub-pixel accuracy; no drift over 1000 operations
- **Implementation**: Float64 matrix math; periodic re-normalization

## NFR1.3: Bundle Size
- **Target**: ≤8KB gzipped
- **Rationale**: Pure math + minimal DOM; no deps

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR1.1 | OK |