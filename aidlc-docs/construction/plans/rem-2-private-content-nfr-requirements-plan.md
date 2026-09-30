# REM-2 Private Content — NFR Requirements 계획

**단계**: CONSTRUCTION / REM-2 NFR Requirements (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- `verification-remediation-2026-09-18.md` F01/F02/F05/F07 + §10 RJ-AC
- `requirements.md` NFR-P1/P2/P3/P4/P5/P6/P7, NFR-R1/R2/R3/R4, NFR-C1, NFR-M1/M2, NFR-O1
- `verification-remediation-2026-09-18.md` §9 Security/Resiliency/PBT 확장
- `aidlc-state.md` REM-1 완료: clock(±118ms), mTLS(loopback), launchd installer, receipt signer, keychain, backup/restore evidence, load acceptance

**목표**: REM-2 Private Content의 NFR Requirements 상세 계획을 작성하고, 13개 결정 질문(REM-2-NFR-Q1~13)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1의 versioned 계약(`shared/dtos`, `shared/ports`, `shared/vector-spec`)이 동결돼 공급된다.
- REM-1 런타임 기반(clock ±118ms, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance)은 검증 완료돼 런타임 기반으로 존재한다.
- Security Full, PBT Full, Resiliency custom single-host(RESILIENCY-08 면제) 계승.
- `RESILIENCY-08` 면제: 단일 Mac fault isolation. 나머지는 적용.
- full corpus rebuild 별도 승인.

---

## 분해 질문 (Decomposition Questions)

### REM-2-NFR-Q1 — NFR-P1 검색 SLA와 job 접수 latency 분리

NFR-P1: `lite=검색 SLA 대상 / full=비-SLA 에이전트 프로파일`. 공개 job 계약(RJ-AC01~12) 도입으로 **접수 latency(job accepted)**와 **실행 latency(job completed)**가 분리됐다. 검색 SLA는 `lite` 검색 자체에만 적용되며, job 접수/대기/결과 전달 시간은 별도 측정한다.

A) **검색 SLA = lite 검색 단독 latency(권장)** — NFR-P1 SLA(제안: p95 < 500ms)는 `GET /search?lite` 자체 응답 시간만 측정. job 접수/실행/전달은 별도 NFR-R4(응답성)로 관리. job 전환 임계값(FD-Q3)은 SLA와 무관.

B) 통합 SLA — 검색부터 결과 전달까지 종단 latency로 SLA 정의. job 전환 시 SLA 위반 위험.

C) 기타

[Answer]: AA) **검색 SLA = lite 검색 단독 latency(권장)** — NFR-P1 SLA(제안: p95 < 500ms)는 `GET /search?lite` 자체 응답 시간만 측정. job 접수/실행/전달은 별도 NFR-R4(응답성)로 관리. job 전환 임계값(FD-Q3)은 SLA와 무관.

---

### REM-2-NFR-Q2 — NFR-P2 online generation 예산과 cache hit 즉시 반환

NFR-P2: `캐시 hit 시 즉시 HTTP 결과 반환 전제는 빠른 cache-backed job 완료/전달로 대체하되 불필요한 model 재실행은 허용하지 않는다.` RJ-AC07(cache hit 시 model skip)과 RJ-AC08(asset 직접 전달)이 이를 구현한다. cache hit 경로의 **예산 상한(ms)**과 **완료→전달 파이프라인**을 확정한다.

A) **Cache hit = 동기 경로, budget ≤ 200ms(권장)** — cache hit 시 job 생성 없이 동기 HTTP 200 반환(assetId 포함). asset 전달은 별도 same-origin GET(RJ-AC08). miss 시에만 job 접수(FD-Q3 임계값 적용).

B) Cache hit도 job으로 접수하되 즉시 completed 반환 — 구현 단순화지만 접수/대기 오버헤드 발생.

C) 기타

[Answer]: AA) **Cache hit = 동기 경로, budget ≤ 200ms(권장)** — cache hit 시 job 생성 없이 동기 HTTP 200 반환(assetId 포함). asset 전달은 별도 same-origin GET(RJ-AC08). miss 시에만 job 접수(FD-Q3 임계값 적용).

---

### REM-2-NFR-Q3 — NFR-P6 비동기 생성 예산: p95 wall-clock 상한

