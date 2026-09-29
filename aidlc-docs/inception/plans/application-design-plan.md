# 애플리케이션 설계 계획 (Application Design Plan)

> **현재 승인 기록**: 하단 Deployable-Service 설계 검증 기록과 DAD1을 참조한다. DAD1=A로 다섯 설계 산출물이 승인됐고 다음 단계는 Units Generation 재시작이다. 초기 DQ/RQ 계획은 해당 시점 이력이다.

**단계**: INCEPTION → Application Design · **일자**: 2026-06-15
**입력**: `requirements.md`(FR/NFR/SEC/RES/QT), `stories.md`(21개), `personas.md`(P1/P2/OP), `execution-plan.md`(예비 유닛 U1~U6).
**범위**: 고수준 컴포넌트 식별 + 서비스 계층 설계(상세 비즈니스 로직은 CONSTRUCTION/Functional Design). **기술 스택(언어·프레임워크)은 여기서 확정하지 않음** — NFR Requirements/Construction 소관. 단 **아키텍처 스타일·토폴로지·통신 패턴**은 본 단계에서 결정.

아래 설계 질문에 답하거나(또는 **"approve plan"** 으로 권장안 수락) 후, 설계 산출물을 생성한다.

---

## 설계 질문 (Design Questions)

## DQ1 — 아키텍처 스타일
배포·운영 단위를 어떻게 구성할까? (중간 티어·소규모 팀·공개 프로덕션·단일 리전 멀티 AZ 전제)

A) **모듈형 모놀리스 + 분리된 인제스천 워커(권장)** — 단일 배포 API(도메인 모듈 경계 명확) + 스케줄 인제스천 잡 분리. 운영·비용 단순, 데모·확장 균형.

B) 마이크로서비스 — 유닛별 독립 서비스(운영 복잡도↑, 소규모 팀엔 과함).

C) 풀 서버리스 — 기능별 Lambda 함수(이전 사이클 경험; 콜드 스타트·NFR-P1 긴장).

D) 하이브리드 — 서버리스 인제스천 + 모놀리스 API 등 혼합.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## DQ2 — 프런트엔드/백엔드 토폴로지
폰 우선 모바일 웹(NFR-U1/U2)을 어떻게 전달할까?

A) **SSR 모바일 웹(예: Next.js) + 백엔드 API(권장)** — 이전 사이클 Amplify/Next.js 경험 부합, 폰 목업 프레임(NFR-U2) 처리 용이.

B) SPA + 별도 API.

C) 기타.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## DQ3 — 인제스천 실행 모델
arXiv 인제스천·인덱싱(U1/FR-6)을 어떻게 실행할까?

A) **스케줄 배치 잡/워커(API와 분리)(권장)** — 일 1회 갱신, 사용자 경로와 디커플; 실패가 검색에 영향 없음.

B) API 서비스 내부 작업.

C) 이벤트 드리븐(신규 논문 트리거).

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: C

## DQ4 — 컴포넌트 조직 방식
코드/모듈을 어떻게 묶을까?

A) 유닛별 모듈(Discovery/Accounts/Library/Ingestion/Ops).

B) 레이어드(컨트롤러/서비스/리포지토리)만.

C) **하이브리드(권장)** — 도메인 모듈(유닛) + 공유 레이어(공통 어댑터·횡단 관심사).

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: C

## DQ5 — 횡단 관심사 위치
비용 가드/서킷 브레이커(NFR-C1), 근거화 강제(FR-5), 관측성(NFR-O1), 인증/인가(SEC-8/12)를 어디에 둘까?

A) **전용 횡단 모듈/미들웨어(권장)** — 게이트웨이/미들웨어 계층에 집중(SEC-11 격리 원칙 부합).

B) 컴포넌트별 내장.

C) 외부 서비스 위임.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## DQ6 — 통신 패턴
컴포넌트 간 통신은?

A) **사용자 경로 동기 REST + 인제스천 비동기/스케줄(권장)** — 디스커버리는 요청/응답, 인제스천은 잡.

B) 전부 동기.

C) 이벤트 드리븐 전반.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: C

## DQ7 — API 스타일
클라이언트-백엔드 API는?

A) **REST(권장)** — 단순, 모바일 웹·캐싱 친화.

B) GraphQL.

C) 기타.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

---

