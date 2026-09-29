# 유닛 분해 계획 (Unit of Work Plan)

> **현재 승인 기록**: 하단 `2026-09-19 Deployable-Service Units Restart Plan`의 Part 2 검증 기록과 UGR1을 참조한다. UGR1=A로 세 산출물이 승인됐고 Construction의 REM-1 Functional Design을 시작한다. 초기 UQ 및 planning-overlay UQR 계획은 당시 이력이다.

**단계**: INCEPTION → Units Generation (Part 1: 계획) · **일자**: 2026-06-15
**입력**: `application-design/`(U1~U6 컴포넌트·서비스·의존성), `stories.md`(21개), `execution-plan.md`.
**목표**: 시스템을 개발 단위(unit of work)로 공식 분해 — 경계·의존성·스토리 매핑·코드 조직(Greenfield)·빌드 순서.

아래 질문에 답하거나(또는 **"approve plan"** 으로 권장안 수락) 후, 유닛 산출물을 생성한다.

---

## 분해 질문 (Decomposition Questions)

## UQ1 — 유닛 집합
Application Design의 6 유닛(U1~U6)을 그대로 개발 단위로 확정할까?

A) **6 유닛 그대로(권장)** — U1 Ingestion / U2 Discovery / U3 Accounts / U4 Library / U5 Frontend / U6 Reliability·Ops. 설계와 1:1.

B) U6를 유닛이 아닌 횡단 관심사로 흡수 → 5 유닛(미들웨어는 API에 내장, 탐지/대시보드만 별도).

C) 기타 재그룹핑(아래 기술).

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A (approve plan — 권장안 수락)

## UQ2 — 코드 조직 / 리포 구조 (Greenfield)
디렉터리·배포 구조는?

A) **모노레포(권장)** — `frontend/`(SSR 폰 우선) · `backend/`(모듈형 모놀리스 API: `modules/discovery|accounts|library`, `middleware/`(U6 게이트웨이)) · `ingestion/`(U1 워커) · `ops/`(U6 탐지·대시보드 워커) · `shared/`(공유 계약: VectorSpec·DTO·이벤트 스키마).

B) 멀티 레포(유닛별 분리 저장소).

C) 단일 앱 단일 디렉터리.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A (approve plan — 권장안 수락)

## UQ3 — 배포 단위 매핑
런타임 배포 단위(모듈형 모놀리스 전제)는?

A) **4 배포 단위(권장)** — ① API 서비스(U2+U3+U4+U6 게이트웨이 미들웨어, 동기 REST) ② 인제스천 워커(U1, 이벤트/스케줄) ③ Ops/탐지 워커(U6 탐지기·대시보드, 이벤트 백본) ④ 프런트엔드(U5, SSR). 공유 벡터 인덱스·DB·이벤트 버스·오브젝트 스토리지는 공유 capability.

B) 3 배포 단위(Ops를 API에 흡수).

C) 기타.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A (approve plan — 권장안 수락)

## UQ4 — 빌드/개발 순서
어떤 순서로 구축할까? (각 유닛은 CONSTRUCTION 유닛별 루프로 진행)

A) **데모 우선 / 히어로 경로(권장)** — U1 Ingestion → U2 Discovery → U5 Frontend(히어로 US-H1 동작) → U3 Accounts → U4 Library → U6 Reliability·Ops 강화. 매직 모먼트를 가장 먼저 가시화.

B) 파운데이션 우선 — U6 미들웨어 + U3 Accounts 먼저(공통 게이트·인증), 이후 디스커버리.

C) 기타.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A (approve plan — 권장안 수락)

## UQ5 — 공유 계약 소유권
공유 계약(VectorSpec 임베딩 스키마, 결과/DTO, 이벤트 스키마)은 어디서 소유?

A) **`shared/` 공유 패키지 단일 소유(권장)** — U1 writer·U2 reader가 동일 VectorSpec 소비; 이벤트 스키마(SearchExecuted·AI 인시던트) 공유. 버전·호환 한 곳 관리.

B) 생산자 유닛이 각자 소유·노출.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A (approve plan — 권장안 수락)

---

## 필수 유닛 산출물 (답변·승인 후 생성)
- [x] `application-design/unit-of-work.md` — 유닛 정의·책임 + **코드 조직 전략(Greenfield)**
- [x] `application-design/unit-of-work-dependency.md` — 유닛 의존성 매트릭스(동기/이벤트/공유)
- [x] `application-design/unit-of-work-story-map.md` — 스토리(21개) → 유닛 매핑(전수 할당 검증)
- [x] 유닛 경계·의존성 검증, 모든 스토리 유닛 할당 확인

## 생성 단계 (승인 후)
- application-design/ + stories.md 기반으로 3 산출물 생성, 스토리 전수 매핑·의존성 비순환 검증. (설계가 이미 확정적이므로 직접 생성 + 정합 검증; 필요 시 경량 비평.)

