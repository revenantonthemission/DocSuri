# CI/CD Pipeline — ContentJobApi

## Pipeline Stages (Shared with JobStatus)

### 1. Lint & TypeCheck
- ESLint: `no-restricted-imports` blocks direct gateway URLs
- TypeScript: Strict mode

### 2. Unit Tests
- **Vitest** + MSW mocking BFF proxy
- **Coverage**: ≥80% lines
- **Tests**: `contentJobApi.test.ts`, `Transport.test.ts`, `useIdempotencyStorage.test.ts`

### 3. E2E Tests
- **Playwright**: Full submission flow
- **MSW**: Mock gateway responses
- **Scenarios**: Submit → status → cancel, idempotency retry, network error retry

### 4. Build & Deploy
- Same as JobStatus (part of frontend monorepo)

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
| SEC-8 Enforcement | Lint (no-restricted-imports) |
| Idempotency Retry | Unit + E2E tests |
| Error Sanitization | Unit tests |