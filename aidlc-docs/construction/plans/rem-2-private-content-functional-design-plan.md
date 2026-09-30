# REM-2 Private Content — Functional Design 계획

**단계**: CONSTRUCTION / REM-2 Functional Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- `verification-remediation-2026-09-18.md` F01/F02/F05/F07
- `requirements.md` FR-1/2/3/4/5/7/8/9/10/11/12/13/14/17/18/28/38/47/52
- `verification-remediation-2026-09-18.md` §10 REM 공개 job 계약 (RJ-AC01~12)
- `application-design/` U1/U3/U5/U6/U7/U11/U12/U13 컴포넌트·서비스·의존성
- `unit-of-work-plan.md` REM-2 Private Content / `rem-2-private-content`
- `aidlc-state.md` REM-1 완료 상태 (REM-1 계약 검증·공급망 인수 완료)

**목표**: REM-2 Private Content의 Functional Design 상세 계획을 작성하고, 8개 결정 질문(REM-2-FD-Q1~8)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- REM-1의 versioned 계약(`shared/dtos`, `shared/ports`, `shared/vector-spec`)이 동결돼 공급된다. REM-2는 이를 **변경 없이 소비**한다.
- REM-1의 공급망 인수(SBOM, lockfile, frozen artifact, launchd installer, receipt signer, keychain, protected clock, mTLS, backup/restore evidence, load acceptance)는 검증 완료돼 런타임 기반으로 존재한다.
- `RESILIENCY-08` 면제(단일 Mac), Security Full, PBT Full은 REM-2에도 계승된다.
- full corpus rebuild는 별도 명시 승인 전 실행하지 않는다.
- 공개 job 계약(RJ-AC01~12)은 F01/F02/F05/F07 이관 경로에 이미 적용된다.

---

## 분해 질문 (Decomposition Questions)

### REM-2-FD-Q1 — F01 private userdoc 읽기 경계 구현 범위

F01: `public corpus DocModel route는 userdoc:를 거부한다. private document 전용 read는 authenticated owner를 검증하며 non-owner에게 존재 여부를 노출하지 않는다.`

기존 `GET /paper/{id}` route는 public corpus만 서비스한다. private userdoc은 별도 namespace(`userdoc:{owner}:{docId}`)로 저장되고, owner-only read path가 필요하다.

A) **전용 route 추가(권장)** — `GET /private/userdoc/{docId}` 또는 `GET /userdoc/{owner}/{docId}`를 신설하고, owner 검증 후 DocModel 반환. public route는 `userdoc:` prefix를 404로 거부.

B) 기존 route에 `scope` 파라미터 추가 — `GET /paper/{id}?scope=private`로 owner 검증 분기. namespace 분리 없이 ACL로만 제어.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **전용 route 추가(권장)** — `GET /private/userdoc/{docId}` 또는 `GET /userdoc/{owner}/{docId}`를 신설하고, owner 검증 후 DocModel 반환. public route는 `userdoc:` prefix를 404로 거부.

---

### REM-2-FD-Q2 — F02 공유 번역 cache 오염 방지: cache key 구성

F02: `공유 artifact source는 server-verified metadata/DocModel만 사용한다. cache key는 canonical source identity/content version에 결속한다. client-provided source가 다른 사용자 또는 canonical paper 결과를 결정하지 못한다.`

기존 번역 cache가 `content_hash`만으로 key를 구성해 client가 제공한 source로 오염될 수 있다. server가 검증한 canonical identity(`paperId:version:sourceTier`)를 cache key에 포함해야 한다.

