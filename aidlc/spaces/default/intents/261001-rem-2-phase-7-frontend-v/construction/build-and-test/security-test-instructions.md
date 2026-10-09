# Security Test Instructions — Build and Test

Verified against commit `156fb206` on 2026-10-09. The security posture is anchored by the mandated mid-implementation asset security review and pinned by tests.

## Executed security checks (all green)

```bash
cd frontend
./node_modules/.bin/vitest run --config vitest.u3.config.ts   # BFF asset branch + migrated surfaces + static no-presigned checks
./node_modules/.bin/vitest run                                # combined (includes u1 job-stream auth/cookie regressions)
```

- **BFF asset branch (C5 / SEC-8 / SEC-9):** explicit redirect refusal (`redirect: 'manual'`), image-only passing with `nosniff`, `private, max-age=60` fallback with upstream values preserved, empty no-store 404 collapse (no Location/body), session Set-Cookie relayed from real upstream responses even on error (none fabricated on timeout), HEAD support, 10 s timeout, non-canonical path segments refused before any upstream fetch. Pinned in `test/u3BffAssetBranch.test.ts` and `test/assetDelivery.test.ts`.
- **No presigned delivery anywhere in the changed surfaces:** `browserAssetSrc` fails closed for off-origin/absolute URLs; static scans in `test/u3AssetViewer.test.tsx`; production CSP `img-src 'self' data:` checked in `test/assetDelivery.test.ts`.
- **BFF-only content-job routing:** all content-job calls go through `/bff/api/content-jobs` (u1/u2 suites + static checks); no direct `/api/content-jobs/*` calls.
- **Redaction/scrubbing:** job diagnostics never contain identifiers or content (u1/u2 telemetry tests); no secrets in client code; no new network egress introduced by the viewer controls/minimap (same authorized `src` only).

## Review artifacts

- `construction/u3-secure-assets/code-generation/reviews/asset-security-review-01.md` — verdict READY with U3-SEC-01/U3-BLD-01 resolved and U3-SEC-02/U3-SCOPE-01 dispositioned as accepted-risk deferrals (schema wording drift; dormant UnsubscribePage mount).

## How to re-run

```bash
./node_modules/.bin/vitest run --config vitest.u3.config.ts --coverage
rg -n "presign|signed|amazonaws|X-Amz|getAssetUrl|issueAssetToken" frontend/components/AssetViewer.tsx frontend/components/UnsubscribePage.tsx frontend/lib/api/contentJobApi.ts frontend/lib/api/assetSrc.ts
```

Backend-side auth/license re-check and real-store security verification are outside this repository's frontend run; they remain recorded obligations with their own operational authorizations.
