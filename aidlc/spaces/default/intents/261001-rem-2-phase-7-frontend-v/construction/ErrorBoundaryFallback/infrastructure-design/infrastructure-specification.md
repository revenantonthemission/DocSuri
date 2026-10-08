# Infrastructure Specification — ErrorBoundaryFallback

## Client-Only Infrastructure

### Component
- **Type**: Pure Functional Component (no hooks, no state)
- **Props**: `error`, `reset`, `boundaryName`, `variant`, `errorCode`
- **Variants**: `inline` | `page` | `modal`

### Styling
- **CSS Module**: `ErrorBoundaryFallback.module.css`
- **Tailwind**: Utility classes for colors, spacing
- **clsx + tailwind-merge**: Conditional classes
- **Icons**: Inline SVG (no icon library)

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| ErrorBoundaryFallback | CSS Module + Tailwind (build) |