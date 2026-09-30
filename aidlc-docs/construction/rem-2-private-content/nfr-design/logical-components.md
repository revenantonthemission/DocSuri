# REM-2 Private Content — Logical Components

**단계**: CONSTRUCTION / REM-2 NFR Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `nfr-design-patterns.md` 승인 (ND-Q1~10 전수 A), NFR Requirements, Functional Design

---

## LC-R2-01: CanonicalPaperRegistry

**책임**: `paperId + version` → `canonical_id + source_tier` 정규화 (PAT-R2-01)  
**인터페이스**:
```python
class CanonicalPaperRegistry(Protocol):
    def resolve(self, paper_id: str, version: int) -> CanonicalIdentity: ...
    
@dataclass(frozen=True)
class CanonicalIdentity:
    canonical_id: str      # "arxiv:2301.12345" | "semantic:987654321" | "userdoc:owner:docId"
    source_tier: SourceTier  # ARXIV_HTML > SEMANTIC_SCHOLAR_PDF > OPENALEX_PDF > USER_UPLOAD
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/registry.py`  
**의존성**: 없음 (순수 로직)  
**테스트**: `test_canonical_registry.py` — arXiv/Semantic Scholar/OpenAlex/userdoc 각각 정규화 검증

---

## LC-R2-02: TranslationCacheService

**책임**: 번역 결과 캐싱, canonical identity 기반 key 구성 (PAT-R2-01, PAT-R2-03)  
**인터페이스**:
```python
class TranslationCacheService(Protocol):
    async def lookup(self, cache_key: str) -> TranslationCacheEntry | None: ...
    async def store(self, entry: TranslationCacheEntry) -> None: ...
    def compose_key(
        self, canonical_id: str, version: int, source_tier: SourceTier,
        target_lang: str, persona_hash: str
    ) -> str: ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/cache.py`  
**저장소**: Redis (key: `translate:{canonical_id}:{version}:{tier}:{lang}:{persona_hash}`, value: `assetId`, TTL 30일)  
**의존성**: `CanonicalPaperRegistry`, Redis client  
**테스트**: `test_translation_cache_property.py` — canonical identity binding, client source 무시, hit/miss 멱등성

---

## LC-R2-03: ContentJobService

**책임**: Content job 생명주기 관리 — 제출, 멱등성, 상태 기계, 이벤트 발행 (PAT-R2-02, PAT-R2-06)  
**인터페이스**:
```python
class ContentJobService(Protocol):
    async def submit(
        self, task_type: TaskType, input: JobInput, idempotency_key: str
    ) -> str: ...  # returns jobId
    
    async def get_state(self, job_id: str) -> JobState: ...
    async def subscribe_events(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[JobEvent, None]: ...
```

**구현**: `ops/platform-integrity/content_job_service.py`  
**상태 기계**: `SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED | FAILED | ABSTAINED` (역전환 불가)  
**멱등성**: `idempotency_key = content:{canonical_id}:{task_type}:{input_hash}:{params_hash}` (PAT-R2-06)  
**이벤트**: `JobEventEmitter`로 SSE 발행, Outbox 패턴으로 replay 지원 (PAT-R2-02)  
**저장소**: PostgreSQL (`jobs` 테이블), Outbox 테이블로 이벤트 지속성  
**테스트**: `test_job_state_machine_property.py`, `test_job_event_order_property.ts`

---

## LC-R2-04: JobEventEmitter + SSE Endpoint

**책임**: Job 상태 변경 이벤트 발행, SSE 스트리밍, replay 지원 (PAT-R2-02)  
**인터페이스**:
```python
class JobEventEmitter(Protocol):
    def emit(self, event: JobEvent) -> None: ...
    async def subscribe(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[JobEvent, None]: ...

@dataclass(frozen=True)
class JobEvent:
    event_id: str
    job_id: str
    state: JobState
    timestamp_us: int
    payload: dict | None = None  # assetId, error, abstainReason 등
```

**구현**: `ops/platform-integrity/event_emitter.py`  
**구독**: `GET /jobs/{jobId}/events` (SSE, `Last-Event-ID` 헤더로 replay, RJ-AC04)  
**Outbox 패턴**: 이벤트를 DB `outbox` 테이블에 동일 트랜잭션으로 기록, 재연결 시 replay  
**테스트**: `test_job_event_order_property.ts` — event 순서 보장, replay 정확성

---

## LC-R2-05: ContentJobWorker (4종)

