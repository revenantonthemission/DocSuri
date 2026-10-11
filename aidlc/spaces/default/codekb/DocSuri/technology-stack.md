# DocSuri Technology Stack

## Declared application stack

Values below are manifest constraints/pins read on 2026-10-11, not claims about installed or deployed versions. Lockfiles exist but their full transitive resolution was not audited.

| Area | Language/runtime constraint | Frameworks and key libraries |
|---|---|---|
| Backend shell | Python >=3.13; package version 0.1.0 | FastAPI >=0.110, Uvicorn >=0.29, SQLAlchemy >=2,<3, psycopg >=3.1, Redis >=5, Pydantic >=2.7,<3, HTTPX, Argon2, cryptography, pyotp, boto3, Lambda runtime adapter |
| Discovery | Python >=3.11 | Pydantic/shared; optional FastAPI; real extras OpenSearch client >=2.4 and boto3 |
| Summarization | Python >=3.11 | Pydantic/shared; optional FastAPI; real extras boto3, Redis, psycopg and psycopg_pool |
| Ingestion | Python >=3.11 | Pydantic/settings, HTTPX, boto3, opensearch-py >=2.6,<3, psycopg >=3.2/pool, structlog, pdfplumber, lxml >=6.1, BeautifulSoup, defusedxml; optional PDFium/Pillow assets |
| Ops | Python >=3.13 | shared, docsuri-platform-integrity 0.1.0, Pydantic, psutil |
| Platform integrity | Python >=3.13 | Pydantic >=2.13.4, RFC8785, cryptography >=50; optional API FastAPI >=0.138/Uvicorn >=0.49; PostgreSQL psycopg >=3.3.4; tooling/REM extras |
| Shared Python | Python >=3.11 | Pydantic bindings/utilities; datamodel-code-generator/jsonschema tooling |
| Frontend | TypeScript 5.7.3; pnpm 9.15.9 | Next.js 15.5.26, React 19.0.0, SWR 2.5.1, Tailwind 4.3.3, Sentry 11.4.0, clsx 2.1.1, tailwind-merge 3.7.0, MathJax ^3.2.2 |

Sources: each package's `pyproject.toml`, `frontend/package.json`. Backend's uv sources use local shared/discovery/summarization/ops paths; Hatch builds the standalone Python package wheels. Python minimum versions differ across packages; the assembled supported runtime must satisfy all selected packages, not just a module's minimum.

## Build and validation tools

- Python uv dependency environments and lockfiles, Hatchling package builds, pytest/Hypothesis, Ruff, coverage/pytest-cov and pip-audit.
- Frontend Next standalone output, strict TypeScript, ESLint 9.18, Prettier 3.4.2, Vitest 3.2.6 and Playwright 1.55.1; schema/type consumer generation checks.
- GitHub Actions CI, CodeQL, Gitleaks, dependency audit and release automation. Configuration is not evidence of a recent successful run.
- Docker/Compose and AWS CDK/serverless-era definitions coexist with native/local launchd tooling. No infrastructure was provisioned or selected for v2.

## Storage and integration technology

Application adapters target PostgreSQL, Redis, OpenSearch, S3-compatible storage and SQS-compatible queues. `backend/docker-compose.yml` declares digest-pinned PostgreSQL 16, Redis 7.4.11, OpenSearch 2.19.5, MinIO and ElasticMQ. `ops/local-stack/colima-stack.compose.yaml` is explicitly a development stack with different PostgreSQL and SeaweedFS stand-in choices and local security relaxations. Neither file proves running versions or usable credentials.

LLM/embedding adapters include AWS Bedrock and OpenAI-compatible/local endpoints; the inspected summary real wiring selects an OpenAI-compatible provider only when explicitly configured and otherwise constructs Bedrock. Source default/local model strings are not measured capacity or quality guarantees. External metadata/auth/export/email providers are inventoried in [dependencies](dependencies.md).

## One observed test environment

The parent independently ran one existing isolated SSE regression using the already-installed backend environment: Python 3.13.7, pytest 9.1.0, pytest-asyncio 1.4.0, FastAPI 0.137.1 and Starlette 1.3.1. This is only that test's environment, not a v2 selection or proof all manifests agree. The module-local interpreter lacked FastAPI and could not collect it. See [test evidence](../../intents/261010-docsuri-v2-rebuild/verification/reverse-engineering-test-evidence.md).

## Upgrade and feasibility boundary

No vulnerability database or upstream release lookup was performed; no claim of latest, secure or supported versions is made. Current manifest pins/ranges, existing environments, local resource capacity and free-service/provider terms require verification before v2 technology decisions. The approved budget remains $0; existing paid-capable adapters cannot silently become a paid fallback.
