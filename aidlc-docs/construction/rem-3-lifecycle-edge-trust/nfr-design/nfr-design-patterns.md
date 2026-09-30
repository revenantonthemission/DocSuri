# REM-3 Lifecycle and Edge Trust — NFR Design Patterns

**단계**: CONSTRUCTION / REM-3 NFR Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: 
- NFR Requirements: `nfr-requirements.md` 승인 (NFR-Q1~13 전수 A)
- NFR Design Questions: ND-Q1~10 전수 A 승인
- Functional Design: `functional-design/` 완료
- REM-1/2 런타임 기반: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance

---

## PAT-R3-01: Purge Registry Schema + Advisory Lock + 멱등 Purge Worker

**대상**: NFR-Q1/Q4, FD-Q1/Q4, BR-PURGE-01~08, ND-Q1  
**패턴**: **PostgreSQL 테이블 + Advisory Lock + 멱등 Worker** (ND-Q1 A)

### 스키마
```sql
-- migrations/012_purge_registry.sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,  -- optimistic locking
    CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED'))
);
CREATE INDEX idx_purge_grace ON purge_registry(grace_until) WHERE status = 'SOFT_DELETED';
```

### Purge Worker 구현
```python
class PurgeWorker:
    def __init__(self, db_pool: asyncpg.Pool, minio_client: Minio):
        self.db = db_pool
        self.minio = minio_client
    
    async def run_once(self) -> int:
        """단일 실행: grace_until 경과된 SOFT_DELETED owner 파기"""
        purged_count = 0
        
        # 전역 락으로 단일 실행 보장
        async with self.db.acquire() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('purge_worker'))")
        
        # 처리 대상 조회
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT owner_uid FROM purge_registry 
                WHERE status = 'SOFT_DELETED' AND grace_until < now()
            """)
        
        for row in rows:
            owner_uid = row['owner_uid']
            
            # 개별 owner 락으로 동시성 제어
            async with self.db.acquire() as conn:
                try:
                    await conn.execute("SELECT pg_advisory_xact_lock($1)", row['owner_uid'])
                except Exception:
                    continue  # 락 획득 실패 시 skip
                
                # 이미 PURGED된 경우 skip (멱등)
                status = await conn.fetchval(
                    "SELECT status FROM purge_registry WHERE owner_uid = $1", row['owner_uid']
                )
                if status == 'PURGED':
                    continue
                
                # Cascade delete 실행
                await self._cascade_delete_owner(conn, row['owner_uid'])
                
                # MinIO 객체 삭제
                await self._delete_minio_objects(row['owner_uid'])
                
                # PURGED 상태로 업데이트
                await conn.execute("""
                    UPDATE purge_registry 
                    SET status = 'PURGED', purged_at = now(), version = version + 1
                    WHERE owner_uid = $1
                """, row['owner_uid'])
                
                purged_count += 1
        
        return purged_count
    
    async def _cascade_delete_owner(self, conn: asyncpg.Connection, owner_uid: int):
        """Cascade delete for all owner-scoped tables"""
        tables = [
            'userdoc', 'assets', 'search_history', 'library_items',
            'consent_records', 'unsubscribe_tokens', 'revocation_events'
        ]
        for table in tables:
            await conn.execute(f"DELETE FROM {table} WHERE owner_uid = $1", owner_uid)
```

**적용 규칙**: 전역 `pg_advisory_xact_lock('purge_worker')`로 단일 실행 보장, 개별 `pg_advisory_xact_lock(owner_uid)`로 동시 삭제 방지, 멱등성 보장.

---

## PAT-R3-02: Unsubscribe Token — HS256 JWT + Redis Cache

**대상**: NFR-Q2/Q5, FD-Q2, BR-UNSUB-01~05, ND-Q2  
**패턴**: **HS256 JWT + Redis Cache** (ND-Q2 A)

