# Tech Stack Decisions — JobStatus

## NFR6.1: SSE Client — Native `EventSource`
- **Decision**: Use browser-native `EventSource` API
- **Rationale**: 
  - Zero dependencies (mandated: no axios, no tanstack-query)
  - Automatic reconnection with `Last-Event-ID`
  - Built-in SSE parsing
  - Supported in all target browsers (Chrome 6+, Firefox 6+, Safari 5+, Edge 12+)
- **Alternatives Considered**:
  - `event-source-polyfill` — rejected (adds 3KB; native support sufficient)
  - Custom WebSocket — rejected (SSE is simpler for server→client only)
  - `axios` + streaming — rejected (forbidden: no axios)

## NFR6.2: Polling Fallback — SWR
- **Decision**: Use SWR (`useSWR`) for polling fallback
- **Rationale**:
  - Already in stack (mandated: use SWR for server state)
  - Built-in deduplication, caching, revalidation
  - `refreshInterval: 2000` matches mandated 2s fixed interval
  - Lightweight (~5KB) vs tanstack-query (~13KB)
- **Configuration**:
  ```ts
  useSWR(`/bff/api/content-jobs/${jobId}`, fetcher, {
    refreshInterval: 2000,
    revalidateOnFocus: false,
    dedupingInterval: 1000,
  })
  ```

## NFR6.3: Error Boundary — Custom Class Component
- **Decision**: Custom `ErrorBoundary` class component (React 16+ requirement)
- **Rationale**:
  - No library dependency (forbidden: no external error boundary libs)
  - Full control over fallback UI and Sentry integration
  - Compatible with React 18 concurrent features

## NFR6.4: State Management — React `useReducer` + `useTransition`
- **Decision**: Local state with `useReducer` for complex status transitions; `useTransition` for non-blocking updates
- **Rationale**:
  - No global state needed (component-scoped)
  - `useTransition` prevents UI freeze during frequent status updates
  - No Zustand/Redux (forbidden: no external state libs)

## NFR6.5: Styling — CSS Modules + Tailwind
- **Decision**: CSS Module for component-scoped styles + Tailwind utilities
- **Rationale**:
  - Mandated: CSS Modules + Tailwind
  - No styled-components, @emotion (forbidden)
  - `clsx` + `tailwind-merge` for conditional classes

## NFR6.6: TypeScript — Strict Mode
- **Decision**: Full strict TypeScript
- **Configuration**: Inherits from project `tsconfig.json` (`strict: true`, all strict flags)
- **No `any`**: All SSE event types explicitly typed via discriminated union

## NFR6.7: Testing — Vitest + React Testing Library
- **Decision**: Unit tests with Vitest + RTL; E2E with Playwright
- **Coverage Target**: ≥80% line coverage (feature scope floor)
- **MSW**: Mock SSE with `msw` custom handlers for deterministic tests

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR5 (Polling Fallback) | NFR6.2 | OK |
| NFR6 (Error Boundary) | NFR6.3 | OK |
| NFR7 (Sentry) | NFR6.3 | OK |