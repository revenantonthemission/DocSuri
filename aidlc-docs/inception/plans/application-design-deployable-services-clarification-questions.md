# Deployable-Service Application Design 명확화 질문

**단계**: INCEPTION -> Application Design 답변 분석
**기준**: `application-design-plan.md`의 DSRQ1=A, DSRQ2=A, DSRQ3=A, DSRQ4=C, DSRQ5=A, DSRQ6=A, DSRQ7=A
**상태**: DSRQF1=A, DSRQF2=A 확정 및 선행 RJR1/RJS2/WPR2 승인 완료 (2026-09-19). 설계 산출물은 `application-design-plan.md` DAD1 리뷰 대상이다.

## 명확화 배경

- DSRQ4=C는 사용자 업무 read/status까지 job resource와 queue/event로 처리한다는 선택이다. 외부 API 변경 범위와 완료 결과 전달 경로를 정해야 구현 가능한 계약이 된다.
- DSRQ6=A의 gateway 경유 점진 전환은 외부 응답이 기존 DTO인지 새 job 계약인지까지 정하지 않는다. 공개 job 계약은 기존 workflow의 User Stories skip 근거에 영향을 준다.
- F07은 브라우저가 인증된 same-origin URL에서 자산 bytes를 받아야 한다. DSRQ7=A는 REM-1 evidence/readiness의 read-only 제공을 선택했다. status 조회가 job을 생성한다면 그 조회의 완료를 관측할 별도 전달 경계가 필요하다.

## DSRQF1 - 외부 API 및 사용자 흐름 변경 범위

DSRQ4=C의 job resource를 어느 경계까지 노출할까?

A) **REM으로 이관되는 F01~F13 관련 사용자 업무 경로에 공개 job 계약을 도입한다.** frontend가 job 접수, 대기, 완료, 실패와 결과 수신을 처리하며 DSRQ6=A에 따라 versioned route별로 전환한다. 이관 대상 밖의 기존 제품 API까지 일괄 job화하지 않는다. 영향을 받는 요구사항과 사용자 스토리, workflow를 제한적으로 개정한 뒤 Application Design을 이어간다. (C의 사용자-facing 비동기 의도를 유지하는 권장안)

B) 외부 REST/DTO와 사용자 흐름을 유지하고 queue/job 계약은 gateway와 REM 사이에만 둔다. gateway는 정해진 응답 예산 안에서 결과를 변환하고, 기존에 허용된 경로에서만 pending을 반환한다. 이 선택은 DSRQ4의 사용자-facing C를 **내부 비동기 방식인 X로 수정**한다. timeout과 compatibility 인수를 재검토한다.

C) DSRQ4를 원래 A로 정정한다. bounded read/status/stream은 동기 API, generation/purge/audit/repair 등 장기 작업은 durable async operation으로 설계한다. 이 경우 DSRQF2에는 `X: DSRQF1=C에 따른 기존 DSRQ4=A 경계 적용`을 기록한다.

X) 기타 (아래 `[Answer]:` 뒤에 job 계약을 노출할 경로와 외부 client 변경 범위를 기술)

[Answer]: A

## DSRQF2 - 비동기 status와 결과 전달 및 운영 경계

DSRQF1에서 A 또는 B를 선택한 경우, 업무 read/status의 비동기 실행과 결과 전달/운영 점검을 어떻게 구분할까?

A) **업무 read와 명시적 status 조회도 job으로 처리한다.** 완료 결과는 해당 호출자를 인가한 event/subscription 경로로 전달하며, 완료된 자산 bytes는 별도 인증된 same-origin 전달 경로로 제공한다. job 접수 확인, event 구독/재연결, 완료 결과 전달은 새 업무 job을 만들지 않는다. health/readiness와 REM-1의 read-only evidence 조회도 bounded 직접 관측 경로로 두어 queue 장애 중에도 상태를 판정한다. (C의 업무 read/status 비동기화를 유지하는 권장안)

