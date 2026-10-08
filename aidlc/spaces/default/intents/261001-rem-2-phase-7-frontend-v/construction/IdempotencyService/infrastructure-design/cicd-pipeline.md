# CI/CD Pipeline — IdempotencyService

## Pipeline Stages (Shared)

### 1. Lint & TypeCheck
- ESLint, TypeScript strict

### 2. Unit Tests
- **Vitest**: Mock `crypto.subtle`, `localStorage`
- **Coverage**: ≥80%
- **Tests**: `generateIdempotencyKey.test.ts`, `useIdempotencyStorage.test.ts`

### 3. Build & Deploy
- Part of frontend monorepo

## Quality Gates
| Gate | Threshold |
|------|-----------|
| Lint | 0 errors |
| TypeCheck | 0 errors |
| Unit Coverage | ≥80% |

## Traceability
| NFR Design | Pipeline Stage |
|------------|----------------|
| Deterministic Keys | Unit tests (fixed inputs → fixed outputs) |
| Storage Resilience | Unit tests (quota, parse, permission errors) |