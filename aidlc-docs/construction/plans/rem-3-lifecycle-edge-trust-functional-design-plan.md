# REM-3 Lifecycle and Edge Trust — Functional Design 계획

**단계**: CONSTRUCTION / REM-3 Functional Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- `verification-remediation-2026-09-18.md` F04/F09/F10
- `requirements.md` FR-28/47/9/10/27/29/40~43/49/52, NFR-R1/2/4/5/11, SEC-5/8/9/11/12/15, RES-2/5/11/12
- `aidlc-state.md` REM-2 완료 상태
- `application-design/` U3/U5/U6/U13/U14/U15 컴포넌트·서비스·의존성

**목표**: REM-3 Lifecycle and Edge Trust의 Functional Design 상세 계획을 작성하고, 8개 결정 질문(REM-3-FD-Q1~8)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-2 인프라 완료: launchd workers(4종), keychains(3종), worker accounts(4개), platform_integrity/ops 공통 계약 동결
- Security Full, PBT Full, Resiliency custom(RESILIENCY-08 면제) 계승
- `RESILIENCY-08` 면제(단일 Mac), full corpus rebuild 별도 승인
- REM-2 contracts(`shared/dtos`, `shared/ports`, `shared/vector-spec`) 동결·공급

---

## 분해 질문 (Decomposition Questions)

### REM-3-FD-Q1 — F04 Owner Purge: 중앙 purge registry와 cascade 파기

F04: `중앙 purge registry가 모든 owner-scoped SQL table과 private object prefix를 포함한다. 실제 DB/object integration에서 대상 owner 데이터는 0, 다른 owner 데이터는 불변이다. 재실행은 멱등이다.`

기존 FR-28/38/SEC-8에서 owner-scoped 데이터 파기가 필요. soft delete + 유예 기간 후 비동기 영구 파기. cascade 파기 시 foreign key 제약 고려.

A) **중앙 registry + 비동기 worker(권장)** — `purge_registry` 테이블에 owner별 파기 대상 table/prefix 기록. `purge_worker`가 순차 처리: soft delete → 유예 기간(N일) → hard delete. 재실행 시 멱등(이미 처리된 항목 skip). foreign key는 `ON DELETE CASCADE` 또는 application-level cascade.

B) 동기 단일 트랜잭션 — 단순하지만 대량 데이터 시 타임아웃/락 경합 위험.

C) 기타

[Answer]: AA) **중앙 registry + 비동기 worker(권장)** — `purge_registry` 테이블에 owner별 파기 대상 table/prefix 기록. `purge_worker`가 순차 처리: soft delete → 유예 기간(N일) → hard delete. 재실행 시 멱등(이미 처리된 항목 skip). foreign key는 `ON DELETE CASCADE` 또는 application-level cascade.

---

### REM-3-FD-Q2 — F09 익명 이메일 수신 해지 토큰 검증

F09: `token unsubscribe route는 명시적 public endpoint이며 token 자체를 검증한다. email paper link는 실제 `/paper/{id}` route를 사용한다. valid/invalid/expired token과 익명 접근을 테스트한다.`

FR-47/48(이메일 다이제스트, 팔로우 목록)에서 수신 해지 토큰 필요. token 자체만으로 검증(세션/인증 불필요). valid/invalid/expired token과 익명 접근 구분.

A) **HS256 서명된 JWT 토큰(권장)** — `unsubscribe_token = JWT(payload={email, purpose="unsubscribe", exp}, key=HS256_secret)`. endpoint `GET /unsubscribe?token=<jwt>`에서 검증. `expired` → `401`, `invalid signature` → `400`, `malformed` → `400`. 수신 해지 즉시 durable 수락 시점부터 추가 발송 차단(RJ-AC10).

B) opaque random token + DB lookup — 단순하지만 token 자체에 정보 없음, DB lookup 필요.

C) 기타

[Answer]: AA) **HS256 서명된 JWT 토큰(권장)** — `unsubscribe_token = JWT(payload={email, purpose="unsubscribe", exp}, key=HS256_secret)`. endpoint `GET /unsubscribe?token=<jwt>`에서 검증. `expired` → `401`, `invalid signature` → `400`, `malformed` → `400`. 수신 해지 즉시 durable 수락 시점부터 추가 발송 차단(RJ-AC10).


---