---

## 2026-09-19 F01-F13 교정 Units Generation Amendment Plan

> **SUPERSEDED**: 이 planning-overlay 계획은 UQRF1=B로 중지됐다. 현재 실행 대상은 하단의 deployable-service 재시작 계획이다.

**단계**: INCEPTION -> Units Generation Part 1 (Planning)
**입력**: 승인된 F01-F13 requirements, workflow plan, Application Design RQ1~RQ7 및 mandatory 5개 설계 산출물
**목표**: 기존 제품 유닛 U1~U16과 deploy boundary를 변경하지 않고 REM-1~REM-4를 Construction용 remediation planning unit으로 확정한다.

### 상속된 비협상 결정

- REM-1~REM-4의 네 유닛과 finding grouping은 승인된 workflow plan을 따른다.
- 새 runtime remediation service, deployable product unit, repository, public job endpoint를 만들지 않는다.
- 기존 product/domain unit이 코드와 데이터의 canonical owner다. REM unit은 여러 owner path의 변경 순서와 검증 gate를 조정하는 temporary planning overlay다.
- safe targeted live repair는 Build and Test의 backup/restore/rollback gate 뒤에만 수행한다.
- full corpus rebuild, bulk reparse/reembed, live alias cutover는 별도 명시 승인 전 실행하지 않는다.

### Part 1 - Planning 체크리스트

- [x] 승인된 requirements, workflow plan, Application Design과 기존 U1~U16 unit artifacts를 로드한다.
- [x] Story Grouping, Dependencies, Team Alignment, Technical Considerations, Business Domain, Code Organization 적용성을 평가한다.
- [x] UQR1~UQR5 답변을 모두 수집하고 모순/모호성을 검증한다. UQRF1=B로 기존 architecture를 의도적으로 supersede하고 Workflow Planning으로 복귀한다.
- [ ] unit decomposition plan 승인을 받는다.

### Part 2 - Generation 체크리스트 (계획 승인 후)

- [ ] `application-design/unit-of-work.md`에 REM-1~REM-4 정의, 책임, finding/owner path, 완료 gate를 추가한다.
- [ ] `application-design/unit-of-work-dependency.md`에 remediation dependency/merge order, 기존 product-unit mapping, destructive gate를 추가한다.
- [ ] `application-design/unit-of-work-story-map.md`에 User Stories skip 근거와 F01~F13/requirements-to-remediation-unit 전수 매핑을 추가한다.
- [ ] 모든 finding이 정확히 한 primary REM owner와 필요한 product-unit contributors에 배정됐는지 검증한다.
- [ ] code/deploy dependency DAG, Security Full, Resiliency custom, PBT Full stage applicability를 검증한다.

### 적용성 평가

- **Story Grouping**: 신규 user story가 없으므로 finding/acceptance-criteria mapping 방식을 확정해야 한다 -> UQR1.
- **Dependencies**: workflow 순서를 hard gate로 볼지 merge ordering만 강제할지 확정해야 한다 -> UQR2.
- **Team Alignment**: REM unit별 review/approval boundary와 shared path 변경 조정 방식을 확정해야 한다 -> UQR3.
- **Technical Considerations**: REM unit이 deployable인지 planning overlay인지 artifact에 재확인해야 한다 -> UQR4.
- **Business Domain**: REM unit과 기존 U1~U16 canonical ownership 관계를 확정해야 한다 -> UQR5.
- **Code Organization**: Brownfield이며 기존 monorepo/package layout을 변경하지 않으므로 Greenfield-only 질문은 N/A다.

## UQR1 - Finding Mapping Strategy

User Stories를 건너뛴 이번 remediation에서 `unit-of-work-story-map.md`는 무엇을 전수 매핑할까?

A) 기존 user story 표는 보존하고, 별도 remediation mapping으로 F01~F13 각각의 acceptance criteria와 primary REM owner/contributing product units를 매핑한다. 신규 pseudo-story는 만들지 않는다. (권장)

B) F01~F13을 임시 user story ID로 변환해 기존 story 표에 추가한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## UQR2 - Dependency Gate Strength

REM unit 의존 순서를 어느 수준으로 강제할까?

A) REM-1 검증 완료를 REM-2/3/4의 merge 전제조건으로 두고, REM-2 -> REM-3 -> REM-4 순서는 구현 병렬성을 허용하되 merge/isolated integration gate를 순차 적용한다. REM-4 relevance enforcement는 verified corpus에 추가로 종속한다. (권장)

B) REM-1~REM-4를 완전 직렬로 구현하며 이전 unit의 모든 Construction 단계 승인 전 다음 unit을 시작하지 않는다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## UQR3 - Review and Change Boundary

여러 package를 건드리는 remediation 변경을 어떤 review boundary로 관리할까?

