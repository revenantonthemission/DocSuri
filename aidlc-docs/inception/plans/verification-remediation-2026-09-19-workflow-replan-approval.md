# F01-F13 Deployable-Service Workflow Replan Approval

> **현재 승인 질문**: 하단 WPR2. WPR1은 네 deployable service 선택 당시의 승인 이력이다.

**Stage**: INCEPTION -> Workflow Planning review gate
**Decision source**: UQRF1=B
**Plan under review**: `verification-remediation-2026-09-18-workflow-plan.md`, section `2026-09-19 UQRF1=B Deployable-Service Replan Amendment`

## Review Summary

- REM-1 through REM-4 become four long-lived independently deployable remediation services.
- Application Design is re-executed comprehensively before Units Generation restarts.
- Each service executes Functional Design, NFR Requirements, NFR Design, Infrastructure Design, and Code Generation.
- Integrated Build and Test covers multi-process contracts, partial deployment, failure isolation, rollback, and safe targeted live repair.
- Full corpus rebuild, bulk reparse/reembed, and live alias cutover remain behind a separate explicit approval gate.
- Security Full and PBT Full remain enabled. Resiliency uses the approved single-Mac custom profile.

## WPR1 - Workflow Replan Approval

How should the revised workflow proceed?

A) **Proceed with the recommended workflow.** Approve the deployable-service replan and continue to comprehensive Application Design redesign. (Recommended)

B) Modify the recommended stages or their depth. Describe the exact changes after the answer tag.

C) Add a stage currently marked skipped or reused. Identify the stage and desired depth after the answer tag.

D) Remove a recommended stage. Identify the stage and rationale after the answer tag.

X) Other. Describe the desired workflow after the answer tag.

[Answer]: A

## Approval Gate

- [x] Revised workflow, service sequence, risk gates, visualization, and extension compliance documented.
- [x] Mermaid rendering, Markdown structure, and whitespace validation passed.
- [x] WPR1 answer received and validated.
- [x] Workflow replan approved and Application Design redesign authorized.

Workflow replan approved on 2026-09-19. Comprehensive Application Design redesign is authorized; Units Generation remains stopped until that design is approved.

---

## Public Job Workflow Amendment Review - 2026-09-19

**입력**: Requirements RJR1=A, User Stories RJS2=A, DSRQ4=C 및 DSRQF1/2=A
**리뷰 대상**: `verification-remediation-2026-09-18-workflow-plan.md`의 `2026-09-19 Public Job Workflow Amendment - WPR2`

- 네 장기 deployable service와 기존 domain authority를 유지하고 공개 job/frontend 흐름을 service별 vertical slice에 포함한다.
- Application Design의 해소된 결정을 재사용해 5개 산출물을 생성한 뒤 Units Generation을 재시작한다.
- 각 service의 Functional/NFR Requirements/NFR Design/Infrastructure/Code loop와 통합 Build and Test를 실행한다.
- REM-1 foundation -> REM-2 private job/result/UI -> REM-3 lifecycle/identity -> REM-4 corpus/search의 merge/integration 순서와 승인된 독립 구현 병렬성을 따른다.
- G0~G5에 F01~F13 및 RJ-AC01~12, contract/consumer/owner/browser/복구/안전한 전환 인수를 연결한다.
- full corpus rebuild/bulk reparse/reembed/live alias cutover는 별도 명시 승인 경계다.

## WPR2 - Public Job Workflow Approval

공개 job 범위를 반영한 실행 계획을 어떻게 진행할까?

A) **Approve & Continue** - WPR2 계획을 승인하고 Application Design 산출물 생성을 재개한다. (권장)

B) **Request Changes** - stage의 깊이, package 순서 또는 checkpoint의 변경 내용을 답변 태그 뒤에 기술한다.

C) 재사용하는 단계의 재실행 또는 추가 단계를 요청한다. 대상과 이유를 기술한다.

D) 권장 실행 stage의 제외를 요청한다. 대상과 이유를 기술한다.

X) 기타 (아래 `[Answer]:` 뒤에 원하는 실행 계획을 기술)

[Answer]: A

### WPR2 승인 기록

- [x] 공개 job workflow와 Mermaid/인수 coverage/질문/whitespace 검증을 완료했다.
- [x] WPR2 답변을 수집하고 승인된 scope/요구사항과 정합성을 검증했다.
- [x] Workflow 개정 승인을 기록하고 Application Design을 재개했다. 사용자 "WPR2: A" (2026-09-19).
