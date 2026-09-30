# REM-2 Private Content — Code Generation 계획

**단계**: CONSTRUCTION / REM-2 Code Generation (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- REM-2 Functional Design (FD-Q1~8, 승인 대기)
- REM-2 NFR Requirements (NFR-Q1~13, 승인 대기)
- REM-2 NFR Design (ND-Q1~10, 승인 대기)
- REM-2 Infrastructure Design (ID-Q1~8, 승인 대기)
- REM-1 완료 산출물: `platform_integrity/`, `ops/platform-integrity/`, `shared/`, launchd installer, receipt signer, keychain, clock, mTLS, backup/restore, load acceptance

**목표**: REM-2 Private Content의 Code Generation 상세 체크리스트를 작성하고, 5개 결정 질문(REM-2-CG-Q1~5)에 대한 답변을 수집해 Generation Part 2 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1 `platform_integrity/`, `ops/platform-integrity/`, `shared/` 산출물 고정 공급.
- Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2/psycopg, async/await, Ruff, pytest, Hypothesis.
- TypeScript/Next.js 14, React 18, fast-check, Vitest, Playwright.
- Security Full, PBT Full, Resiliency custom(`RESILIENCY-08` 면제).
- `RESILIENCY-08` 면제(단일 Mac), full corpus rebuild 별도 승인.

---

## 생성 체크리스트 (Part 2 승인 후 실행)

### 1. Private userdoc read/write 경로
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/filesystem.py`에 `UserDocReader`/`UserDocWriter` 추가
  - `read(userdoc_id: str, owner: str) -> DocModel | None` — owner 검증 후 반환, non-owner는 `None`(존재 은폐)
  - `write(owner: str, doc_model: DocModel) -> str` — `userdoc:{owner}:{docId}` key로 저장, dedup 없음
- [ ] `platform_integrity/src/docsuri_platform_integrity/api/app.py`에 전용 route 추가
  - `GET /private/userdoc/{doc_id}` — owner 검증 후 DocModel 반환 (FD-Q1)
  - `POST /private/userdoc` — 업로드 접수 → job 발행 → `202 {jobId}` (FD-Q5)
  - `GET /private/userdoc/{doc_id}/asset/{asset_id}` — asset 서빙 (ND-Q4)

### 2. Translation cache canonical identity binding
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/cache.py`에 `TranslationCache` 확장
  - `key = f"translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}"` (NFR-Q8, ND-Q1)
  - `CanonicalPaperRegistry.resolve(paper_id, version) -> canonical_paper_id` 구현
  - `source_tier` enum: `ARXIV_HTML`, `SEMANTIC_SCHOLAR_PDF`, `OPENALEX_PDF`, `USER_UPLOAD`
  - client-provided source 파라미터 무시, server-verified canonical identity만 사용 (NFR-Q8)

### 3. Content job pipeline + 상태 기계 + SSE event
- [ ] `ops/platform-integrity/content_job_service.py` 신규
  - `JobService.submit(task_type, input, idempotency_key) -> jobId` — 멱등성 키로 기존 job 조회/반환 (ND-Q6)
  - `JobStateMachine` — `submitted → accepted → queued → running → completed/failed/abstained` 전이 검증
  - `JobEventEmitter` — 상태 변경 시 `JobEvent{jobId, state, timestamp, payload?}` 발행 (ND-Q2)
- [ ] `ops/platform-integrity/job_queue.py` — ElasticMQ 연동 (ID-Q3)
  - queue: `content-job-{task_type}` (translate, summarize, novelty, evidence)
  - DLQ: `content-job-dlq`, visibility timeout 5분, maxReceiveCount 3
  - 메시지: `{jobId, taskType, input, idempotencyKey, attempt, createdAt}`

### 4. Worker 구현 (4종)
- [ ] `ops/platform-integrity/workers/translate_worker.py` — 번역 job 처리, cache hit 시 즉시 completed (ND-Q3)
- [ ] `ops/platform-integrity/workers/summarize_worker.py` — 요약 job, map-reduce for 긴 본문
- [ ] `ops/platform-integrity/workers/novelty_worker.py` — novelty job, evidence agent 결과 소비
- [ ] `ops/platform-integrity/workers/evidence_worker.py` — evidence formation job
- 각 worker: `semaphore`로 동시성 상한(ID-Q4), `attempt` 기반 멱등성(ND-Q8), `effect_ledger` 기록

### 5. Asset serving + presigned URL + CSP
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/assets.py` 신규
  - `AssetService.issue_presigned(asset_id, caller, action) -> presigned_url` — owner/license/object 재검증 → MinIO presigned GET(1분 TTL) (ND-Q4, ND-Q7)
  - `assetId = "asset:" + sha256(content)[:32]`, 토큰 = HS256 JWT(1분 TTL, nonce 포함) (ND-Q7)
- [ ] `platform_integrity/src/docsuri_platform_integrity/api/app.py`에 asset endpoint 추가
  - `GET /api/v1/assets/{asset_id}?token={jwt}` → owner/license/object 재검증 → `307 Redirect` to presigned URL (ND-Q4)
  - CSP header: `img-src 'self' http://127.0.0.1:9000` (ID-Q7)

### 6. Authorization 재검증 미들웨어 체인
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/authz.py`에 `JobAuthzMiddleware` 추가
  - 각 단계(접수, 큐 진입, 실행, status, event, asset) 진입 시 `authorize(caller, jobId, action)` 재검증 (ND-Q5)
  - `AuthzCache` 1분 TTL로 DB round-trip 최소화 (NFR-Q7)
  - 권한 만료 시 즉시 `failed` + event `permission_revoked` 발행 (NFR-Q7, RJ-AC11)

### 7. Rate-limit: client identity 기반
- [ ] `platform_integrity/src/docsuri_platform_integrity/adapters/ratelimit.py` 신규
  - `X-Client-Identity` 헤더 파싱 → identity별 token bucket (NFR-Q10)
  - Cloudflare → BFF → FastAPI identity 체인 구현

### 7. Timeout 정렬: browser → BFF → API → model → worker
- [ ] `ops/platform-integrity/timeouts.yaml` 신규 (NFR-Q11)
  - task type별 동기 경로 timeout 역산표 정의 (NFR-Q10)

### 8. Private userdoc write path (ingestion 재사용)
- [ ] `ops/platform-integrity/provision_userdoc.py` 신규 (FD-Q5)
  - `POST /private/userdoc` → job 발행 → DocModel 생성 → `userdoc:{owner}:{docId}` 저장
  - public corpus와 dedup 안 함 (사용자 private)
  - 실패 시 `abstained` 반환

### 9. Launchd service 등록 (4개 worker)
- [ ] `ops/platform-integrity/provision_content_workers.py` 신규 (ID-Q6)
  - `rem-2-content-translate`, `rem-2-content-summarize`, `rem-2-content-novelty`, `rem-2-content-evidence` launchd plist 생성
  - `UserName`=`_docsuri_rem2_worker`, `GroupName`=`_docsuri_rem2_worker`, `InitGroups=false`, `Umask=0o077`
  - `WorkingDirectory`=/Library/Application Support/DocSuri/rem-2/workers/{type}
  - 로그 분리, `ProcessType=Background`, `ThrottleInterval=5`, `ExitTimeOut=30`

### 10. Secret/Key 관리 (Keychain 패턴 재사용)
- [ ] `ops/platform-integrity/provision_rem2_keys.py` 신규 (ID-Q8)
  - Asset JWT secret, ElasticMQ creds, MinIO keys를 Keychain에 저장
  - `provision_receipts.py` 패턴으로 root provisioner가 생성·ACL 설정
  - 런타임은 `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽기

### 10. Backup/restore: private path 포함
- [ ] `ops/platform-integrity/backup_evidence.py` 수정 (ID-Q5)
  - `collect`에 `private/userdoc/`, `assets/` 추가
  - `gc`에 owner별 격리 복원/파기 지원 (`ManagedPath` 마커 활용)

### 11. Property tests (PBT Full)
- [ ] `platform_integrity/tests/test_job_state_machine_property.py` — 상태 전이 불변식
- [ ] `platform_integrity/tests/test_cache_idempotent_property.py` — 멱등성 키 → 동일 결과
- [ ] `platform_integrity/tests/test_authz_recheck_property.py` — 권한 만료 → failed
- [ ] `platform_integrity/tests/test_queue_redelivery_property.py` — redelivery 중복 차단
- [ ] `ops/tests/test_job_event_order_property.py` — event 순서 보장
- [ ] `ops/tests/test_asset_delivery_property.py` — assetId → presigned URL
- CI seed `20260930` 고정, Hypothesis/fast-check shrinking 유지

### 12. Integration tests
- [ ] `platform_integrity/tests/test_private_userdoc_read.py` — owner/non-owner read 격리
- [ ] `platform_integrity/tests/test_translation_cache_canonical.py` — canonical identity binding
- [ ] `ops/tests/test_content_job_pipeline.py` — 제출→수락→큐→실행→완료/실패/기권
- [ ] `ops/tests/test_asset_serving.py` — presigned URL 발급/전달/만료
- [ ] `ops/tests/test_job_authz_recheck.py` — 권한 만료 시 즉시 failed
- [ ] `ops/tests/test_queue_redelivery_idempotent.py` — worker crash 시 멱등성

### 13. Frontend: job status SSE + asset 소비
- [ ] `frontend/lib/api/contentJobApi.ts` — `submit()`, `subscribeEvents()`, `getAsset()`
- [ ] `frontend/components/JobStatus.tsx` — SSE 구독, 상태 표시(submitted/accepted/queued/running/completed/failed/abstained)
- [ ] `frontend/components/AssetViewer.tsx` — presigned URL로 이미지/자산 렌더링

---

## 분해 질문 (Decomposition Questions)

### REM-2-CG-Q1 — Content job service: 단일 모듈 vs task type별 별도 모듈

4개 task type(translate, summarize, novelty, evidence)의 job 처리 로직을 어떻게 구성할까?

A) **단일 `ContentJobService` + task type 전략 패턴(권장)** — `ContentJobService`가 공통 파이프라인(접수, 멱등성, 큐 발행, 상태 기계, event 발행) 담당. task type별 실행 로직만 `TaskExecutor` 인터페이스로 분리(`TranslateExecutor`, `SummarizeExecutor`, `NoveltyExecutor`, `EvidenceExecutor`). 공통 코드 중복 최소화.

