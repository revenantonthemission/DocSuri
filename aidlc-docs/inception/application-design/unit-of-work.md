# unit-of-work.md — 유닛 정의 (Units of Work)

> **현재 산출물**: 하단 `2026-09-19 Deployable-Service Units`가 UGP1=A에 따른 현재 unit 정의다. 상단의 초기 배포 번호/AWS/동기-only 설명과 Greenfield tree는 이력이며, 현재 runtime/계약은 승인된 DAD1/WPR2 및 아래 정의를 따른다.

**단계**: INCEPTION → Units Generation · **일자**: 2026-06-15
**근거**: `application-design/`(U1~U6), UQ1=A(6 유닛), UQ2=A(모노레포), UQ3=A(4 배포 단위), UQ4=A(데모 우선), UQ5=A(공유 계약 `shared/`). 2026-06-26 U1 Corpus 리뷰: 신규 유닛 없이 기존 U1 확장.
**2026-08-03 유닛 재구성**(`inception/plans/unit-recomposition-plan.md`, UQ1~5 답변 완료): U10·U13 정식 등재, U11/U12 코드 위치 정정, 구 `research` 모듈 U11 흡수(`backend/modules/evidence/sessions/`), `user_docmodel` U1 소유 확정(포트 `docsuri_shared.ports.UserDocModelCoordinatorPort`).

**정의**: 유닛 = 개발용 스토리 논리 묶음. 모듈형 모놀리스(DQ1)이므로 일부 유닛은 한 배포 단위(API) 내 **모듈**, 일부는 **독립 배포**(워커·프런트).

---

## 유닛 정의

