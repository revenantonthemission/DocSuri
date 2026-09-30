# REM-3 Lifecycle and Edge Trust — Business Rules

**단계**: CONSTRUCTION / REM-3 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `domain-entities.md`, `business-logic-model.md`, FD-Q1~8 승인 (전수 A)

---

## 표기 규칙

| 접두사 | 의미 |
|---|---|
| **BR-PURGE** | Purge lifecycle (soft delete → grace → hard delete) |
| **BR-UNSUB** | Unsubscribe token 발급/검증/소비 |
| **BR-RL** | Rate-limit identity 체인 |
| **BR-CONSENT** | Consent/token lifecycle |
| **BR-REV** | Revocation 전파 |
| **BR-EDGE** | Edge trust (ingress identity, spoofing 방지) |
| **BR-ACC** | Account lifecycle |
| **BR-PURGE-W** | Purge worker 구현 |

각 규칙은 `ID: 설명` 형식으로 번호 매겨지며, `business-logic-model.md`의 흐름/시나리오와 1:1 추적된다.

---

## 1. Purge Lifecycle Rules (BR-PURGE)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-PURGE-01** | 계정 삭제 요청 시 즉시 `SOFT_DELETED` 상태로 전이, `grace_until = now + 30일` 설정. | FD-Q1, FD-Q4 |
| **BR-PURGE-02** | `grace_until` 경과 전까지 계정 복구 가능. 복구 시 `ACTIVE`로 복원, `grace_until` 초기화. | FD-Q1, FD-Q4 |
| **BR-PURGE-03** | `grace_until` 경과 후 `purge_worker`가 영구 파기 실행. `pg_advisory_xact_lock`으로 동시 실행 방지. | FD-Q1, FD-Q4 |
| **BR-PURGE-03** | 파기 순서: DB cascade delete → MinIO 객체 삭제 → Backup gc → `PURGED` 상태 업데이트. | FD-Q1 |
| **BR-PURGE-05** | `purge_registry` 테이블에 `owner_uid` PK, `status`, `requested_at`, `grace_until`, `purged_at`, `version` 저장. | FD-Q4 |
| **BR-PURGE-06** | `pg_advisory_xact_lock(owner_uid)`로 개별 owner 락, `pg_advisory_xact_lock('purge_worker')`로 전역 락. | FD-Q4 |
| **BR-PURGE-07** | 재실행 멱등: 이미 `PURGED` 상태면 skip. `version` optimistic locking으로 동시 수정 방지. | FD-Q4 |
| **BR-PURGE-08** | `PURGED` 도달 시 복구 불가. 백업에서도 `gc --apply --approve-critical`로 별도 승인 후 파기. | FD-Q4 |

---

## 2. Unsubscribe Token Rules (BR-UNSUB)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-UNSUB-01** | Unsubscribe token은 HS256 JWT로 발급. payload: `{email, purpose="unsubscribe", exp: now+24h, iat}`. | FD-Q2 |
| **BR-UNSUB-02** | Client 제공 `source` 파라미터 무시. 서버가 canonical identity로만 검증. | FD-Q2, BR-CACHE-01 |
| **BR-UNSUB-03** | Token 검증: 로컬 `jwt.decode` → `exp` 확인 → Redis `GET unsubscribe:{token_hash}` → job_id 반환. | FD-Q2, NFR-Q2 |
| **BR-UNSUB-04** | Cache hit 시 동기 200 반환 (job_id), model 미실행. Cache miss 시 job 접수 (202). | NFR-Q2 |
| **BR-UNSUB-05** | Token 1회용: 검증 후 Redis에서 즉시 `DEL`. 재사용 시 `400` 반환. | FD-Q2 |
| **BR-UNSUB-05** | 만료/철회/위조 토큰은 각각 `401`/`410`/`400` 반환, 상세 사유 노출 안 함. | FD-Q2 |

---

