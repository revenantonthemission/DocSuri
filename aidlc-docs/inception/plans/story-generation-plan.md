# 스토리 생성 계획 (Story Generation Plan)

> **공개 job 승인 기록**: 문서 하단의 `2026-09-19 REM 공개 job Story Amendment Plan`, Part 2 검증 기록 및 RJS2를 참조한다. RJS1 계획과 RJS2 산출물은 승인됐으며 다음 단계는 Workflow Planning 개정이다. 기존 PQ1~PQ5와 초기 완료 기록은 승인 이력이다.

**단계**: INCEPTION → 사용자 스토리(Part 1: 계획) · **일자**: 2026-06-15
**입력**: `requirements.md` (FR-1..11, NFR, SEC-1..15, RES-1..12, QT-1..4), 페르소나 P1(박지훈) / P2.

본 계획은 요구사항을 사용자 스토리로 변환하는 **방법**을 정의한다. 아래 계획 질문에 답하거나(또는 **"approve plan"** 으로 모든 권장안 수락) 후, `stories.md` + `personas.md`를 생성한다.

---

## 계획 질문 (Planning Questions)

## PQ1 — 스토리 분해 방식
스토리를 어떻게 조직할까?

A) **에픽 기반, 에픽 내 여정 순서(권장)** — 역량 에픽(디스커버리, 계정, 검색 저장 & 라이브러리, 인제스천, 신뢰성 & 운영)으로 묶고, 디스커버리 에픽 내에서는 히어로 여정 순으로 정렬.

B) 순수 사용자 여정 기반 — 스토리가 종단 흐름을 엄격히 따름.

C) 기능 기반 — 시스템 기능/컴포넌트 단위로 묶음.

D) 페르소나 기반 — P1 / P2 / 운영자 단위로 묶음.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## PQ2 — 페르소나 세트
스토리가 다룰 페르소나는?

A) **P1 + P2 + 경량 운영자/유지보수자(권장)** — P1(박지훈) 주, P2 부를 유지하고, 복원력/비용/AI 인시던트 스토리(RES-*, NFR-C1, CQ6 인시던트 클래스)를 담당할 최소 운영자 페르소나 추가.

B) P1 + P2 만 — 스토리는 순수 최종 사용자; 운영/비용/인시던트는 기능 스토리의 인수 기준으로만 처리, 운영자 페르소나 없음.

C) P1 만 — 단일 페르소나 MVP; P2 니즈는 P1에 흡수.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## PQ3 — 인수 기준 형식
인수 기준 형식은?

A) **Given/When/Then(Gherkin)(권장)** — 테스트 가능하며 QT-1..4·PBT 및 이후 테스트 생성에 깔끔히 매핑.

B) 조건 불릿 체크리스트.

C) 스토리별 서술형 "완료 정의(DoD)" 문단.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## PQ4 — 스토리 입도(granularity)
스토리를 얼마나 잘게 자를까?

A) **얇은 INVEST 수직 슬라이스 + 단일 종단 "히어로" 스토리(권장)** — 작고 독립적으로 테스트 가능한 슬라이스, 그리고 매직 모먼트 데모 전체(가입 → 자연어 질의 → 근거화 결과)를 담는 단일 히어로 스토리(데모 게이트용).

B) 얇은 수직 슬라이스만 — 별도 히어로 스토리 없음(데모는 슬라이스로 암시).

C) 더 굵은 에픽 크기 스토리 — 더 적고 큰 스토리.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

## PQ5 — 횡단 NFR / 품질 / AI 인시던트 관심사 표현 방식
비기능·AI 인시던트 관심사(엄격 근거화, 우아한 저하, 비용 폭발, 할루시네이션, 반쪽짜리 결과, 보안)를 어떻게 표현할까?

A) **하이브리드(권장)** — NFR/SEC 기대를 기능 스토리의 인수 기준에 엮고, 동시에 두드러진 관심사(엄격 근거화/기권, 우아한 저하, 비용 상한 서킷 브레이커, AI 인시던트 탐지)에 대해 별도의 품질/운영 스토리 몇 개 추가.