| 유닛 | 책임 | 유형 | 배포 단위 | 코드 위치 | 경로 종류 |
|---|---|---|---|---|---|
| **U1 Ingestion** | arXiv·Semantic Scholar·OpenAlex AI/ML 논문 수집 → FullText → eager DocModel → DocModel Block 청크·임베딩 → 공유 Corpus 인덱스/OpenSearch·S3 생성·갱신(단일 writer) | 독립 워커 | ② 인제스천 워커 | `ingestion/` | 이벤트/스케줄 |
| **U2 Discovery** | 자연어 질의 동기 검색 읽기 경로(질의 이해·하이브리드 검색·랭킹·근거화 어댑팅·결과 조립) | API 모듈 | ① API | `backend/modules/discovery/` | 동기 REST |
| **U3 Accounts/Auth** | 가입/로그인/세션·자격증명·**객체 소유권 인가 단일 결정점** | API 모듈 | ① API | `backend/modules/accounts/` | 동기 REST(+이벤트 신호) |
| **U4 Library** | 검색 저장·라이브러리·이력(소유자 비공개) | API 모듈 | ① API | `backend/modules/library/` | 동기 CRUD(+이력 이벤트 소비) |
| **U5 Frontend** | SSR 폰 우선 웹 UI(검색·결과·계정·라이브러리·상태; 폰 목업 프레임) | 독립 프런트 | ④ 프런트엔드 | `frontend/` | 동기 REST(클라이언트) |
| **U6 Reliability/Ops** | DQ5 횡단 미들웨어/게이트웨이(API 내) + 운영 워커(탐지·대시보드) | 미들웨어 + 워커 | ① API(게이트웨이) · ③ Ops 워커(탐지·대시보드) | `backend/middleware/` · `ops/` | 동기 게이트 + 이벤트 백본 |
| **U7 Summarization** *(2026-06-18 편입)* | 검색된 단일 논문의 온디맨드 요약(Sonnet)·초록 번역(Haiku)·개인화(persona/뷰/용어집); 근거 앵커·기권; 영구저장(S3)+핫캐시(Redis) | API 모듈(+초장문 비동기 잡 옵션) | ① API (+③ 비동기 잡 옵션) | `backend/modules/summarization/` | 동기 REST(스트리밍) + 이벤트(관측/비용) |
| **U8 Citation Graph** *(2026-06-19 편입)* | 논문 상세보기의 backward references 각주 트리; ID 해소·unresolved 분리·깊이/노드 상한·라이브러리 저장 연동; 외부 citation API 캐시/저하 | API 모듈 | ① API | `backend/modules/citation_graph/` | 동기 REST + 캐시 + 관측 이벤트 |
| **U9 Personalization** *(2026-06-23 편입)* | 의미 있는 사용자 행동 이벤트 기록, 관심 프로필 집계, 개인화 설정/삭제/초기화, 검색·요약·번역 기본값 개인화 제공 | API 모듈 | ① API | `backend/modules/personalization/` | 동기 REST + 비차단 이벤트 기록 |
| **U10 MyPage** *(2026-08-03 등재 — 타 팀원 빌드 머지분 사후 반영)* | 마이페이지 — mock 구독(플랜 표시·"하는 척만" Q10, 실 PG/청구 없음 — U16 편입 후 플랜 값은 U16 소유) + 계정 메뉴 백엔드(`/mypage/*`). 관심 논문·로그아웃 메뉴는 FE가 U4 `GET /library`·U3 `POST /logout` 직접 호출(U10 백엔드 없음) | API 모듈 + FE 메뉴 | ① API (+④ 프런트엔드) | `backend/modules/mypage/` | 동기 REST |
| **U11 Evidence Agent** *(2026-06-29 편입 — 재인셉션 Phase 4 / requirements 초안 "[U4]" 오기 → U11 정정 2026-06-30)* | 로그인 필수 대화형 다논문 문헌탐색·근거형성 Agent. 사용자 질의/첨부에 대해 여러 논문을 교차확인해 핵심 주장·방법·결과 수치·한계를 추출·비교하고 쟁점 오버레이로 제시; 근거 없으면 기권(FR-5). 세션·결과 owner-scoped 영속. EvidenceFormationPort(D5)를 통해 U12(novelty Agent)에 Tool로 노출. **2026-07-23 확장**: 웹검색 레퍼런스 도구(FR-49 — 학술 공개 API 링크백 전용, C-11; 포트는 U12에도 노출) | API 모듈 (+비동기 잡 옵션) | ① API (+③ 잡 옵션) | `backend/modules/evidence/` *(2026-08-03 재구성 정정 — 구 표기 `evidence_agent/`는 오기)* + 세션 셸 `backend/modules/evidence/sessions/` *(구 `research` 모듈 흡수 — 라우트 `/api/research`·readyz 라벨 `research` 유지)* | 동기 REST(SSE 스트리밍) + 비동기 잡 (장분석) |
| **U12 Novelty Agent** *(2026-06-29 편입 / 번호 확정 2026-06-30 — requirements 초안 "[신규]")* | 차별화(novelty)/연구아이디어 형성 Agent. 자연어 의도·업로드 원고에서 EvidenceFormationPort(U11)·U2 `full` 검색·GitHub/데이터셋 외부 탐색을 소비해 유사 연구 정리·bounded 차별화 아이디어·실험 계획·원고 위험 신호 생성; 단계별 진행상태·owner-scoped 저장·승인형 Notion export; 근거 없으면 기권(FR-5). FR-30~35·US-NV1~9·QT-10·NFR-P5/R3 | 독립 Agent 워커 (+비동기 잡) | ⑤ novelty 워커 (`Docsuri-Novelty` 스택, `NOVELTY_AGENT_ENABLED` 게이트) | `backend/modules/novelty/` + `Docsuri-Novelty` 워커 스택(`ops/cdk/stacks/`) *(2026-08-03 재구성 정정 — 설계 문서는 `construction/novelty-agent/`)* | 비동기 잡(생성/폴링/취소) |
| **U13 Agent Chat Frontend** *(2026-08-03 등재 — 인셉션 산출물[requirements·stories US-AG1~6·application-design·construction/agent-chat-frontend]은 U13으로 완결·Build&Test 완료였으나 본 표 등재 누락 정정)* | 에이전트 채팅 UI — evidence/novelty 모드 선택·고정(BR-AG-1), 세션 drawer·멀티턴, 탐구 timeline, 첨부(PDF/MD/TXT allowlist), mock/real transport 경계·failed/degraded 분류. U11(`/api/research`)·U12(novelty 잡) REST/SSE 소비 | 프런트 슬라이스 | ④ 프런트엔드 | `frontend/`(agent chat 컴포넌트·transport) | 동기 REST(클라이언트) + SSE |
| **U14 Onboarding** *(2026-07-23 편입 — Phase 3)* | 가입/차기 로그인 시 관심사 수집(arXiv 카테고리 픽커, 스킵 가능) + ORCID 프로필·저작 관심사 유도 → **관심사 설정 행동 이벤트**(FR-39 개정)로 U9 프로필 시딩(`categoryWeights`+`keywordWeights`) — 개인화 콜드스타트 해소. US-P5 선행 포함. FR-44~46·US-OB1~4·C-7/C-8 | API 모듈 + FE 플로우 | ① API (+④ 프런트엔드) | `backend/modules/onboarding/` *(제안 — 설계 단계 확정)* · `frontend/`(픽커 플로우) | 동기 REST + 비차단 이벤트 기록 |
| **U15 Trends/Notifications** *(2026-07-23 편입 — Phase 3)* | 명시적 팔로우 주제 목록(설정 UI, U14/U9 관심 프로필과 별개) + **옵트인** 이메일 다이제스트 — harvest 신규 논문을 키워드/임베딩 유사도로 매칭해 plain list 발송(기본 daily·사용자 설정, 기존 `EMAIL_PROVIDER` 경로 = SES on `559352512800`). FR-47~48·US-TN1~3·C-9/C-10 | API 모듈 + 배치 발송 잡 + FE 설정 플로우 | ① API (+③ 잡) (+④ 프런트엔드) | `backend/modules/trends/` *(제안 — 설계 단계 확정)* · `frontend/`(설정 플로우) | 동기 REST + 스케줄 배치 발송 |
| **U16 Subscription/Plans** *(2026-07-24 편입 — Phase 3)* | 플랜/티어 도메인(2단 **free/plus**) — 플랜이 에이전트 daily 쿼터(evidence·novelty)를 결정, 기타 기능 전 티어 동일. **v1 결제 카브아웃**(C-12): ADMIN 수동 부여(월 기간)·paid-through-period·만료 자동 free 전환. per-user 일일 spend 롤업 신설(실측 캘리브레이션 파이프라인). FR-50~51·US-SB1~3·C-12 | API 모듈 + 만료 전환 잡 + FE 플랜 표시 | ① API (+③ 잡) (+④ 프런트엔드) | `backend/modules/plans/` *(제안 — 설계 단계 확정)* · `frontend/`(플랜 표시) | 동기 REST + 만료 배치 |
> **U6 분할 주석**: U6는 두 곳에 산다 — (a) **게이트웨이 미들웨어**(authn/authz·검증·레이트리밋·비용 상태·근거화 강제 후크)는 API 배포 단위 ① 내부, (b) **Ops 워커**(AI 인시던트 탐지기·대시보드)는 이벤트 백본 소비 독립 워커 ③.