## 3. Rate-Limit Identity Chain Rules (BR-RL)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-RL-01** | Cloudflare에서 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 설정. | FD-Q3, FD-Q6 |
| **BR-RL-02** | BFF는 `X-Client-Identity` 헤더만 프록시, 검증하지 않음. | FD-Q3, FD-Q6 |
| **BR-RL-03** | FastAPI `RateLimitMiddleware`가 `X-Client-Identity` 파싱 → identity별 token bucket. | FD-Q3, FD-Q6 |
| **BR-RL-04** | Identity 형식: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`. 동일 identity 동일 버킷. | FD-Q3, NFR-Q10 |
| **BR-RL-05** | Task type별 독립 버킷 (translate, summarize, novelty, evidence, unsubscribe). | NFR-Q5 |
| **BR-RL-06** | 버킷 초과 시 `429 Too Many Requests` + `Retry-After` 헤더. | NFR-Q10 |

---

## 3. Job State Machine & Idempotency (BR-JOB)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-JOB-01** | 상태 전이: `SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED | FAILED | ABSTAINED`. 역전환 불가. | FD-Q6 |
| **BR-JOB-02** | 멱등성 키: `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}`. 동일 키 재제출 시 기존 `jobId` 반환 (RJ-AC06). | ND-Q6 |
| **BR-JOB-03** | `attempt` 1부터 시작, redelivery 시 증가. `effect_ledger(job_id, attempt)` PK로 중복 차단. | ND-Q8 |
| **BR-JOB-05** | 상태 변경 시 `JobEventEmitter`가 `JobEvent` 단일 발행. Outbox 패턴으로 replay 지원. | ND-Q2 |

---

## 4. Cache Canonical Identity (BR-CACHE)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-CACHE-01** | 번역 cache key = `translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. | FD-Q2, NFR-Q8 |
| **BR-CACHE-02** | `canonical_paper_id`는 오직 `CanonicalPaperRegistry.resolve()`로만 확정. Client source 무시. | FD-Q2, NFR-Q8 |
| **BR-CACHE-03** | `source_tier` 순위: `ARXIV_HTML` > `SEMANTIC_SCHOLAR_PDF` > `OPENALEX_PDF` > `USER_UPLOAD`. | FD-Q2 |
| **BR-CACHE-03** | Cache hit 시 동기 200 반환 (`assetId`), model 미실행 (RJ-AC07). | NFR-Q2 |
| **BR-CACHE-04** | Cache miss 시 job 접수 → `202 {jobId}` 반환. | FD-Q2 |

---

## 4. Asset Serving (BR-ASSET)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-ASSET-01** | `assetId = "asset:" + sha256(content)[:32]`. 내용 변경 = 새 asset. | FD-Q4 |
| **BR-ASSET-03** | `GET /assets/{assetId}?token` → owner/license/object 재검증 → MinIO presigned GET(1분 TTL) → `307 Redirect`. | FD-Q4, ID-Q7 |
| **BR-ASSET-04** | Presigned token = HS256 JWT, payload `{assetId, action, nonce, exp=now+60s, sub}`. 1분 TTL. | ND-Q7 |
| **BR-ASSET-05** | CSP: `img-src 'self' http://127.0.0.1:9000`. MinIO internal only. | ID-Q7 |

---

## 5. Authorization Recheck (BR-AUTHZ)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-AUTHZ-01** | Job 파이프라인 **모든 단계**(접수, 큐 진입, 실행, status, event, asset)에서 `authorize(caller, jobId, action)` 재검증. | NFR-Q7 |
| **BR-AUTHZ-02** | `AuthzCache` 1분 TTL, key=`{caller}:{job_id}:{action}` → `(allowed, expires_at)`. p99 ≤ 50ms. | NFR-Q7 |
| **BR-AUTHZ-03** | 권한 만료/철회 시 즉시 `FAILED` + event `permission_revoked` 발행 (RJ-AC11). | NFR-Q7, RJ-AC11 |
| **BR-AUTHZ-04** | `JobAuthzMiddleware` 체인으로 각 단계 진입 시 실행. | ND-Q5 |

---

## 4. Rate Limit (BR-RL)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-RL-01** | Client identity별 task type별 토큰 버킷. 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`. | NFR-Q10 |
| **BR-RL-02** | Identity 체인: Cloudflare(`CF-Connecting-IP` + 토큰 검증) → BFF(`X-Client-Identity`) → FastAPI token bucket. | NFR-Q10 |
| **BR-RL-03** | 버킷 초과 시 `429 Too Many Requests` + `Retry-After` 헤더. | Scenario 10 |

---

## 5. Timeout Alignment (BR-TIMEOUT)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-TIMEOUT-01** | 동기/비동기 분기 임계값: 번역 12k, 요약 8k, novelty 16k, evidence 20k 문자. | FD-Q3, Scenario 4, 5 |
| **BR-TIMEOUT-02** | 레이어별 timeout 역산: 모델 p95 + 여유(2~4초) = 하위 레이어 timeout. 예: 번역 모델 6s → worker 8s → API 10s → BFF 12s → 브라우저 15s. | NFR-Q11, CG-Q4, Scenario 11 |
| **BR-TIMEOUT-03** | 동기 경로는 브라우저 timeout(15~30s) 내 완료 보장. 비동기 경로는 job 접수 후 긴 timeout 적용. | FD-Q3, NFR-Q3 |

---

## 5. Consumer Contracts (BR-CONS)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-CONS-01** | U11(U11 Evidence Agent)은 `EvidenceFormationPort.form_evidence()`만 호출. **직접 파싱/근거형성 로직 재구현 금지** (CI static analysis로 차단). | FD-Q8, Scenario 12 |
| **BR-CONS-02** | U12(U12 Novelty Agent)는 `EvidenceFormationPort` 결과 + `SourceRef`만 소비. **직접 파싱/근거형성 로직 재구현 금지**. | FD-Q8, Scenario 13 |
| **BR-CONS-03** | U13(Agent Chat Frontend)는 `ContentJobService.submit()`, `subscribeEvents()`, `getAsset()`만 사용. `JobStatus`가 SSE 구독, `AssetViewer`가 presigned URL로 렌더링. | FD-Q8, Scenario 14 |
| **BR-CONS-04** | 공통 계약 타입(`EvidenceItem`, `SourceRef`, `JobEvent`, `AssetId`)은 `docsuri_shared._generated`에서만 import 허용. | FD-Q8 |

