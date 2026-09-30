# REM-2 Private Content — NFR Requirements

**단계**: CONSTRUCTION / REM-2 NFR Requirements Generation Part 2  
**일자**: 2026-09-30  
**기반**: 
- Functional Design: `functional-design/domain-entities.md`, `business-logic-model.md`, `business-rules.md`, `scenarios.md`
- NFR-Q1~13 전수 A 승인
- REM-1 완료 런타임: clock ±118µs, mTLS loopback, launchd installer, receipt signer, keychain, backup/restore evidence, load acceptance
- `verification-remediation-2026-09-18.md` Security Full, PBT Full, Resiliency custom (RESILIENCY-08 면제)

---

## 1. 성능 (Performance)

### NFR-P1: 검색 SLA와 Job 접수 Latency 분리
**NFR-Q1 A** — 검색 SLA = lite 검색 단독 latency (p95 < 500ms). Job 접수/대기/전달 시간은 별도 NFR-R4로 관리.

| 지표 | 목표 | 측정 방식 |
|---|---|---|
| Lite 검색 p95 | < 500ms | BFF → FastAPI → OpenSearch 경로만 측정 |
| Full 검색 | 비-SLA (에이전트 프로파일) | 별도 프로파일링 |
| Job 접수 latency | p99 < 100ms | 접수 API만 측정 (큐 진입 전) |

### NFR-P2: Online Generation 예산 — Cache Hit 즉시 반환
**NFR-Q2 A** — Cache hit 시 동기 HTTP 200 반환 (assetId 포함), model 미실행 (RJ-AC07). Budget ≤ 200ms.

| 경로 | Budget | 비고 |
|---|---|---|
| Cache hit (동기) | p95 ≤ 200ms | `TranslationCacheService.lookup()`만 수행 |
| Cache miss → Job 접수 | p99 ≤ 100ms | `ContentJobService.submit()`만 수행 |
| Asset 전달 (presigned) | p95 ≤ 10s | MinIO presigned URL 생성 + redirect |

### NFR-P3: 검색 품질 — Rerank Fail-Soft
**NFR-Q6 A** — 재랭킹 어댑터 실패/예산 초과 시 융합점수(RRF) 순서로 즉시 fallback. 응답 지연 없음.

| 조건 | 동작 |
|---|---|
| 재랭킹 어댑터 예산 초과 | 즉시 fuse 순서로 진행, `rerank_skipped: true` 로그 |
| 재랭킹 어댑터 예외 발생 | 즉시 fuse 순서로 진행, 에러 로그만 기록 |
| 응답 지연 | 0ms 추가 (즉시 fallback) |

### NFR-P4: 비동기 생성 예산
**NFR-Q3 A** — 비동기 생성 작업(p95 완료 ≤ 5분, 폴링 2초).

| Task Type | p95 완료 시간 | 폴링 간격 | 타임아웃 |
|---|---|---|---|
| TRANSLATE | ≤ 5분 | 2초 | 10분 |
| SUMMARIZE | ≤ 5분 | 2초 | 10분 |
| NOVELTY | ≤ 8분 | 2초 | 15분 |
| EVIDENCE | ≤ 10분 | 2초 | 15분 |

진행 상태: `PENDING → RUNNING → COMPLETED/FAILED/ABSTAINED` SSE event로 전달.

---

## 2. 응답성 (Responsiveness)

### NFR-R4: Job 상태 Event 전달 Latency
**NFR-Q4 A** — Job 상태 변경 시 SSE event 푸시 p99 ≤ 500ms. Status query는 REST로 queued/completed만 조회.

| Event Type | 전달 방식 | p99 Latency |
|---|---|---|
| 상태 변경 (ACCEPTED/QUEUED/RUNNING/COMPLETED/FAILED/ABSTAINED) | SSE 푸시 | ≤ 500ms |
| Status Query (REST) | queued/completed만 반환 | ≤ 100ms |
| 재연결 Replay | Last-Event-ID 기반 | ≤ 1s |

Reconnection 시 `Last-Event-ID` 헤더로 missed event replay (RJ-AC04).

---

## 3. 에러 처리 (Error Handling)

### NFR-R1/R2: Job 실패 표준화 — 표준 에러 엔벨로프 + 재시도 힌트
**NFR-Q5 A** — `abstained`는 정상 terminal 상태, `failed`는 원인별 분류.

```json
{
  "errorType": "timeout|model_unavailable|validation_failed|permission_revoked|abstained",
  "message": "사용자 친화적 메시지",
  "retryable": true|false,
  "retryAfterSeconds": 30,
  "assetId": "asset:..."  // COMPLETED 시만
}
```