> **U7 주석 (요약/번역)**: U7은 결과 카드의 **온디맨드 보조 기능**(검색 SLA NFR-P1 비대상, NFR-P2). U6 게이트웨이를 단일 진입으로 도달하며, **U1 DocModel/FullText(S3 read = capability)·U6 근거화 후크/비용 게이트(`shared/ports` lib)에 의존**한다(U2와 동일 패턴 — 코드 순환 없음). LLM 호출은 U2 검색과 별개 경로. 대부분 단일 콜 동기 스트리밍, **초장문(map-reduce)만 비동기 잡**(배포 ③). 산출물은 S3 영구 + Redis 핫캐시(키 immutable, 논문당 평생 1회 생성).

> **U8 주석 (인용 그래프/각주 트리)**: U8은 논문 상세보기 페이지에서 호출되는 **로그인 필수 온디맨드 읽기 경로**다. v1은 backward references만 다루며 forward citations·3-hop 이상·FE 구현은 제외한다. 외부 citation API(Semantic Scholar 우선)는 온디맨드 조회 + 7일 snapshot 캐시로 감싼다. 노드 저장은 U4 Library 계약을 재사용한다.

> **U9 주석 (개인화/행동 인텔리전스)**: U9는 사용자별 원시 행동 이벤트와 집계 관심 프로필을 소유한다. v1은 검색 결과의 작은 boost/rerank와 요약/번역 기본값 제안만 다루며, 별도 추천 목록·전체 클릭스트림·hover/scroll 추적·강한 리랭크·실시간 ML 추천 파이프라인은 제외한다. U9 실패는 U2/U4/U7 본 기능을 막지 않는 비차단 저하로 처리한다.

> **U10 주석 (마이페이지)**: 2026-08-03 재구성에서 머지된 코드 기준으로 정식 등재(구 자리 주석 해소). U10은 **UI+얇은 백엔드**만 소유 — 계정 도메인 규칙은 U3, 라이브러리 데이터는 U4, 플랜/쿼터 값은 U16이 소유한다(U10 구독 표시는 mock).
>
> **U11 주석 (문헌탐색·근거형성 Agent)**: U11 = 재인셉션 차터 페이즈 4(requirements "[U4]"). LLM Agent가 Search·DocModel·Summary 도구를 자율 오케스트레이션해 다논문 근거를 형성한다. 스트리밍 우선(NFR-P6), 긴 분석은 비동기 잡 옵션(U7 패턴 재사용). EvidenceFormationPort 단일 구현자(D5 계약 게이트) — U12(연구아이디어 Agent, 미래)가 소비. U11 실패는 본 유닛 응답만 영향(U2/U4/U7/U9 비차단).
> **U11 확장 (2026-07-23 — 웹검색 레퍼런스, FR-49/C-11, 에픽 14 US-WR1~2)**: 학술 공개 API(Semantic Scholar·OpenAlex — 무키) 웹검색 도구 추가 — 결과에 **링크백 전용** 웹 레퍼런스 목록 동봉(claims 불참여, C-11 — SourceRef 실재성 검증 체계 무변경). 외부검색 포트는 U12 novelty에도 노출(GitHub/HF/Zenodo 대열 합류). Noop 저하·기존 evidence 쿼터(30/day) 흡수. **신규 유닛·신규 배포 단위 없음.** 결정 기록: `requirements/web-references.md`.
>
> **연구 에이전트 번호 재부여 완료(2026-06-29 / U12 빌드 반영 2026-06-30)**: 구 통합 "U11 Research Agent"는 폐기되고 **U11(문헌탐색·근거형성) / U12(차별화·연구아이디어 novelty)**로 분리 확정(재인셉션 차터 §4). 둘 다 본 표에 정의. **U12(novelty)는 별도 인셉션 사이클로 이미 빌드됨** — 요구사항 FR-30~35·스토리 US-NV1~9·QT-10·NFR-P5/R3, 설계/코드 `construction/novelty-agent/`, 배포 `Docsuri-Novelty` 스택(`NOVELTY_AGENT_ENABLED`). (코드/CDK는 구 U11 엄브렐러 네이밍 잔존 — 인셉션 유닛 번호는 U12.)
>
> **U14 주석 (온보딩)**: U14는 시딩 이벤트의 **생산자**일 뿐, 프로필 저장·집계는 U9 소유를 유지한다(직접 프로필 기록 금지 — C-7, TTL/재집계 소실 방지). 픽커/ORCID 유도 실패는 가입·로그인을 막지 않는 비차단 저하(NFR-P4). 결정 기록: `inception/requirements/onboarding.md`(OQ 7건 오너 결정, 2026-07-23).
>
> **U15 주석 (트렌드/알림)**: 다이제스트 실효는 **daily harvest 재개**(오너 추후 결정 — 현재 CDK `ArxivDailySchedule` `enabled=False`)에 종속 — U15 빌드/테스트는 기존 코퍼스로 가능. 매칭은 기존 코퍼스 임베딩 재사용, 팔로우 주제는 등록 시 1회 임베딩. 옵트인 전 무발송(FR-48), 발송 실패는 타 사용자·타 기능 무영향 비차단 저하. **SES sandbox→production access**(계정 `559352512800`)와 로컬 서빙용 자격증명 방식은 운영/설계 후속. 결정 기록: `inception/requirements/trends-notifications.md`(OQ 8건 오너 결정, 2026-07-23).
> **U16 주석 (구독제/플랜)**: **v1 결제 없음**(C-12 — PG 연동·청구 코드 제외, ADMIN 수동 부여만; 결제 도입 시 PG 어댑터 추가 경로). 플랜은 CostGuard 집행에 **쿼터 값만 공급**(계약 불변, NFR-C1 — 미부여=free=현행 쿼터 무회귀). **plus 수치 TBD** — `reports/costguard-spend-report-2026-07.md`(OQ-5 선행물)의 상한 산식으로 설계 단계 오너 확정(기본 제안 3×: evidence 90/day·novelty 15/day, 월 최악 ~$378/인). per-user 일일 spend 롤업 신설로 차기 캘리브레이션은 실측 기반. 결정 기록: `inception/requirements/subscription.md`(OQ 8건 오너 결정, 2026-07-24).

