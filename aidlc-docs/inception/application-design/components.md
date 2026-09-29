# components.md — 컴포넌트 정의 (Application Design)

> **현재 승인 설계**: 하단 `2026-09-19 Deployable Services and Public Jobs`를 참조한다. WPR2/RJR1/RJS2 및 DSRQ 결정에 따른 설계가 DAD1=A로 승인됐다. 이전 in-package remediation 절은 superseded 이력이다.

> 범위: AI/ML 논문 디스커버리 시스템의 유닛 컴포넌트.
> 기술 스택 미확정 — 모든 외부 의존성은 capability("vector store", "LLM/embedding gateway", "event bus/backbone", "object storage", "managed DB/persistence adapter")로 참조한다.
> 아키텍처 잠금: DQ1 모듈형 모놀리스 API + 별도 인제스천 워커, DQ2 SSR 폰 우선 프런트엔드, DQ3 이벤트 드리븐 인제스천, DQ4 하이브리드(도메인 모듈 + 공유 레이어), DQ5 전용 횡단 미들웨어/게이트웨이, DQ6 인제스천/운영은 이벤트 백본·디스커버리 READ는 동기 REST, DQ7 REST.

## 비평 반영 요약 (이 문서 관련)
- **[blocking] 근거화 단일 소유자**: FR-5/QT-1 런타임 근거화 게이트는 DQ5에 따라 **U6.GroundingEnforcementHook**가 단일 권위 소유자다. U2.`GroundingAbstainEnforcer`는 후보+검색 레코드를 후크에 전달하고 `GroundingDecision`을 `GroundedResults | AbstainResult`로 매핑만 하는 **얇은 어댑터(GroundingAdapter)** 로 강등됐다 — 독자적 provenance 검사·인시던트 발행 없음.
- **[major] 인시던트 발행 대상 정합**: 팬텀 `IncidentSignalPublisher`를 제거. 근거화 위반 신호는 U6의 실재 컴포넌트 **HallucinationDetector**(AiIncidentDetectorSuite 내 승격된 1급 서브컴포넌트)로 향하고, 발행은 **IncidentEventPublisher**가 담당한다.
- **[major] SEC-8 객체 소유권 단일 권위**: 객체 단위 소유권 결정의 권위 소유자는 **U3.AuthorizationGuard**. U6.AuthnAuthzGuard는 미들웨어 강제 이음새로서 이 결정을 U3에 위임만 한다. U4.UserDataRepository의 owner-scoped 질의는 데이터 계층 백스톱(심층 방어)이다.
- **[major] QT-3 소유자 신설**: U6.HealthMonitoringService에 **ReliabilityEvalProbe** 진입점(우아한 저하/강제 장애 검증)을 부여해 QT-3을 소유. HybridRetriever·CostGuardCircuitBreaker·PartialResultDetector에 QT-3 교차 트레이스.
- **[major] US-I1 소유자**: phase-1 Corpus 빌드와 재생성은 IngestionPipelineService(end-to-end)·CorpusIndexWriter·CorpusRefreshScheduler(triggerBackfill/triggerRebuild)가 소유.
- **[minor] RES-1 팬텀 트레이스 제거**: U1 source adapter 계층에서 RES-1(워크로드 중요도·의존성 맵 문서화) 삭제 — FR-6/C-1/RES-8/RES-9로 유효 트레이스 유지.
- **[minor] PBT-02/03/07 개별 소유자**: 라운드트립/정렬/디덥 불변식을 가진 컴포넌트에 개별 PBT-0x 트레이스 부여.
- **[minor] US-H1 홈 정정**: 히어로 스토리를 U5.SearchScreen·AppShell에 추가(프런트 히어로 표면 소유), U2 백엔드 트레이스는 백킹 경로로 유지.
- **[minor] VectorSpec 공유 계약**: 임베딩 스키마는 공유 임베딩 게이트웨이 레이어가 소유하는 단일 진실 원천(VectorSpec). U1 writer와 U2 reader가 동일 계약을 소비.

---

## U1 — Ingestion (이벤트 드리븐 Corpus 인제스천 워커)

DQ1=A에 따라 사용자向 API와 분리 배포되는 독립 워커. DQ3=C/DQ6에 따라 비동기 이벤트·스케줄 백본으로만 동작(동기 사용자 경로 아님). 워커 내부의 학술 소스/GROBID/임베딩/인덱스 호출은 "워커→업스트림" 동기 호출이며 사용자 동기 경로가 아니다.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **CorpusSourceAdapterSet** | arXiv·Semantic Scholar·OpenAlex 수집 어댑터 집합. | arXiv는 HTML 우선/PDF 폴백, Semantic Scholar·OpenAlex는 PDF→GROBID 입력을 제공; 소스별 레이트/쿼터·타임아웃 준수; OA/인덱싱 허용 여부 표면화 | `fetchMetadataPage`, `fetchFullTextCandidate`, `sourceWatermark` | FR-6, C-1, RES-8, RES-9 |
| **FullTextExtractionProcessor** | 소스 원문 후보를 FullText/DocModel 입력으로 정규화. | HTML 파싱 우선; PDF는 transient GROBID 처리 후 원시 PDF 미저장; 비허용 라이선스·손상 문서 거부; 입력 검증(SEC-5) | `extractFullText`, `validateLicense`, `normalizeSource` | FR-6, FR-18, C-1, SEC-5, RES-9 |
| **SourcePriorityDeduplicationGuard** | cross-source 중복 제거와 승자 선택. | DOI → arXiv id → 정규화(title+1저자+연도) 순으로 dedup; 소스 우선순위와 전문 품질로 canonical paper/version 결정; 멱등성 보장 | `deduplicate`, `canonicalize`, `fingerprint` | FR-6, NFR-C1, QT-9, **PBT-07** |
| **DocModelBuildCoordinator** | 수집 시점 eager DocModel 완성형 생성·저장. | `(paperId, version)`별 DocModel 생성/검증/저장; Section/Block·표·수식·그림 AssetRef·provenance 포함; 누락/재빌드/backfill 큐로 보강 | `buildDocModel`, `storeDocModel`, `validateDocModel` | FR-6, FR-18, QT-9, **PBT-09** |
| **DocModelBlockChunker** | DocModel Block 기반 청킹. | Block 경계를 존중하고 섹션 컨텍스트를 붙여 길이 상한 내 결정적 청크 생성; 모든 청크가 실재 Block id를 참조 | `chunkDocModel`, `chunkId` | FR-6, FR-5, FR-18, QT-9, **PBT-08** |
| **EmbeddingGatewayAdapter** | 공유 임베딩 게이트웨이 capability의 U1측 어댑터. | 청크 배치 벡터화; 타임아웃·재시도·서킷(RES-9); 임베딩 비용 텔레메트리 보고(NFR-C1); **공유 VectorSpec 일관성 보장(U2 reader와 동일 임베딩 공간)**; 게이트웨이 장애 fail-closed(SEC-15) | `embedBatch`, `embeddingSchema` | FR-6, NFR-C1, RES-9, SEC-15 |
| **CorpusIndexWriter** | DocModel 청크를 U2가 읽는 OpenSearch index generation에 멱등 upsert. | vector+lexical 필드 동시 기록; `(paperId, version)` 정합; blue/green generation write와 alias cutover 지원; tombstone/reindex 안전성 | `upsert`, `tombstone`, `indexStats`, `prepareGeneration` | FR-6, FR-2, FR-18, RES-2, QT-9, **PBT-08**, **US-I1** |
| **CorpusRefreshScheduler** | source별 스케줄 갱신·watermark·backfill 진입점. | arXiv/Semantic Scholar/OpenAlex watermark 단조 전진; phase-1 seed/backfill/rebuild job 발행; 비용 상한 도달 시 후순위 작업 보류 | `onSchedule`, `advanceWatermark`, `triggerBackfill`, `triggerRebuild` | FR-6, FR-18, RES-7, RES-2, QT-9, **US-I1** |
| **IngestFailureHandler** | 인제스천 전 단계 실패 분류·재시도·백오프·DLQ·경보. | 재시도 가능/영구 분류; 지수 백오프+최대 재시도(RES-9)·쿼터 인지(RES-8); 소진 항목 DLQ 격리(US-I3); 실패 신호 구조화 로그·경보(RES-7, NFR-O1) | `classify`, `scheduleRetry`, `sendToDLQ`, `emitFailureSignal` | FR-6, RES-7, RES-8, RES-9, NFR-O1, SEC-15 |

---

## U2 — Discovery/Search (동기 검색 읽기 경로)