B) 4개 독립 서비스 — 각 task type마다 완전 독립 모듈. 중복 코드 발생 but 격리 명확.

C) 기타

[Answer]: AA) **단일 `ContentJobService` + task type 전략 패턴(권장)** — `ContentJobService`가 공통 파이프라인(접수, 멱등성, 큐 발행, 상태 기계, event 발행) 담당. task type별 실행 로직만 `TaskExecutor` 인터페이스로 분리(`TranslateExecutor`, `SummarizeExecutor`, `NoveltyExecutor`, `EvidenceExecutor`). 공통 코드 중복 최소화.

---

### REM-2-CG-Q2 — Asset serving: BFF redirect vs proxy stream

ND-Q4/ID-Q7: asset 전달 방식. BFF가 presigned URL 생성 후 `307 Redirect` vs BFF가 MinIO에서 스트리밍 프록시.

A) **Presigned redirect(권장)** — BFF가 owner/license/object 재검증 후 MinIO presigned GET(1분 TTL) 생성 → `307 Redirect`. 브라우저가 MinIO에서 직접 다운로드. BFF 대역폭 절약, CSP `img-src 'self' http://127.0.0.1:9000`로 허용.

B) Proxy stream — BFF가 MinIO에서 스트리밍. 대역폭 소모 but 토큰 검증 단순화, CSP 단순.