B) 인수 기준만 — 모든 NFR/SEC 관심사는 기능 스토리 기준으로만; 독립 비기능 스토리 없음.

C) 전용 스토리만 — 모든 NFR/SEC 관심사를 각각 독립 스토리로 분리.

X) 기타 (아래 [Answer]: 태그 뒤에 기술)

[Answer]: A

---

## 필수 산출물 (Part 2에서 생산)
- [x] `aidlc-docs/inception/user-stories/stories.md` — **INVEST**(Independent, Negotiable, Valuable, Estimable, Small, Testable) 충족 사용자 스토리.
- [x] `aidlc-docs/inception/user-stories/personas.md` — 페르소나 아키타입(P1 박지훈, P2, + PQ2=A이면 운영자).
- [x] 모든 스토리에 인수 기준(PQ3 형식).
- [x] 페르소나 → 스토리 매핑.
- [x] 요구사항 → 스토리 추적성(FR/NFR/SEC/RES/QT ID).

## Part 2 실행 체크리스트 (계획 승인 후 실행)
- [x] requirements §3로부터 personas.md 작성(+ 선택 시 운영자).
- [x] 디스커버리 에픽 스토리 작성(히어로 여정: 질의 → 검색 → 랭킹 → 표시 → 근거화/기권).
- [x] 계정 에픽 작성(가입/로그인/세션).
- [x] 검색 저장 & 라이브러리 에픽 작성.
- [x] 인제스천 에픽 작성(arXiv 수집 → 임베딩 → 인덱스 → 갱신).
- [x] 신뢰성 & 운영 에픽 작성(근거화/기권, 우아한 저하, 비용 상한, AI 인시던트 탐지) — PQ5 기준.
- [x] 모든 스토리에 인수 기준 + 추적성 추가.
- [x] INVEST 준수 자체 점검; 모든 FR이 ≥1 스토리를 갖는지 검증.
- [x] 완료 + 리뷰 게이트 제시.

---

## 2026-09-19 REM 공개 job Story Amendment Plan

**단계**: INCEPTION -> User Stories Part 2 (Generation)
**상태**: story/persona 생성·검증 및 RJS2=A 산출물 승인 완료 (2026-09-19)
**입력**: RJR1=A로 승인된 `requirements.md` FR-52/NFR-R4/QT-12/C-13 및 §14, `verification-remediation-2026-09-18.md` §10, 기존 `stories.md`/`personas.md`, `user-stories-assessment.md`의 2026-09-19 평가
**범위**: REM으로 이관되는 사용자 업무의 공개 job 경험 및 기존 인수의 정합성. DSRQ4=C와 DSRQF1/2=A가 정의한 업무 read/status와 직접 전달/운영 관측 경계를 따른다.

### Part 1 - 계획 체크리스트

- [x] RJR1 승인과 RJ-AC01~12를 확인한다.
- [x] User Stories 실행 필요성을 `user-stories-assessment.md`에 기록한다.
- [x] 기존 persona/story/traceability와 신규 사용자 흐름의 접점을 대조한다.
- [x] 질문 범주 8개와 story 분해 접근법 5개를 평가한다.
- [x] 제안 story 배치, 인수 coverage, 필수 산출물 및 Part 2 실행 단계를 작성한다.
- [x] 계획 내용, ID/참조, 질문 형식과 whitespace를 검증했다. RJ-AC01~12 전수 매핑, 신규 story ID 충돌 없음, RJS1 질문/빈 답변 1개 및 기타 선택지 확인, `git diff --check` 통과.
- [x] RJS1 답변을 수집하고 모호성/모순을 검증했다. 단일 선택 A이며 승인된 요구사항과 정합적이다.
- [x] story 접근법과 본 amendment plan의 명시 승인을 기록했다. 사용자 "RJS1: A" (2026-09-19).

### 문맥별 질문 범주 평가