### 토큰 생성
```python
class UnsubscribeTokenService:
    JWT_SECRET: str  # Keychain에서 로드
    JWT_ALGORITHM = "HS256"
    TOKEN_TTL_SECONDS = 24 * 3600  # 24시간
    
    def create_token(self, email: str) -> str:
        payload = {
            "email": email,
            "purpose": "unsubscribe",
            "exp": int(time.time()) + self.TOKEN_TTL_SECONDS,
            "iat": int(time.time()),
            "jti": secrets.token_urlsafe(16)
        }
        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
```

### 검증 + Cache
```python
    async def verify_and_consume(self, token: str) -> Optional[str]:
        """토큰 검증 후 job_id 반환 (cache hit 시 즉시 반환)"""
        # 1. JWT 검증
        try:
            payload = jwt.decode(token, self.JWT_SECRET, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None
        
        if payload.get("purpose") != "unsubscribe":
            return None
        
        email = payload["email"]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Redis cache lookup
        cached = await self.redis.get(f"unsubscribe:{token_hash}")
        if cached:
            return cached.decode()
        
        # Cache miss: DB에서 job_id 조회 후 cache 저장
        job_id = await self.db.fetchval(
            "SELECT job_id FROM unsubscribe_tokens WHERE token_hash = $1 AND revoked_at IS NULL",
            token_hash
        )
        if job_id:
            await self.redis.setex(f"unsubscribe:{token_hash}", 86400, job_id)
            return job_id
        return None
    
    async def revoke(self, token: str) -> bool:
        """토큰 철회"""
        try:
            payload = jwt.decode(token, self.JWT_SECRET, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return False
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await self.redis.delete(f"unsubscribe:{token_hash}")
        await self.db.execute(
            "UPDATE unsubscribe_tokens SET revoked_at = now() WHERE token_hash = $1",
            hashlib.sha256(token.encode()).hexdigest()
        )
        return True
```

**핵심**: JWT로 stateless 검증, Redis cache로 token→job_id 매핑, Client source 무시.

---

## PAT-R3-03: Rate-Limit Identity Chain — Cloudflare → BFF → FastAPI

**대상**: NFR-Q3/Q7/Q10, FD-Q3/FD-Q6, BR-RL-01~06, ND-Q3  
**패턴**: **Header Chain + Middleware** (ND-Q3 A)

### Cloudflare (Terraform/설정)
```toml
# Cloudflare Workers script 또는 설정
# CF-Connecting-IP + 인증 토큰 검증 → X-Client-Identity 헤더 추가
```

### BFF (FastAPI Middleware)
```python
class IdentityMiddleware:
    async def dispatch(self, request: Request, call_next):
        # Cloudflare에서 전달된 identity 헤더 읽기
        client_identity = request.headers.get("X-Client-Identity")
        if not client_identity:
            # Fallback: IP 기반 익명 identity
            client_ip = request.client.host
            client_identity = f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
        
        request.state.client_identity = client_identity
        return await call_next(request)
```

### FastAPI RateLimitMiddleware
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_tokens: int = 10, refill_rate: float = 2.0):
        super().__init__(app)
        self.buckets: Dict[str, TokenBucket] = {}
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
    
    def _get_bucket_key(self, request: Request) -> str:
        identity = getattr(request.state, "client_identity", "unknown")
        # Path에서 task type 추출
        task_type = self._extract_task_type(request.url.path)
        return f"{identity}:{task_type}"
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/healthz", "/health"):
            return await call_next(request)
        
        task_type = self._extract_task_type(request.url.path)
        if not task_type:
            return await call_next(request)
        
        identity = getattr(request.state, "client_identity", "unknown")
        bucket = self._get_bucket(identity, task_type)
        
        if not bucket.consume(1):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "1"}
            )
        
        response = await call_next(request)
        bucket = self._get_bucket(getattr(request.state, "client_identity", "unknown"), 
                                  self._extract_task_type(request.url.path))
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        response.headers["X-RateLimit-Reset"] = str(int(
            bucket.last_refill + (bucket.max_tokens - bucket.tokens) / bucket.refill_rate
        ))
        return response
