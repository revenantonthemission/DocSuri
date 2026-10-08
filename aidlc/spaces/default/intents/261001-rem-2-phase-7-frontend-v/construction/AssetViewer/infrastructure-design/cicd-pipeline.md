# CI/CD Pipeline — AssetViewer

## Pipeline Stages (Shared)

### 1. Lint & TypeCheck
- ESLint: `no-restricted-imports` blocks presigned URL patterns
- TypeScript: Strict mode

### 2. Unit Tests
- **Vitest**: Mock BFF asset route
- **Coverage**: ≥80%
- **Tests**: `AssetViewer.test.tsx`, `PDFRenderer.test.tsx`, `ImageRenderer.test.tsx`, `VideoRenderer.test.tsx`

### 3. E2E Tests
- **Playwright**: Real asset flow
- **Scenarios**: PDF load, image load, video stream, Range requests, auth expiry, error boundary retry
- **Test Files**: `assetviewer-pdf.spec.ts`, `assetviewer-auth.spec.ts`, `assetviewer-error.spec.ts`

### 4. Security Scan
- **CodeQL**: Scan for presigned URL patterns
- **ESLint**: Custom rule for `presigned`, `s3.amazonaws.com`, `blob.core.windows.net`

### 5. Build & Deploy
- PDF.js worker copied to `/public` during build
- Same as JobStatus (frontend monorepo)

## Quality Gates
| Gate | Threshold |
|------|-----------|
| Lint | 0 errors |
| TypeCheck | 0 errors |
| Unit Coverage | ≥80% |
| E2E | All pass |
| Security Scan | 0 findings |

## Traceability
| NFR Design | Pipeline Stage |
|------------|----------------|
| SECURITY-08 (No Presigned) | Lint + Security Scan |
| SEC-9 (Auth Re-check) | E2E (auth expiry test) |
| Range Requests | E2E (video seek, PDF byte-range) |