DQ6 재조정에 따라 사용자向 검색 READ는 동기 REST(NFR-P1 P50<3s). 모든 단계는 동기 순차. 유일한 두 이벤트(SearchExecuted 발행, 관측성/인시던트 신호)는 응답 경로 밖 fire-and-forget이다.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **QueryIntakeController** | 동기 REST 검색 진입점(`POST /api/search`). 검증·정규화·위임·폰 DTO 직렬화. **U2의 공개 REST 계약 표면(외부에서 'DiscoveryAPI'로 부르지 않음)**. | 동기 엔드포인트 노출(NFR-P1); FR-1 입력 계약(≤500자, 비어있지 않음, SEC-5); 검증 실패 시 업스트림 미전송; U6 게이트웨이가 주입한 degradation/cost-circuit·인증 컨텍스트 수신; 종단 상태(정상/기권/빈/저하/검증오류)를 명시 HTTP 매핑(FR-11); 전역 페일클로즈(SEC-15) | REST 컨트롤러. inbound HTTP POST → `SearchResultPageDTO \| AbstainDTO \| DegradedResultDTO \| ValidationErrorDTO`. `SearchOrchestrationService`에 sync 호출 | FR-1, FR-11, SEC-5, SEC-15, NFR-P1, NFR-R1, US-D1, US-D7, US-H1(백킹) |
| **QueryValidator** | 질의 검증·정규화·새니타이즈 순수 컴포넌트. | 길이/빈값/허용문자(SEC-5, FR-1); 정규화(트림·공백·유니코드)로 결정성; 구조화 ValidationResult(US-D1); 제어문자 새니타이즈 | `validate`, `normalize` | FR-1, SEC-5, US-D1, QT-4, **PBT-02**(normalize 라운드트립 멱등) |
| **QueryUnderstandingExpander** | 검증 질의를 임베딩 벡터+lexical 텀으로 확장(하이브리드 입력). | 임베딩 변환(**공유 VectorSpec과 동일 공간** — U1 인덱스 호환); lexical 텀/동의어 확장(FR-2); 필터 힌트 도출; cost-circuit 'LLM off' 시 lexical-only 폴백(NFR-C1, US-R2); 호출 타임아웃·실패 전파(RES-9) | `expand` | FR-2, NFR-C1, RES-9, US-D2, US-R2 |
| **HybridRetriever** | 공유 벡터+lexical 인덱스 후보 검색·병합·디덥. | ANN 시맨틱 검색; lexical 검색·병합·디덥(멱등); 저하 모드 lexical-only/부분 폴백(NFR-R2, US-R2); 각 후보를 실재 레코드 참조와 반환(FR-5 사전조건); 타임아웃·서킷 존중(RES-9) | `retrieve` | FR-2, NFR-R2, RES-9, US-D2, US-R2, QT-4, **QT-3**(저하 폴백), **PBT-07**(디덥 불변식) |
| **RelevanceRanker** | 후보를 관련도순 상위 N(제안 20) 정렬. | 점수 산출·내림차순 절단(FR-3); N 미만이면 가용분만 반환(US-D3); cost-circuit 'rerank off' 시 baseline 폴백(NFR-C1, US-R3); 순서 안정성·점수 노출; QT-2 평가셋 출력 표면 | `rank` | FR-3, NFR-C1, QT-2, US-D3, US-R3, QT-4, **PBT-03**(랭킹 순서 안정성) |
| **GroundingAdapter** *(이전 GroundingAbstainEnforcer — 강등)* | **얇은 도메인 어댑터**. 후보+검색 레코드를 U6 근거화 후크 입력으로 정형화하고 후크의 `GroundingDecision`을 `GroundedResults \| AbstainResult`로 매핑. **독자적 provenance 검사·인시던트 발행 없음.** | 후크 입력(candidate+retrievedRecords) 정형화; 후크 verdict→GroundedResults/AbstainResult 매핑; 기권 시 종단 상태 형성 | `toGroundingInput`, `mapDecision` | FR-5, FR-11, NFR-R1, US-D5, US-D6 |
| **ResultAssembler** | 근거화 결과/기권/빈/저하를 폰 화면 DTO로 조립. | 카드 DTO 매핑(제목·저자·연도·arXiv ID·스니펫·관련도·링크, FR-4); 결과셋 메타(건수·저하·기권 플래그, FR-11); 폰 우선 직렬화(NFR-U1); 내부 점수·디버그 비노출(SEC-9); 반쪽짜리 결과 저하 신호 명시(RES-11(c)) | `assemble` | FR-4, FR-11, NFR-U1, NFR-U2, SEC-4, RES-11(c), US-D4, US-D7, QT-4, **PBT-09**(DTO 라운드트립) |

> **단일 근거화 게이트 주석**: FR-5/QT-1 런타임 강제는 응답 엣지에서 **U6.GroundingEnforcementHook 한 곳**에서만 일어난다. U2는 후크를 호출·매핑만 하며 이중 강제·독자 차단·독자 인시던트 발행을 하지 않는다(invocation site 정의는 services.md 참조).

---

## U3 — Accounts/Auth (계정·인증 도메인 모듈)

모듈형 모놀리스 내 식별·인증 도메인 모듈. 사용자向 가입/로그인/로그아웃은 동기 REST; 텔레메트리/남용 탐지는 이벤트 백본으로 비동기 발행. 횡단 게이트웨이(DQ5)가 요청별 토큰 검증·레이트 리미팅을 강제하며, U3는 게이트웨이가 호출하는 SessionVerifier·권한 결정점을 제공한다.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **AccountController** | 가입/로그인/로그아웃/세션 조회 동기 REST 표면. | 라우트 노출(REST, DQ7); 페이로드 형식·길이 검증 위임·새니타이즈(SEC-5); secure/httpOnly/sameSite 쿠키 세팅·클리어(SEC-12); 일반화 에러(자격증명 존재 미노출, SEC-9/SEC-15); 민감 필드 비로깅(SEC-3) | `POST /auth/signup\|login\|logout`, `GET /auth/session` | FR-7, US-A1, US-A2, SEC-5, SEC-12, SEC-15 |
| **SignupService** | 공개 셀프 가입 오케스트레이터. | 이메일 형식·유일성·비밀번호 정책(PasswordPolicy 위임); 유출 검사 반영(SEC-12); 적응형 해싱·계정 영속(평문 미저장·미로깅, SEC-12/SEC-3); `AccountCreated` 발행; 도메인 측 중복·속도 신호 `SignupAbuseSignal`(SEC-11) | `register` | FR-7, US-A1, SEC-11, SEC-12 |
| **AuthenticationService** | 로그인/로그아웃 오케스트레이터. | 자격증명 검증(상수시간 의도); 성공 시 세션 발급, 실패 시 일반화 에러; 반복 실패 `AuthFailureSignal`(SEC-12); 로그아웃 세션 무효화(US-A2); 노후 해시 재해싱 트리거 | `authenticate`, `revoke` | FR-7, US-A2, SEC-12 |
| **SessionManager** | 세션·토큰 수명주기 관리자. | 서버검증 세션 발급·만료; secure/httpOnly/sameSite 쿠키 정책; 서버측 토큰 검증(SEC-8); 즉시 무효화(US-A2); SessionStore 위임 | `issue`, `verify`, `invalidate` | FR-7, US-A2, SEC-8, SEC-12 |
| **SessionVerifier** | 게이트웨이(DQ5)가 요청별 인증 강제 시 호출하는 검증 어댑터. | 게이트웨이 전달 토큰을 SessionManager로 검증; 인증 주체 반환→다운스트림 컨텍스트 주입; 부재/무효/만료 시 거부(fail closed, SEC-15); P50<3s 예산 침해 없는 경량 동기(NFR-P1) | `verifyRequest` | SEC-8, SEC-12, SEC-15, NFR-P1 |
| **AuthorizationGuard** | **객체 단위 소유권 인가의 단일 권위 결정점(deny-by-default).** U6 게이트웨이와 U4가 이 결정을 위임받는다. | 기본 거부 정책(SEC-8); **객체 단위 소유권 결정(SEC-8) — 시스템 내 유일 권위**; 관리자 역할/MFA 결정점; 거부 결정 반환(일반화는 호출측, fail closed, SEC-15) | `authorize`, `authorizeAdmin` | SEC-8, SEC-12, SEC-15 |
| **CredentialStore** | 자격증명(해시) 영속·검증. 평문 미저장·미반환. | 적응형 해싱(메모리-하드 KDF, SEC-12); 상수시간 의도 검증·재해싱 필요 플래그; 자격증명 영속·조회(평문·시크릿 비로깅, SEC-3); 계정↔식별자 소유권 데이터(SEC-8) | `createCredential`, `verifyCredential`, `rehash` | FR-7, SEC-12, SEC-8, SEC-3 |
| **PasswordPolicy** | 비밀번호 정책·유출 검사 규칙. | 길이·복잡도·차단목록(SEC-12); 유출 검사(breach 어댑터 위임, SEC-12); 구조화 사유 코드 | `evaluate` | SEC-12, US-A1 |
| **SessionStore** | 세션 상태 영속 어댑터(공유 데이터 레이어). | 세션 레코드 영속·조회·삭제; 서버측 무효화 즉시성(US-A2); 계정/세션 메타 RPO~24h 백업 분류(RES-2) | `persist`, `load`, `remove` | FR-7, US-A2, SEC-8, RES-2 |
| **AccountDeletionService** | 계정 소프트 삭제 및 파기 오케스트레이션. | 계정 비활성화, 파기 잡 스케줄링, `AccountDeleted` 발행 및 `AccountPurged` 캐스케이드 추적(GDPR) | `requestDeletion`, `purgeJob` | FR-28, US-A6, SEC-8 |
| **PasswordResetService** | 비밀번호 분실 재설정 흐름. | 토큰 해시 영속화, 재설정 메일 발송 위임, 토큰 검증 후 비밀번호 재해싱 갱신(전 세션 무효화) | `requestReset`, `confirmReset` | FR-26, BR-A8 |
| **EmailVerificationService** | 계정 이메일 인증 및 변경. | 토큰 발급, 이메일 변경 절차 시 기존 메일 알림, 상태 활성화 전환 | `verifyEmail`, `requestEmailChange`, `confirmEmailChange` | BR-A5, BR-A10 |
| **SocialLoginService** | 소셜(OIDC) 로그인 오케스트레이션. | OIDC 인가 시작, 콜백(CSRF 방어), 기존 계정 매핑 및 pre-hijacking 방어 | `start`, `callback` | FR-27, BR-A9 |

