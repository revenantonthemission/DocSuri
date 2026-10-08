# U1 Tech-Stack and Verification Decisions

## Sources and Current Evidence

Affirmed team/project rules and approved contracts fix the approach. Current manifest evidence comes from `frontend/package.json` and `backend/modules/summarization/pyproject.toml`. `aidlc/spaces/default/codekb/DocSuri/technology-stack.md` is historical inventory, not an installation/readiness receipt. No dependency installation, application build or environment verification occurred in this stage.

## Decisions

| Area | Decision | Evidence / implementation obligation |
|---|---|---|
| Frontend | Existing Next.js/React application with strict TypeScript | Manifest pins Next.js 15.5.26, React 19.0.0 and TypeScript 5.7.3; no framework replacement |
| Job transport | Native fetch through custom Transport and same-origin BFF; native EventSource; SWR fixed two-second fallback | Mandated and contracted. Current manifest does not declare SWR; integration/install/version verification belongs to approved Code Generation, not a false installed-state claim |
| Client identity | Native crypto.subtle SHA-256 and allowlisted localStorage recovery record | Existing browser APIs; no random fallback or crypto dependency substitution |
| Presentation | CSS Modules/Tailwind and clsx/tailwind-merge per affirmed rules, existing semantic light/dark tokens | Verify actual source/config/dependencies during implementation; absence from this manifest is not permission to replace the mandated approach or claim packages present |
| Client diagnostics | Sentry with scrubbed safe events | Mandatory planned integration; manifest does not establish installed SDK or configured project. Confirm config/readiness and approved implementation wiring |
| Backend | Existing Python module and FastAPI boundary; existing generation pipeline | Module requires Python >=3.11, Pydantic >=2.7,<3; FastAPI >=0.110 is an optional API extra. Do not assert deployed versions from range declarations |
| Job/result authority | Existing relational job store with separate immutable final prepared-result record | Human-selected placement. Existing real adapters declare psycopg and queue/storage SDK extras; actual availability and migrations remain verification obligations |
| Queue and generation | Existing runtimes/queue with C6/C7 authority and compatibility rules | No new cloud platform or replacement pipeline; real dispatch and old-runtime isolation must be proved |
| Testing | Existing frontend Vitest/Testing Library/Playwright and backend pytest/Hypothesis/Ruff where applicable | Manifest frontend Vitest 3.2.6, Testing Library 16.1.0, Playwright 1.55.1; module dev dependencies are ranges, not installed versions |

Forbidden alternatives remain forbidden: axios, TanStack Query, lodash, moment/date-fns substitutions, classnames, and styled-components/emotion. A historical evaluated alternative does not override current project rules. Exact new dependency versions are selected and checked in the approved implementation plan/lockfile, not invented from old analysis.

## Detailed Verification Requirement

| ID | Requirement / pass-fail condition | Source |
|---|---|---|
| NFR11.1 | Implement each applicable component then author/run its meaningful tests under the affirmed test-after ordering. New-code line coverage is at least 80%; current existing suites, lint, strict typechecking and relevant integration/E2E checks pass before merge. Record actual commands/results and prerequisites; skipped live-dependency tests do not prove the real skeleton. | NFR11, team/project practices, Delivery Planning |

The current package declares `lint: next lint`, test/test:contracts/e2e/build and generated-type checks, but no test:coverage or typecheck script. Reconcile actual runnable tooling under Code Generation rather than report historical script names as working. Module integration tests may skip when live extras/dependencies are absent; those skips must be recorded and cannot satisfy required real-store or integrated evidence.

## Deferred Execution Parameters and Upstream Finding

NFR Design must supply numerical worker/queue/reconciliation budgets, cleanup schedule/alert margin and repeatable resource/volume fixtures. Infrastructure/deployment work verifies real configured services, compatible rollout/rollback and data/backup protection before live actions. The exact integrated verification command remains explicitly deferred and requires its own human authorization before the U1 checkpoint.

Functional Design's Minor R-05 remains an upstream ER optionality concern for the initial SubmissionDraft. The authoritative input/workflow permits an unprepared draft; this stage does not rewrite that reviewed artifact or claim the finding resolved. Carry its recorded disposition to the U1 human checkpoint.
