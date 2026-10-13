# U1 isolated bootstrap evidence

Captured 2026-10-11 during Code Generation Step 2. This proves a framework/build transport slice, not the paper journey or operating feasibility.

## Configuration and resource boundary

The wrapper `scripts/verify_docsuri_u1.py` creates only its manifest-owned PostgreSQL container and persistent volume, using cached digest `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`. Listeners bind loopback. PostgreSQL has 512 MiB memory, 0.5 CPU, 64 PIDs, 12 connections, 32 MiB shared buffers, 2 MiB work memory, 5s statement timeout and 2s lock timeout. The private manifest and migration credential record are separate; runtime profile loading rejects embedded administrator credentials. Owner migrations are not yet installed.

Setup reserves an 8 GiB host floor, 2 GiB incremental dependency/build allowance, 1 GiB runtime and 1 GiB recovery allowance. Initial free capacity was about 12.82 GiB; locked environment reconciliation left about 12.63 GiB. A later sample after generated bindings and build was 13,434,880,000 bytes free. These are samples, not proof of sustained bounded load. Existing dependency directories were approximately 202 MiB backend, 685 MiB frontend and 63 MiB shared; no model download or shared cache removal occurred.

Actual runtime bindings: Python 3.13.7, FastAPI 0.141.1 (MIT), Starlette 1.7.0 (BSD-3-Clause), Uvicorn 0.53.0 (BSD-3-Clause), Pydantic 2.13.5 (MIT), psycopg 3.3.6 and psycopg-pool 3.3.3 (LGPL-3.0-only), email-validator 2.3.0 (Unlicense). License identifiers are read from installed distribution metadata; distribution obligations still apply to later packaging. Node 24.14.0, corepack-pinned pnpm 9.15.9, React 19.0.0 and Vite 6.4.3 use the existing frontend lock. No newer framework was selected from an unconstrained install.

## Commands and results

From the repository root unless otherwise stated:

- `uv --no-cache sync --project backend --locked --group dev` and the equivalent shared/python invocation succeeded. After the explicit shared email-extra amendment, both project locks were regenerated and synchronized. Generated email validation is retained.
- `shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py` exported the amended canonical schemas into the existing shared catalogue. Browser and trusted execution definitions are separated; trusted execution context is excluded from the browser roots.
- `uv --no-cache run --project shared/python --locked --no-sync python shared/python/tools/generate.py` generated 16 schema bindings successfully. `corepack pnpm@9.15.9 exec node scripts/gen-types.mjs` in frontend generated consumer types. Generated files are not hand-edited.
- `corepack pnpm@9.15.9 exec vite build` in frontend succeeded: 28 modules, 383ms, HTML 0.41kB, CSS 2.27kB and JavaScript 186.57kB plus 868.54kB source map. This is a static mount skeleton, not completed UX.
- `python3 scripts/verify_docsuri_u1.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json` succeeded. Repeated setup verifies exact ownership; authored lock amendments retain prior lock hashes in configuration history and require fresh verification.
- `python3 scripts/verify_docsuri_u1.py --phase runner-readiness --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json` succeeded for imports/locks/owned resource checks and explicitly reported unauthored suites and no behavioral readiness.
- `python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json` collected and passed 8 tests in 0.61s. Actual loopback HTTP exercised static Korean deep links, liveness versus unavailable readiness, Host/origin denial with a positive control, a test-only cookie round trip and byte-exact SSE framing. The test-only transport route grants no identity or job authority and is absent from the product assembly.

## Evidence integrity and remaining work

Private phase reports bind HEAD plus actual tracked/new source/configuration bytes, collection and execution commands, outcomes and timestamps. Phase execution rejects empty collections, required skips, missing outcome reports, child errors and changing source bytes. A follow-up component run collected and passed 17 tests in 0.43s, including injected empty/error collection, all-skipped/partially skipped results, changing source, absent coverage inventory, environment credential filtering and low-disk denial. Frontend/browser structured outcome accounting is implemented but awaits its actual suites; no claim is made that it has executed. The explicit coverage inventory remains unfinished and the coverage phase currently refuses execution. No missing suite is counted as a pass.

Installed frontend package metadata confirms React/React DOM 19.0.0, Vite 6.4.3 and Vitest 3.2.6 under MIT, and Playwright 1.55.1 under Apache-2.0. The canonical schema export `--check` passed after generation. Later contract tests still need round-trip/consumer verification.

The local host never calls the ambient legacy assembly. Its readiness remains HTTP 503 with eight missing owner capabilities. Current tests do not prove database grants, authenticated sessions, job recovery, source permission, model quality, complete UX, coverage targets, license-complete packaging or public deployment. Those required checks remain assigned to subsequent plan steps. No completion command has been approved.
