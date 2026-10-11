# DocSuri Code Structure

## Repository layout and classification

The application is a monorepo. Current tracked counts below are **files**, not functions, test cases, authored-source totals or passing checks. They include manifests, tests, lockfiles and generated contract bindings. Counts came from `git ls-files` on the scan checkout.

| Area | Tracked files | Primary roles |
|---|---:|---|
| backend/ | 392 | application shell, middleware, domain modules, repositories/adapters, migrations, tests, packaging |
| frontend/ | 307 | Next routes, React UI, browser/BFF contracts, state/hooks, tests, styles/assets, packaging |
| ingestion/ | 81 | corpus application/domain/adapters, worker/CLI, SQL control plane, tests |
| ops/ | 108 | reliability application, deployment/CDK/local/server tooling, tests |
| platform_integrity/ | 117 | authority/evidence domain, adapters, restricted API/CLI, migrations, tests |
| shared/ | 107 | schemas, vector spec, ports, authored Python utilities and generated bindings, contract tooling/tests |
| tests/ | 35 | account/library tests, load-test script and lint configuration |
| .github/ | 6 | four workflows, CODEOWNERS and PR template |

Root application/config context includes `CONVENTIONS.md`, `pytest.ini`, `.gitignore` and `.dockerignore`. Root agent/MCP/lifecycle settings and AI-DLC contribution blocks are tooling context, excluded from the application inventory. There is no claim that every tracked file was deeply reviewed; the dated coverage file is authoritative.

### Exhaustive classification rule at inventory depth

Within the inventoried application roots, classify `tests/`, `test/`, `e2e/` and `test_*`/`*.test.*` as tests/fixtures; `migrations/` as schema/control changes; manifests/lockfiles/Docker/compose/workflow/settings files as build/configuration; README/runbooks as documentation; frontend `app/` as routes/layouts, `components/` as presentation, `lib/` as orchestration/state/API utilities, and `types/` as contracts. Python `domain/` and models/schemas files hold domain/data contracts; controller/api files are HTTP boundaries; service/application files orchestrate; repository/adapters/integrations implement persistence/external ports; worker/CLI files are execution entrypoints. Remaining assets/styles are presentation resources and package initializers are packaging glue. Generated contract output is recognized but excluded from manual source analysis.

## Package boundaries and entrypoints

| Package or area | Entry / main composition | Layout and pattern |
|---|---|---|
| Backend shell | `backend/app.py`, `backend/wiring.py` | imports independent module routers; owns configuration, middleware, authorities and persistence overrides |
| Accounts/library/mypage | module `controller.py`, services/repository trees | FastAPI DI plus domain errors; SQL and memory seams |
| Discovery | `backend/modules/discovery/src/discovery/` | standalone Python package: api, service, domain, adapters; real and mock composition |
| Summarization | `backend/modules/summarization/src/summarization/` | standalone package: API, job/domain/protocol/result models, services, real adapters and worker |
| Citation/personalization/onboarding/trends/plans | sibling backend modules | controller/service/repository models; citation implementation concentrates provider/cache/controller logic in one file |
| Evidence/research | `backend/modules/evidence/`; research under `sessions/` | grounded orchestration, attachment tools, streaming, repository and worker |
| Novelty | `backend/modules/novelty/` | controller/service/repository, large provider adapter and worker implementations |
| Private documents | `backend/modules/user_docmodel/coordinator.py` | shared owner-bound upload/build/read coordinator |
| Frontend | `frontend/app/`, `components/`, `lib/` | server routes plus client islands; BFF catchall mediates backend transport; explicit job state/contracts |
| Ingestion | `ingestion/src/docsuri_ingestion/` | ports, domain, application, adapters, resilience, CLI and worker |
| Ops | `ops/src/docsuri_ops/` | telemetry/cost/grounding/incident/evaluation services and CLI; deployment material is outside package src |
| Platform integrity | `platform_integrity/src/docsuri_platform_integrity/` | contracts/domain/application/adapters/api/cli/deployment; standalone controlled operational subsystem |
| Shared | `shared/python/src/docsuri_shared/`, JSON schema groups | authored ports/authz/identity/vector utilities plus generated bindings |

## Frontend navigation surface

The route inventory covers home/search, paper detail and document model/translation, agent workspace, library/saved/history, mypage/account library/recent/settings/subscription, login/signup/reset-password/verify-email/social-link-required, unsubscribe, privacy and terms. Error/global-error routes provide fallback rendering. BFF lives at `app/bff/[...path]/route.ts`.

Route existence is distinct from feature availability. UI component internals and browser persistence beyond the inspected job client were shallowly inventoried, not a full accessibility or interaction audit.

## Code patterns worth preserving

- Typed request/domain models and explicit result unions; ports separate algorithms from external stores/providers.
- FastAPI dependency overrides connect module-local defaults to app-level configuration.
- BFF normalizes transport, selected retries, cookies, SSE and binary assets.
- Content jobs use owner-scoped idempotency, ordered events and terminal state rules; frontend applies sequence watermarks.
- Generated schema consumers have drift/inventory tooling, while private document identity has shared helpers.

## Repairability concentrations

Measured file lengths identify navigation/ownership hotspots, not cyclomatic complexity: `backend/wiring.py` 1,037 lines, `backend/modules/accounts/controller.py` 1,180, `backend/modules/novelty/adapters.py` 1,818, `ingestion/src/docsuri_ingestion/application.py` 1,167, `frontend/lib/api/apiClient.ts` 1,494 and `frontend/components/agent/AgentChatScreen.tsx` 1,146. Adapter/UI internals in this list remain shallow coverage. Prefer responsibility-based extraction after behavior is captured; size alone does not authorize deletion or prove dead code.

## Coverage exclusions

AI-DLC installations/workspace/generated agents and `.aidlc-rule-details/` are not product modules. Dependency environments, node_modules, caches, .next/build output, generated DTO implementation bodies, secrets/environment values and user databases were not inspected. SQL parsing gaps and graph limitations are recorded in [coverage](reverse-engineering-timestamp.md). Historical docs were not used to claim current runtime health.
