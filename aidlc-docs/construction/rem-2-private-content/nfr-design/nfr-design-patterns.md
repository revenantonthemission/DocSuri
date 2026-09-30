# REM-2 Private Content — NFR Design Patterns

**단계**: CONSTRUCTION / REM-2 NFR Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: 
- NFR Requirements: `nfr-requirements.md` 승인 (NFR-Q1~13 전수 A)
- NFR Design Questions: ND-Q1~10 전수 A 승인
- Functional Design: `functional-design/` 산출물 완료
- REM-1 런타임 기반: clock ±118µs, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance

---

## PAT-R2-01: Canonical Identity Binding for Cache Keys

**대상**: NFR-Q8, FD-Q2, BR-CACHE-01  
**패턴**: **Canonical Lookup → Key Composition** (ND-Q1 A)

### 구조
```python
class CanonicalPaperRegistry:
    """paperId + version → canonical_id + source_tier 정규화"""
    
    def resolve(self, paper_id: str, version: int) -> CanonicalIdentity:
        # 1. arXiv 우선
        if paper_id.startswith("arxiv:"):
            return CanonicalIdentity(f"arxiv:{paper_id.split(':')[1]}", SourceTier.ARXIV_HTML)
        # 2. Semantic Scholar
        if paper_id.startswith("semantic:"):
            return CanonicalIdentity(f"semantic:{paper_id.split(':')[1]}", SourceTier.SEMANTIC_SCHOLAR_PDF)
        # 3. OpenAlex
        if paper_id.startswith("openalex:"):
            return CanonicalIdentity(f"openalex:{paper_id.split(':')[1]}", SourceTier.OPENALEX_PDF)
        # 4. Private userdoc
        if paper_id.startswith("userdoc:"):
            return CanonicalIdentity(paper_id, SourceTier.USER_UPLOAD)
        raise ValueError(f"Unknown paper_id format: {paper_id}")
```

### Cache Key Composition
```python
def compose_translation_cache_key(
    canonical_id: str,
    version: int,
    source_tier: SourceTier,
    target_lang: str,
    persona_hash: str
) -> str:
    """client source 파라미터 완전 무시, server-verified identity만 사용"""
    return f"translate:{canonical_id}:{version}:{source_tier.value}:{target_lang}:{persona_hash}"
```

**적용 규칙**: Client 제공 `source` 파라미터 완전 무시. Server-verified canonical identity만 cache key에 사용 (BR-CACHE-01, NFR-Q8).

---

## PAT-R2-02: Job State Machine + SSE Event Emission

**대상**: NFR-Q4, FD-Q6, BR-JOB-01~08, ND-Q2  
**패턴**: **Centralized State Machine + Event Emitter** (ND-Q2 A)

### State Machine (불변 전이만 허용)
```python
class JobStateMachine:
    VALID_TRANSITIONS = {
        "SUBMITTED": {"ACCEPTED", "FAILED"},
        "ACCEPTED": {"QUEUED"},
        "QUEUED": {"RUNNING"},
        "RUNNING": {"COMPLETED", "FAILED", "ABSTAINED"},
        # Terminal: COMPLETED, FAILED, ABSTAINED (전환 불가)
    }
    
    def transition(self, job: ContentJob, new_state: str) -> None:
        if new_state not in self.VALID_TRANSITIONS.get(job.state, set()):
            raise InvalidTransition(f"{job.state} → {new_state} 불가")
        old_state = job.state
        job.state = new_state
        job.updated_at = now_us()
        # 동일 트랜잭션에서 이벤트 발행 보장
        self.event_emitter.emit(JobEvent(job.job_id, new_state, now_us(), payload))
```

### Event Emitter + SSE
```python
class JobEventEmitter:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
    
    def emit(self, event: JobEvent) -> None:
        for queue in self._subscribers[event.job_id]:
            queue.put_nowait(event)
        # Outbox 패턴으로 DB에도 기록 (재연결 replay용)
        self.outbox.append(event)
    
    async def subscribe(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[JobEvent, None]:
        # Replay missed events
        if last_event_id:
            for event in self.outbox:
                if event.event_id > last_event_id:
                    yield event
        # Live subscription
        queue = asyncio.Queue()
        self._subscribers[job_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[job_id].remove(queue)
```

**SSE Endpoint**: `GET /jobs/{jobId}/events` with `Last-Event-ID` header for replay (RJ-AC04, ND-Q2 A).

---

## PAT-R2-03: Cache Hit Synchronous Return + AssetId

**대상**: NFR-Q2, FD-Q2, FD-Q3, BR-CACHE-03, ND-Q3  
**패턴**: **Cache Lookup → Sync Return or Job Submit** (ND-Q3 A)

