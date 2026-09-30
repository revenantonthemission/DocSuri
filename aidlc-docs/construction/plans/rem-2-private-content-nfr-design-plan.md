# REM-2 Private Content — NFR Design 계획

**단계**: CONSTRUCTION / REM-2 NFR Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- REM-2 Functional Design (FD-Q1~8)
- REM-2 NFR Requirements (NFR-Q1~13)
- REM-1 런타임: clock(±118ms), mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance
- `requirements.md` NFR-P1~7, NFR-R1~4, NFR-C1, NFR-M1/M2, NFR-O1
- `verification-remediation-2026-09-18.md` Security/Resiliency/PBT 확장

**목표**: REM-2 Private Content의 NFR Design 패턴·구체 구현 방안을 확정하고, 10개 결정 질문(REM-2-ND-Q1~10)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1 런타임 기반(clock, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance) 고정.
- Security Full, PBT Full, Resiliency custom(RESILIENCY-08 면제) 계승.
- REM-1 versioned 계약 동결·공급.
- `RESILIENCY-08` 면제(단일 Mac), 나머지는 적용.

---

## 분해 질문 (Decomposition Questions)

### REM-2-ND-Q1 — Cache key canonical identity binding 구현 패턴

NFR-Q8: cache key에 **canonical source identity(content version)** 필수 포함. 번역 cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. client-provided source 무시.

A) **서비스 계층에서 canonical lookup → key 구성(권장)** — `TranslationCacheService.lookup(paperId, version, sourceTier, targetLang, persona)`가 내부적으로 `CanonicalPaperRegistry.resolve(paperId, version)` 호출해 `canonical_paper_id` 확정 후 key 구성. client source 파라미터는 무시. Registry는 `arxiv:{id}`, `semantic:{id}`, `openalex:{id}`, `userdoc:{owner}:{docId}`를 동일 인터페이스로 정규화.

B) Controller에서 canonical lookup 후 service에 key 전달 — controller 책임 증가.

C) 기타

[Answer]: AA) **서비스 계층에서 canonical lookup → key 구성(권장)** — `TranslationCacheService.lookup(paperId, version, sourceTier, targetLang, persona)`가 내부적으로 `CanonicalPaperRegistry.resolve(paperId, version)` 호출해 `canonical_paper_id` 확정 후 key 구성. client source 파라미터는 무시. Registry는 `arxiv:{id}`, `semantic:{id}`, `openalex:{id}`, `userdoc:{owner}:{docId}`를 동일 인터페이스로 정규화.

---

### REM-2-ND-Q2 — Job 상태 기계 + event/subscription 구현 패턴

NFR-Q4/RJ-AC04: job 상태(`submitted → accepted → queued → running → completed/failed/abstained`) 변경 시 **SSE event 푸시**, status query는 REST로 queued/completed만. 재연결 시 마지막 event부터 replay.

A) **JobEventEmitter + SSE endpoint(권장)** — `JobEventEmitter`가 상태 변경 시 `JobEvent{jobId, state, timestamp, payload?}` 발행. BFF의 `GET /jobs/{jobId}/events`가 SSE 스트림으로 구독. `Last-Event-ID` 헤더로 재연결 시 missed event replay. 상태 기계는 `JobStateMachine` 클래스로 중앙화, invalid transition 거부.

B) Polling-only — SSE 미구현, 클라이언트 주기적 폴링. 구현 단순하나 latency·대역폭 비효율.

C) 기타

[Answer]: AA) **JobEventEmitter + SSE endpoint(권장)** — `JobEventEmitter`가 상태 변경 시 `JobEvent{jobId, state, timestamp, payload?}` 발행. BFF의 `GET /jobs/{jobId}/events`가 SSE 스트림으로 구독. `Last-Event-ID` 헤더로 재연결 시 missed event replay. 상태 기계는 `JobStateMachine` 클래스로 중앙화, invalid transition 거부.


---

### REM-2-ND-Q3 — Cache hit 동기 반환 + assetId 발급 패턴

