# REM-2 Private Content — Business Rules

**단계**: CONSTRUCTION / REM-2 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `domain-entities.md`, `business-logic-model.md`, FD-Q1~8 승인 (전수 A)

---

## 표기 규칙

| 접두사 | 의미 |
|---|---|
| **BR-PRIV** | Private userdoc 격리/읽기/쓰기 |
| **BR-CACHE** | 번역 cache canonical identity/히트/미스 |
| **BR-JOB** | ContentJob 상태 기계/멱등성/전이 |
| **BR-ASSET** | Asset 발급/전달/서명 URL |
| **BR-AUTHZ** | 권한 재검증/만료/철회 |
| **BR-RL** | Rate-limit/identity |
| **BR-TIMEOUT** | 동기/비동기 임계값/레이어 timeout |
| **BR-CONS** | U11/U12/U13 consumer 계약 |
| **BR-QUEUE** | Queue redelivery/멱등성/DLQ |
| **BR-EVENT** | JobEvent 발행/SSE/replay |

각 규칙은 `ID: 설명` 형식으로 번호 매겨지며, `business-logic-model.md`의 흐름/시나리오와 1:1 추적된다.

---

## 1. Private UserDoc Isolation (BR-PRIV)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-PRIV-01** | `userdoc:` prefix를 가진 모든 경로(`GET /private/userdoc/{docId}`, `POST /private/userdoc`)는 public route(`GET /paper/{id}`)에서 **404로 거부**한다. | FD-Q1, Scenario 1, 9 |
| **BR-PRIV-02** | Non-owner가 `GET /private/userdoc/{docId}` 호출 시 **404 Not Found**를 반환한다(존재 여부 은폐, F01). | FD-Q1, Scenario 9 |
| **BR-PRIV-03** | `POST /private/userdoc` 업로드 시 `owner = caller UID`로 고정한다. client가 owner를 지정할 수 없다. | FD-Q5 |
| **BR-PRIV-04** | Private userdoc은 public corpus(`paperId` namespace)와 **dedup 하지 않는다**. 별도 `userdoc:{owner}:{docId}` key로 저장한다. | FD-Q5 |
| **BR-PRIV-05** | Private userdoc write path는 기존 ingestion 파이프라인(파서/GROBID/DocModel 생성)을 재사용한다. 저장만 `userdoc:` prefix로 분리한다. | FD-Q5 |
| **BR-PRIV-06** | Private userdoc 파싱 실패 시 `ContentJob` 상태를 `FAILED`로 전이하고, `errorType: "parsing_failed"`로 기록한다. | Scenario 1 |
| **BR-PRIV-07** | `PrivateUserDoc.docModel`은 `DocModel` 스키마 검증을 통과한 것만 저장한다. 검증 실패 시 저장 거부. | `domain-entities.md` |

---

## 2. Translation Cache Canonical Identity (BR-CACHE)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-CACHE-01** | 번역 cache key는 **오직** `CanonicalPaperRegistry.resolve(paperId, version)`이 반환하는 `canonical_paper_id`와 `source_tier`로 구성한다. client 제공 `source` 파라미터는 **무시**한다. | FD-Q2, ND-Q1, Scenario 2, 8 |
| **BR-CACHE-02** | `source_tier` 품질 순위는 `ARXIV_HTML` > `SEMANTIC_SCHOLAR_PDF` > `OPENALEX_PDF` > `USER_UPLOAD`로 고정한다. 상위 tier가 존재하면 하위 tier는 cache key에서 배제된다(상위만 hit). | FD-Q2, ND-Q1 |
| **BR-CACHE-03** | Cache hit 시 **동기 HTTP 200**으로 `assetId` 즉시 반환한다. model 실행을 **절대** 하지 않는다(RJ-AC07). | FD-Q2, NFR-Q2, Scenario 2 |
| **BR-CACHE-04** | Cache miss 시 `ContentJobService.submit(task=TRANSLATE, ...)`로 job 접수 후 `202 {jobId}` 반환한다. | FD-Q2, Scenario 3 |
| **BR-CACHE-04** | Cache entry 생성/갱신은 동일 `cacheKey`에 대해 **원자적 치환**한다(멱등). | `domain-entities.md` |
| **BR-CACHE-05** | `persona_hash`는 persona config의 canonical JSON 직렬화 SHA256[:16]로 구성한다. persona 변경 시 별도 cache entry 생성. | `domain-entities.md` |