**책임**: Task type별 job 실행 — translate, summarize, novelty, evidence (PAT-R2-05, ID-Q4)  
**공통 구조**:
```python
class BaseWorker:
    def __init__(self, task_type: TaskType, semaphore: asyncio.Semaphore):
        self.task_type = task_type
        self.semaphore = semaphore  # 동시성 상한 제어
    
    async def run(self, message: JobMessage) -> JobResult:
        async with self.semaphore:
            attempt = message.attempt
            # Effect ledger insert 시도 (PK: job_id, attempt)
            try:
                await self.effect_ledger.insert(message.job_id, attempt, ...)
            except UniqueViolation:
                return JobResult(skipped=True)  # 중복 attempt skip
            
            result = await self.execute(message.input)
            await self.complete_job(message.job_id, result)
            return JobResult(completed=True)
```

### 4종 Worker 설정 (ID-Q4 A)

| Worker | Task Type | 동시성 상한 | Queue Depth | 비고 |
|---|---|---|---|---|
| `TranslateWorker` | `TRANSLATE` | 2 | 50 | Cache hit 시 즉시 completed |
| `SummarizeWorker` | `SUMMARIZE` | 2 | 50 | Map-reduce for 긴 본문 |
| `NoveltyWorker` | `NOVELTY` | 1 | 20 | Evidence agent 결과 소비 |
| `EvidenceWorker` | `EVIDENCE` | 2 | 30 | Evidence formation |

**동시성 제어**: `asyncio.Semaphore` + 단일 consumer loop (CG-Q4 A)  
**멱등성**: `effect_ledger(job_id, attempt)` PK로 중복 차단 (PAT-R2-06)  
**DLQ**: maxReceiveCount 3 초과 시 `content-job-dlq` 이동  
**테스트**: `test_content_job_pipeline.py`, `test_queue_redelivery_property.py`

---

## LC-R2-06: AssetService + Presigned Redirect

**책임**: Asset 발급/저장, presigned URL 생성, same-origin 전달 (PAT-R2-04)  
**인터페이스**:
```python
class AssetService(Protocol):
    async def issue(self, content: bytes, owner: str, license: LicenseType, object_ref: str) -> str: ...  # returns assetId
    async def issue_presigned(self, asset_id: str, caller: str, action: str = "view") -> str: ...  # returns presigned URL
    async def authorize(self, caller: str, asset_id: str, action: str) -> bool: ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/assets.py`  
**AssetId**: `asset:{sha256(content)[:32]}` (결정론적)  
**Presigned Token**: HS256 JWT, payload `{assetId, action, nonce, exp=now+60s, sub}` (1분 TTL, PAT-R2-04, ND-Q7)  
**전달**: `307 Redirect` to MinIO presigned GET (1분 TTL, inline disposition)  
**CSP**: `img-src 'self' http://127.0.0.1:9000` (ID-Q7)  
**MinIO**: Internal only (`127.0.0.1:9000`), 외부 직접 접근 차단  
**테스트**: `test_asset_serving.py`, `test_asset_delivery_property.ts`

---

## LC-R2-07: JobAuthzMiddleware + AuthorizationService

**책임**: Job 파이프라인 모든 단계에서 권한 재검증 (PAT-R2-05, PAT-R2-07)  
**인터페이스**:
```python
class AuthorizationService(Protocol):
    async def recheck(self, caller: str, job_id: str, action: str) -> bool: ...

class JobAuthzMiddleware:
    ACTIONS = ["SUBMIT", "ENQUEUE", "EXECUTE", "STATUS", "EVENT", "ASSET"]
    async def __call__(self, request: Request, call_next): ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/authz.py`  
**AuthzCache**: 1분 TTL, key=`{caller}:{job_id}:{action}` → `(allowed, expires_at)` (NFR-Q7 p99 ≤ 50ms)  
**권한 만료 시**: 즉시 `FAILED` 전이 + `permission_revoked` event 발행 (RJ-AC11, BR-AUTHZ-03)  
**적용 지점**: 접수, 큐 진입, 실행 시작, status 조회, event 푸시, asset 전달 (BR-AUTHZ-01)  
**테스트**: `test_authz_recheck_property.py` — 권한 만료 시 즉시 FAILED + event 발행

---

## LC-R2-08: RateLimitMiddleware

**책임**: Client identity별 task type별 토큰 버킷 (PAT-R2-05, NFR-Q10)  
**인터페이스**:
```python
class RateLimitMiddleware:
    async def __call__(self, request: Request, call_next): ...
```

