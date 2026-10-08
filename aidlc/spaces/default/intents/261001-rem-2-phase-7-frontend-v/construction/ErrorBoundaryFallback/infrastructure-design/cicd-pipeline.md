# CI/CD Pipeline — ErrorBoundaryFallback

## Pipeline Stages (Shared)

### 1. Lint & TypeCheck
- ESLint, TypeScript strict

### 2. Unit Tests
- **Vitest + RTL**: Render variants, test reset callback, accessibility
- **Coverage**: ≥80%
- **A11y**: axe-core in tests

### 3. Build & Deploy
- Part of frontend monorepo

## Quality Gates
| Gate | Threshold |
|------|-----------|
| Lint | 0 errors |
| TypeCheck | 0 errors |
| Unit Coverage | ≥80% |
| A11y | 0 violations |

## Traceability
| NFR Design | Pipeline Stage |
|------------|----------------|
| Accessibility (WCAG 2.1 AA) | Unit tests + axe-core |
| Reset Reliability | Unit tests |