| 범주 | 계획에 적용할 근거와 방법 |
|---|---|
| User Personas | 기존 P1/P2/OP를 유지한다. 로그아웃·익명 token 접근은 연구자의 상황이며, 운영 권한은 OP의 권한 있는 활동으로 표현한다. |
| Story Granularity | 얇은 사용자 가치 단위의 INVEST story. 접수/상태, 재연결, private 결과 열람을 분리하고 Given에 필요한 기존 job/결과 상태를 두어 독립 검증한다. |
| Story Format | 승인된 PQ3=A의 As/I want/so that + Given/When/Then + Traces를 재사용한다. |
| Breakdown Approach | 기존 에픽/ID를 개정하고 공통 job 여정은 작은 추가 에픽으로 묶는 구체적 hybrid. 아래 배치표를 승인 대상으로 제시한다. |
| Acceptance Criteria | RJ-AC01~12를 전수 매핑한다. 정상/실패/권한/재연결/중복/만료를 분리하고 관측 가능한 결과로 표현한다. |
| User Journeys | 요청 -> 접수/대기 -> 명시적 상태 확인 또는 결과 구독 -> 완료/실패 -> 재연결/재시도. 삭제·수신 해지의 즉시 보호와 운영 health는 별도 기존 story에 반영한다. |
| Business Context | 연구자의 기다림/오판/중복 작업과 private 결과 노출을 줄이고 OP가 실제 장애를 판정할 수 있게 한다. 기존 F01~F13 교정 목표에 추적한다. |
| Technical Constraints | C-13의 적용 범위, owner 권한, same-origin 결과 전달, 단일 Mac profile, NFR-P1의 결과 도달 기준을 지킨다. endpoint/schema/TTL/queue 구현은 후속 설계가 담당한다. |

이미 승인된 persona/형식/사업 범위를 다시 선택할 질문은 없다. 아래 RJS1에서 이 개정의 story 분해·배치와 전체 실행 계획을 승인하거나 변경한다.

### Story 분해 접근법 비교

| 접근법 | 장점 | 이번 변경의 trade-off |
|---|---|---|
| User Journey-Based | 접수부터 재연결/결과까지 경험을 따라 검증하기 쉽다. | 기존 domain 인수를 모두 옮기면 추적성과 ID 이력이 흔들린다. 공통 job 에픽 내부 순서에 적용한다. |
| Feature-Based | 요약/문서/자산별 기능 경계가 명확하다. | 동일한 job lifecycle 인수가 기능마다 반복될 수 있다. |
| Persona-Based | 연구자와 OP의 기대가 잘 드러난다. | P1/P2가 공유하는 경험이 중복된다. persona map으로 보완한다. |
| Domain-Based | 기존 business authority와 기능별 인수 소유를 유지하기 쉽다. | 횡단 재연결/상태 경험이 여러 에픽에 흩어질 수 있다. 기존 domain story 개정에 적용한다. |
| Epic-Based (권장) | 기존 에픽과 ID를 보존하면서 공통 job 경험을 한 곳에 모을 수 있다. | 공통 에픽과 domain story 사이의 명시적 인수 연결이 필요하다. 아래 coverage 표로 관리한다. |

### 제안 story 배치

기존 에픽 0~15에 영향을 받는 인수를 개정하고, **에픽 16 - 공개 job 경험**에 공통 여정 3개를 추가한다. 아래는 생성할 story의 범위 계획이며 최종 story 본문은 Part 2에서 작성한다.

