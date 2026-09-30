# REM-3 Lifecycle and Edge Trust — Functional Scenarios (15 Scenarios)

**단계**: CONSTRUCTION / REM-3 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `domain-entities.md`, `business-logic-model.md`, `business-rules.md`, FD-Q1~8 승인 (전수 A)

---

각 시나리오는 **Given/When/Then** 형식으로 기술하며, `business-rules.md`의 규칙 ID와 1:1 추적된다.

---

## Scenario 1: Account Deletion — Soft Delete → Grace Period → Hard Delete

**ID**: SC-ACC-01  
**관련**: FD-Q1, FD-Q4, FD-Q8, BR-PURGE-01~08, BR-PURGE-W-01~07

### Given
- 인증된 사용자 `owner` (UID: `600`)가 세션을 보유함
- 계정에 연관된 데이터: private userdoc 3개, assets 5개, 검색 이력 10건

### When
1. `DELETE /account` 호출 (비밀번호 재인증)
2. 서버가 `PurgeRegistry`에 `SOFT_DELETED` 삽입 (`grace_until = now + 30일`)
3. 계정 비활성화 (`IsHidden=1`, 세션 무효화)
4. 30일 경과 후 `purge_worker` 실행
5. `pg_advisory_xact_lock(owner_uid)` 획득 → cascade delete → MinIO 삭제 → `PURGED` 상태 업데이트

### Then
- 1단계: `200 {state: "SOFT_DELETED", grace_until: now+30d}` 반환
- Grace period 중 `GET /account` → `404` (존재 은폐, BR-PURGE-02)
- Grace period 내 복구 요청 시 `ACTIVE` 복원, `grace_until` 초기화
- 30일 후 `purge_worker` 실행 → cascade delete → MinIO 삭제 → `PURGED` 상태
- 재실행 시 이미 `PURGED` → skip (멱등, BR-PURGE-07)

---

## Scenario 2: Private UserDoc Write → Read (Owner vs Non-Owner)

**ID**: SC-PRIV-01  
**관련**: FD-Q1, FD-Q5, BR-PRIV-01~07

### Given
- 사용자 `owner` (UID: `600`)가 세션 보유
- 업로드할 PDF 파일 (`paper.pdf`, 2.3 MiB)
- Public corpus에 동일 논문 없음

### When
1. `POST /private/userdoc` 호출 (multipart: `file=paper.pdf`)
2. Server: `ContentJobService.submit(task=INGEST_USERDOC)` → job 접수 → `202 {jobId}`
3. Client: `GET /jobs/{jobId}/events` SSE 구독
4. Worker: 파일 파싱 → DocModel 생성 → `userdoc:owner:{docId}` 저장 → `COMPLETED`
5. SSE로 `COMPLETED` 수신 → `GET /private/userdoc/{docId}`로 DocModel 조회

### Then
- `202 {jobId, state: ACCEPTED}` 반환 (RJ-AC01)
- SSE 이벤트 순서 `ACCEPTED → QUEUED → RUNNING → COMPLETED` 수신
- `GET /private/userdoc/{docId}` → `200 DocModel`, `docModel.owner == owner`
- `GET /paper/{docId}` (public route) → `404` (BR-PRIV-01)
- Non-owner `GET /private/userdoc/{docId}` → `404` (존재 은폐, BR-PRIV-02)

---

## Scenario 3: Translation Cache Hit (Canonical Identity Binding)

**ID**: SC-CACHE-01  
**관련**: FD-Q2, BR-CACHE-01~05, NFR-Q2, NFR-Q8

### Given
- 논문 `arxiv:2301.12345` v1이 public corpus에 존재, `source_tier = ARXIV_HTML`
- 한국어 번역 cache entry 기존 존재:
  - `cacheKey = "translate:arxiv:2301.12345:1:ARXIV_HTML:ko:persona_hash_a1b2"`
  - `assetId = "asset:sha256_abc123..."`
- 사용자 `owner`가 세션 보유, 동일한 persona config 사용

### When
`POST /translate` 호출: `{paperId: "arxiv:2301.12345", version: 1, targetLang: "ko", persona: {...}, source: "client_provided_source"}`