## 배포 단위 (UQ3=A)
1. **API 서비스** — U2 + U3 + U4 + **U7 + U8 + U9 + U10 + U11(+sessions) + U14 + U15 + U16** + U6 게이트웨이 미들웨어 (동기 REST, 모듈형 모놀리스) *(2026-08-03 재구성: U10·U14~U16 반영, U11 세션 셸 포함)*
2. **인제스천 워커** — U1 (이벤트/스케줄)
3. **Ops/탐지 워커** — U6 탐지기·대시보드 (이벤트 백본) **(+ U7 초장문 요약 비동기 잡 옵션)**
4. **프런트엔드** — U5 (SSR) + **U13 agent chat 슬라이스** (+U14/U15/U16 FE 플로우)
5. **novelty 에이전트 워커** — U12 (`Docsuri-Novelty` 스택, `NOVELTY_AGENT_ENABLED` 게이트, 비동기 잡 — 별도 인셉션 사이클로 빌드; 코드 위치 `backend/modules/novelty/`)

공유 capability(기술 미확정): Corpus/OpenSearch 인덱스, DocModel/FullText 오브젝트 스토리지, GROBID 런타임, 관리형 DB/영속화, 이벤트 버스/백본, 임베딩/LLM 게이트웨이, DLQ. **(U7 추가 활용: 오브젝트 스토리지[DocModel/FullText read + 요약 영구저장]·핫캐시[Redis]·LLM 게이트웨이[Sonnet/Haiku]. U8 추가 활용: citation snapshot 캐시/스토어·외부 citation API 쿼터 카운터. U9 추가 활용: 사용자 행동 이벤트/관심 프로필 RDS 테이블.)**

## 코드 조직 전략 (Greenfield, UQ2=A 모노레포)
```text
<repo-root>/
├── frontend/                # U5 — SSR 폰 우선 웹 (배포 ④)
├── backend/                 # 배포 ① API (모듈형 모놀리스)
│   ├── modules/
│   │   ├── discovery/       # U2
│   │   ├── accounts/        # U3
│   │   ├── library/         # U4
│   │   ├── summarization/   # U7 — 요약/번역(온디맨드, Sonnet/Haiku)
│   │   ├── citation_graph/  # U8 — 각주 트리/backward references
│   │   ├── personalization/ # U9 — 행동 이벤트/관심 프로필/개인화 설정
│   │   ├── mypage/          # U10 — 마이페이지(mock 구독·계정 메뉴)
│   │   ├── evidence/        # U11 — 근거형성 Agent (+ sessions/ 채팅 세션 셸, 구 research)
│   │   ├── novelty/         # U12 — novelty Agent (워커 스택 Docsuri-Novelty)
│   │   ├── onboarding/      # U14 — 온보딩(관심사 시딩 이벤트 생산)
│   │   ├── trends/          # U15 — 트렌드/알림(팔로우 주제·다이제스트)
│   │   ├── plans/           # U16 — 구독제/플랜(쿼터 값 공급)
│   │   └── user_docmodel/   # U1 백엔드 seam — 사용자 PDF→DocModel 코디네이터(포트=docsuri_shared.ports)
│   └── middleware/          # U6 게이트웨이(authn/authz·검증·레이트리밋·비용·근거화 후크)
├── ingestion/               # U1 — 인제스천 워커 (배포 ②)
├── ops/                     # U6 — 탐지기·대시보드 워커 (배포 ③)
└── shared/                  # UQ5=A 공유 계약 단일 소유
    ├── vector-spec          # 임베딩 스키마(U1 writer ↔ U2 reader 동일 공간 불변식)
    ├── dtos                 # 결과/카드/계정/라이브러리 DTO
    ├── events               # 이벤트 스키마(SearchExecuted, AI 인시던트)
    └── ports                # 횡단 후크 인터페이스(근거화·비용) — 의존성 역전(코드 순환 방지)
```
구체 언어·프레임워크·런타임은 **NFR Requirements/Construction**에서 확정(이전 사이클 Python 백엔드 + Next.js 프런트는 선행 사례).