| Story | 처리 | 사용자 가치/개정 범위 |
|---|---|---|
| US-RJ1 | 신규 | 업무 접수·진행·명시적 상태 확인을 구분하고 접수를 완료로 오인하지 않는다. 제출 재시도로 중복 효과가 생기지 않는 경험을 포함한다. |
| US-RJ2 | 신규 | 연결이 끊겨도 같은 작업의 진행/결과를 다시 확인하고 완료·실패·만료를 구분한다. 전달 중복/역순으로 완료 표시가 되돌아가지 않는다. |
| US-RJ3 | 신규 | 현재 권한 안에서 private 결과/DocModel/자산을 열람하고 다른 사용자의 job/내용은 노출되지 않는다. 결과 전달과 새 업무 요청의 경계를 반영한다. |
| US-S5 | 개정 | 이관된 요약/번역은 job 접수 후 결과를 수신하며 캐시 결과는 재생성 없이 빠르게 전달된다. 미전환 경로의 호환 범위를 표시한다. |
| US-A6 | 개정 | 즉시 계정 비활성화/세션 무효화, owner job/event/result 파기, 진행 중 작업의 private 데이터 재생성/전달 차단을 포함한다. |
| US-TN2 | 개정 | 익명 token 수신 해지의 접수/완료를 구분하고 durable 수락 후 발송 차단이 queue 대기로 풀리지 않음을 포함한다. |
| US-R2 / US-R4 / US-R5 | 개정 | 비동기 실패·저하의 명시적 표시, job 단계 관측, queue 장애 중 직접 health 판정을 각각 담당한다. |
| US-S1 / US-S2 / US-S3 | 인수/참조 정합 | 요약/번역/출처 열람의 기존 기능 인수와 US-S5/US-RJ1~3을 연결한다. |
| US-EV4 / US-EV7 / US-EV8 / US-NV7 / US-AG4 / US-AG5 | 영향 경로만 보강 | REM으로 이관되는 첨부/private read·결과·진행 인수만 공통 job story에 연결한다. 기존 agent 전체 lifecycle을 이번 job 계약으로 일괄 전환하지 않는다. |

공통 lifecycle 인수는 US-RJ story에 한 번 정의하고 domain story는 고유 인수와 연결만 가진다. 소유권/삭제/수신 해지의 고유 인수는 해당 domain story가 맡는다. 단일 사용자 story를 REM 서비스별 구현 작업 목록으로 나누지 않는다.

### RJ-AC coverage 계획

| 인수 | 관측 가능한 검증 초점 | 계획된 story |
|---|---|---|
| RJ-AC01 | 실제 접수 확인과 업무 완료/접수 실패 구분 | US-RJ1 |
| RJ-AC02 | 명시적 status 요청의 결과를 재귀 조회 없이 수신 | US-RJ1, US-RJ2 |
| RJ-AC03 | pending/completed/failed 및 domain outcome의 정확한 표시 | US-RJ1, US-S5, US-R2 |
| RJ-AC04 | 재연결, 중복/역순 event, 결과 만료의 일관된 사용자 상태 | US-RJ2 |
| RJ-AC05 | 접수부터 private 결과 전달까지 현재 caller 권한과 비노출 | US-RJ3 |
| RJ-AC06 | 재시도·재전달의 중복 효과 방지 및 다른 caller job 격리 | US-RJ1, US-RJ3 |
| RJ-AC07 | cache-backed job 결과 재사용과 source 무결성 | US-S5, US-S1, US-S2 |
| RJ-AC08 | 준비된 결과/자산의 인가된 same-origin 직접 전달 | US-RJ3, US-S3 |
| RJ-AC09 | owner job 데이터 파기와 진행 중 작업의 데이터 재생성 방지 | US-A6, US-EV8 |
| RJ-AC10 | 익명 token 해지 결과 권한과 즉시 발송 차단 | US-TN2 |
| RJ-AC11 | 선행 인가/rate-limit 및 즉시 비활성화/세션 무효화 | US-RJ1, US-A6 |
| RJ-AC12 | 장애/재시작/부분 배포의 복구 또는 명시적 실패, 직접 health 관측 | US-RJ2, US-R2, US-R4, US-R5 |

### Persona 및 인수 작성 기준

- P1/P2: 접수·결과·재연결·권한 만료의 의미를 이해하는 연구자 관점. 정당한 사용자의 실제 결과와 거부된 접근의 비노출을 각각 검증한다.
- OP: job 실패/queue outage/복구/health를 관측하는 관점. 세션이 무효화된 탈퇴 사용자에게 private 파기 진행 화면 접근을 새로 부여하지 않는다.
- 익명 token unsubscribe: P1/P2가 로그아웃 상태에서 받은 링크를 사용하는 상황이다. 해당 해지 결과에 한정된 권한을 명시한다.
- 각 story는 As/I want/so that과 Given/When/Then을 사용하고, FR/RJ-AC 및 관련 NFR/SEC/RES/QT trace를 기록한다.
- INVEST 검토: 준비된 작업/계정/결과를 Given으로 두어 개별 검증 가능하게 만들고, 사용자 가치와 결과를 명시한다. endpoint/DTO 필드/TTL/프로토콜 수치는 이 단계에서 정하지 않는다.
- Security Full의 owner 권한/만료/비노출/선행 제한과 Resiliency custom의 직접 health/명시적 실패/재연결 인수를 story에 반영한다. 나머지 기술 제약은 승인된 requirements와 후속 설계로 추적한다.
- PBT-01~10은 User Stories 실행 검증 N/A이며 Full 활성 상태는 유지한다. QT-12의 불변식과 example scenario를 Functional/NFR/Code/Build 단계에 연결한다.