## 필수 설계 산출물 (답변·승인 후 생성)
- [x] `application-design/components.md` — 컴포넌트 정의·책임·인터페이스
- [x] `application-design/component-methods.md` — 메서드 시그니처·입출력(상세 비즈니스 규칙은 Functional Design)
- [x] `application-design/services.md` — 서비스 정의·오케스트레이션
- [x] `application-design/component-dependency.md` — 의존성 매트릭스·통신 패턴·데이터 흐름
- [x] `application-design/application-design.md` — 위 문서 통합본
- [x] 설계 완전성·일관성 검증(스토리/요구사항 추적) — 3 critic(아키텍처/추적성/경계) 비평→보정 반영

## 생성 단계 실행 방식 (승인 후)
- 6 유닛(U1~U6)에 대한 컴포넌트·메서드·서비스·의존성을 **병렬 생성 → 적대적 비평(일관성·추적성·경계) → 통합**(멀티에이전트 워크플로). API 회복 상태이므로 워크플로 사용.

---

## 2026-09-19 F01-F13 교정 Application Design Amendment Plan

**입력**: 승인된 `verification-remediation-2026-09-18.md`와 `verification-remediation-2026-09-18-workflow-plan.md`
**범위**: REM-1~REM-4의 고수준 컴포넌트, 인터페이스, 서비스 오케스트레이션, 의존 관계. 상세 비즈니스 규칙과 기술 선택은 Construction에서 확정한다.

### 실행 체크리스트

- [x] 기존 application design 5종과 현재 코드 경계를 대조한다.
- [x] REM-1~REM-4의 컴포넌트/메서드/서비스/의존성 결정이 필요한 지점을 식별한다.
- [x] 아래 RQ1~RQ7의 답변을 모두 수집하고 모순/모호성을 검증한다.
- [x] `application-design/components.md`에 remediation 컴포넌트 정의와 책임을 추가한다.
- [x] `application-design/component-methods.md`에 remediation 메서드 시그니처와 입출력을 추가한다.
- [x] `application-design/services.md`에 remediation 서비스 및 오케스트레이션을 추가한다.
- [x] `application-design/component-dependency.md`에 의존성, 통신 패턴, 데이터 흐름을 추가한다.
- [x] `application-design/application-design.md`에 통합 요약과 F01-F13 추적성을 추가한다.
- [x] Security, Resiliency custom, PBT Full 및 설계 완전성/비순환성을 검증한다.

### 설계 질문

## RQ1 - Remediation Component Placement

REM-1~REM-4 컴포넌트를 코드에 어떻게 배치할까?

A) 기존 도메인 패키지가 기능을 소유하고, migration registry·contract generator·repair manifest처럼 실제로 공유되는 최소 컴포넌트만 공통 경계에 둔다. 새 runtime remediation 서비스는 만들지 않는다. (권장)

B) F01-F13을 전담하는 신규 remediation runtime 모듈을 만들고 기존 도메인이 이를 호출한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ2 - Private Document Read Boundary

`userdoc:` private DocModel과 파생 자산은 어떤 API 경계로 읽을까?

A) 공용 paper/summary/asset 경로는 `userdoc:`를 항상 거부하고, evidence attachment 또는 novelty manuscript처럼 owner context가 이미 있는 전용 경로와 `UserDocModelCoordinator`에서만 읽는다. (권장)

B) 중앙 private-document owner registry를 신설·backfill하고 범용 private DocModel/asset endpoint를 이번 cycle에 추가한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ3 - Summarization Job Contract

동기 예산을 넘는 uncached 요약/번역을 어떤 계약으로 비동기화할까?

A) 기존 `{status: "pending"}` 응답과 repeat-request polling 계약을 유지하되 canonical source/cache identity 기반 durable job marker, enqueue 결과, terminal failure, visibility/retry budget을 추가한다. (권장)

B) 명시적 owner-scoped job resource와 `jobId`/status endpoint를 신설하고 frontend polling을 새 계약으로 전환한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ4 - Account Purge Recovery Model

SQL과 private object storage를 함께 지우는 계정 파기를 어떻게 재시도 가능하게 만들까?

A) SQL 삭제 전에 대상 table/object/cache key를 durable purge manifest와 단계 상태로 동결하고, 단계별 성공을 기록해 실패 후 같은 manifest로 재개한다. (권장)

B) 매 재시도마다 현재 SQL/object 상태에서 대상을 다시 계산하고 별도 manifest/state는 저장하지 않는다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ5 - Trusted Client Identity