### Then
- 서버가 `CanonicalPaperRegistry.resolve("arxiv:2301.12345", 1)` → `canonicalId="arxiv:2301.12345"`, `sourceTier=ARXIV_HTML` 확정 (BR-CACHE-01)
- Client 제공 `source` 파라미터 **무시** (BR-CACHE-01)
- Cache key `translate:arxiv:2301.12345:1:ARXIV_HTML:ko:persona_hash_a1b2`로 lookup → **HIT**
- **동기 HTTP 200** 반환: `{assetId: "asset:sha256_abc123...", source: "cache"}` (BR-CACHE-03)
- 모델 실행 **안 함** (RJ-AC07, BR-CACHE-03)
- 응답 시간 ≤ 200ms (NFR-Q2)

---

## Scenario 4: Translation Cache Miss → Async Job → Completion

**ID**: SC-CACHE-02  
**관련**: FD-Q2, FD-Q3, BR-CACHE-04, BR-JOB-01~08, BR-TIMEOUT-01~04

### Given
- 논문 `semantic:987654321` v2가 corpus에 존재, `source_tier = SEMANTIC_SCHOLAR_PDF`
- 동일 persona/언어로 번역 cache **미존재**
- 입력 문자 수 15,000자 → 번역 임계값(12k) 초과 → 비동기 경로 분기 (BR-TIMEOUT-01)

### When
1. `POST /translate` 호출: `{paperId: "semantic:987654321", version: 2, targetLang: "ko", persona: {...}}`
2. Server: `CanonicalPaperRegistry.resolve()` → `canonicalId="semantic:987654321"`, `sourceTier=SEMANTIC_SCHOLAR_PDF`
3. Cache lookup → **MISS**
4. 입력 문자 수 15,000 > 12,000(번역 임계값) → `should_use_async() = true`
5. `ContentJobService.submit(task=TRANSLATE, ...)` → `202 {jobId}` 반환
6. Client: `GET /jobs/{jobId}/events` SSE 구독
7. Worker 실행 → 번역 완료 → `assetId` 발급 → `COMPLETED` 전이
8. SSE로 `COMPLETED` 이벤트 수신 → `GET /api/v1/assets/{assetId}?token={jwt}`로 결과 조회

### Then
- 1~5단계: `202 {jobId, state: ACCEPTED}` 반환 (RJ-AC01)
- 6단계: SSE 이벤트 순서 `ACCEPTED → QUEUED → RUNNING → COMPLETED` 수신 (BR-EVENT-01~03)
- 7단계: `COMPLETED` event payload에 `assetId` 포함 (BR-EVENT-03)
- 8단계: `GET /api/v1/assets/{assetId}?token={jwt}` → `307 Redirect` to presigned URL → MinIO 직접 다운로드 (BR-ASSET-03~04)
- 전체 비동기 경로 소요 시간 ≤ 번역 p95(6s) + 여유 = worker 8s 내 완료 (BR-TIMEOUT-02)

---

## Scenario 5: Sync Generation (Below Threshold)

**ID**: SC-JOB-01  
**관련**: FD-Q3, BR-TIMEOUT-01, BR-TIMEOUT-03

### Given
- 사용자 `owner`가 요약 요청: 입력 문자 수 5,000자 (요약 임계값 8,000자 이하)
- 논문 `arxiv:2301.12345` v1, `source_tier = ARXIV_HTML`

### When
`POST /summarize` 호출: `{paperId: "arxiv:2301.12345", version: 1, persona: "expert"}`

### Then
- `should_use_async(5000, SUMMARIZE) = false` → **동기 경로** 실행
- 브라우저 timeout(15s) 내 **직접 200 반환** (결과 JSON 포함)
- Job 접수/큐/이벤트 과정 **없음** (동기 경로)
- 응답 시간 ≤ 8초 (브라우저 timeout 15s 내 완료, BR-TIMEOUT-03)

---

## Scenario 5: Asset Serving via Presigned URL

**ID**: SC-ASSET-01  
**관련**: FD-Q4, BR-ASSET-01~07, ND-Q4, ND-Q7, ID-Q7

### Given
- Job `job-123` 완료, `assetId = "asset:sha256_abc123..."` 발급
- Asset content: 한국어 번역본 JSON, `license = ARXIV`
- Asset 저장 위치: `MinIO assets/asset:sha256_abc123...`
- 사용자 `owner`가 세션 보유, asset 접근 권한 있음

### When
`GET /api/v1/assets/asset:sha256_abc123...?token={jwt}` 호출 (JWT payload: `{assetId, action="view", nonce, exp=now+60s, sub="owner"}`)

