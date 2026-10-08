# Evidence — Practices Discovery (Phase 7 Frontend Wiring)

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Sources Scanned

1. **Reverse Engineering Artifacts** (9 files under `aidlc/spaces/default/codekb/DocSuri/`):
   - `business-overview.md` — Product context, user flows, tech stack
   - `architecture.md` — System architecture, data flows, integration points
   - `code-structure.md` — Repository layout, module dependencies, migration checklist
   - `api-documentation.md` — Current vs required endpoints, schemas, SSE format
   - `component-inventory.md` — All components, detailed analysis, dependency graph
   - `technology-stack.md` — Full stack, versions, configs, CI/CD, performance budgets
   - `dependencies.md` — Prod/dev deps, licenses, bundle size, forbidden patterns
   - `code-quality-assessment.md` — Static analysis, test coverage, gaps, recommendations
   - `reverse-engineering-timestamp.md` — Scan metadata

2. **Repository Configuration** (scanned directly):
   - `frontend/package.json` — Dependencies, scripts
   - `frontend/tsconfig.json` — TypeScript strict config
   - `frontend/eslint.config.mjs` — ESLint flat config
   - `frontend/.prettierrc` — Prettier + Tailwind plugin
   - `frontend/next.config.mjs` — Next.js config (standalone output)
   - `frontend/middleware.ts` — CSP nonce, security headers
   - `frontend/next.config.mjs` — Next.js config
   - `frontend/Dockerfile` — Containerized deployment

3. **Source Code** (key files):
   - `frontend/lib/api/contentJobApi.ts` — Content job API (bypasses BFF)
   - `frontend/components/JobStatus.tsx` — SSE component (unmounted)
   - `frontend/components/AssetViewer.tsx` — Presigned URL pattern
   - `frontend/app/bff/[...path]/route.ts` — BFF proxy (ready)
   - `frontend/components/PaperDetailIsland.tsx` — Mount point
   - `frontend/components/SummaryModal.tsx` — Trigger point
   - `frontend/components/DocModelViewer.tsx` — Asset consumer
   - `frontend/lib/api/routeHandlerTransport.ts` — BFF transport

4. **Git History & CI** (inferred):
   - Feature branch workflow (short-lived)
   - Squash-merge to main
   - GitHub Actions CI (implied by repo structure)

---

## Lead Agent Inferences (aidlc-pipeline-deploy-agent)

| Practice Area | Inference | Evidence |
|---------------|-----------|----------|
| **Branching** | Trunk-based, short-lived feature branches (1-2 days) | Git structure, no long-lived release branches |
| **Merging** | Squash-merge to main | Org.md default, no merge commits observed |
| **Walking Skeleton** | OFF for feature scope | Feature scope doesn't declare `skeleton: on`; Phase 7 is wiring only |
| **Testing Methodology** | test-after | Org.md default for feature scope; 356 tests exist |
| **Testing Ordering** | Implement layer, then test | Org.md default; current tests are post-implementation |
| **Coverage Floor** | 80% line coverage (feature scope) | Org.md: `feature` adds 80% floor |
| **Deployment** | Deploy on merge to staging; prod manual | Org.md default; Next.js standalone + Dockerfile |
| **Formatter** | Prettier + Tailwind plugin | `.prettierrc` + `prettier-plugin-tailwindcss` |
| **Linter** | ESLint 9 flat config | `eslint.config.mjs` with React, TS, a11y, import, Tailwind |
| **Naming** | camelCase/PascalCase/UPPER_SNAKE_CASE | TypeScript conventions, component files |
| **TypeScript** | Strict mode all flags | `tsconfig.json` strict: true + all strict flags |

---

## Support Agent Reviews (Blind)

### aidlc-quality-agent (Testing Posture)

**Inspected:** `code-quality-assessment.md`, `technology-stack.md`, `dependencies.md`, test files

**Findings:**
- Current coverage ~65% overall, but Phase 7 components at 0% (JobStatus, contentJobApi BFF routing)
- 356 frontend tests (Vitest + RTL), 473 backend tests
- Playwright E2E configured but only ~30% coverage
- CI runs: lint, typecheck, test:coverage, test:e2e
- **Gaps:** Phase 7 components completely untested; no Error Boundary tests; no SSE polling fallback tests; no idempotency key tests

**Positions:**
- AGREE: test-after methodology (team default)
- AGREE: 80% coverage floor for feature scope
- AGREE: implement layer then test ordering
- AGREE: All existing tests must remain green

### aidlc-developer-agent (Code Style & Structure)

