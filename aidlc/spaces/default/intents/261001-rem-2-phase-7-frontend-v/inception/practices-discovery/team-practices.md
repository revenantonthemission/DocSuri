# Team Practices — DocSuri (Phase 7 Frontend Wiring)

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Project Type:** Brownfield
**Discovered:** 2026-10-02
**Affirmed:** Pending human approval

---

## Way of Working

We use **trunk-based development**. All work merges to `main` via short-lived feature branches (typically resolved within 1-2 days). Long-lived branches accumulate merge debt; we avoid them.

For Construction worktrees, the worktree base branch is `main` and the merge target is `main`.

If our project requires multiple environments (staging, production), we still keep one trunk and gate releases via tags or environment-specific deployment configs — not via long-lived release branches.

We **squash-merge** Bolt branches into `main`. Each Bolt becomes one commit on the trunk, named by the Bolt slug, with the full Bolt commit history preserved on the source branch until the worktree is discarded.

Squash gives us a clean linear `main` history that maps 1:1 to delivery-planning's Bolt sequence. We accept the trade-off of losing intermediate commits on `main` because the audit log preserves the full event sequence anyway.

**Evidence from reverse-engineering:**
- Git history shows feature branches with short lifetimes
- `frontend/` uses Next.js standalone output for containerized deployment
- CI/CD via GitHub Actions (implied by repo structure)
- No long-lived release branches observed

---

## Walking Skeleton

**Stance: ON** — Build a thin end-to-end slice first. A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect before the real features go in. For this feature scope, we will run the skeleton ceremony: the first Unit will be the smallest working integrated slice, run through all applicable per-unit stages including Code Generation, verified with the Construction Verification Command, and require human skeleton checkpoint approval.

**Evidence from reverse-engineering:**
- Feature scope (`feature`) does not declare `skeleton: on` by default
- Phase 7 is frontend wiring only — backend contract already complete (473 tests)
- **Human Decision:** Walking skeleton ON for this feature (end-to-end verification first)

---

## Testing Posture

**Methodology:** test-after
**Ordering:** Test-last per component — Implement component fully, then write its tests.

**Scope floors (feature scope):**
- 80% line-coverage floor for new code
- CI execution before merge
- Existing test suites must remain green (473 backend + 356 frontend)

**Evidence from reverse-engineering:**
- Current coverage: ~65% overall, but Phase 7 target components at 0% (JobStatus, contentJobApi BFF routing)
- 356 frontend tests passing (Vitest + React Testing Library)
- 473 backend tests passing
- Playwright E2E configured (~25 tests, ~30% coverage)
- CI runs lint, typecheck, test:coverage, test:e2e
- **Gap:** Phase 7 components (JobStatus, AssetViewer migration, contentJobApi BFF routing) completely untested
- **Gap:** No Error Boundary tests, no SSE polling fallback tests, no idempotency key tests

**Affirmed posture for Phase 7:**
- Maintain test-after methodology (team default)
- Ordering: Test-last per component (implement fully, then test)
- 80% coverage floor for new code enforced in CI
- All existing tests must remain green

---

## Deployment

We **deploy on merge** to staging environments **and automatically to production** (continuous deployment). Every commit that passes CI (lint, typecheck, test:coverage, test:e2e) auto-deploys to production.

This reflects the team's investment in test coverage and observability, graduating to continuous deployment to production.

**Evidence from reverse-engineering:**
- Next.js `output: 'standalone'` for containerized deployment
- Dockerfile present in `frontend/`
- BFF proxy in same Next.js server (`/bff/[...path]`)
- Gateway URL via `DOCSURI_GATEWAY_URL` env var
- **Human Decision:** Continuous deployment to production on merge

---

## Code Style

We defer to project-level configurations:
- **Formatter:** Prettier (JS/TS) — `.prettierrc` with `prettier-plugin-tailwindcss`
- **Linter:** ESLint 9.x flat config — `eslint.config.mjs` with React, TypeScript, JSX a11y, import order, Tailwind plugins
- **Naming conventions:** camelCase for JS/TS, PascalCase for components, UPPER_SNAKE_CASE for constants
- **TypeScript:** Strict mode enabled (strict, noImplicitAny, strictNullChecks, strictFunctionTypes, noUncheckedIndexedAccess, exactOptionalPropertyTypes, noImplicitReturns, noFallthroughCasesInSwitch)

**Evidence from reverse-engineering:**
- `eslint.config.mjs` uses flat config with: @typescript-eslint, eslint-plugin-react, eslint-plugin-react-hooks, eslint-plugin-jsx-a11y, eslint-plugin-import, eslint-plugin-tailwindcss
- `.prettierrc` with `prettier-plugin-tailwindcss`
- `tsconfig.json` has `strict: true` and all strict flags
- `clsx` + `tailwind-merge` for className composition
- CSS Modules for component-scoped styles + Tailwind utilities
- Forbidden patterns enforced via ESLint `no-restricted-imports`: axios, tanstack-query, lodash, moment, classnames, styled-components, @emotion/*

**Forbidden patterns (enforced):**
- NEVER use `axios` — use native `fetch` + custom Transport
- NEVER use `@tanstack/react-query` — use SWR (lighter)
- NEVER use `lodash` — use native JS
- NEVER use `moment.js` — use native Date/Intl
- NEVER use `classnames` — use `clsx`
- NEVER use `styled-components` or `@emotion/*` — use CSS Modules + Tailwind

**Mandated patterns:**
- ALWAYS use native `fetch` + custom Transport interface for API calls
- ALWAYS use SWR for server state (stale-while-revalidate)
- ALWAYS use `clsx` + `tailwind-merge` for conditional classNames
- ALWAYS use CSS Modules + Tailwind for styling
- ALWAYS use native `crypto.subtle` for cryptographic operations
- ALWAYS use `EventSource` for SSE (native browser API)
- ALWAYS use strict TypeScript — no `any`, no implicit any