---

## 3. Content Job State Machine & Idempotency (BR-JOB)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-JOB-01** | 상태 전이는 **순방향만** 허용: `SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED | FAILED | ABSTAINED`. 역전환 불가. | FD-Q6, Scenario 6 |
| **BR-JOB-02** | `SUBMITTED`에서 입력 검증 실패 시 즉시 `FAILED`로 전이한다(큐 진입 전 거부). | FD-Q6 |
| **BR-JOB-03** | `ABSTAINED`는 **정상 terminal 상태**다. 근거 없음(FR-5) 또는 초극단 입력 거절 시 사용한다. `FAILED`와 구분된다. | `domain-entities.md`, Scenario 6 |
| **BR-JOB-04** | 멱등성 키: `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}`. 동일 키 재제출 시 **기존 jobId 반환**(RJ-AC06). | ND-Q6, Scenario 6, 7 |
| **BR-JOB-05** | `attempt`는 1부터 시작, redelivery 시 증가. `effect_ledger(job_id, attempt)` 유니크 인덱스로 중복 차단(ND-Q8). | ND-Q8, Scenario 7 |
| **BR-JOB-06** | 상태 변경 시 `JobEventEmitter`가 `JobEvent{jobId, state, timestamp, payload?}`를 **단 한 번** 발행한다. | ND-Q2, Scenario 6 |
| **BR-JOB-07** | `COMPLETED` 전이 시 `assetId` 필수. `FAILED` 시 `error{errorType, message, retryable, retryAfterSeconds?}` 필수. `ABSTAINED` 시 `abstainReason` 필수. | `domain-entities.md` |
| **BR-JOB-08** | 상태 전이 불가 예외(역전환, 알 수 없는 상태)는 `JobStateMachine`이 예외로 던지고, 호출자는 `FAILED`로 기록한다. | FD-Q6 |

---

## 4. Asset Issuance & Serving (BR-ASSET)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-ASSET-01** | `assetId = "asset:" + sha256(content)[:32]`. 내용 변경 = 새 asset(결정론적). | `domain-entities.md`, Scenario 5 |
| **BR-ASSET-02** | Asset 저장 시 `owner = job.owner`, `license = source material license` 계승(`GENERATED`는 파생물). | `domain-entities.md` |
| **BR-ASSET-03** | `GET /api/v1/assets/{assetId}?token={jwt}` → owner/license/object **재검증** 후 MinIO presigned GET(1분 TTL, `inline` disposition) 생성 → `307 Redirect`. | FD-Q4, ND-Q4, ID-Q7, Scenario 5 |
| **BR-ASSET-04** | Presigned token = HS256 JWT, payload: `{assetId, action="view", nonce, exp=now+60s, sub=caller}`. 1분 TTL, nonce로 재사용 방지(ND-Q7). | ND-Q7, Scenario 5 |
| **BR-ASSET-05** | CSP 헤더: `img-src 'self' http://127.0.0.1:9000` (MinIO internal endpoint만 허용). | ID-Q7, Scenario 5 |
| **BR-ASSET-06** | Asset 조회 시 owner/license/object 권한 **재검증** 후 presigned URL 발급. 권한 없으면 403/404. | ND-Q4, RJ-AC08 |
| **BR-ASSET-07** | MinIO는 **internal network만** 바인딩(`127.0.0.1:9000`). 외부 직접 접근 차단(ID-Q2). | ID-Q2 |

---

