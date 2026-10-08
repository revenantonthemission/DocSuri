# Technology Stack — DocSuri Frontend

**Project:** DocSuri
**Date:** 2026-10-02

---

## Core Framework

| Technology | Version | Purpose |
|------------|---------|---------|
| **Next.js** | 15.x (App Router) | React framework, SSR, standalone output |
| **React** | 18.x | UI library, concurrent features |
| **TypeScript** | 5.x (strict) | Type safety, strict mode enabled |

---

## Runtime & Build

| Tool | Version | Purpose |
|------|---------|---------|
| **Node.js** | 20.x LTS | JavaScript runtime |
| **pnpm** | 9.x | Package manager (fast, disk-efficient) |
| **Turbopack** | Built-in | Next.js dev/build bundler |
| **SWCs** | Built-in | Fast TypeScript/JS compilation |

---

## Styling

| Technology | Version | Purpose |
|------------|---------|---------|
| **CSS Modules** | Native | Component-scoped styles (`.module.css`) |
| **Tailwind CSS** | 3.x | Utility-first utilities (via className) |
| **CSS Variables** | Native | Design tokens (colors, spacing, radii) |

**Design Token Pattern:**
```css
:root {
  --color-status-running: #3B82F6;
  --color-status-completed: #22C55E;
  --color-status-failed: #EF4444;
  --progress-height: 8px;
  --jobstatus-radius: 8px;
}
```

---

## Data Fetching & State

| Library | Version | Purpose |
|---------|---------|---------|
| **SWR** | 2.x | Server state, caching, polling fallback (planned) |
| **TanStack Query** | 5.x | Alternative for complex server state (evaluated) |
| **React useState/useEffect** | Native | Local component state |
| **React Context** | Native | Global state (auth, theme) |
| **localStorage** | Native | Idempotency key persistence |

**Transport Layer (Custom):**
- `HttpTransport` — Production gateway communication
- `MockTransport` — Dev/preview without infra
- `RouteHandlerTransport` — Client → BFF (`/bff/*`)
- `Transport` interface — Unified send() contract

---

## Real-time Communication

| Technology | Purpose |
|------------|---------|
| **EventSource (SSE)** | Job progress events (`/api/content-jobs/{jobId}/events`) |
| **Last-Event-ID** | Resume missed events on reconnect |
| **EventSource Polyfill** | Not needed (native browser support) |

---

## Testing

| Tool | Version | Purpose |
|------|---------|---------|
| **Vitest** | 2.x | Unit & integration tests (fast, Vite-native) |
| **React Testing Library** | 15.x | Component testing (user-centric) |
| **Playwright** | 1.4x | E2E tests (Chromium, Firefox, WebKit) |
| **MSW (Mock Service Worker)** | 2.x | API mocking for tests/dev |
| **@testing-library/jest-dom** | 6.x | Custom matchers |
| **axe-core** | 4.x | Accessibility testing |

**Coverage Targets (Feature Scope):**
- Line coverage: ≥80% (new code)
- Branch coverage: ≥70% (new code)
- Function coverage: ≥80% (new code)

---

## Linting & Formatting

| Tool | Version | Config |
|------|---------|--------|
| **ESLint** | 9.x (flat config) | `eslint.config.mjs` |
| **Prettier** | 3.x | `.prettierrc` |
| **TypeScript ESLint** | 8.x | Type-aware linting |
| **React Hooks ESLint** | 5.x | Rules of hooks |

**Key Rules:**
- `@typescript-eslint/no-explicit-any` — error
- `react-hooks/exhaustive-deps` — error
- `jsx-a11y/*` — warn (accessibility)
- `no-console` — warn (allow in dev)

---

