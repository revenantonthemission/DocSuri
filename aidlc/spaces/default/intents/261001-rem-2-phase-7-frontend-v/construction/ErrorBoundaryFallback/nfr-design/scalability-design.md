# Scalability Design — ErrorBoundaryFallback

## NFR3.1: Reusable Variants
**Design**: Props-driven variants
```tsx
<ErrorBoundaryFallback variant="inline" />   // In JobStatus
<ErrorBoundaryFallback variant="page" />     // Page-level
<ErrorBoundaryFallback variant="modal" />    // Modal overlay
```
- Single component, conditional rendering via `variant` prop

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | Props-driven variants |