## 5. Authorization Recheck (BR-AUTHZ)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-AUTHZ-01** | 잡 파이프라인 **모든 단계**(접수, 큐 진입, 실행 시작, status 조회, event 푸시, asset 전달)에서 `authorize(caller, jobId, action)` 재검증한다(NFR-Q7). | ND-Q5, Scenario 6 |
| **BR-AUTHZ-02** | `AuthorizationService.recheck(jobId, caller, action)`가 DB/캐시에서 권한 확인. 1분 TTL `AuthzCache`로 DB round-trip 최소화(NFR-Q7 p99 ≤ 50ms). | NFR-Q7 |
| **BR-AUTHZ-03** | 권한 만료/철회 시 즉시 잡 상태를 `FAILED`로 전이하고 event `permission_revoked` 발행(RJ-AC11). | NFR-Q7, RJ-AC11, Scenario 6 |
| **BR-AUTHZ-04** | `JobAuthzMiddleware`가 각 단계 진입 시 체인으로 실행. `actions = [SUBMIT, ENQUEUE, EXECUTE, STATUS, EVENT, ASSET]`. | ND-Q5 |
| **BR-AUTHZ-05** | 권한 토큰 = HS256 서명, 1분 TTL. 만료 시 자동 재발급 필요. | `domain-entities.md` |

---

## 6. Rate Limit (BR-RL)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-RL-01** | Client identity별 task type별 토큰 버킷 적용. 인증된 사용자: `user:{uid}`, 익명: `ip:{sha256(ip)[:16]}`. | NFR-Q10, Scenario 10 |
| **BR-RL-02** | Identity 체인: Cloudflare(`CF-Connecting-IP` + 인증 토큰 검증) → BFF(`X-Client-Identity` 헤더) → FastAPI 미들웨어가 identity별 token bucket 적용. | NFR-Q10 |
| **BR-RL-03** | 버킷 초과 시 `429 Too Many Requests` 반환, `retryAfterSeconds` 포함. | Scenario 10 |
| **BR-RL-04** | 동일 identity는 동일 버킷 공유, spoofing 불가(Cloudflare/BFF 검증된 identity만 사용). | NFR-Q10 |

---

## 7. Timeout Alignment (BR-TIMEOUT)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-TIMEOUT-01** | 동기/비동기 분기 임계값: 번역 12k, 요약 8k, novelty 16k, evidence 20k 문자(FD-Q3 A). | FD-Q3, Scenario 4, 5 |
| **BR-TIMEOUT-02** | 레이어별 timeout 역산: 모델 p95 + 여유(2~4초) = 하위 레이어 timeout. 예: 번역 모델 6s → worker 8s → API 10s → BFF 12s → 브라우저 15s. | NFR-Q11, CG-Q4, Scenario 11 |
| **BR-TIMEOUT-03** | 동기 경로는 브라우저 timeout(15~30s) 내 완료 보장. 비동기 경로는 job 접수 후 긴 timeout 적용. | FD-Q3, NFR-Q3 |
| **BR-TIMEOUT-04** | 임계값 초과 입력은 무조건 job 접수(202) → SSE/폴링. 동기 경로로 강제 실행 불가. | FD-Q3 |

---

## 8. Consumer Contracts (BR-CONS)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-CONS-01** | U11(U11 Evidence Agent)은 `EvidenceFormationPort.form_evidence()`만 호출한다. **직접 파싱/근거형성 로직 재구현 금지** (CI static analysis로 차단). | FD-Q8, Scenario 12 |
| **BR-CONS-02** | U12(U12 Novelty Agent)는 `EvidenceFormationPort` 결과 + `SourceRef`만 소비한다. **직접 파싱/근거형성 로직 재구현 금지**. | FD-Q8, Scenario 13 |
| **BR-CONS-03** | U13(Agent Chat Frontend)는 `ContentJobService.submit()`, `subscribeEvents()`, `getAsset()`만 사용한다. `JobStatus` 컴포넌트가 SSE 구독, `AssetViewer`가 presigned URL로 렌더링. | FD-Q8, Scenario 14 |
| **BR-CONS-04** | 공통 계약 타입(`EvidenceItem`, `SourceRef`, `JobEvent`, `AssetId`)은 `docsuri_shared._generated`에서만 import 허용. | FD-Q8 |

---