Cloudflare Tunnel -> Next.js BFF -> FastAPI 경로의 rate-limit client identity를 어떻게 전달할까?

A) tunnel-only BFF가 단일 `CF-Connecting-IP`를 검증·정규화해 private internal header로 덮어쓰고, FastAPI는 실제 socket peer가 loopback일 때만 이를 신뢰한다. 모든 JSON/PDF/SSE 경로가 같은 helper를 사용한다. (권장)

B) BFF가 client identity payload를 서명하고 FastAPI가 공유 secret으로 검증하는 별도 서명 프로토콜을 도입한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ6 - Corpus Audit and Repair Isolation

운영 fixture 제거와 corpus completeness/readiness를 어떤 컴포넌트 경계로 둘까?

A) ingestion 소유의 standalone audit/repair 도구가 generation-bound report와 exact backup/restore manifest를 만들고, API readiness는 최근 검증 report만 읽는다. startup/readiness는 corpus를 직접 수정하지 않는다. (권장)

B) API startup/readiness가 OpenSearch를 직접 검사하고 발견한 fixture를 자동 삭제한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## RQ7 - Migration Registry Ownership

startup과 CLI migration 목록을 어떻게 단일화할까?

A) backend migration package가 명시적 ordered registry를 소유하고 startup/CLI가 같은 registry를 import한다. legacy ledger ID를 유지하고 이름 충돌을 시작 전에 거부한다. (권장)

B) startup/CLI가 매 실행 시 repository 전체의 migration directory를 자동 탐색해 정렬한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

### 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 RQ1~RQ7에 각각 A를 기록한다. 모든 답변을 검증하기 전에는 설계 산출물 생성으로 진행하지 않는다.

### 답변 분석 - 2026-09-19

- RQ1~RQ7은 모두 A로 확정됐다.
- 답변은 단일 선택이며 모호한 용어, 혼합 기준, 누락이 없다.
- 기존 도메인 소유권을 유지하고 최소 공유 컴포넌트만 추가하는 RQ1은 RQ2~RQ7의 경계와 일치한다.
- public/private 문서 분리(RQ2), repeat-request polling(RQ3), immutable purge manifest(RQ4), loopback trust boundary(RQ5), read-only corpus readiness(RQ6), explicit migration registry(RQ7) 사이에 상충이 없다.
- full corpus rebuild 별도 승인, single-Mac fault-domain 예외, Security Full 및 PBT Full 요구와 일치한다.

### 검증 결과 - 2026-09-19

- F01~F13 모두 `application-design.md`의 finding-to-component/service 표에 정확히 한 행 이상 추적된다.
- 기존 deploy/package 경계를 유지하며 새 runtime remediation service 또는 deployable unit이 없다.
- composition root 주입, report contract, domain port를 사용해 신규 package dependency cycle이 없다.
- public/private route, browser/object storage, untrusted internal header, readiness/repair 사이의 금지 edge가 명시됐다.
- Security Full: SECURITY-01~15 모두 Application Design 산출물 기준 Compliant, blocking finding 없음.
- Resiliency custom: RESILIENCY-01~07/10~15 Compliant; RESILIENCY-08 N/A; RESILIENCY-09는 horizontal autoscale N/A이고 bounded concurrency/backpressure/capacity gate로 대체. blocking finding 없음.
- PBT Full: detailed rule의 stage applicability에 따라 PBT-01~10은 Application Design에서 N/A이며, downstream Functional Design/NFR Requirements/Code Generation/Build and Test로 test surface를 추적했다.
- 새 Mermaid/ASCII diagram을 추가하지 않고 numbered text data-flow alternative를 사용했다. Markdown amendment table/fence structural check와 `git diff --check`가 통과했다.

### Supersession - 2026-09-19

- 사용자 UQRF1=B가 RQ1=A를 명시적으로 대체했다.
- 본 amendment plan과 생성한 5개 artifact의 RQ1=A remediation sections는 승인 이력으로 보존하지만 현재 implementation authority가 아니다.
- Units Generation을 중지하고 Workflow Planning으로 복귀했다. 수정 workflow 승인 후 네 deployable remediation services를 위한 새 Application Design plan/questions를 작성한다.

---

## 2026-09-19 Deployable-Service Application Design Redesign Plan

