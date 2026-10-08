# CI/CD Pipeline — ZoomPanControls

## Pipeline Stages (Shared)

### 1. Lint & TypeCheck
- ESLint, TypeScript strict

### 2. Unit Tests
- **Vitest**: Matrix math, transform calculations
- **Coverage**: ≥80%
- **Tests**: `Matrix3D.test.ts`, `ZoomPanControls.test.tsx` (with fake DOM)

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
| 60fps Performance | Unit tests (math accuracy) |
| Input Handling | Unit tests (pointer events) |