---

## 6. Queue Redelivery & Idempotency (BR-QUEUE)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-QUEUE-01** | ElasticMQ queue: `content-job-{task_type}`, DLQ: `content-job-dlq`. visibility timeout 5분, maxReceiveCount 3 후 DLQ 이동. | ID-Q3 |
| **BR-QUEUE-02** | `effect_ledger(job_id, attempt, effect_type, payload_hash, created_at)` 유니크 인덱스 `(job_id, attempt)`로 중복 차단. | ND-Q8, Scenario 7 |
| **BR-QUEUE-03** | Worker가 `attempt = MAX(attempt)+1`로 insert 시도 → 충돌 시 skip(멱등). job 완료와 ledger insert는 같은 transaction. | ND-Q8, Scenario 7 |
| **BR-QUEUE-04** | Worker crash 시 다음 redelivery가 `attempt+1`로 재시도. `semaphore.release()`는 `finally` 블록에서 보장. | ID-Q4, Scenario 7 |
| **BR-QUEUE-05** | DLQ 진입 시 운영 경보 발생. 수동 조사 후 재처리 또는 폐기 결정. | ID-Q3 |

---

## 6. Job Event & SSE (BR-EVENT)

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-EVENT-01** | 상태 변경 시 `JobEventEmitter`가 `JobEvent{jobId, state, timestamp, payload?}` 단일 발행. 중복 발행 없음. | ND-Q2, BR-JOB-06 |
| **BR-EVENT-02** | SSE endpoint `GET /jobs/{jobId}/events` 제공. `Last-Event-ID` 헤더로 재연결 시 missed event replay (RJ-AC04). | ND-Q2, RJ-AC04, Scenario 6 |
| **BR-EVENT-03** | `COMPLETED` event payload에 `assetId` 포함. `FAILED`에 `error`, `ABSTAINED`에 `abstainReason`. | `domain-entities.md` |
| **BR-EVENT-04** | Event 발행은 상태 전이와 **같은 transaction**에서 수행 (outbox 패턴). | ND-Q2 |

---

## 6. Cross-Cutting Rules

| ID | 규칙 | 추적 |
|---|---|---|
| **BR-XCUT-01** | 모든 비밀번호/키/토큰은 **Keychain/환경변수**로만 관리. 코드/로그/아카이브에 노출 금지 (C-13/C-14, ID-Q8). | ID-Q8 |
| **BR-XCUT-02** | `ContentJobService`는 단일 모듈 + task type 전략 패턴(`TaskExecutor` 인터페이스)로 구현 (CG-Q1 A). | CG-Q1 |
| **BR-XCUT-03** | Asset serving은 presigned redirect(`307`) 방식 사용 (CG-Q2 A). | CG-Q2 |
| **BR-XCUT-04** | Private userdoc write는 기존 ingestion 파이프라인 재사용 (CG-Q3 A). | CG-Q3 |
| **BR-XCUT-05** | Worker 동시성은 `asyncio.Semaphore` + 단일 consumer loop로 제어 (CG-Q4 A). | CG-Q4 |
| **BR-XCUT-06** | Property test composite strategy: job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오 조합 (CG-Q5 A). | CG-Q5 |
| **BR-XCUT-07** | 모든 외부 호출(MinIO, ElasticMQ, Postgres)은 **timeout + retry + circuit breaker** 적용. | NFR-Q11, RESILIENCY-10 |
| **BR-XCUT-07** | 로그에 토큰/private 본문/내부 키 기록 금지 (SEC-12/15, BR-EVENT-03 payload에 secret 없음). | SEC-12/15 |

---

## 12. Traceability: FD Question → Business Rules

| FD Question | Business Rules |
|---|---|
| FD-Q1 (purge) | BR-PURGE-01~08 |
| FD-Q2 (unsubscribe) | BR-UNSUB-01~05 |
| FD-Q3 (rate-limit) | BR-RL-01~06, BR-TIMEOUT-01~04 |
| FD-Q4 (purge lifecycle) | BR-PURGE-01~08 |
| FD-Q5 (consent/revocation) | BR-CONSENT-01~04, BR-REV-01~04 |
| FD-Q6 (edge trust) | BR-RL-01~06, BR-AUTHZ-01~04, BR-ASSET-03~06 |
| FD-Q7 (이관 경로) | BR-CACHE-01~04, BR-AUTHZ-01~04, BR-ASSET-03~06, BR-RL-01~06 |
| FD-Q8 (account lifecycle) | BR-ACC-01~04, BR-PURGE-01~08 |
