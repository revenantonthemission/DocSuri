# REM-3 Lifecycle and Edge Trust — Infrastructure Design

**단계**: CONSTRUCTION / REM-3 Infrastructure Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: 
- NFR Design: `nfr-design/` 승인 (ND-Q1~10 전수 A)
- Infrastructure Design Questions: ID-Q1~8 전수 A 승인
- REM-1/2 인프라: launchd, Colima(Postgres/Redis/OpenSearch/SeaweedFS/ElasticMQ), clock, receipt signer, keychain, backup/restore, load acceptance
- `verification-remediation-2026-09-18.md` §2 Single-Mac Production 기준

---

## 0. Corrective note (2026-10-01) — 이 문서의 일부는 실제 승인 구현으로 대체됨

이 문서는 2026-09-30 작성된 초기 설계이며, 이후 승인된 corrective 결정과 어긋나는 부분이 있다.
구현의 정본은 코드와 `rem-3-corrective-plan.md` §3a, `rem-3-duplicate-implementation-decision-questions.md`다.

| 이 문서 | 실제 승인 구현 | 근거 |
|---|---|---|
| §1 `purge_registry` 테이블 + migration 012 | **미채택.** 파기 레지스트리는 기존 `account_deletions`(003) 가 담당. `purge_registry`를 조회하는 코드는 없다. | `grep purge_registry` 0건 |
| `acquire_purge_worker_lock` / `acquire_owner_purge_lock(owner_uid)` | `accounts_try_purge_lock()` (전역 xact try-lock) + `account_deletions.version` 낙관적 잠금. owner별 xact lock 대신 전역 락 + 버전 가드로 구현. | migration 013/014 |
| 인프라 = OrbStack | 런타임은 **Colima**. 로컬 포트는 `ops/local-stack/.env` 로 시프트(15432/16379/19200/19324/19000/19333/18080). | `ops/local-stack/colima-stack.compose.yaml` |
| MinIO | MinIO 이미지 UNOBTAINABLE → 로컬은 **SeaweedFS** 대체, 프로덕션 Pin 유지·마킹. | `ops/platform-integrity/cve-disposition.md` |
| 7개 adapter (`purge`/`unsubscribe`/`identity`/`ratelimit`/`revocation`/`authz`/`assets`) | **삭제됨.** F04/F09/F10은 `backend/` 의 기존 home에 구현. `revocation`/`authz`는 REM-3 범위 밖. | `rem-3-duplicate-implementation-decision-questions.md` |

---

## 1. Purge Registry 테이블 + Migration (ID-Q1 A)

### Migration 012: Purge Registry Table
```sql
-- migrations/012_purge_registry.sql
CREATE TABLE purge_registry (
    owner_uid        INT PRIMARY KEY,
    status           VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    grace_until      TIMESTAMPTZ NOT NULL,
    purged_at        TIMESTAMPTZ,
    version          INT NOT NULL DEFAULT 1,
    CHECK (status IN ('ACTIVE','SOFT_DELETED','PURGED'))
);
CREATE INDEX idx_purge_grace ON purge_registry(grace_until) WHERE status = 'SOFT_DELETED';
```

### Advisory Lock 함수
```sql
-- Advisory lock 함수들
CREATE OR REPLACE FUNCTION acquire_purge_worker_lock() RETURNS BOOLEAN AS $$
BEGIN
    RETURN pg_try_advisory_xact_lock(hashtext('purge_worker'));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION acquire_owner_purge_lock(owner_uid INT) RETURNS BOOLEAN AS $$
BEGIN
    RETURN pg_try_advisory_xact_lock(owner_uid);
END;
$$ LANGUAGE plpgsql;
```

---

## 2. Unsubscribe Token Endpoint + JWT 검증 (ID-Q2 A)

### FastAPI 엔드포인트
```python
# platform_integrity/src/docsuri_platform_integrity/api/unsubscribe.py
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
import jwt
import hashlib

router = APIRouter(prefix="/unsubscribe", tags=["unsubscribe"])

class UnsubscribeResponse(BaseModel):
    status: str
    message: str

@router.get("", response_model=UnsubscribeResponse)
async def unsubscribe(
    token: str = Query(..., description="HS256 JWT unsubscribe token"),
    unsubscribe_service: UnsubscribeTokenService = Depends(get_unsubscribe_service),
):
    """익명 수신 해지 토큰 검증 및 처리"""
    job_id = await unsubscribe_service.verify_and_consume(token)
    if job_id is None:
        # 토큰 검증 실패 (만료/위조/이미 사용됨)
        raise HTTPException(400, "Invalid or expired unsubscribe token")
    
    return UnsubscribeResponse(
        status="success",
        message="Successfully unsubscribed"
    )
```

### JWT Secret Keychain 저장
- Keychain: `rem-2-unsubscribe-jwt.keychain-db`
- Service: `docsuri.rem2.unsubscribe`
- Account: `unsubscribe-jwt`
- HS256 32-byte secret