B) 업무 처리와 데이터 read는 job으로 실행하되, job status와 완료 결과는 권한 검증된 read projection에서 직접 조회한다. health/readiness와 REM-1 evidence도 직접 관측한다. status polling을 허용하는 이 선택은 DSRQ4=C의 **status까지 비동기** 범위를 수정하는 명시적 예외다.

X) 기타 (아래 `[Answer]:` 뒤에 완료 결과 전달 방법, status 조회의 재귀 방지, queue 장애 중 health/readiness 관측 방법을 기술. DSRQF1=C이면 위 안내의 N/A 사유를 기록)

[Answer]: A

## 답변 해석과 후속 순서

- 권장 조합은 DSRQF1=A, DSRQF2=A다. 이 조합은 선택한 DSRQ4=C를 구체화하고, frontend에 보이는 job 계약 변경을 명시한다.
- DSRQF1=A이면 영향 경로에 한정한 Requirements/User Stories/Workflow 개정이 선행된다. 기존 성능 목표, F05 pending/poll 인수와 F07 same-origin 전달을 어떻게 만족하거나 개정할지 그 단계에서 명시한다.
- DSRQF1=B이면 외부 계약 보존과 응답 예산을 검증한 뒤 선행 단계 개정 필요성을 판정한다. DSRQF1=C이면 기존 hybrid 계약 기준으로 답변 정합성을 다시 검증한다.
- 모든 선택에서 job ID만으로 접근을 허용하지 않는다. DSRQ5=A의 service identity와 principal 검증은 접수, 실행, 상태/결과 전달의 권한 경계에 반영한다. queue 대기가 credential 만료 또는 owner 권한 변경을 우회하지 않게 상세 설계한다.
- durable operation/outbox, bounded concurrency/backpressure, F01~F13 데이터 인수와 별도 corpus rebuild 승인 경계가 계속 적용된다. 전체 제품을 job API로 전환하거나 성능 목표를 완화하는 결정은 별도로 명시해야 한다.

## 진행 체크리스트

- [x] 원 답변과 명확화가 필요한 두 경계를 기록했다.
- [x] 질문 2개, 빈 `[Answer]:` 2개, 마지막 기타 선택지 2개와 Markdown 구조를 검증했다. tracked diff 및 신규 질문 파일의 whitespace check가 통과했다.
- [x] DSRQF1~DSRQF2 답변을 수집한다. 두 답변 모두 A로 확정했다.
- [x] 답변 간 모순 및 Requirements/User Stories/Workflow 영향을 검증한다. 공개 job 계약과 직접 전달/관측 예외가 정합적이며 사용자 흐름 변경에 한정한 선행 단계 개정이 필요하다.
- [x] 필요한 선행 단계 개정과 승인을 완료했다. RJR1=A, RJS2=A, WPR2=A (2026-09-19).
- [x] 해소된 경계를 `application-design-plan.md`와 상태 기록에 반영한다.

## 답변 분석 - 2026-09-19

- 사용자 원문: `DSRQF1: A, DSRQF2: A`
- DSRQ4=C를 유지한다. F01~F13 때문에 REM으로 이관되는 사용자 업무 호출은 공개 job 계약을 사용하고 frontend는 접수/대기/완료/실패를 표시한다.
- 업무 read와 명시적 status 조회는 queued job이다. 접수 확인, 인가된 event/subscription 및 재연결, 완료 결과/asset bytes 전달, health/readiness, REM-1 read-only evidence는 새 업무 job을 만들지 않는 직접 경로다.
- DSRQ5=A의 caller authorization과 DSRQ6=A의 gateway 경유 versioned route 전환을 함께 적용한다. 이 결정은 전체 제품 API 전환이나 기존 보안/성능 인수의 완화를 뜻하지 않는다.
- 남은 답변 모호성은 없다. 다음 순서는 제한적 Requirements 개정/승인 -> User Stories 개정/승인 -> Workflow Planning 개정/승인 -> Application Design 재개다.