A) REM unit별 독립 plan/review/verification boundary를 사용하고, shared 파일은 REM-1이 먼저 소유한다. 후속 unit은 승인된 shared contract를 소비하며 변경이 필요하면 REM-1 contract review를 다시 연다. (권장)

B) 네 REM unit을 하나의 단일 review/approval boundary로 관리한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## UQR4 - Deployment Semantics

REM-1~REM-4를 runtime/deployment 관점에서 어떻게 표현할까?

A) 모두 temporary planning units로만 표현하고 기존 API, frontend, ingestion, ops/worker deploy units에 변경을 매핑한다. 새 service/process/repository는 추가하지 않는다. (권장, 승인된 RQ1 계승)

B) 각 REM unit을 장기 유지되는 독립 deployable remediation service로 만든다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: B

## UQR5 - Canonical Domain Ownership

REM unit과 기존 U1~U16의 ownership이 겹칠 때 최종 코드/데이터 계약 owner는 누구인가?

A) 기존 product/domain unit이 canonical owner를 유지한다. REM unit은 변경 coordination, dependency order, acceptance gate만 소유하며 완료 후 별도 domain authority로 남지 않는다. (권장)

B) REM unit이 변경된 코드/데이터 계약의 장기 canonical owner가 된다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

### 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 UQR1~UQR5에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 unit artifact generation으로 진행하지 않는다.

### 답변 분석 - 2026-09-19

- 사용자 표기 `UQ1`~`UQ5`는 현재 질문 게이트의 UQR1~UQR5 답변으로 해석했다.
- UQR1=A, UQR2=A, UQR3=A, UQR5=A는 각각 finding mapping, merge gate, unit별 review, 기존 domain ownership을 명확히 확정한다.
- UQR4=B는 각 REM unit을 장기 독립 deployable service로 만든다는 선택이다.
- UQR4=B는 승인된 Workflow Planning의 "새 deployable product unit 없음", Application Design RQ1=A의 "새 runtime remediation service 없음", 본 plan 목표/비협상 결정과 직접 충돌한다.
- UQR4=B는 UQR5=A의 "REM unit은 완료 후 별도 domain authority로 남지 않는다"와도 장기 runtime ownership 관점에서 충돌한다.
- 아래 UQRF1을 해소하기 전에는 plan 승인 또는 Part 2 generation으로 진행하지 않는다.

## UQRF1 - Deployment Contradiction Resolution

UQR4=B와 앞서 승인된 architecture/deployment 결정을 어떻게 정합시킬까?

A) UQR4를 A로 정정한다. REM-1~REM-4는 temporary planning units이고 기존 API/frontend/ingestion/ops deploy units에 변경을 매핑한다. 승인된 Workflow/Application Design과 UQR5=A를 유지한다. (권장)

B) UQR4=B를 유지한다. Units Generation을 중지하고 Workflow Planning과 Application Design으로 돌아가 네 장기 deployable remediation services, runtime ownership, data/API contracts, deployment/operations를 다시 설계한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 충돌을 해소하는 정확한 deployment/ownership 규칙 기술)

[Answer]: B

### UQRF1 결과

- UQR4=B를 유지한다.
- 본 Units Generation Part 1은 승인 대기 상태가 아니라 **중지/superseded** 상태다. Part 2 artifact generation을 수행하지 않는다.
- 승인된 기존 workflow의 planning-overlay 전제와 Application Design RQ1=A는 더 이상 현재 권위가 아니다.
- Workflow Planning을 다시 실행해 네 장기 deployable remediation services를 반영한 phase/dependency/risk plan을 승인받은 뒤, Application Design 질문/산출물과 Units Generation을 새 경계로 다시 수행한다.

---

## 2026-09-19 Deployable-Service Units Restart Plan

**단계**: INCEPTION -> Units Generation Part 2 (Generation)
**상태**: 세 unit 산출물 생성·검증 및 UGR1=A 승인 완료 (2026-09-19)
**입력**: DAD1=A로 승인된 5개 Application Design 신규 절, WPR2=A, RJR1=A, RJS2=A 및 기존 U1~U16 unit artifacts
**목표**: 이번 Construction을 네 장기 deployable REM service 단위로 실행할 수 있도록 책임, 기존 domain 기여, component/story/finding/인수, 의존성과 완료 기준을 세 unit 산출물에 정합시킨다.

### Part 1 체크리스트

