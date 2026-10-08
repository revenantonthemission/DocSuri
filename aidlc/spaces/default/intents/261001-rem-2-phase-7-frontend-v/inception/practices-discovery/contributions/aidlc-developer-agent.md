**Collaborator:** aidlc-developer-agent

## Contribution

### Code Style & Structure Assessment

**Current State (from reverse-engineering):**

**TypeScript Configuration:**
- `strict: true` with all strict flags enabled
- `noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noFallthroughCasesInSwitch`
- Path aliases: `@/*`, `@/components/*`, `@/lib/*`, `@/types/*`
- Generated types from OpenAPI in `types/generated/`

**ESLint Configuration (Flat Config):**
- `eslint.config.mjs` with plugins:
  - `@typescript-eslint` (strict TS rules)
  - `eslint-plugin-react` (React rules)
  - `eslint-plugin-react-hooks` (exhaustive-deps, no-unstable-nested-components)
  - `eslint-plugin-jsx-a11y` (accessibility)
  - `eslint-plugin-import` (import order, groups)
  - `eslint-plugin-tailwindcss` (Tailwind class sorting)
- `no-restricted-imports` enforces forbidden patterns

**Prettier:**
- `.prettierrc` with `prettier-plugin-tailwindcss` for class sorting
- Single quotes, trailing commas, 100 char line width

**Package Manager:** pnpm 9.x with frozen lockfile in CI

**Architecture Patterns Observed:**

1. **Transport Abstraction** — Clean interface with 3 implementations:
   ```typescript
   interface Transport {
     send({ method, path, body, headers, idempotent }): TransportResponse
   }
   // HttpTransport (prod), MockTransport (dev), RouteHandlerTransport (client→BFF)
   ```

2. **BFF Proxy** — `frontend/app/bff/[...path]/route.ts`:
   - Cookie forwarding, SSE proxy, asset relay, Set-Cookie relay
   - Per-path timeouts (evidence 90s, search 30s, SSE 15s, asset 10s)
   - SQ3 mitigation: GET retry once after 1.5s (502/503/504)

3. **Islands Pattern** — SSR shell + client islands:
   - `app/paper/[id]/page.tsx` (SSR) → `PaperDetailIsland` (client)
   - Action bar, modals, inline doc-model (desktop) / full-screen routes (mobile)

4. **Component Structure:**
   - `PaperDetailIsland` — main island (actions, modals, metadata)
   - `JobStatus` — SSE consumer (exists, unmounted)
   - `AssetViewer` — presigned URL pattern (migration target)
   - `SummaryModal` — 요약/번역 trigger
   - `DocModelViewer` — full text with AssetViewer for figures

**Code Style Conventions:**
- `clsx` + `tailwind-merge` for conditional classNames
- CSS Modules for component-scoped + Tailwind utilities
- Native `fetch` + custom Transport (no axios)
- SWR for server state (planned for polling fallback)
- Native `EventSource` for SSE
- Native `crypto.subtle` for SHA-256 hashing

**Gaps for Phase 7:**
1. `contentJobApi.ts` hardcodes `/api/content-jobs` (bypasses BFF)
2. `AssetViewer` uses presigned 307 redirect (SECURITY-08 violation)
3. `JobStatus` exists but unmounted in `PaperDetailIsland`
4. No idempotency key generation in `contentJobApi`
4. No polling fallback in `JobStatus`
5. No Error Boundary for `JobStatus`
6. No ARIA live region / progressbar on `JobStatus`

---

## Positions

- **AGREE:** Prettier + Tailwind plugin for formatting (already configured)
- **AGREE:** ESLint flat config with React/TS/a11y/import/Tailwind (already configured)
- **AGREE:** CSS Modules + Tailwind for styling (current pattern)
- **AGREE:** `clsx` + `tailwind-merge` for classNames (current pattern)
- **AGREE:** Strict TypeScript with all strict flags (already configured)
- **AGREE:** Native `fetch` + custom Transport (no axios — enforced by ESLint)
- **AGREE:** SWR for server state (already in stack, planned for polling)
- **AGREE:** Native `EventSource` for SSE (current implementation)
- **AGREE:** Native `crypto.subtle` for SHA-256 (no crypto-js)
- **AGREE:** Forbidden patterns enforced via ESLint `no-restricted-imports`:
  - NEVER axios → use native fetch + Transport
  - NEVER @tanstack/react-query → use SWR
  - NEVER lodash → use native JS
  - NEVER moment.js → use native Date/Intl
  - NEVER classnames → use clsx
  - NEVER styled-components/@emotion/* → use CSS Modules + Tailwind
- **AGREE:** Path aliases `@/*`, `@/components/*`, `@/lib/*`, `@/types/*`
- **AGREE:** CSS Modules for component scope + Tailwind utilities