## 9. Queue Redelivery & Idempotency (BR-QUEUE)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-QUEUE-01** | ElasticMQ queue: `content-job-{task_type}`, DLQ: `content-job-dlq`. visibility timeout 5분, maxReceiveCount 3 후 DLQ 이동(ID-Q3). | ID-Q3 |
| **BR-QUEUE-02** | `effect_ledger(job_id, attempt, effect_type, payload_hash, created_at)` 유니크 인덱스 `(job_id, attempt)`로 중복 차단(ND-Q8). | ND-Q8, Scenario 7 |
| **BR-QUEUE-03** | Worker가 `attempt = MAX(attempt)+1`로 insert 시도 → 충돌 시 skip(멱등). job 완료와 ledger insert는 같은 transaction. | ND-Q8, Scenario 7 |
| **BR-QUEUE-04** | Worker crash 시 다음 redelivery가 `attempt+1`로 재시도. `semaphore.release()`는 `finally` 블록에서 보장. | ID-Q4, Scenario 7 |
| **BR-QUEUE-05** | DLQ 진입 시 운영 경보 발생. 수동 조사 후 재처리 또는 폐기 결정. | ID-Q3 |

---

## 10. Job Event & SSE (BR-EVENT)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-EVENT-01** | 상태 변경 시 `JobEventEmitter`가 `JobEvent{jobId, state, timestamp, payload?}` 단일 발행. 중복 발행 없음. | ND-Q2, BR-JOB-06 |
| **BR-EVENT-02** | SSE endpoint `GET /jobs/{jobId}/events` 제공. `Last-Event-ID` 헤더로 재연결 시 missed event replay(RJ-AC04). | ND-Q2, RJ-AC04, Scenario 6 |
| **BR-EVENT-03** | `COMPLETED` event payload에 `assetId` 포함. `FAILED`에 `error`, `ABSTAINED`에 `abstainReason`. | `domain-entities.md` |
| **BR-EVENT-04** | Event 발행은 상태 전이와 **같은 transaction**에서 수행(또는 outbox 패턴으로 보장). | ND-Q2 |

---

## 11. Cross-Cutting Rules

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-XCUT-01** | 모든 비밀번호/키/토큰은 **Keychain/환경변수**로만 관리. 코드/로그/아카이브에 노출 금지(C-13/C-14, ID-Q8). | ID-Q8 |
| **BR-XCUT-02** | `ContentJobService`는 단일 모듈 + task type 전략 패턴(`TaskExecutor` 인터페이스)로 구현(CG-Q1 A). | CG-Q1 |
| **BR-XCUT-03** | Asset serving은 presigned redirect(`307`) 방식 사용(CG-Q2 A). | CG-Q2 |
| **BR-XCUT-04** | Private userdoc write는 기존 ingestion 파이프라인 재사용(CG-Q3 A). | CG-Q3 |
| **BR-XCUT-05** | Worker 동시성은 `asyncio.Semaphore` + 단일 consumer loop로 제어(CG-Q4 A). | CG-Q4 |
| **BR-XCUT-06** | Property test composite strategy: job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오 조합(CG-Q5 A). | CG-Q5 |
| **BR-XCUT-07** | 모든 외부 호출(MinIO, ElasticMQ, Postgres)은 **timeout + retry + circuit breaker** 적용. | NFR-Q11, RESILIENCY-10 |
| **BR-XCUT-08** | 로그에 토큰/private 본문/내부 키 기록 금지(SEC-12/15, BR-EVENT-03 payload에 secret 없음). | SEC-12/15 |

---

## 12. Traceability: FD Question → Business Rules

| FD Question | Business Rules |
|---|---|
| FD-Q1 (private read) | BR-PRIV-01, BR-PRIV-02 |
| FD-Q2 (cache canonical) | BR-CACHE-01, BR-CACHE-02, BR-CACHE-03 |
| FD-Q3 (timeout branching) | BR-JOB-01 (async path), BR-TIMEOUT-01~04 |
| FD-Q4 (asset serving) | BR-ASSET-01~07 |
| FD-Q5 (userdoc write) | BR-PRIV-03~05 |
| FD-Q6 (job state machine) | BR-JOB-01~08 |
| FD-Q7 (RK/DELIVERY/EDGE/UI/AUTH) | BR-AUTHZ-01~05, BR-RL-01~04, BR-ASSET-03~06, BR-EVENT-01~04 |
| FD-Q8 (consumer contracts) | BR-CONS-01~04 |
