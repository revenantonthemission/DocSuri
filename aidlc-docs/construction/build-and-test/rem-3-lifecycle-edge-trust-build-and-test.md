# REM-3 Lifecycle and Edge Trust — Build and Test 계획

**단계**: CONSTRUCTION / REM-3 Build and Test  
**일자**: 2026-09-30 (Code Generation Part 2 완료 후)  
**전제**: REM-3 Code Generation Part 2 승인·완료, 모든 산출물 생성됨

---

## 빌드 환경

- **Python**: 3.13 (Ruff, pytest, Hypothesis, FastAPI, Pydantic v2, psycopg, SQLAlchemy 2)
- **TypeScript/Next.js**: 14 (React 18, Vitest, Playwright, fast-check)
- **Runtime**: OrbStack Postgres/Redis/OpenSearch/MinIO/ElasticMQ (loopback only)
- **Launchd**: `rem-2-purge` worker 서비스 + 기존 4종
- **Keychain**: unsubscribe JWT, rate-limit credentials
- **MinIO**: `docsuri` bucket, `purged/` prefix
- **ElasticMQ**: `content-job-{translate|summarize|novelty|evidence}` queues + DLQ
- **Redis**: pub/sub (revocation), cache (unsubscribe token)
- **Cloudflare Tunnel**: `/unsubscribe` public endpoint

---

## 빌드 순서

1. **Python 패키지 빌드**
   ```bash
   cd platform_integrity && uv pip install -e . --all-extras
   cd ops && uv pip install -e . --all-extras
   cd shared/python && uv pip install -e .
   ```

2. **Frontend 빌드**
   ```bash
   cd frontend && pnpm install && pnpm run build
   ```

3. **데이터베이스 마이그레이션**
   ```bash
   cd platform_integrity && uv run python -m migrations.run 012_purge_registry
   ```

4. **Launchd worker 서비스 설치 (root 필요)**
   ```bash
   sudo uv run --directory ops python platform-integrity/provision_purge_worker.py --profile test --replace
   ```

5. **Keychain provisioning (root 필요)**
   ```bash
   sudo uv run --directory ops python platform-integrity/provision_rem2_keys.py --profile test
   ```

---

## 테스트 실행 순서

### 1. Python 단위/속성 테스트 (platform_integrity)
```bash
cd platform_integrity
.venv/bin/python -B -m pytest tests/ \
  -q --no-header -p no:cacheprovider \
  -k "not postgres" \
  --tb=short 2>&1 | tail -20
```
- 기대: **전체 pass**, property tests 포함

### 2. Python 단위/속성 테스트 (ops)
```bash
cd ops
.venv/bin/python -B -m pytest tests/ \
  -q --no-header -p no:cacheprovider \
  -k "not postgres" \
  --tb=short 2>&1 | tail -20
```
- 기대: **전체 pass**, property tests 포함

### 3. PostgreSQL 통합 테스트 (격리된 test DB)
```bash
# OrbStack Postgres 실행 중 확인
docker ps | grep postgres

cd platform_integrity
.venv/bin/python -B -m pytest tests/ \
  -q --no-header -p no:cacheprovider \
  -k "postgres" \
  --tb=short 2>&1 | tail -20

cd ../ops
.venv/bin/python -B -m pytest tests/ \
  -q --no-header -p no:cacheprovider \
  -k "postgres" \
  --tb=short 2>&1 | tail -20
```
- 기대: **전체 pass**

### 4. Ruff 린트 (양쪽)
```bash
cd platform_integrity && .venv/bin/python -B -m ruff check src tests
cd ../ops && .venv/bin/python -B -m ruff check src tests ../ops/platform-integrity
```
- 기대: **All checks passed!**

### 5. Frontend 테스트
```bash
cd frontend
pnpm run test 2>&1 | tail -30
pnpm run lint 2>&1 | tail -10
```
- 기대: **pass**, type check pass

### 6. E2E 테스트 (Playwright) — 선택적
```bash
cd frontend
pnpm run test:e2e 2>&1 | tail -30
```
- 기대: 주요 user flow pass (purge request, unsubscribe, consent revoke, account deletion)

---

## 통합 검증 시나리오 (수동/자동)

| 시나리오 | 검증 내용 | 자동화 |
|---|---|---|
| Account deletion soft delete → grace → hard delete | 요청 → SOFT_DELETED → grace period → PURGED | 자동 |
| Unsubscribe token validation | JWT verify → Redis cache hit/miss → job 접수 | 자동 |
| Consent revocation propagation | revoke API → Redis pub/sub → worker cache DEL → job FAILED | 자동 |
| Rate-limit identity chain | Cloudflare header → BFF proxy → FastAPI token bucket | 자동 |
| Edge trust: ingress identity spoofing 방지 | spoofed header → 403 거부 | 자동 |
| Purge worker hourly execution | launchd trigger → advisory lock → cascade delete | 수동 (launchd) |
| Consent grant/revoke lifecycle | grant → active → revoked → expired | 자동 |
| Account deletion cascade | account delete → cascade purge → backup purge | 자동 |
| Password reset flow | request → email → token → reset | 자동 |
| Social login (Google/ORCID) | OIDC flow → account link/create | 자동 |

---

## 검증 게이트 (모두 pass 시에만 통과)

- [ ] Python 전체 테스트 pass (platform_integrity + ops)
- [ ] Frontend 테스트 pass
- [ ] Ruff 깨끗
- [ ] Property tests (Hypothesis/fast-check) pass
- [ ] 통합 시나리오 자동화 pass
- [ ] 수동 Launchd/Keychain 검증 pass (root 필요)
- [ ] Backup/restore 검증 pass
- [ ] `git diff --check` 깨끗

---

## 롤백 계획

- Migration: `uv run python -m migrations.run 012_purge_registry --rollback`
- Launchd: `sudo launchctl bootout system/rem-2-purge` + plist 삭제
- Keychain: `sudo security delete-keychain /Library/Application Support/DocSuri/rem-2/keys/*.keychain-db`
- DB: purge_registry 테이블만 rollback, 기존 데이터 영향 없음
- Launchd plist: `/Library/LaunchDaemons/rem-2-purge.plist` 삭제

---

## 승인 기준

- [ ] 위 모든 자동 테스트 pass
- [ ] Ruff 깨끗
- [ ] 수동 Launchd/Keychain/Backup 검증 pass (operator 서명)
- [ ] `aidlc-docs/audit.md`에 빌드/테스트 결과 기록
- [ ] `aidlc-state.md` REM-3 Build and Test 완료 체크