### Then
1. 서버가 `AssetService`로 owner/license/object 권한 재검증 → 허용 (BR-ASSET-06)
2. MinIO presigned GET 생성: 1분 TTL, `response-content-disposition: inline` (BR-ASSET-04)
3. `307 Redirect` 반환, `Location: https://127.0.0.1:9000/assets/asset%3Asha256_abc123...?X-Amz-Signature=...`
4. 브라우저가 MinIO(`127.0.0.1:9000`)에서 직접 다운로드 (BFF 대역폭 절약)
5. CSP 헤더: `img-src 'self' http://127.0.0.1:9000` (BR-ASSET-05)
6. 토큰 1분 후 만료 → 재사용 시 `403` (BR-ASSET-04)

---

## Scenario 7: Job Authz Recheck — Permission Revoked Mid-Execution

**ID**: SC-AUTHZ-01  
**관련**: BR-AUTHZ-01~05, NFR-Q7, RJ-AC11

### Given
- Job `job-456` (task=TRANSLATE) 상태 `QUEUED`
- Owner `owner`가 세션 보유, 초기 권한 유효
- Queue에서 메시지 수신 전 `owner`의 계정이 비활성화됨 (권한 철회)

### When
1. Worker가 queue에서 메시지 수신 → `semaphore.acquire()` → 상태 `RUNNING` 전이 시도
2. `JobAuthzMiddleware`가 실행 직전 `authorize(caller=owner, jobId, EXECUTE)` 재검증 (BR-AUTHZ-01)
3. 권한 철회 감지 → 즉시 잡 상태 `FAILED` 전이
4. `error = {errorType: "permission_revoked", message: "Caller permission revoked", retryable: false}` 설정
5. `JobEventEmitter`가 `FAILED` event 발행 (payload에 `error` 포함)

### Then
- 잡 상태 `FAILED`로 전이 (RUNNING 도달 전 차단)
- `FAILED` event SSE로 푸시: `state=FAILED, payload={error: {...}}` (BR-EVENT-03)
- Client SSE 수신 → `FAILED` 상태 표시, 재시도 버튼 비활성화 (`retryable: false`)
- `permission_revoked` event 별도 발행 (RJ-AC11)

---

## Scenario 8: Translation Cache Hit — Client Source Ignored

**ID**: SC-CACHE-03  
**관련**: FD-Q2, BR-CACHE-01, BR-CACHE-03, NFR-Q8

### Given
- Scenario 3과 동일 조건: cache hit 기조건 성립
- Client가 악의적으로 `source: "fake_source_override"` 파라미터 전송

### When
`POST /translate` 호출 시 `source: "fake_source_override"` 포함

### Then
- 서버가 `CanonicalPaperRegistry.resolve()`로 canonical identity 확정 (BR-CACHE-01)
- Client 제공 `source` 파라미터 **완전히 무시** — cache key 구성에 사용 안 함 (BR-CACHE-01)
- Cache hit → 동기 200 반환, 모델 미실행 (BR-CACHE-03)
- 응답에 `source: "cache"` 포함, client source 반영 안 됨

---

## Scenario 9: Queue Redelivery Idempotency (Worker Crash)

**ID**: SC-QUEUE-01  
**관련**: BR-QUEUE-01~04, ND-Q8, BR-QUEUE-02~03

### Given
- Job `job-789` (task=SUMMARIZE) 상태 `RUNNING`, `attempt=1`
- Worker가 실행 중 `attempt=1`로 `effect_ledger` insert 시도 → 성공
- 번역 실행 중 Worker 프로세스 crash (OOM kill)
- ElasticMQ visibility timeout(5분) 만료 → 메시지 redelivery

### When
1. 새 Worker가 동일 메시지 수신 → `attempt=2`로 `effect_ledger` insert 시도
2. `effect_ledger(job_id, attempt)` 유니크 인덱스 충돌 → insert 실패 (BR-QUEUE-02)
3. Worker가 충돌 감지 → **기존 ledger 행 존재 확인** → 작업 skip
4. 기존 `COMPLETED` 상태(첫 attempt에서 이미 완료됨) 확인 → 중복 실행 안 함
4. Job 상태 이미 `COMPLETED` → 중복 event 발행 안 함

### Then
- `effect_ledger`에 `job-789, attempt=1` 행만 존재 (중복 0개, BR-QUEUE-02)
- 잡 상태 `COMPLETED` 유지, 추가 실행 없음
- Client에게 중복 결과 전달 안 함 (RJ-AC06 멱등성)