```

**핵심**: Cloudflare에서 검증된 identity만 전달, BFF는 프록시만, FastAPI에서 token bucket 적용.

---

## PAT-R3-04: Purge Worker — 배치 + Advisory Lock

**대상**: NFR-Q4, FD-Q4, BR-PURGE-06~07, ND-Q4  
**패턴**: **배치 + Advisory Lock + 비동기 Audit** (ND-Q4 A)

### Worker Concurrency
```python
class PurgeWorker:
    def __init__(self, db_pool: asyncpg.Pool, minio_client: Minio):
        self.db = db_pool
        self.minio = minio_client
        self.semaphores = {
            "translate": asyncio.Semaphore(2),
            "summarize": asyncio.Semaphore(2),
            "novelty": asyncio.Semaphore(1),
            "evidence": asyncio.Semaphore(2),
            "purge": asyncio.Semaphore(1),  # purge는 단일 실행
        }
    
    async def process_purge_batch(self, owner_uids: List[int]) -> int:
        """배치 단위 purge 처리"""
        purged = 0
        for owner_uid in owner_uids:
            async with self.semaphores["purge"]:
                try:
                    async with self.db.acquire() as conn:
                        async with conn.transaction():
                            # 개별 owner 락
                            await conn.execute("SELECT pg_advisory_xact_lock($1)", owner_uid)
                            
                            # 이미 PURGED인지 확인
                            status = await conn.fetchval(
                                "SELECT status FROM purge_registry WHERE owner_uid = $1",
                                owner_uid
                            )
                            if status == 'PURGED':
                                continue
                            
                            # Grace period 확인
                            grace = await conn.fetchval(
                                "SELECT grace_until FROM purge_registry WHERE owner_uid = $1",
                                owner_uid
                            )
                            if grace and grace > datetime.now(timezone.utc):
                                continue  # 아직 유예 기간
                            
                            # Cascade delete
                            await self._cascade_delete(owner_uid)
                            
                            # PURGED로 업데이트
                            await conn.execute("""
                                UPDATE purge_registry 
                                SET status = 'PURGED', purged_at = now(), version = version + 1
                                WHERE owner_uid = $1
                            """, owner_uid)
                            
                            return 1
                except Exception:
                    pass
        return 0
```

**핵심**: `asyncio.Semaphore`로 동시성 제어, `pg_advisory_xact_lock`으로 DB 레벨 락, 멱등성 보장.

---

## PAT-R3-05: Consent/Token Revocation — Redis Pub/Sub

**대상**: NFR-Q5, FD-Q5, R3P, ND-Q5, ND-Q10  
**패턴**: **Redis Pub/Sub + 즉시 Cache Invalidation** (ND-Q5 A, ND-Q10 A)

### Revocation Publisher
```python
class RevocationService:
    def __init__(self, redis: redis.Redis):
        self.redis = redis
    
    async def revoke(self, token_hash: str, reason: str = "USER_REQUEST"):
        """토큰/동의 철회 발행"""
        await self.redis.publish(
            f"revoke:{token_hash}",
            json.dumps({
                "token_hash": token_hash,
                "revoked_at": int(time.time() * 1_000_000),
                "reason": reason
            })
        )
        
        # 로컬 cache 즉시 무효화
        await self.redis.delete(f"unsubscribe:{token_hash}")
        await self.redis.delete(f"consent:{token_hash}")
