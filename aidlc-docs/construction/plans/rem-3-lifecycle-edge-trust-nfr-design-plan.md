# REM-3 Lifecycle and Edge Trust — NFR Design 계획

**단계**: CONSTRUCTION / REM-3 NFR Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- NFR Requirements (NFR-Q1~13 승인 대기)
- Functional Design (FD-Q1~8 승인 대기)
- REM-1/2 런타임: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance
- `verification-remediation-2026-09-18.md` Security/Resiliency/PBT 확장

**목표**: REM-3 Lifecycle and Edge Trust의 NFR Design 패턴·구체 구현 방안을 확정하고, 10개 결정 질문(REM-3-ND-Q1~10)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1/2 런타임 기반: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance
- Security Full, PBT Full, Resiliency custom(`RESILIENCY-08` 면제) 계승
- REM-1/2 contracts(`shared/dtos`, `shared/ports`, `shared/vector-spec`) 동결·공급
- `RESILIENCY-08` 면제(단일 Mac), full corpus rebuild 별도 승인

---

## 분해 질문 (Decomposition Questions)

### REM-3-ND-Q1 — Purge registry 스키마 + 멱등 purge worker

NFR-Q1/Q4: `purge_registry` 테이블 스키마와 `purge_worker` 구현. soft delete → grace period → hard delete 멱등 처리.

A) **PostgreSQL 테이블 + advisory lock + 멱등 worker(권장)** — 
```sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL,  -- ACTIVE, SOFT_DELETED, PURGED
    requested_at     TIMESTAMPTZ NOT NULL,
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,  -- optimistic locking
    CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED'))
);
```
`purge_worker`: advisory lock(`pg_advisory_xact_lock`)로 동시 실행 방지 → `SOFT_DELETED` + `grace_until < now` 조회 → `pg_advisory_lock`로 개별 owner 락 → cascade delete 실행 → `PURGED` 업데이트. 멱등: 이미 `PURGED`면 skip. 재시도 안전.

B) 단일 트랜잭션 — 동시성/재시도 처리 복잡.

C) 기타

[Answer]: AA) **PostgreSQL 테이블 + advisory lock + 멱등 worker(권장)** — 
```sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL,  -- ACTIVE, SOFT_DELETED, PURGED
    requested_at     TIMESTAMPTZ NOT NULL,
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,  -- optimistic locking
    CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED'))
);

---

### REM-3-ND-Q2 — Unsubscribe token: HS256 JWT + Redis cache

NFR-Q2/Q5: unsubscribe token 검증 경로. HS256 JWT verify(로컬) + Redis cache로 token→job_id 매핑.

A) **HS256 JWT + Redis cache(권장)** — 
- Token: `JWT(payload={email, purpose="unsubscribe", exp}, HS256_key)` 
- 검증: 로컬 `jwt.decode`(~1ms) → Redis `GET unsubscribe:{token}` → job_id 반환
- Cache miss 시 DB lookup → Redis SETEX(24h)
- `unsubscribe` endpoint: `GET /unsubscribe?token=<jwt>` → 검증 후 job 접수

B) Opaque token + DB only — 단순하지만 latency 높음.

C) 기타

[Answer]: AA) **HS256 JWT + Redis cache(권장)** — 
- Token: `JWT(payload={email, purpose="unsubscribe", exp}, HS256_key)` 
- 검증: 로컬 `jwt.decode`(~1ms) → Redis `GET unsubscribe:{token}` → job_id 반환
- Cache miss 시 DB lookup → Redis SETEX(24h)
- `unsubscribe` endpoint: `GET /unsubscribe?token=<jwt>` → 검증 후 job 접수

---

### REM-3-ND-Q3 — Rate-limit identity 체인: Cloudflare → BFF → FastAPI

NFR-Q3/Q7: Cloudflare → BFF → FastAPI identity 체인 구현.

A) **헤더 체인 + 미들웨어(권장)** — 
- Cloudflare: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket
- Identity 형식: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`

B) Cookie/session 기반 — 단순하지만 stateless 아님.

C) 기타

