## Developer Code Scan Results

### Scan Coverage

This is a full rescan replacing all prior nine analyses at Standard depth, with repository-wide breadth and **partial deep coverage**. It is not a deep read of every authored file. All application roots were inventoried; exact source files, narrowed graph queries/traces, HTTP AST extraction, manifest/CI inspection and focused test reading support the claims.

**Analyzed deeply** (57 paths; 56 files plus BFF directory containing only the already-read route):
- `CONVENTIONS.md`
- `backend/app.py`
- `backend/wiring.py`
- `backend/health.py`
- `backend/middleware/auth.py`
- `backend/middleware/wiring.py`
- `backend/modules/library/controller.py`
- `backend/modules/citation_graph/controller.py`
- `backend/modules/onboarding/controller.py`
- `backend/modules/plans/controller.py`
- `backend/modules/personalization/controller.py`
- `backend/modules/user_docmodel/coordinator.py`
- `backend/modules/summarization/src/summarization/api/router.py`
- `backend/modules/summarization/src/summarization/service/job_service.py`
- `backend/modules/summarization/src/summarization/domain/job.py`
- `backend/modules/summarization/src/summarization/real_wiring.py`
- `backend/modules/summarization/src/summarization/adapters/content_job_queue.py`
- `backend/modules/summarization/tests/test_content_job_api.py`
- `backend/modules/summarization/tests/conftest.py`
- `frontend/app/bff/`
- `frontend/lib/api/contentJobApi.ts`
- `frontend/lib/api/contentJobContracts.ts`
- `frontend/lib/jobState.ts`
- `frontend/test/u1ContentJobApi.test.ts`
- `frontend/test/u1JobContracts.test.ts`
- `frontend/test/u1PaperJobJourney.test.tsx`
- `platform_integrity/src/docsuri_platform_integrity/api/app.py`
- `platform_integrity/src/docsuri_platform_integrity/application/evidence.py`
- `platform_integrity/src/docsuri_platform_integrity/domain/compatibility.py`
- `backend/pyproject.toml`
- `backend/modules/discovery/pyproject.toml`
- `backend/modules/summarization/pyproject.toml`
- `ingestion/pyproject.toml`
- `ops/pyproject.toml`
- `platform_integrity/pyproject.toml`
- `shared/python/pyproject.toml`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vitest.config.ts`
- `frontend/playwright.config.ts`
- `frontend/next.config.mjs`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/branch-name-check.yml`
- `.github/CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `backend/docker-compose.yml`
- `ops/local-stack/colima-stack.compose.yaml`
- `ops/server/README.md`
- `shared/README.md`
- `ingestion/README.md`
- `ops/README.md`
- `pytest.ini`
- `backend/modules/discovery/src/discovery/api/router.py`
- `backend/modules/trends/controller.py`
- `backend/modules/mypage/controller.py`

**Skimmed only** (except deep paths above):
- `backend/`
- `frontend/`
- `ingestion/`
- `ops/`
- `platform_integrity/`
- `shared/`
- `tests/`
- In these roots, remaining controllers/services/provider adapters, migrations/stored procedures, operational scripts/CDK, UI internals and tests received file/module/route or selected-snippet inspection. Central ingestion index flow, discovery orchestration, evidence orchestration and novelty lifecycle/export were read in selected ranges, not promoted to whole-file deep coverage.

**Left out**:
- AI-DLC installs/workspace/generated contributions: aidlc/, .codex/, .claude/, .kiro/, .cursor/, .opencode/, .aidlc/, .aidlc-rule-details/, generated .agents/.github entries and marked root blocks.
- Dependency environments, node_modules, caches and generated build outputs including .next.
- Generated Python binding and TypeScript DTO implementation bodies.
- Environment/secret values, databases/user objects, external archives/disks and live service state.

Graph evidence: target Users-revenantonthemission-Projects-DocSuri, Tier 2. Initial generation 2026-10-10T23:42:10Z; final source/coverage verification at 2026-10-11T00:31:52Z with matching complete metadata. Scope queries have no outstanding pages. Exact cited paths show metadata_match/no_recorded_issue except directly-read CODEOWNERS freshness not_tracked. No recorded issue is not completeness proof. Timestamp lists all parse-partial files/ranges and exclusions. Dynamic route/wiring claims use source because graph Route inventory was insufficient; false heuristic cross-language edges were not accepted.

### Packages Found

- Backend modular app — Python — fourteen mount groups covering accounts, discovery, library, mypage, ops, citation graph, personalization, onboarding, trends, plans, research, novelty, summary and evidence.
- docsuri-discovery / docsuri-summarization — Python — separately packaged domain/service/adapter units.
- Frontend — TypeScript/React/Next — pages, BFF and browser state.
- docsuri-ingestion — Python — corpus and private document builds, canonical/index control.
- docsuri-ops — Python — reliability authorities, incidents/evaluation and operational tooling.
- docsuri-platform-integrity — Python — authority/run/evidence/compatibility operational protocols.
- docsuri-shared — Python plus JSON schemas — DTOs/events/ports/vector/authz/identity and generated consumers.

### Build System

- Type: uv/pyproject/Hatch Python packages; pnpm/Next frontend; GitHub Actions.
- Config files: seven package pyproject.toml files in the deep list, frontend package.json/tsconfig/Next/Vitest/Playwright, root pytest.ini, four application workflows.
- Build dependencies: backend local shared/discovery/summary/ops; ingestion/shared; ops/shared/platform-integrity; frontend generated schema consumers.
- Declared minimum Python varies >=3.11 to >=3.13; manifest versions are not deployed-version evidence.

### APIs Discovered

- 108 backend source HTTP method/path declarations, health plus fourteen mount groups.
- 4 separate readonly platform-integrity HTTP declarations.
- Next BFF forwards six methods and special-cases SSE/assets.
- Ingestion/ops CLI, queue jobs, shared protocols/events and direct repository/service calls.
- Candidate API document includes every discovered static HTTP declaration grouped by module; dynamic mount and feature availability remain conditional.

### Frameworks & Libraries

- FastAPI/Pydantic, SQLAlchemy/psycopg, Redis, OpenSearch client, boto3, HTTPX and parsing libraries.
- Next 15.5.26/React 19.0.0/TypeScript 5.7.3, SWR, Tailwind and MathJax.
- Platform integrity adds RFC8785, cryptography and local PostgreSQL/filesystem/clock/TLS/credential adapters.
- Full declared constraints and observed isolated-test environment are in technology-stack.md.

### Test Coverage

- Directories: backend/tests; backend/modules/discovery/tests; backend/modules/summarization/tests; frontend/test and e2e; ingestion/tests; ops/tests; platform_integrity/tests; shared/python/tests; tests/accounts and tests/library.
- Frameworks: pytest/Hypothesis/coverage; Vitest/testing-library; Playwright; isolated PostgreSQL and property/security CI lanes.
- Coverage config: present in multiple lanes; no universal percentage or complete suite result established.
- Actual execution by parent: one isolated existing SSE regression failed with [] versus four expected states; no skip/external dependency. A preceding module-local attempt failed collection due to missing FastAPI. Evidence saved in ../../verification/reverse-engineering-test-evidence.md relative to this stage.
- No builds, service restarts, full test suite, live browser, provider calls or model generation were run by this agent.

### Code Quality Indicators

- Linting: Ruff per package, strict TypeScript and ESLint.
- CI/CD: ci.yml, codeql.yml, branch-name-check.yml and release.yml; release no longer has the old deployment job. Configuration does not prove a fresh run passed.
- Documentation: package/runbooks present, but old aidlc-docs/track/deployment statements need reconciliation.
- Security: owner-scoped boundaries and private ID validation present; security/audit jobs exist; no current vulnerability conclusion or full security audit.

### Technical Debt Signals

- Q-01 missing seq in mounted content-job state vs browser parser.
- Q-02 resultRef-only mounted result vs preparedResult browser contract and distinct status handling.
- Q-03 mounted no-op enqueue accepts work without queue dispatch.
- Q-04 literal backslash-n SSE framing, verified by one failed isolated regression.
- Q-05 module presence/readiness omits some retained capability groups.
- Q-06 authoritative environment/data/backups/free-local capacity remain unresolved.
- Q-07 test environment/documentation drift; Q-08 concentrated responsibility/contract layers.
- Exact producers/consumers/test coverage and closure evidence appear once in code-quality-assessment.md.

## Handoff Summary

- **Intent-relevant finding:** source-defined breadth is much larger than paper search/summary alone. Business overview inventories 20 capability groups. The paper-job path has four concrete integration gaps; mounted router at backend/modules/summarization/src/summarization/api/router.py:106,156,193 and shell wiring.py:477–495 disagree with frontend contentJobContracts.ts:143–148,310–318. Preserve these as acceptance work rather than assuming historical tests prove the journey.
- **Risks / follow-up:** establish authoritative users/data and recoverable backups; measure resource fit under $0; investigate obligations; prove complete journey and remaining parity before release. No stack, migration, schedule or numeric quality targets selected.
- **Decisions preserved:** existing human approval, all capabilities, risk-first sequence, one human with agents, concise reviews, $0 free/local, working branch → PR develop → release promotion main.
- **Produced artifacts:** nine candidate files at aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/.aidlc-engine/codekb-stage-DocSuri/; this developer-scan.md; scope-draft-DocSuri.md.
- **Validation:** three Mermaid diagrams manually checked, each has text fallback. Revised scope retains 57 analyzed paths, narrows analyzed components to 13 verified boundaries, and retains 7 shallow paths. Accounts, Evidence/Research, Novelty, Ingestion and Reliability/Ops remain breadth-only component coverage. Mint returned literal unknown for full deep list, simple backend/app.py and ./ in this agent runtime, both named-repo and documented root form; all listed paths exist. Parent must resolve fresh fingerprint/publication validation; no hash fabricated.
- **Next step:** parent compares the revised scope draft against the prior shared-store scope. The previous comparison returned UNKNOWN_SCOPE because that scope was absent; no COVERS/NARROWER verdict was established, and the tool removed that draft. This timestamp revision recreates the draft for a fresh canonical comparison. The pre-scan source/store snapshot separately binds guarded publication. Parent then completes transactional publication and artifact receipt/checks and presents the stage review. This agent did not publish or commit.

### Reproducible scope mint input

The canonical deep-path command was executed as a standalone command (single quotes preserve path syntax):
```sh
bun .codex/tools/aidlc.ts engine workspace codekb-scope-diff --repo DocSuri --mint --paths 'CONVENTIONS.md,backend/app.py,backend/wiring.py,backend/health.py,backend/middleware/auth.py,backend/middleware/wiring.py,backend/modules/library/controller.py,backend/modules/citation_graph/controller.py,backend/modules/onboarding/controller.py,backend/modules/plans/controller.py,backend/modules/personalization/controller.py,backend/modules/user_docmodel/coordinator.py,backend/modules/summarization/src/summarization/api/router.py,backend/modules/summarization/src/summarization/service/job_service.py,backend/modules/summarization/src/summarization/domain/job.py,backend/modules/summarization/src/summarization/real_wiring.py,backend/modules/summarization/src/summarization/adapters/content_job_queue.py,backend/modules/summarization/tests/test_content_job_api.py,backend/modules/summarization/tests/conftest.py,frontend/app/bff/,frontend/lib/api/contentJobApi.ts,frontend/lib/api/contentJobContracts.ts,frontend/lib/jobState.ts,frontend/test/u1ContentJobApi.test.ts,frontend/test/u1JobContracts.test.ts,frontend/test/u1PaperJobJourney.test.tsx,platform_integrity/src/docsuri_platform_integrity/api/app.py,platform_integrity/src/docsuri_platform_integrity/application/evidence.py,platform_integrity/src/docsuri_platform_integrity/domain/compatibility.py,backend/pyproject.toml,backend/modules/discovery/pyproject.toml,backend/modules/summarization/pyproject.toml,ingestion/pyproject.toml,ops/pyproject.toml,platform_integrity/pyproject.toml,shared/python/pyproject.toml,frontend/package.json,frontend/tsconfig.json,frontend/vitest.config.ts,frontend/playwright.config.ts,frontend/next.config.mjs,.github/workflows/ci.yml,.github/workflows/release.yml,.github/workflows/codeql.yml,.github/workflows/branch-name-check.yml,.github/CODEOWNERS,.github/PULL_REQUEST_TEMPLATE.md,backend/docker-compose.yml,ops/local-stack/colima-stack.compose.yaml,ops/server/README.md,shared/README.md,ingestion/README.md,ops/README.md,pytest.ini,backend/modules/discovery/src/discovery/api/router.py,backend/modules/trends/controller.py,backend/modules/mypage/controller.py'
```

