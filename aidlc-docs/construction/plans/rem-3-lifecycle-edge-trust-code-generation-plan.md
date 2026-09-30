# REM-3 Lifecycle and Edge Trust — Code Generation 계획

**단계**: CONSTRUCTION / REM-3 Code Generation (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- Functional Design (FD-Q1~8 승인 대기)
- NFR Requirements (NFR-Q1~13 승인 대기)
- NFR Design (ND-Q1~10 승인 대기)
- Infrastructure Design (ID-Q1~8 승인 대기)
- REM-1/2 완료 산출물: `platform_integrity/`, `ops/platform-integrity/`, `shared/`, launchd, receipt signer, keychain, clock, mTLS, backup/restore, load acceptance

**목표**: REM-3 Lifecycle and Edge Trust의 Code Generation 상세 체크리스트를 작성하고, 5개 결정 질문(REM-3-CG-Q1~5)에 대한 답변을 수집해 Generation Part 2 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1/2 `platform_integrity/`, `ops/platform-integrity/`, `shared/` 산출물 고정 공급
- Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2/psycopg, async/await, Ruff, pytest, Hypothesis
- TypeScript/Next.js 14, React 18, fast-check, Vitest, Playwright
- Security Full, PBT Full, Resiliency custom(`RESILIENCY-08` 면제)
- `RESILIENCY-08` 면제(단일 Mac), full corpus rebuild 별도 승인

---

## 생성 체크리스트 (Part 2 승인 후 실행)

### 1. Purge Registry + Migration
- [ ] `platform_integrity/migrations/012_purge_registry.sql` — `purge_registry` 테이블 + advisory lock 함수
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/purge.py` — `PurgeRegistry` 어댑터 (soft delete, grace period, hard delete 멱등)

### 2. Purge Worker
- [ ] `ops/platform-integrity/workers/purge_worker.py` — `PurgeWorker` (advisory lock, cascade delete, 멱등)
- [ ] `ops/platform-integrity/provision_purge_worker.py` — launchd 서비스 등록 (`rem-2-purge`, 매시간 실행)

### 3. Unsubscribe Token + Endpoint
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/unsubscribe.py` — `UnsubscribeTokenService` (HS256 JWT 생성/검증, Redis cache)
- [ ] `platform_integrity/src/docsuri_platform_integrity/api/unsubscribe.py` — `GET /unsubscribe?token=<jwt>` 엔드포인트
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/email.py` — 이메일 발송(다이제스트/알림)용 템플릿

### 4. Cloudflare/BFF/FastAPI Identity Chain
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/identity.py` — `ClientIdentity` 추출/검증 (Cloudflare 헤더 파싱)
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/ratelimit.py` 확장 — identity별 token bucket (Cloudflare→BFF→FastAPI 체인)

### 5. Consent/Token Revocation + Redis Pub/Sub
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/revocation.py` — `RevocationService` (Redis pub/sub, cache invalidation)
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/consent.py` — `ConsentService` (grant/revoke/expire, token hash 저장)

### 6. Consent/Token Revocation Propagation
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/authz.py` 확장 — `AuthorizationService.recheck`에 revocation 체크 추가
- [ ] `ops/platform-integrity/content_job_service.py` 확장 — `recheck_authz`에서 revocation 체크

### 6. Account Lifecycle (Password Reset, Social Login, Account Deletion)
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/account.py` — `AccountLifecycleService` (비번 재설정, 소셜 로그인 Google/ORCID, 계정 삭제 cascade)
- [ ] `platform_integrity/src/docsuri_platform_integrity/api/account.py` — 계정 관리 API (`/account/password-reset`, `/account/delete`, `/account/social-login`)

### 7. Purge Worker Launchd Provisioning
- [ ] `ops/platform-integrity/provision_purge_worker.py` — launchd 서비스 등록 (`rem-2-purge`, 매시간 실행)

### 7. Edge Trust: Ingress Identity + Rate-limit
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/edge.py` — `EdgeIdentityMiddleware` (Cloudflare→BFF→FastAPI 체인)

### 8. Property Tests (PBT Full)
- [ ] `platform_integrity/tests/test_purge_property.py` — purge 상태 기계 불변식
- [ ] `platform_integrity/tests/test_unsubscribe_property.py` — token 검증/멱등성
- [ ] `platform_integrity/tests/test_revocation_property.py` — revocation 전파 불변식
- [ ] `platform_integrity/tests/test_authz_recheck_property.py` — 권한 재검증 불변식
- [ ] `platform_integrity/tests/test_rate_limit_property.py` — rate-limit bucket 격리
- [ ] `ops/tests/test_purge_worker.py` — purge worker 멱등성/동시성
- [ ] `ops/tests/test_unsubscribe.py` — token 검증/캐시
- [ ] `ops/tests/test_revocation.py` — revocation 전파

### 8. Integration Tests
- [ ] `platform_integrity/tests/test_purge_integration.py` — purge lifecycle E2E
- [ ] `platform_integrity/tests/test_unsubscribe_integration.py` — unsubscribe flow E2E
- [ ] `platform_integrity/tests/test_consent_revocation_integration.py` — consent/token 철회 E2E
- [ ] `ops/tests/test_edge_trust_integration.py` — identity 체인/rate-limit E2E

### 9. Frontend: Unsubscribe/Consent/Account UI
- [ ] `frontend/components/UnsubscribePage.tsx` — token 검증 후 상태 표시
- [ ] `frontend/components/ConsentManager.tsx` — consent grant/revoke UI
- [ ] `frontend/components/AccountSettings.tsx` — password reset, social login, account deletion

### 10. Provisioning Scripts
- [ ] `ops/platform-integrity/provision_purge_worker.py` — launchd purge worker 등록
- [ ] `ops/platform-integrity/provision_edge_keys.py` — edge trust keychain (unsubscribe JWT, rate-limit)

---

## 분해 질문 (Decomposition Questions)

### REM-3-CG-Q1 — Purge worker: 단일 프로세스 vs 배치 프로세서

대량 owner purge 시 단일 프로세스가 순차 처리 vs 배치 프로세서(여러 worker가 분산 처리).

A) **단일 프로세스 + advisory lock + 배치 DELETE(권장)** — 단일 `purge_worker`가 hourly 실행, `pg_advisory_xact_lock`으로 동시 실행 방지, `DELETE FROM table WHERE owner_uid = $1` bulk delete로 효율 처리. 동시 실행 방지가 핵심.