### Part 2 - 생성 체크리스트 (RJS1 승인 후)

- [x] 본 계획과 승인된 요구사항을 다시 읽고 RJS1 답변/승인을 확인했다.
- [x] `inception/user-stories/personas.md`에 P1/P2의 job 경험과 OP의 job/health 관측 맥락을 개정했다.
- [x] `inception/user-stories/stories.md`에 에픽 16 및 US-RJ1~US-RJ3의 사용자 서술과 Given/When/Then을 작성했다.
- [x] US-S5, US-A6, US-TN2, US-R2/4/5의 고유 인수를 개정했다.
- [x] 배치표의 기존 요약/자산/agent story를 REM 이관 경로에 한정해 연결하고 응답 계약 충돌을 정리했다.
- [x] P1/P2/OP -> story map과 FR-52/NFR-R4/QT-12/C-13 및 RJ-AC01~12 -> story coverage를 갱신했다. 기존 온보딩/트렌드/웹/구독 story의 persona map 누락도 본문 actor에 맞게 연결했다.
- [x] INVEST, story ID 유일성, 중복/누락 인수, 권한/삭제/해지/health 및 활성 확장 규칙의 stage 적용성을 검토했다. 아래 검증 기록 참조.
- [x] story 총수/에픽 수/추적성 문구, Markdown 구조와 whitespace를 검증했다. 85 story, 17 epic, 3 persona, RJ-AC 12행; 중복 story ID 없음; `git diff --check` 통과.
- [x] story/persona 산출물과 상태/감사 기록을 갱신하고 RJS2 User Stories 완료 리뷰를 준비·기록했다.
- [x] 생성된 story/persona의 명시 승인을 받고 Workflow Planning으로 진행했다. 사용자 "RJS2: A" (2026-09-19).

## RJS1 - 공개 job Story Amendment Plan 승인

위 story 개정 접근법과 Part 2 실행 계획을 어떻게 진행할까?

A) **Approve Plan** - 기존 P1/P2/OP, 에픽 기반 구조와 Given/When/Then을 사용한다. 공통 job 여정 3개(US-RJ1~3)를 추가하고 배치표의 기존 story/persona/coverage를 개정하는 본 계획을 승인한다. (권장)

B) **Request Changes** - 위 접근법 비교와 배치표를 참고해 변경할 story 조직, 입도 또는 persona/인수 범위를 답변 태그 뒤에 기술한다. 수정 계획을 검토한 뒤 생성한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 story 접근법과 계획 변경을 기술)

[Answer]: A

RJS1=A는 story 접근법 및 Part 2 실행 계획의 명시 승인이다. 생성 후 story/persona 산출물은 별도 완료 리뷰를 거친다.

### Part 2 검증 기록 - 2026-09-19

- 신규: US-RJ1~3. 기존 인수/연결 개정: US-A6, US-R2/4/5, US-S1/2/3/5, US-NV7, US-EV4/7/8, US-AG4/5, US-TN2 (15개).
- 기존 82개 story ID를 유지하고 3개를 추가했다. 총 85개/17개 에픽이며 중복 ID가 없다. P1/P2/OP map에 모든 story가 연결되고 RJ-AC01~12가 본문 인수와 coverage 표에 추적된다.
- 승인된 queued 업무 read/status, 직접 결과 전달/health, owner 권한, 삭제/해지의 즉시 보호와 호환 전환을 문서 간 대조했다. REM 하위 작업과 기존 전체 agent lifecycle을 구분했다.
- Markdown heading/table/inline escaping을 검토했고 새 diagram은 없다. `git diff --check` 통과. 검증은 story 산출물의 정합성을 대상으로 한다.

