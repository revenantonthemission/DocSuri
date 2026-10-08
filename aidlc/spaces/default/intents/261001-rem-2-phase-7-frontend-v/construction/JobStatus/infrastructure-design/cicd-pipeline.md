# CI/CD Pipeline — JobStatus

## Pipeline Stages (GitHub Actions)

### 1. Lint & TypeCheck
```yaml
- name: Lint
  run: npm run lint
- name: TypeCheck
  run: npm run typecheck
```
- **ESLint**: Flat config with React, TypeScript, JSX a11y, import order, Tailwind
- **TypeScript**: Strict mode, no `any`, no implicit any

### 2. Unit Tests
```yaml
- name: Test
  run: npm run test:coverage
```
- **Vitest** + React Testing Library
- **MSW**: Mock SSE with custom handlers
- **Coverage Floor**: ≥80% lines (feature scope)
- **Test Files**: `JobStatus.test.tsx`, `useSSE.test.ts`, `usePollingFallback.test.ts`

### 3. E2E Tests
```yaml
- name: E2E
  run: npm run test:e2e
```
- **Playwright**: Chromium, Firefox, WebKit
- **Scenarios**: SSE connect, event flow, fallback activation, error boundary retry
- **Test Files**: `jobstatus-sse.spec.ts`, `jobstatus-fallback.spec.ts`

### 4. Build
```yaml
- name: Build
  run: npm run build
```
- **Output**: `.next/standalone` for Docker
- **Bundle Analysis**: `next-bundle-analyzer` (verify ≤15KB)

### 5. Docker Build & Push
```yaml
- name: Docker Build
  run: docker build -t $REGISTRY/docjsuri-frontend:$SHA .
- name: Docker Push
  run: docker push $REGISTRY/docjsuri-frontend:$SHA
```

### 6. Deploy (Continuous Deployment)
```yaml
- name: Deploy
  run: |
    # Vercel: automatic on merge to main
    # AWS ECS: update service with new image
```
- **Trigger**: Merge to `main` (after all checks pass)
- **Rollback**: Previous image tag available

## Quality Gates
| Gate | Threshold | Blocking |
|------|-----------|----------|
| Lint | 0 errors | Yes |
| TypeCheck | 0 errors | Yes |
| Unit Coverage | ≥80% lines | Yes |
| E2E | All pass | Yes |
| Bundle Size | ≤15KB gzipped | Warning |

## Traceability
| NFR Design | Pipeline Stage |
|------------|----------------|
| Performance (bundle ≤15KB) | Build + Bundle Analysis |
| Reliability (ErrorBoundary) | Unit + E2E tests |
| Observability (Sentry) | Deploy (DSN injection) |
| Security (CSP) | Lint (no-restricted-imports) |