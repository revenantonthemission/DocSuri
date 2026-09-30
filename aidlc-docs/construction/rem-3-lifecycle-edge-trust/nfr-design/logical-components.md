# REM-3 Lifecycle and Edge Trust — Logical Components

**단계**: CONSTRUCTION / REM-3 NFR Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `nfr-design-patterns.md` 승인 (ND-Q1~10 전수 A), NFR Requirements, Functional Design

---

## LC-R3-01: PurgeRegistry

**책임**: `purge_registry` 테이블 관리, soft delete → grace period → hard delete 상태 기계  
**인터페이스**:
```python
class PurgeRegistry(Protocol):
    async def request_purge(self, owner_uid: int) -> PurgeRegistryEntry: ...
    async def get_due_purges(self) -> List[PurgeRegistryEntry]: ...
    async def mark_purged(self, owner_uid: int) -> bool: ...
    async def restore(self, owner_uid: int) -> bool: ...

@dataclass(frozen=True)
class PurgeRegistryEntry:
    owner_uid: int
    status: Literal["ACTIVE", "SOFT_DELETED", "PURGED"]
    requested_at: int  # microseconds UTC
    grace_until: int   # microseconds UTC
    purged_at: int | None
    version: int
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/purge.py`  
**의존성**: `asyncpg.Pool` (PostgreSQL)  
**테스트**: `test_purge_registry_property.py` — 상태 전이 불변식, 멱등성, optimistic locking

---

## LC-R3-02: UnsubscribeTokenService

**책임**: HS256 JWT 토큰 발급/검증, Redis cache로 token→job_id 매핑 (PAT-R3-02)  
**인터페이스**:
```python
class UnsubscribeTokenService(Protocol):
    def create_token(self, email: str) -> str: ...
    async def verify_and_consume(self, token: str) -> Optional[str]: ...  # returns job_id
    async def revoke(self, token: str) -> bool: ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/unsubscribe.py`  
**의존성**: `jwt` (HS256), `redis.asyncio`, Keychain에서 secret 로드  
**테스트**: `test_unsubscribe_property.py` — canonical identity binding, client source 무시, cache hit/miss 멱등성

---

## LC-R3-03: RateLimitIdentityService

**책임**: Cloudflare → BFF → FastAPI identity 체인, client identity별 token bucket 관리 (PAT-R3-03)  
**인터페이스**:
```python
class RateLimitIdentityService(Protocol):
    def extract_identity(self, request: Request) -> str: ...
    def get_bucket(self, identity: str, task_type: str) -> TokenBucket: ...
    def consume(self, identity: str, task_type: str) -> bool: ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/identity.py`  
**의존성**: `RateLimitMiddleware`, Redis (token bucket 저장)  
**테스트**: `test_rate_limit_property.py` — identity별 격리, 버킷 리필, 스푸핑 방지

---

## LC-R3-04: PurgeWorker

**책임**: Soft delete → grace period → hard delete 실행, advisory lock으로 동시성 제어 (PAT-R3-04)  
**인터페이스**:
```python
class PurgeWorker(Protocol):
    async def run_once(self) -> int: ...  # returns purged count
    async def process_owner(self, owner_uid: int) -> bool: ...
```

**구현**: `ops/platform-integrity/workers/purge_worker.py`  
**의존성**: `asyncpg.Pool`, `minio` client, `pg_advisory_xact_lock`  
**Launchd**: `rem-2-purge` (매시간 실행, `StartCalendarInterval: Hour=*`)  
**테스트**: `test_purge_worker_property.py` — advisory lock 멱등성, 동시 실행 방지, cascade delete 완전성

---

## LC-R3-05: UnsubscribeTokenService + Endpoint

**책임**: HS256 JWT 발급/검증, Redis cache로 token→job_id 매핑, `GET /unsubscribe` 엔드포인트 (PAT-R3-02)  
**구현**: 
- `platform_integrity/src/docsuri_platform_integrity/adapters/unsubscribe.py`
- `platform_integrity/src/docsuri_platform_integrity/api/unsubscribe.py`