[Answer]: AA) **헤더 체인 + 미들웨어(권장)** — 
- Cloudflare: `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정
- BFF: `X-Client-Identity` 헤더 검증 → FastAPI에 `X-Client-Identity` 프록시
- FastAPI: `RateLimitMiddleware`가 헤더 파싱 → identity별 token bucket
- Identity 형식: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`

---

### REM-3-ND-Q4 — Purge worker throughput: 배치 + advisory lock

NFR-Q4: `purge_worker` 초당 ≥ 100 owners 처리. DB bulk delete + MinIO bulk delete + audit log 비동기.

A) **배치 + advisory lock + 비동기 audit(권장)** — 
- `pg_advisory_xact_lock(owner_uid)`로 개별 owner 락
- `DELETE FROM table WHERE owner_uid = $1` bulk delete
- MinIO `mc rm --recursive` 병렬 삭제
- Audit log: `COPY TO` 또는 비동기 producer로 비동기 기록
- 동시 실행 방지: `pg_advisory_xact_lock(hashtext('purge_worker'))`

B) 단일 스레드 순차 — 단순하지만 throughput 낮음.

C) 기타

[Answer]: AA) **배치 + advisory lock + 비동기 audit(권장)** — 
- `pg_advisory_xact_lock(owner_uid)`로 개별 owner 락
- `DELETE FROM table WHERE owner_uid = $1` bulk delete
- MinIO `mc rm --recursive` 병렬 삭제
- Audit log: `COPY TO` 또는 비동기 producer로 비동기 기록
- 동시 실행 방지: `pg_advisory_xact_lock(hashtext('purge_worker'))`


---

### REM-3-ND-Q5 — Consent/token revocation propagation: Redis pub/sub

NFR-Q5: consent/token 철회(revoke) 후 즉시 전파. Redis pub/sub로 revocation event 발행 → 모든 worker 즉시 cache invalidation.

A) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- `REVOKE` 채널: `{"token_hash": "...", "revoked_at": timestamp}`
- 모든 worker가 `SUBSCRIBE REVOKE` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE 연결은 `permission_revoked` event 수신 → 즉시 종료

B) Polling — 지연 발생.

C) 기타

[Answer]: AA) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- `REVOKE` 채널: `{"token_hash": "...", "revoked_at": timestamp}`
- 모든 worker가 `SUBSCRIBE REVOKE` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE 연결은 `permission_revoked` event 수신 → 즉시 종료


---

### REM-3-ND-Q6 — Authz recheck middleware: 모든 단계 재검증

NFR-Q6: job 파이프라인 모든 단계에서 `authorize(caller, object, action)` 재검증. p99 ≤ 50ms.

A) **단일 `AuthzMiddleware` 체인 + 1분 TTL 캐시(권장)** — 
- `JobAuthzMiddleware`가 각 단계(접수, 큐 진입, 실행, status, event, asset) 진입 시 실행
- `AuthzCache`(1분 TTL, key=`{caller}:{job_id}:{action}`)로 DB round-trip 최소화
- 권한 만료 시 즉시 `FAILED` + event `permission_revoked` 발행 (RJ-AC11)
- `actions = [SUBMIT, ENQUEUE, EXECUTE, STATUS, EVENT, ASSET]`

B) 각 단계별 개별 미들웨어 — 중복 코드 but 명확한 분리.

C) 기타

[Answer]: AA) **단일 `AuthzMiddleware` 체인 + 1분 TTL 캐시(권장)** — 
- `JobAuthzMiddleware`가 각 단계(접수, 큐 진입, 실행, status, event, asset) 진입 시 실행
- `AuthzCache`(1분 TTL, key=`{caller}:{job_id}:{action}`)로 DB round-trip 최소화
- 권한 만료 시 즉시 `FAILED` + event `permission_revoked` 발행 (RJ-AC11)
- `actions = [SUBMIT, ENQUEUE, EXECUTE, STATUS, EVENT, ASSET]`

---

### REM-3-ND-Q7 — Dependency audit 격리: purge/unsubscribe 전용 lockfile

NFR-Q6: purge/unsubscribe path에서 사용하는 dependency 별도 lockfile로 격리. CI에서 audit 강제.

A) **별도 lockfile + CI gate(권장)** — 
- `requirements-purge.txt`, `package-purge.json` 별도 관리
- PR CI에서 `pip-audit` + `npm audit` + `grype` scan 실패 시 merge 차단
- 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록

