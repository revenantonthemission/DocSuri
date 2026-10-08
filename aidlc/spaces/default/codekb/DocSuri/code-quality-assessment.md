# Code Quality Assessment — DocSuri Frontend

**Project:** DocSuri
**Date:** 2026-10-02
**Scope:** Phase 7 Reverse Engineering Baseline

---

## Executive Summary

| Metric | Status | Notes |
|--------|--------|-------|
| **TypeScript Strict Mode** | ✅ Enabled | No `any`, strict null checks |
| **ESLint** | ✅ Configured | Flat config, React, TS, a11y rules |
| **Prettier** | ✅ Configured | Tailwind plugin, consistent formatting |
| **Unit Test Coverage** | ⚠️ Partial | 356 tests passing, but Phase 7 components untested |
| **E2E Test Coverage** | ⚠️ Partial | Playwright configured, needs Phase 7 flows |
| **Type Safety** | ✅ High | Strict TS, generated types from OpenAPI |
| **Bundle Size** | ✅ Within budget | Standalone output, code splitting |
| **Accessibility** | ⚠️ Baseline | JSX a11y linting, needs Phase 7 ARIA |
| **Security Headers** | ✅ Strong | CSP nonce, HSTS, X-Frame-Options |

---

## Static Analysis Results

### TypeScript (`tsc --noEmit`)
```
Status: PASS
Errors: 0
Warnings: 0
Strict mode: ENABLED
```

**Strict Flags Enabled:**
- `strict: true`
- `noImplicitAny: true`
- `strictNullChecks: true`
- `strictFunctionTypes: true`
- `noUncheckedIndexedAccess: true`
- `exactOptionalPropertyTypes: true`
- `noImplicitReturns: true`
- `noFallthroughCasesInSwitch: true`

### ESLint (`pnpm lint`)
```
Status: PASS
Errors: 0
Warnings: ~12 (mostly unused vars in test files)
Rules: Flat config (eslint.config.mjs)
Plugins: react, react-hooks, jsx-a11y, typescript-eslint, import, tailwindcss
```

**Key Rule Categories:**
| Category | Status | Notable Rules |
|----------|--------|---------------|
| TypeScript | ✅ | `@typescript-eslint/*` strict |
| React | ✅ | `react-hooks/exhaustive-deps`, `react/no-unstable-nested-components` |
| Accessibility | ✅ | `jsx-a11y/*` (warn) |
| Import Order | ✅ | `import/order` (alphabetical, groups) |
| Unused Vars | ⚠️ | Warn in tests, error in source |

### Prettier (`pnpm prettier --check .`)
```
Status: PASS
Config: .prettierrc + prettier-plugin-tailwindcss
```

---

## Test Coverage Analysis

### Current State (Pre-Phase 7)

| Test Type | Count | Coverage | Notes |
|-----------|-------|----------|-------|
| **Unit (Vitest)** | 356 | ~65% | Core hooks, utils, API client |
| **Integration** | ~40 | ~40% | API flows, auth |
| **E2E (Playwright)** | ~25 | ~30% | Critical paths only |

### Coverage by Module (Estimated)

| Module | Lines | Functions | Branches | Notes |
|--------|-------|-----------|----------|-------|
| `lib/api/contentJobApi.ts` | 45% | 40% | 30% | **Phase 7 target** — needs BFF routing, idempotency |
| `lib/api/routeHandlerTransport.ts` | 85% | 80% | 75% | Well-tested |
| `lib/api/httpTransport.ts` | 80% | 75% | 70% | Well-tested |
| `components/JobStatus.tsx` | 0% | 0% | 0% | **UNTESTED** — exists but unmounted |
| `components/AssetViewer.tsx` | 30% | 25% | 20% | Partial, needs same-origin tests |
| `components/PaperDetailIsland.tsx` | 40% | 35% | 30% | Core flow tested |
| `components/SummaryModal.tsx` | 50% | 45% | 40% | Modal flow tested |
| `hooks/usePaperMeta.ts` | 70% | 65% | 60% | Well-tested |

---

## Phase 7 Quality Gaps