---

## U4 — Saved Searches & Library (검색 저장·라이브러리·이력)

DQ6에 따라 사용자向 CRUD는 동기 REST. 이력 쓰기만 이벤트 드리븐(SearchExecuted 구독), 읽기는 동기. **재실행(rerun)은 U2 직접 호출이 아니라 게이트웨이-프런티드 검색 계약을 통해 U6 횡단 계층을 다시 통과한다(아래 reconciliation 참조).**

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **SavedSearchController** | 검색 저장 save/list/delete/rerun 동기 REST 진입. | 라우트 매핑; **rerun을 게이트웨이-프런티드 검색 계약으로 위임(직접 U2 호출 아님)**; SEC-5 입력 검증 위임; U3 인증 컨텍스트 전파; NotFound/Forbidden 일반화(SEC-9) | `createSavedSearch`, `listSavedSearches`, `deleteSavedSearch`, `rerunSavedSearch` | FR-8, US-L1, SEC-8, SEC-5, DQ7, DQ6 |
| **LibraryController** | 라이브러리 add/list/remove 동기 REST 진입. | 라우트 매핑; arXiv ID·메타 스냅샷 DTO 검증(SEC-5); 인증 컨텍스트 전파·소유권 위임(SEC-8); 폰 카드 호환 직렬화(FR-4); 중복/미존재 멱등 매핑(QT-4) | `addLibraryItem`, `listLibrary`, `removeLibraryItem` | FR-9, US-L2, SEC-8, SEC-5, DQ7 |
| **SearchHistoryController** | 이력 list/rerun/clear 동기 REST 진입. | 라우트 매핑; **rerun을 게이트웨이-프런티드 검색 계약으로 위임**; 최근순 페이지네이션 검증; 인증 컨텍스트 전파·소유권 위임(SEC-8) | `listHistory`, `rerunHistoryEntry`, `clearHistory` | FR-10, US-L3, SEC-8, DQ7 |
| **SavedSearchService** | 검색 저장 도메인 오케스트레이션. | UserDataRepository owner-scoped CRUD(SEC-8); **rerun은 게이트웨이-프런티드 U2 검색 계약 동기 호출(검색 로직 U2 소관, U6 근거화·비용 후크 통과)**; 저장 정원/중복 정책 지점; 핵심 변경 감사 이벤트(SEC-13) | `save`, `list`, `delete`, `rerun` | FR-8, US-L1, SEC-8, SEC-13, DQ4 |
| **LibraryService** | 라이브러리 도메인 오케스트레이션. | owner-scoped CRUD(SEC-8); (userId, arXivId) 멱등(QT-4); 메타데이터 스냅샷 보존(U2/인덱스 가용성 비의존); 감사 이벤트(add/remove, SEC-13) | `addItem`, `list`, `removeItem` | FR-9, US-L2, SEC-8, SEC-13, DQ4 |
| **SearchHistoryService** | 이력 도메인 오케스트레이션(쓰기 비동기·읽기 동기). | `SearchExecuted` 이벤트 구독해 비동기 기록(NFR-P1 비차단); owner-scoped 최근순 조회(SEC-8); **rerun은 게이트웨이-프런티드 U2 검색 계약 동기 호출**; 이력 보존 정책 지점 | `recordSearch`, `list`, `rerun`, `clear` | FR-10, US-L3, SEC-8, DQ6, NFR-P1 |
| **UserDataRepository** | 3개 엔티티 영속화 포트(공유 어댑터 위). **SEC-8 데이터 계층 백스톱(심층 방어) — 독자적 authz 결정 아님.** | 모든 질의에 userId 강제(구조적 owner-scoping, SEC-8 백스톱, NFR-R1); CRUD·페이지네이션 원시 연산; at-rest 암호화·TLS는 공유 어댑터 위임(SEC-1); 타임아웃·재시도 공유 어댑터 위임(RES-9) | `insert`, `findByOwner`, `listByOwner`, `deleteByOwner` (하위: SavedSearchRepository/LibraryRepository/SearchHistoryRepository) | SEC-8, SEC-1, RES-9, DQ4 |
| **UserDataDTOAndValidation** | U4 DTO·SEC-5 검증·새니타이즈. | DTO 정의(SavedSearch/LibraryItem/HistoryEntry + 페이지 래퍼); query≤500자·arXiv ID 형식·페이지 파라미터 검증(SEC-5); 라운드트립 속성(QT-4); 내부↔외부 매핑(소유자 등 내부 필드 비노출, SEC-9) | `validateAndMap`, `toDTO`, `fromDTO` | SEC-5, FR-1, SEC-9, QT-4, **PBT-09**(DTO 라운드트립) |

---

## U5 — Mobile Web Frontend (SSR, 폰 우선)

