# CI/CD Pipeline — ErrorBoundary

## Pipeline Stages (Shared)

### 1. Lint & TypeCheck
- ESLint, TypeScript strict

### 2. Unit Tests
- **Vitest**: Trigger errors via `act()`, test fallback render
- **Coverage**: ≥80%
- **Tests**: `ErrorBoundary.test.tsx`, `ErrorBoundaryFallback.test.tsx`

### 3. E2E Tests
- **Playwright**: Inject error → verify fallback → retry → success
- **Test Files**: `errorboundary-retry.spec.ts`

### 4. Build & Deploy
- Sentry DSN injected at build time (`NEXT_PUBLIC_SENTRY_DSN`)
- Source maps uploaded to Sentry automatically

## Quality Gates
| Gate | Threshold |
|------|-----------|
| Lint | 0 errors |
| TypeCheck | 0 errors |
| Unit Coverage | ≥80% |
| E2E | All pass |

## Traceability
| NFR Design | Pipeline Stage |
|------------|----------------|
| Error Containment | Unit + E2E tests |
| Sentry Integration | Build (DSN injection) |
| Accessibility | axe-core in CI |