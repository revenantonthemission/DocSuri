# REM-3 Lifecycle and Edge Trust — Business Logic Model

**단계**: CONSTRUCTION / REM-3 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `domain-entities.md`, FD-Q1~8 승인 (전수 A)

---

## 1. Purge Lifecycle Flow (F04, R3C)

### 1.1 Account Deletion Request → Soft Delete

```mermaid
sequenceDiagram
    participant User
    participant AccountService
    participant PurgeRegistry
    participant BackupService
    
    User->>AccountService: DELETE /account (password 확인)
    AccountService->>AccountService: 비밀번호 재인증 (FR-26)
    AccountService->>PurgeRegistry: INSERT SOFT_DELETED (grace_until = now + 30일)
    AccountService->>AccountService: 계정 비활성화 (IsHidden=1, 세션 무효화)
    AccountService->>BackupService: SOFT_DELETED 상태 백업 예약
    AccountService-->>User: 200 {state: "SOFT_DELETED", grace_until}
```

### 1.2 Grace Period → Hard Delete (Purge Worker)

```mermaid
sequenceDiagram
    participant Scheduler
    participant PurgeWorker
    participant PurgeRegistry
    participant DB
    participant MinIO
    participant BackupService
    
    Scheduler->>PurgeWorker: 매시간 트리거 (StartCalendarInterval: Hour=*)
    PurgeWorker->>PurgeWorker: pg_advisory_xact_lock('purge_worker')
    PurgeWorker->>PurgeRegistry: SELECT * WHERE status=SOFT_DELETED AND grace_until < now
    loop 각 owner_uid
        PurgeWorker->>PurgeWorker: pg_advisory_xact_lock(owner_uid)
        PurgeWorker->>DB: cascade DELETE (CASCADE 제약)
        PurgeWorker->>MinIO: mc rm --recursive private/userdoc/{owner}/ assets/{owner}/
        PurgeWorker->>BackupService: purge 대상 백업에서 제거 (gc --apply)
        PurgeWorker->>PurgeRegistry: UPDATE status=PURGED, purged_at=now
    end
    PurgeWorker->>PurgeWorker: pg_advisory_xact_unlock('purge_worker')
```

**핵심 규칙 (FD-Q1 A, FD-Q4 A)**:
- `pg_advisory_xact_lock`으로 동시 실행 방지 + 개별 owner 락
- `ON DELETE CASCADE` + application-level cascade로 완전 파기
- 재실행 멱등: 이미 `PURGED`면 skip

---

## 2. Unsubscribe Token Flow (F09, FD-Q2)

### 2.1 Token 발급

```mermaid
sequenceDiagram
    participant User
    participant EmailService
    participant UnsubscribeTokenService
    participant Redis
    
    EmailService->>UnsubscribeTokenService: create_token(email, purpose="unsubscribe")
    UnsubscribeTokenService->>UnsubscribeTokenService: HS256 JWT 생성 (email, purpose, exp=24h)
    UnsubscribeTokenService->>Redis: SETEX unsubscribe:{token_hash} 86400 "pending"
    UnsubscribeTokenService-->>EmailService: token 반환
    EmailService-->>User: 이메일에 unsubscribe 링크 포함 발송
```

### 2.2 Token 검증 + 수신 해지

```mermaid
sequenceDiagram
    participant User
    participant UnsubscribeEndpoint
    participant Redis
    participant DB
    
    User->>UnsubscribeEndpoint: GET /unsubscribe?token=<jwt>
    UnsubscribeEndpoint->>UnsubscribeTokenService: verify(token)
    alt 유효
        UnsubscribeTokenService->>Redis: GET unsubscribe:{token_hash}
        alt Cache Hit
            Redis-->>UnsubscribeTokenService: job_id 반환
        else Cache Miss
            UnsubscribeTokenService->>DB: SELECT job_id FROM unsubscribe_tokens WHERE token_hash=?
            Redis->>UnsubscribeTokenService: SETEX 86400
        end
        UnsubscribeTokenService->>DB: UPDATE subscriptions SET status='UNSUBSCRIBED' WHERE email=?
        Redis->>UnsubscribeTokenService: DEL unsubscribe:{token_hash}
        UnsubscribeTokenService-->>User: 200 "수신 해지 완료"
    else 무효/만료/철회
        UnsubscribeTokenService-->>User: 400/401/410 적절한 에러
    end
```

**핵심 규칙 (FD-Q2 A, ND-Q2 A)**:
- HS256 JWT로 토큰 자체에 payload 포함 (stateless 검증 가능)
- Redis cache로 token→job_id 매핑, DB lookup 최소화
- 토큰 1회용, 검증 후 즉시 Redis에서 삭제

---

## 3. Rate-Limit Identity Chain (F10, FD-Q3, FD-Q6)

### 3.1 Identity Chain Flow