DQ2 SSR 폰 우선 프런트엔드. 백엔드와 동기 REST(DQ7). 모든 데이터 입출력은 ApiClient 단일 진입점으로 캡슐화하며 인증/인가/레이트리밋/근거화는 백엔드 횡단 계층(U6) 책임.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **AppShell** | SSR 폰 우선 셸(루트 레이아웃·라우팅·전역 상태·네비게이션). | SSR 루트 레이아웃·라우트 트리; 폰 뷰포트 1급 강제(NFR-U1); 세션 컨텍스트 전파·보호 라우트 가드(SEC-8 클라이언트측 반영); 전역 로딩/에러 바운더리(FR-11, NFR-R1); **히어로 랜딩 골격(US-H1)** | `render`, `navigate`, `useSession` | NFR-U1, FR-11, SEC-8, NFR-R1, **US-H1** |
| **PhoneMockupFrame** | 데스크톱/태블릿에서 폰 목업 프레임 중앙 배치(리플로우 금지). | 뷰포트 분기(폰 풀블리드 / 데스크톱 목업, NFR-U2); SEC-4 카브아웃(frame-ancestors=self) 부합 마크업; 프레임 내부 폭을 폰 뷰포트로 고정 | `wrap`, `classifyViewport` | NFR-U2, SEC-4, C-3 |
| **SecurityHeaderPolicy** | SSR 응답 CSP·보안 헤더 주입(자기-프레이밍 예외 캡슐화). | frame-ancestors/X-Frame-Options self만 허용(SEC-4); script/connect/default-src 제한·SRI 유지(SEC-4); 응답마다 일관 부착 | `buildHeaders`, `buildCsp` | SEC-4 |
| **SearchScreen** | 자연어 질의 입력·동기 검색 트리거·결과/상태 표시. **프런트 히어로 표면 소유.** | 질의 입력(≤500자)·제출(FR-1, NFR-U1); 클라이언트 검증·인라인 메시지(SEC-5); 진행/결과/빈/실패/저하 전이(FR-11); 단일 요청/응답·로딩(NFR-P1); **첫 검색 매직 모먼트(US-H1)** | `submitQuery`, `renderState`, `validateInput` | FR-1, SEC-5, NFR-U1, NFR-P1, FR-11, **US-H1** |
| **ResultList** | 관련도순 상위 N건 세로 스크롤 목록. | 정렬 순서 보존·상위 N(≈20) 표시(FR-3); ResultCard 배치·0건/부분 상태 위임(FR-11); 저하 배너 상단 표시(US-D7) | `render` | FR-3, FR-11 |
| **ResultCard** | 단일 논문 폰 최적화 카드(가로 스크롤 없음). | 제목·저자·연도·arXiv ID·스니펫·관련도·링크 배치(FR-4, NFR-U1); 해소 가능 실재 arXiv ID/링크만·근거화 필드만 표시(FR-5 날조 미표시); 라이브러리 저장 진입점(FR-9) | `render`, `onSaveToLibrary` | FR-4, NFR-U1, FR-5, FR-9 |
| **AccountScreens** | 가입·로그인·로그아웃·세션 UI. | 폼(이메일+정책 비밀번호)·로그아웃(FR-7); 클라이언트 검증·비밀번호 비로깅(SEC-5, SEC-12); 레이트리밋/락아웃 비기술 메시지(SEC-11, SEC-12, FR-11); 세션 쿠키 기반 인증 상태 반영(SEC-12) | `renderSignup`, `renderLogin`, `submitSignup`, `submitLogin`, `logout` | FR-7, SEC-12, SEC-11, SEC-5, FR-11 |
| **LibraryHistoryScreens** | 저장 검색·라이브러리·이력 화면군(소유자 비공개). | 저장 검색 목록·재실행·삭제(FR-8); 라이브러리 목록·삭제(FR-9); 이력 목록·재실행(FR-10); 보호 라우트·미인증 시 로그인 유도·소유권 백엔드 위임(SEC-8) | `renderSavedSearches`, `renderLibrary`, `renderHistory`, `rerun`, `remove` | FR-8, FR-9, FR-10, SEC-8 |
| **StateView** | 빈/실패/저하/로딩 비기술 UX 공유 컴포넌트. | 빈/장애/저하/로딩 구분(FR-11, US-D6/D7); fail closed 일반화 에러·스택 트레이스 차단(SEC-15, NFR-R1); 기권/부분 상태 명시(FR-5, RES-11) | `renderEmpty`, `renderError`, `renderDegraded`, `renderLoading` | FR-11, NFR-R1, SEC-15, FR-5, **QT-3**(저하 UX 표면) |
| **ApiClient** | 백엔드 REST 동기 호출 어댑터(공유 레이어, 단일 진입점). | 타입드 동기 요청/응답(DQ6 동기 read, DQ7 REST); 세션 쿠키 전송·401/403/429/5xx를 UserFacingError로 정규화(SEC-8, SEC-11, SEC-15); 요청 타임아웃·단일 요청/응답 계약(NFR-P1, RES-9) | `search`, `signup`, `login`, `logout`, `listSavedSearches`, `saveSearch`, `deleteSavedSearch`, `listLibrary`, `addToLibrary`, `removeFromLibrary`, `listHistory` | FR-2, FR-7, FR-8, FR-9, FR-10, SEC-8, SEC-15, NFR-P1, RES-9 |

---

## U6 — Reliability & Operations (DQ5 전용 횡단 미들웨어/게이트웨이 + 운영)

DQ5 전용 횡단 계층의 정문 + 운영(관측성·비용 가드·헬스·AI 인시던트 탐지). 사용자 동기 READ 경로(DQ6 동기 REST)를 래핑하고 이벤트 백본(DQ6 비동기)을 생산·소비. 모듈형 모놀리스 내부 미들웨어 + 별도 운영/탐지 워커(DQ1).

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **ApiGatewayMiddleware** | 모든 사용자向 동기 REST가 통과하는 단일 진입 미들웨어. **응답 엣지에서 U2 라우트에 근거화 후크를 적용하는 단일 invocation site.** | 전처리 체인(보안 헤더→입력 검증→인증/세션→객체 인가→레이트 리밋→핸들러); 전역 에러 핸들러 fail-closed(SEC-9/SEC-15); 요청 ID 발급·관측성 제출(NFR-O1); **U2 응답 엣지 post-handler 단계로 GroundingEnforcementHook.enforce 적용(단일 게이트, FR-5)** | HTTP 미들웨어 체인. 아웃바운드: 가드들·CostGuard·GroundingEnforcementHook(lib), ObservabilityHub(sync) | SEC-4, SEC-5, SEC-8, SEC-9, SEC-11, SEC-12, SEC-15, NFR-O1, NFR-R1, FR-11, FR-5, US-D7 |
| **AuthnAuthzGuard** | 횡단 인증/인가 가드(미들웨어 이음새). **객체 소유권 결정을 U3.AuthorizationGuard에 위임(재구현 아님).** | 서버측 세션/토큰 검증·만료 거부(U3.SessionVerifier 위임, SEC-12); deny-by-default 라우트(SEC-8); **객체 단위 소유권은 U3.AuthorizationGuard에 위임(SEC-8) — 미들웨어는 강제 이음새**; 관리자 MFA 확인(SEC-12); 인가 결정 감사(SEC-14) | `authenticate`(U3 위임), `authorize`(U3.AuthorizationGuard 위임) | SEC-8, SEC-12, SEC-11, SEC-14, US-A2, US-L1, US-L2, US-L3 |
| **InputValidationGuard** | 타입·길이·형식 검증·새니타이즈 단일 강제(SEC-5). | 선언적 스키마 검증·인라인 에러(SEC-5, FR-1, US-D1); 인젝션 방지 새니타이즈·파라미터화 규약(SEC-5); 표준 클라이언트 에러 매핑(fail-closed, SEC-15) | `validate` | SEC-5, FR-1, FR-11, US-D1, SEC-15 |
| **RateLimiter** | 남용·비용 폭주 통제 레이트 리미팅(SEC-11). | 출처별 슬라이딩 윈도·429(SEC-11); 공개 가입 대량 가입 스로틀·봇 완화(SEC-11, US-A1); 한도 초과를 비용 폭발 보조 신호로 공급(RES-11(a)) | `checkLimit` | SEC-11, RES-11, US-A1, NFR-C1 |
| **CostGuardCircuitBreaker** | 월 비용 상한($300/월 제안) 이전 우아한 저하 + 준실시간 텔레메트리 + 서킷. | 준실시간 집계·임계 평가(80% 경보/100% 전 차단, NFR-C1); OPEN 시 'LLM 리랭킹 비활성→lexical 폴백' 지시(NFR-R2, RES-9); 지출 상태 동기 노출·회복 시 CLOSE; 인트라데이 급증을 CostExplosionDetector로(RES-11(a)) | `getBudgetState`, `recordSpend`, `evaluateCircuit` | NFR-C1, NFR-R2, RES-9, RES-11, SEC-11, US-R3, **QT-3**(저하 모드 검증 대상) |
| **GroundingEnforcementHook** | **FR-5/QT-1 근거화의 단일 권위 런타임 게이트(DQ5).** U2 응답 직전 미들웨어 post-handler 단계에서 호출. | 노출 논문이 인덱스 실재 레코드(arXiv ID/링크)에 매핑되는지 검증(FR-5, US-D5); AI 텍스트가 검색 근거에 한정되는지 검사·위반 차단/기권(FR-5, US-D6); 위반 시 **HallucinationDetector로 신호(RES-11(b))**; QT-1 평가셋 동일 후크 재사용 진입점(QT-1, US-R1) | `enforce`, `runEvalSet` | FR-5, QT-1, RES-11, NFR-R1, US-D5, US-D6, US-R1 |
| **ObservabilityHub** | 메트릭·로그·트레이스·감사 로그 단일 수집점(NFR-O1, RES-5, SEC-14). | 지연·에러율·처리량·근거화/검색 건강도·지출 메트릭·구조화 로그·트레이스(NFR-O1, RES-5, US-R4); PII/시크릿 차단(SEC-3)·추가 전용 감사 90일+(SEC-14/SEC-13); 대시보드·탐지기 공급; 임계 위반 경보 라우팅(RES-7) | `emitMetric`, `emitLog`, `startSpan`, `auditAppend` | NFR-O1, RES-5, RES-7, SEC-3, SEC-13, SEC-14, US-R4 |
| **HealthCheckService** | 얕은·깊은 헬스 체크(RES-6). | 얕은 체크 liveness/readiness(RES-6, US-R5); 깊은 체크 arXiv·LLM 게이트웨이·벡터 스토어 연결성(RES-6, US-R5); 비정상 시 라우팅 제외·건강도 메트릭(RES-6, RES-7); 합성 모니터링 프로브(RES-6) | `shallowCheck`, `deepCheck` | RES-6, RES-7, RES-9, US-R5 |
| **ReliabilityEvalProbe** *(신설 — QT-3 소유자)* | **QT-3 신뢰성/우아한 저하 인수 평가 진입점**(GroundingEnforcementHook.runEvalSet의 QT-1 대응물). | 정의된 업스트림 장애·빈 결과·강제 저하 경로의 동작 검증·보고(QT-3); 저하 모드(LLM off/벡터 스토어 장애/부분 결과) 시나리오 실행·결과 표면화; OP/팀이 소유 | `runReliabilityEvalSet`, `verifyDegradedMode` | **QT-3**, NFR-R1, NFR-R2, RES-9, US-R2 |
| **AiIncidentDetectorSuite** | RES-11 AI 인시던트 탐지 계층(별도 워커, DQ1). **세 탐지기를 1급 서브컴포넌트로 선언.** | (a) **CostExplosionDetector**: 지출·레이트 신호 급증 탐지(RES-11(a), US-R3); (b) **HallucinationDetector**: 근거화 위반·QT-1 결과 날조 패턴 탐지(RES-11(b), US-R1); (c) **PartialResultDetector**: 완결성/저하 마커·의존성 장애 탐지(RES-11(c), US-R2); 각 인시던트 분류·심각도 부여 후 IncidentEventPublisher로 방출 | `onTelemetryEvent`, `classify` (서브컴포넌트: CostExplosionDetector, HallucinationDetector, PartialResultDetector) | RES-11, NFR-O1, US-R1, US-R2, US-R3, US-R4, FR-11, NFR-R1, NFR-R2, **QT-3**(PartialResultDetector 저하 검증) |
| **IncidentEventPublisher** | 탐지 인시던트·경보를 이벤트 백본에 표준 스키마로 발행하는 어댑터. **U2/U6 인시던트 발행의 실재 단일 대상(팬텀 IncidentSignalPublisher 대체).** | typed 인시던트(class a/b/c·심각도·요청 ID 상관) 발행(RES-11); IR 라우팅·COE 컨텍스트 첨부(RES-11, US-R4); 발행 감사(SEC-14) | `publishIncident`, `publishAlert` | RES-11, RES-7, SEC-14, US-R4 |
| **OpsDashboardService** | OP 운영 대시보드 데이터 제공(NFR-O1, RES-5). | 집계 텔레메트리를 뷰 모델로(NFR-O1, US-R4); 세 인시던트 클래스 상태·경보 이력(RES-11, US-R4); 비용 상한 대비 지출(서킷 상태)·인제스천 건강도(RES-7) | `GET /ops/dashboard`, `GET /ops/incidents` (관리자 인가 SEC-8/MFA SEC-12) | NFR-O1, RES-5, RES-7, RES-11, SEC-12, US-R4 |
| **RealSearchGatewayAdapter** | U4 rerun(SearchGatewayPort) 요청을 U2 검색 처리로 중계하는 실제 어댑터. | `StubSearchGateway`를 대체하여 주입됨; 게이트웨이 파이프라인(비용/근거화 후크 등)의 강제 로직을 재사용·통과하도록 통합 위임 | `search` (SearchGatewayPort 구현) | INV-L2 |
## U10 — Mypage (사용자 마이페이지 도메인 모듈)