NFR-P6: `긴 다논문 분석은 비동기 잡 오프로드 + 진행 상태 폴링`. 요약(FR-12)·번역(FR-13)·novelty(FR-30~35)·evidence(FR-37) 비동기 경로의 **p95 완료 시간(분)**과 **폴링 간격/타임아웃**을 확정한다.

A) **p95 ≤ 5분, 폴링 2초(권장)** — job 접수 후 5분 내 95% 완료. 폴링 간격 2초, 타임아웃 10분(그 후 terminal `failed`로 전환). 진행 상태는 `pending → running → completed/failed/abstained` event로 전달.

B) p95 ≤ 10분, 폴링 5초 — 넉넉한 예산이지만 UX 저하.

C) 기타

[Answer]: AA) **p95 ≤ 5분, 폴링 2초(권장)** — job 접수 후 5분 내 95% 완료. 폴링 간격 2초, 타임아웃 10분(그 후 terminal `failed`로 전환). 진행 상태는 `pending → running → completed/failed/abstained` event로 전달.

---

### REM-2-NFR-Q4 — NFR-R4 응답성: job 상태 event 전달 latency

NFR-R4: `durable job + queued 명시적 status query + event/subscription 전달`. job 상태 변경(`accepted → queued → running → completed/failed/abstained`)을 event로 푸시하고, status query는 queued/completed만 반환. event 전달 **p99 latency 상한(ms)**을 확정한다.

A) **p99 ≤ 500ms, WebSocket/Server-Sent Events(권장)** — BFF가 job 상태 변경 시 SSE로 event 푸시. status query는 REST로 queued/completed만 조회. 재연결 시 마지막 event부터 replay(RJ-AC04).

B) Polling-only — SSE 없이 클라이언트 폴링으로 상태 조회. 구현 단순하지만 latency·대역폭 비효율.

C) 기타

[Answer]: AA) **p99 ≤ 500ms, WebSocket/Server-Sent Events(권장)** — BFF가 job 상태 변경 시 SSE로 event 푸시. status query는 REST로 queued/completed만 조회. 재연결 시 마지막 event부터 replay(RJ-AC04).

---

### REM-2-NFR-Q5 — NFR-R1/R2/R* 에러 처리: job 실패의 구체적 표면화

NFR-R1: `오류 시 fail closed·일반화된 프로덕션 에러`. NFR-R2: `우아하게 저하`. job 실패(`failed`, `abstained`) 시 **에러 분류·사용자 메시지·재시도 힌트**를 표준화한다. `abstained`(근거 없음/초극단 거절)는 실패가 아닌 정상 terminal 상태.

A) **표준 에러 엔벨로프 + 재시도 힌트(권장)** — `{errorType, message, retryable, retryAfterSeconds?, assetId?}`. `abstained`는 `errorType: "abstained"`, `retryable: false`. `failed`는 원인별(`timeout`, `model_unavailable`, `validation_failed`)로 분류하고 재시도 가능 여부 표시.

B) 단순 성공/실패 — 구현 단순하지만 UX·디버깅 어려움.

C) 기타

[Answer]: AA) **표준 에러 엔벨로프 + 재시도 힌트(권장)** — `{errorType, message, retryable, retryAfterSeconds?, assetId?}`. `abstained`는 `errorType: "abstained"`, `retryable: false`. `failed`는 원인별(`timeout`, `model_unavailable`, `validation_failed`)로 분류하고 재시도 가능 여부 표시.

---

### REM-2-NFR-Q6 — NFR-C1 예산 저하: RERANK_OFF/LEXICAL_ONLY fail-soft

NFR-C1: `재랭킹은 순위 품질 향상일 뿐 하드 의존이 아니며 응답을 막거나 저하 모드로 만들지 않음`. 검색 재랭킹 어댑터 실패/예산 초과 시 융합점수(RRF) 순서로 **fail-soft**. job flow에서 재랭킹을 별도 단계로 분리하고 실패 시 base 순서로 즉시 반환.

A) **재랭킹 단계 분리 + 즉시 fallback(권장)** — search pipeline: `retrieve → fuse → [rerank] → response`. `[rerank]` 단계에서 예산 초과/어댑터 실패 시 즉시 fuse 순서로 진행, 응답 지연 없음. 로그에 `rerank_skipped: true` 기록.

B) 재랭킹 실패 시 전체 검색 실패 — 단순하지만 NFR-C1 위배.

C) 기타