| errorType | retryable | 비고 |
|---|---|---|
| `timeout` | true | `retryAfterSeconds` 포함 |
| `model_unavailable` | true | `retryAfterSeconds` 포함 |
| `validation_failed` | false | 입력 수정 필요 |
| `permission_revoked` | false | 즉시 FAILED, 재시도 불가 (RJ-AC11) |
| `abstained` | false | 정상 terminal, 재시도 불가 |

---

## 4. 보안 (Security) — Security Full 적용

### SECURITY-08 / F01/F04: Owner Authorization 전 단계 재검증
**NFR-Q7 A** — Job 파이프라인 모든 단계에서 `authorize(caller, jobId, action)` 재검증. p99 ≤ 50ms.

| 단계 | Action | 재검증 방식 |
|---|---|---|
| 접수 | `SUBMIT` | `AuthorizationService.recheck()` |
| 큐 진입 | `ENQUEUE` | 동일 |
| 실행 시작 | `EXECUTE` | 동일 (권한 만료 시 즉시 FAILED, RJ-AC11) |
| Status 조회 | `STATUS` | 동일 |
| Event 푸시 | `EVENT` | 동일 |
| Asset 전달 | `ASSET` | 동일 |

`AuthzCache` 1분 TTL로 DB round-trip 최소화. 권한 만료 시 즉시 `FAILED` + event `permission_revoked` 발행 (RJ-AC11, BR-AUTHZ-03).

### SECURITY-13 / F02/F13: Cache/Source Integrity — Canonical Identity Binding
**NFR-Q8 A** — Cache key에 canonical source identity 필수 포함. Client-provided source 무시.

| 항목 | 요구사항 |
|---|---|
| Cache key 구성 | `{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}` |
| `canonical_paper_id` 출처 | 오직 `CanonicalPaperRegistry.resolve()`만 |
| `source_tier` 순위 | `ARXIV_HTML` > `SEMANTIC_SCHOLAR_PDF` > `OPENALEX_PDF` > `USER_UPLOAD` |
| Client source 파라미터 | **무시** (cache key 구성에 사용 안 함) |

### SECURITY-10 / F06: Dependency Audit — Content Job 격리
**NFR-Q9 A** — Content job dependency 별도 lockfile로 격리, CI에서 audit 강제.

| 산출물 | 관리 방식 |
|---|---|
| Python deps | `ops/platform-integrity/requirements-content-job.txt` 별도 관리 |
| JS deps | `frontend/package-content-job.json` 별도 관리 |
| CI Gate | PR에서 `pip-audit` + `npm audit` + `grype` scan 실패 시 merge 차단 |
| 예외 관리 | `SBOM_EXCEPTIONS.md`에 근거·만료일 기록 |

### SECURITY-11 / F10: Trusted Client Rate-Limit Identity
**NFR-Q10 A** — Cloudflare → BFF → FastAPI identity 체인.