NFR-Q2: cache hit 시 **동기 HTTP 200 반환(assetId 포함)**, model 미실행(RJ-AC07). asset 전달은 별도 same-origin GET(RJ-AC08).

A) **Cache hit → 즉시 200 + assetId, miss → job 접수(권장)** — `TranslationController.translate()`가 cache 조회 → hit 시 `200 {assetId, source: "cache"}` 즉시 반환. miss 시 `JobService.submit()`로 job 접수 → `202 {jobId}` 반환. client는 assetId가 있으면 `GET /api/assets/{assetId}`로 결과 수신, jobId면 SSE/폴링으로 완료 대기.

B) Cache hit도 job으로 접수해 즉시 completed — 구현 단순화 but 접수 오버헤드.

C) 기타

[Answer]: AA) **Cache hit → 즉시 200 + assetId, miss → job 접수(권장)** — `TranslationController.translate()`가 cache 조회 → hit 시 `200 {assetId, source: "cache"}` 즉시 반환. miss 시 `JobService.submit()`로 job 접수 → `202 {jobId}` 반환. client는 assetId가 있으면 `GET /api/assets/{assetId}`로 결과 수신, jobId면 SSE/폴링으로 완료 대기.


---

### REM-2-ND-Q4 — Private asset serving: same-origin endpoint + 서명 URL

NFR-Q4/F07: `GET /api/assets/{assetId}?token={signed}`에서 owner/license/object 재검증 후 MinIO presigned GET(1분 TTL) redirect 또는 proxy stream. CSP `img-src 'self'` 허용.

A) **Presigned redirect(권장)** — `GET /api/v1/assets/{assetId}?token={jwt}`가 owner/license/object 재검증 → MinIO presigned GET(1분 TTL, `response-content-disposition: inline`) 생성 → `307 Redirect` to presigned URL. 브라우저가 MinIO에서 직접 다운로드. 토큰은 HS256 서명, 1분 TTL, `assetId`, `action=view`, `nonce` 포함. CSP `img-src 'self' https://minio.internal` 허용.

B) BFF proxy stream — BFF가 MinIO에서 스트리밍. 대역폭 소모 but 토큰 검증 단순화.

C) 기타

[Answer]: AA) **Presigned redirect(권장)** — `GET /api/v1/assets/{assetId}?token={jwt}`가 owner/license/object 재검증 → MinIO presigned GET(1분 TTL, `response-content-disposition: inline`) 생성 → `307 Redirect` to presigned URL. 브라우저가 MinIO에서 직접 다운로드. 토큰은 HS256 서명, 1분 TTL, `assetId`, `action=view`, `nonce` 포함. CSP `img-src 'self' https://minio.internal` 허용.

---

### REM-2-ND-Q5 — Job pipeline 권한 재검증 미들웨어 체인

NFR-Q7: job 접수·큐 진입·실행 시작·status 조회·event 푸시·asset 전달 **모든 단계**에서 `authorize(caller, object, action)` 재검증. p99 ≤ 50ms. 권한 만료 시 즉시 `failed` + event `permission_revoked`.

A) **단일 `JobAuthzMiddleware` 체인(권장)** — `JobAuthzMiddleware`가 request context에서 `caller`, `jobId`, `action` 추출 → `AuthorizationService.recheck(jobId, caller, action)` 호출. 캐시된 권한 토큰(`AuthzCache`)로 DB round-trip 최소화(1분 TTL). 실패 시 즉시 `failed` + event `permission_revoked` 발행. 각 단계(접수, 큐 진입, 실행, status, event, asset) 진입 시 체인 실행.

B) 각 단계별 개별 미들웨어 — 중복 코드 but 명확한 분리.

C) 기타