### Flow
```python
async def translate(self, request: TranslateRequest) -> TranslateResponse:
    # 1. Canonical identity 확정
    canonical = self.registry.resolve(request.paper_id, request.version)
    
    # 2. Cache lookup (canonical identity만 사용)
    cache_key = compose_translation_cache_key(
        canonical.canonical_id, request.version, 
        canonical.source_tier, request.target_lang, 
        self.persona_hash(request.persona)
    )
    
    # 3. Cache hit → 동기 즉시 반환
    if cached := await self.cache.get(cache_key):
        return TranslateResponse(
            asset_id=cached.asset_id,
            source="cache",
            source_tier=canonical.source_tier.value
        )
    
    # 4. Cache miss → 비동기 job 접수
    job_id = await self.job_service.submit(
        task_type=TaskType.TRANSLATE,
        input=TranslateInput(...),
        idempotency_key=self.make_idempotency_key(canonical.canonical_id, ...)
    )
    return TranslateResponse(job_id=job_id, state="ACCEPTED")
```

**핵심**: Cache hit 시 **동기 200 반환** (`assetId` 포함), model 미실행 (RJ-AC07, NFR-Q2 A, ND-Q3 A). Miss 시 job 접수 → 202 반환.

---

## PAT-R2-04: Asset Serving — Presigned Redirect

**대상**: FD-Q4, BR-ASSET-01~07, ND-Q4, ND-Q7, ID-Q7  
**패턴**: **Presigned Redirect (307)** (ND-Q4 A, ND-Q7 A, ID-Q7 A)

### Asset Service
```python
class AssetService:
    def issue_presigned(self, asset_id: str, caller: str, action: str = "view") -> str:
        # 1. 권한 재검증 (owner/license/object)
        if not self.authz.recheck(caller, asset_id, "VIEW"):
            raise PermissionError("Asset access denied")
        
        # 2. MinIO presigned GET 생성 (1분 TTL, inline)
        presigned = self.minio.presigned_get_object(
            bucket="docsuri",
            object_name=f"assets/{asset_id}",
            expires=timedelta(minutes=1),
            response_headers={"response-content-disposition": "inline"}
        )
        
        # 3. JWT 토큰 생성 (1분 TTL, nonce 포함)
        token = jwt.encode({
            "assetId": asset_id,
            "action": "view",
            "nonce": uuid4().hex,
            "exp": int(time.time()) + 60,
            "sub": caller
        }, ASSET_JWT_SECRET, algorithm="HS256")
        
        return f"{presigned}&token={token}"
```

### Controller
```python
@router.get("/api/v1/assets/{asset_id}")
async def get_asset(asset_id: str, token: str):
    # 1. JWT 검증
    payload = jwt.decode(token, ASSET_JWT_SECRET, algorithms=["HS256"])
    if payload["assetId"] != asset_id:
        raise HTTPException(403, "Token mismatch")
    
    # 2. 권한 재검증 (owner/license/object)
    if not await asset_service.authorize(payload["sub"], asset_id, "VIEW"):
        raise HTTPException(403, "Asset access denied")
    
    # 3. Presigned URL 생성 후 307 Redirect
    presigned = await asset_service.issue_presigned(asset_id, payload["sub"])
    return RedirectResponse(url=presigned, status_code=307)
```

**CSP**: `Content-Security-Policy: img-src 'self' http://127.0.0.1:9000` (ID-Q7 A).  
**MinIO**: Internal only (`127.0.0.1:9000`), 외부 직접 접근 차단 (ID-Q2 A).

---

## PAT-R2-05: Authorization Recheck Middleware Chain

**대상**: NFR-Q7, FD-Q7, BR-AUTHZ-01~05, ND-Q5  
**패턴**: **Middleware Chain with AuthzCache** (ND-Q5 A)

### Middleware Chain
```python
class JobAuthzMiddleware:
    ACTIONS = ["SUBMIT", "ENQUEUE", "EXECUTE", "STATUS", "EVENT", "ASSET"]
    
    def __init__(self, authz_service: AuthorizationService):
        self.authz = authz_service
    
    async def __call__(self, request: Request, call_next):
        # 1. Job ID 추출 (path/query/body에서)
        job_id = self.extract_job_id(request)
        if not job_id:
            return await call_next(request)  # job 관련 아닌 요청 통과
        
        # 2. Action 결정
        action = self.map_action(request.method, request.url.path)
        
        # 3. 권한 재검증 (AuthzCache 1분 TTL)
        caller = request.state.user_uid
        if not await self.authz.recheck(caller, job_id, action):
            # 권한 만료/철회 → 즉시 FAILED + event 발행 (RJ-AC11)
            await self.emit_failed(job_id, "permission_revoked")
            raise HTTPException(403, "Permission revoked")
        
        return await call_next(request)
```

### AuthzCache (1분 TTL)
```python
class AuthzCache:
    def __init__(self):
        self._cache: dict[str, tuple[bool, float]] = {}  # key -> (allowed, expires_at)
    
    async def check(self, caller: str, job_id: str, action: str) -> bool:
        key = f"{caller}:{job_id}:{action}"
        if key in self._cache:
            allowed, expires = self._cache[key]
            if time.time() < expires:
                return allowed
        
        # DB 조회
        allowed = await self.db.check_permission(caller, job_id, action)
        self._cache[key] = (allowed, time.time() + 60)  # 1분 TTL
        return allowed
```