- [x] DAD1 승인과 기존 unit 정의/의존성/story map을 확인했다.
- [x] 기존 UQR 결정과 이후 DSRQ/RJR1/RJS2/WPR2의 대체 범위를 분석했다.
- [x] Story Grouping, Dependencies, Team Alignment, Technical Considerations, Business Domain, Code Organization을 근거와 함께 평가했다.
- [x] 네 unit, 17 component, 13 finding, 18개 신규/개정 story와 12개 job 인수의 배치 계획을 작성했다.
- [x] 전체 85개 story의 canonical product owner 정합화 방식과 세 mandatory artifact 생성 순서를 정의했다.
- [x] 계획의 범위/수량/의존성/질문 및 Markdown/whitespace를 검증했다. 85개 story 계획의 합계, 개별 delivery 18행/component 17행/finding 13행/RJ-AC 12행, UGP1 단일 미답변 및 parsing/diff check 확인.
- [x] UGP1 답변을 수집하고 모호성/모순을 분석했다. 단일 선택 A이며 DAD1/WPR2와 정합적이다.
- [x] 명시적인 unit plan 승인을 기록하고 Part 2로 진행했다. 사용자 "UGP1: A" (2026-09-19).

### 승인 결정 계승 및 질문 범주 평가

| 범주 | 이전 결정 / 현재 근거 | 현재 적용 및 질문 처리 |
|---|---|---|
| Story Grouping | UQR1=A의 finding-to-REM 매핑 원칙; RJS2=A의 실제 공개 job stories | pseudo-story로 findings를 바꾸지 않는다. F01~F13, 실제 story 및 RJ-AC를 별도 연결한다. 신규/누락 story owner와 이번 delivery primary의 제안은 UGP1에서 승인한다. |
| Dependencies | UQR2=A 및 WPR2 §4/5 | REM-1 선행, REM-2 -> REM-3 -> REM-4 merge/isolated integration; 계약 동결 후 독립 구현 병렬성 계승. runtime/activation 의존과 merge 순서를 구분한다. |
| Team Alignment | UQR3=A, 기존 product/domain owner, RES-3 | REM별 독립 plan/review/verification이며 domain 변경은 해당 owner가 검토한다. shared 계약 변경은 REM-1 조정 및 원 domain owner review를 다시 연다. 개인 담당자를 새로 지정하지 않는다. |
| Technical Considerations | UQR4=B, UQRF1=B, DSRQ1/3/7, DAD1 | 네 independently deployable services 및 role별 credential/artifact/health. RK/AUTH/DELIVERY/EXEC/OBS는 library/port 또는 service-local instance이며 별도 다섯 번째 REM이 아니다. |
| Business Domain | UQR5=A를 DSRQ2=A/DAD1이 명확화 | U1~U16 business/schema authority 유지, REM은 운영 state/실행 조정 소유. 구 UQR5의 temporary-only 문구는 승인된 장기 runtime ownership으로 대체됐다. |
| Code Organization | Brownfield, 기존 monorepo 및 DAD1 source layering | Greenfield-only 재조직 질문은 N/A다. 아래 기존 source 기여 경로를 매핑하고 새 artifact의 구체 packaging/entry path는 승인된 per-unit NFR/Code plan에서 정한다. |

이미 확정된 서비스 수/배포 형태/계약/권위는 재질문하지 않는다. UGP1은 아래 unit 배치와 전체 생성 계획에 대한 승인이다.

### 두 종류의 ownership

- **Canonical product story owner**: 사용자 가치/인수의 기존 책임 유닛 U1~U16. 이 표시는 모든 관련 코드/데이터를 그 유닛으로 이동한다는 뜻이 아니다. 실제 business rule/data writer는 DAD1의 domain별 배치를 따른다.
- **Primary REM delivery unit**: 이번 변경의 구현/통합 인수를 마감하는 책임 service. contributor가 필요한 domain/frontend/ops 변경까지 포함해 vertical slice를 완결한다.
- 기존 16개 product 유닛은 장기 domain 참조 체계이며, 이번 cycle의 Construction loop는 **REM 4개**다. 16개 product 유닛을 모두 다시 구현하는 별도 loop를 추가하지 않는다.
- REM service별 code/test/운영 산출물과 실제 consumer 연결이 완료 기준이다. 문서 Owner 배정이나 mock enqueue 성공만으로 unit을 완료 처리하지 않는다.

### 네 unit의 경계