**상태**: 다섯 Application Design 산출물 생성·검증 및 DAD1=A 승인 완료 (2026-09-19)
**권위 입력**: UQRF1=B/WPR1=A, DSRQ/명확화 결정, RJR1=A 요구사항, RJS2=A story/persona, WPR2=A 실행 계획 및 single-Mac production runtime.
**범위**: REM-1~REM-4의 장기 독립 배포 경계, API/event 계약, 데이터 권위, 내부 인증, dependency DAG, cutover와 control-plane 권한

### 현재 runtime 분석에서 도출한 비협상 제약

- public ingress는 Cloudflare -> Next.js BFF -> FastAPI gateway를 유지하며 browser가 REM listener를 직접 호출하지 않는다.
- 모든 REM listener는 loopback/private binding, 독립 service identity, versioned artifact, launchd lifecycle, liveness/readiness를 가져야 한다.
- shared store admin credential, unsigned owner header, automatic fail-open fallback, unbounded synchronous work, queue-only canonical state와 startup mutation은 금지한다.
- REM-3의 client-identity policy는 service가 version/evidence를 소유하되 BFF/gateway의 rate-limit 이전 earliest trusted boundary에서 집행한다. REM-3 synchronous availability를 모든 request의 선결조건으로 만들지 않는다.
- REM-4의 degraded-empty/relevance policy는 service가 version/calibration evidence를 소유하되 U2/U5의 canonical response boundary에서 집행한다. audit/readiness는 repair 또는 alias cutover를 자동 실행하지 않는다.
- ElasticMQ는 wake-up/redelivery transport이며 durable operation/outbox state를 대체하지 않는다.
- full corpus rebuild, bulk reparse/reembed, live alias cutover는 별도 명시 승인 전 실행하지 않는다.

### 실행 체크리스트

- [x] 승인된 요구사항, workflow replan, superseded Application Design, 현재 single-Mac runtime과 코드 seam을 대조한다.
- [x] 네 deployable service의 설계를 차단하는 최소 경계 결정을 식별한다.
- [x] DSRQ1~DSRQ7에 상호 배타적인 선택지, 권장안, 위험한 대안을 기록한다.
- [x] DSRQ1~DSRQ7의 답변을 모두 수집한다. 사용자 표기 DQ1~DQ7을 현재 DSRQ1~DSRQ7로 대응했다.
- [x] 답변의 누락, 모호성, 상호 모순과 UQRF1=B/UQR5=A 정합성을 검토한다. DSRQ4=C의 외부 계약 범위와 result/status/control 경계가 미확정이다.
- [x] `application-design-deployable-services-clarification-questions.md`에 DSRQF1~DSRQF2 후속 질문을 작성한다.
- [x] DSRQF1~DSRQF2를 수집하고 외부 계약, 운영 경계, 선행 단계 영향의 모호성을 모두 해소한다. DSRQF1=A, DSRQF2=A (2026-09-19).
- [x] 공개 job 계약에 필요한 Requirements/User Stories/Workflow 개정 및 각 단계 승인을 완료했다.
  - [x] Requirements 개정 RJR1=A 승인 (2026-09-19).
  - [x] User Stories 산출물 완료 승인 RJS2=A (계획 RJS1=A, 2026-09-19).
  - [x] Workflow Planning WPR2=A 승인 (2026-09-19).
- [x] `application-design/components.md`를 네 deployable service 경계 기준으로 재설계했다. component ID, ordinary writer/maintenance authority, criticality 및 직접 제어 경계를 정의했다.
- [x] `application-design/component-methods.md`에 versioned public/internal API, command/receipt, typed operation/authority/결과 계약을 정의했다.
- [x] `application-design/services.md`에 DS-1~DS-8의 orchestration, current authority, consent/write barrier, domain receipt saga, failure/cutover를 정의했다.
- [x] `application-design/component-dependency.md`에 source/synchronous DAG, 의도된 async command/receipt feedback, 금지 edge 및 검증된 Mermaid data flow 2개와 text alternative를 정의했다.
- [x] `application-design/application-design.md` §8에 통합 설계, 17개 component/4 service, F01~F13 및 RJ-AC01~12 추적성, supersession과 per-rule extension review를 반영했다.
- [x] Security Full, Resiliency custom single-Mac, PBT Full의 단계별 준수 상태를 검증했다. 통합 개요 §8.7의 per-rule 근거와 N/A/후속 적용을 확인했다.
- [x] Markdown 구조, 특수문자, diagram 및 `git diff --check`를 검증했다. 5문서 Prettier debug-check, 저장된 Mermaid 2개 렌더, 17 component/13 finding/12 RJ-AC/8 flow 정합 확인.
- [x] DAD1에서 Application Design 산출물 승인을 받고 Units Generation을 재시작했다. 사용자 "DAD1: A" (2026-09-19).

