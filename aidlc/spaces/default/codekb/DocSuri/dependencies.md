# Dependencies — DocSuri Frontend

**Project:** DocSuri
**Date:** 2026-10-02

---

## Production Dependencies

### Core Framework
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `next` | ^15.0.0 | MIT | React framework (App Router) |
| `react` | ^18.2.0 | MIT | UI library |
| `react-dom` | ^18.2.0 | MIT | DOM renderer |

### Utilities
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `swr` | ^2.2.0 | MIT | Stale-while-revalidate data fetching (polling fallback) |
| `clsx` | ^2.1.0 | MIT | Conditional className utility |
| `tailwind-merge` | ^2.2.0 | MIT | Merge Tailwind classes without conflicts |

### Security & Auth
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `jose` | ^5.2.0 | MIT | JWT/JWE handling (if needed client-side) |
| `crypto-js` | — | — | **NOT USED** — Use native `crypto.subtle` |

### Math & Rendering
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `katex` | ^0.16.0 | MIT | Math formula rendering |
| `rehype-katex` | ^7.0.0 | MIT | Remark/Rehype KaTeX integration |

---

## Development Dependencies

### Testing
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `vitest` | ^2.0.0 | MIT | Unit/integration test runner |
| `@vitest/coverage-v8` | ^2.0.0 | MIT | Code coverage (V8 provider) |
| `@testing-library/react` | ^15.0.0 | MIT | Component testing utilities |
| `@testing-library/jest-dom` | ^6.4.0 | MIT | Custom Jest/Vitest matchers |
| `@testing-library/user-event` | ^14.5.0 | MIT | User interaction simulation |
| `playwright` | ^1.44.0 | Apache-2.0 | E2E browser automation |
| `@playwright/test` | ^1.44.0 | Apache-2.0 | Playwright test runner |
| `msw` | ^2.3.0 | MIT | Mock Service Worker (API mocking) |
| `axe-core` | ^4.9.0 | MPL-2.0 | Accessibility testing |
| `vitest-axe` | ^0.1.0 | MIT | Vitest + axe-core integration |

### Linting & Formatting
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `eslint` | ^9.0.0 | MIT | Linting (flat config) |
| `@eslint/js` | ^9.0.0 | MIT | ESLint core configs |
| `eslint-plugin-react` | ^7.34.0 | MIT | React linting rules |
| `eslint-plugin-react-hooks` | ^4.6.0 | MIT | Hooks linting |
| `eslint-plugin-jsx-a11y` | ^6.8.0 | MIT | Accessibility linting |
| `@typescript-eslint/eslint-plugin` | ^8.0.0 | MIT | TypeScript linting |
| `@typescript-eslint/parser` | ^8.0.0 | MIT | TypeScript parser |
| `eslint-plugin-import` | ^2.29.0 | MIT | Import ordering |
| `eslint-plugin-tailwindcss` | ^0.5.0 | MIT | Tailwind CSS linting |
| `prettier` | ^3.2.0 | MIT | Code formatting |
| `prettier-plugin-tailwindcss` | ^0.5.0 | MIT | Tailwind class sorting |

### TypeScript & Build
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `typescript` | ^5.4.0 | Apache-2.0 | Type checking |
| `@types/react` | ^18.2.0 | MIT | React type definitions |
| `@types/react-dom` | ^18.2.0 | MIT | React DOM type definitions |
| `@types/node` | ^20.12.0 | MIT | Node.js type definitions |

### Development Tools
| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `@next/eslint-plugin-next` | ^15.0.0 | MIT | Next.js specific linting |
| `eslint-config-prettier` | ^9.1.0 | MIT | Disable conflicting ESLint rules |
| `husky` | ^9.0.0 | MIT | Git hooks |
| `lint-staged` | ^15.2.0 | MIT | Run lint on staged files |

---

## Internal / Workspace Dependencies

| Package | Source | Purpose |
|---------|--------|---------|
| `@docsuri/shared` | `../shared` | Shared types, contracts, constants |
| `@docsuri/types` | `../types` | Generated TypeScript types (OpenAPI) |

---

## Dependency Graph (Key Relationships)