| Unit / 문서 slug | 주 finding 및 산출 | 기존 product/source 기여 | 완료 checkpoint |
|---|---|---|---|
| REM-1 Platform Integrity / `rem-1-platform-integrity` | F06/F08/F13; R1C/R1R, ordered registry, offline bindings, frozen artifact/lock/SBOM 및 공통 계약·관측 규약 | shared, backend migration/app-shell, frontend type tooling, ops/CI 및 각 schema owner | G1. 후속 REM이 소비할 versioned 계약/검증 기반; startup/CLI 동치, build-consumed drift와 공급망 인수 |
| REM-2 Private Content / `rem-2-private-content` | F01/F02/F05/F07; R2A/R2W 및 RK/DELIVERY/EDGE/UI/AUTH의 최초 content-job 통합 | U1/U3/U5/U6/U7/U11/U12/U13; ingestion/user_docmodel, summarization, current authority/context adapter, BFF/viewer/agent seams | G2 및 관련 G4. 실제 consumer, current authority, source/cache, status/SSE/result/asset, browser 인수. 공개 활성화는 REM-3 보호 및 통합 gate 충족 후 |
| REM-3 Lifecycle and Edge Trust / `rem-3-lifecycle-edge-trust` | F04/F09/F10; R3C/R3P/R3E 및 EXEC의 domain별 연결, direct lifecycle/consent 보호 | U3/U5/U6/U15와 owner-scoped data를 보유한 모든 product domain; accounts/trends/middleware/BFF 및 각 maintenance executor | G3 및 관련 G4/G5. late write/control copy 포함 purge, 익명 token/즉시 suppression, identity/spoof 방어 |
| REM-4 Corpus Integrity / `rem-4-corpus-integrity` | F03/F11/F12; R4A/R4R/SEARCH, generation-bound evidence와 승인된 repair | U1/U2/U5/U6; ingestion audit/repair, discovery assembler/policy, frontend classifier, health | G2/G4/G5. fixture/source/completeness, degraded-empty/no-match, verified calibration 및 별도 destructive gate |

문서 slug는 이후 `aidlc-docs/construction/{slug}/`에서 사용한다. 애플리케이션 code는 workspace root의 승인된 source 경로에 둔다. 이 계획 승인으로 새 code directory나 runtime을 생성하는 것은 아니다.

### 17개 component의 delivery 배치

Primary는 이 cycle의 통합 책임이다. 공통 component의 인스턴스나 business authority를 primary REM 하나로 중앙집중화하지 않는다.

| Component | Primary REM | 필수 contributor / owner 경계 |
|---|---|---|
| EDGE | REM-2 | REM-3의 F10 및 token 경로, U5/U6/U3의 기존 ingress 권위 |
| UI | REM-2 | REM-3 해지 UX, U5/U13; REM-4 검색 상태는 SEARCH 경계 |
| AUTH | REM-2 | 최초 current projection/consumer 통합을 U3/resource owner 코드에서 제공. REM-3 lifecycle/system-purpose 강화 및 REM-4의 허용 operator 소비 |
| RK | REM-2 | REM-1 shared 계약/검증, REM-3/4의 독립 operational instance 및 자기 realm store |
| DELIVERY | REM-2 | REM-3 제한된 token observer 및 REM-4 operator 결과 instance |
| EXEC | REM-3 | REM-2의 초기 write fence/U1 private producer, REM-4 repair; 실제 adapter는 각 data owner가 소유 |
| R1C | REM-1 | platform evidence read consumer 및 U6 운영 관측 |
| R1R | REM-1 | 각 domain의 schema/migration/lock owner 및 CI/deploy 담당 경계 |
| R2A | REM-2 | U1/U3/U7/U11/U12 context/namespace 및 U5 bridge |
| R2W | REM-2 | U7 generation core, U1 source builder/reader, domain-owned current authority |
| R3C | REM-3 | U15 token/settings/sender 및 U5 observer 경로 |
| R3P | REM-3 | U3 lifecycle 및 모든 등록된 domain EXEC/owner store |
| R3E | REM-3 | U5 BFF/U6 gateway/U3 limiter의 로컬 집행 |
| R4A | REM-4 | U1 corpus 규칙 및 U2 eval/calibration 규칙 |
| R4R | REM-4 | U1의 purpose-bound mutation port 및 U6 backup/restore 증거 |
| SEARCH | REM-4 | U2 결과/정책 및 U5 분류, 기존 검색 경계 유지 |
| OBS | REM-1 | U6 관측 계약/공통 규약 선행; REM-2/3/4가 자기 entry/worker/queue/health 인수를 구현 |

초기 AUTH/current projection 및 EXEC write-fence처럼 REM-2가 실제로 필요로 하는 provider 변경은 REM-2 slice에 포함해 원 domain owner review를 받는다. REM-3가 primary라는 이유로 모든 EXEC 구현을 뒤로 미루지 않는다. 후속 lifecycle/purge/consent 연결은 REM-3에서 통합 검증하고 G3 전에는 공개 job activation을 허용하지 않는다. 공통 envelope/contract는 REM-1이 조정하며, 후속 domain schema 확장은 versioned 변경 및 shared review를 거친다.

### 전체 85개 story의 product owner 정합화 계획

기존 story map은 45개 core 표 및 후속 일부 range 주석만 갖고 있어 최신 stories.md와 수량이 다르다. Part 2에서는 아래 규칙을 **85개 개별 story 행**으로 펼쳐 단일 current map을 작성하고 기존 표/수치는 이력으로 표시한다.