A) **Canonical identity 필수 포함(권장)** — cache key = `translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. client source 무시. server가 canonical paper를 lookup해 identity 추출 후 cache 조회.

B) `content_hash` + `source_tier` 이중 key — client source가 canonical paper와 매핑될 때만 cache hit 허용. 매핑 실패 시 miss로 처리.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **Canonical identity 필수 포함(권장)** — cache key = `translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`. client source 무시. server가 canonical paper를 lookup해 identity 추출 후 cache 조회.

---

### REM-2-FD-Q3 — F05 generation timeout: job/pending/poll 전환 경계

F05: `browser, BFF, API, model, worker 시간 예산이 정렬된다. 동기 예산을 넘는 정상 생성은 job/pending/poll로 전환되고 유효한 12초 이상 응답이 임의 10초 504로 잘리지 않는다.`

요약(FR-12)·번역(FR-13)·novelty(FR-30~35)·evidence formation(FR-37)은 동기 10초 게이트웨이를 넘을 수 있다. REM-1의 공개 job 계약(RJ-AC01~12)이 이미 정의됐으므로, 각 generation 작업의 **전환 임계값(문자 수·예상 토큰·모델 latency percentile)**과 **job 상태 기계**를 확정한다.

A) **문자 수 + 모델 p95 기반 임계값(권장)** — 입력 DocModel 문자 수와 대상 모델의 p95 latency로 동기/비동기 분기. 임계값 이하 = 동기 반환, 초과 = job 접수(RJ-AC01) + event/subscription(RJ-AC04) + 완료 asset 직접 전달(RJ-AC08). 기본 임계값: 요약 8k chars, 번역 12k chars, novelty 16k chars.

B) 고정 시간 임계값 — 동기 경로 8초로 고정, 초과 시 무조건 job 전환. 단순하지만 모델별 latency 편차를 흡수 못 함.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **문자 수 + 모델 p95 기반 임계값(권장)** — 입력 DocModel 문자 수와 대상 모델의 p95 latency로 동기/비동기 분기. 임계값 이하 = 동기 반환, 초과 = job 접수(RJ-AC01) + event/subscription(RJ-AC04) + 완료 asset 직접 전달(RJ-AC08). 기본 임계값: 요약 8k chars, 번역 12k chars, novelty 16k chars.

---

### REM-2-FD-Q4 — F07 private asset serving: same-origin asset endpoint 설계

F07: `browser asset URL은 authenticated same-origin endpoint다. backend가 owner/license/object authorization을 적용하고 MinIO 내부 endpoint/key를 노출하지 않는다. CSP가 해당 same-origin 렌더를 허용한다.`

그림(FR-17)·표 데이터·리치뷰(FR-18) 자산은 job 완료 시 `assetId`로 참조되고, `GET /api/assets/{assetId}` 같은 same-origin endpoint로 서빙된다. owner/license/object 권한을 재검증하고, 서명 URL로 1회용 전달 후 만료.

A) **전용 asset endpoint + 서명 URL(권장)** — `GET /api/v1/assets/{assetId}?token={signed}`에서 owner/license/object 재검증 후 MinIO presigned GET(1분 TTL) redirect 또는 proxy stream. CSP `img-src 'self'` 허용.

B) BFF가 MinIO에서 직접 프록시 — `GET /api/assets/{assetId}`가 owner/license 검증 후 MinIO 내부 GET을 스트리밍. 서명 URL 불필요하지만 BFF 대역폭 소모.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **전용 asset endpoint + 서명 URL(권장)** — `GET /api/v1/assets/{assetId}?token={signed}`에서 owner/license/object 재검증 후 MinIO presigned GET(1분 TTL) redirect 또는 proxy stream. CSP `img-src 'self'` 허용.

---

### REM-2-FD-Q5 — Private userdoc write path: ingestion → DocModel → userdoc namespace

FR-6(U1 Corpus)은 public corpus(`paperId`) 대상이다. F01 private userdoc은 별도 write path가 필요하다: 사용자 업로드(PDF/Markdown/TXT) → ingestion/doc-model 파이프라인 재사용 → `userdoc:{owner}:{docId}`로 저장 → owner-only read. 업로드 크기/형식 제한, 비동기 job, 실패 시 기권(abstain) 경로 포함.

A) **기존 ingestion 파이프라인 재사용 + 별도 namespace(권장)** — `POST /private/userdoc`로 업로드 접수 → job(RJ-AC01) → DocModel 생성 → `userdoc:{owner}:{docId}` 저장. public corpus와 dedup 않음(사용자 private이므로). 실패 시 `abstain` 반환.

B) 전용 lightweight 파이프라인 신설 — GROBID/파서만 공유하고 저장·인덱싱은 별도. 중복 코드 최소화.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **기존 ingestion 파이프라인 재사용 + 별도 namespace(권장)** — `POST /private/userdoc`로 업로드 접수 → job(RJ-AC01) → DocModel 생성 → `userdoc:{owner}:{docId}` 저장. public corpus와 dedup 않음(사용자 private이므로). 실패 시 `abstain` 반환.

---

### REM-2-FD-Q6 — R2A/R2W: content job 통합 — 생성/재조회 상태 기계

R2A(생성), R2W(재조회/결과)는 REM-2의 핵심 job 흐름이다. 생성 job(요약/번역/novelty/evidence)은 `submitted → accepted → queued → running → completed/failed/abstained` 상태 전이를 가지며, 재조회는 `status job`(RJ-AC02)로 처리한다. terminal 상태(`completed`, `failed`, `abstained`) 보존, 중복 제출 멱등성(RJ-AC06), cache hit 시 model 미실행(RJ-AC07).

A) **표준 5-state + abstained(권장)** — `submitted | accepted | queued | running | completed | failed | abstained`. `abstained`는 FR-5 기권(근거 없음)과 생성 초극단 거절을 구분. cache hit는 `completed`로 즉시 반환(RJ-AC07). status job은 terminal 상태만 반환, 중간 상태는 event로 전달(RJ-AC04).

B) 단순 3-state + 상세 reason — `pending | completed | failed`. reason 필드로 `abstained`, `timeout`, `cache_hit` 등 세분화.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **표준 5-state + abstained(권장)** — `submitted | accepted | queued | running | completed | failed | abstained`. `abstained`는 FR-5 기권(근거 없음)과 생성 초극단 거절을 구분. cache hit는 `completed`로 즉시 반환(RJ-AC07). status job은 terminal 상태만 반환, 중간 상태는 event로 전달(RJ-AC04).

---

### REM-2-FD-Q7 — RK/DELIVERY/EDGE/UI/AUTH 첫 content-job 통합 범위

RK(번역 cache/캐논니컬 source), DELIVERY(자산/결과 전달), EDGE(ingress identity/rate-limit), UI(frontend status/asset), AUTH(인가/세션) 경계를 REM-2 content job이 처음 통과한다. 각 경계를 job flow에 어떻게 연결할지:

- RK: canonical paper identity lookup → cache key 구성 → hit 시 model skip(RJ-AC07)
- DELIVERY: job 완료 → assetId 발급 → same-origin asset endpoint(RJ-AC08) → 결과 bytes 직접 전달
- EDGE: job 접수 전 Cloudflare/BFF에서 client identity 검증(RJ-AC11) → queue rate-limit
- UI: frontend가 `submitted/accepted/queued/running/completed/failed/abstained` + event/subscription을 소비(RJ-AC03/04)
- AUTH: job 접수·실행·status·event·asset 모든 단계에서 caller/object 권한 재검증(RJ-AC05)

A) **경계별 미들웨어 체인(권장)** — 각 경계를 독립 middleware/hook로 구현하고 job pipeline에 순서대로 연결. 테스트·교체·관측 용이. shared `JobContext`로 경계 간 데이터 전달.

B) 단일 job handler에 인라인 구현 — 단순하지만 경계별 재사용·테스트 어려움.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **경계별 미들웨어 체인(권장)** — 각 경계를 독립 middleware/hook로 구현하고 job pipeline에 순서대로 연결. 테스트·교체·관측 용이. shared `JobContext`로 경계 간 데이터 전달.

---

### REM-2-FD-Q8 — U11/U12/U13 consumer 계약: EvidenceFormationPort/SourceRef 공유

U11(evidence agent), U12(novelty agent), U13(agent chat frontend)는 REM-2의 content job을 소비한다. U11/U12는 `EvidenceFormationPort`/`SourceRef`만 소비하고 직접 파싱/근거형성 로직을 재구현하지 않는다. U13은 frontend에서 job 접수/대기/결과 수신 UX만 담당.

A) **Port 소비만 허용, 구현 재사용 강제(권장)** — U11/U12 코드에 `EvidenceFormationPort` 호출 외 private DocModel 파싱 로직 금지. `docsuri_shared._generated`의 `EvidenceItem`, `SourceRef` 타입만 import 허용. 위반 시 CI에서 static analysis로 차단.

B) 문서화만 하고 코드 레벨 강제는 하지 않음 — 리뷰로 확인.

C) 기타 (아래 `[Answer]:` 뒤에 기술)

[Answer]: AA) **Port 소비만 허용, 구현 재사용 강제(권장)** — U11/U12 코드에 `EvidenceFormationPort` 호출 외 private DocModel 파싱 로직 금지. `docsuri_shared._generated`의 `EvidenceItem`, `SourceRef` 타입만 import 허용. 위반 시 CI에서 static analysis로 차단.

---

## 산출물 체크리스트 (Part 2 Generation 승인 후 생성)

- [ ] `construction/rem-2-private-content/functional-design/domain-entities.md` — private userdoc, content job, asset, cache entry, status event 엔티티
- [ ] `construction/rem-2-private-content/functional-design/business-logic-model.md` — job 상태 기계, cache lookup/insert, asset 발급/전달, 권한 재검증 흐름
- [ ] `construction/rem-2-private-content/functional-design/business-rules.md` — F01/F02/F05/F07/RJ-AC01~12/R2A/R2W 규칙 전수
- [ ] `construction/rem-2-private-content/functional-design/scenarios.md` — 15개 시나리오 (private read/write, cache hit/miss, timeout 전환, asset 서빙, 권한 거부, 기권, 재연결, queue 유실 복구 등)

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-2-FD-Q1~8에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