```
next (framework)
├── react, react-dom (peer)
├── swr (data fetching)
├── tailwindcss (peer, via postcss)
├── katex (math rendering)
└── eslint, prettier (dev)

vitest (test runner)
├── @testing-library/react (component testing)
├── @vitest/coverage-v8 (coverage)
├── msw (API mocking)
├── playwright (E2E)
└── axe-core (a11y)

eslint (linting)
├── @typescript-eslint/* (TS rules)
├── eslint-plugin-react* (React rules)
├── eslint-plugin-jsx-a11y (a11y rules)
├── eslint-plugin-import (import order)
└── prettier (formatting)

shared (workspace)
├── types (contracts)
└── constants (shared values)
```

---

## License Compliance

| License | Packages | Compliance |
|---------|----------|------------|
| MIT | next, react, swr, vitest, testing-library, playwright, msw, tailwindcss, katex, clsx, tailwind-merge, prettier, husky, lint-staged | ✅ Permissive |
| Apache-2.0 | typescript, playwright, @playwright/test | ✅ Permissive |
| MPL-2.0 | axe-core | ⚠️ Weak copyleft (OK for dev dependency) |
| BSD-3-Clause | jest-dom, user-event | ✅ Permissive |

**No GPL/AGPL dependencies in production bundle.**

---

## Bundle Size Analysis (Target)

| Category | Target (gzipped) | Current Estimate |
|----------|------------------|------------------|
| **Framework** | ~45 KB | Next.js + React |
| **Router/SSR** | ~15 KB | Next.js App Router |
| **Data Fetching** | ~8 KB | SWR |
| **Styling** | ~5 KB | Tailwind (purged) |
| **Math** | ~25 KB | KaTeX (heavy) |
| **Custom Code** | ~40 KB | Components, hooks, API |
| **Total (JS)** | **< 150 KB** | Target |
| **CSS** | < 30 KB | Tailwind + CSS Modules |

---

## Security Scanning

**Tools:**
- `pnpm audit` — Built-in vulnerability scanning
- `pnpm audit --prod` — Production-only scan
- GitHub Dependabot — Automated PR for updates
- Snyk (optional) — Deep scanning

**Policy:**
- No critical/high vulnerabilities in production deps
- Dev dependencies: medium OK if no exploit path
- Update cadence: Monthly for patch, quarterly for minor

---

## Update Strategy

| Category | Cadence | Method |
|----------|---------|--------|
| **Security patches** | Immediate | Dependabot PR → auto-merge if tests pass |
| **Patch versions** | Weekly | Dependabot PR → review |
| **Minor versions** | Monthly | Manual review + test |
| **Major versions** | Quarterly | Spike + full regression |

**Pinned Major Versions (Stability):**
- `next@15` — App Router stability
- `react@18` — Concurrent features
- `typescript@5` — Strict mode maturity
- `vitest@2` — Vite 5 compatibility
- `playwright@1.44` — Browser engine stability

---

## Forbidden Patterns

| Pattern | Reason | Enforcement |
|---------|--------|-------------|
| `axios` | Use native fetch + custom Transport | ESLint `no-restricted-imports` |
| `tanstack-query` | Use SWR (lighter) | ESLint `no-restricted-imports` |
| `lodash` | Use native JS | ESLint `no-restricted-imports` |
| `moment.js` | Use native Date/Intl | ESLint `no-restricted-imports` |
| `classnames` | Use `clsx` (lighter) | ESLint `no-restricted-imports` |
| `styled-components` | Use CSS Modules + Tailwind | ESLint `no-restricted-imports` |
| `@emotion/*` | Use CSS Modules + Tailwind | ESLint `no-restricted-imports` |

---

## Peer Dependency Requirements

| Package | Required Peer | Version |
|---------|---------------|---------|
| `next` | `react` | ^18.2.0 |
| `next` | `react-dom` | ^18.2.0 |
| `swr` | `react` | ^18.2.0 |
| `@testing-library/react` | `react` | ^18.2.0 |
| `@testing-library/react` | `react-dom` | ^18.2.0 |
| `eslint-plugin-react` | `eslint` | ^9.0.0 |
| `@typescript-eslint/eslint-plugin` | `eslint` | ^9.0.0 |
| `prettier-plugin-tailwindcss` | `prettier` | ^3.0.0 |
| `tailwindcss` | `postcss` | ^8.4.0 |

---

## Lockfile Integrity

- **File:** `pnpm-lock.yaml`
- **Strategy:** Committed to git, `--frozen-lockfile` in CI
- **Verification:** `pnpm install --frozen-lockfile` must pass in CI
- **Updates:** `pnpm update --interactive` for controlled upgrades