| Story 집합 | 수 | Canonical product story owner |
|---|---:|---|
| 기존 core US-H/D/A/L/I/R/S/CG/P | 45 | 기존 45행의 Owner 유지. 현재 story 제목/기여/trace와 정합시키되 ownership을 재배정하지 않음 |
| US-NV1~9 | 9 | U12 |
| US-EV1~9 | 9 | U11 |
| US-AG1~7 | 7 | U13. 기존 AG1~6 범위를 AG7의 frontend 품질 인수까지 완결 |
| US-OB1~4 | 4 | U14 |
| US-TN1~3 | 3 | U15 |
| US-WR1 / US-WR2 | 2 | 각각 U11 / U12 |
| US-SB1~3 | 3 | U16 |
| US-RJ1~3 | 3 | U5 (공통 사용자 job 경험의 story 책임). backend business/data 권위는 DAD1의 기존 domain/REM operational 경계를 따름 |

합계는 85개다. 각 story는 product owner 한 개를 가지며, implementation/quality contributor는 여러 개일 수 있다. 같은 기능을 여러 owner의 독립 story로 복제하지 않는다.

### 이번 신규/개정 story 18개의 REM delivery 배치

| Story | Product owner | Primary REM | 필수 추가 기여 |
|---|---|---|---|
| US-RJ1 | U5 | REM-2 | REM-3 admission 보호, U3/U6 및 각 업무 domain |
| US-RJ2 | U5 | REM-2 | REM-3 observer/receipt, U6 및 해당 service별 failure/compatibility |
| US-RJ3 | U5 | REM-2 | U1/U3/U7/U11/U12 context/권한, REM-3 lifecycle |
| US-S1 | U7 | REM-2 | U1 canonical source, U5 |
| US-S2 | U7 | REM-2 | U1 canonical source, U5 |
| US-S3 | U7 | REM-2 | U1 asset/DocModel, U5, U3 권한 |
| US-S5 | U7 | REM-2 | U5/U6 cache-backed job/진행/실패 |
| US-NV7 | U12 | REM-2 | U13의 REM 하위 작업 표시 |
| US-EV4 | U11 | REM-2 | U1 user_docmodel, U3 권한, U13 |
| US-EV7 | U11 | REM-2 | U13 재열람/현재 권한 |
| US-AG4 | U13 | REM-2 | U11/U12, U5 공통 job 상태 |
| US-AG5 | U13 | REM-2 | U1/U11/U12 private 첨부와 U3 권한 |
| US-A6 | U3 | REM-3 | REM-2 및 모든 owner store, U5/U10 |
| US-TN2 | U15 | REM-3 | U5 token observer, U3/U6의 제한된 접근/집행 |
| US-EV8 | U11 | REM-3 | U3 lifecycle, REM-2/U1 late-write 및 private 결과 정리 |
| US-R2 | U6 | REM-4 | REM-2/3의 job 실패/복구 및 U2/U5 저하 |
| US-R4 | U6 | REM-1 | REM-2/3/4의 local instrumentation/경보/trace |
| US-R5 | U6 | REM-1 | REM-2/3/4의 실제 role별 health/readiness |

나머지 67개 story는 product owner와 기존 추적성을 유지한다. REM primary가 없는 기존 story도 관련 F01~F13 회귀 검증에서 필요하면 참조하되 제품 범위를 자동 확대하지 않는다. 새 runtime 공통 코드와 모든 service-local 검증은 primary/contributor 양쪽의 완료 조건에 포함한다.

### Finding primary 배정

| Finding | Primary REM | 필수 원 domain/검증 표면 |
|---|---|---|
| F01 | REM-2 | U1/private context, U3 권한, U7 public namespace, U11/U12 |
| F02 | REM-2 | U7 canonical source/owner variant, U1/U2 source 계약 |
| F03 | REM-4 | U1 corpus/repair, U6 readiness, verified source |
| F04 | REM-3 | U3 lifecycle 및 모든 owner store/job/control data |
| F05 | REM-2 | U7/RK/worker, U5 접수/완료/timeout |
| F06 | REM-1 | 각 package lock/artifact/CI/SBOM |
| F07 | REM-2 | U1 asset, U3 owner/license 권한, U5 binary/CSP |
| F08 | REM-1 | domain migration 정의, 단일 ordered registry/startup/CLI |
| F09 | REM-3 | U15 token/consent/sender, U5 실제 link/observer |
| F10 | REM-3 | U5 trusted origin/BFF, U6/U3 동일 client identity |
| F11 | REM-4 | U2 assembler, U5 state classifier |
| F12 | REM-4 | U1 verified corpus, U2 calibration/정책 |
| F13 | REM-1 | shared schema 및 실제 Python/TS build-consumed bindings |

### RJ-AC primary 및 contributor 계획