```mermaid
sequenceDiagram
    participant Cloudflare
    participant BFF
    participant FastAPI
    participant RateLimitMiddleware
    
    Client->>Cloudflare: Request
    Cloudflare->>Cloudflare: CF-Connecting-IP + 인증 토큰 검증
    Cloudflare->>BFF: X-Client-Identity: user:{uid} 또는 ip:{hash}
    BFF->>FastAPI: X-Client-Identity 헤더 프록시
    FastAPI->>RateLimitMiddleware: identity 추출
    RateLimitMiddleware->>RateLimitMiddleware: token bucket consume
    alt 허용
        FastAPI->>Handler: Request 처리
    else 거부
        RateLimitMiddleware-->>Client: 429 + Retry-After
    end
```

**핵심 규칙 (FD-Q3 A, FD-Q6 A, ND-Q3 A)**:
- Cloudflare에서 `CF-Connecting-IP` + 인증 토큰 검증 후 `X-Client-Identity` 헤더 설정
- BFF는 헤더만 프록시, 검증하지 않음
- FastAPI `RateLimitMiddleware`가 identity별 token bucket 적용
- Identity: 인증 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`

---

## 4. Consent/Token Revocation + Redis Pub/Sub (R3P, FD-Q5, ND-Q5)

### 4.1 Revocation 발행

```mermaid
sequenceDiagram
    participant Admin
    participant RevocationService
    participant Redis
    participant Workers
    
    Admin->>RevocationService: revoke_token(token_hash, reason)
    RevocationService->>DB: UPDATE consent SET revoked_at=now, status='REVOKED'
    RevocationService->>Redis: PUBLISH revoke:{token_hash} '{"revoked_at": now}'
    Redis->>Workers: SUBSCRIBE revoke:* → 수신 즉시 로컬 cache DEL
    Workers->>Workers: 진행 중 job 다음 authz_recheck에서 감지 → FAILED
    Workers->>Workers: SSE 연결 시 permission_revoked event 수신 → 즉시 종료
```

**핵심 규칙 (FD-Q5 A, ND-Q5 A, ND-Q10 A)**:
- Redis pub/sub로 즉시 전파 (지연 없음)
- 모든 worker가 `SUBSCRIBE revoke:*` 구독
- 수신 즉시 로컬 cache `DEL`, 진행 중 작업은 다음 authz recheck에서 차단
- SSE 연결은 `permission_revoked` event 수신 시 즉시 종료

---

## 5. Consent/Token Lifecycle (R3P, FD-Q5, FD-Q8)

### 5.1 Consent Grant → Revoke → Expire

```mermaid
stateDiagram-v2
    [*] --> GRANTED: 사용자 동의
    GRANTED --> REVOKED: 사용자 철회 / 관리자 철회
    GRANTED --> EXPIRED: 만료일 경과
    REVOKED --> [*]: 철회 완료
    EXPIRED --> [*]: 만료 완료
```

**핵심 규칙 (FD-Q5 A, FD-Q8 A)**:
- `GRANTED` → `REVOKED` (즉시, `revoked_at` 설정)
- `GRANTED` → `EXPIRED` (만료일 경과 시 자동)
- 철회 시 Redis pub/sub로 즉시 전파, 토큰 즉시 무효화

---

## 6. Account Lifecycle (FR-26/27/28/44~46, FD-Q8)

### 6.1 Account Deletion: Soft Delete → Grace → Hard Delete

```mermaid
sequenceDiagram
    participant User
    participant AccountService
    participant PurgeRegistry
    participant PurgeWorker
    
    User->>AccountService: DELETE /account (password 확인)
    AccountService->>AccountService: 비밀번호 재인증 (FR-26)
    AccountService->>PurgeRegistry: INSERT SOFT_DELETED (grace_until = now + 30일)
    AccountService->>AccountService: 계정 비활성화 (IsHidden=1, 세션 무효화)
    AccountService-->>User: 200 {state: "SOFT_DELETED", grace_until}
    
    Note over PurgeWorker: grace_until 경과 후
    PurgeWorker->>PurgeRegistry: SELECT SOFT_DELETED WHERE grace_until < now
    PurgeWorker->>DB: cascade DELETE (ON DELETE CASCADE)
    PurgeWorker->>MinIO: mc rm --recursive user data
    PurgeWorker->>Backup: purge 대상 백업에서 제거
    PurgeWorker->>PurgeRegistry: UPDATE PURGED
```

### 6.2 Password Reset (FR-26)

```mermaid
sequenceDiagram
    User->>AccountService: POST /account/password-reset (email)
    AccountService->>EmailService: 단일 사용 30분 토큰 발송
    User->>AccountService: POST /account/password-reset/confirm (token, new_password)
    AccountService->>AccountService: 토큰 검증 → 비밀번호 해시 갱신 → 전 세션 무효화