### 설계 질문

## DSRQ1 - Service Runtime and Deployable Form

single-Mac production에서 네 REM service를 어떤 실행/배포 형태로 운영할까?

A) 각 REM을 독립 version/artifact와 launchd lifecycle을 가진 host-native service package로 만든다. request-facing 역할은 loopback API daemon, background 역할은 같은 artifact의 별도 worker/one-shot role로 감독한다. REM-1은 control API daemon과 명시적 CLI/one-shot runner를 함께 제공하며 기존 data store는 OrbStack에 유지한다. (권장)

B) 각 REM을 정확히 하나의 장기 HTTP daemon으로 만들고 worker, scheduler, migration, repair 작업도 그 request process 안에서 실행한다.

C) 네 REM을 OrbStack Compose container service로 배포하고 API/worker 역할도 container 안에서 운영한다. host launchd는 Compose lifecycle만 감독한다.

D) 네 REM을 하나의 remediation host process에 함께 탑재하고 논리 모듈로만 분리한다. 이 선택은 UQRF1=B의 독립 배포 경계를 충족하지 못한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## DSRQ2 - Canonical Domain and Runtime Ownership

UQR5=A의 기존 domain ownership과 UQRF1=B의 독립 service runtime authority를 어떻게 함께 유지할까?

A) REM service shell이 deployment, transport, orchestration, service credentials, operational state를 소유하고 기존 domain package가 business rule, DTO/schema, migration definition과 데이터 의미의 canonical authority를 유지한다. REM-1은 registry 검증과 evidence를 소유하지만 각 domain schema 의미를 재정의하지 않는다. (권장)

B) business rule, schema, migration과 data semantics를 각 REM service package로 이전하고 기존 domain package는 compatibility adapter로만 남긴다.

C) cutover 이후에도 REM service와 기존 domain package가 같은 rule/schema/data를 공동 수정하는 dual authority를 유지한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## DSRQ3 - Data and Dependency Topology

네 service의 persistent data 접근과 service 간 dependency를 어떻게 구성할까?

A) 기존 Postgres, Redis, OpenSearch, MinIO를 물리적으로 공유하되 service별 least-privilege credential, logical schema/key prefix/index grant를 둔다. 각 datum은 ordinary writer 하나만 가지며 다른 service는 versioned API/event 또는 immutable read projection으로 접근한다. (권장)

B) service마다 전용 physical store를 만들고 필요한 데이터는 versioned event/API로 복제한다.

C) 물리 store와 admin credential을 공유하고 각 service가 필요한 table/key/index를 직접 읽고 수정한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## DSRQ4 - Synchronous and Asynchronous Contracts

사용자 응답 경로와 장기 작업의 통신 계약을 어디에서 나눌까?

A) bounded read/status/stream만 synchronous API로 두고 generation, purge, audit, calibration, repair와 platform operation은 durable asynchronous operation으로 둔다. Postgres operation state/outbox가 진실원천이고 비영속 ElasticMQ는 wake-up/redelivery transport로만 사용한다. (권장)

B) generation, purge, audit, repair를 포함한 모든 service 작업을 synchronous RPC로 완료한다.

C) user-facing read/status까지 모두 queue/event 기반 비동기로 전환하고 모든 호출에 job resource를 요구한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: C

## DSRQ5 - Internal Authentication and Owner Context

gateway에서 REM service로 user/service identity를 어떻게 전달하고 검증할까?

A) 기존 gateway가 browser session을 검증하고, service hop은 별도 service identity와 짧은 수명의 audience-bound signed principal envelope를 함께 사용한다. 수신 service는 signature/audience/expiry를 검증한 뒤 object owner 권한을 다시 확인하며 browser는 REM listener를 직접 호출하지 않는다. (권장)

B) 각 REM service가 browser session cookie를 직접 받아 Redis session을 독립 검증하고 별도 delegated principal 계약은 두지 않는다.