| 인수 | Primary REM | 필수 integration 기여 / gate |
|---|---|---|
| RJ-AC01 | REM-2 | REM-3의 suppression admission; G2/G4 |
| RJ-AC02 | REM-2 | REM-3 status-query instance; G0/G2/G4 |
| RJ-AC03 | REM-2 | REM-4 SEARCH 저하, REM-3 업무 outcome; G4 |
| RJ-AC04 | REM-2 | REM-3 observer와 각 service retention; G2/G4 |
| RJ-AC05 | REM-2 | U3/resource owner 및 REM-3/4 목적별 current authority; G2/G3/G4 |
| RJ-AC06 | REM-2 | REM-3 재전달/삭제, REM-4 operation instance; G2/G3 |
| RJ-AC07 | REM-2 | U7/U1 canonical source/cache; G2/G4 |
| RJ-AC08 | REM-2 | U5 BFF/UI, U1 manifest, U3 권한; G2/G4 |
| RJ-AC09 | REM-3 | 모든 domain EXEC 및 REM-2/4 owner-bound control data; G3/G5 |
| RJ-AC10 | REM-3 | U15 sender/settings, U5 제한 observer; G3/G4 |
| RJ-AC11 | REM-3 | U3 직접 제어, U5/U6 ingress, REM-2 admission fence; G3/G4 |
| RJ-AC12 | REM-1 | REM-2/3/4가 실제 queue/crash/reconnect/restore/health scenario를 각각 제공; G2/G4/G5 통합 |

### 의존성과 integration/activation 구분

1. **Contract/build 기반**: REM-1이 공통 검증/registry/contract 버전의 첫 gate를 제공한다. domain 의미의 sign-off는 원 owner가 유지하며 후속 변경은 review를 다시 거친다.
2. **Merge/isolated integration 순서**: REM-1 -> REM-2 -> REM-3 -> REM-4. 독립 구현 병렬성을 허용하되 이 순서와 각 service의 완전한 Construction loop/리뷰를 유지한다.
3. **Public activation**: REM-2 job 경로는 REM-3의 lifecycle/consent/identity 및 G4 검증 전 활성화하지 않는다. REM-3가 REM-2 data inventory를 소비하는 것은 integration/데이터 의존이며 역방향 source import나 순환 merge gate가 아니다.
4. **Corpus data gate**: REM-4의 relevance 집행은 검증된 generation/report/calibration에 종속한다. full rebuild/대량 reparse/reembed/live alias cutover는 별도 승인이다.
5. **Runtime/source**: DAD1의 source/synchronous DAG와 의도된 async command/receipt feedback을 그대로 매핑한다. 공유 store가 임의 cross-domain write 또는 다른 service의 controller import를 허용하지 않는다.
6. **Done**: 각 unit은 자기 finding 및 배정된 story/RJ-AC의 primary/contributor 구현과 실제 consumer/role 검증을 제출한다. 최종 F01~F13/RJ-AC01~12 통합 및 안전한 live 변경은 WPR2 G0~G5와 별도 실행 승인을 따른다.

### 필수 산출물 및 Part 2 생성 체크리스트

- [x] 승인된 본 계획과 DAD1/WPR2 입력 및 기존 세 unit artifact, 85개 story ID를 다시 확인했다.
- [x] `application-design/unit-of-work.md`에 REM 4개 정의/역할/산출/기여 경로/document slug/완료 기준과 17 component 배치를 추가했다. U1~U16 authority 및 과거 배포 설명의 이력 범위를 명시했다.
- [x] `application-design/unit-of-work-dependency.md`에 C/M/R/E/D/A 관계, merge matrix, runtime/data edges 및 공동 activation/별도 destructive gate를 추가했다.
- [x] `application-design/unit-of-work-story-map.md`에 85개 개별 current product-owner 행과 이번 18개 story의 REM primary/contributor를 생성했다. 기존 표/수치는 이력으로 보존했다.
- [x] 17개 component를 unit 정의에, F01~F13 및 RJ-AC01~12의 REM primary/contributor와 gate를 story map에 반영했다.
- [x] 실제 story ID 집합과 current map을 비교하고, core 45 owner 및 18개 delivery 배정, 17 component/13 finding/12 RJ-AC primary를 승인 계획과 대조했다. 합계 85/18/17/13/12, 추가 delivery primary 없는 기존 story 67개를 확인했다.
- [x] DAD1 business/data authority, single-writer/local instance, C/M/R/E/D/A 의존 및 네 service/세 artifact 정합성을 검토했다. M/source/sync DAG와 의도된 E feedback을 구분했다.
- [x] `unit-of-work.md`에 4개 unit의 확장 책임 및 SECURITY 15/RESILIENCY 15/PBT 10개 per-rule 배정과 N/A/후속 검증을 기록했다.
- [x] 세 unit artifact와 plan의 Prettier debug-check, ID/title/owner/primary 집합 비교 및 `git diff --check`를 수행하고 plan/state/audit를 갱신했다.
- [x] UGR1 Units Generation 산출물 완료 리뷰를 준비·기록했다.
- [x] UGR1의 명시 승인 후 Construction의 REM-1 Functional Design으로 진행했다. 사용자 "UGR1: A" (2026-09-19).

## UGP1 - Deployable-Service Unit Plan Approval

