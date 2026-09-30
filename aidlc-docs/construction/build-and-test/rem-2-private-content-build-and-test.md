# REM-2 Private Content — Build and Test 계획

**단계**: CONSTRUCTION / REM-2 Build and Test  
**일자**: 2026-09-30 (Code Generation Part 2 완료 후)  
**전제**: REM-2 Code Generation Part 2 승인·완료, 모든 산출물 생성됨

---

## 빌드 환경

- **Python**: 3.13 (Ruff, pytest, Hypothesis, FastAPI, Pydantic v2, psycopg, SQLAlchemy 2)
- **TypeScript/Next.js**: 14 (React 18, Vitest, Playwright, fast-check)
- **Runtime**: OrbStack Postgres/Redis/OpenSearch/MinIO/ElasticMQ (loopback only)
- **Launchd**: `rem-2-content-translate|summarize|novelty|evidence` worker 서비스
- **Keychain**: asset JWT, ElasticMQ, MinIO credentials
- **MinIO**: `docsuri` bucket, `private/userdoc/`, `assets/` prefix
- **ElasticMQ**: `content-job-{translate|summarize|novelty|evidence}` queues + DLQ
- **CSP**: `img-src 'self' http://127.0.0.1:9000`

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

3. **Launchd worker 서비스 설치 (root 필요)**
   ```bash
   sudo uv run --directory ops python platform-integrity/provision_content_workers.py \
     --profile test --replace
   ```

3. **Keychain provisioning (root 필요)**
   ```bash
   sudo uv run --directory ops python platform-integrity/provision_rem2_keys.py \
     --profile test
   ```

4. **데이터베이스 마이그레이션 (이미 적용됨 — REM-1에서 완료)**
   - `migrations/001~011` 이미 적용됨. REM-2 추가 테이블 없음(기존 `effect_ledger`, `outbox` 재사용).

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
- 기대: 주요 user flow pass (job 제출 → SSE 상태 → asset 조회)

---

## 통합 검증 시나리오 (수동/자동)

| 시나리오 | 검증 내용 | 자동화 |
|---|---|---|
| Private userdoc write → read | 업로드 → job → DocModel 저장 → owner read 성공, non-owner 404 | 자동 |
| Translation cache hit | 동일 canonical paper 재요청 → 동기 200 + assetId, model 미실행 | 자동 |
| Translation cache miss | 신규 paper → job 접수 → SSE 상태 전이 → 완료 → asset 전달 | 자동 |
| Asset serving | assetId + token → presigned URL → 307 redirect → MinIO 다운로드 | 자동 |
| Job authz recheck | 권한 만료 중 job 실행 → 즉시 failed + event | 자동 |
| Queue redelivery | worker crash 시뮬레이션 → redelivery → 중복 effect ledger 0 | 자동 |
| Rate-limit | 동일 identity 급증 → 429 반환 | 자동 |
| Timeout alignment | 긴 생성 → job 전환 → 완료 → asset 전달 | 자동 |
| Backup/restore | private userdoc + asset backup → new incarnation restore → 검증 | 자동 |
| Launchd worker | service 등록/시작/중지/로그 회전 | 수동 (root) |

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

- Launchd: `sudo launchctl bootout system/rem-2-content-*` + plist 삭제
- Keychain: `sudo security delete-keychain /Library/Application Support/DocSuri/rem-2/keys/*.keychain-db`
- MinIO: `mc rm --recursive --force local/docsuri/assets/rem2-test/`, `mc rm --recursive --force local/docsuri/private/userdoc/rem2-test/`
- DB: migration rollback 불필요(추가 테이블 없음). `effect_ledger`/`outbox`만 REM-2 job용 행 정리.
- Launchd plist: `/Library/LaunchDaemons/rem-2-content-*.plist` 삭제

---

## 승인 기준

- [ ] 위 모든 자동 테스트 pass
- [ ] Ruff 깨끗
- [ ] 수동 Launchd/Keychain/Backup 검증 pass (operator 서명)
- [ ] `aidlc-docs/audit.md`에 빌드/테스트 결과 기록
- [ ] `aidlc-state.md` REM-2 Build and Test 완료 체크