C) loopback network를 신뢰해 unsigned user header와 공용 static secret만 전달하고 수신 service는 gateway의 owner 판정을 그대로 신뢰한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## DSRQ6 - Public Routing and Cutover

BFF/FastAPI routing과 기존 in-process 경로에서 service 경로로의 전환을 어떻게 수행할까?

A) public topology를 `Cloudflare -> Next.js BFF -> existing FastAPI gateway -> REM-2/3/4`로 유지한다. route별 strangler, side-effect 없는 shadow read, 명시적 manual switch와 bounded rollback window를 사용하며 authorization/integrity 경로의 automatic fail-open fallback과 dual write는 금지한다. REM-1은 user request path 밖에 둔다. (권장)

B) Next.js BFF가 path별로 REM service를 직접 선택하고 session/service authentication, timeout과 error translation도 service별로 수행한다.

C) 기존 FastAPI route를 한 번에 제거하고 네 service로 big-bang cutover하며 compatibility window를 두지 않는다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

## DSRQ7 - REM-1 Control-Plane Authority

REM-1 Platform Integrity Service가 runtime에서 어떤 권한을 가져야 할까?

A) 장기 control API는 version, compatibility, migration/contract/SBOM evidence와 readiness를 read-only로 제공한다. migration 적용, binding generation, dependency repair와 artifact promotion은 인증된 명시적 CLI/one-shot operation과 승인 gate로만 실행하며 startup이나 user request에서 자동 mutation하지 않는다. (권장)

B) REM-1 daemon이 각 service startup마다 migration, contract generation, dependency repair와 artifact promotion을 자동 실행한다.

C) REM-1을 offline CLI/CI 도구로만 만들고 장기 daemon/control endpoint는 운영하지 않는다. 이 선택은 장기 deployable service 요구를 다시 해석해야 한다.

X) 기타 (아래 `[Answer]:` 태그 뒤에 기술)

[Answer]: A

### 답변 방법

각 `[Answer]:` 뒤에 하나의 선택 문자와 필요한 설명을 기록한다. 모든 권장안을 채택하려면 DSRQ1~DSRQ7에 각각 A를 기록한다. 모든 답변을 검증하기 전에는 mandatory Application Design artifact를 생성하거나 Units Generation을 재개하지 않는다.

### 답변 분석 - DSRQ1~DSRQ7 (2026-09-19)

- 사용자 원문: `DQ1: A. DQ2: A, DQ3: A, DQ4: C, DQ5: A, DQ6: A, DQ7: A`
- 직전 안내의 현재 질문 게이트에 따라 DQ1~DQ7을 DSRQ1~DSRQ7로 기록했다. 문서 상단의 2026-06-15 DQ1~DQ7 답변은 해당 시점 이력이다.
- 7개 답변 모두 유효한 단일 선택이며 누락이 없다: DSRQ1=A, DSRQ2=A, DSRQ3=A, **DSRQ4=C**, DSRQ5=A, DSRQ6=A, DSRQ7=A.
- DSRQ1/2/3/5/6/7의 A는 독립 host-native 배포, 기존 domain의 business/schema authority, 공유 store의 단일 writer와 권한 분리, signed delegated identity, gateway 경유 점진 전환, REM-1 read-only control plane으로 상호 정합적이다. DSRQ2=A는 UQR5=A의 기존 business authority와 장기 runtime coordination ownership을 구분한다.
- DSRQ4=C는 업무 read/status까지 queue/event와 job resource로 처리한다는 선택으로 보존한다. 외부 client에도 새 job 계약을 노출할지, gateway 내부에만 적용할지가 아직 명확하지 않다. DSRQ6=A는 routing/cutover를 정하지만 이 응답 계약까지 정하지는 않는다.
- 모든 status 조회가 다시 job을 만든다면 결과 전달/구독 경계가 필요하다. F07의 same-origin asset bytes, DSRQ7=A의 read-only evidence, RESILIENCY-06의 health/readiness가 그 job 규칙에 포함되는지도 명시해야 한다. event-driven 설계 자체가 불가능하다는 판정은 아니다.
- 외부 계약이 job-first로 바뀌면 workflow의 Requirements 재사용 및 User Stories skip 근거를 다시 평가해야 한다. 기존 NFR-P1 결과 도달 지연 목표, F05 pending/poll, F07 자산 전달 인수의 변경은 transport 선택으로 자동 승인되지 않는다.
- 후속 질문: `application-design-deployable-services-clarification-questions.md`의 DSRQF1~DSRQF2. 두 답변과 선행 단계 영향이 정리된 뒤 설계 산출물 생성 순서를 확정한다.