### REM-3-FD-Q3 — F10 Client rate-limit identity 체인

F10: `Cloudflare/BFF 신뢰 경계에서 검증한 client identity만 FastAPI에 전달한다. 임의 client header spoofing은 거부하고 서로 다른 client는 독립 bucket, 같은 client는 동일 bucket을 사용한다.`

Cloudflare → BFF → FastAPI identity 체인 구축. Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 프록시. FastAPI 미들웨어가 identity별 token bucket 적용.

A) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자는 `user:{uid}`, 익명은 `ip:{sha256(ip)[:16]}`.

B) IP-only rate-limit — 단순하지만 NAT/공용 WiFi에서 과도 제한.

C) 기타

[Answer]: AA) **Cloudflare → BFF → FastAPI identity 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자는 `user:{uid}`, 익명은 `ip:{sha256(ip)[:16]}`.

---

### REM-3-FD-Q4 — R3C Purge Lifecycle: soft delete → grace period → hard delete

R3C: purge lifecycle의 상세 상태 기계 정의. soft delete(표시) → 유예 기간(N일) → hard delete(영구 파기). 재실행 멱등. 중앙 registry에 모든 owner-scoped SQL table과 private object prefix 포함.

A) **3-state machine: ACTIVE → SOFT_DELETED(유예) → PURGED(권장)** — `purge_registry` 테이블: `owner_uid`, `status`, `requested_at`, `grace_until`, `purged_at`. `purge_worker`가 주기적 스캔: `SOFT_DELETED` + `grace_until < now` → hard delete 실행 → `PURGED`. 멱등: 이미 `PURGED`면 skip. foreign key `ON DELETE CASCADE` 또는 application cascade.

B) 2-state: ACTIVE → PURGED — 유예 기간 없음. 즉시 파기.

C) 기타

[Answer]: AA) **3-state machine: ACTIVE → SOFT_DELETED(유예) → PURGED(권장)** — `purge_registry` 테이블: `owner_uid`, `status`, `requested_at`, `grace_until`, `purged_at`. `purge_worker`가 주기적 스캔: `SOFT_DELETED` + `grace_until < now` → hard delete 실행 → `PURGED`. 멱등: 이미 `PURGED`면 skip. foreign key `ON DELETE CASCADE` 또는 application cascade.


---

### REM-3-FD-Q5 — R3P Consent Management: consent lifecycle과 token 철회

R3P: consent(동의) lifecycle 관리. grant → active → revoked/expired. token(이메일 unsubscribe, OAuth consent) 발급/철회/만료. FR-47/48 이메일 다이제스트/팔로우 목록 수신 해지 포함.

A) **Consent 레코드 + token 발급/철회(권장)** — `consent` 테이블: `owner_uid`, `scope`, `granted_at`, `revoked_at`, `expires_at`, `token_hash`. token 발급 시 `token_hash` 저장. 철회 시 `revoked_at` 설정 + token 무효화. `GET /consent/{id}/revoke`로 철회. 만료 시 자동 `expired` 전환.

B) 간단한 boolean flag — 상세 이력 없음.

C) 기타

[Answer]: AA) **Consent 레코드 + token 발급/철회(권장)** — `consent` 테이블: `owner_uid`, `scope`, `granted_at`, `revoked_at`, `expires_at`, `token_hash`. token 발급 시 `token_hash` 저장. 철회 시 `revoked_at` 설정 + token 무효화. `GET /consent/{id}/revoke`로 철회. 만료 시 자동 `expired` 전환.

---

### REM-3-FD-Q6 — R3E Edge Trust: ingress identity 검증/rate-limit

R3E: `ingress identity 검증/rate-limit은 접수 이전 직접 집행. policy/version 관리만 service 책임으로 설계.`

Cloudflare/BFF 신뢰 경계에서 검증한 client identity만 FastAPI에 전달. 임의 client header spoofing 거부. 서로 다른 client 독립 bucket, 같은 client 동일 bucket. queue outage로 인증/인가/rate-limit 우회 불가.