| 레이어 | 역할 |
|---|---|
| Cloudflare | `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더 |
| BFF (FastAPI) | `X-Client-Identity` 헤더 파싱 → identity별 token bucket |
| Identity 형식 | 인증: `user:{uid}`, 익명: `ip:{sha256(ip)[:16]}` |
| 버킷 격리 | 동일 identity 동일 버킷, task type별 별도 버킷 |

---

## 5. 레질리언시 (Resiliency) — Custom Single-Host Profile

### RESILIENCY-10 / F05: Timeout Alignment — 레이어별 역산 정렬
**NFR-Q11 A** — 브라우저 timeout 기준 역산 정렬표 적용.

| Task Type | 모델 p95 | Worker | API | BFF | 브라우저 |
|---|---|---|---|---|---|
| TRANSLATE | 6s | 8s | 10s | 12s | 15s |
| SUMMARIZE | 6s | 8s | 10s | 12s | 15s |
| NOVELTY | 10s | 14s | 18s | 22s | 30s |
| EVIDENCE | 12s | 16s | 20s | 24s | 30s |

각 레이어 timeout = 하위 레이어 timeout + 여유(2~4초). 동기 경로는 브라우저 timeout 내 완료 보장.

### RESILIENCY-14 / RJ-AC12: Queue/Worker/Artifact 복구 검증
**NFR-Q11 (RESILIENCY-14) A** — 장애 주입 테스트 스위트로 검증.

| 테스트 | 주입 장애 | 검증 기준 |
|---|---|---|
| `test_queue_loss.py` | ElasticMQ 메시지 유실 시뮬레이션 | 중복 effect ledger 0개, 상태 정확 복구 |
| `test_worker_crash.py` | Worker 프로세스 kill (SIGKILL) | Redelivery → 중복 ledger 0개, 상태 정확 복구 |
| `test_partial_deploy.py` | 배포 중 rolling restart | Accepted job 재조정 완료, asset 전달 중복 0개 |

CI에서 주 1회 실행, 실패 시 merge 차단.

---

## 6. Property-Based Testing — PBT Full

### PBT-03/04/07/08: Content Job 불변식·멱등성·Domain Generator·Shrinking
**NFR-Q12 A** — Python Hypothesis + TS fast-check 병행, CI seed `20260930` 고정, shrinking 유지.

| Property Test | 대상 | Strategy |
|---|---|---|
| `test_job_state_machine_property.py` | 상태 전이 불변식 | `job_input × state_transition × authz_scenario × queue_scenario` composite |
| `test_cache_idempotent_property.py` | Cache 멱등성 | 동일 멱등성 키 → 동일 결과(assetId 또는 jobId) |
| `test_authz_recheck_property.py` | 권한 재검증 | 권한 만료 → 즉시 FAILED + event |
| `test_queue_redelivery_property.py` | Queue redelivery 멱등성 | 동일 `jobId`+`attempt` 중복 차단 |
| TS: `test_job_event_order_property.ts` | Event 순서 보장 | SSE event 순서 불변식 |
| TS: `test_asset_delivery_property.ts` | Asset 전달 | assetId → presigned URL → 307 redirect |

CI seed `20260930` 고정, shrinking 유지, shrunk counterexample 저장.

---

## 7. 운영 관측 (Observability)

### NFR-O1: Job/Asset/Queue 메트릭·경보
**NFR-Q13 A** — 8 핵심 지표 + 경보, 구조화 JSON 로그로 stdout 출력.

| # | 지표 | 경보 조건 |
|---|---|---|
| 1 | `job_accepted_total` (rate) | 급증 > 10x baseline for 2m |
| 2 | `job_completed/failed/abstained_total` | 실패율 > 5% for 5m |
| 3 | `job_queue_depth` | 백로그 > 1000 for 2m |
| 4 | `job_latency_p95_seconds` (accepted→completed) | p95 > 300s for 10m |
| 5 | `asset_delivery_p95_seconds` | p95 > 10s for 5m |
| 6 | `cache_hit_ratio` | < 0.3 for 15m |
| 7 | `queue_redelivery_rate` | > 0.01 for 5m |
| 8 | `authz_recheck_failures_total` | > 0 즉시 (즉시 조사) |

로그 형식: 구조화 JSON 라인 (`{"metric": "...", "labels": {...}, "value": 1, "timestamp": "..."}`). CloudWatch/로컬 파일 수집.

---

## 8. 추적성 매트릭스: NFR Question → Requirement

| NFR Question | NFR Requirements |
|---|---|
| NFR-Q1 (검색 SLA/Job latency 분리) | NFR-P1, NFR-R4 분리 측정 |
| NFR-Q2 (Cache hit 즉시 반환) | NFR-P2 budget ≤ 200ms, RJ-AC07 구현 |
| NFR-Q3 (비동기 예산) | NFR-P4: p95 ≤ 5분, 폴링 2초 |
| NFR-Q4 (Event 전달 latency) | NFR-R4: SSE p99 ≤ 500ms, replay ≤ 1s |
| NFR-Q5 (에러 표준화) | NFR-R1/R2: 표준 엔벨로프 + 재시도 힌트 |
| NFR-Q6 (Rerank fail-soft) | NFR-P3: 즉시 fallback, 지연 0ms |
| NFR-Q7 (Authz 재검증) | SECURITY-08: 전 단계 재검증 p99 ≤ 50ms |
| NFR-Q8 (Cache canonical identity) | SECURITY-13: Canonical identity binding, client source 무시 |
| NFR-Q9 (Dependency audit 격리) | SECURITY-10: 별도 lockfile + CI gate |
| NFR-Q10 (Rate-limit identity) | SECURITY-11: Cloudflare→BFF→FastAPI identity 체인 |
| NFR-Q11 (Timeout alignment) | RESILIENCY-10: 역산 정렬표, 브라우저 timeout 내 완료 |
| NFR-Q12 (PBT) | PBT-03/04/07/08: Hypothesis+fast-check 병행, seed 고정 |
| NFR-Q13 (운영 메트릭) | NFR-O1: 8지표 + 경보, JSON 구조화 로그 |

---

## 9. 승인 기록

| 질문 | 답변 | 일자 |
|---|---|---|
| NFR-Q1~13 | A (전수) | 2026-09-30 |

**다음**: NFR Design Generation Part 2 → `construction/rem-2-private-content/nfr-design/`
