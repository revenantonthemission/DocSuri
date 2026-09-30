# REM-2 Private Content — Tech Stack Decisions

**단계**: CONSTRUCTION / REM-2 NFR Requirements Generation Part 2  
**일자**: 2026-09-30  
**기반**: `nfr-requirements.md` 승인 (NFR-Q1~13 전수 A), REM-1 확정 스택 계승

---

## 1. 언어·런타임 (Inherited from REM-1)

| 계층 | 기술 | 버전 | 비고 |
|---|---|---|---|
| Python | CPython | 3.13 | `-I -B` 필수, `-B`로 bytecode 생성 방지 |
| Python 비동기 | asyncio | stdlib | `asyncio.Semaphore`로 동시성 제어 |
| TypeScript | TypeScript | 5.3+ | Next.js 14 App Router |
| React | React | 18.2 | Server Components + Client Components |
| Next.js | Next.js | 14.2 | App Router, Server Actions |

---

## 2. 프레임워크·라이브러리 (Python)

| 용도 | 라이브러리 | 버전 | 비고 |
|---|---|---|---|
| Web Framework | FastAPI | 0.109+ | `uvicorn` ASGI 서버 |
| Validation | Pydantic | v2.7+ | `model_validate_json(canonical(...))` 필수 |
| ORM | SQLAlchemy | 2.0+ | async session, `AsyncSession` |
| DB Driver | psycopg | 3.1+ | `psycopg[binary]`, `asyncpg` 미사용 |
| Async HTTP | httpx | 0.26+ | `AsyncClient`, timeout 설정 필수 |
| Serialization | orjson | 3.9+ | `orjson.dumps(option=orjson.OPT_SERIALIZE_NUMPY)` |
| JWT | python-jose | 3.3+ | HS256, `jwt.encode/decode` |
| ElasticMQ Client | aio-pika | 9.3+ | async RabbitMQ/ElasticMQ client |
| MinIO Client | minio | 7.2+ | presigned URL 생성 |
| Crypto | cryptography | 42+ | Ed25519, HKDF, AES-GCM |
| Testing | pytest | 8.0+ | `-p no:cacheprovider`, Hypothesis |
| Property Testing | Hypothesis | 6.100+ | `@given`, `@settings(max_examples=2000)` |
| Property Testing (TS) | fast-check | 3.19+ | `@fc.test`, `@fc.property` |
| Lint | Ruff | 0.3+ | `select = ["E","F","I","UP","B"]` (BLE 제외) |
| Type Check | pyright | 1.1+ | strict mode |

---

## 3. 프레임워크·라이브러리 (TypeScript/Frontend)

| 용도 | 라이브러리 | 버전 | 비고 |
|---|---|---|---|
| React | React | 18.2 | Server/Client Component 분리 |
| Next.js | Next.js | 14.2 | App Router, Server Actions |
| State | Zustand | 4.4+ | Client-side state만 |
| HTTP | ky | 1.3+ | 브라우저 fetch wrapper |
| SSE | EventSource | native | `EventSource` API 직접 사용 |
| JWT Decode | jwt-decode | 4.0+ | 클라이언트 사이드 검증용 |
| Testing | Vitest | 2.0+ | `--pool=forks` |
| E2E | Playwright | 1.40+ | `--project=chromium` |
| Property Testing | fast-check | 3.19+ | `@fc.test` |
| Lint | ESLint | 8.56+ | `@typescript-eslint` |
| Format | Prettier | 3.2+ | `--single-quote --trailing-comma=es5` |

---

## 4. 인프라·미들웨어 (Inherited from REM-1)

| 구성요소 | 기술 | 배포 | 비고 |
|---|---|---|---|
| Process Manager | launchd | macOS | `InitGroups=false`, `Umask=0o077` |
| Container Runtime | OrbStack | macOS | Postgres/Redis/OpenSearch/MinIO/ElasticMQ |
| PostgreSQL | Postgres | 16 | OrbStack container, named volume |
| Redis | Redis | 7.2 | OrbStack container |
| OpenSearch | OpenSearch | 2.11 | OrbStack container |
| MinIO | MinIO | RELEASE.2024 | `127.0.0.1:9000` internal only |
| ElasticMQ | ElasticMQ | 1.3+ | `127.0.0.1:9324` internal only |
| Keychain | macOS Security Framework | system | `security` CLI로 관리 |
| Backup Drive | USB APFS encrypted | `/Volumes/DocSuri_Backup` | 일일 03:00 KST |

---

## 4.1 Content Job 전용 추가 인프라

| 구성요소 | 기술 | 설정 | 비고 |
|---|---|---|---|
| Job Queue | ElasticMQ | `content-job-{translate\|summarize\|novelty\|evidence}` | visibility timeout 5분, maxReceiveCount 3 |
| Dead Letter Queue | ElasticMQ | `content-job-dlq` | maxReceiveCount 3 초과 시 이동 |
| Asset Storage | MinIO | `assets/` + `private/userdoc/` prefix | presigned URL로만 접근 |
| Keychain Secrets | macOS Keychain | `rem-2-asset-jwt`, `rem-2-queue`, `rem-2-minio` | `_docsuri_rem2_sign` 계정 소유 |
| Launchd Workers | launchd | `rem-2-content-{translate\|summarize|novelty|evidence}` | `_docsuri_rem2_worker` 계정, `InitGroups=false` |