**엔드포인트**: `GET /unsubscribe?token=<jwt>` → JWT 검증 → Redis cache lookup → job_id 반환 또는 400/401/410

---

## LC-R3-05: RateLimitIdentityService + Middleware

**책임**: Cloudflare → BFF → FastAPI identity 체인, token bucket 관리 (PAT-R3-03)  
**구현**: 
- `platform_integrity/src/docsuri_platform_integrity/adapters/identity.py` — `ClientIdentityService`
- `platform_integrity/src/docsuri_platform_integrity/adapters/ratelimit.py` — `RateLimitMiddleware`

---

## LC-R3-06: RevocationService + Pub/Sub

**책임**: Consent/token 철회 발행/구독, 즉시 cache invalidation (PAT-R3-05, PAT-R3-10)  
**인터페이스**:
```python
class RevocationService(Protocol):
    async def revoke(self, token_hash: str, reason: str) -> None: ...
    async def subscribe(self) -> AsyncGenerator[RevocationEvent, None]: ...

@dataclass(frozen=True)
class RevocationEvent:
    token_hash: str
    revoked_at: int  # microseconds UTC
    reason: str
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/revocation.py`  
**Redis Channel**: `revoke:{token_hash}` → `{"token_hash": "...", "revoked_at": us, "reason": "USER_REQUEST"}`

---

## LC-R3-07: AuthzRecheckMiddleware

**책임**: Job 파이프라인 모든 단계에서 권한 재검증, 1분 TTL 캐시 (PAT-R3-06)  
**인터페이스**:
```python
class AuthorizationService(Protocol):
    async def recheck(self, caller: str, job_id: str, action: str) -> bool: ...

class JobAuthzMiddleware:
    ACTIONS = ["SUBMIT", "ENQUEUE", "EXECUTE", "STATUS", "EVENT", "ASSET"]
    async def __call__(self, request: Request, call_next): ...
```

**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/authz.py`  
**AuthzCache**: 1분 TTL, key=`{caller}:{job_id}:{action}` → `(allowed, expires_at)`

---

## LC-R3-08: RevocationSubscriber + Cache Invalidation

**책임**: Redis pub/sub 구독, 즉시 로컬 cache 무효화 (PAT-R3-05, PAT-R3-10)  
**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/revocation.py`

```python
class RevocationSubscriber:
    async def start(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("revoke:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                token_hash = message["channel"].decode().split(":")[1]
                self.cache.pop(f"unsubscribe:{token_hash}", None)
                self.cache.pop(f"consent:{token_hash}", None)
```

---

## LC-R3-09: DependencyAuditMiddleware

**책임**: Purge/Unsubscribe path dependency 별도 lockfile + CI audit gate (PAT-R3-07)  
**구현**: 
- `requirements-purge.txt`, `requirements-unsubscribe.txt` 별도 관리
- `package-purge.json`, `package-unsubscribe.json` 별도 관리
- CI: `pip-audit -r requirements-purge.txt`, `npm audit` + `grype` scan

---

## LC-R3-09: Property Test Suite

**책임**: PBT Full 구현 (PAT-R3-08)  
**파일**:
- `platform_integrity/tests/test_purge_property.py` — purge 상태 기계 불변식
- `platform_integrity/tests/test_unsubscribe_property.py` — token 검증/멱등성
- `platform_integrity/tests/test_revocation_property.py` — revocation 전파 불변식
- `platform_integrity/tests/test_authz_recheck_property.py` — 권한 재검증 불변식
- `platform_integrity/tests/test_queue_redelivery_property.py` — queue redelivery 멱등성
- `ops/tests/test_job_event_order_property.py` — event 순서 보장
- `ops/tests/test_asset_delivery_property.py` — assetId → presigned URL

**Seed**: `20260930` 고정, `derandomize=True`, shrinking 유지

---

## LC-R3-10: ObservabilityMetrics + Alerting

**책임**: 8 핵심 지표 수집, 구조화 JSON 로그 출력, 경보 규칙 (PAT-R3-09)  
**구현**: `platform_integrity/src/docsuri_platform_integrity/adapters/observability.py`

