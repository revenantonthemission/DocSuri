# Performance Design — ErrorBoundary

## NFR1.1: Zero Overhead When Healthy
**Design**: Class component with no state until error
- `componentDidCatch` only runs on error
- No `shouldComponentUpdate` needed (React 18 bailout)

## NFR1.2: Fallback Mount ≤16ms
**Design**: Synchronous `setState` in `componentDidCatch`
- Immediate render of fallback
- No async boundary

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | Class component, no state when healthy |
| NFR1.2 | Sync setState in componentDidCatch |