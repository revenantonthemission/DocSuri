# U1 Tech-Stack and Verification Decisions

## Sources and Current Evidence

Affirmed team/project rules and approved contracts fix the approach. Current read-only manifest evidence comes from `frontend/package.json`, `backend/pyproject.toml` and `backend/modules/summarization/pyproject.toml`, inspected on 2026-10-05. `aidlc/spaces/default/codekb/DocSuri/technology-stack.md` is historical inventory, not an installation/readiness receipt. No dependency installation, application build or environment verification occurred in this stage.

The current confirmed Q3 amendment consumes `../functional-design/functional-spec.md`, `../functional-design/rules.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/contract-design/contract-summary.md` and that historical technology-stack input. Recovery/readiness follows `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`; source declarations below are not current deployment or qualification claims.

## Decisions

| Area | Decision | Evidence / implementation obligation |
|---|---|---|
| Frontend | Existing Next.js/React application with strict TypeScript | Manifest pins Next.js 15.5.26, React 19.0.0 and TypeScript 5.7.3; no framework replacement |
| Job transport | Native fetch through custom Transport and same-origin BFF; native EventSource; SWR fixed two-second fallback | Current manifest declares SWR 2.5.1. Correct native streaming/fallback/current-context wiring, frozen installed closure and actual staging behavior still require implementation/qualification; a declaration is not a pass |
| Client identity | Native crypto.subtle SHA-256 and allowlisted localStorage recovery record | Existing browser APIs; no random fallback or crypto dependency substitution |
| Presentation | CSS Modules/Tailwind and clsx/tailwind-merge per affirmed rules, existing semantic light/dark tokens | Manifest declares clsx 2.1.1, tailwind-merge 3.7.0, Tailwind 4.3.3 and matching PostCSS package. Actual configuration/source compatibility, installed closure and rendered accessibility remain verification obligations |
| Client diagnostics | Sentry with scrubbed safe events | Manifest declares @sentry/nextjs 11.4.0. This does not establish configured project, safe event wiring or live delivery; qualify integration/scrubbing and the actual notification path |
| Backend | Existing Python module and FastAPI boundary; existing generation pipeline | Parent backend requires Python >=3.13; standalone summarization declares >=3.11 and Pydantic >=2.7,<3. Parent declares FastAPI >=0.110; module also has its optional API extra. Distinguish those source constraints from actual frozen/deployed interpreter/package versions |
| Job/result authority | Existing relational job store with separate immutable final prepared-result record | Human-selected placement. Existing real adapters declare psycopg and queue/storage SDK extras; actual availability and migrations remain verification obligations |
| Queue and generation | Existing runtimes/queue with C6/C7 authority and compatibility rules | No new cloud platform or replacement pipeline; real dispatch and old-runtime isolation must be proved |
| Testing | Existing frontend Vitest/Testing Library/Playwright and backend pytest/Hypothesis/Ruff where applicable | Frontend declares Vitest 3.2.6 with matching coverage-v8, Testing Library 16.1.0 and Playwright 1.55.1. Parent/module pin pytest-cov 7.0.0 and coverage 7.10.7; other dev ranges are source constraints, not installed-version evidence |

Forbidden alternatives remain forbidden: axios, TanStack Query, lodash, moment/date-fns substitutions, classnames, and styled-components/emotion. A historical evaluated alternative does not override current project rules. Exact new dependency versions are selected and checked in the approved implementation plan/lockfile, not invented from old analysis.

## Detailed Verification Requirement

| ID | Requirement / pass-fail condition | Source |
|---|---|---|
| NFR11.1 | Implement each applicable component then author/run its meaningful tests under the affirmed test-after ordering. New-code line coverage is at least 80%; current existing suites, lint, strict typechecking and relevant integration/E2E checks pass before merge. Record actual commands/results and prerequisites; skipped live-dependency tests do not prove the real skeleton. | NFR11, team/project practices, Delivery Planning |

The current frontend scripts declare `lint: eslint .`, scoped `lint:u1`, full `typecheck` and `typecheck:u1`, full/U1 coverage commands, `e2e` and `e2e:u1`, plus existing build/contract/generated-type checks. These source declarations supersede the earlier missing-script/next-lint observation. Qualify the actual commands and complete source-bound frontend/backend/controller/assembly/helper/shell/SQL coverage evidence under current Code Generation authority; the stricter imported U1 graph, residual dependency and image/runtime/control/notification gaps remain open in the preserved handoff. Historical optional integration skips cannot satisfy required U1 real-store/realm or integrated evidence; missing/wrong prerequisites fail the required runner.

## Execution Prerequisites and Current Upstream Evidence

NFR Design must supply numerical worker/queue/reconciliation budgets, cleanup schedule/alert margin and repeatable resource/volume fixtures. Infrastructure/deployment work verifies real configured services, compatible rollout/rollback and data/backup protection before live actions. The exact integrated verification command remains explicitly deferred and requires its own human authorization before the U1 checkpoint.

Current Functional Design review `../functional-design/reviews/review-03.md` independently resolves all five carried findings, including R-05's draft optionality, and reports no new architectural finding. Use the actual current model/workflows rather than the earlier unresolved carry-forward note; this does not certify the partial application or real integrated skeleton.

Contract Design R-03 remains Accepted risk: the original schema-check dependency set lacks an active date-time checker. Its payload-shape passes are not timestamp/TTL proof. Require the separate actual application/store validation and expiry evidence under NFR11.2/NFR11.5; the NFR document update does not alter that owning contract disposition.

The public PostgreSQL bootstrap handoff is preparation only. Concrete admitted image/runtime/launcher/resource identities, independent measured isolation/protected realm proof, bounded role/marker preflight and operational authorization precede mutation. Preserve separate authority/minimal-purge databases, the original immutable source baseline, narrowly guarded migration admission and the current implementation-plan/source-footprint approval boundary. A frozen development install or declared SDK is not artifact/runtime/control/CI/staging qualification.

## Document-Level Verification

Executed read-only document checks on 2026-10-05 retain 35 detailed IDs and all 12 inception-NFR rows, with valid targets, no unmapped detail and the same two justified asset exclusions. Traceability bytes remain identical to the archived original. Of the existing requirement conditions, 32 are byte-identical; only NFR1.4/NFR1.5/NFR11.2 add the confirmed C2 validation/exactness precision. The existing latency, cleanup, competing-actor and coverage targets are preserved. Each of the six Markdown deliverables cites all five declared inputs; 52 explicit file references resolve. Manifest/script presence and distinct parent/module Python source constraints were checked against the actual files. Traceability, explicit five-input coverage and required-section checks passed with zero findings. The seven archive copies were compared byte-identical before revision. These checks establish document/source consistency, not installed/deployed dependencies, passing application tests, real-store or operational acceptance.