| INVEST | 검토 결과 |
|---|---|
| Independent | US-RJ1은 허용된 요청, US-RJ2는 접수된 작업, US-RJ3은 준비된 결과/권한을 Given으로 두어 각각 독립 검증할 수 있다. |
| Negotiable | 사용자에게 관측되는 결과를 명시하고 endpoint/schema/transport/TTL 구현 선택은 후속 설계에 둔다. |
| Valuable | 중복 작업/완료 오판 방지, 재연결 후 연구 연속성, private 자료 보호의 사용자 가치를 분리했다. |
| Estimable | 신규 story별 접수/관측/전달 경계와 domain 연결 및 실패 시나리오가 식별돼 있다. |
| Small | 공통 여정 3개와 기존 domain story의 고유 인수로 나누어 전체 REM 구현을 한 story로 묶지 않았다. |
| Testable | Given/When/Then에서 접수 여부, terminal 상태, 비노출, 파기 후 대상 0건/비대상 불변 등 판정 가능한 결과를 명시했다. |

### User Stories 확장 준수 요약

Compliant는 이번 story/persona 산출물에 적용되는 인수의 반영 여부다. N/A인 기술 설정/실행 검증은 활성 요구사항을 유지한 채 해당 설계·구현 단계에 추적한다.

| Security 규칙 | 상태 | 근거 또는 N/A 사유 |
|---|---|---|
| SECURITY-01 | N/A | 저장소 암호화/TLS 설정 산출물이 없는 단계. SEC-1을 NFR/Infrastructure로 계승한다. |
| SECURITY-02 | N/A | 네트워크 intermediary logging 설정은 후속 인프라 설계 대상이다. SEC-2 유지. |
| SECURITY-03 | Compliant | US-R4의 구조화 correlation 및 민감정보 제외 인수. |
| SECURITY-04 | N/A | HTTP header/CSP 설정은 후속 설계 대상이다. same-origin 사용자 전달 인수는 US-RJ3에 포함했다. |
| SECURITY-05 | Compliant | US-RJ1 입력 거부, US-TN2 invalid/expired token 검증. |
| SECURITY-06 | N/A | service/store 권한 정책은 후속 설계 대상. persona는 임의 private 접근 권한을 부여하지 않는다. |
| SECURITY-07 | N/A | network binding/firewall을 생성하는 단계가 아니다. SEC-7/C-5 계승. |
| SECURITY-08 | Compliant | US-RJ3의 모든 경계 owner 검증/비노출 및 US-TN2의 한정된 public token 예외. |
| SECURITY-09 | Compliant | US-RJ1~3의 일반화된 오류와 내부 key 비노출. 배포 hardening 상세는 후속 설계다. |
| SECURITY-10 | N/A | 의존성/lock/SBOM을 생성하지 않는 단계. F06/SEC-10 후속 gate 유지. |
| SECURITY-11 | Compliant | US-RJ1의 접수 전 제한, 중복 제출·capacity 남용 인수. |
| SECURITY-12 | Compliant | US-A6 즉시 session 무효화 및 US-RJ3 만료/철회 후 실행·전달 차단. |
| SECURITY-13 | Compliant | US-S5 canonical source/cache, US-RJ1 멱등 효과, US-R4 감사 가능성. |
| SECURITY-14 | Compliant | US-R4의 권한 거부/장애 경보·추가 전용 감사, US-A6의 private 정보 제거 보존 정책. |
| SECURITY-15 | Compliant | US-RJ1~3 및 US-R2의 fail-closed, terminal failure, 접수 실패 구분. |