## 빌드/개발 순서 (병렬화 조율 반영 - 2026-06-16)
개발 기간 단축을 위해 `shared/` 공용 규약을 선행 작성한 뒤, 아래와 같이 3개 독립 트랙으로 병렬 개발을 진행합니다.

* **준비 단계**: `shared/` 규약 고정 (`vector-spec` 및 API DTO, 이벤트 스펙 선행 작성)
* **[트랙 1] 데이터 파이프라인**: **U1 Ingestion** (멀티소스 Corpus 인제스천 워커) ──> **U6 Reliability/Ops** (비동기 탐지 워커)
* **[트랙 2] 인증 및 사용자 데이터**: **U3 Accounts** (가입/로그인) ──> **U4 Library** (저장/라이브러리)
* **[트랙 3] 사용자 검색 및 UI**: **U2 Discovery** (Mock API 기반 선행 개발) ──> **U5 Frontend** (UI 화면 및 인터랙션)
* **[확장 / 2026-06-18] 요약·번역**: **U7 Summarization** — 코어(U1~U6) 빌드·배포 완료 후 편입되는 신규 유닛. **선행 의존**: U1(DocModel/FullText S3 capability)·U6(근거화 후크·CostGuard)·shared(DTO·ports) = 이미 가용. 결과 카드 표면은 U2/U5와 연결. 단일 트랙으로 CONSTRUCTION 유닛 루프 진행(**실배포 기준 real-first 구현** — LLM·스토어 어댑터는 포트 뒤 실 구현 단일본[Bedrock·S3·Redis], mock/인메모리 대역 없음. _2026-06-18 U7 FD 답변 Q10/Q11로 확정._).
* **[확장 / 2026-06-19] 인용 그래프·각주 트리**: **U8 Citation Graph** — 논문 상세보기 페이지의 4개 액션 중 각주 트리 API를 제공한다. **선행 의존**: U3/U6(로그인·게이트웨이), U4(라이브러리 저장 계약), U5/상세보기 분기(FE 표면), shared(DTO·events). Requirements/User Stories/Units Generation까지만 진행하고, Construction은 별도 승인 후 시작한다.
* **[확장 / 2026-06-23] 개인화/행동 인텔리전스**: **U9 Personalization** — 행동 이벤트와 관심 프로필을 소유하는 API 모듈. **선행 의존**: U3/U6(로그인·게이트웨이), U2(검색 결과 개인화), U4(라이브러리 신호), U7(요약/번역 기본값), U5(설정/표시), shared(DTO·events). Construction은 U9 단일 유닛 루프로 진행한다.
* **[확장 / 2026-06-24 → 2026-06-28 재구성] 연구 에이전트**: 구 통합 "U11 Research Agent"는 폐기되고 **문헌탐색·근거형성 / 연구아이디어 2개 유닛으로 분리**(재인셉션 차터 §4). 유닛 번호·경계·선행 의존(2유닛 간 의존 포함)은 **신규 인셉션 사이클의 units-generation에서 재부여**한다.

> 각 유닛은 CONSTRUCTION의 유닛별 루프(Functional/NFR/Infra Design → Code Generation)로 진행한다.

---

## 2026-09-19 Deployable-Service Units

**입력**: UGP1=A, DAD1=A, WPR2=A, RJR1=A, RJS2=A.
**상태**: 생성·검증 및 UGR1=A 승인 완료 (2026-09-19). 승인 기록은 `../plans/unit-of-work-plan.md`다.
**정의**: 이번 Construction delivery unit은 **REM-1~REM-4 네 service**다. 기존 U1~U16은 canonical product/domain 참조 체계이며, 16개 product를 다시 구현하는 추가 loop로 계산하지 않는다.

- product story owner는 사용자 가치/인수의 책임, REM primary는 이번 구현/통합의 책임이다. 실제 코드·business rule·data authority는 DAD1의 domain/ordinary-writer/maintenance 배치를 따른다.
- 각 REM은 독립 versioned artifact와 daemon/worker/허용 one-shot role, credential/health/재시작 경계를 갖는다. 공통 RK/AUTH/DELIVERY/EXEC/OBS는 library/port 또는 local instance이며 별도 REM service가 아니다.
- 현재 배포 기준은 single Mac + launchd + OrbStack + Cloudflare Tunnel + Ollama다. 기존 API/BFF/ingestion/agent 역할과의 연결도 각 REM의 vertical slice에 포함한다.

### REM delivery unit 정의

| Unit | 독립 runtime 역할 | Primary component / finding | 필수 산출과 완료 경계 |
|---|---|---|---|
| REM-1 Platform Integrity | read-only evidence daemon, 별도 승인 build/CLI/privileged runner | R1C/R1R/OBS; F06/F08/F13 | ordered registry/ledger, offline public/server bindings, pinned/frozen artifact·audit·SBOM, compatibility/관측 규약. G1 기반 검증을 제공하고 US-R4/5 및 RJ-AC12의 최종 통합 증거 조정을 담당 |
| REM-2 Private Content | content admission/observation daemon, content/status-query worker | EDGE/UI/AUTH/RK/DELIVERY/R2A/R2W; F01/F02/F05/F07 | current authority/context, canonical source/cache, durable 접수, queued status, SSE/result/asset 전달과 UI. 실제 U1/U3/U7/U11/U12 provider 및 consumer 연결을 G2로 검증 |
| REM-3 Lifecycle and Edge Trust | opt-out/policy/observation daemon, purge/consent/status worker | EXEC/R3C/R3P/R3E; F04/F09/F10 | owner/run fence, domain quiescence/manifest/receipt, control copy 포함 파기, token observer/즉시 suppression, trusted client identity. G3와 관련 G4/G5 인수 |
| REM-4 Corpus Integrity | report/운영 admission daemon, audit/calibration worker, 별도 privileged repair runner | R4A/R4R/SEARCH; F03/F11/F12 | production seed fence, generation/source/completeness/calibration evidence, U2/U5의 degraded-empty/no-match, 승인된 exact repair. G2/G4/G5와 corpus data gate |