사용자 프로필 설정, 보안 제어(비밀번호/이메일 변경), 그리고 애플리케이션 내의 다양한 개인화 및 도메인 데이터 관리를 담당하는 모듈. 다른 모듈(U3 계정, U9 개인화 등)의 제어 UI를 통합 제공하며, U3/U9/U4의 API를 동기적으로 호출하여 상태를 조회 및 변경한다.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **MypageController** | 마이페이지 기능 동기 REST 진입점. | 라우트 매핑; 프로필 조회, 개인화 설정 변경, 데이터 내보내기/삭제 위임; 인증 컨텍스트 전파(SEC-8) | `GET /api/mypage/profile`, `PUT /api/mypage/settings`, `GET /api/mypage/export` | US-A5, US-P6, SEC-8 |
| **UserPreferencesService** | 개인 설정(개인화, UI 테마 등) 관리 오케스트레이션. | 사용자 설정 조회 및 변경; U9 개인화 선호도 갱신 위임; U3 연동 | `getPreferences`, `updatePreferences` | US-P6, SEC-8 |
| **DataExportService** | 사용자 데이터(이력, 저장 검색, 라이브러리) 내보내기. | GDPR 준수 데이터 내보내기(Data Portability); U4 등 도메인 데이터 조회 후 JSON/CSV 등 형식 변환 다운로드 제공 | `exportUserData` | FR-28, SEC-8 |

---

## U11 — Evidence Formation Agent (문헌탐색·근거형성 Agent, 재인셉션 Phase 4)

> DQ1=A 모듈형 모놀리스 내 API 모듈(+긴 분석용 비동기 잡 옵션). 로그인 필수 온디맨드 대화형 경로(Q7=A 멀티턴). U6 게이트웨이 단일 진입. LLM Agent가 Search·DocModel 도구를 자율 오케스트레이션해 EvidenceItem(statement + supporting[] + conflicting[])을 추출·비교한다. 근거 없으면 FR-5 기권(날조 금지). EvidenceFormationPort(shared/ports §4) 단일 구현자(D5) — U12 연구아이디어 Agent(미래)가 소비.

| 컴포넌트 | 목적 | 핵심 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **EvidenceChatController** | 세션 CRUD + 채팅 턴 동기 REST 진입점(SSE 스트리밍). | 세션 생성/목록/삭제·채팅 메시지 수신·스트리밍 응답(FR-36); 인증 컨텍스트 전파(SEC-8); fail-closed 에러(SEC-15) | `POST /api/evidence/sessions`, `GET /api/evidence/sessions`, `DELETE /api/evidence/sessions/:id`, `POST /api/evidence/sessions/:id/messages` (SSE), `GET /api/evidence/sessions/:id` | FR-36, FR-38, SEC-8, SEC-15, US-EV1, US-EV7, US-EV8 |
| **EvidenceAgentOrchestrator** | LLM-driven Agent 코어 — 도구 자율 오케스트레이션·멀티턴 맥락 유지·스트리밍 출력. | 요청/후속 질문 해석; EvidencePaperSearchTool·EvidenceDocModelTool을 자율 순서로 호출; EvidenceExtractor로 명제 추출; EvidenceComparisonAssembler로 결과 조립; 근거 없으면 EvidenceAbstainResult 반환(FR-5); SSE 청크 스트리밍(NFR-P6) | `run(request, ctx) -> AsyncStream<EvidenceChunk>`, `continueSession(sessionId, followUp, ctx) -> AsyncStream<EvidenceChunk>` | FR-36, FR-37, FR-5, NFR-P6, C-2, Q7=A, US-EV2, US-EV5 |
| **EvidencePaperSearchTool** | Agent가 호출하는 논문 검색 도구 어댑터. | auto/mixed scope 시 주제 쿼리로 코퍼스 검색(공유 벡터 스토어); explicit scope 시 paper_ids 직접 조회; IndexRecord 목록 반환 | `searchPapers(query, scope, paperIds?) -> IndexRecord[]` | FR-37, Q4=A, US-EV2, US-EV3 |
| **EvidenceDocModelTool** | Agent가 호출하는 DocModel 블록 읽기 도구 어댑터. | paperId+recordRef로 오브젝트 스토리지에서 DocModel 블록 조회; anchor 기반 섹션 슬라이싱 | `fetchBlocks(paperId, recordRef, anchor?) -> DocModelBlock[]` | FR-37, FR-18, US-EV2 |
| **EvidenceExtractor** | DocModel 블록에서 EvidenceItem 추출(C-2 추출 전용). | 논문 본문에서 핵심 주장·방법·결과 수치·한계 명제 추출(Q1=A); SourceRef(paperId·recordRef·anchor·quote) 구성; 생성 산문 금지(C-2, FR-5); confidence 제외(Q3=B) | `extractItems(blocks, paperId, recordRef) -> EvidenceItem[]` | FR-37, FR-5, C-2, QT-8, US-EV2 |
| **EvidenceComparisonAssembler** | EvidenceItem 목록을 비교표 + 쟁점 오버레이로 조립(Q2=A). | 지지/상충 출처 기반 쟁점 오버레이 계산; coverage 메타(사용 논문 수·쿼리) 조립; EvidenceResult(state=ok) 반환 | `assemble(items, coverage) -> EvidenceResult`, `buildConflictOverlay(items) -> ConflictMatrix` | FR-37, Q2=A, US-EV2 |
| **AttachmentDocModelAdapter** | 사용자 첨부 문서를 doc-model 파이프라인으로 일시 처리(Q6=A). | 첨부 핸들 수신 → DocModel 블록 추출(U1 파이프라인 재사용, transient); 형식·크기 검증; 원시 파일 미저장 | `processAttachment(handle) -> DocModelBlock[]` | FR-37, FR-18, Q6=A, US-EV4 |
| **EvidenceSessionRepository** | 근거형성 세션·결과 owner-scoped 영속(SEC-8). | 세션 생성/조회/목록/턴 추가/삭제/초기화; owner 키 강제(SEC-8 백스톱); 타 소유자 비가시 | `createSession`, `loadSession`, `listSessions`, `appendTurn`, `deleteSession`, `resetAllSessions` | FR-38, SEC-8, US-EV7, US-EV8 |
| **EvidenceFormationService** | **EvidenceFormationPort(D5) 단일 구현자** — U12 연구아이디어 Agent에 Tool로 노출. | `form_evidence(request, ctx)`를 EvidenceAgentOrchestrator로 라우팅; 긴 분석은 비동기 잡 오프로드(NFR-P6, Q9=A); EvidenceResult \| EvidenceAbstainResult 반환; 재구현 금지(U12 only via port) | `form_evidence(request, ctx) -> EvidenceResult \| EvidenceAbstainResult` (EvidenceFormationPort 구현) | D5, NFR-P6, FR-37, US-EV9 |