**Unit of work plan complete. Review the plan in aidlc-docs/inception/plans/unit-of-work-plan.md. Ready to proceed to generation?**

A) **Approve Plan** - 위 네 unit, product/delivery ownership 구분, 85개 story 정합화 및 18개 변경 story/17개 component/13개 finding/12개 인수 배치와 Part 2 계획을 승인한다. (권장)

B) **Request Changes** - 아래 답변 태그 뒤에 변경할 grouping, primary/contributor 또는 의존성/완료 기준을 기술한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 unit 분해 또는 진행 방향을 기술)

[Answer]: A

UGP1=A는 본 재시작 계획과 Part 2 생성의 승인이다. 생성된 세 unit 산출물은 별도 완료 리뷰를 거친다.

### Part 1 검증 기록 - 2026-09-19

- DAD1의 네 service와 17개 component를 배치표에 대조했다. component/finding/RJ-AC 및 이번 변경 story의 primary는 각각 한 REM이며 필요한 contributor를 명시했다.
- 전체 story 계획은 45 + 9 + 9 + 7 + 4 + 3 + 2 + 3 + 3 = 85개다. 신규/개정 delivery 대상은 REM-2 12개, REM-3 3개, REM-4 1개, REM-1 2개로 총 18개이며 기존 67개와 구분했다.
- merge/isolated integration의 선행 순서와 public activation의 REM-2/3 공동 보호 조건을 구분했다. 초기 AUTH/EXEC provider를 후속 unit까지 미루는 순환 개발 전제는 두지 않는다.
- 기존 U1~U16과 DAD1의 canonical business/data authority 및 source/sync DAG를 유지한다. shared library/port를 추가 runtime service로 계산하지 않는다.
- `prettier --debug-check`로 unit plan 및 승인 상태가 변경된 application design plan의 Markdown parsing을 확인했고 `git diff --check`가 통과했다. 새 diagram은 작성하지 않았다.
- 이는 Part 1 계획 검증이다. 85개 개별 current map과 unit 정의/의존성 artifact의 전수 검증은 UGP1 승인 후 Part 2에서 실행한다.

### Part 2 검증 기록 - 2026-09-19

- `unit-of-work.md`, `unit-of-work-dependency.md`, `unit-of-work-story-map.md`에 현재 REM 단위 산출물을 생성하고 기존 정의/매핑을 이력으로 보존했다.
- 실제 `stories.md`의 85개 ID 및 현재 제목을 새 map과 추출/정렬 비교해 정확히 일치함을 확인했다. 중복 ID와 누락은 없고 모든 current 행에 U1~U16 중 product owner 하나가 있다.
- 이력 core 45행의 owner를 추출해 현재 core 45행과 비교했다. 모두 동일하다. 후속 AG/OB/TN/WR/SB 및 신규 RJ는 UGP1의 owner로 완결했다.
- 승인 계획과 산출물의 18개 `(story, product owner, REM primary)` 쌍, 17개 `(component, REM primary)`, 13개 `(finding, REM primary)`, 12개 `(RJ-AC, REM primary)` 집합이 각각 일치한다.
- current map의 REM primary 18개와 기존 67개를 확인했다. unit별 primary story 수는 REM-1=2, REM-2=12, REM-3=3, REM-4=1이다. product owner별 합계도 85이며 U10은 명시된 contributor-only 경계다.
- merge matrix는 REM-1 -> REM-2 -> REM-3 -> REM-4의 하향 의존으로 비순환이다. source/sync DAG는 DAD1을 계승하며 E feedback과 A 공동 activation을 M edge에 혼합하지 않았다. 초기 AUTH/EXEC 및 최종 통합 인수의 시점을 검토했다.
- SECURITY 15개/RESILIENCY 15개/PBT 10개의 unit-level 배정 및 N/A/후속 검증을 기록했다. single-Mac 예외와 PBT Full 유지, 현 unit 배정의 blocking finding 없음.
- 세 산출물 및 plan의 `prettier --debug-check`, `git diff --check`가 통과했다. 새 diagram은 없으며 기존 도식은 이력으로 보존했다. 검증은 분해/문서 정합성이며 구현·runtime 합격을 의미하지 않는다.

## UGR1 - Units Generation Artifact Approval

생성된 세 unit 산출물과 current story/인수 매핑을 어떻게 진행할까?

A) **Approve & Continue** - 산출물을 승인하고 Construction의 **REM-1 Functional Design**으로 진행한다. (권장)

B) **Request Changes** - 아래 답변 태그 뒤에 변경할 unit 경계, owner/contributor, 의존성 또는 매핑을 기술한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 변경 또는 진행 방향을 기술)

[Answer]: A

**승인 기록**: 2026-09-19T08:19:25Z. 사용자 `UGR1: A`로 세 unit 산출물을 승인하고 REM-1 Functional Design을 시작했다.