**적용 지점**: 접수, 큐 진입, 실행 시작, status 조회, event 푸시, asset 전달 — 모든 단계 (BR-AUTHZ-01, NFR-Q7 A).

---

## PAT-R2-06: Idempotency Key + Effect Ledger for Queue Redelivery

**대상**: ND-Q6, ND-Q8, BR-QUEUE-02~03, BR-JOB-04  
**패턴**: **Idempotency Key + Effect Ledger with Attempt Counter** (ND-Q6 A, ND-Q8 A)

### Idempotency Key Generation
```python
def make_idempotency_key(
    canonical_paper_id: str,
    task_type: TaskType,
    input_data: bytes,
    params: JobParams
) -> str:
    input_hash = sha256(input_data).hexdigest()[:16]
    params_hash = sha256(canonical_json(params)).hexdigest()[:16]
    return f"content:{canonical_paper_id}:{task_type.value}:{input_hash}:{params_hash}"
```

### Effect Ledger (중복 차단)
```sql
CREATE TABLE effect_ledger (
    job_id      TEXT NOT NULL,
    attempt     INT  NOT NULL,
    effect_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, attempt)
);
```

### Worker Redelivery Handling
```python
async def process_message(self, message: Message) -> None:
    job_id = message.job_id
    attempt = message.attempt  # ElasticMQ가 관리
    
    # 1. Effect ledger insert 시도 (PK: job_id, attempt)
    try:
        await self.db.execute(
            "INSERT INTO effect_ledger (job_id, attempt, ...) VALUES ($1, $2, ...)",
            job_id, attempt, ...
        )
    except UniqueViolation:
        # 이미 처리된 attempt → skip (멱등)
        logger.info(f"Duplicate attempt skipped: job={job_id}, attempt={attempt}")
        return
    
    # 2. 실제 작업 수행
    result = await self.execute_task(message)
    
    # 3. Job 완료 + ledger commit은 같은 트랜잭션
    await self.db.execute("UPDATE jobs SET state='COMPLETED' WHERE job_id=$1", job_id)
```

**핵심**: `effect_ledger(job_id, attempt)` PK로 중복 차단. Worker crash 시 redelivery 시 `attempt+1`로 재시도, 기완료 attempt는 PK 충돌로 skip (ND-Q8 A, BR-QUEUE-02~03).

---

## PAT-R2-07: Job Authz Recheck Middleware Chain

**대상**: NFR-Q7, FD-Q7, BR-AUTHZ-01~05, ND-Q5  
**패턴**: **Single Middleware Chain with AuthzCache** (ND-Q5 A) — PAT-R2-05와 동일, 별도 문서화

---

## PAT-R2-08: Queue Redelivery Idempotency + Duplicate Effect Prevention

**대상**: ND-Q8, BR-QUEUE-02~03, RESILIENCY-14  
**패턴**: **Effect Ledger + Attempt Counter** (ND-Q8 A) — PAT-R2-06과 동일, 별도 문서화

---

## PAT-R2-09: Property Test Composite Strategy

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
    # Composite scenario 실행
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

**Seed**: `20260930` 고정, shrinking 유지 (ND-Q12 A, CG-Q5 A).

---

## PAT-R2-10: Observability Metrics + Alerting

**대상**: NFR-Q13, NFR-O1  
**패턴**: **Structured JSON Logs + 8 Core Metrics + Alert Rules** (NFR-Q13 A)

### Structured Log Format
```json
{"metric": "job_accepted_total", "labels": {"task_type": "translate"}, "value": 1, "timestamp": "2026-09-30T23:59:59.123456Z"}
{"metric": "job_latency_p95_seconds", "labels": {"task_type": "translate"}, "value": 45.2, "timestamp": "..."}
```

### 8 Core Metrics + Alert Rules
| # | Metric | Alert Condition |
|---|---|---|
| 1 | `job_accepted_total` (rate) | 급증 > 10x baseline for 2m |
| 2 | `job_failed_total` / `job_abstained_total` | 실패율 > 5% for 5m |
| 3 | `job_queue_depth` | 백로그 > 1000 for 2m |
| 4 | `job_latency_p95_seconds` | p95 > 300s for 10m |
| 5 | `asset_delivery_p95_seconds` | p95 > 10s for 5m |
| 6 | `cache_hit_ratio` | < 0.3 for 15m |
| 7 | `queue_redelivery_rate` | > 0.01 for 5m |
| 8 | `authz_recheck_failures_total` | > 0 즉시 (즉시 조사) |

**로그 출력**: stdout JSON lines, CloudWatch/로컬 파일 수집 (NFR-Q13 A).
