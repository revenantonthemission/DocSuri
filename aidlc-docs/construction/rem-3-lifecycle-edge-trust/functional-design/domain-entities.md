# REM-3 Lifecycle and Edge Trust — Domain Entities

**단계**: CONSTRUCTION / REM-3 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: FD-Q1~8 승인 (전수 A), NFR-Q1~13/ND-Q1~10/ID-Q1~8/CG-Q1~5 승인 대기 중

---

## 1. PurgeRegistry

계정 삭제 요청부터 영구 파기까지의 상태를 관리하는 중앙 레지스트리.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `owner_uid` | `Ref` | PK, `accounts.uid` 참조 | 계정 소유자 UID |
| `status` | `Enum` | `ACTIVE`, `SOFT_DELETED`, `PURGED` | 삭제 상태 |
| `requested_at` | `U64` | 마이크로초 UTC | 삭제 요청 시각 |
| `grace_until` | `U64` | 마이크로초 UTC | 유예 기간 만료 시각 (기본 30일 후) |
| `purged_at` | `U64` | 마이크로초 UTC | 영구 파기 완료 시각 |
| `version` | `U64` | ≥ 1, optimistic locking | 동시성 제어용 버전 |

**불변식**:
- `status` 전이: `ACTIVE` → `SOFT_DELETED` → `PURGED` (역방향 불가)
- `grace_until` = `requested_at` + 30일 (기본값, 설정 가능)
- `version`은 각 상태 전이마다 증가

---

## 2. UnsubscribeToken

익명 수신 해지 토큰. HS256 JWT로 서명, Redis cache로 빠른 조회.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `token` | `Ref` | HS256 JWT 문자열 | `email`, `purpose="unsubscribe"`, `exp`, `iat` 포함 |
| `email` | `Ref` | RFC 5322 이메일 | 수신 해지 대상 이메일 |
| `exp` | `U64` | 마이크로초 UTC | 만료 시각 (발급 + 24시간) |
| `issued_at` | `U64` | 마이크로초 UTC | 발급 시각 |
| `revoked_at` | `U64` | 마이크로초 UTC | 철회 시각 (철회 시 설정) |

**불변식**:
- 토큰은 1회용, 사용 후 즉시 무효화
- `revoked_at` 설정 시 즉시 무효
- `exp` 경과 시 자동 만료

---

## 3. RateLimitBucket

Client identity별 task type별 토큰 버킷.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `identity` | `Ref` | `user:{uid}` \| `ip:{sha256(ip)[:16]}` | Client identity |
| `task_type` | `Enum` | `translate`, `summarize`, `novelty`, `evidence`, `unsubscribe` | Task type |
| `tokens` | `U64` | 현재 토큰 수 | 실시간 잔여 토큰 |
| `max_tokens` | `U64` | 버킷 용량 | task type별 설정 |
| `refill_rate` | `U64` | 초당 리필량 | 지속 가능한 처리율 |
| `last_refill` | `U64` | 마이크로초 UTC | 마지막 리필 시각 |

**불변식**:
- 동일 `identity` + `task_type` 조합은 단일 버킷 공유
- `refill_rate` × 경과 시간으로 토큰 리필
- 버킷 고갈 시 `429 Too Many Requests`

---

## 4. ConsentRecord

사용자 동의(consent) 레코드. grant → active → revoked/expired.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `consent_id` | `Ref` | UUID v7 | 고유 식별자 |
| `owner_uid` | `Ref` | `accounts.uid` 참조 | 동의 소유자 |
| `scope` | `Enum` | `email_digest`, `follow_notify`, `marketing`, `personalization` | 동의 범위 |
| `status` | `Enum` | `GRANTED`, `REVOKED`, `EXPIRED` | 동의 상태 |
| `granted_at` | `U64` | 마이크로초 UTC | 동의 시각 |
| `revoked_at` | `U64` | 마이크로초 UTC | 철회 시각 (철회 시) |
| `expires_at` | `U64` | 마이크로초 UTC | 만료 시각 (자동 만료 시) |
| `token_hash` | `Ref` | SHA256(token) | 연계된 토큰 해시 (철회용) |

**불변식**:
- `GRANTED` → `REVOKED` 또는 `EXPIRED`만 전이 가능
- `revoked_at` 설정 시 즉시 `REVOKED` 전이
- `expires_at` 경과 시 자동 `EXPIRED` 전이

---

## 5. RevocationEvent

동의/토큰 철회 이벤트. Redis pub/sub로 즉시 전파.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `event_id` | `Ref` | UUID v7 | 이벤트 고유 ID |
| `token_hash` | `Ref` | SHA256(token) | 철회 대상 토큰 해시 |
| `revoked_at` | `U64` | 마이크로초 UTC | 철회 시각 |
| `reason` | `Enum` | `USER_REQUEST`, `ACCOUNT_DELETED`, `POLICY_VIOLATION`, `EXPIRED` | 철회 사유 |
| `propagated` | `Bool` | 기본 `false` | 전파 완료 여부 |

---

## 6. ClientIdentity

Cloudflare → BFF → FastAPI 체인에서 전달되는 클라이언트 식별자.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `identity` | `Ref` | `user:{uid}` \| `ip:{sha256(ip)[:16]}` | 클라이언트 식별자 |
| `authenticated` | `Bool` | 인증 여부 | `true`면 `user:{uid}`, `false`면 `ip:...` |
| `source` | `Enum` | `CLOUDFLARE`, `BFF`, `FASTAPI` | 검증된 소스 |
| `verified_at` | `U64` | 마이크로초 UTC | 검증 시각 |

---

## 7. AccountLifecycleState

계정 생명주기 상태. `ACTIVE` → `SOFT_DELETED` → `PURGED`.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `owner_uid` | `Ref` | `accounts.uid` | 계정 UID |
| `state` | `Enum` | `ACTIVE`, `SOFT_DELETED`, `PURGED` | 현재 상태 |
| `soft_deleted_at` | `U64` | 마이크로초 UTC | Soft delete 요청 시각 |
| `grace_until` | `U64` | 마이크로초 UTC | 유예 기간 만료 (기본 30일) |
| `purged_at` | `U64` | 마이크로초 UTC | 영구 파기 완료 시각 |
| `purged_by` | `Ref` | `purge_worker` | 파기 실행자 |

**불변식**:
- `ACTIVE` → `SOFT_DELETED` → `PURGED` 단방향
- `grace_until` = `soft_deleted_at` + 30일 (기본)
- `PURGED` 도달 시 복구 불가

---

## 8. EdgeTrustPolicy

Ingress edge에서 적용되는 신뢰 정책.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `identity_verification` | `Enum` | `CLOUDFLARE_VERIFIED`, `BFF_VERIFIED`, `FASTAPI_VERIFIED` | 검증 단계 |
| `rate_limit_enabled` | `Bool` | 기본 `true` | Rate-limit 활성화 |
| `spoofing_protection` | `Bool` | 기본 `true` | Header spoofing 방지 |
| `max_requests_per_minute` | `U64` | 기본 60 | IP별 분당 최대 요청 |
| `waf_rules` | `List[Ref]` | WAF 룰 ID 목록 | Cloudflare WAF 룰 ID |

---
