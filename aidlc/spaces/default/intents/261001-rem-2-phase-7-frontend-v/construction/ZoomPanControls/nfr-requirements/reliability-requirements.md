# Reliability Requirements — ZoomPanControls

## NFR4.1: State Persistence
- **Target**: Zoom/pan state preserved during parent re-renders
- **Implementation**: State in `useRef` (not `useState`) to avoid re-renders; synced to DOM transform
- **Recovery**: On ErrorBoundary reset, controls reinitialize to default (100%, center)

## NFR4.2: Boundary Constraints
- **Target**: Zoom clamped to [10%, 500%]; pan constrained to content bounds
- **Implementation**: Math clamping in transform calculation

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR4.1 | OK |