중요도는 DAD1을 계승한다: REM-1/4 High, REM-2/3 Critical. 각 unit의 장애 영향/직접 health/복구 범위는 DAD1 및 NFR-A1/RES-2를 따른다. single-host best-effort, persistent state의 RPO ≤24h 및 수 시간 RTO 목표를 재사용하며 상세 role별 수치는 Construction NFR에서 검증한다.

### 기존 canonical product와 기여 경로

아래 경로는 기존 source의 기여 위치다. service별 새 packaging/entry path와 physical credential/port는 per-unit NFR/Infrastructure/Code plan에서 확정한다.

| Product | 현재 유지할 authority | 이번 REM 연결 / 기존 source |
|---|---|---|
| U1 | corpus, source/private DocModel·asset 및 user_docmodel 의미 | REM-2 source/context/build/fence, REM-3 owner purge, REM-4 corpus/repair; `ingestion/`, `backend/modules/user_docmodel/` |
| U2 | 검색/retrieval/outcome/relevance 의미 | REM-2 metadata 소비, REM-4 정책/분류; `backend/modules/discovery/` |
| U3 | account/session/current authority와 직접 lifecycle | REM-2 최초 AUTH projection, REM-3 system purpose/purge/revocation; `backend/modules/accounts/` |
| U4 | library/saved search/history | REM-3의 domain-owned purge 참여; `backend/modules/library/` |
| U5 | 공통 웹/BFF 및 사용자 job 경험 story | REM-2 bridge/UI, REM-3 token UX, REM-4 search classifier; `frontend/` |
| U6 | ingress/관측/health 및 운영 정책 | REM-1 공통 규약, 각 REM local 계측, REM-3 trust 집행; `backend/middleware/`, `ops/` |
| U7 | summary/translation/source·glossary 규칙 | REM-2-hosted generation과 단일 writer 전환, owner variant 분류; `backend/modules/summarization/` |
| U8 | citation graph/caches/저장 연동 | 원 계약 유지; owner data 존재 시 REM-3 inventory/EXEC 참여; `backend/modules/citation_graph/` |
| U9 | 행동/profile/개인화 의미 | REM-2의 필요한 owner preference 소비, REM-3 purge; `backend/modules/personalization/` |
| U10 | 마이페이지의 얇은 UI/backend 연결 | U3/U16 authority를 유지하는 UI contributor, 특히 US-A6; `backend/modules/mypage/`, `frontend/` |
| U11 | evidence/context/session 및 evidence port | REM-2 private context/하위 job, REM-3 purge; `backend/modules/evidence/` 및 `sessions/` |
| U12 | novelty/context/결과 및 agent 단계 | REM-2 하위 job, REM-3 purge; `backend/modules/novelty/` |
| U13 | agent chat frontend | REM-2 sub-job timeline/첨부 및 현재 권한; `frontend/`의 agent chat/transport |
| U14 | onboarding 입력/시딩 이벤트 | owner state의 REM-3 inventory/EXEC; `backend/modules/onboarding/` |
| U15 | digest token/consent/settings/sender 의미 | REM-3의 suppression/command/receipt 및 handoff barrier; `backend/modules/trends/` |
| U16 | plan/쿼터/spend 의미 | owner state의 REM-3 inventory/EXEC; `backend/modules/plans/` |

U10은 현재 story map의 primary story가 없더라도 U3 설정 UI 등의 contributor다. product owner가 없다는 뜻이 아니다. U8 등 실제 owner data 보유 여부는 registry inventory로 검증하며 추정으로 누락하지 않는다.

### Component primary 및 local instance 책임

| Component | Primary REM | 필수 contributor / canonical 경계 |
|---|---|---|
| EDGE | REM-2 | REM-3 F10/token; U5/U6/U3 ingress 권위 |
| UI | REM-2 | REM-3 해지 UX, U5/U13; 검색 분류는 REM-4 SEARCH |
| AUTH | REM-2 | U3/resource owner의 최초 current projection과 소비 연결; REM-3 lifecycle/system-purpose 강화, REM-4 operator 소비 |
| RK | REM-2 | REM-1 계약/검증; REM-3/4의 독립 instance와 각 realm persistence |
| DELIVERY | REM-2 | REM-3 token observer, REM-4 operator 결과 instance |
| EXEC | REM-3 | REM-2에 필요한 초기 write-fence/provider, REM-4 repair; 실제 구현은 각 data owner |
| R1C | REM-1 | U6 운영 및 platform evidence consumer |
| R1R | REM-1 | domain schema/migration/lock owner, CI/deploy 경계 |
| R2A | REM-2 | U1/U3/U7/U11/U12 context 및 U5 bridge |
| R2W | REM-2 | U7 core, U1 source consumer, current authority |
| R3C | REM-3 | U15 consent/sender/settings와 U5 observer |
| R3P | REM-3 | U3 lifecycle 및 모든 등록된 domain EXEC |
| R3E | REM-3 | U5/U6/U3의 로컬 identity/limiter 집행 |
| R4A | REM-4 | U1 corpus 및 U2 eval/calibration |
| R4R | REM-4 | U1 purpose-bound mutation, U6 backup/restore |
| SEARCH | REM-4 | U2 outcome/policy, U5 classifier |
| OBS | REM-1 | U6 계약 선행; 각 REM이 자기 role의 실제 telemetry/health 구현 |

