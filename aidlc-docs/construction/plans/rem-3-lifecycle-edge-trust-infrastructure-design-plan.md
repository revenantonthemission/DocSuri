# REM-3 Lifecycle and Edge Trust — Infrastructure Design 계획

**단계**: CONSTRUCTION / REM-3 Infrastructure Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- NFR Requirements (NFR-Q1~13 승인 대기)
- NFR Design (ND-Q1~10 승인 대기)
- Functional Design (FD-Q1~8 승인 대기)
- REM-1/2 인프라: launchd, OrbStack(Postgres/Redis/OpenSearch/MinIO/ElasticMQ), clock, receipt signer, keychain, backup/restore, load acceptance
- `verification-remediation-2026-09-18.md` §2 Single-Mac Production 기준

**목표**: REM-3 Lifecycle and Edge Trust의 인프라 배치·배포·운영 설계를 확정하고, 8개 결정 질문(REM-3-ID-Q1~8)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- **Single-Mac production**: OrbStack으로 Postgres/Redis/OpenSearch/MinIO/ElasticMQ 실행. host port loopback 전용. Cloudflare Tunnel로 공개 경로.
- **Launchd**가 API, web, ingestion, summarization, evidence, novelty worker, purge, backup, heartbeat, tunnel 관리.
- **Backup**: 일일 03:00 Asia/Seoul, `/Volumes/DocSuri_Backup`(USB APFS 암호화 volume, 상시 연결). RPO 24h / RTO 수 시간.
- **REM-1/2 계약 동결**: `shared/dtos`, `shared/ports`, `shared/vector-spec` 공급.
- **Security Full, PBT Full, Resiliency custom**(`RESILIENCY-08` 면제) 계승.

---

## 분해 질문 (Decomposition Questions)

### REM-3-ID-Q1 — Purge registry 테이블 + migration

F04/R3C: `purge_registry` 테이블 추가. 기존 `migrations/001~011` 이후 `012_purge_registry.sql`로 추가.

A) **Migration 012 + advisory lock(권장)** — 
```sql
-- migrations/012_purge_registry.sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,
    UNIQUE (owner_uid, version)
);
CREATE INDEX idx_purge_grace ON purge_registry(grace_until) WHERE status = 'SOFT_DELETED';
```
advisory lock(`pg_advisory_xact_lock`)로 동시 실행 방지.

B) Migration 없이 별도 스키마 — 기존 migration 체인 위반.

C) 기타

[Answer]: AA) **Migration 012 + advisory lock(권장)** — 
```sql
-- migrations/012_purge_registry.sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,
    UNIQUE (owner_uid, version)
);
CREATE INDEX idx_purge_grace ON purge_registry(grace_until) WHERE status = 'SOFT_DELETED';
```
advisory lock(`pg_advisory_xact_lock`)로 동시 실행 방지.

---

### REM-3-ID-Q2 — Unsubscribe token endpoint + JWT 검증

F09/RJ-AC10: `GET /unsubscribe?token=<jwt>` 엔드포인트. HS256 JWT 검증 + Redis cache.

A) **FastAPI endpoint + Redis cache(권장)** — 
- Endpoint: `GET /unsubscribe?token=<jwt>`
- 검증: `jwt.decode(token, HS256_KEY, algorithms=["HS256"])` → `exp` 확인 → `payload.email` 추출
- Redis: `GET unsubscribe:{token_hash}` → job_id 반환 (cache hit 시 즉시 200)
- Cache miss 시 DB lookup → `SETEX unsubscribe:{token_hash} 86400 {job_id}`

B) Opaque token + DB only — 단순하지만 latency 높음.

C) 기타

[Answer]: AA) **FastAPI endpoint + Redis cache(권장)** — 
- Endpoint: `GET /unsubscribe?token=<jwt>`
- 검증: `jwt.decode(token, HS256_KEY, algorithms=["HS256"])` → `exp` 확인 → `payload.email` 추출
- Redis: `GET unsubscribe:{token_hash}` → job_id 반환 (cache hit 시 즉시 200)
- Cache miss 시 DB lookup → `SETEX unsubscribe:{token_hash} 86400 {job_id}`

---

### REM-3-ID-Q3 — Rate-limit identity 체인: Cloudflare → BFF → FastAPI

F10/SECURITY-11: Cloudflare → BFF → FastAPI identity 체인 구현.

A) **헤더 체인 + 미들웨어(권장)** — 
- Cloudflare: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket
- Identity: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`

B) Cookie/session 기반 — 단순하지만 stateless 아님.

C) 기타

[Answer]: AA) **헤더 체인 + 미들웨어(권장)** — 
- Cloudflare: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket
- Identity: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`

---

### REM-3-ID-Q4 — Purge worker: launchd 서비스 + advisory lock

F04/R3C: `purge_worker`를 launchd 서비스로 등록. advisory lock으로 동시 실행 방지.

A) **Launchd 서비스 + advisory lock(권장)** — 
- Label: `rem-2-purge`
- Schedule: 매시간 실행(`StartCalendarInterval: Hour=*`)
- Worker: `pg_advisory_xact_lock(hashtext('purge_worker'))`로 단일 실행 보장
- 처리: `SOFT_DELETED` + `grace_until < now` → advisory lock(`owner_uid`) → cascade delete → `PURGED`
- Concurrency: 단일 인스턴스, 동시 실행 방지