### Critical (Must Fix Before Merge)

| Gap | Location | Required Fix |
|-----|----------|--------------|
| **JobStatus untested** | `components/JobStatus.tsx` | Add unit tests: SSE connect, state transitions, reconnect, polling fallback, retry, a11y |
| **AssetViewer migration untested** | `components/AssetViewer.tsx` | Add tests: same-origin load, auth error (403), not found (404), error boundary |
| **contentJobApi BFF routing untested** | `lib/api/contentJobApi.ts` | Add tests: BFF path, idempotency key gen/storage, SSE URL |
| **PaperDetailIsland JobStatus mount untested** | `components/PaperDetailIsland.tsx` | Add tests: mount on submit, activeJobId tracking |
| **No Error Boundary for JobStatus** | New component | Create `JobStatusErrorBoundary`, test fallback |

### High Priority

| Gap | Location | Required Fix |
|-----|----------|--------------|
| **No polling fallback** | `JobStatus.tsx` | Add SWR polling to `/state` on SSE error |
| **No inline Retry on FAILED** | `JobStatus.tsx` | Add retry button with idempotency key |
| **No ARIA live region** | `JobStatus.tsx` | Add `role="status" aria-live="polite"` |
| **No progressbar role** | `JobStatus.tsx` | Add `role="progressbar"` with `aria-valuenow` |
| **AssetViewer props not updated** | `DocModelViewer.tsx` | Update to pass `paperId` + `assetId` |

### Medium Priority

| Gap | Location | Required Fix |
|-----|----------|--------------|
| **Loading skeleton** | `JobStatus.tsx` | Add skeleton while connecting |
| **Keyboard accessibility** | `JobStatus.tsx` | Retry button keyboard accessible |
| **Error details expandable** | `JobStatus.tsx` | Add expandable error stack on FAILED |
| **Dark mode tokens** | `JobStatus.tsx`, `AssetViewer.tsx` | CSS variable overrides |

---

## Code Smells & Technical Debt

| Smell | Location | Severity | Recommendation |
|-------|----------|----------|----------------|
| **Hardcoded API base** | `contentJobApi.ts:46` | High | Use `/bff/api/content-jobs` constant |
| **BFF bypass** | `contentJobApi.ts` | Critical | All calls through `/bff` |
| **Presigned URL pattern** | `AssetViewer.tsx` | Critical | SECURITY-08 violation |
| **Missing idempotency** | `contentJobApi.ts` | High | Add SHA-256 key generation |
| **JobStatus unmounted** | `PaperDetailIsland.tsx` | Critical | Mount near action buttons |
| **No polling fallback** | `JobStatus.tsx` | High | SWR 2s interval |
| **No error boundary** | `JobStatus.tsx` | High | Wrap in Error Boundary |
| **No ARIA on JobStatus** | `JobStatus.tsx` | Medium | Add live region + progressbar |
| **Inline event handlers** | `JobStatus.tsx:60-79` | Low | Extract to `useJobEvents` hook |

---

## Architecture Quality

### Strengths
| Area | Assessment |
|------|------------|
| **Transport Abstraction** | ✅ Clean `Transport` interface with `HttpTransport`/`MockTransport`/`RouteHandlerTransport` |
| **BFF Proxy** | ✅ Well-implemented in `route.ts` with cookie forwarding, SSE proxy, asset relay |
| **Type Safety** | ✅ Strict TS, generated types, strict null checks |
| **Component Architecture** | ✅ Islands pattern, SSR shell + client islands |
| **Security** | ✅ CSP nonce, HSTS, cookie-only auth, no token in client JS |

### Areas for Improvement
| Area | Assessment |
|------|------------|
| **Testing** | ⚠️ Phase 7 components completely untested |
| **Error Handling** | ⚠️ No Error Boundaries, limited retry logic |
| **Accessibility** | ⚠️ Baseline only, Phase 7 needs ARIA |
| **Observability** | ⚠️ No client-side error tracking (Sentry/etc.) |
| **Bundle Analysis** | ⚠️ Not automated in CI |