초기 AUTH/current projection와 EXEC write fence 등 REM-2의 필수 provider는 REM-2 slice에서 원 domain owner와 함께 구현한다. component primary가 후속 REM이라는 이유로 미구현 dependency를 남겨 G2를 통과했다고 판정하지 않는다. 후속 lifecycle/purge/consent 연결은 REM-3가 검증하며 공개 job activation은 G3/G4 이후다.

### Construction 문서 위치 및 단계

| Unit | 문서 root | 자기 loop |
|---|---|---|
| REM-1 | `aidlc-docs/construction/rem-1-platform-integrity/` | Functional Design -> NFR Requirements -> NFR Design -> Infrastructure Design -> Code Generation |
| REM-2 | `aidlc-docs/construction/rem-2-private-content/` | 동일 loop, 필요한 기존 domain/frontend/provider 포함 |
| REM-3 | `aidlc-docs/construction/rem-3-lifecycle-edge-trust/` | 동일 loop, 모든 owner-data domain contributor 포함 |
| REM-4 | `aidlc-docs/construction/rem-4-corpus-integrity/` | 동일 loop, verified corpus 및 policy consumer 포함 |

애플리케이션 code는 workspace root의 승인된 package 경로에 둔다. 위 root는 문서용이다. Brownfield이므로 Greenfield 디렉터리 전략을 새로 강제하지 않으며, 독립 release를 위한 packaging 변경은 DAD1의 C0~C3 layering과 per-unit 계획으로 검증한다.

### Unit-local 완료와 최종 인수

- REM-1의 첫 unit-local 완료는 G1 platform 기반이다. 후속 service-local 구현이 필요한 US-R4/5 및 RJ-AC12의 전체 인수를 그 시점에 통과로 표시하지 않는다. REM-1은 최종 통합 증거의 primary 조정을 유지한다.
- REM-2/3/4의 각 loop는 자기 source 변경과 실제 provider/consumer/role 연결 증거를 제출한다. local 완료와 public activation, 전체 F/RJ-AC 인수는 별도 판정한다.
- 최종 story/RJ-AC 성공은 primary와 필수 contributor의 증거를 함께 확인한 G4/G5 결과다. 이 구분으로 후속 service를 모두 구현해야 REM-1 기반 작업을 시작/마칠 수 있는 순환 전제를 피한다.
- actor/domain/store inventory, primary별 인수, 실제 failure/recovery scenario, consumer binding, backup/rollback 및 unresolved gate를 unit summary에 남긴다.
- Units 산출물 승인 후 첫 Construction 단계는 **REM-1 Functional Design**이다. 통합 Build and Test는 네 loop의 결과를 연결한다. full corpus rebuild/bulk reparse/reembed/live alias cutover는 별도 명시 승인이다.

### Unit별 확장 적용과 후속 검증

| Unit | Security Full 적용 초점 | Resiliency custom 적용 초점 | PBT Full 후속 표면 |
|---|---|---|---|
| REM-1 | registry/bindings/lock/pin/SBOM, runner 최소 권한 및 evidence 무결성 | artifact/version 호환, startup/CLI 검증, 공통 telemetry/복구 증거 | registry/reference model, offline schema round-trip, generation 실패 원자성 |
| REM-2 | 전 경계 owner/current grant, public/private namespace, source/cache, SSE/asset | durable 접수, outbox/consumer, timeout/backpressure, reconnect/rollback | caller/source 격리, retry/publication 멱등성, status/event 시퀀스 |
| REM-3 | direct lifecycle/consent 보호, 목적 제한 system/token grant, identity | quiescence/receipt/resume, late write, consent handoff, control-data cleanup | purge/재활성화/해지 경쟁, 다른 owner 보존, token/status scope |
| REM-4 | production fixture 방어, 검증된 report/policy, 승인 mutation | generation/freshness, dependency readiness, restore/rollback 및 별도 corpus gate | fixture/reference oracle, generation binding, degraded-empty/no-match |

모든 unit은 DAD1 §8.7 및 WPR2 G0~G5의 적용 규칙을 계승한다. single-Mac의 RESILIENCY-08 예외와 RESILIENCY-09 bounded-capacity 대체를 유지한다. PBT의 실행 검증은 Units Generation에 N/A이며 Functional/NFR/Code/Build의 Full 요구로 연결한다.

### 확장 규칙의 unit-level 배정 검토

Compliant는 해당 제약/검증 책임이 unit과 contributor에 배정됐다는 뜻이다. 실제 runtime 설정/테스트 합격은 Construction의 증거로 판정한다.