### 명확화 결과 - DSRQF1=A, DSRQF2=A (2026-09-19)

- DSRQ4=C의 공개 job 계약을 REM으로 이관되는 F01~F13 관련 사용자 업무 경로에 적용한다. frontend의 job 접수/대기/완료/실패 및 결과 수신이 이번 변경 범위에 포함된다.
- 업무 read/status는 queue/event job이며, 접수 확인과 event 구독/재연결, 완료 결과/asset bytes 전달은 새 업무 job을 생성하지 않는다. health/readiness와 REM-1 evidence도 bounded 직접 관측 경로다.
- 기존 domain authority, single-writer, delegated identity, gateway 경유 점진 전환과 정합적이다. 원 DSRQ4 답변 C와 두 명확화 답변을 함께 읽는다.
- 공개 응답 계약 변경으로 기존 Requirements 재사용/User Stories skip 근거가 대체됐다. 제한적 Requirements 개정부터 수행하고 User Stories 및 Workflow 개정을 승인받은 뒤 다섯 설계 산출물 생성을 재개한다.

### Deployable-Service 설계 검증 기록 - 2026-09-19

- 5개 mandatory artifact의 `2026-09-19 Deployable Services and Public Jobs` 절을 생성했다. 기존 superseded 설계는 이력으로 유지하고 각 파일 상단에 현재 리뷰 위치를 표시했다.
- component catalog의 **17개 ID**가 method inventory와 흐름/의존성에 대응한다. 네 deployable의 role/criticality, canonical business owner, ordinary writer 및 domain-owned privileged executor를 대조했다.
- public ClientJobSpec과 서버측 OperationIntent/grant를 분리하고, queued 업무/status와 직접 SSE/result/asset/health 예외를 검증했다. 익명 unsubscribe의 observer scope와 System 후속 작업 권한은 일반 user 권한과 분리했다.
- source import 및 synchronous call은 명시한 계층의 하향 dependency이며 callback cycle이 없다. async command/receipt/publication은 의도된 feedback으로 표시하고 parent/run fence에 결속했다.
- 삭제·재활성화 경쟁, quiescence, staging/command copy/recipient inbox 및 coordinator control-data 정리, consent handoff/새 opt-in revision 경쟁을 cross-document 검토했다. 파기 완료는 control cleanup 이후이며 queue ack나 lease 만료만으로 완료를 추정하지 않는다.
- F01~F13 **13행**, RJ-AC01~12 **12행**, DS-1~8 **8개**의 전수 연결을 확인했다. namespace/current authority/canonical source 인수는 legacy compatibility 경로에도 적용한다.
- Mermaid 2개는 작성 전 렌더와 저장된 `component-dependency.md` 재렌더 모두 통과했고 text alternative를 포함한다. 렌더 출력은 승인된 임시 디렉터리에 있다.
- 다섯 설계 문서의 `prettier --debug-check`가 통과했다. 후속 수정된 method/service 문서도 재검증했고 `git diff --check`가 통과했다. 이는 설계/문서 검증이며 실제 code dependency/runtime 검증은 Construction의 gate다.
- 확장: SECURITY-01~15 design-level Compliant; RESILIENCY-01~07/10~15 Compliant, 08 N/A(single-Mac), 09 bounded-capacity replacement; PBT-01~10은 Application Design N/A이며 downstream Full 검증 표면을 유지한다. 현재 설계에 적용되는 blocking finding 없음.

## DAD1 - Deployable-Service Application Design Approval

생성한 네 service/공개 job Application Design 산출물을 어떻게 진행할까?

A) **Approve & Continue** - `application-design/`의 5개 신규 설계 절과 추적성을 승인하고 Units Generation을 재시작한다. (권장)

B) **Request Changes** - 답변 태그 뒤에 변경할 component, contract, ownership 또는 orchestration을 기술한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 설계 변경 또는 진행 방향을 기술)

[Answer]: A

**승인 기록**: 2026-09-19T07:31:57Z. 사용자 `DAD1: A`로 다섯 신규 설계 절과 추적성을 승인하고 Units Generation Part 1을 재시작했다.