```

### 6.3 Social Login (Google/ORCID) (FR-27)

```mermaid
sequenceDiagram
    User->>AccountService: GET /auth/google 또는 /auth/orcid
    AccountService->>Provider: OIDC Authorization Code 흐름
    Provider-->>AccountService: 인증 코드
    AccountService->>Provider: 토큰 교환 (JWKS 검증)
    alt 이메일 제공 (Google)
        AccountService->>AccountService: 검증된 이메일로 기존 계정 자동 연결 / 신규 생성
    else 이메일 미제공 (ORCID)
        AccountService->>AccountService: (provider, subject) 신원으로 계정 생성 (이메일 NULL 허용)
    end
    AccountService->>AccountService: 세션 발급 (동일 secure/httpOnly/sameSite 쿠키)
```

### 6.3 Account Management (FR-28)

```mermaid
sequenceDiagram
    User->>AccountService: PUT /account/password (현재 비번, 새 비번)
    User->>AccountService: PUT /account/email (새 이메일 → 재검증 후 반영)
    User->>AccountService: DELETE /account (soft delete → grace → hard delete)
```

---

## 7. Edge Trust: Ingress Identity + Rate-Limit (R3E, FD-Q6)

### 7.1 Ingress Identity Verification

```mermaid
sequenceDiagram
    participant Cloudflare
    participant BFF
    participant FastAPI
    
    Client->>Cloudflare: Request
    Cloudflare->>Cloudflare: CF-Connecting-IP + 인증 토큰 검증
    Cloudflare->>BFF: X-Client-Identity 헤더 추가
    BFF->>FastAPI: X-Client-Identity 헤더 프록시
    FastAPI->>RateLimitMiddleware: identity 추출
    FastAPI->>RateLimitMiddleware: identity별 token bucket consume
    alt 허용
        FastAPI->>Handler: Request 처리
    else 거부
        RateLimitMiddleware-->>Client: 429 + Retry-After
    end
```

**핵심 규칙 (FD-Q6 A, ND-Q3 A, ND-Q6 A)**:
- Cloudflare에서 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더
- BFF는 헤더만 프록시, 검증 안 함
- FastAPI `RateLimitMiddleware`가 identity별 token bucket 적용
- 동일 identity 동일 버킷, spoofing 불가

---

## 8. Backup/Restore: Purge 대상 포함 (ID-Q7)

```mermaid
sequenceDiagram
    participant BackupService
    participant PurgeWorker
    participant MinIO
    
    BackupService->>MinIO: 일일 03:00 백업 (corpus/, private/userdoc/, assets/, purged/)
    PurgeWorker->>MinIO: purge 시 mc rm --recursive purged/{owner}/
    PurgeWorker->>BackupService: gc --apply로 해당 owner 데이터만 제거
    BackupService->>BackupService: gc --apply --approve-critical로 영구 파기
```

---

## 9. Keychain Provisioning: Unsubscribe JWT Signing Key (ID-Q8)

```mermaid
sequenceDiagram
    participant Operator
    provision_rem2_keys.py
    Keychain
    
    Operator->>provision_rem2_keys.py: --profile test
    provision_rem2_keys.py->>Keychain: create-keychain -p password
    provision_rem2_keys.py->>Keychain: add-generic-password -s docsuri.rem2.unsubscribe -a unsubscribe-jwt -w <32-byte-secret>
    provision_rem2_keys.py->>Keychain: set-keychain-settings -l -t 300
    provision_rem2_keys.py->>Keychain: set-key-partition-list -S apple: -k ...
    Keychain-->>Operator: All Keychains provisioned successfully
```

---

## 9. Traceability Matrix

| FD Question | Domain Entity | Business Flow | Scenario | Business Rule |
|---|---|---|---|---|
| FD-Q1 (purge) | `PurgeRegistry`, `AccountLifecycleState` | 1.1, 1.2, 6.1 | SC-PURGE-01, SC-PURGE-02 | BR-PURGE-01~07 |
| FD-Q2 (unsubscribe) | `UnsubscribeToken` | 2.1, 2.2 | SC-UNSUB-01, SC-UNSUB-02 | BR-UNSUB-01~04 |
| FD-Q3 (rate-limit) | `RateLimitBucket`, `ClientIdentity` | 3.1 | SC-RL-01 | BR-RL-01~04 |
| FD-Q4 (purge lifecycle) | `PurgeRegistry`, `AccountLifecycleState` | 1.2, 6.1 | SC-PURGE-02, SC-PURGE-03 | BR-PURGE-08 |
| FD-Q5 (consent) | `ConsentRecord`, `RevocationEvent` | 4.1, 5.1 | SC-CONSENT-01, SC-REV-01 | BR-CONSENT-01~04 |
| FD-Q6 (edge trust) | `ClientIdentity`, `EdgeTrustPolicy` | 7.1 | SC-EDGE-01 | BR-EDGE-01~04 |
| FD-Q7 (이관 경로) | `ContentJob`, `UnsubscribeToken` | 3.1, 2.2 | SC-CONS-01 | BR-CONS-01 |
| FD-Q8 (account lifecycle) | `AccountLifecycleState`, `AccountService` | 6.1, 6.2, 6.3 | SC-ACC-01~03 | BR-ACC-01~04 |
