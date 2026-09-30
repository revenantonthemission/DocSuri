# REM-3 Lifecycle and Edge Trust — NFR Requirements 계획

**단계**: CONSTRUCTION / REM-3 NFR Requirements (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- Functional Design (FD-Q1~8 승인 대기)
- `verification-remediation-2026-09-18.md` F04/F09/F10 + §10
- `requirements.md` NFR-P1~7, NFR-R1~4, NFR-C1, NFR-M1/M2, NFR-O1
- `verification-remediation-2026-09-18.md` §9 Security/Resiliency/PBT 확장
- REM-1/2 런타임: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance

**목표**: REM-3 Lifecycle and Edge Trust의 NFR Requirements 상세 계획을 작성하고, 13개 결정 질문(REM-3-NFR-Q1~13)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1/2 런타임 기반: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance
- Security Full, PBT Full, Resiliency custom(`RESILIENCY-08` 면제) 계승
- REM-1/2 contracts(`shared/dtos`, `shared/ports`, `shared/vector-spec`) 동결·공급
- `RESILIENCY-08` 면제(단일 Mac), full corpus rebuild 별도 승인

---

## 분해 질문 (Decomposition Questions)

### REM-3-NFR-Q1 — Purge latency: soft delete → hard delete 완료 시간

FR-28 계정 삭제 → soft delete 즉시 → 유예 기간(N일) → hard delete. **p95 hard delete 완료 시간**을 어떻게 정의할까? 유예 기간 만료 후 worker가 실제 파기까지 걸리는 시간.

A) **유예 기간 만료 후 24시간 내 p95 ≤ 1시간(권장)** — grace period 만료 후 `purge_worker`가 1시간 내 파기 완료. 유예 기간은 설정 가능(기본 30일). worker 주기적 스캔 간격 1시간.

B) 즉시 hard delete — soft delete 없이 즉시 파기. 유예 없음.

C) 기타

[Answer]: AA) **유예 기간 만료 후 24시간 내 p95 ≤ 1시간(권장)** — grace period 만료 후 `purge_worker`가 1시간 내 파기 완료. 유예 기간은 설정 가능(기본 30일). worker 주기적 스캔 간격 1시간.

---

### REM-3-NFR-Q2 — Unsubscribe token latency: token 검증 → 응답 시간

FR-47/49/RJ-AC10: 익명 unsubscribe token 검증 엔드포인트 응답 시간. token 검증(JWT verify) + DB lookup + durable 수락 확인.

A) **p99 ≤ 100ms(권장)** — JWT verify(로컬, ~1ms) + Redis cache lookup(~5ms) + DB lookup(~10ms) + 응답 직렬화. 캐시 히트 시 20ms 이하.

B) p99 ≤ 500ms — DB lookup만으로 충분.

C) 기타

[Answer]: AA) **p99 ≤ 100ms(권장)** — JWT verify(로컬, ~1ms) + Redis cache lookup(~5ms) + DB lookup(~10ms) + 응답 직렬화. 캐시 히트 시 20ms 이하.

---

### REM-3-NFR-Q3 — Rate-limit enforcement latency: Cloudflare → BFF → FastAPI 체인

NFR-Q10/SECURITY-11: Cloudflare → BFF → FastAPI identity 체인에서 rate-limit 검증 latency. client identity 추출 + token bucket consume.

A) **p99 ≤ 5ms(권장)** — Cloudflare에서 검증된 identity 헤더만 파싱 + in-memory token bucket consume. 네트워크 RTT 제외 순수 처리 시간.

B) p99 ≤ 50ms — 외부 서비스 호출 포함.

C) 기타

[Answer]: AA) **p99 ≤ 5ms(권장)** — Cloudflare에서 검증된 identity 헤더만 파싱 + in-memory token bucket consume. 네트워크 RTT 제외 순수 처리 시간.

---

### REM-3-NFR-Q4 — Purge worker throughput: 초당 파기 처리량

`purge_worker`가 soft deleted owner 데이터를 파기하는 초당 처리량. DB row 삭제 + object storage 객체 삭제 + audit log 기록.

A) **≥ 100 owners/sec(권장)** — 배치 처리 + 비동기 I/O. DB bulk delete + MinIO bulk delete. audit log 비동기 append.

B) 10 owners/sec — 순차 처리.

C) 기타

[Answer]: AA) **≥ 100 owners/sec(권장)** — 배치 처리 + 비동기 I/O. DB bulk delete + MinIO bulk delete. audit log 비동기 append. 

---

### REM-3-NFR-Q4 — Unsubscribe token search latency

FR-49/RJ-AC10: unsubscribe token으로 job/status 조회 시 latency. token → job_id lookup → 상태 반환.

A) **p99 ≤ 50ms(권장)** — Redis cache에 token→job_id 매핑 저장. cache miss 시 DB lookup(~10ms).

B) p99 ≤ 200ms — DB only.

C) 기타

[Answer]: AA) **p99 ≤ 50ms(권장)** — Redis cache에 token→job_id 매핑 저장. cache miss 시 DB lookup(~10ms).

