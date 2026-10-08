**Collaborator:** aidlc-devsecops-agent

## Contribution

### Security & Supply Chain Assessment

**Current Security Posture (from reverse-engineering):**

**Security Headers (middleware.ts):**
- **CSP:** Nonce-based per-request via Edge runtime `crypto.randomUUID()`
  - Production: `script-src 'self' 'nonce-{uuid}' https://www.google.com/recaptcha/ ...`
  - Dev: `'unsafe-inline' 'unsafe-eval'` for HMR
- **HSTS:** `max-age=31536000; includeSubDomains`
- **X-Frame-Options:** `SAMEORIGIN`
- **X-Content-Type-Options:** `nosniff`
- **Referrer-Policy:** `strict-origin-when-cross-origin`
- **CSP Nonce:** Per-request `crypto.randomUUID()` in Edge middleware

**BFF Proxy Security (route.ts):**
- Cookie forwarding: `req.headers.get('cookie')` → Gateway
- Set-Cookie relay: Gateway `set-cookie` → Browser response
- No token in client JS — httpOnly session cookie only
- SSE proxy with `Last-Event-ID` support
- Asset relay (`proxyAssetImage`): Validates content-type `image/*`, status 200, no 307 redirect
- Per-path timeouts prevent resource exhaustion
- SQ3 mitigation: GET retry once after 1.5s (502/503/504)

**Gateway Security (Backend — inferred):**
- SEC-8: Gateway injects `x-principal-user-id` header ✅
- SEC-9: Asset delivery re-checks auth/license at delivery ✅
- RJ-AC04: CAS state transitions ✅
- RJ-AC05: Owner-scoped authorization at every boundary ✅
- Effect ledger prevents double-payment ✅

---

### Critical Security Violations (Frontend — Phase 7 Must Fix)

| Violation | Standard | Location | Fix |
|-----------|----------|----------|-----|
| **SEC-8 Bypass** | All calls through BFF for principal injection | `contentJobApi.ts:46` uses `/api/content-jobs` | Change `API_BASE` to `/bff/api/content-jobs` |
| **SECURITY-08** | No presigned URLs anywhere | `AssetViewer.tsx:27` expects 307 redirect | Migrate to same-origin `/bff/api/papers/{id}/assets/{id}` |
| **SEC-9 Bypass** | Asset auth re-check at delivery | `AssetViewer` uses presigned URL (no re-check) | BFF `proxyAssetImage()` does auth re-check |

**Risk Assessment:**
- **SEC-8 Bypass:** HIGH — Requests without principal header fail authZ at gateway
- **SECURITY-08:** HIGH — Presigned URLs expose object storage directly
- **SEC-9 Bypass:** HIGH — No owner validation at asset delivery time

---

### Supply Chain Security

**Dependencies (package.json):**
- **Licenses:** MIT, Apache-2.0, MPL-2.0 (axe-core), BSD-3-Clause — **No GPL/AGPL**
- **No known vulnerabilities** in production deps (pnpm audit clean)
- **Dev dependencies only:** axe-core (MPL-2.0, weak copyleaf, OK for dev)

**Forbidden Patterns (enforced via ESLint):**
- NEVER `axios` — reduces attack surface, use native fetch + Transport
- NEVER `@tanstack/react-query` — use SWR (lighter, same stack)
- NEVER `lodash` — use native JS
- NEVER `moment.js` — use native Date/Intl
- NEVER `classnames` — use `clsx`
- NEVER `styled-components` / `@emotion/*` — CSS-in-JS increases bundle

**CI/CD Security Gates:**
- `pnpm audit --prod` in CI (must pass)
- Dependabot PRs for security patches
- No secrets in repo (`.env*` in `.gitignore`)
- Docker multi-stage build (standalone output)

**Gaps:**
- No client-side error tracking (Sentry/DataDog) — consider for Phase 7
- No SAST/DAST in CI — CodeQL or similar recommended
- No dependency license check in CI — `pnpm-licenses` could be added

---

## Positions

- **AGREE:** CSP nonce per-request (SEC-4) — implemented correctly
- **AGREE:** HSTS, X-Frame-Options, Referrer-Policy — implemented correctly
- **AGREE:** Cookie-only auth via BFF (no token in client JS) — correct pattern
- **AGREE:** Forbidden patterns (axios, tanstack-query, lodash, moment, classnames, styled-components) — reduces attack surface
- **AGREE:** No GPL/AGPL in production dependencies
- **MANDATED FIX:** BFF routing for contentJobApi (SEC-8 compliance)
- **MANDATED FIX:** Same-origin asset delivery via BFF (SEC-9, SECURITY-08 compliance)
- **MANDATED FIX:** Remove presigned URL logic from AssetViewer (SECURITY-08 compliance)
- **RECOMMEND:** Add client-side error tracking (Sentry) for Phase 7 observability
- **RECOMMEND:** Add CodeQL SAST to CI pipeline
- **RECOMMEND:** Add `pnpm-licenses` check to CI for license compliance