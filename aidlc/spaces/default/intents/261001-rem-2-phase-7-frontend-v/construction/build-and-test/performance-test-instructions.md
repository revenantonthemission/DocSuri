# Performance Test Instructions — Build and Test

No measured performance result is claimed by this stage. What exists and is verified is the deterministic measurement plumbing; what remains is a real-browser benchmark run under the separately authorized real environment.

## Verified now (deterministic evidence)

- Bounded measurement points in the job surface, exercised by the unit suites:
  - stream mount-to-open `latencyMs` and status mount-to-first-commit `latencyMs` (`frontend/lib/jobDiagnostics.ts`; bounded 0–600000 ms, invalid values dropped — tests in `frontend/test/u2JobDiagnostics.test.tsx` and `u1JobDiagnostics.test.ts`).
  - asset decoded-readiness `readinessMs` (`asset` diagnostic kind; tests in `frontend/test/u3ViewerMinimap.test.tsx`).
- Fixed fallback cadence: 2 s SWR polling (tested), 10 s asset gateway timeout constant asserted in the BFF branch tests.

## How to run a real performance pass (deferred; requires the authorized environment)

```bash
cd frontend
npm run build && npm run start
# Real-origin E2E/perf against a reachable gateway:
npx playwright test                       # existing Playwright suites (u1 config: playwright.u1.config.ts)
# Optional Lighthouse pass on the built app for the reading surfaces
npx lighthouse http://localhost:3000/paper/<id> --only-categories=performance
```

- Treat any number from that run as environment-specific; record it with the environment, revision and workload alongside the unit summaries' measurement points.
- Performance budgets are design parameters (documented in the unit records), not asserted budgets; nothing in this stage weakens the ≥80% coverage floor or the quality gates.