---

## 3. Rate-Limit Identity 체인: Cloudflare → BFF → FastAPI (ID-Q3 A)

### Cloudflare Workers 설정
```javascript
// Cloudflare Worker script
export default {
  async fetch(request, env, ctx) {
    const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
    const authToken = request.headers.get("Authorization");
    
    // 인증 토큰 검증 (JWT 또는 세션)
    const identity = await verifyIdentity(authToken);
    
    // X-Client-Identity 헤더 설정
    const clientIdentity = identity 
      ? `user:${identity.uid}` 
      : `ip:${sha256(clientIP).substring(0, 16)}`;
    
    const response = await fetch(request, {
      headers: {
        ...Object.fromEntries(request.headers),
        "X-Client-Identity": clientIdentity,
        "CF-Connecting-IP": clientIP,
      }
    });
    
    return response;
  }
}
```

### BFF (FastAPI) Identity Middleware
```python
# platform_integrity/src/docsuri_platform_integrity/adapters/identity.py
class IdentityMiddleware(BaseHTTPMiddleware):
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

---

## 4. Purge Worker: Launchd 서비스 + Advisory Lock (ID-Q4 A)

### Launchd Plist
```xml
<!-- /Library/LaunchDaemons/org.docsuri.rem-2-purge.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.docsuri.rem-2-purge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>-i</string>
        <string>PATH=/usr/bin:/bin</string>
        <string>LANG=en_US.UTF-8</string>
        <string>HOME=/var/empty</string>
        <string>/usr/bin/python3.13</string>
        <string>-B</string>
        <string>/Library/Application Support/DocSuri/rem-2/workers/purge/purge_worker.py</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>*</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Library/Application Support/DocSuri/rem-2/workers/purge</string>
    <key>StandardOutPath</key>
    <string>/Library/Application Support/DocSuri/rem-2/workers/purge/logs/purge.out</string>
    <key>StandardErrorPath</key>
    <string>/Library/Application Support/DocSuri/rem-2/workers/purge/logs/purge.err</string>
    <key>UserName</key>
    <string>root</string>
    <key>GroupName</key>
    <string>wheel</string>
    <key>InitGroups</key>
    <false/>
    <key>Umask</key>
    <integer>63</key>
    <key>ProcessType</key>
    <string>Background</string>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>ExitTimeOut</key>
    <integer>30</integer>
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>256</integer>
        <key>Core</key>
        <integer>0</integer>
    </dict>
    <key>HardResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>256</integer>
        <key>Core</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