---

## 2026-09-19 F01-F13 교정 컴포넌트 개정

> **SUPERSEDED - 2026-09-19 UQRF1=B**: 아래 기존-package component placement는 이력이다. REM-1~REM-4 deployable-service 경계는 재개된 Application Design에서 다시 정의한다.
>
> RQ1=A에 따라 아래 항목은 기존 도메인/플랫폼 패키지 안에서 소유한다. F01-F13 전용 runtime remediation 서비스나 새 deployable product unit은 만들지 않는다. 표의 컴포넌트는 고수준 경계이며 상세 상태 전이, 스키마, timeout, retry 수치는 Construction 단계에서 확정한다.

### REM-1 - Platform and Contract Integrity

| 컴포넌트 | 소유 경계 | 목적과 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **OrderedMigrationRegistry** | `backend.migrations` 공유 기반 | startup과 CLI가 소비하는 명시적 ordered migration SSOT. 기존 ledger ID를 보존하고 duplicate ID/path, missing file, 미등록 backend SQL을 DB 연결 전에 거부한다. | `entries`, `validate`, `identitySet` | F08, NFR-M1, RESILIENCY-04, PBT-04/05 |
| **OfflineContractBindingGenerator** | `shared` schema tooling + frontend generated bindings | 모든 local schema를 자동 발견하고 `$id`/`$ref`를 network 없이 해소한다. 전체 성공 후에만 build-consumed Python/TypeScript 산출물을 원자 교체하며 drift check와 실패 exit를 소유한다. | `discoverSchemas`, `resolveLocalRefs`, `generate`, `checkDrift` | F13, SEC-5/13, NFR-M1, PBT-02 |
| **RuntimeSupplyChainVerifier** | 각 deploy unit의 lock/build/CI + `ops/server` preflight | production runtime version, frozen lock closure, image digest, critical/high advisory, SBOM을 검증한다. 예외는 advisory ID, reachability 근거, owner, expiry가 있는 명시 record만 허용한다. | `verifyRuntime`, `auditLocks`, `verifyImagePins`, `emitSbom` | F06, SEC-10, RESILIENCY-03/04 |

### REM-2 - Private Content and Generation

| 컴포넌트 | 소유 경계 | 목적과 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **PublicPaperNamespacePolicy** | summarization API/domain | public summary, DocModel, asset 경로에서 `userdoc:`를 존재 여부와 무관하게 동일한 일반화 거부로 차단한다. raw object reader는 owner-neutral로 유지하고 public wiring에 이 정책을 적용한다. | `requirePublicPaperRef`, `isPublicPaperRef` | F01, SEC-8/9/15 |
| **UserDocModelCoordinator** *(기존 확장)* | `backend.modules.user_docmodel` | authenticated owner context로만 `UserDocModelRef`를 구성/검증하고 evidence/novelty 등 context-bound private 경로에 DocModel을 제공한다. 범용 private DocModel endpoint는 제공하지 않는다. | `validateOwnedRef`, `loadOwnedDocModel`, `loadOwnedAsset` | F01, F07, FR-18/38, SEC-8 |
| **CanonicalSummarySourceResolver** | summarization domain | server-verified metadata/DocModel에서 canonical paper ID, revision, source kind, content digest를 결정한다. client abstract가 shared artifact 또는 cache identity를 결정하지 못하게 한다. | `resolveCanonicalSource`, `sourceIdentity` | F02, FR-5/13, SEC-13, QT-5 |
| **SummaryGenerationJobRegistry** | summarization service + persistence port | canonical source/cache identity에 결속한 durable generation marker를 소유한다. enqueue/running/succeeded/failed/terminal 상태와 attempt를 기록하며 기존 `pending` repeat-request 계약을 유지한다. | `ensureJob`, `loadJob`, `recordEnqueue`, `recordRunning`, `recordTerminal` | F05, NFR-P2/R2, RESILIENCY-10, PBT-04/06 |
| **AuthenticatedPaperAssetController** | summarization API + asset adapter | authenticated public-paper asset 요청에서 namespace, license, manifest를 검증하고 object key를 노출하지 않은 채 safe metadata와 byte stream을 반환한다. private asset은 owner context 경로에만 위임한다. | `streamAsset` | F07, SEC-4/8/9 |
| **SameOriginAssetProxy** | Next.js BFF | backend asset stream을 same-origin `/bff/...` 응답으로 중계하고 허용된 content/cache header만 전달한다. 일반 JSON transport와 분리된 binary path다. | `proxyAssetStream` | F07, SEC-4/8/9, RESILIENCY-10 |

### REM-3 - Owner Lifecycle and Edge Trust

| 컴포넌트 | 소유 경계 | 목적과 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **OwnerPurgeRegistry** | accounts purge orchestration의 중앙 registry | 모든 owner-scoped SQL table, private object prefix, derived asset, cache key enumerator를 명시적으로 등록한다. 누락/중복/미해결 owner binding은 purge 시작 전에 거부한다. | `registeredTargets`, `validateCoverage`, `inventoryOwner` | F04, FR-28/38, SEC-8, PBT-05 |
| **PurgeManifestRepository** | accounts persistence | SQL 삭제 전에 생성한 immutable owner purge manifest, manifest hash, 단계 상태, attempt를 durable하게 저장한다. 동일 manifest를 사용한 resume를 보장한다. | `createManifest`, `loadManifest`, `advanceStage`, `markFailed`, `markComplete` | F04, RESILIENCY-02/04/12, PBT-02/04/06 |
| **OwnerPurgeCoordinator** *(AccountDeletionService 확장)* | accounts service/worker | manifest 생성 후 object/cache 정리, owner SQL/credential transaction, zero-residue 검증을 단계별 실행하고 실패 위치에서 재개한다. 다른 owner 보존을 명시적 완료 조건으로 둔다. | `planPurge`, `resumePurge`, `verifyResidue` | F04, FR-28/38, SEC-8, RESILIENCY-14 |
| **DigestUnsubscribeController** | trends API | 정확한 public route 하나에서 signed token을 검증한 뒤 owner settings에 조건부 unsubscribe를 적용한다. 인증 우회 범위는 이 exact path로 한정한다. | `unsubscribe` | F09, FR-47, SEC-5/8/12 |
| **DigestLinkTokenVerifier** | trends domain | versioned issued-at token의 signature, age, settings version을 검증하며 production signing key 부재 시 fail closed한다. | `issue`, `verify` | F09, SEC-5/13/15 |
| **EdgeClientIdentityForwarder** | Next.js BFF | Cloudflare tunnel ingress의 단일 client IP를 검증/정규화하고 브라우저 제공 internal header를 제거한 뒤 JSON, PDF, SSE에 같은 private header를 설정한다. | `trustedClientHeaders` | F10, SEC-2/11 |
| **TrustedClientIdentityResolver** | FastAPI ingress middleware | 실제 socket peer가 loopback인 경우에만 BFF private header를 신뢰하고 canonical identity를 request context에 한 번 기록한다. gateway와 accounts limiter가 같은 값을 소비한다. | `resolveClientIdentity`, `attachRequestIdentity` | F10, SEC-2/11/15 |