B) 기존 lockfile 공유 — 단순하지만 audit noise 증가.

C) 기타

[Answer]: AA) **별도 lockfile + CI gate(권장)** — 
- `requirements-purge.txt`, `package-purge.json` 별도 관리
- PR CI에서 `pip-audit` + `npm audit` + `grype` scan 실패 시 merge 차단
- 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록


---

### REM-3-ND-Q8 — Property test composite strategy: purge/unsubscribe 불변식

PBT Full: job 상태 기계, cache 멱등성, authz 재검증, queue redelivery에 대한 property test.

A) **Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오(권장)** — 
- `job_input_strategy = st.builds(JobInput, task_type=st.sampled_from(types), ...)`
- `state_transition_strategy = st.sampled_from(valid_transitions + invalid_transitions)`
- `authz_scenario = st.sampled_from([valid, expired, revoked, missing])`
- `queue_scenario = st.sampled_from([normal, redelivery, crash, dlq])`
이들을 `st.tuples`로 조합해 동시 검증. shrinking 유지, CI seed `20260930` 고정.

B) 각 property 별도 전략 — 조합 미검증.

C) 기타

[Answer]: AA) **Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오(권장)** — 
- `job_input_strategy = st.builds(JobInput, task_type=st.sampled_from(types), ...)`
- `state_transition_strategy = st.sampled_from(valid_transitions + invalid_transitions)`
- `authz_scenario = st.sampled_from([valid, expired, revoked, missing])`
- `queue_scenario = st.sampled_from([normal, redelivery, crash, dlq])`
이들을 `st.tuples`로 조합해 동시 검증. shrinking 유지, CI seed `20260930` 고정.


---

### REM-3-ND-Q9 — Observability: purge/unsubscribe 메트릭 + 경보

NFR-Q13: 8 핵심 지표 + 경보를 구조화 JSON 로그로 출력.

A) **구조화 JSON + 8지표(권장)** — 
1. `purge_requested_total` (rate) — 급증 > 10x baseline for 2m
2. `purge_completed/failed_total` — 실패율 > 5% for 5m
3. `purge_queue_depth` — > 1000 for 2m
4. `purge_latency_p95_seconds` — p95 > 3600s for 10m
5. `unsubscribe_verification_p95_ms` — p99 > 100ms for 5m
5. `unsubscribe_rate_total` — 급증 경보
6. `revocation_propagation_latency_p95` — > 5초 경보
7. `authz_recheck_failures_total` — > 0 즉시

JSON lines stdout 출력, Prometheus 수집.

C) 기타

[Answer]: AA) **구조화 JSON + 8지표(권장)** — 
1. `purge_requested_total` (rate) — 급증 > 10x baseline for 2m
2. `purge_completed/failed_total` — 실패율 > 5% for 5m
3. `purge_queue_depth` — > 1000 for 2m
4. `purge_latency_p95_seconds` — p95 > 3600s for 10m
5. `unsubscribe_verification_p95_ms` — p99 > 100ms for 5m
5. `unsubscribe_rate_total` — 급증 경보
6. `revocation_propagation_latency_p95` — > 5초 경보
7. `authz_recheck_failures_total` — > 0 즉시

---

### REM-3-ND-Q10 — Consent/token revocation: 즉시 cache invalidation

NFR-Q5/R3P: consent/token 철회 시 즉시 cache invalidation. Redis pub/sub로 즉시 전파.

A) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- `REVOKE` 채널: `{"token_hash": "...", "revoked_at": timestamp}`
- 모든 worker가 `SUBSCRIBE REVOKE` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE 연결은 `permission_revoked` event 수신 → 즉시 종료

B) Polling — 지연 발생.

C) 기타

[Answer]: AA) **Redis pub/sub + 즉시 cache invalidation(권장)** — 
- `REVOKE` 채널: `{"token_hash": "...", "revoked_at": timestamp}`
- 모든 worker가 `SUBSCRIBE REVOKE` → 수신 즉시 로컬 cache `DEL`
- 진행 중 job은 다음 `authz_recheck`에서 감지 → 즉시 `FAILED`
- 진행 중 SSE 연결은 `permission_revoked` event 수신 → 즉시 종료

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-ND-Q1~10에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
