# Tech Stack Decisions — ErrorBoundary

## NFR6.1: Implementation — React Class Component
- **Decision**: Class component (required for `componentDidCatch`)
- **Rationale**: 
  - Function components cannot be error boundaries (React limitation)
  - No external library (forbidden: no react-error-boundary, etc.)
  - Minimal ~50 lines

## NFR6.2: Fallback UI — `ErrorBoundaryFallback` Component (separate unit)
- **Decision**: Compose separate fallback component
- **Rationale**: 
  - Separation of concerns (boundary logic vs UI)
  - Reusable across boundaries
  - Testable in isolation

## NFR6.3: Sentry — `@sentry/nextjs`
- **Decision**: Official Sentry Next.js SDK
- **Rationale**: 
  - Mandated: ALWAYS integrate Sentry for client-side error tracking
  - Automatic source map upload
  - Next.js integration (pages router + app router)

## NFR6.4: TypeScript — Strict
- **Decision**: Full strict mode
- **Props**: `fallback?: ReactNode` | `fallbackRender?: (error, reset) => ReactNode`

## NFR6.5: Testing — Vitest + RTL
- **Decision**: Unit tests with Vitest; trigger errors via `act()`
- **Coverage Target**: ≥80% line coverage

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR6.1, NFR6.2 | OK |
| NFR7 (Sentry) | NFR6.3 | OK |