[Answer]: AA) **단일 `JobAuthzMiddleware` 체인(권장)** — `JobAuthzMiddleware`가 request context에서 `caller`, `jobId`, `action` 추출 → `AuthorizationService.recheck(jobId, caller, action)` 호출. 캐시된 권한 토큰(`AuthzCache`)로 DB round-trip 최소화(1분 TTL). 실패 시 즉시 `failed` + event `permission_revoked` 발행. 각 단계(접수, 큐 진입, 실행, status, event, asset) 진입 시 체인 실행.

---

### REM-2-ND-Q6 — Job 상태 기계 + cache hit/miss 멱등성 구현

NFR-Q12/PBT-03/04: job 상태 기계(`submitted → accepted → queued → running → completed/failed/abstained`) + cache hit/miss 멱등성. cache hit 시 동기 반환, miss 시 job 접수. `canonical_paper_id` + `task_type` + `input_hash`로 멱등성 키 구성. 동일 멱등성 키 재제출 시 기존 job 반환(RJ-AC06).

A) **멱등성 키 = `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}`(권장)** — `JobService.submit()`이 멱등성 키로 기존 job 조회 → 존재 시 기존 jobId 반환(RJ-AC06). cache hit은 별도 경로(ND-Q3)로 즉시 반환하므로 멱등성 키는 miss 경로만 적용. `abstained` terminal 상태 포함.

B) 단순 UUID — 멱등성 미보장.

C) 기타

[Answer]: AA) **멱등성 키 = `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}`(권장)** — `JobService.submit()`이 멱등성 키로 기존 job 조회 → 존재 시 기존 jobId 반환(RJ-AC06). cache hit은 별도 경로(ND-Q3)로 즉시 반환하므로 멱등성 키는 miss 경로만 적용. `abstained` terminal 상태 포함.

---

### REM-2-ND-Q7 — AssetId 발급 + same-origin asset endpoint + CSP

ND-Q4 이어짐: assetId 발급 포맷, 서명 토큰 구성, CSP 설정.

A) **assetId = `asset:{sha256(content)}`, 토큰 = HS256 JWT(권장)** — asset 저장 시 `assetId = "asset:" + sha256(content)[:32]` 발급. 토큰 = `jwt.encode({assetId, action: "view", nonce: uuid4(), exp: now+60s}, ASSET_JWT_SECRET, HS256)`. CSP: `Content-Security-Policy: img-src 'self' https://minio.internal; script-src 'self'; connect-src 'self' wss://api.docsuri.com`. MinIO는 internal network만 허용, 외부 직접 접근 차단.

B) assetId = UUID, 토큰 = opaque random string — 구현 단순 but audit 어려움.

C) 기타

[Answer]: AA) **assetId = `asset:{sha256(content)}`, 토큰 = HS256 JWT(권장)** — asset 저장 시 `assetId = "asset:" + sha256(content)[:32]` 발급. 토큰 = `jwt.encode({assetId, action: "view", nonce: uuid4(), exp: now+60s}, ASSET_JWT_SECRET, HS256)`. CSP: `Content-Security-Policy: img-src 'self' https://minio.internal; script-src 'self'; connect-src 'self' wss://api.docsuri.com`. MinIO는 internal network만 허용, 외부 직접 접근 차단.

---

### REM-2-ND-Q8 — Queue redelivery 멱등성 + 중복 효과 방지

NFR-Q11/RESILIENCY-14: ElasticMQ redelivery, worker crash 시 **중복 효과 부재**. `effect_ledger`에 `(jobId, attempt)` 유니크 키로 중복 차단. job 완료 시 `effect_ledger` 행 기록(atomic with job completion). redelivery 시 기존 행 존재하면 skip.

A) **Effect ledger + attempt counter(권장)** — `effect_ledger(job_id, attempt, effect_type, payload_hash, created_at)` 유니크 인덱스 `(job_id, attempt)`. worker가 `attempt = MAX(attempt)+1`로 insert 시도 → 충돌 시 skip. job 완료와 ledger insert는 같은 transaction. worker crash 시 다음 redelivery가 `attempt+1`로 재시도.

B) 단순 `job.completed` 플래그만 — race condition 가능.

C) 기타

