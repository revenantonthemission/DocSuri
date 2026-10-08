# Tech Stack Decisions — ErrorBoundaryFallback

## NFR6.1: Component — Functional React Component
- **Decision**: Pure function component (no hooks, no state)
- **Rationale**: Maximum performance; testable; composable

## NFR6.2: Styling — CSS Modules + Tailwind
- **Decision**: Mandated pattern
- **CSS Module**: `ErrorBoundaryFallback.module.css` for layout
- **Tailwind**: Utility classes for colors, spacing, typography
- **clsx + tailwind-merge**: Conditional classes for variants

## NFR6.3: Icons — Inline SVG
- **Decision**: Inline SVG (no icon library)
- **Rationale**: Zero deps; tree-shakeable; styleable with `currentColor`

## NFR6.4: TypeScript — Strict
- **Decision**: Full strict mode
- **Props**: 
  ```ts
  interface Props {
    error: Error;
    reset: () => void;
    boundaryName?: string;
    variant?: 'inline' | 'page' | 'modal';
    errorCode?: string;
  }
  ```

## NFR6.5: Testing — Vitest + RTL
- **Decision**: Unit tests with Vitest + React Testing Library
- **Coverage Target**: ≥80% line coverage
- **A11y**: axe-core in tests

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR6.1, NFR6.2, NFR6.4 | OK |