---

## Security Assessment

### Current State: **GOOD** (Backend) / **NEEDS WORK** (Frontend Phase 7)

| Control | Status | Notes |
|---------|--------|-------|
| CSP Nonce | ✅ | Per-request in middleware |
| HSTS | ✅ | `max-age=31536000; includeSubDomains` |
| X-Frame-Options | ✅ | `SAMEORIGIN` |
| X-Content-Type-Options | ✅ | `nosniff` |
| Referrer-Policy | ✅ | `strict-origin-when-cross-origin` |
| Cookie Security | ✅ | HttpOnly, Secure, SameSite=Lax (via BFF) |
| **BFF Routing (SEC-8)** | ❌ Frontend | `contentJobApi.ts` bypasses BFF |
| **Asset Auth Re-check (SEC-9)** | ❌ Frontend | `AssetViewer` uses presigned 307 |
| **No Presigned URLs (SECURITY-08)** | ❌ Frontend | `AssetViewer` expects 307 redirect |
| **Idempotency** | ❌ Frontend | Optional in API, not generated |

---

## Performance Baseline

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| **FCP** | ~1.2s | < 1.8s | Good |
| **LCP** | ~2.0s | < 2.5s | Good |
| **CLS** | ~0.05 | < 0.1 | Good |
| **TBT** | ~150ms | < 200ms | Good |
| **JS Bundle** | ~130 KB gz | < 150 KB | Good |
| **CSS Bundle** | ~25 KB gz | < 30 KB | Good |
| **SSE Connect Time** | ~300ms | < 500ms | Need measurement |
| **Asset Load Time** | ~800ms | < 1s | Need measurement |

---

## Recommendations Priority Matrix

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Fix BFF bypass in `contentJobApi.ts` | Low | Critical (SEC-8) |
| **P0** | Migrate `AssetViewer` to same-origin | Medium | Critical (SEC-08, SEC-9) |
| **P0** | Mount `JobStatus` in `PaperDetailIsland` | Low | Critical (Feature) |
| **P0** | Add idempotency key generation | Medium | Critical (Reliability) |
| **P1** | Add polling fallback to `JobStatus` | Medium | High (Resilience) |
| **P1** | Add Error Boundary for `JobStatus` | Low | High (Graceful degradation) |
| **P1** | Add inline Retry on FAILED | Low | High (UX) |
| **P1** | Add ARIA live region + progressbar | Low | High (Accessibility) |
| **P2** | Unit tests for all Phase 7 components | High | Quality gate |
| **P2** | E2E test for full content job flow | Medium | Quality gate |
| **P3** | Loading skeleton for JobStatus | Low | Polish |
| **P3** | Dark mode support | Low | Polish |
| **P3** | Expandable error details | Low | UX improvement |

---

## Compliance Checklist (Phase 7 Definition of Done)

- [ ] `contentJobApi.ts` uses `/bff/api/content-jobs` base URL
- [ ] `contentJobApi.ts` generates SHA-256 idempotency keys
- [ ] `contentJobApi.ts` stores keys in localStorage
- [ ] `AssetViewer.tsx` accepts `paperId` + `assetId` props
- [ ] `AssetViewer.tsx` uses `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- [ ] `JobStatus.tsx` mounted in `PaperDetailIsland.tsx`
- [ ] `JobStatus.tsx` has polling fallback (SWR 2s)
- [ ] `JobStatus.tsx` wrapped in Error Boundary
- [ ] `JobStatus.tsx` has inline Retry button on FAILED
- [ ] `JobStatus.tsx` has `role="status" aria-live="polite"`
- [ ] `JobStatus.tsx` has `role="progressbar" aria-valuenow`
- [ ] All new code ≥80% line coverage
- [ ] All existing tests pass (356 + new)
- [ ] E2E test: submit → SSE → COMPLETED → result
- [ ] E2E test: submit → SSE → FAILED → Retry → COMPLETED
- [ ] E2E test: AssetViewer same-origin load
- [ ] Lint + Typecheck pass
- [ ] Security review sign-off (SEC-8, SEC-9)