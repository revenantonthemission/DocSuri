# 사용자 스토리 실행 평가 (User Stories Assessment)

> **현재 개정 평가**: 문서 하단의 `2026-09-19 REM 공개 job 계약 평가`를 참조한다. 상단은 초기 제품 평가 이력이다.

## 요청 분석
- **원 요청**: AI 기반 연구 지원 앱 구축(AI/ML 문헌 **디스커버리**로 범위 한정, 폰 우선 모바일 웹, 공개 프로덕션).
- **사용자 영향**: 직접 — 제품 전체가 사용자 대면.
- **복잡도**: 복잡(Complex)(멀티 페르소나, 공개 계정, RAG 검색, 엄격 근거화, 복원력/보안 베이스라인, AI 특화 인시던트 처리).
- **이해관계자**: 주 페르소나 P1(현역 AI/ML 연구자 — 박지훈), 부 페르소나 P2(대학원생), 그리고 비용/인시던트 처리를 위한 운영자(operator) 관심사.

## 충족된 평가 기준
- [x] **High Priority — 신규 사용자 기능**: 완전히 사용자 대면인 신규 디스커버리 제품.
- [x] **High Priority — 멀티 페르소나 시스템**: P1 + P2(및 복원력/비용을 위한 운영자 관심사).
- [x] **High Priority — 복잡한 비즈니스 로직**: 엄격 근거화/기권, 검색 랭킹, 저하 모드, AI 인시던트 분류.
- [x] **High Priority — 고객 대면**: 공개 셀프 가입 웹 앱.
- [x] **이점**: QT-1..4 + PBT로 이어지는 테스트 가능 인수 기준; 팀 공동 이해; FR-1..11 / NFR / SEC / RES를 데모 가능한 슬라이스로 깔끔히 매핑.

## 결정
**사용자 스토리 실행**: 예
**근거**: 모든 High-Priority 지표가 해당. 요구사항에는 실질적 행위 뉘앙스(날조-대-기권, 우아한 저하, AI 인시던트 클래스)가 있어 NFR에 암묵적으로 남기기보다 명시적·테스트 가능 사용자 스토리로 풀어내는 편이 유리.

## 기대 산출
- 페르소나에 근거한, INVEST를 충족하는 스토리(Given/When/Then 인수 기준 포함).
- FR/NFR/SEC/RES 요구사항 → 스토리 → 테스트로의 직접 추적성.
- 매직 모먼트 데모를 위한 단일 종단 "히어로" 스토리.

---

## 2026-09-19 REM 공개 job 계약 평가

### 요청 분석

- **입력**: 승인된 FR-52/NFR-R4/QT-12/C-13 및 `verification-remediation-2026-09-18.md` §10의 RJ-AC01~12. 사용자 "Approve & continue"를 RJR1=A로 기록했다.
- **사용자 영향**: 직접. REM으로 이관되는 업무 read/status가 공개 job 계약으로 바뀌며 사용자는 접수, 대기, 완료, 실패, 재연결 후 결과를 구분한다.
- **복잡도**: Complex. 문서/자산 열람, 요약/번역, 계정 파기, 익명 token 수신 해지와 운영 관측이 서로 다른 권한·수명주기를 갖는다.
- **이해관계자**: P1/P2 연구자와 OP 운영자. 로그인하지 않은 다이제스트 수신자는 P1/P2의 이용 상황으로 다루며 별도 페르소나를 추가할 근거는 없다.

### 충족 기준

- [x] **High Priority - User Experience Changes**: 기존 read/결과 응답과 pending/poll 경험을 job 접수·event 결과 수신으로 개정한다.
- [x] **High Priority - Customer-Facing APIs**: frontend가 versioned 공개 job 계약을 소비한다.
- [x] **High Priority - Multi-Persona / Cross-Team**: P1/P2/OP 및 기존 domain owner와 REM runtime owner의 인수 기대를 연결해야 한다.
- [x] **High Priority - Multiple Business Scenarios**: 권한 만료/철회, 재연결, 중복 전달, 삭제 중 작업, queue 장애와 token unsubscribe의 조합을 검증해야 한다.
- [x] **Concrete Benefit**: RJ-AC01~12를 사용자에게 관측 가능한 Given/When/Then으로 풀고 테스트 누락·중복·기존 story와의 충돌을 줄인다.

### 결정과 기대 산출

**Execute User Stories: Yes.** 공개 사용자 흐름을 변경하므로 이전 workflow의 User Stories skip 판단을 대체한다.

- 기존 P1/P2/OP, As/I want/so that, Given/When/Then과 INVEST 방법을 재사용한다.
- 공통 job 경험은 작고 독립 검증 가능한 story로 묶고, domain별 고유 인수는 기존 story에 개정한다.
- `stories.md`와 `personas.md`, persona/story map 및 FR/RJ-AC coverage를 함께 갱신한다.
- Security Full, Resiliency custom, PBT Full의 승인된 요구를 story 인수와 후속 테스트 추적으로 연결한다. 서비스 구현/배포 작업 자체를 사용자 story로 치환하지 않는다.
- **계획 승인 게이트**: `story-generation-plan.md`의 RJS1. 사용자 story 접근법 승인 후 Part 2를 실행한다.
