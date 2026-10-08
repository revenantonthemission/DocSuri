# Reliability Design — ZoomPanControls

## NFR4.1: State Persistence Across Re-renders
**Design**: `useRef` for transform state
- Avoids React re-renders during interaction
- Synced to DOM via `element.style.transform`
- **ErrorBoundary Reset**: Reinitializes to defaults (100%, center)

## NFR4.2: Boundary Constraints
**Design**: Clamping in transform calculation
- Zoom: `[0.1, 5.0]` (10% - 500%)
- Pan: Constrained to content bounds
- Smooth clamping (no hard stops)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | useRef state + DOM sync |
| NFR4.2 | Math clamping in transform |