---

## Scenario 10: Rate Limit Enforcement

**ID**: SC-RL-01  
**관련**: BR-RL-01~04, NFR-Q10

### Given
- 익명 사용자(IP `203.0.113.42`)가 번역 API 급속 호출
- Task type `TRANSLATE` 버킷: `maxTokens=10`, `refillRate=2/sec`
- 현재 토큰 0개 (버킷 소진)

### When
동일 IP에서 `POST /translate` 5회 연속 호출 (1초 간격)

### Then
- 처음 2회: 토큰 리필로 성공 (`202` 또는 동기 `200`)
- 3~5회: 토큰 부족 → `429 Too Many Requests` 반환 (BR-RL-03)
- 응답 헤더: `Retry-After: 1` (초 단위 재시도 힌트)
- 동일 IP(identity) 버킷 공유, spoofing 불가 (BR-RL-04)
- 인증된 사용자(`user:{uid}`)는 별도 버킷, IP와 격리 (BR-RL-01)

---

## Scenario 11: Timeout Alignment — Sync Path Completes Within Browser Timeout

**ID**: SC-TIMEOUT-01  
**관련**: BR-TIMEOUT-01~04, NFR-Q3, NFR-Q11

### Given
- 번역 요청: 입력 10,000자 (임계값 12k 이하 → 동기 경로)
- 모델 p95 latency: 6초
- Layer timeout 역산: 모델 6s → worker 8s → API 10s → BFF 12s → 브라우저 15s (BR-TIMEOUT-02)

### When
`POST /translate` 동기 호출 (10,000자 입력)

### Then
- 모델 실행 5.8초 만에 완료 (p95 내)
- Worker 7.2초, API 9.1초, BFF 11.3초, 브라우저 14.1초에 응답 수신
- **브라우저 timeout(15s) 내 완료** (BR-TIMEOUT-03)
- 어떤 레이어도 timeout으로 잘리지 않음 (역산 여유 2~4초 작동)

---

## Scenario 12: U11 Evidence Agent → Content Job (Consumer Contract)

**ID**: SC-CONS-01  
**관련**: BR-CONS-01, FD-Q8, Scenario 12

### Given
- U11 Evidence Agent가 사용자 질문 `"diffusion models for protein structure prediction"` 수신
- 대상 논문 집합: `[arxiv:2301.12345, semantic:987654321]`
- 첨부 파일: 없음

### When
U11 Agent가 `EvidenceFormationPort.form_evidence(question, papers, attachments)` 호출

### Then
- U11 내부에서 `ContentJobService.submit(task=EVIDENCE, input={question, paper_ids, attachments})` 호출
- **직접 파싱/근거형성 로직 재구현 없음** (BR-CONS-01)
- Job 접수 → SSE로 진행 수신 → 완료 시 `EvidenceResult` 반환
- 결과 계약: `EvidenceResult{items: [EvidenceItem{statement, supporting[], conflicting[]}]}`

---

## Scenario 13: U12 Novelty Agent → Content Job (Consumer Contract)

**ID**: SC-CONS-02  
**관련**: BR-CONS-02, FD-Q8, Scenario 13

### Given
- U12 Novelty Agent가 사용자 연구 의도 `"novel approaches to federated learning"` 수신
- 업로드 원고: `manuscript.pdf` (첨부)

### When
U12 Agent가 `ContentJobService.submit(task=NOVELTY, input={intent, manuscript, evidence_result})` 호출

### Then
- U12 내부에서 `ContentJobService.submit(task=NOVELTY, ...)`만 호출
- **직접 파싱/근거형성 로직 재구현 없음** (BR-CONS-02)
- Upstream `EvidenceFormationPort` 결과 + `SourceRef`만 소비
- Job 완료 시 `NoveltyResult{similar_works[], ideas[], risks[]}` 반환

---

## Scenario 14: U13 Frontend SSE Status + Asset Viewer

**ID**: SC-CONS-03  
**관련**: BR-CONS-03, FD-Q8, Scenario 14

### Given
- 사용자가 `/agent` 페이지에서 `novelty` mode 선택, 연구 의도 입력, `제출` 클릭
- Frontend가 `ContentJobService.submit()` → `jobId` 수신