**Identity Chain**: Cloudflare(`CF-Connecting-IP` + 인증 토큰) → BFF(`X-Client-Identity` 헤더) → FastAPI token bucket  
**Identity**: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}` (NFR-Q10)  
**버킷**: Task type별 별도, `maxTokens=10`, `refillRate=2/sec` (configurable)  
**초과 시**: `429 Too Many Requests` + `Retry-After` 헤더 (BR-RL-03)  
**테스트**: `test_rate_limit_property.py` — 동일 identity 급증 시 429, spoofing 불가

---

## LC-R2-09: TimeoutProfile + Layered Timeouts

**책임**: Task type별 동기/비동기 임계값, 레이어별 timeout 역산 (PAT-R2-03, PAT-R2-09, NFR-Q11)  
**설정** (`ops/platform-integrity/timeouts.yaml`):
```yaml
TRANSLATE:
  sync_threshold_chars: 12000
  model_p95_sec: 6
  worker_sec: 8
  api_sec: 10
  bff_sec: 12
  browser_sec: 15
SUMMARIZE:
  sync_threshold_chars: 8000
  model_p95_sec: 6
  worker_sec: 8
  api_sec: 10
  bff_sec: 12
  browser_sec: 15
NOVELTY:
  sync_threshold_chars: 16000
  model_p95_sec: 10
  worker_sec: 14
  api_sec: 18
  bff_sec: 22
  browser_sec: 30
EVIDENCE:
  sync_threshold_chars: 20000
  model_p95_sec: 12
  worker_sec: 16
  api_sec: 20
  bff_sec: 24
  browser_sec: 30
```

**역산 원칙**: 모델 p95 + 여유(2~4초) = 하위 레이어 timeout. 동기 경로는 브라우저 timeout 내 완료 보장 (BR-TIMEOUT-02, NFR-Q11).

---

## LC-R2-10: ObservabilityMetrics + Alerting

**책임**: 8 핵심 지표 수집, 구조화 JSON 로그 출력, 경보 규칙 (PAT-R2-10, NFR-Q13)  
**로그 형식**: stdout JSON lines
```json
{"metric": "job_accepted_total", "labels": {"task_type": "translate"}, "value": 1, "timestamp": "2026-09-30T23:59:59.123456Z"}
```

### 8 Core Metrics
| # | Metric | Type | Labels | Alert |
|---|---|---|---|---|
| 1 | `job_accepted_total` | Counter | `task_type` | rate > 10x baseline for 2m |
| 2 | `job_completed_total`, `job_failed_total`, `job_abstained_total` | Counter | `task_type`, `state` | 실패율 > 5% for 5m |
| 3 | `job_queue_depth` | Gauge | `task_type` | > 1000 for 2m |
| 4 | `job_latency_p95_seconds` | Histogram | `task_type` | p95 > 300s for 10m |
| 5 | `asset_delivery_p95_seconds` | Histogram | - | p95 > 10s for 5m |
| 6 | `cache_hit_ratio` | Gauge | `task_type` | < 0.3 for 15m |
| 7 | `queue_redelivery_rate` | Gauge | `task_type` | > 0.01 for 5m |
| 8 | `authz_recheck_failures_total` | Counter | - | > 0 즉시 |

**출력**: stdout JSON lines, Prometheus node_exporter 수집 (NFR-Q13 A)

---

## LC-R2-11: Provisioning Scripts (Infrastructure)

**책임**: Launchd worker 서비스, Keychain secret, Backup 포함 (ID-Q1~8)  
**스크립트**:
- `provision_content_workers.py` — 4종 launchd plist 생성/설치 (`rem-2-content-translate|summarize|novelty|evidence`)
- `provision_rem2_keys.py` — Keychain 3종 생성 (asset-jwt, queue, minio), ACL 설정
- `backup_evidence.py` 수정 — `private/userdoc/`, `assets/` 경로 포함, owner별 격리 복원/파기

**Launchd 설정** (ID-Q6 A):
- Label: `rem-2-content-{translate|summarize|novelty|evidence}`
- User/Group: `_docsuri_rem2_worker` / `_docsuri_rem2_worker`
- `InitGroups=false`, `Umask=0o077`, `ProcessType=Background`
- `ThrottleInterval=5`, `ExitTimeOut=30`, `RunAtLoad=false`

**Keychain** (ID-Q8 A):
- `asset-jwt.keychain-db` (service `docsuri.rem2.asset`, account `asset-jwt`)
- `queue.keychain-db` (service `docsuri.rem2.queue`, account `elasticmq`)
- `minio.keychain-db` (service `docsuri.rem2.minio`, account `minio`)
- Owner: `_docsuri_rem2_sign`, ACL로 worker만 접근 허용

---

## Component Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                         │
│  JobStatus (SSE) ── AssetViewer (presigned) ── RateLimitMiddleware│
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BFF (FastAPI)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ JobAuthzMw  │ │ RateLimitMw │ │ AssetController │ TimeoutProfile │
│  └──────┬──────┘ └──────┬──────┘ └───────┬───────┘ └─────┬─────┘ │
└─────────┼───────────────┼────────────────┼───────────────┼───────┘
          │               │                │               │
          ▼               ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ContentJobService                            │
│  submit() → 멱등성 체크 → 상태 기계 → JobEventEmitter → ElasticMQ  │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┬──────────────┐
              ▼              ▼              ▼              ▼
       ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
       │Translate │   │Summarize │   │ Novelty  │   │ Evidence │
       │ Worker   │   │ Worker   │   │ Worker   │   │ Worker   │
       │(sem=2)   │   │(sem=2)   │   │(sem=1)   │   │(sem=2)   │
       └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
            │              │              │              │
            ▼              ▼              ▼              ▼
       ┌─────────────────────────────────────────────────────────┐
       │                    Effect Ledger (PK: job_id, attempt)   │
       │                 + JobEventEmitter (SSE)                  │
       └────────────────────────────┬────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
         ┌───────────┐      ┌───────────┐       ┌───────────┐
         │  Asset    │      │  Canonical│       │ Authz     │
         │ Service   │      │ Registry  │       │ Service   │
         └─────┬─────┘      └─────┬─────┘       └─────┬─────┘
               │                  │                   │
               ▼                  ▼                   ▼
        ┌────────────┐    ┌────────────┐       ┌────────────┐
        │   MinIO    │    │   Redis    │       │  Postgres  │
        │ (assets/   │    │ (cache,    │       │ (jobs,     │
        │  private/) │    │  queues)   │       │  outbox,   │
        │            │    │            │       │  ledger)   │
        └────────────┘    └────────────┘       └────────────┘
```