```

### Purge Worker 구현
```python
# ops/platform-integrity/workers/purge_worker.py
class PurgeWorker:
    async def run_once(self) -> int:
        # 전역 락으로 단일 실행 보장
        async with self.db.acquire() as conn:
            if not await conn.fetchval("SELECT pg_try_advisory_xact_lock(hashtext('purge_worker'))"):
                return 0  # 이미 실행 중
        
        # 처리 대상 조회
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT owner_uid FROM purge_registry 
                WHERE status = 'SOFT_DELETED' AND grace_until < now()
            """)
        
        purged = 0
        for row in rows:
            owner_uid = row['owner_uid']
            
            # 개별 owner 락
            async with self.db.acquire() as conn:
                try:
                    await conn.execute("SELECT pg_advisory_xact_lock($1)", row['owner_uid'])
                except Exception:
                    continue
                
                # 이미 PURGED인지 확인
                status = await conn.fetchval(
                    "SELECT status FROM purge_registry WHERE owner_uid = $1", row['owner_uid']
                )
                if status == 'PURGED':
                    continue
                
                # Cascade delete 실행
                await self._cascade_delete_owner(owner_uid)
                
                # MinIO 객체 삭제
                await self._delete_minio_objects(owner_uid)
                
                # PURGED 상태로 업데이트
                await conn.execute("""
                    UPDATE purge_registry 
                    SET status = 'PURGED', purged_at = now(), version = version + 1
                    WHERE owner_uid = $1
                """, row['owner_uid'])
                
                purged += 1
        
        return purged
```

---

## 5. Unsubscribe Token Endpoint: Cloudflare Tunnel 경로 (ID-Q5 A)

### Cloudflare Tunnel 설정
```yaml
# cloudflared config.yml
tunnel: rem-2-unsubscribe
credentials-file: /etc/cloudflared/rem-2-unsubscribe.json
ingress:
  - hostname: unsubscribe.docsuri.com
    service: http://127.0.0.1:8000/unsubscribe
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

### Nginx/Cloudflare WAF 규칙
```nginx
# /unsubscribe 경로에 대한 rate limiting
location /unsubscribe {
    limit_req zone=unsubscribe burst=5 nodelay;
    limit_req_zone $binary_remote_addr zone=unsubscribe:10m rate=10r/m;
    
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header X-Client-Identity $http_x_client_identity;
}
```

---

## 6. Consent/Token Revocation: Redis Pub/Sub (ID-Q6 A)

### Redis Pub/Sub 채널
```python
# 채널: revoke:{token_hash}
# 메시지: {"token_hash": "...", "revoked_at": 1234567890123456, "reason": "USER_REQUEST"}
```

### Publisher (철회 API)
```python
async def revoke_token(token_hash: str, reason: str = "USER_REQUEST"):
    await redis.publish(
        f"revoke:{token_hash}",
        json.dumps({
            "token_hash": token_hash,
            "revoked_at": int(time.time() * 1_000_000),
            "reason": reason
        })
    )
    # 로컬 cache 즉시 무효화
    await redis.delete(f"unsubscribe:{token_hash}")
    await redis.delete(f"consent:{token_hash}")
```

### Subscriber (Worker에서 실행)
```python
class RevocationSubscriber:
    async def start(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("revoke:*")
        
        async for message in self.pubsub.listen():
            if message["type"] == "pmessage":
                token_hash = message["channel"].decode().split(":")[1]
                # 로컬 cache 즉시 무효화
                self.cache.pop(f"unsubscribe:{token_hash}", None)
                self.cache.pop(f"consent:{token_hash}", None)
                # 진행 중 job은 다음 authz_recheck에서 감지
```

---

## 7. Cloudflare WAF + Rate-Limit: Ingress Identity 검증 (ID-Q7 A)

### Cloudflare WAF Rules
```yaml
# Cloudflare WAF Custom Rules
rules:
  - id: "rate-limit-unsubscribe"
    expression: '(http.request.uri.path contains "/unsubscribe")'
    action: "rate_limit"
    rate_limit:
      requests_per_minute: 10
      key: "ip"
      
  - id: "block-spoofed-identity"
    expression: '(http.headers["x-client-identity"] != "") and not cf.edge.client_ip_valid'
    action: "block"
    
  - id: "require-client-identity"
    expression: 'not http.headers["x-client-identity"] and not http.request.uri.path contains "/health"'
    action: "challenge"
```

### FastAPI RateLimitMiddleware
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Cloudflare에서 전달된 identity 헤더 검증
        client_identity = request.headers.get("X-Client-Identity")
        if not client_identity:
            raise HTTPException(400, "Missing client identity")
        
        # Identity 파싱
        if client_identity.startswith("user:"):
            identity_type = "user"
            identity_key = client_identity
        elif client_identity.startswith("ip:"):
            identity_type = "ip"
            identity_key = client_identity
        else:
            raise HTTPException(400, "Invalid identity format")
        
        # Token bucket consume
        bucket = self.get_bucket(identity_key, task_type)
        if not bucket.consume(1):
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "1"})
        
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        return response
```

---

## 8. Backup/Restore: Purge 대상 포함 (ID-Q7 A)

### Backup Evidence 수집 확장
```python
# ops/src/docsuri_ops/backup_evidence.py 수정
def collect_backup_evidence(...):
    # 기존 소스에 purge path 추가
    sources = [
        args.source,
        "/Library/Application Support/DocSuri/rem-2/purged/",  # NEW
    ]
    
    for source in sources:
        archive_digest, encrypted, detail = archive.write_archive(source, name=cut.generation)
        # ...
```

### GC에 Purge Path 포함
```python
# ops/src/docsuri_ops/backup_evidence.py
def collect_expired_backups(root: Path, ...):
    for entry in iter_backup_candidates(root):
        if entry.name.startswith("purged_"):
            # Purge된 데이터는 별도 retention 정책 적용
            if is_purge_expired(entry):
                yield entry  # 파기 대상
```

---

## 8. Keychain Secret: Unsubscribe Token Signing Key (ID-Q8 A)

### Keychain 생성
```bash
# Keychain 생성
security create-keychain -p "password" /Library/Application\ Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db

# Secret 추가
security add-generic-password \
  -a "unsubscribe-jwt" \
  -s "docsuri.rem2.unsubscribe" \
  -w "$(openssl rand -base64 32)" \
  /Library/Application\ Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db

# 설정
security set-keychain-settings -l -t 300 /Library/Application\ Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db

# ACL 설정 (worker 계정만 접근)
for account in _docsuri_rem2_translate _docsuri_rem2_summarize _docsuri_rem2_novelty _docsuri_rem2_evidence; do
    security set-key-partition-list -S apple: -k "$account" \
      /Library/Application\ Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db
done
```

### 런타임 사용
```python
# platform_integrity/src/docsuri_platform_integrity/adapters/unsubscribe.py
def get_jwt_secret(self) -> str:
    result = subprocess.run([
        "security", "find-generic-password",
        "-s", "docsuri.rem2.unsubscribe",
        "-a", "unsubscribe-jwt",
        "-w",
        "/Library/Application Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db"
    ], capture_output=True, text=True, check=True)
    return result.stdout.strip()
```

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-ID-Q1~8에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