**Inspected:** `code-structure.md`, `architecture.md`, `component-inventory.md`, source files

**Findings:**
- Clean Transport abstraction (HttpTransport, MockTransport, RouteHandlerTransport)
- BFF proxy well-architected in `route.ts` (cookie forwarding, SSE proxy, asset relay)
- Islands pattern correctly implemented (SSR shell + client islands)
- Strict TypeScript with all strict flags
- Clean component architecture (PaperDetailIsland as main island)
- **Gaps:** BFF bypass in contentJobApi.ts; AssetViewer presigned URL; JobStatus unmounted

**Positions:**
- AGREE: Prettier + Tailwind plugin for formatting
- AGREE: ESLint flat config with React/TS/a11y/import/Tailwind
- AGREE: CSS Modules + Tailwind for styling
- AGREE: clsx + tailwind-merge for classNames
- AGREE: Strict TypeScript (all strict flags)
- AGREE: Forbidden patterns (axios, tanstack-query, lodash, moment, classnames, styled-components)

### aidlc-devsecops-agent (Security & Supply Chain)

**Inspected:** `architecture.md`, `api-documentation.md`, `code-quality-assessment.md`, `middleware.ts`, `route.ts`

**Findings:**
- Strong security headers: CSP nonce, HSTS, X-Frame-Options, Referrer-Policy
- BFF proxy implements cookie forwarding, Set-Cookie relay, SSE proxy
- Gateway injects principal (SEC-8) — but frontend bypasses BFF
- Asset auth re-check implemented in gateway (SEC-9) — but frontend uses presigned URLs
- **Violations:** SEC-8 bypass, SECURITY-08 presigned URLs, SEC-9 no auth re-check
- Dependencies: No GPL/AGPL; MIT/Apache-2.0/MPL-2.0 only
- CSP nonce per-request via Edge runtime crypto.randomUUID()

**Positions:**
- AGREE: CSP nonce per-request (SEC-4)
- AGREE: HSTS, X-Frame-Options, Referrer-Policy
- AGREE: Cookie-only auth via BFF (no token in client JS)
- AGREE: Forbidden: axios, tanstack-query (attack surface reduction)
- **MANDATED FIX:** BFF routing for contentJobApi (SEC-8)
- **MANDATED FIX:** Same-origin asset delivery (SEC-9, SECURITY-08)

---

## Interview Decisions (Human Affirmed)

### 1. Walking Skeleton
**Decision:** B — Yes, build skeleton (end-to-end verification first)
**Status:** AFFIRMED — Walking skeleton ON for this feature

### 2. Testing Methodology
**Decision:** A — test-after (team default)
**Status:** AFFIRMED — Maintain test-after methodology

### 3. Testing Ordering
**Decision:** C — Test-last per component (implement fully, then test)
**Status:** AFFIRMED — Test-last per component ordering

### 4. Deployment — Production Approval
**Decision:** B — Automatic on merge (continuous deployment)
**Status:** AFFIRMED — Continuous deployment to production on merge

### 5. Code Style — Forbidden Patterns
**Decision:** A — Yes, all forbidden (enforce via ESLint)
**Status:** AFFIRMED — All forbidden patterns enforced

### 6. Testing Coverage Floor
**Decision:** A — 80% (matches org.md feature scope)
**Status:** AFFIRMED — 80% line coverage floor

### 7. Security Review Timing
**Decision:** B — Mid (Week 2) after AssetViewer complete
**Status:** AFFIRMED — Mid-implementation security review

### 8. Observability
**Decision:** A — Yes, add Sentry (full error tracking for Phase 7)
**Status:** AFFIRMED — Add Sentry for Phase 7 error tracking

## Unresolved Uncertainties

1. **Walking Skeleton for Phase 7:** Feature scope doesn't declare `skeleton: on`. If team wants skeleton ceremony, scope file must be updated.
2. **Testing Methodology Mix:** If team wants BDD for user-facing flows + test-after for internals, methodology becomes "custom" — need clarification.
3. **Security Review Timing:** Architect review suggested mid-implementation (Week 2) — need team confirmation.
4. **Observability:** No client-side error tracking (Sentry/DataDog) currently — decide if Phase 7 should add.

---

## Next Steps

1. ✅ Human reviewed and answered all interview questions
2. ✅ Lead agent integrated decisions into final `team-practices.md` and `discovered-rules.md`
3. ⏳ Affirmation gate: Approve → promote to `aidlc/spaces/default/memory/team.md` and `project.md`
4. ⏳ Continue to Requirements Analysis (2.3)