[Answer]: AA) **재랭킹 단계 분리 + 즉시 fallback(권장)** — search pipeline: `retrieve → fuse → [rerank] → response`. `[rerank]` 단계에서 예산 초과/어댑터 실패 시 즉시 fuse 순서로 진행, 응답 지연 없음. 로그에 `rerank_skipped: true` 기록.

---

### REM-2-NFR-Q7 — SECURITY-08/SEC-8 owner authorization: job 전 단계 재검증

SECURITY-08/F01/F04: `owner authorization·파기 인수`. job 접수·실행·status·event·asset **모든 단계**에서 caller/object 권한 재검증(RJ-AC05). queue 대기 중 권한 만료/철회 시 즉시 terminal `failed`(RJ-AC11). authorization check **p99 latency 상한**을 확정한다.

A) **각 단계 미들웨어에서 재검증, p99 ≤ 50ms(권장)** — job pipeline의 각 단계(접수, 큐 진입, 실행 시작, status 조회, event 푸시, asset 전달) 진입 시 `authorize(caller, object, action)` 호출. 캐시된 권한 토큰으로 DB round-trip 최소화. 권한 만료 시 즉시 `failed` + event `permission_revoked`.

B) 접수 시점만 검증 후 신뢰 — 단순하지만 권한 변경 반영 안 됨(RJ-AC11 위배).

C) 기타

[Answer]: AA) **각 단계 미들웨어에서 재검증, p99 ≤ 50ms(권장)** — job pipeline의 각 단계(접수, 큐 진입, 실행 시작, status 조회, event 푸시, asset 전달) 진입 시 `authorize(caller, object, action)` 호출. 캐시된 권한 토큰으로 DB round-trip 최소화. 권한 만료 시 즉시 `failed` + event `permission_revoked`.

---

### REM-2-NFR-Q8 — SECURITY-13 F02/F13 cache/source integrity: canonical identity binding

SECURITY-13/F02/F13: `source/cache/contract integrity 인수`. cache key에 **canonical source identity(content version)** 필수 포함(FD-Q2). 번역 cache는 `paperId:version:sourceTier`로 key 구성. client-provided source 무시. cache poisoning 방지.

A) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. source tier는 server-verified enum(`ARXIV_HTML`, `SEMANTIC_SCHOLAR_PDF`, `OPENALEX_PDF`, `USER_UPLOAD`). client source 파라미터는 무시.

B) source 파라미터 검증 후 key 구성 — client가 canonical paperId 제공하면 lookup 후 일치 시 hit 허용. 추가 lookup 오버헤드.

C) 기타

[Answer]: AA) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. source tier는 server-verified enum(`ARXIV_HTML`, `SEMANTIC_SCHOLAR_PDF`, `OPENALEX_PDF`, `USER_UPLOAD`). client source 파라미터는 무시.

---

### REM-2-NFR-Q9 — SECURITY-10 F06 dependency audit: content job dependency 격리

SECURITY-10/F06: `production dependency audit에서 known critical/high finding 0 또는 source-unreachable 예외 승인`. content job(요약/번역/novelty/evidence)이 사용하는 Python/JS dependency를 별도 lockfile로 격리하고, CI에서 `pip-audit`/`npm audit` + `grype` scan을 강제한다.

A) **별도 lockfile + CI gate(권장)** — `ops/platform-integrity/requirements-content-job.txt`, `frontend/package-content-job.json` 별도 관리. PR CI에서 audit 실패 시 merge 차단. 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록.

B) 기존 lockfile 공유 — 단순하지만 audit noise 증가.

C) 기타

[Answer]: AA) **별도 lockfile + CI gate(권장)** — `ops/platform-integrity/requirements-content-job.txt`, `frontend/package-content-job.json` 별도 관리. PR CI에서 audit 실패 시 merge 차단. 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록.

---

### REM-2-NFR-Q10 — SECURITY-11 F10 trusted client rate-limit identity

SECURITY-11/F10: `Cloudflare/BFF 신뢰 경계에서 검증한 client identity만 FastAPI에 전달`. job 접수·status·asset endpoint에 **client identity 기반 rate-limit** 적용. 동일 client 독립 bucket, spoofing 거부.

A) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자는 `user:{id}`, 익명은 `ip:{hash}`.

B) IP-only rate-limit — 단순하지만 NAT/공용 WiFi에서 과도 제한.

C) 기타

[Answer]: AA) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자는 `user:{id}`, 익명은 `ip:{hash}`.

---

