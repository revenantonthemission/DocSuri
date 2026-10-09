# Build and Test — Test Results

Executed against commit `156fb206` on 2026-10-09. Every figure below is from an executed command on the frozen bytes; nothing is projected.

| Check | Command | Result |
|---|---|---|
| Production build | `npm run build` (frontend) | **Pass** — Next.js standalone build; shared first-load JS 103 kB; all routes compiled |
| Combined suite | `vitest run` | **86 files / 494 tests green** |
| u1 lane | `vitest run --config vitest.u1.config.ts` | **23 files / 104 tests green** |
| u2 lane | `vitest run --config vitest.u2.config.ts` | **31 files / 144 tests green** |
| u3 lane | `vitest run --config vitest.u3.config.ts` | **13 files / 73 tests green** |
| u2 coverage | `vitest run --config vitest.u2.config.ts --coverage` | **85.58% lines** (threshold 80) |
| u3 coverage | `vitest run --config vitest.u3.config.ts --coverage` | **87.16% lines** (threshold 80) |
| Executor integration | `cd ops && .venv/bin/python -m pytest tests/test_u1_colima_executor.py -q` | **12 passed** |
| Sandbox integration | `node --test scripts/u1-sandbox.test.mjs` | **7 passed** |
| Repository typecheck | `npm run typecheck` | **exit 0** |
| Unit-scoped lint | `npm run lint:u1`, `lint:u2`, `lint:u3` | **clean (exit 0)** |
| Repo-wide lint | `npm run lint` | 4 pre-existing errors (generated `next-env.d.ts`, generated `types/wire/dtos.ts`, e2e specs outside tsconfig projects) + 11 pre-existing warnings; **none on unit-authored lines** |
| Strict-type graph (u3) | `tsc --project tsconfig.u3.json --noEmit` | 81 pre-existing errors; **none on unit-authored lines** |
| Stability (u3 gate) | `vitest run --config vitest.u3.config.ts --coverage` ×26 (18 standalone / 8 concurrent full-suite load) | **26/26 green** after the in-test retry fix (reviewed in u3 review-04) |

Failures observed and dispositioned: none open. The only failure class observed during the stage window was the u3 coverage-gate flake, repaired and stability-proven (26/26) before the stage; it is recorded in `construction/u3-secure-assets/code-generation/reviews/review-04.md`.

Deferred (not claimed): real-origin E2E, Lighthouse/benchmark numbers, real gateway/backend and deployment execution.
