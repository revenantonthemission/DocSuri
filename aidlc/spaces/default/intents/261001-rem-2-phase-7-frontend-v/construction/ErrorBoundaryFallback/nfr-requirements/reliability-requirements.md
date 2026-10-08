# Reliability Requirements — ErrorBoundaryFallback

## NFR4.1: Reset Function Reliability
- **Target**: `reset()` callback always remounts boundary subtree
- **Implementation**: Parent `ErrorBoundary` uses `key` prop; `reset()` increments key
- **Validation**: Integration test — error → fallback → retry → success

## NFR4.2: Accessibility (NFR6)
- **Target**: Fallback meets WCAG 2.1 AA
- **Implementation**: 
  - Semantic HTML (`<main>`, `<button>`, `<p>`)
  - Focus management: retry button auto-focused
  - ARIA: `role="alert"` on error message
  - Color contrast: Tailwind `text-red-600` on `bg-red-50` (4.5:1)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR4.1, NFR4.2 | OK |