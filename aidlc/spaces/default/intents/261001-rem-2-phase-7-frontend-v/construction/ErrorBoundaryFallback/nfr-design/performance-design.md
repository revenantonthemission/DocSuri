# Performance Design — ErrorBoundaryFallback

## NFR1.1: Render ≤5ms
**Design**: Pure functional component, no hooks, no state
- Props: `error`, `reset`, `boundaryName`, `variant`, `errorCode`
- No `useEffect`, no `useState`

## NFR1.2: Bundle ≤3KB gzipped
**Design**: Minimal + CSS Module + Tailwind utilities
- No external deps
- Inline SVG icons

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | Pure functional component |
| NFR1.2 | CSS Module + Tailwind, inline SVG |