---

### REM-3-NFR-Q5 — Consent/token revocation propagation latency

FR-47/48/R3P: consent/token 철회(revoke) 후 모든 관련 경로에서 반영되는 시간. token revocation → cache invalidation → 진행 중 job 중단.

A) **≤ 5초(권장)** — Redis pub/sub로 revocation event 발행 → 모든 worker가 즉시 cache invalidation. 진행 중 job은 다음 authz recheck에서 감지 → 즉시 FAILED.

B) ≤ 30초 — 주기적 polling.

C) 기타

[Answer]: AA) **≤ 5초(권장)** — Redis pub/sub로 revocation event 발행 → 모든 worker가 즉시 cache invalidation. 진행 중 job은 다음 authz recheck에서 감지 → 즉시 FAILED.

---

### REM-3-NFR-Q5 — Rate-limit bucket isolation: 동일 identity 독립 bucket

NFR-Q10: 동일 identity(인증된 user 또는 익명 IP)는 task type별 독립 bucket. task type 간 격리.

A) **Task type별 독립 bucket + identity별 격리(권장)** — `user:{uid}:translate`, `user:{uid}:summarize` 등 별도 버킷. 동일 identity라도 task type 간 격리.

B) 단일 버킷 — 모든 task type 공유.

C) 기타

[Answer]: AA) **Task type별 독립 bucket + identity별 격리(권장)** — `user:{uid}:translate`, `user:{uid}:summarize` 등 별도 버킷. 동일 identity라도 task type 간 격리.

---

### REM-3-NFR-Q6 — SECURITY-08 owner authorization: purge/unsubscribe 전 단계 재검증

SECURITY-08/F01/F04: purge/unsubscribe 전 단계(접수, 큐 진입, 실행, status, event, asset)에서 `authorize(caller, object, action)` 재검증. p99 ≤ 50ms.

A) **각 단계 미들웨어에서 재검증, AuthzCache 1분 TTL(권장)** — `AuthorizationService.recheck(caller, object, action)` 호출. 1분 TTL 캐시로 DB round-trip 최소화. 권한 만료 시 즉시 `FAILED` + event `permission_revoked` 발행.

B) 접수 시점만 검증 — 단순하지만 권한 변경 반영 안 됨.

C) 기타

[Answer]: AA) **각 단계 미들웨어에서 재검증, AuthzCache 1분 TTL(권장)** — `AuthorizationService.recheck(caller, object, action)` 호출. 1분 TTL 캐시로 DB round-trip 최소화. 권한 만료 시 즉시 `FAILED` + event `permission_revoked` 발행.

---

### REM-3-NFR-Q6 — SECURITY-10 F06 dependency audit: purge/unsubscribe path dependency 격리

SECURITY-10/F06: purge/unsubscribe 경로에서 사용하는 Python/JS dependency 별도 lockfile로 격리. CI에서 `pip-audit`/`npm audit` + `grype` scan 강제.

A) **별도 lockfile + CI gate(권장)** — `requirements-purge.txt`, `package-purge.json` 별도 관리. PR CI에서 audit 실패 시 merge 차단. 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록.

B) 기존 lockfile 공유 — 단순하지만 audit noise 증가.

C) 기타

[Answer]: AA) **별도 lockfile + CI gate(권장)** — `requirements-purge.txt`, `package-purge.json` 별도 관리. PR CI에서 audit 실패 시 merge 차단. 예외는 `SBOM_EXCEPTIONS.md`에 근거·만료일 기록.

---

### REM-3-NFR-Q7 — SECURITY-11 F10 trusted client rate-limit identity

SECURITY-11/F10: Cloudflare/BFF 신뢰 경계에서 검증한 client identity만 FastAPI에 전달. 동일 client 독립 bucket, spoofing 거부.

A) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용.

B) IP-only rate-limit — 단순하지만 NAT/공용 WiFi에서 과도 제한.

C) 기타

[Answer]: AA) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용.

---

### REM-3-NFR-Q7 — SECURITY-13 F02/F13 cache/source integrity: canonical identity binding

SECURITY-13/F02/F13: cache key에 canonical source identity 필수 포함. 번역 cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. client-provided source 무시.

A) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. `source_tier`는 server-verified enum. client source 파라미터 무시.

B) source 파라미터 검증 후 key 구성 — client가 canonical paperId 제공하면 lookup 후 일치 시 hit 허용.

C) 기타

[Answer]: AA) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. `source_tier`는 server-verified enum. client source 파라미터 무시.


---

### REM-3-NFR-Q8 — RESILIENCY-10 timeout alignment: browser→BFF→API→model→worker 정렬

RESILIENCY-10/F05: browser, BFF, API, model, worker 시간 예산 정렬. 동기 예산(8~15초) 넘는 정상 생성은 job/pending/poll 전환.

A) **역산 정렬표(권장)** — 모델 p95 + 여유(2~4초) = 하위 레이어 timeout. 예: 번역 모델 6s → worker 8s → API 10s → BFF 12s → 브라우저 15s. 동기 경로는 브라우저 timeout 내 완료 보장.