```python
class ObservabilityMetrics:
    def record_job_accepted(self, task_type: str): ...
    def record_job_completed(self, task_type: str, latency_us: int): ...
    def record_job_failed(self, task_type: str, error_type: str): ...
    def record_purge_requested(self): ...
    def record_purge_completed(self, latency_us: int): ...
    def record_unsubscribe_verification(self, latency_ms: int): ...
    def record_revocation_propagation(self, latency_us: int): ...
    def record_authz_recheck_failure(self): ...
    
    def flush(self) -> None:  # stdout JSON lines 출력
```

### Alert Rules (Prometheus/Alertmanager)
```yaml
groups:
- name: rem3-alerts
  rules:
  - alert: PurgeFailureRateHigh
    expr: rate(purge_failed_total[5m]) / rate(purge_completed_total[5m]) > 0.05
    for: 5m
    labels: {severity: critical}
    annotations: {summary: "Purge failure rate > 5%"}
  - alert: PurgeQueueBacklog
    expr: purge_queue_depth > 1000
    for: 2m
  - alert: UnsubscribeLatencyHigh
    expr: histogram_quantile(0.99, rate(unsubscribe_latency_seconds_bucket[5m])) > 0.1
    for: 5m
```

---

## Component Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                         │
│  UnsubscribePage ── ConsentManager ── AccountSettings          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BFF (FastAPI)                            │
│  IdentityMiddleware → RateLimitMiddleware → JobAuthzMiddleware  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ PurgeWorker   │  │ ContentJob    │  │ Revocation    │
│ (launchd)     │  │ Service       │  │ Subscriber    │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL                                 │
│  purge_registry | unsubscribe_tokens | consent_records |        │
│  revocation_events | effect_ledger | jobs | purge_registry      │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌─────────┐   ┌─────────┐   ┌─────────┐
         │  Redis  │   │  MinIO  │   │ElasticMQ│
         │(cache/  │   │ (assets/│   │(queues) │
         │ pub/sub)│   │ purged/)│   │         │
         └─────────┘   └─────────┘   └─────────┘
```

---

## 인터페이스 계약 요약

| 컴포넌트 | 주요 메서드 | 반환/효과 |
|---|---|---|
| `PurgeRegistry` | `request_purge()`, `get_due_purges()`, `mark_purged()`, `restore()` | `PurgeRegistryEntry` |
| `UnsubscribeTokenService` | `create_token()`, `verify_and_consume()`, `revoke()` | `str` (token), `job_id`, `bool` |
| `RateLimitIdentityService` | `extract_identity()`, `get_bucket()`, `consume()` | `str`, `TokenBucket`, `bool` |
| `PurgeWorker` | `run_once()`, `process_owner()` | `int` (purged count), `bool` |
| `RevocationService` | `revoke()`, `subscribe()` | `None`, `AsyncGenerator[RevocationEvent]` |
| `JobAuthzMiddleware` | `__call__(request, call_next)` | `Response` |
| `ObservabilityMetrics` | `record_*()`, `flush()` | `None` (stdout JSON) |

---

## 데이터 플로우 요약

1. **Account Deletion**: `AccountService` → `PurgeRegistry.request_purge()` → `PurgeWorker` (hourly) → cascade delete → `PURGED`
2. **Unsubscribe**: Client → `GET /unsubscribe?token=` → JWT verify → Redis cache → `200` or `202` job
3. **Rate Limit**: Cloudflare → `X-Client-Identity` → BFF proxy → FastAPI `RateLimitMiddleware` → token bucket
3. **Revocation**: API → `RevocationService.revoke()` → Redis `PUBLISH` → Workers `SUBSCRIBE` → cache `DEL`
4. **Authz Recheck**: 각 단계에서 `JobAuthzMiddleware` → `AuthorizationService.recheck()` (1분 TTL cache)
5. **Metrics**: 각 단계에서 `ObservabilityMetrics.record_*()` → stdout JSON → Prometheus