A) **Cloudflare → BFF → FastAPI 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`. 동일 client 독립 bucket.

B) BFF만으로 검증 — Cloudflare 거치지 않고 BFF에서 직접 검증. 단순하지만 spoofing 위험.

C) 기타

[Answer]: AA) **Cloudflare → BFF → FastAPI 체인(권장)** — Cloudflare가 `CF-Connecting-IP` + 인증 토큰 검증 → `X-Client-Identity` 헤더로 BFF 전달 → BFF가 FastAPI에 `X-Client-Identity` 프록시. FastAPI 미들웨어가 identity별 token bucket 적용. 인증된 사용자 `user:{uid}`, 익명 `ip:{sha256(ip)[:16]}`. 동일 client 독립 bucket.

---

### REM-3-FD-Q7 — F01/F02/F07/F10 이관 경로: 공개 job 계약과 연계

F01 private userdoc 읽기, F02 공유 번역 cache 오염, F07 private asset serving, F10 rate-limit identity가 공개 job 계약(RJ-AC01~12)과 연계되어 이관됨. 각 finding의 인수가 job 계약의 구체적 단계(RJ-AC01~12)에 매핑.

A) **Job 계약 단계별 인수 매핑(권장)** — 
- F01: RJ-AC05(권한 검증), RJ-AC08(asset 직접 전달)
- F02: RJ-AC07(cache hit 시 model 미실행), RJ-AC01(durable 접수)
- F07: RJ-AC08(인가된 직접 전달 경로), RJ-AC05(owner/license/object 재검증)
- F10: RJ-AC11(rate-limit/인가 선행 집행), RJ-AC12(queue outage 복구)

B) 개별 구현 — 연계 없이 개별 구현.

C) 기타

[Answer]: AA) **Job 계약 단계별 인수 매핑(권장)** — 
- F01: RJ-AC05(권한 검증), RJ-AC08(asset 직접 전달)
- F02: RJ-AC07(cache hit 시 model 미실행), RJ-AC01(durable 접수)
- F07: RJ-AC08(인가된 직접 전달 경로), RJ-AC05(owner/license/object 재검증)
- F10: RJ-AC11(rate-limit/인가 선행 집행), RJ-AC12(queue outage 복구)


---

### REM-3-FD-Q8 — Account lifecycle integration: ORCID/소셜 로그인 연계

FR-26/27/44~46: 비밀번호 재설정, 소셜 로그인(Google/ORCID), 계정 라이프사이클(비번 변경, 이메일 변경, 탈퇴). ORCID iD는 마이페이지(U10)에 실표시. 계정 삭제 시 owner-scoped 데이터 캐스케이드 파기(U3 AccountDeleted 구독, FR-28 준용).

A) **통합 계정 라이프사이클 서비스(권장)** — `AccountLifecycleService`: 비밀번호 재설정(단일 사용 30분 토큰, FR-26), 소셜 로그인(Google/ORCID, FR-27), 계정 관리(FR-28). 탈퇴 시 soft delete → 유예 → hard delete(FD-Q4). ORCID iD 마이페이지 표시. owner-scoped 데이터 캐스케이드 파기(SEC-8).

B) 분리된 핸들러 — 각 기능별 독립 핸들러. 중복 코드 발생 가능.

C) 기타

[Answer]: AA) **통합 계정 라이프사이클 서비스(권장)** — `AccountLifecycleService`: 비밀번호 재설정(단일 사용 30분 토큰, FR-26), 소셜 로그인(Google/ORCID, FR-27), 계정 관리(FR-28). 탈퇴 시 soft delete → 유예 → hard delete(FD-Q4). ORCID iD 마이페이지 표시. owner-scoped 데이터 캐스케이드 파기(SEC-8).


---

## 산출물 체크리스트 (Part 2 Generation 승인 후 생성)

- [ ] `construction/rem-3-lifecycle-edge-trust/functional-design/domain-entities.md` — purge registry, consent, token, account lifecycle 엔티티
- [ ] `construction/rem-3-lifecycle-edge-trust/functional-design/business-logic-model.md` — purge lifecycle, consent lifecycle, token 검증, identity 체인 흐름
- [ ] `construction/rem-3-lifecycle-edge-trust/functional-design/business-rules.md` — F04/F09/F10/R3C/R3P/R3E/FD-Q7/FD-Q8 규칙 전수
- [ ] `construction/rem-3-lifecycle-edge-trust/functional-design/scenarios.md` — 15개 시나리오 (purge lifecycle, unsubscribe token, rate-limit, consent, edge trust, account lifecycle)

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-3-FD-Q1~8에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