### REM-4 - Corpus and Search Integrity

| 컴포넌트 | 소유 경계 | 목적과 책임 | 인터페이스 | Trace |
|---|---|---|---|---|
| **ProductionSeedGuard** | ingestion bootstrap/tooling | fixture/seed 경로를 explicit non-production mode로 제한하고 production bootstrap에서 fixture import/실행을 거부한다. | `assertSeedAllowed` | F03, SEC-9/15 |
| **CorpusIntegrityAuditor** | ingestion standalone tooling | active alias/backing generation을 read-only 검사해 fixture fingerprints, source metadata, 최근 365일 범위 completeness, generation identity와 report hash를 기록한다. | `auditGeneration`, `writeReport` | F03, FR-2/5/6, QT-1/9 |
| **CorpusRepairCoordinator** | ingestion standalone tooling | backup/restore 확인과 exact dry-run manifest를 전제로 fixture-free candidate generation, 검증, atomic alias cutover, rollback을 오케스트레이션한다. readiness/startup에서는 호출되지 않는다. | `planRepair`, `applyApprovedRepair`, `rollbackRepair` | F03, RESILIENCY-02/04/12/14 |
| **CorpusReadinessProvider** | ops/backend health | 최근 immutable audit report만 읽어 stale, generation mismatch, fixture, completeness 상태를 readiness reason으로 노출한다. OpenSearch를 직접 수정하지 않는다. | `readCorpusReadiness` | F03, RESILIENCY-05/06/07 |
| **ResultAssembler** *(U2 기존 확장)* | discovery domain | 0건 결과에서도 known degradation mode와 provenance를 보존해 normal no-match와 degraded-empty를 다른 response union으로 조립한다. | `assemble`, `assembleEmpty` | F11, FR-11, NFR-R1/R2, SEC-15 |
| **SearchStateClassifier** *(frontend 기존 분류 경계 확장)* | frontend API/view state | `meta.degraded`를 result count보다 먼저 판정해 normal empty와 degraded empty를 구분하고 복구 가능한 상태를 렌더한다. | `classifySearchResponse` | F11, FR-11, NFR-R1/R2 |
| **RelevanceFloorEvaluator** | discovery eval tooling | source-verified generation과 labeled in/out-of-scope 평가셋에서 candidate floor별 false-abstain/false-pass를 generation-bound report로 산출한다. | `evaluateFloors`, `writeCalibrationReport` | F12, FR-5/11, QT-1 |
| **RelevanceFloorPolicy** | discovery read path | current generation/model과 일치하는 승인된 floor만 사용하며 malformed/zero/stale 정책은 readiness/configuration failure로 처리한다. shadow 결과를 거친 뒤에만 enforce한다. | `loadPolicy`, `classifyBestMatch` | F12, FR-5/11, QT-1, SEC-15 |

---

## 2026-09-19 Deployable Services and Public Jobs

**상태**: DAD1=A 승인 완료 (2026-09-19).
**우선순위**: 이 절은 F01~F13/FR-52 범위의 현재 승인 설계이며 기존 RQ1=A, public job 없음, startup mutation 및 repeat-request-only 전제를 대체한다. 상세 계약은 `component-methods.md`의 동명 절을 따른다.

### 배포 경계와 중요도

| Deployable | 역할과 독립 배포 단위 | 중요도 / 중단 영향 | 영속 state 및 권한 경계 |
|---|---|---|---|
| REM-1 Platform Integrity | read-only evidence daemon + 명시적 CLI/one-shot runner를 동일 versioned artifact의 별도 launchd 역할로 제공 | High; daemon 중단은 운영 evidence 관측 저하, runner/검증 실패는 build/deploy 차단 | compatibility/migration/audit/SBOM evidence. daemon은 read-only, runner만 목적별 mutation 권한 |
| REM-2 Private Content | content admission/관측 daemon + content/status-query workers | Critical; private 열람/요약/번역/결과 전달이 실패 또는 대기 | REM-2 operation/outbox/event/result 및 U7 생성 artifact. U1 source와 U11/U12 context는 승인된 read 계약만 소비 |
| REM-3 Lifecycle and Edge Trust | opt-out admission/관측 및 policy daemon + purge/consent/status workers | Critical; 해지 접수/파기 진행 중단. U3 즉시 비활성화와 ingress 보호는 계속 직접 집행 | REM-3 operation, suppression intent, purge manifest/receipt, versioned edge policy. 다른 domain의 일반 데이터 수정 권한 없음 |
| REM-4 Corpus Integrity | report/운영 admission daemon + audit/calibration workers + 별도 privileged repair runner | High; evidence 갱신 중단으로 stale readiness/정책 차단. 정상 검색은 유효 evidence 범위에서 U2가 수행 | generation-bound audit/calibration/repair evidence. daemon/auditor는 corpus read-only, 명시적 repair 역할만 U1 mutation port 사용 |

네 service는 각각 artifact/version/credential/health/재시작 경계를 가진다. daemon과 worker의 분리는 추가 REM domain을 뜻하지 않는다. 데이터 저장소와 Ollama는 현재 OrbStack/host capability를 사용한다. 가용성은 NFR-A1의 best-effort 단일 host이며 persistent state는 RES-2의 RPO ≤24h/수 시간 RTO 목표에 포함한다. port 번호, OS 계정, role별 자원 상한은 Infrastructure/NFR 설계에서 확정한다.

### 컴포넌트 카탈로그

ID는 아래 네 문서와 통합 개요에서 공통으로 사용한다. 공통 kernel/port는 라이브러리와 service-local instance이며 별도 다섯 번째 service가 아니다.