B) Cron + PID file — launchd 미사용, 단순하지만 재시작/로그 관리 불편.

C) 기타

[Answer]: AA) **Launchd 서비스 + advisory lock(권장)** — 
- Label: `rem-2-purge`
- Schedule: 매시간 실행(`StartCalendarInterval: Hour=*`)
- Worker: `pg_advisory_xact_lock(hashtext('purge_worker'))`로 단일 실행 보장
- 처리: `SOFT_DELETED` + `grace_until < now` → advisory lock(`owner_uid`) → cascade delete → `PURGED`
- Concurrency: 단일 인스턴스, 동시 실행 방지

---

### REM-3-ID-Q5 — Unsubscribe token endpoint: Cloudflare Tunnel 경로

F09: `/unsubscribe` 엔드포인트를 Cloudflare Tunnel로 공개. 인증 없는 public endpoint.

A) **Cloudflare Tunnel + public endpoint(권장)** — 
- Tunnel: `unsubscribe.docsuri.com` → `127.0.0.1:8000/unsubscribe`
- Cloudflare WAF: rate-limit(10 req/min per IP) + bot management
- Endpoint: 인증 불필요, JWT token만 검증
- CSP: `frame-ancestors 'none'`

B) 인증 필요 — unsubscribe는 익명 접근 필요.

C) 기타

[Answer]: AA) **Cloudflare Tunnel + public endpoint(권장)** — 
- Tunnel: `unsubscribe.docsuri.com` → `127.0.0.1:8000/unsubscribe`
- Cloudflare WAF: rate-limit(10 req/min per IP) + bot management
- Endpoint: 인증 불필요, JWT token만 검증
- CSP: `frame-ancestors 'none'`

---

### REM-3-ID-Q5 — Consent/token revocation: Redis pub/sub

R3P: consent/token 철회 시 즉시 전파. Redis pub/sub로 즉시 전파.

A) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- Channel: `revoke:{token_hash}`
- Publisher: 철회 API → `PUBLISH revoke:{token_hash} '{"revoked_at":...}'`
- Subscriber: 모든 worker `SUBSCRIBE revoke:*` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job: 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE: `permission_revoked` event 수신 → 즉시 종료

B) Polling + TTL — 지연 발생.

C) 기타

[Answer]: AA) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- Channel: `revoke:{token_hash}`
- Publisher: 철회 API → `PUBLISH revoke:{token_hash} '{"revoked_at":...}'`
- Subscriber: 모든 worker `SUBSCRIBE revoke:*` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job: 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE: `permission_revoked` event 수신 → 즉시 종료

---

### REM-3-ID-Q6 — Cloudflare WAF + rate-limit: ingress identity 검증

F10/SECURITY-11: Cloudflare WAF에서 client identity 검증 후 BFF 전달.

A) **Cloudflare WAF + BFF 헤더 프록시(권장)** — 
- Cloudflare WAF: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- Rate-limit: Cloudflare에서 IP별/user별 bucket 적용
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket

B) BFF만으로 검증 — Cloudflare 거치지 않고 BFF에서 직접 검증.

C) 기타

[Answer]: AA) **Cloudflare WAF + BFF 헤더 프록시(권장)** — 
- Cloudflare WAF: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- Rate-limit: Cloudflare에서 IP별/user별 bucket 적용
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket


---

### REM-3-ID-Q7 — Backup/restore: purge 대상 포함

RES-2/11/12: 일일 backup에 purge 대상(soft deleted data) 포함. owner purge 시 backup에서도 해당 owner 데이터만 제거.

A) **기존 backup_evidence.py에 purge path 포함(권장)** — 
- `collect`에 `private/userdoc/`, `assets/` 외 `purged/` 경로 추가
- `gc`에 owner별 격리 파기 지원 (`ManagedPath` 마커 활용)
- `--incarnation`으로 new incarnation 복원 검증

B) 별도 backup 스크립트 — 중복 but 격리 명확.

C) 기타

[Answer]: AA) **기존 backup_evidence.py에 purge path 포함(권장)** — 
- `collect`에 `private/userdoc/`, `assets/` 외 `purged/` 경로 추가
- `gc`에 owner별 격리 파기 지원 (`ManagedPath` 마커 활용)
- `--incarnation`으로 new incarnation 복원 검증

---

### REM-3-ID-Q8 — Keychain secret: unsubscribe token signing key

F09: unsubscribe token HS256 서명 키를 Keychain에 저장.

A) **Keychain + launchd worker 접근(권장)** — 
- Keychain: `rem-2-unsubscribe-jwt.keychain-db` (service `docsuri.rem2.unsubscribe`, account `jwt`)
- Owner: `_docsuri_rem2_sign`, ACL로 worker 계정만 접근 허용
- Provisioning: `provision_rem2_keys.py`에 추가
- Runtime: `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽기

B) 환경변수 — 단순하지만 코드/프로세스 리스트 노출 위험.

C) 기타

[Answer]: AA) **Keychain + launchd worker 접근(권장)** — 
- Keychain: `rem-2-unsubscribe-jwt.keychain-db` (service `docsuri.rem2.unsubscribe`, account `jwt`)
- Owner: `_docsuri_rem2_sign`, ACL로 worker 계정만 접근 허용
- Provisioning: `provision_rem2_keys.py`에 추가
- Runtime: `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽기

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-ID-Q1~8에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