### When
1. `JobStatus` 컴포넌트가 `subscribeEvents(jobId)`로 SSE 구독
2. 이벤트 수신 순서: `ACCEPTED → QUEUED → RUNNING → COMPLETED`
3. `COMPLETED` 수신 시 `assetId` 추출 → `AssetViewer`가 `getAsset(assetId)` 호출
4. `AssetViewer`가 presigned URL로 이미지/자산 렌더링

### Then
- 상태 표시: `접수됨(ACCEPTED) → 대기중(QUEUED) → 처리중(RUNNING) → 완료(COMPLETED)` 순차 업데이트
- `COMPLETED` 시 `AssetViewer`가 presigned URL로 번역본/요약본/novelty 결과 렌더링
- 재연결 시 `Last-Event-ID`로 missed event replay (RJ-AC04)
- 에러 시 `FAILED`/`ABSTAINED` 상태별 비기술적 메시지 표시 (BR-CONS-03, BR-EVENT-03)

---

## Scenario 15: Queue Loss / Worker Crash / Partial Deploy Recovery (RJ-AC12)

**ID**: SC-QUEUE-02  
**관련**: BR-QUEUE-01~05, RJ-AC12, RESILIENCY-14

### Given
- ElasticMQ queue에 `job-A`, `job-B`, `job-C` 대기 중
- Worker 1이 `job-A` 처리 중 crash
- Worker 2가 `job-B` 처리 중 deploy로 재시작 (graceful shutdown 30초 내 완료)
- ElasticMQ broker 재시작 (partial deploy)

### When
1. `job-A`: Worker 1 crash → visibility timeout 만료 → redelivery → Worker 3가 수신 → `attempt=2`로 실행 → 완료
2. `job-B`: Worker 2 graceful shutdown 시 `semaphore.release()` → 메시지 requeue → Worker 3가 수신 → 완료
3. `job-C`: broker 재시작 시 메시지 지속성 보장(ElasticMQ persistence) → 재시작 후 delivery → 완료

### Then
- **중복 효과 0개**: `effect_ledger` 유니크 인덱스로 중복 차단 (BR-QUEUE-02)
- **상태 정확 복구**: 모든 job 최종 상태 `COMPLETED` (RJ-AC12)
- **Accepted job 재조정 완료**: crash/shutdown된 job 모두 재처리 또는 확정적 terminal 상태 도달
- **Asset 전달 중복 0개**: 각 assetId 단일 발급 (BR-ASSET-01 결정론적)
- Health/readiness: broker 재시작 후 `deep readiness`가 실제 의존 장애 반영 (RJ-AC12)

---

## Traceability Matrix

| Scenario | FD Question | Business Rules | NFR/ND/ID/CG Ref |
|---|---|---|---|
| SC-ACC-01 | FD-Q1, FD-Q4, FD-Q8 | BR-PURGE-01~08 | - |
| SC-PRIV-01 | FD-Q1, FD-Q5 | BR-PRIV-01~07 | - |
| SC-CACHE-01 | FD-Q2 | BR-CACHE-01~05 | NFR-Q2, NFR-Q8 |
| SC-CACHE-02 | FD-Q2, FD-Q3 | BR-CACHE-04, BR-JOB-01~08, BR-TIMEOUT-01~04 | NFR-Q3 |
| SC-JOB-01 | FD-Q3 | BR-TIMEOUT-01, BR-TIMEOUT-03 | NFR-Q3 |
| SC-ASSET-01 | FD-Q4 | BR-ASSET-01~07 | ND-Q4, ND-Q7, ID-Q7 |
| SC-AUTHZ-01 | FD-Q7 | BR-AUTHZ-01~05 | NFR-Q7, RJ-AC11 |
| SC-CACHE-03 | FD-Q2 | BR-CACHE-01, BR-CACHE-03 | NFR-Q8 |
| SC-QUEUE-01 | FD-Q6, FD-Q7 | BR-QUEUE-01~04 | ND-Q8, BR-QUEUE-02~03 |
| SC-RL-01 | FD-Q3 | BR-RL-01~04 | NFR-Q10 |
| SC-TIMEOUT-01 | FD-Q3 | BR-TIMEOUT-01~04 | NFR-Q3, NFR-Q11 |
| SC-CONS-01 | FD-Q8 | BR-CONS-01 | - |
| SC-CONS-02 | FD-Q8 | BR-CONS-02 | - |
| SC-CONS-03 | FD-Q8 | BR-CONS-03 | - |
| SC-QUEUE-02 | FD-Q6, FD-Q7 | BR-QUEUE-01~05 | RJ-AC12, RESILIENCY-14 |