| Rule | 상태 | 배정 / 후속 검증 |
|---|---|---|
| SECURITY-01 | Compliant | 모든 REM 및 store owner의 NFR/Infrastructure; 새 operation/result/backup 암호화/TLS와 G5 |
| SECURITY-02 | Compliant | REM-2/3 EDGE, U5/U6 및 각 listener의 접근 로그; Infrastructure/G4 |
| SECURITY-03 | Compliant | REM-1 OBS 규약, 모든 REM local logger/correlation/redaction |
| SECURITY-04 | Compliant | REM-2 U5 BFF/UI의 same-origin/CSP/safe binary headers, G4 |
| SECURITY-05 | Compliant | REM-1 schema 검증 및 각 REM의 kind/context/token/cursor/manifest 입력 검증 |
| SECURITY-06 | Compliant | 각 REM 및 domain owner의 role/grant/single-writer/maintenance 분리 |
| SECURITY-07 | Compliant | 각 REM Infrastructure와 U5/U6 ingress; private listener/고정 routing |
| SECURITY-08 | Compliant | REM-2 current AUTH/DELIVERY, REM-3 lifecycle/token, 모든 resource owner |
| SECURITY-09 | Compliant | REM-4 production seed fence, 모든 REM의 일반화 오류/내부 locator 비노출 |
| SECURITY-10 | Compliant | REM-1 lock/pin/audit/SBOM gate 및 모든 후속 artifact 재검증 |
| SECURITY-11 | Compliant | REM-3 trusted identity, REM-2 admission/observer 제한, 모든 role backpressure |
| SECURITY-12 | Compliant | U3/REM-2 current grant, REM-3 즉시 철회/목적 제한 token/System 권한 |
| SECURITY-13 | Compliant | REM-1 bindings/registry, REM-2 canonical publication, REM-3 manifest/receipt, REM-4 evidence |
| SECURITY-14 | Compliant | REM-1/U6 감사 규약, 각 REM 신호/보존/경보, REM-3 private control-data 정리 |
| SECURITY-15 | Compliant | 모든 REM의 fail-closed/명시적 실패/cleanup 및 G2~G4 |
| RESILIENCY-01 | Compliant | 네 unit 중요도 및 C/M/R/E/D/A 의존/장애 경계 |
| RESILIENCY-02 | Compliant | 모든 unit이 승인된 NFR-A1/RES-2를 계승하고 새 state에 매핑 |
| RESILIENCY-03 | Compliant | REM별 리뷰 + 원 domain/shared owner sign-off, 기존 GitHub review/git-flow |
| RESILIENCY-04 | Compliant | REM-1 artifact/registry, 각 REM version/진행 중 job/단일 writer rollback |
| RESILIENCY-05 | Compliant | REM-1 공통 OBS와 REM-2/3/4의 실제 role 계측, U6 통합 |
| RESILIENCY-06 | Compliant | 각 REM 직접 shallow/deep/compatibility health, G4 synthetic 확인 |
| RESILIENCY-07 | Compliant | 모든 unit의 queue/backup/disk/model/report age 및 처리 지연 경보 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | horizontal scaling N/A; unit별 bounded concurrency/backpressure/capacity gate |
| RESILIENCY-10 | Compliant | 각 service의 worker/observer/authority/health 격리 및 bounded I/O |
| RESILIENCY-11 | Compliant | 새 persistent state를 기존 backup-and-restore 전략에 포함 |
| RESILIENCY-12 | Compliant | REM-2/3/4 및 원 store owner의 backup/retention/purge, G5 restore |
| RESILIENCY-13 | Compliant | REM-1 compatibility evidence와 각 REM consumer/job/receipt 복구 runbook |
| RESILIENCY-14 | Compliant | 각 REM local fault scenario 및 RJ-AC12의 통합 G4/G5 |
| RESILIENCY-15 | Compliant | U6/각 REM의 실패 증거와 기존 RES-11 COE/수정 추적 |
| PBT-01 | N/A - Units Generation | 모든 REM Functional Design에서 domain property 식별 |
| PBT-02 | N/A - Units Generation | REM-1 bindings 및 각 REM DTO/event/manifest round-trip |
| PBT-03 | N/A - Units Generation | REM-2 owner/source, REM-3 파기/consent, REM-4 generation/저하 불변식 |
| PBT-04 | N/A - Units Generation | REM-1 migration, REM-2 submit/publication, REM-3 purge/해지, REM-4 repair의 멱등성 |
| PBT-05 | N/A - Units Generation | registry/상태/권한/corpus-policy reference model |
| PBT-06 | N/A - Units Generation | REM-2/3/4의 crash/revoke/reconnect/purge/rollback 시퀀스 |
| PBT-07 | N/A - Units Generation | 각 domain/REM의 의미 있는 input/owner/grant/version generator |
| PBT-08 | N/A - Units Generation | REM-1 CI 규약 및 각 unit Code/Build shrinking/seed 재현성 |
| PBT-09 | N/A - Units Generation | per-unit NFR Requirements의 Hypothesis/fast-check 매핑 |
| PBT-10 | N/A - Units Generation | F01~F13/RJ-AC 예시 회귀와 각 unit property 병행 |

현재 unit 배정 수준의 적용 규칙에는 blocking finding이 없다. 이 표의 N/A는 활성 확장 해제를 뜻하지 않는다.
