# Build Instructions — DocSuri Frontend (Build and Test)

Verified against commit `156fb206` on 2026-10-09. This stage performs no source changes; the build below was executed as recorded.

## Prerequisites

- Node.js 20+ and npm (repo uses npm scripts; lockfile committed).
- Dependencies: `npm ci` (or `npm install`) in `frontend/`.
- No secrets are required at build time. Runtime configuration is read from environment (`DOCSURI_GATEWAY_URL`, optional `DOCSURI_BFF_ALLOW_MOCK` for dev mock mode, Sentry variables) and is not embedded by the build.

## Build

```bash
cd frontend
npm run build
```

- Next.js (`output: 'standalone'`) production build; the route table and the standalone server bundle are emitted under `.next/`.
- **Verified result (2026-10-09):** build succeeded; shared first-load JS 103 kB; all application routes compiled (paper/[id], doc-model, translate, mypage/*, library/*, auth routes, `/bff/[...path]` proxy and `/unsubscribe`).

## Run (for smoke checks)

```bash
cd frontend
npm run start        # serves the production build locally
```

No deployment, container build or environment provisioning is performed or claimed by this stage; those remain separate operational steps with their own authorizations.