| ID / 컴포넌트 | Runtime 및 canonical owner | 책임 / 인터페이스 | 주요 trace |
|---|---|---|---|
| EDGE / GatewayJobBridge | 기존 BFF + FastAPI; U5/U6/U3 | trusted edge identity, session/token 검증, 입력/사용량 제한, 고정 route-to-service adapter, 짧은 audience-bound delegation, same-origin JSON/event/binary relay. `admitRequest`, `relayObservation`, `relayResult` | F07/F10, RJ-AC01/05/08/11 |
| UI / JobExperienceController | 기존 frontend; U5 및 관련 U13 화면 | 접수와 완료, 연결 단절과 실패를 분리; 중복/역순 event와 결과 만료 처리. 준비된 결과 전달을 새 업무로 제출하지 않음. `submit`, `observe`, `applyEvent`, `openResult` | US-RJ1~3, US-S5, RJ-AC03/04 |
| AUTH / AuthorityProjectionPort | U3 및 resource domain 소유 계약; 각 consumer에 read-only adapter | 현재 account/session/deletion epoch와 resource binding을 검증해 immutable snapshot/짧은 실행 허가 제공. event-cache만으로 허가하지 않음. `currentAuthority`, `authorizeExecution`, `authorizeDelivery` | F01/F04, RJ-AC05/09/11 |
| RK / DurableOperationKernel | REM-2/3/4 각각 독립 instance; shared 계약 + 각 service operational owner | operation/outbox 원자 접수, dedupe/lease/reconcile, 순서 있는 safe event 및 terminal/result publication. `accept`, `claim`, `publish`, `reconcile`, `observeStatus` | FR-52, NFR-R4, RJ-AC01/02/04/06/12 |
| DELIVERY / AuthorizedResultDelivery | REM-2/3/4 각 daemon; 해당 operation owner | 현재 권한으로 published event/result만 전달; live 업무 조회를 새로 실행하지 않음. cursor는 job/scope/version에 결속. `subscribe`, `openPublishedResult`, `openAsset` | F07, RJ-AC04/05/08 |
| EXEC / FencedDomainExecutionPort | 기존 domain 소유의 worker/maintenance adapter; 각 data owner host | 일반 write와 privileged purge/repair를 목적별 구분. owner epoch/lease를 실제 I/O 및 publication 경계에서 집행하고 quiescence/삭제 receipt 제공. `beginWrite`, `quiesce`, `executeMaintenance`, `verifyResidue` | F04, RJ-AC09/12 |
| R1C / PlatformEvidenceController | REM-1 read-only daemon; platform coordination | version/schema compatibility, migration/lock/SBOM evidence 조회. startup은 registry/evidence 검증만 수행. `readEvidence`, `checkCompatibility` | F06/F08/F13 |
| R1R / PlatformIntegrityRunner | REM-1 privileged one-shot/build role; domain별 정의는 기존 owner | ordered registry 검증/명시적 apply, 모든 local ref offline binding 생성, drift/audit/pin/SBOM 및 artifact evidence publication. `verifyRegistry`, `runApproved`, `generateBindings`, `verifySupplyChain` | F06/F08/F13 |
| R2A / ContentAdmissionService | REM-2 daemon; U7/user_docmodel 및 context domain 계약 | public namespace/owner context와 command allowlist 검증, caller intent 접수. canonical source는 server가 해결하며 client 본문은 shared source가 아님. `acceptPublic`, `acceptPrivate`, `acceptStatusQuery` | F01/F02/F05, RJ-AC01/02/05 |
| R2W / ContentExecutionWorker | REM-2 worker; U7 business library + U1 source ports | fresh authority -> canonical source/version/digest -> cache 재사용 또는 bounded 생성 -> fenced publication. U1 build 필요 시 durable 내부 command/receipt 사용. `executeContent`, `executeStatusQuery` | F02/F05/F07, RJ-AC06/07/08/12 |
| R3C / OptOutAdmissionService | REM-3 daemon/worker; U15 token/consent 규칙 | token 검증 후 suppression intent + operation/outbox를 같은 접수 단위로 기록. 모든 digest sender와 공유하는 send barrier를 통해 즉시 차단. canonical settings 반영은 U15 executor에 위임. `acceptOptOut`, `issueObserverGrant`, `recordConsentReceipt` | F09, RJ-AC10 |
| R3P / PurgeSagaCoordinator | REM-3 worker; U3 lifecycle + 각 domain target specs | coverage registry, owner quiescence, immutable manifest, purpose-bound domain command/receipt, 재개/zero-residue 검증 및 control-data 정리. `startPurge`, `resumePurge`, `finalizePurge` | F04, RJ-AC09/11/12 |
| R3E / EdgePolicyPublisher | REM-3 policy daemon; U5/U6/U3가 enforcement 소비 | versioned trust/normalization 정책과 evidence 배포. BFF header overwrite 및 raw peer 검증, gateway/accounts limiter의 한 identity는 로컬 강제. `publishEdgePolicy`, `validateEdgePolicy` | F10, RJ-AC11 |
| R4A / CorpusEvidenceService | REM-4 daemon/worker; U1/U2 규칙 | production seed fence, generation/source/fixture/completeness audit, eval/calibration 및 검증 report 발행. `acceptAudit`, `acceptCalibration`, `readReport` | F03/F12 |
| R4R / CorpusRepairRunner | REM-4 privileged runner; U1 mutation port | verified backup/restore와 exact manifest/승인에 묶인 targeted repair. full rebuild/alias 변경은 별도 승인. `planRepair`, `runApprovedRepair` | F03, RES-2/4/12 |
| SEARCH / SearchIntegrityConsumers | 기존 U2 assembler/정책 + U5 classifier | current generation/model/freshness가 맞는 report만 집행; degraded-empty/provenance와 no-match 보존. `loadVerifiedPolicy`, `assembleOutcome`, `classifyOutcome` | F11/F12 |
| OBS / ServiceHealthTelemetry | 모든 entry point; U6 공통 계약 | shallow/deep/compatibility health, 단계별 metrics와 trace, redacted structured log/감사, backlog/backup/권한 경보. health는 queue에서 실행하지 않음. `health`, `readiness`, `recordSignal` | US-R4/5, RJ-AC12 |

### 데이터 및 writer 배치

공유 물리 store는 공유 admin credential을 뜻하지 않는다. 아래 ordinary writer는 logical service/owner 경계이며, 같은 service의 daemon/worker는 그 경계 안에서 transaction/lease로 조정한다. privileged maintenance는 domain이 구현한 목적 한정 adapter만 수행한다.

| 데이터 | Canonical business owner | Ordinary writer / 읽기 계약 |
|---|---|---|
| 계정/credential/session, lifecycle/deletion epoch | U3 | 기존 accounts runtime. REM은 AUTH의 versioned current projection을 read-only 소비; 계정 삭제 직접 제어는 U3에 유지 |
| evidence/novelty 첨부 context, 업로드 원본 참조 | U11/U12 | 기존 context runtime. REM-2는 context-bound projection과 허용된 immutable source만 읽음 |
| public/private DocModel 및 source asset/manifest | U1 | 지정된 ingestion consumer. REM-2는 source read/build command 계약 소비; public/private namespace 분리 |
| 요약/번역 canonical artifact/cache | U7 | 전환된 namespace/version은 REM-2-hosted U7 worker. legacy worker는 같은 key space를 동시에 쓰지 않음 |
| REM-2 operation/outbox/event/result refs | REM-2 operational owner, domain payload는 원 domain | REM-2. caller job은 공유 canonical artifact와 별도 권한/metadata 경계 |
| 내부 CommandProjection 및 recipient inbox/outbox copies | payload 의미는 원 domain, transport state는 sender/recipient owner | immutable view는 sender, 자기 inbox/receipt는 recipient만 기록. recipient/purpose/parent/run fence와 owner purge 분류 적용 |
| digest settings/consent version | U15 | 기존 U15 runtime/동일 owner의 executor. REM-3는 versioned projection과 목적 한정 command로 연계 |
| opt-out suppression intent, observer scope, REM-3 jobs/manifests/receipts | REM-3 operational owner; 의미는 U15/U3 | REM-3. suppression은 설정과 별도 veto이며 U15 sender는 동기 barrier를 반드시 소비 |
| 각 domain의 owner data | 기존 U1~U16 해당 domain | 기존 writer. domain-owned EXEC만 manifest-bound privileged delete 수행; REM-3가 임의 SQL/object 삭제 권한을 획득하지 않음 |
| corpus records/generation/alias | U1 | ingestion writer. repair runner는 승인된 fenced U1 mutation 계약으로만 변경 |
| corpus audit/calibration/repair report | REM-4 operational owner; U1/U2 검증 규칙 | REM-4. U2/U6는 immutable report + 현재 generation head를 검증해 소비 |
| registry/schema/lock 정의 및 platform evidence | 기존 domain/shared owner / REM-1 evidence owner | source 정의는 원 owner, evidence는 REM-1 runner. daemon은 read-only |

**Current projection**은 domain이 발행한 immutable revision과 현재 revision/철회 상태를 일관되게 읽는 전용 계약이다. consumer에 일반 업무 table 쓰기 권한을 주지 않으며, 오래된 event snapshot만으로 권한을 승인하지 않는다. 실제 projection schema/transaction primitive는 Functional/NFR Design에서 확정한다.

공개 canonical artifact와 owner별 파생 variant를 domain 정책으로 구분한다. 개인 glossary/선호가 결과에 영향을 주는 variant는 owner scope를 identity/저장/인가/purge에 포함한다. client의 visibility 값으로 공유 가능성을 결정하지 않는다. 공유 public source/artifact는 한 caller의 job 삭제 때문에 다른 caller에게서 제거하지 않는다.

### 직접 제어 경계

- U3의 계정 비활성화/session 무효화는 기존 직접 경로다. owner epoch를 먼저 닫고 durable lifecycle 신호를 기록해 REM-3의 유예 파기로 연결한다. 큐가 멈춰도 private admission/쓰기/전달이 새로 허용되지 않는다.
- R3C의 성공 접수는 suppression이 durable해진 시점과 결속된다. U15 sender의 provider handoff는 같은 consent barrier에 참여하며, 수락 이후 새 발송을 시작할 수 없다. fence 확인이 불가능하면 성공 접수나 발송을 추정하지 않는다.
- EXEC는 남아 있는 write를 증명 가능하게 종료/차단한 뒤 quiescence receipt를 준다. lease 만료만으로 외부 object I/O가 끝났다고 간주하지 않는다. REM-3는 미확정 write가 있으면 purge 완료를 선언하지 않는다.
- AUTH/RK/DELIVERY의 일반 user grant와 operator/system maintenance grant를 구분한다. 비활성화된 owner의 일반 작업은 거부하되 적법한 목적 한정 purge를 진행할 수 있다.