B) 각 레이어 독립 timeout — 단순하지만 timeout 불일치로 504/잘림 발생.

C) 기타

[Answer]: AA) **역산 정렬표(권장)** — 모델 p95 + 여유(2~4초) = 하위 레이어 timeout. 예: 번역 모델 6s → worker 8s → API 10s → BFF 12s → 브라우저 15s. 동기 경로는 브라우저 timeout 내 완료 보장.

---

### REM-3-NFR-Q9 — RESILIENCY-14 queue/worker/artifact 복구 검증

RESILIENCY-14/RJ-AC12: queue loss/crash/reconnect/partial deploy에서 중복 효과와 상태 오판 방지 검증.

A) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 0개, (2) terminal 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.

B) 문서화만 — 실제 장애 미검증.

C) 기타

[Answer]: AA) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 0개, (2) terminal 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.


---

### REM-3-NFR-Q10 — SECURITY-13 F02/F13 cache/source integrity: canonical identity binding

SECURITY-13/F02/F13: cache key에 canonical source identity 필수 포함. 번역 cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. client-provided source 무시.

A) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. source tier는 server-verified enum. client source 파라미터 무시.

B) source 파라미터 검증 후 key 구성 — client가 canonical paperId 제공하면 lookup 후 일치 시 hit 허용.

C) 기타

[Answer]: AA) **Canonical identity 필수 + 버전 pinning(권장)** — cache key = `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. source tier는 server-verified enum. client source 파라미터 무시.

---

### REM-3-NFR-Q11 — RESILIENCY-14 RJ-AC12 queue/worker/artifact 복구 검증: 상세

RJ-AC12: `queue loss/crash/reconnect/partial deploy에서 중복 효과와 상태 오판 방지 검증`. ElasticMQ 큐 유실, worker crash, 부분 배포 시 중복 효과 부재·상태 정확·accepted job 재조정 검증.

A) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 0개, (2) 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.

B) 문서화만 — 실제 장애 미검증.

C) 기타

[Answer]: AA) **장애 주입 테스트 스위트(권장)** — `test_queue_loss.py`, `test_worker_crash.py`, `test_partial_deploy.py`로 각각 주입. 검증: (1) 중복 effect ledger 0개, (2) 상태 정확히 복구, (3) accepted job 재조정 완료, (4) asset 전달 중복 0개. CI에서 주 1회 실행.

---

### REM-3-NFR-Q12 — PBT-03/04/07/08: purge/unsubscribe 불변식·멱등성·domain generator·shrinking

PBT Full: 
- PBT-03: `owner 격리, terminal 보존, 비재귀 전달 불변식`
- PBT-04: `submit retry/redelivery 논리적 멱등성`
- PBT-07: `owner/job/token/version/event domain generator`
- PBT-08: `shrinking + fixed/logged CI seed`

purge/unsubscribe job 상태 기계, cache hit/miss, authz 재검증, queue redelivery에 대한 property test 명세.

A) **Python Hypothesis + TS fast-check 병행(권장)** — Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오. CI seed `20260930` 고정, shrinking 유지.

B) Python만 — TS 경로 커버리지 부족.

C) 기타

[Answer]: AA) **Python Hypothesis + TS fast-check 병행(권장)** — Composite strategy = job 입력 × 상태 전이 × 권한 시나리오 × queue 시나리오. CI seed `20260930` 고정, shrinking 유지.

---

### REM-3-NFR-Q13 — NFR-O1 운영 관측: purge/unsubscribe 메트릭·경보

NFR-O1: `운영 대시보드 소비`. purge/unsubscribe 핵심 지표를 구조화 로그로 내보내고 경보 임계값 정의.

A) **핵심 8지표 + 경보(권장)** — 
1. `purge_requested_total` (rate) — 급증 경보
2. `purge_completed_total` / `purge_failed_total` — 실패율 > 5% 경보
3. `purge_queue_depth` — 백로그 > 1000 경보
4. `purge_latency_p95_seconds` — p95 > 3600s(1시간) 경보
5. `unsubscribe_token_verification_p95_ms` — p99 > 100ms 경보
6. `unsubscribe_rate_total` — 급증 경보
7. `revocation_propagation_latency_p95` — > 5초 경보
8. `authz_recheck_failures_total` — > 0 즉시

구조화 JSON 로그 stdout 출력, Prometheus 수집.

C) 기타

[Answer]: AA) **핵심 8지표 + 경보(권장)** — 
1. `purge_requested_total` (rate) — 급증 경보
2. `purge_completed_total` / `purge_failed_total` — 실패율 > 5% 경보
3. `purge_queue_depth` — 백로그 > 1000 경보
4. `purge_latency_p95_seconds` — p95 > 3600s(1시간) 경보
5. `unsubscribe_token_verification_p95_ms` — p99 > 100ms 경보
6. `unsubscribe_rate_total` — 급증 경보
7. `revocation_propagation_latency_p95` — > 5초 경보
8. `authz_recheck_failures_total` — > 0 즉시

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-NFR-Q1~13에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
