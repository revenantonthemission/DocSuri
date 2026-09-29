# unit-of-work-story-map.md — 스토리 → 유닛 매핑

> **현재 매핑**: 하단 `2026-09-19 Current Story and Remediation Map`의 85개 개별 story 행을 참조한다. 상단의 45개 core 표/범위 주석은 당시 이력이다. 현재 map은 RJS2/DAD1 및 UGP1=A를 반영한다.

**단계**: INCEPTION → Units Generation · **일자**: 2026-06-15
**근거**: `stories.md`(핵심 45 + US-NV1~9[U12] + US-EV1~9[U11] + US-AG1~6[U13] 등), `unit-of-work.md`(U1~U16 — 2026-08-03 재구성으로 U10·U13 등재).
**2026-08-03 유닛 재구성 노트**: US-AG1~6 Owner=**U13**(Agent Chat FE). 구 `research` 모듈의 U11 흡수는 스토리 소유 **무변**(US-EV Owner=U11 유지 — 세션 셸은 U11 내부 이동). U10 관련 UI 기여 표기(US-A5/A6 등)는 유효. 각 스토리에 **주 소유 유닛(Owner)** + 기여 유닛. (구 통합 U11 연구 에이전트 스토리는 2유닛 분리로 제거 후 **에픽 9 US-NV(U12 novelty)·에픽 10 US-EV(U11 evidence)로 재생성 완료** — 2026-06-29; 아래 U11/U12 묶음 참조. 정정 2026-06-30, `aidlc-suite-review` PR #280.)

---

## 매핑 (45개 전수)

| 스토리 | Owner | 기여 유닛 |
|---|---|---|
| **US-H1** 히어로(가입→질의→근거화 결과) | U5 | U2(백킹 검색), U3(가입), U1(Corpus 인덱스) |
| **US-D1** 자연어 질의 입력 | U2 | U5(검색 화면) |
| **US-D2** 시맨틱 검색 | U2 | U1(공유 Corpus 인덱스) |
| **US-D3** 상위 N 랭킹 | U2 | — |
| **US-D4** 폰 결과 카드 | U2(조립) | U5(카드) |
| **US-D5** 엄격 근거화 | U6(근거화 후크) | U2(어댑터), U1(DocModel Block anchor) |
| **US-D6** 기권 | U2(어댑터) | U6(후크) |
| **US-D7** 빈/실패/저하 UX | U5(StateView) | U2 |
| **US-A1** 공개 가입 | U3 | U5(계정 화면), U6(레이트리밋) |
| **US-A2** 로그인/세션 | U3 | U5, U6(게이트웨이) |
| **US-A3** 비밀번호 재설정 | U3 | U5(재설정 화면), U6(레이트리밋), 이메일=Resend |
| **US-A4** 소셜 로그인(Google OIDC) | U3 | U5(소셜 버튼·콜백 UI), U6(게이트웨이), 외부 Google OIDC |
| **US-A5** 비번/이메일 변경 | U3 | U5/U10(설정 UI), 이메일=Resend |
| **US-A6** 계정 삭제(소프트+유예 캐스케이드) | U3 | U4·U2(owner-scoped 데이터 **이벤트 구독·파기**), U5/U10(UI) |
| **US-A7** 인증 에러 표면화·입력 견고화 | U3 | U5(에러 표면화·재발송 UX) |
| **US-L1** 검색 저장 | U4 | U5 |
| **US-L2** 라이브러리 | U4 | U5 |
| **US-L3** 검색 이력 | U4 | U2(SearchExecuted 생산) |
| **US-I1** 멀티소스 Corpus & DocModel 인덱싱 | U1 | — |
| **US-I2** source별 스케줄 갱신 | U1 | U6(갱신 실패 경보) |
| **US-I3** 복원력 인제스천 | U1 | U6(관측) |
| **US-R1** 근거화 보장+할루시네이션 탐지 | U6 | U2 |
| **US-R2** 우아한 저하+반쪽짜리 탐지 | U6 | U2(저하 폴백) |
| **US-R3** 비용 상한+비용 폭발 탐지 | U6 | — |
| **US-R4** 관측성+AI 인시던트 경보 | U6 | (전 유닛 신호원) |
| **US-R5** 헬스 체크 | U6 | — |
| **US-S1** AI 구조화 요약 | U7 | U1(전문 원본), U2/U5(결과 카드) |
| **US-S2** 한국어 번역 | U7 | U1(초록 원본), U5(표시) |
| **US-S3** 출처 보기 + 기권 | U7 | U6(근거화 후크), U5(하이라이트 UI) |
| **US-S4** 요약/번역 개인화 | U7 | U5(수준/뷰 전환 UI) |
| **US-S5** 온디맨드 즉시/스트리밍 | U7 | U5(점진 렌더) |
| **US-S6** 요약 비용 게이트 + 근거화 운영 | U6 | U7(요약 경로), (관측 신호원) |
| **US-CG1** 논문 상세보기에서 각주 트리 열기 | U8 | U5(상세보기 UI), U6(게이트웨이) |
| **US-CG2** 제한된 깊이와 노드 메타데이터 | U8 | — |
| **US-CG3** 인용 근거화와 unresolved 분리 | U8 | U6(관측/인시던트 신호) |
| **US-CG4** 인용 노드 라이브러리 저장 | U8 | U4(저장 계약), U3(인가) |
| **US-CG5** 인용 API 실패/쿼터 저하 | U8 | U6(레이트리밋/관측) |
| **US-CG6** 인용 그래프 운영 관측성 | U6 | U8(관측 신호원) |
| **US-P1** 의미 있는 행동 이벤트 기록 | U9 | U2/U4/U7/U5(성공 경로 신호원), U6(저하 관측) |
| **US-P2** 라이브러리 저장/해제와 출처 앵커 신호 | U9 | U4(저장/해제), U7/U5(출처 앵커) |
| **US-P3** 사용자 관심 프로필 집계 | U9 | — |
| **US-P4** 검색 결과 소폭 개인화 | U9 | U2(랭킹 적용), U5(표시/끄기 진입점) |
| **US-P5** 요약/번역 기본값 개인화 | U9 | U7(기본값 적용), U5(옵션 UI) |
| **US-P6** 개인화 제어권 | U9 | U5(설정 UI), U3(사용자/인가) |
| **US-P7** 개인화 운영 관측성과 저하 | U6 | U9(저하/집계 신호원) |

## 유닛별 스토리 묶음
- **U1 Ingestion** — US-I1, US-I2, US-I3 (+US-H1/US-D2 Corpus 인덱스 백킹)
- **U2 Discovery** — US-D1, US-D2, US-D3, US-D4, US-D6 (+US-D5/US-D7/US-R1/R2 기여, US-H1 백킹, US-L3 생산자)
- **U3 Accounts** — US-A1..A7 (+US-H1 가입); 프로덕션화 US-A3~A7(재설정·소셜 OIDC·비번/이메일 변경·삭제·입력 견고화) 추가. **자가관리 설정 UI = U10 마이페이지 소유, U3 = 백엔드 엔드포인트·도메인 규칙 소유**(경계 Q2=A).
- **U4 Library** — US-L1, US-L2, US-L3
- **U5 Frontend** — US-H1(주), US-D7(주) (+US-D1/D4/A1/A2/L1/L2/L3 UI 기여)
- **U6 Reliability/Ops** — US-D5(주), US-R1, US-R2, US-R3, US-R4, US-R5, US-S6 (+US-A1 레이트리밋, US-I2/I3 관측)
- **U7 Summarization** — US-S1, US-S2, US-S3, US-S4, US-S5 (+US-S6 요약 경로 기여)
- **U8 Citation Graph** — US-CG1, US-CG2, US-CG3, US-CG4, US-CG5 (+US-CG6 관측 신호원)
- **U9 Personalization** — US-P1, US-P2, US-P3, US-P4, US-P5, US-P6 (+US-P7 관측 신호원)
- **U11 Evidence Agent** — US-EV1~9 (에픽 10; 문헌탐색·근거형성. requirements 초안 `[U4]` 오기 → U11 정정 2026-06-30)
- **U12 Novelty Agent** — US-NV1~9 (에픽 9; 차별화 novelty·별도 인셉션 사이클로 빌드 `construction/novelty-agent/`. US-NV9=운영 관측성 페르소나 OP)

## 전수 할당 검증
- 스토리 **45개** = US-H1 + US-D1..D7(7) + **US-A1..A7(7)** + US-L1..L3(3) + US-I1..I3(3) + US-R1..R5(5) + **US-S1..S6(6)** + **US-CG1..CG6(6)** + **US-P1..P7(7)** → **전부 Owner 배정 완료(미할당 0)**.
- 횡단 스토리(US-D5 근거화)는 Owner=U6(단일 권위 후크), 기여=U2(어댑터) — Application Design 단일-소유자 규칙과 일치.
- US-H1(히어로)은 통합 슬라이스 — Owner=U5(프런트 표면), 다수 유닛 백킹(US-D*/US-A1으로 실현).
- **U7 추가(2026-06-18)**: US-S1..S5 Owner=U7(요약/번역 신규 책임), US-S6은 비용게이트·근거화 운영이라 Owner=U6(단일 권위) 기여=U7 — 단일-소유자 규칙 일치. U7은 U1(전문)·U6(근거화/비용)에 의존하나 코드 의존 그래프는 비순환 유지(`unit-of-work-dependency.md` §비순환 검증).
- **U8 추가(2026-06-19)**: US-CG1..CG5 Owner=U8(각주 트리 신규 책임), US-CG6은 운영 관측성이라 Owner=U6 기여=U8 — 단일-소유자 규칙 일치. U8은 U3/U6 인증 경로와 U4 저장 계약에 의존하나 역호출이 없어 코드 의존 그래프는 비순환 유지.
- **U9 추가(2026-06-23)**: US-P1..P6 Owner=U9(행동 이벤트/프로필/제어 신규 책임), US-P7은 운영 관측성이라 Owner=U6 기여=U9 — 단일-소유자 규칙 일치. U9는 U3/U6 인증·관측 경로에 의존하고 U2/U4/U7/U5는 U9를 비차단 호출하나, U9 역호출이 없어 코드 의존 그래프는 비순환 유지.
- **연구 에이전트(2026-06-28 재구성 → 2026-06-29 재생성 완료)**: 구 통합 U11(US-RA1~8)은 폐기되고 **U11(문헌탐색·근거형성)·U12(novelty/연구아이디어) 2유닛으로 분리**(차터 §4). 스토리·Owner 재생성 완료 — **에픽 10 US-EV1~9 Owner=U11**, **에픽 9 US-NV1~9 Owner=U12**(운영 관측성 US-NV9는 페르소나 OP). 의존: U11→U2/U7/U6/`shared`, U12→U11(`EvidenceFormationPort`)·U2 `full`·외부탐색 — D5 포트 역전으로 비순환 유지.
- **U3 확장 — 계정 프로덕션화(2026-06-24)**: US-A3~A7 Owner=**U3**(재설정·소셜 OIDC·비번/이메일 변경·삭제·입력 견고화 — 신규 에픽 아님, 에픽 2 확장). **경계(Q2=A)**: U10 마이페이지(타 팀원)=프로필/설정 **UI만**, U3=백엔드 `/auth/*` 엔드포인트·도메인 규칙 소유. **신규 의존**: U3→외부 Google OIDC(콜백·토큰 교환). **삭제 캐스케이드**: U4/U2는 이미 U3 인증에 의존하므로 U3가 이들을 **직접 호출하면 순환** — 따라서 캐스케이드는 **이벤트 구동**(U3가 `AccountDeleted` 발행 → U4/U2가 각자 owner-scoped 데이터 구독·파기)으로 의존성 역전(U7↔U6 `shared/ports` 패턴 동일) → **코드 의존 그래프 비순환 유지**. (분리될 연구 에이전트 유닛도 동일 이벤트 구독 패턴으로 편입 예정.) 이벤트 계약·유예 잡 메커니즘 = Construction(Functional/Infra Design).
- **U1 확장 — Corpus 완성형(2026-06-26)**: US-I1~I3 Owner=**U1** 유지. 멀티소스 수집(arXiv/Semantic Scholar/OpenAlex), GROBID, eager DocModel, DocModel Block 청킹/임베딩/index generation, source watermark, retry/DLQ는 모두 write-side Corpus 파이프라인 책임이므로 신규 유닛을 만들지 않는다. U2/U7은 Corpus/DocModel capability read 소비자이며 코드 의존 그래프 비순환 유지.

---

## 2026-09-19 Current Story and Remediation Map

**입력**: RJS2=A의 `../user-stories/stories.md`, DAD1=A 설계, UGP1=A unit plan.
**상태**: 생성·검증 및 UGR1=A 승인 완료 (2026-09-19). 승인 기록은 `../plans/unit-of-work-plan.md`다.

- **Product owner**는 story의 사용자 가치/인수 책임이며 실제 코드/data의 단독 소유를 뜻하지 않는다. canonical business authority/ordinary writer는 DAD1의 배치를 따른다.
- **REM primary**는 이번 18개 신규/개정 story의 delivery 책임이다. `—`인 67개 story도 product owner가 있으며, 관련 F01~F13 회귀 검증의 대상에서 제외된다는 뜻은 아니다.
- contributor는 필수 협업 경계다. 모든 REM의 공통 REM-1/shared 기반은 unit dependency 모델을 따르며 각 행에서 반복하지 않는다.

### 전체 current story map

| Story ID | 현재 story | Product owner | REM primary | 필수 contributor / 연결 |
|---|---|---|---|---|
| US-H1 | 첫 검색 매직 모먼트 | U5 | — | U2 검색, U3 가입, U1 corpus |
| US-D1 | 자연어 질의 입력 | U2 | — | U5 입력 화면 |
| US-D2 | 공유 AI/ML Corpus 인덱스에 대한 시맨틱 검색 | U2 | — | U1 corpus |
| US-D3 | 관련도순 상위 N건 | U2 | — | U5 표시 |
| US-D4 | 폰 최적화 결과 카드 | U2 | — | U5 카드/UI |
| US-D5 | 엄격히 근거화된 결과 | U6 | — | U2 adapter, U1 source/anchor |
| US-D6 | 날조 대신 기권 | U2 | — | U6 grounding |
| US-D7 | 빈/실패/저하 UX | U5 | — | U2 outcome |
| US-A1 | 공개 셀프 가입 | U3 | — | U5 UI, U6 rate-limit |
| US-A2 | 로그인, 로그아웃, 세션 | U3 | — | U5 UI, U6 gateway |
| US-A3 | 비밀번호 재설정(분실 복구) | U3 | — | U5 UI, U6 제한, 기존 email 경로 |
| US-A4 | 소셜 로그인(Google OIDC) | U3 | — | U5 callback/UI, U6 gateway |
| US-A5 | 비밀번호·이메일 변경(자가 관리) | U3 | — | U5/U10 설정 UI |
| US-A6 | 계정 삭제(탈퇴) | U3 | REM-3 | REM-2 및 모든 owner store, U5/U10 |
| US-A7 | 인증 실패의 명확한 표면화 & 입력 견고화 | U3 | — | U5 오류/재발송 UI |
| US-L1 | 검색 저장 & 재실행 | U4 | — | U5 UI, U2 검색 계약 |
| US-L2 | 라이브러리 저장 | U4 | — | U5 UI |
| US-L3 | 검색 이력 | U4 | — | U2 SearchExecuted 생산 |
| US-I1 | 멀티소스 Corpus & DocModel 인덱싱 파이프라인 | U1 | — | 원 source/저장 capability |
| US-I2 | 최신성 스케줄 갱신 | U1 | — | U6 갱신 실패 관측 |
| US-I3 | 복원력 있는 인제스천 | U1 | — | U6 관측/복구 |
| US-R1 | 근거화 보장 + 할루시네이션 탐지 | U6 | — | U2 |
| US-R2 | 우아한 저하 + 반쪽짜리 결과 탐지 | U6 | REM-4 | REM-2/3 job 실패·복구, U2/U5 저하 |
| US-R3 | 비용 상한 서킷 브레이커 + 비용 폭발 탐지 | U6 | — | 각 비용/용량 신호원 |
| US-R4 | 관측성 & AI 인시던트 경보 | U6 | REM-1 | REM-2/3/4 local instrumentation/경보/trace |
| US-R5 | 헬스 체크 | U6 | REM-1 | REM-2/3/4 실제 role별 health/readiness |
| US-S1 | AI 구조화 요약 | U7 | REM-2 | U1 canonical source, U2/U5 표시 |
| US-S2 | 한국어 번역 (초록 / 전문) | U7 | REM-2 | U1 canonical source, U5 |
| US-S3 | 출처 보기 & 근거 부족 시 기권 | U7 | REM-2 | U1 DocModel/asset, U5, U3 권한, U6 관측 |
| US-S4 | 요약/번역 개인화 (수준·용어 선호) | U7 | — | U5 수준/용어 UI, U9 기본값 |
| US-S5 | 온디맨드 job 진행과 요약/번역 결과 수신 | U7 | REM-2 | U5/U6 cache-backed job/진행/실패 |
| US-S6 | 요약 비용 게이트 + 근거화 운영 | U6 | — | U7 domain validator/관측 신호 |
| US-CG1 | 논문 상세보기에서 각주 트리 열기 | U8 | — | U5 UI, U6 gateway |
| US-CG2 | 제한된 깊이와 노드 메타데이터 | U8 | — | U5 표시 |
| US-CG3 | 인용 근거화와 unresolved 분리 | U8 | — | U6 관측 |
| US-CG4 | 인용 노드 라이브러리 저장 | U8 | — | U4 저장, U3 인가 |
| US-CG5 | 인용 API 실패/쿼터 저하 | U8 | — | U6 제한/관측 |
| US-CG6 | 인용 그래프 운영 관측성 | U6 | — | U8 신호원 |
| US-P1 | 의미 있는 행동 이벤트 기록 | U9 | — | U2/U4/U7/U5 신호원, U6 관측 |
| US-P2 | 라이브러리 저장/해제와 출처 앵커 신호 | U9 | — | U4, U7/U5 |
| US-P3 | 사용자 관심 프로필 집계 | U9 | — | 기존 profile 저장소 |
| US-P4 | 검색 결과 소폭 개인화 | U9 | — | U2 랭킹, U5 UI |
| US-P5 | 요약/번역 기본값 개인화 | U9 | — | U7 적용, U5 UI |
| US-P6 | 개인화 제어권 | U9 | — | U5 설정, U3 인가 |
| US-P7 | 개인화 운영 관측성과 저하 | U6 | — | U9 신호원 |
| US-NV1 | 자연어 연구 의도에서 novelty job 시작 | U12 | — | U11 evidence, U2 검색, U13 UI |
| US-NV2 | 업로드 원고에서 novelty job 시작 | U12 | — | U1/user_docmodel, U11, U13 |
| US-NV3 | 유사 연구 표 정리 | U12 | — | U11 evidence, U2 검색 |
| US-NV4 | GitHub와 데이터셋 근거 보강 | U12 | — | 외부 탐색 port, U6 관측 |
| US-NV5 | 원고 위험 신호 표시 | U12 | — | U1 source, U13 UI |
| US-NV6 | 차별화 후보와 실험 계획 생성 | U12 | — | U11 근거, U13 표시 |
| US-NV7 | 탐구 프로세스 진행상태 표시 | U12 | REM-2 | U13의 REM 하위 작업 표시 |
| US-NV8 | 내부 저장 후 Notion export | U12 | — | 기존 export port, U3 권한 |
| US-NV9 | novelty Agent 운영 관측성과 품질 게이트 | U12 | — | U6 관측/품질 지원 |
| US-EV1 | 근거형성 세션 시작 | U11 | — | U3 인증, U13 UI |
| US-EV2 | 자동 범위 근거형성 질문 | U11 | — | U2 검색, U1 source, U13 |
| US-EV3 | 명시 논문 집합 근거형성 | U11 | — | U4 선택, U1 source |
| US-EV4 | 첨부 문서 근거형성 | U11 | REM-2 | U1 user_docmodel, U3 권한, U13 |
| US-EV5 | 멀티턴 후속 질문 | U11 | — | U13 UI |
| US-EV6 | 기권 경로 (근거 없음·범위 밖) | U11 | — | U1/U2 근거, U13 표시 |
| US-EV7 | 세션 재열람 & 영속 | U11 | REM-2 | U13 재열람, U3 현재 권한 |
| US-EV8 | 세션 삭제·초기화 | U11 | REM-3 | U3 lifecycle, REM-2/U1 late-write/private 결과 정리 |
| US-EV9 | 근거형성 근거화·불변식 운영 | U11 | — | U6 관측, U12 port consumer |
| US-AG1 | 하단 네비에서 에이전트 채팅 진입 | U13 | — | U5 shell, U3 인증 |
| US-AG2 | 새 채팅에서 Agent 모드 선택 및 고정 | U13 | — | U11/U12 mode 계약 |
| US-AG3 | 과거 세션 drawer와 멀티턴 채팅 | U13 | — | U11/U12 session/결과 |
| US-AG4 | 탐구 과정 timeline 표시 | U13 | REM-2 | U11/U12, U5 공통 job 상태 |
| US-AG5 | 파일 첨부와 상태 UX | U13 | REM-2 | U1/U11/U12 private 첨부, U3 권한 |
| US-AG6 | mock/real transport 경계와 실패·저하 처리 | U13 | — | U11/U12 API, U5 transport |
| US-AG7 | 에이전트 채팅 프론트엔드 품질 게이트 | U13 | — | U5 UI tooling, U6 품질/관측 |
| US-OB1 | 가입 시 관심 카테고리 선택 | U14 | — | U3 가입, U5 picker |
| US-OB2 | 기존 사용자 차기 로그인 프롬프트 | U14 | — | U3 로그인, U5 picker |
| US-OB3 | 관심사 설정 이벤트로 프로필 시딩 | U14 | — | U9 이벤트/집계 |
| US-OB4 | ORCID 관심사 유도 | U14 | — | U3 ORCID, U9 시딩 |
| US-TN1 | 팔로우 주제 목록 관리 | U15 | — | U5 설정 UI, U3 권한 |
| US-TN2 | 옵트인과 수신 해지 | U15 | REM-3 | U5 token observer, U3/U6 제한된 접근/집행 |
| US-TN3 | 신규 논문 다이제스트 수신 | U15 | — | U1 harvest, 기존 email 경로 |
| US-WR1 | 근거 결과에 웹 레퍼런스 동봉 | U11 | — | 공유 외부검색 port |
| US-WR2 | novelty 외부 탐색에 학술 웹 합류 | U12 | — | U11/shared 외부검색 계약 |
| US-SB1 | 내 플랜 확인과 free 기본값 | U16 | — | U5/U10 표시, U6 quota |
| US-SB2 | plus 부여와 쿼터 상향 | U16 | — | U3 ADMIN 권한, U6 quota |
| US-SB3 | 만료와 paid-through-period 다운그레이드 | U16 | — | U6 quota, U5 표시 |
| US-RJ1 | 업무 접수와 진행·상태 확인 | U5 | REM-2 | REM-3 admission 보호, U3/U6 및 업무 domain |
| US-RJ2 | 재연결 후 같은 작업의 결과 확인 | U5 | REM-2 | REM-3 observer/receipt, U6 및 service별 failure/compatibility |
| US-RJ3 | 권한 안에서 문서·자산 결과 열람 | U5 | REM-2 | U1/U3/U7/U11/U12 context/권한, REM-3 lifecycle |

### Product owner 및 delivery 요약

| Product owner | Primary story 수 | 집합 |
|---|---:|---|
| U1 | 3 | US-I1~3 |
| U2 | 5 | US-D1~4, US-D6 |
| U3 | 7 | US-A1~7 |
| U4 | 3 | US-L1~3 |
| U5 | 5 | US-H1, US-D7, US-RJ1~3 |
| U6 | 9 | US-D5, US-R1~5, US-S6, US-CG6, US-P7 |
| U7 | 5 | US-S1~5 |
| U8 | 5 | US-CG1~5 |
| U9 | 6 | US-P1~6 |
| U10 | 0 | U3 설정/삭제 UI 등의 contributor |
| U11 | 10 | US-EV1~9, US-WR1 |
| U12 | 10 | US-NV1~9, US-WR2 |
| U13 | 7 | US-AG1~7 |
| U14 | 4 | US-OB1~4 |
| U15 | 3 | US-TN1~3 |
| U16 | 3 | US-SB1~3 |

총 85개다. core 45개의 기존 owner를 유지했고 후속 story와 US-RJ를 UGP1의 개별 owner로 완결했다. OP persona 여부만으로 domain 품질 story를 U6로 재배정하지 않는다(US-NV9=U12, US-EV9=U11, US-AG7=U13).

| REM primary | 이번 delivery story 수 | Story 집합 |
|---|---:|---|
| REM-1 | 2 | US-R4, US-R5 |
| REM-2 | 12 | US-RJ1~3, US-S1/2/3/5, US-NV7, US-EV4/7, US-AG4/5 |
| REM-3 | 3 | US-A6, US-TN2, US-EV8 |
| REM-4 | 1 | US-R2 |

이 18개의 contribution은 unit-local 구현과 최종 integration 증거로 구분한다. 특히 REM-1 primary인 공통 관측/health의 최종 성공은 REM-2/3/4의 실제 local 구현 및 G4/G5를 함께 확인한다.

### F01~F13 primary 및 검증 연결

| Finding | Primary REM | 필수 contributor / 검증 표면 | Gate |
|---|---|---|---|
| F01 | REM-2 | U1/private context, U3 권한, U7 public namespace, U11/U12 | G2/G4 |
| F02 | REM-2 | U7 canonical source/owner variant, U1/U2 source 계약 | G2/G4 |
| F03 | REM-4 | U1 corpus/repair, U6 readiness, verified source | G4/G5 및 별도 corpus gate |
| F04 | REM-3 | U3 lifecycle 및 모든 owner store/job/control copy | G3/G5 |
| F05 | REM-2 | U7/RK/worker, U5 접수/완료/timeout | G2/G4 |
| F06 | REM-1 | 모든 package lock/artifact/CI/SBOM | G1 및 최종 artifact 재검증 |
| F07 | REM-2 | U1 asset, U3 owner/license 권한, U5 binary/CSP | G2/G4 |
| F08 | REM-1 | domain migration 정의, single ordered registry/startup/CLI | G1 |
| F09 | REM-3 | U15 token/consent/sender, U5 실제 link/observer | G3/G4 |
| F10 | REM-3 | U5 trusted ingress/BFF, U6/U3 동일 client identity | G3/G4 |
| F11 | REM-4 | U2 assembler, U5 classifier | G4 |
| F12 | REM-4 | U1 verified generation, U2 calibration/policy | G4 및 corpus data gate |
| F13 | REM-1 | shared schema, 실제 Python/TS build-consumed bindings | G1 및 후속 계약 변경 검증 |

### RJ-AC01~12 primary 및 story 연결

| 인수 | Primary REM | 필수 contributor / 구현 인수 | Story / gate |
|---|---|---|---|
| RJ-AC01 | REM-2 | REM-3 suppression admission; durable commit/불확정 접수 | US-RJ1; G2/G4 |
| RJ-AC02 | REM-2 | REM-3 status instance; queued query/비재귀 직접 결과 | US-RJ1/2; G0/G2/G4 |
| RJ-AC03 | REM-2 | REM-4 SEARCH 및 REM-3 outcome; 접수/terminal/저하 구분 | US-RJ1, US-S5, US-R2; G4 |
| RJ-AC04 | REM-2 | REM-3 observer 및 각 service retention/replay | US-RJ2; G2/G4 |
| RJ-AC05 | REM-2 | U3/resource owner, REM-3/4의 current grant/purpose/비노출 | US-RJ3; G2/G3/G4 |
| RJ-AC06 | REM-2 | REM-3 재전달/삭제, REM-4 instance; 중복 효과/caller 격리 | US-RJ1/3; G2/G3 |
| RJ-AC07 | REM-2 | U7/U1 canonical source/version 및 cache-backed 결과 | US-S1/2/5; G2/G4 |
| RJ-AC08 | REM-2 | U5 BFF/UI, U1 manifest, U3 권한; same-origin bytes | US-RJ3, US-S3; G2/G4 |
| RJ-AC09 | REM-3 | 모든 domain EXEC 및 REM-2/4 owner-bound control data | US-A6, US-EV8; G3/G5 |
| RJ-AC10 | REM-3 | U15 sender/settings, U5 제한 observer; 즉시 suppression | US-TN2; G3/G4 |
| RJ-AC11 | REM-3 | U3 직접 제어, U5/U6 ingress, REM-2 admission fence | US-RJ1, US-A6; G3/G4 |
| RJ-AC12 | REM-1 | REM-2/3/4 실제 queue/crash/reconnect/restore/health 증거 | US-RJ2, US-R2/4/5; G2/G4/G5 |

Component 17개에 대한 primary/local-instance 배치는 `unit-of-work.md`, 위 gate와 의존 종류는 `unit-of-work-dependency.md` 및 WPR2를 따른다. story map이 business/data authority나 runtime grant를 새로 부여하지 않는다.