C) 기타

[Answer]: AA) **Presigned redirect(권장)** — BFF가 owner/license/object 재검증 후 MinIO presigned GET(1분 TTL) 생성 → `307 Redirect`. 브라우저가 MinIO에서 직접 다운로드. BFF 대역폭 절약, CSP `img-src 'self' http://127.0.0.1:9000`로 허용.

---

### REM-2-CG-Q3 — Private userdoc write: 기존 ingestion 파이프라인 재사용 vs 경량 파이프라인

FD-Q5: 사용자 업로드 → DocModel 생성 → `userdoc:{owner}:{docId}` 저장. 기존 `provision_clock.py`/`provision_receipts.py` 패턴 vs 경량 전용 파이프라인.

A) **기존 ingestion/doc-model 파이프라인 재사용 + 별도 namespace(권장)** — `ingestion/`의 PDF/Markdown 파서, DocModel 생성, GROBID 연동 재사용. public corpus와 dedup 안 함. 저장만 `userdoc:{owner}:{docId}` prefix로 분리. 코드 중복 최소화.

B) 경량 전용 파이프라인 — PDF/Markdown 파서만 재사용, DocModel 생성 단순화, 저장·인덱싱 별도. 중복 코드 일부 발생.

C) 기타

[Answer]: AA) **기존 ingestion/doc-model 파이프라인 재사용 + 별도 namespace(권장)** — `ingestion/`의 PDF/Markdown 파서, DocModel 생성, GROBID 연동 재사용. public corpus와 dedup 안 함. 저장만 `userdoc:{owner}:{docId}` prefix로 분리. 코드 중복 최소화.