B) 분산 worker pool — 복잡도 증가, 멱등성 관리 복잡.

C) 기타

[Answer]: A) **단일 프로세스 + advisory lock + 배치 DELETE(권장)** — 단일 `purge_worker`가 hourly 실행, `pg_advisory_xact_lock`으로 동시 실행 방지, `DELETE FROM table WHERE owner_uid = $1` bulk delete로 효율 처리. 동시 실행 방지가 핵심.

---

### REM-3-CG-Q2 — Unsubscribe token: HS256 JWT vs opaque token

HS256 JWT(자체 포함) vs opaque random token + DB lookup.

A) **HS256 JWT + Redis cache(권장)** — token 자체가 payload 포함(email, exp, purpose). 검증 로컬(jwt.decode), Redis cache로 token→job_id 매핑. DB lookup 최소화.

B) Opaque token + DB only — 단순하지만 매 요청 DB hit.

C) 기타

[Answer]: A) **HS256 JWT + Redis cache(권장)** — token 자체가 payload 포함(email, exp, purpose). 검증 로컬(jwt.decode), Redis cache로 token→job_id 매핑. DB lookup 최소화.

---

### REM-3-CG-Q3 — Consent/token revocation: Redis pub/sub vs polling

철회 전파 방식: Redis pub/sub 즉시 전파 vs 주기적 polling.

A) **Redis pub/sub + 즉시 cache invalidation(권장)** — `PUBLISH revoke:{token_hash} {...}` → 모든 worker `SUBSCRIBE revoke:*` → 즉시 로컬 cache `DEL`. 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`.

B) 주기적 polling — 지연 발생, 구현 단순.

C) 기타

[Answer]: A) **Redis pub/sub + 즉시 cache invalidation(권장)** — `PUBLISH revoke:{token_hash} {...}` → 모든 worker `SUBSCRIBE revoke:*` → 즉시 로컬 cache `DEL`. 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`.

---

### REM-3-CG-Q4 — Identity 체인: Cloudflare → BFF → FastAPI 구현 분리

Cloudflare → BFF → FastAPI identity 체인을 단일 미들웨어 vs 분리된 레이어로 구현.

A) **단일 `IdentityMiddleware` 체인(권장)** — `IdentityMiddleware`가 Cloudflare 헤더(`CF-Connecting-IP`, 인증 토큰) 검증 → `X-Client-Identity` 헤더 설정 → BFF가 FastAPI에 프록시 → FastAPI `RateLimitMiddleware`가 identity별 token bucket 적용. 단일 진입점으로 일관성 보장.

B) 분리된 미들웨어 — 각 레이어 독립, 중복 검증 가능.

C) 기타

[Answer]: A) **단일 `IdentityMiddleware` 체인(권장)** — `IdentityMiddleware`가 Cloudflare 헤더(`CF-Connecting-IP`, 인증 토큰) 검증 → `X-Client-Identity` 헤더 설정 → BFF가 FastAPI에 프록시 → FastAPI `RateLimitMiddleware`가 identity별 token bucket 적용. 단일 진입점으로 일관성 보장.

---

### REM-3-CG-Q5 — Account deletion: soft delete → grace → hard delete vs 즉시 hard delete

FR-28 계정 삭제 시 soft delete → grace period(N일) → hard delete vs 즉시 hard delete.

A) **Soft delete + grace period + hard delete(권장)** — `ACTIVE → SOFT_DELETED(요청 시) → grace period(30일) → PURGED(worker)`. 유예 기간 동안 복구 가능. cascade delete로 owner-scoped 데이터 파기.

B) 즉시 hard delete — 단순하지만 복구 불가, 사용자 실수 위험.

C) 기타

[Answer]: A) **Soft delete + grace period + hard delete(권장)** — `ACTIVE → SOFT_DELETED(요청 시) → grace period(30일) → PURGED(worker)`. 유예 기간 동안 복구 가능. cascade delete로 owner-scoped 데이터 파기.

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-CG-Q1~5에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Generation Part 2로 진행하지 않는다.