## TypeScript Configuration

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./*"],
      "@/components/*": ["./components/*"],
      "@/lib/*": ["./lib/*"],
      "@/types/*": ["./types/*"]
    }
  }
}
```

**Strict Mode:** Enabled — no `any`, no implicit any, strict null checks, strict function types.

---

## Package Manager & Scripts

**pnpm** — Fast, disk-efficient, strict peer dependencies.

**Key Scripts (`package.json`):**
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

---

## Development Environment

| Tool | Version | Notes |
|------|---------|-------|
| **VS Code** | Latest | Recommended IDE |
| **ESLint Extension** | — | Auto-fix on save |
| **Prettier Extension** | — | Format on save |
| **Tailwind CSS IntelliSense** | — | Class completion |
| **Playwright Test for VS Code** | — | E2E debugging |

---

## CI/CD Pipeline (GitHub Actions)

| Stage | Command | Gate |
|-------|---------|------|
| Install | `pnpm install --frozen-lockfile` | — |
| Lint | `pnpm lint` | Must pass |
| Typecheck | `pnpm typecheck` | Must pass |
| Unit Tests | `pnpm test:coverage` | ≥80% new code |
| E2E Tests | `pnpm test:e2e` | Must pass |
| Build | `pnpm build` | Must pass |

---

## Deployment

| Environment | Platform | Config |
|-------------|----------|--------|
| **Preview** | Vercel / Preview Deploy | Auto on PR |
| **Staging** | Container (Docker) | `output: 'standalone'` |
| **Production** | Container (Docker) | `output: 'standalone'` |

**Dockerfile:** Multi-stage build, copies `public`, `.next/standalone`, `node_modules` from build stage.

---

## Browser Support

| Browser | Version | Notes |
|---------|---------|-------|
| Chrome | 120+ | Full support |
| Firefox | 121+ | Full support |
| Safari | 17+ | Full support (EventSource native) |
| Edge | 120+ | Full support |

**Polyfills:** None required for target browsers. EventSource is native.

---

## Performance Budgets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **FCP** | < 1.8s | Lighthouse |
| **LCP** | < 2.5s | Lighthouse |
| **CLS** | < 0.1 | Lighthouse |
| **TBT** | < 200ms | Lighthouse |
| **JS Bundle (gz)** | < 150KB | webpack-bundle-analyzer |
| **CSS Bundle (gz)** | < 30KB | — |

---

## Security Headers (Middleware)

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | Nonce-based, strict | XSS prevention |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS enforcement |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing prevention |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer control |
| `X-Frame-Options` | `SAMEORIGIN` | Clickjacking prevention |

**CSP Nonce:** Per-request `crypto.randomUUID()` in Edge middleware.

---

## Environment Variables

| Variable | Required | Environments | Description |
|----------|----------|--------------|-------------|
| `DOCSURI_GATEWAY_URL` | Yes (prod) | Prod, Staging | Backend gateway base URL |
| `DOCSURI_BFF_ALLOW_MOCK` | No | Prod (optional) | Allow MockTransport in prod |
| `NEXT_PUBLIC_*` | As needed | All | Client-exposed config |

---

## Version Compatibility Matrix

| Package | Version Constraint | Rationale |
|---------|-------------------|-----------|
| `next` | `^15.0.0` | App Router, standalone output |
| `react` | `^18.2.0` | Concurrent features, Suspense |
| `react-dom` | `^18.2.0` | — |
| `typescript` | `^5.4.0` | Strict mode, satisfies |
| `vitest` | `^2.0.0` | Vite-native, fast |
| `playwright` | `^1.44.0` | Cross-browser E2E |
| `eslint` | `^9.0.0` | Flat config |
| `prettier` | `^3.2.0` | Consistent formatting |
| `tailwindcss` | `^3.4.0` | Utility-first CSS |
| `swr` | `^2.2.0` | Stale-while-revalidate |

---

## Dependency Philosophy

1. **Minimize runtime dependencies** — Prefer native Web APIs (EventSource, crypto.subtle, fetch)
2. **Custom transport layer** — No Axios, no TanStack Query (yet), custom Transport interface
3. **Type-safe contracts** — Shared types from `shared/` or generated from OpenAPI
4. **Dev/Prod parity** — MockTransport for dev, HttpTransport for prod, same interface