---

## 5. 보안·암호화 스택

| 용도 | 알고리즘/라이브러리 | 키 관리 |
|---|---|---|
| Ed25519 서명/검증 | `cryptography.hazmat.primitives.asymmetric.ed25519` | Keychain에 private key 저장 |
| JWT (Asset Token) | HS256 (`python-jose`) | Keychain `rem-2-asset-jwt` secret |
| AES-GCM (대칭 암호화) | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` | Keychain `rem-2-asset-jwt` 파생 |
| TLS | TLS 1.3, `ssl.create_default_context()` | MinIO/Postgres cert: Keychain `rem-2-minio` |
| Password Hash | Argon2id (`argon2-cffi`) | - |
| Argon2id Params | `time_cost=3, memory_cost=65536, parallelism=4` | OWASP 권장 |

---

## 5.1 Keychain Secret Mapping (REM-2)

| Secret | Keychain Path | Service | Account | Owner | 용도 |
|---|---|---|---|---|---|
| Asset JWT Secret | `/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db` | `docsuri.rem2.asset` | `asset-jwt` | `_docsuri_rem2_sign` | Asset presigned JWT 서명 |
| ElasticMQ Creds | `/Library/Application Support/DocSuri/rem-2/keys/queue.keychain-db` | `docsuri.rem2.queue` | `elasticmq` | `_docsuri_rem2_sign` | ElasticMQ 인증 |
| MinIO Keys | `/Library/Application Support/DocSuri/rem-2/keys/minio.keychain-db` | `docsuri.rem2.minio` | `minio` | `_docsuri_rem2_sign` | MinIO access/secret key |

Provisioning: `provision_rem2_keys.py` (root, `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽기).

---

## 6. 데이터베이스·마이그레이션 (Inherited)

| 항목 | 결정 |
|---|---|
| Migration Tool | `backend/migrations/__main__.py` 커스텀 러너 |
| Ordered Registry | `backend/migrations/registry.py` (단일 ordered registry) |
| Migration Files | `platform_integrity/migrations/001~011_control.sql` 등 |
| REM-2 추가 테이블 | 없음 (기존 `effect_ledger`, `outbox`, `r1_control` 재사용) |
| Locking | `pg_advisory_lock` for effect execution |
| Transaction | `SERIALIZABLE` isolation for effect execution |

---

## 7. 테스트·품질 스택

| 영역 | 도구 | 설정 |
|---|---|---|
| Unit/Integration (Py) | pytest + Hypothesis | `-p no:cacheprovider`, seed `20260930` |
| Property Test (Py) | Hypothesis | `@settings(max_examples=2000, derandomize=True)` |
| Property Test (TS) | fast-check | `@fc.test`, `@fc.property`, `fc.configureGlobal({numRuns: 2000})` |
| Integration (PG) | pytest + disposable PG | `pytest-postgresql` fixture |
| E2E | Playwright | `--project=chromium`, `--retries=2` |
| Lint (Py) | Ruff | `select = ["E","F","I","UP","B"]` (BLE 제외) |
| Lint (TS) | ESLint + Prettier | `--fix` on save |
| Type Check (Py) | pyright | `strict = true` |
| Type Check (TS) | tsc | `strict: true`, `noUncheckedIndexedAccess: true` |
| CI | GitHub Actions | `uv run pytest`, `pnpm test`, `ruff check` |

---

## 8. 관측·로깅

| 구성요소 | 기술 | 설정 |
|---|---|---|
| Structured Logging | `structlog` + `orjson` | JSON 라인, `timestamp`, `level`, `metric`, `labels` |
| Metrics Export | stdout JSON lines | Prometheus node_exporter 수집 |
| Tracing | `structlog` contextvars | `jobId`, `taskType`, `attempt` context |
| Alerting | CloudWatch / 로컬 파일 | NFR-O1 8지표 경보 규칙 적용 |

---

## 9. 버전 관리·빌드

| 항목 | 결정 |
|---|---|
| Python Package Manager | `uv` (lockfile `uv.lock` 필수) |
| Node Package Manager | `pnpm` (lockfile `pnpm-lock.yaml` 필수) |
| Build | `uv build` (Python), `pnpm run build` (Frontend) |
| Release | `uv publish` / `pnpm publish` (필요 시) |
| Lockfile Policy | PR에서 lockfile 변경 시 `uv lock --upgrade` / `pnpm install` 후 커밋 |

---

## 10. 승인 기록

| 결정 항목 | 답변 | 일자 |
|---|---|---|
| NFR-Q1~13 (전수) | A | 2026-09-30 |

**다음**: NFR Design Generation Part 2 → `construction/rem-2-private-content/nfr-design/`