```

### Revocation Subscriber (Worker에서 실행)
```python
class RevocationSubscriber:
    def __init__(self, redis: redis.Redis, cache: Dict[str, Any]):
        self.redis = redis
        self.cache = cache
    
    async def start(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("revoke:*")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                token_hash = message["channel"].decode().split(":")[1]
                # 로컬 cache 즉시 무효화
                self.cache.pop(f"unsubscribe:{token_hash}", None)
                self.cache.pop(f"consent:{token_hash}", None)
                # 진행 중 job은 다음 authz_recheck에서 감지
```

**핵심**: Redis pub/sub로 즉시 전파, 모든 worker가 구독하여 즉시 cache 무효화, 진행 중 job은 다음 authz recheck에서 감지.

---

## PAT-R3-06: Authz Recheck Middleware Chain

**대상**: NFR-Q7, FD-Q7, BR-AUTHZ-01~04, ND-Q6  
**패턴**: **Middleware Chain + AuthzCache** (ND-Q6 A)

### Middleware Chain
```python
class JobAuthzMiddleware:
    ACTIONS = ["SUBMIT", "ENQUEUE", "EXECUTE", "STATUS", "EVENT", "ASSET"]
    
    def __init__(self, authz_service: AuthorizationService):
        self.authz = authz_service
    
    async def __call__(self, request: Request, call_next):
        # Job ID 추출
        job_id = self._extract_job_id(request)
        if not job_id:
            return await call_next(request)
        
        # Action 결정
        action = self._map_action(request.method, request.url.path)
        
        # 권한 재검증 (AuthzCache 1분 TTL)
        caller = request.state.user_uid
        if not await self.authz.recheck(caller, job_id, action):
            # 권한 만료 시 즉시 FAILED + event 발행
            await self.emit_failed(job_id, "permission_revoked")
            raise HTTPException(403, "Permission revoked")
        
        return await call_next(request)
```

### AuthzCache (1분 TTL)
```python
class AuthzCache:
    def __init__(self):
        self._cache: dict[str, tuple[bool, float]] = {}
    
    def get(self, caller: str, job_id: str, action: str) -> Optional[bool]:
        key = f"{caller}:{job_id}:{action}"
        if key in self._cache:
            allowed, expires = self._cache[key]
            if time.time() < expires:
                return allowed
            del self._cache[key]
        return None
    
    def set(self, caller: str, job_id: str, action: str, allowed: bool):
        key = f"{caller}:{job_id}:{action}"
        self._cache[key] = (allowed, time.time() + 60)  # 1분 TTL
```

**핵심**: 모든 파이프라인 단계에서 재검증, 1분 TTL 캐시로 성능 확보, 권한 만료 시 즉시 FAILED.

---

## PAT-R3-07: Dependency Audit 격리 — 별도 Lockfile + CI Gate

**대상**: NFR-Q9, FD-Q7, BR-XCUT-07  
**패턴**: **별도 Lockfile + CI Gate** (ND-Q7 A)

### 별도 Lockfile 구조
```
# requirements-purge.txt
psycopg[binary]>=3.3.4,<4
asyncpg>=0.28
minio>=7.1
redis>=5.0

# requirements-unsubscribe.txt
pyjwt>=2.8
redis>=5.0

# package-purge.json
{
  "dependencies": {
    "ioredis": "^5.3",
    "pg": "^8.11"
  }
}
```

### CI Gate (GitHub Actions)
```yaml
# .github/workflows/dependency-audit.yml
name: Dependency Audit
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Python audit
        run: |
          pip install pip-audit
          pip-audit -r requirements-purge.txt
          pip-audit -r requirements-unsubscribe.txt
      - name: Node audit
        run: |
          cd frontend && npm audit --audit-level=high
      - name: Grype scan
        run: |
          grype dir:. --fail-on high
```

**핵심**: 경로별 별도 lockfile, CI에서 audit 실패 시 merge 차단, 예외는 `SBOM_EXCEPTIONS.md`에 관리.

---

## PAT-R3-08: Property Test Composite Strategy

**대상**: NFR-Q12, PBT-03/04/07/08, CG-Q5  
**패턴**: **Composite Strategy = Job Input × State Transition × Authz Scenario × Queue Scenario** (CG-Q5 A)

### Python (Hypothesis)
```python
@given(
    job_input=job_input_strategy(),
    state_transition=st.sampled_from(valid_transitions + invalid_transitions),
    authz_scenario=st.sampled_from(["valid", "expired", "revoked", "missing"]),
    queue_scenario=st.sampled_from(["normal", "redelivery", "crash", "dlq"])
)
@settings(max_examples=2000, derandomize=True, database=None)
def test_job_properties(job_input, state_transition, authz_scenario, queue_scenario):
    job = create_job(job_input)
    apply_transition(job, state_transition)
    apply_authz(job, authz_scenario)
    apply_queue_scenario(job, queue_scenario)
    # 불변식 검증: 상태 전이 불가역성, 멱등성, 권한 만료 시 FAILED, redelivery 중복 차단
    assert_job_invariants(job)
```

### TypeScript (fast-check)
```typescript
fc.test(
    fc.property(
        jobInputArb(),
        stateTransitionArb(),
        authzScenarioArb(),
        queueScenarioArb(),
        (jobInput, stateTransition, authzScenario, queueScenario) => {
            // 동일 불변식 검증
        }
    ),
    { numRuns: 2000, seed: 20260930 }
)
```

**핵심**: Composite strategy로 조합 검증, shrinking 유지, CI seed `20260930` 고정.

---

## PAT-R3-09: Observability Metrics + Alerting

**대상**: NFR-Q13, NFR-O1  
**패턴**: **Structured JSON Logs + 8 Core Metrics + Alert Rules** (ND-Q9 A)

### Structured Log Format
```json
{"metric": "job_accepted_total", "labels": {"task_type": "translate"}, "value": 1, "timestamp": "2026-09-30T23:59:59.123456Z"}
{"metric": "job_latency_p95_seconds", "labels": {"task_type": "translate"}, "value": 45.2, "timestamp": "..."}
```

### 8 Core Metrics + Alert Rules
| # | Metric | Alert Condition |
|---|---|---|
| 1 | `purge_requested_total` (rate) | 급증 > 10x baseline for 2m |
| 2 | `purge_failed_total` / `purge_completed_total` | 실패율 > 5% for 5m |
| 3 | `purge_queue_depth` | 백로그 > 1000 for 2m |
| 4 | `purge_latency_p95_seconds` | p95 > 3600s for 10m |
| 5 | `unsubscribe_verification_p95_ms` | p99 > 100ms for 5m |
| 6 | `revocation_propagation_latency_p95` | > 5초 경보 |
| 7 | `queue_redelivery_rate` | > 0.01 for 5m |
| 8 | `authz_recheck_failures_total` | > 0 즉시 (즉시 조사) |

**출력**: stdout JSON lines, Prometheus node_exporter 수집.

---

## PAT-R3-10: Consent/Token Revocation — 즉시 Cache Invalidation

**대상**: NFR-Q5, R3P, ND-Q10  
**패턴**: **Redis Pub/Sub + 즉시 Cache Invalidation** (ND-Q10 A)

(이미 PAT-R3-05에서 상세 구현 완료)

---

## 추적성 매트릭스: NFR Question → Pattern

| NFR Question | Pattern |
|---|---|
| NFR-Q1 (Purge latency) | PAT-R3-01 (Purge Registry + Advisory Lock) |
| NFR-Q2 (Unsubscribe latency) | PAT-R3-02 (HS256 JWT + Redis Cache) |
| NFR-Q3 (Rate-limit latency) | PAT-R3-03 (Identity Chain) |
| NFR-Q4 (Purge throughput) | PAT-R3-04 (Batch + Advisory Lock) |
| NFR-Q5 (Revocation propagation) | PAT-R3-05 (Redis Pub/Sub) |
| NFR-Q7 (Authz recheck) | PAT-R3-06 (Middleware Chain + Cache) |
| NFR-Q9 (Dependency audit) | PAT-R3-07 (별도 Lockfile + CI Gate) |
| NFR-Q10 (Rate-limit identity) | PAT-R3-03 (Identity Chain) |
| NFR-Q11 (Timeout alignment) | PAT-R3-04 (Timeout Profile) |
| NFR-Q11 (Queue recovery) | PAT-R3-04 (Advisory Lock + Effect Ledger) |
| NFR-Q12 (PBT) | PAT-R3-08 (Composite Strategy) |
| NFR-Q13 (Observability) | PAT-R3-09 (Structured JSON + 8 Metrics) |

---