| Resiliency 규칙 | 상태 | 근거 또는 N/A 사유 |
|---|---|---|
| RESILIENCY-01 | N/A | service별 criticality/dependency 분류는 Application Design 대상이다. OP의 관측 가치는 명시했다. |
| RESILIENCY-02 | N/A | RTO/RPO 신규 선택 단계가 아니다. 승인된 RES-2를 후속 NFR에 계승한다. |
| RESILIENCY-03 | N/A | 변경 관리 프로세스를 설계하는 단계가 아니다. 기존 GitHub review/git-flow를 유지한다. |
| RESILIENCY-04 | Compliant | US-R2/US-RJ2의 partial deploy/rollback 중 job 무손실·중복 효과 방지 및 명시적 실패. |
| RESILIENCY-05 | Compliant | US-R4의 단계별 metrics/logs/service trace와 종단 완료 측정. |
| RESILIENCY-06 | Compliant | US-R5의 shallow/deep/synthetic 관측과 queue 독립 직접 응답. |
| RESILIENCY-07 | Compliant | US-R4의 queue 적체·장기 pending·disk/model saturation 신호. |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외. US-R5와 OP를 정합시켰다. |
| RESILIENCY-09 | Compliant replacement | horizontal autoscale N/A; US-RJ1의 capacity 제한과 US-R4의 saturation 관측으로 추적한다. |
| RESILIENCY-10 | Compliant | US-S5/US-R2/US-RJ2의 bounded 실패, queue/전달 장애와 업무 결과 구분. |
| RESILIENCY-11 | N/A | DR 전략을 선정하는 단계가 아니다. 기존 backup-and-restore 요구 계승. |
| RESILIENCY-12 | N/A | backup 설정/restore 실행은 후속 설계·검증 대상. 새 job state는 NFR-R4와 RES-2 적용 대상이다. |
| RESILIENCY-13 | Compliant | US-R2/US-RJ2가 복구 이후의 작업 재개/실패 및 결과 재확인 인수를 정의한다. runbook은 후속 단계다. |
| RESILIENCY-14 | Compliant | US-R2/US-RJ2/US-R5에 queue loss/crash/partial deploy/재연결 검증 시나리오를 정의했다. |
| RESILIENCY-15 | Compliant | US-R4의 기존 경보/COE 연계와 OP의 증거 기반 실패 판정. |

| PBT 규칙 | 상태 | N/A 사유와 후속 추적 |
|---|---|---|
| PBT-01 | N/A | User Stories 적용 stage 아님; QT-12를 Functional Design property 식별로 연결. |
| PBT-02 | N/A | DTO round-trip 테스트는 후속 구현/검증 대상. |
| PBT-03 | N/A | US-RJ3/US-A6의 owner·파기 불변식을 후속 property로 연결. |
| PBT-04 | N/A | US-RJ1/US-TN2의 재전달·멱등 효과를 후속 property로 연결. |
| PBT-05 | N/A | 상태·권한 reference model은 Functional/Code 단계 대상. |
| PBT-06 | N/A | US-RJ2의 crash/reconnect/order 상태 시퀀스를 후속 property로 연결. |
| PBT-07 | N/A | domain generator 구현은 Code 단계 대상. |
| PBT-08 | N/A | shrinking/seed 실행 검증은 Code/Build 단계 대상. |
| PBT-09 | N/A | service별 Hypothesis/fast-check 매핑은 NFR Requirements 대상. |
| PBT-10 | N/A | 생성된 Given/When/Then 예시와 property 병행은 후속 구현/검증 대상. |

현재 단계에 적용되는 확장 인수의 blocking finding은 없다. Security Full/Resiliency custom/PBT Full 활성 상태는 유지한다.

## RJS2 - 공개 job Story/Persona 산출물 승인

생성한 `inception/user-stories/stories.md`와 `inception/user-stories/personas.md` 개정안을 어떻게 진행할까?

A) **Approve & Continue** - story/persona 개정과 인수 coverage를 승인하고 Workflow Planning 개정으로 진행한다. (권장)

B) **Request Changes** - 답변 태그 뒤에 수정할 story/persona 또는 인수 기준을 기술한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 진행 방향을 기술)

[Answer]: A

**승인 기록**: 2026-09-19T06:10:19Z. 사용자 `RJS2: A`로 두 산출물과 인수 coverage를 승인하고 Workflow Planning 개정을 시작했다.