---

## 12. 인터페이스 계약 요약

| 컴포넌트 | 주요 메서드 | 반환/효과 |
|---|---|---|
| `CanonicalPaperRegistry` | `resolve(paper_id, version)` | `CanonicalIdentity` |
| `TranslationCacheService` | `lookup(key)`, `store(entry)`, `compose_key(...)` | `TranslationCacheEntry` |
| `ContentJobService` | `submit()`, `get_state()`, `subscribe_events()` | `jobId`, `JobState`, `AsyncGenerator[JobEvent]` |
| `JobEventEmitter` | `emit(event)`, `subscribe(job_id, last_event_id)` | `AsyncGenerator[JobEvent]` |
| `BaseWorker` | `run(message)` | `JobResult` |
| `AssetService` | `issue()`, `issue_presigned()`, `authorize()` | `assetId`, `presigned_url`, `bool` |
| `AuthorizationService` | `recheck(caller, job_id, action)` | `bool` |
| `RateLimitMiddleware` | `__call__(request, call_next)` | `Response` |
| `AssetService` (controller) | `GET /api/v1/assets/{asset_id}?token=` | `307 Redirect` |
| `AuthorizationService` (recheck) | `recheck(caller, job_id, action)` | `bool` (AuthzCache 1분 TTL) |

---

## 13. 데이터 플로우 요약

1. **Client → BFF**: 요청 수신 → `RateLimitMiddleware` → `JobAuthzMiddleware` (SUBMIT)
2. **ContentJobService.submit()**: 멱등성 키 체크 → `ACCEPTED` → ElasticMQ 발행 → `202 {jobId}`
3. **Worker**: ElasticMQ 수신 → `semaphore.acquire()` → `effect_ledger` insert 시도 → 실행 → `COMPLETED/FAILED/ABSTAINED` → `JobEventEmitter.emit()`
4. **SSE**: `JobEventEmitter` → `GET /jobs/{jobId}/events` 스트림 → Client 수신
5. **완료 시**: `AssetService.issue()` → `assetId` 발급 → MinIO 저장 → `JobEventEmitter`로 `COMPLETED` + `assetId` 발행
6. **Client → Asset**: `GET /api/v1/assets/{assetId}?token=` → `AssetService.authorize()` → MinIO presigned → `307 Redirect`
7. **Recheck**: 각 단계에서 `JobAuthzMiddleware` → `AuthorizationService.recheck()` (AuthzCache 1분 TTL) → 권한 없으면 즉시 `FAILED`
6. **메트릭**: 각 단계에서 구조화 JSON 로그 출력 → Prometheus 수집 → Alertmanager 경보