---

### REM-2-CG-Q4 — Worker concurrency: semaphore vs asyncio queue

ID-Q4: 각 worker의 동시성 상한을 `asyncio.Semaphore` vs 별도 `asyncio.Queue` + 고정 worker pool로 제어.

A) **`asyncio.Semaphore` + 단일 consumer loop(권장)** — 각 worker 프로세스가 단일 `asyncio.Queue`에서 메시지 소비, `semaphore.acquire()`로 동시 실행 제한. 구현 단순, backpressure 자연 적용. DLQ 이동 시 `semaphore.release()` 보장.

B) 고정 worker pool + 별도 queue — 각 worker type마다 N개 프로세스. 프로세스 관리 오버헤드.

C) 기타

[Answer]: AA) **`asyncio.Semaphore` + 단일 consumer loop(권장)** — 각 worker 프로세스가 단일 `asyncio.Queue`에서 메시지 소비, `semaphore.acquire()`로 동시 실행 제한. 구현 단순, backpressure 자연 적용. DLQ 이동 시 `semaphore.release()` 보장.

---

### REM-2-CG-Q5 — Property test: Hypothesis 전략 구성

PBT Full: job 상태 기계, cache 멱등성, authz 재검증, queue redelivery에 대한 Hypothesis 전략. 어떤 composite 전략을 사용할까?

A) **Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오(권장)** — 
- `job_input_strategy = st.builds(JobInput, task_type=st.sampled_from(types), input_data=st.text(...))`
- `state_transition_strategy = st.sampled_from(valid_transitions) | st.sampled_from(invalid_transitions)`
- `authz_scenario = st.sampled_from([valid, expired, revoked, missing])`
- `queue_scenario = st.sampled_from([normal, redelivery, crash, dlq])`
이들을 `st.tuples`로 조합해 property test에서 동시 검증. shrinking 유지, CI seed `20260930` 고정.

B) 각 property 별도 전략 — 조합 미검증.

C) 기타

[Answer]: AA) **Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오(권장)** — 
- `job_input_strategy = st.builds(JobInput, task_type=st.sampled_from(types), input_data=st.text(...))`
- `state_transition_strategy = st.sampled_from(valid_transitions) | st.sampled_from(invalid_transitions)`
- `authz_scenario = st.sampled_from([valid, expired, revoked, missing])`
- `queue_scenario = st.sampled_from([normal, redelivery, crash, dlq])`
이들을 `st.tuples`로 조합해 property test에서 동시 검증. shrinking 유지, CI seed `20260930` 고정.

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-2-CG-Q1~5에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Generation Part 2로 진행하지 않는다.