### REM-2-NFR-Q11 — RESILIENCY-10 F05 timeout alignment: browser→BFF→API→model→worker 정렬

RESILIENCY-10/F05: `browser, BFF, API, model, worker 시간 예산이 정렬된다. 동기 예산을 넘는 정상 생성은 job/pending/poll로 전환`. 각 레이어의 timeout을 **job 전환 임계값(FD-Q3) 기준으로 역산**해 정렬한다.

A) **역산 정렬표(권장)** — 예: job 전환 임계값 8k chars(요약) → 모델 p95 6초 → worker timeout 8초 → API timeout 10초 → BFF timeout 12초 → 브라우저 fetch timeout 15초. 각 레이어 timeout = 하위 레이어 timeout + 여유(2~4초). 동기 경로는 8초 브라우저 timeout 내 완료.

B) 각 레이어 독립 timeout — 단순하지만 timeout 불일치로 504/잘림 발생.

C) 기타

[Answer]: AA) **역산 정렬표(권장)** — 예: job 전환 임계값 8k chars(요약) → 모델 p95 6초 → worker timeout 8초 → API timeout 10초 → BFF timeout 12초 → 브라우저 fetch timeout 15초. 각 레이어 timeout = 하위 레이어 timeout + 여유(2~4초). 동기 경로는 8초 브라우저 timeout 내 완료.

---

### REM-2-NFR-Q11 — RESILIENCY-14 RJ-AC12 queue/worker/artifact 복구 검증

RESILIENCY-14/RJ-AC12: `queue loss/crash/reconnect/partial deploy에서 중복 효과와 상태 오판 방지 검증`. ElasticMQ 큐 유실, worker crash, 부분 배포 시 **중복 효과 부재·상태 정확·accepted job 재조정**을 검증한다.

A) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 행 0개, (2) terminal 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.

B) 문서화만 — 실제 장애 미검증.

C) 기타

[Answer]: AA) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 행 0개, (2) terminal 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.

---

### REM-2-NFR-Q12 — PBT-03/04/07/08: content job 불변식·멱등성·domain generator·shrinking

PBT Full: 
- PBT-03: `owner 격리, terminal 보존, 비재귀 전달 불변식`
- PBT-04: `submit retry/redelivery 논리적 멱등성`
- PBT-07: `owner/job/token/version/event domain generator`
- PBT-08: `shrinking + fixed/logged CI seed`

content job 상태 기계, cache hit/miss, asset 전달, 권한 재검증, queue redelivery에 대한 **property test 명세**를 확정한다.

A) **Python Hypothesis + TS fast-check 병행(권장)** — Python: `test_job_state_machine_property.py`, `test_cache_idempotent_property.py`, `test_authz_recheck_property.py`, `test_queue_redelivery_property.py`. TS: `test_job_event_order_property.ts`, `test_asset_delivery_property.ts`. CI seed 고정(`20260930`), shrinking 유지.

B) Python만 — TS 경로 커버리지 부족.

C) 기타

[Answer]: AA) **Python Hypothesis + TS fast-check 병행(권장)** — Python: `test_job_state_machine_property.py`, `test_cache_idempotent_property.py`, `test_authz_recheck_property.py`, `test_queue_redelivery_property.py`. TS: `test_job_event_order_property.ts`, `test_asset_delivery_property.ts`. CI seed 고정(`20260930`), shrinking 유지.

---

### REM-2-NFR-Q13 — NFR-O1 운영 관측: job/asset/queue 메트릭·경보

NFR-O1: `운영 대시보드 소비`. job/asset/queue 핵심 지표를 구조화 로그로 내보내고, **경보 임계값**을 정의한다.

A) **핵심 8지표 + 경보(권장)** — 
1. `job_accepted_total` (rate) — 급증 경보
2. `job_completed_total` / `job_failed_total` / `job_abstained_total` — 실패율 > 5% 경보
3. `job_queue_depth` — 백로그 > 1000 경보
4. `job_latency_p95_seconds` (accepted→completed) — p95 > 300초 경보
5. `asset_delivery_latency_p95_seconds` — p95 > 10초 경보
6. `cache_hit_ratio` — < 0.3 경보
7. `queue_redelivery_rate` — > 0.01 경보
8. `authz_recheck_failures_total` — > 0 경보 (즉시 조사)

구조화 JSON 로그로 stdout 출력, CloudWatch/로컬 파일 수집.

C) 기타

[Answer]: A

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-2-NFR-Q1~13에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