[Answer]: AA) **Effect ledger + attempt counter(권장)** — `effect_ledger(job_id, attempt, effect_type, payload_hash, created_at)` 유니크 인덱스 `(job_id, attempt)`. worker가 `attempt = MAX(attempt)+1`로 insert 시도 → 충돌 시 skip. job 완료와 ledger insert는 같은 transaction. worker crash 시 다음 redelivery가 `attempt+1`로 재시도.

---

### REM-2-ND-Q9 — Property test 명세: job 상태 기계·cache·authz·queue

NFR-Q12/PBT-03/04/07/08: 
- job 상태 기계 불변식: `submitted → accepted → queued → running → completed|failed|abstained`, 역전환 불가, terminal 상태 불변
- cache hit/miss 멱등성: 동일 멱등성 키 → 동일 결과(assetId 또는 jobId)
- authz 재검증: 권한 만료 시 즉시 terminal `failed` + event 발행
- queue redelivery 멱등성: 동일 `jobId` + `attempt` 중복 차단

A) **Python Hypothesis + TS fast-check 병행(권장)** — Python: `test_job_state_machine_property.py`(상태 전이 불변식), `test_cache_idempotent_property.py`(멱등성 키 → 동일 결과), `test_authz_recheck_property.py`(권한 만료 → failed), `test_queue_redelivery_property.py`(redelivery 중복 차단). TS: `test_job_event_order_property.ts`(event 순서 보장), `test_asset_delivery_property.ts`(assetId → presigned URL). CI seed `20260930` 고정, shrinking 유지.

B) Python만 — TS 경로 커버리지 부족.

C) 기타

[Answer]: AA) **Python Hypothesis + TS fast-check 병행(권장)** — Python: `test_job_state_machine_property.py`(상태 전이 불변식), `test_cache_idempotent_property.py`(멱등성 키 → 동일 결과), `test_authz_recheck_property.py`(권한 만료 → failed), `test_queue_redelivery_property.py`(redelivery 중복 차단). TS: `test_job_event_order_property.ts`(event 순서 보장), `test_asset_delivery_property.ts`(assetId → presigned URL). CI seed `20260930` 고정, shrinking 유지.

---

### REM-2-ND-Q10 — 운영 메트릭·경보 대시보드 스펙

NFR-Q13: 8지표 + 경보를 구조화 JSON 로그로 stdout 출력. CloudWatch/로컬 파일 수집.

A) **구조화 JSON + 8지표(권장)** — 각 job event/asset delivery 시 `{"metric": "job_accepted_total", "labels": {"task_type": "translate"}, "value": 1, "timestamp": "..."}` JSON 라인 출력. Prometheus node exporter가 수집. 경보 규칙: 
1. `job_failed_rate > 0.05` for 5m
2. `job_queue_depth > 1000` for 2m
3. `job_latency_p95 > 300s` for 10m
4. `asset_delivery_p95 > 10s` for 5m
5. `cache_hit_ratio < 0.3` for 15m
6. `queue_redelivery_rate > 0.01` for 5m
7. `authz_recheck_failures > 0` 즉시
8. `job_accepted_rate` 급증(> 10x baseline) for 2m

C) 기타

[Answer]: AA) **구조화 JSON + 8지표(권장)** — 각 job event/asset delivery 시 `{"metric": "job_accepted_total", "labels": {"task_type": "translate"}, "value": 1, "timestamp": "..."}` JSON 라인 출력. Prometheus node exporter가 수집. 경보 규칙: 
1. `job_failed_rate > 0.05` for 5m
2. `job_queue_depth > 1000` for 2m
3. `job_latency_p95 > 300s` for 10m
4. `asset_delivery_p95 > 10s` for 5m
5. `cache_hit_ratio < 0.3` for 15m
6. `queue_redelivery_rate > 0.01` for 5m
7. `authz_recheck_failures > 0` 즉시
8. `job_accepted_rate` 급증(> 10x baseline) for 2m

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-2-ND-Q1~10에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
