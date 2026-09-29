# services.md — 서비스 정의·오케스트레이션 (Application Design)

> **현재 승인 설계**: 하단 `2026-09-19 Deployable Services and Public Jobs`의 durable service orchestration이 DAD1=A로 승인됐다. 이전 superseded in-process 흐름은 이력이다.

> 각 서비스의 책임 + 오케스트레이션을 **동기 읽기(sync)** vs **이벤트 백본(event)** 으로 구분 명시한다(DQ6 재조정).
> 동기 경로: 사용자向 디스커버리 READ(NFR-P1 P50<3s), 계정, 라이브러리 CRUD.
> 이벤트 백본: 인제스천, 이력 쓰기, 비용/인시던트 탐지, 관측성 팬아웃.

## 비평 반영 요약 (이 문서 관련)
- **[blocking] 근거화 단일 invocation site**: 응답 엣지 근거화 게이트는 **U6.GatewayPipelineService의 U2 라우트 post-handler 단계 한 곳**에서만 실행된다. U2.SearchOrchestrationService는 더 이상 독자적으로 enforce를 호출하지 않고 `GroundingAdapter`로 후크 입력/출력을 정형화만 한다.
- **[blocking] SearchExecuted 생산자**: U2.SearchOrchestrationService가 성공 검색 후 `publishSearchExecuted`로 이벤트 백본에 발행(FR-10 이력 쓰기 생산자 — 비차단, P50<3s 경로 밖).
- **[major] rerun 게이트웨이 재진입**: U4 SavedSearchService/SearchHistoryService의 rerun은 게이트웨이-프런티드 검색 계약을 통해 U6 횡단 계층(근거화·비용·관측성)을 다시 통과한다.
- **[major] QT-3 평가 서비스**: U6.HealthMonitoringService가 ReliabilityEvalProbe를 통해 QT-3 신뢰성/저하 평가셋을 소유.

---

## U1 — Corpus Ingestion 서비스 (전부 이벤트/스케줄 백본, 사용자 동기 경로 아님)

### IngestionPipelineService
- **책임**: 멀티소스 논문 후보를 fetch→license/fulltext→source-priority dedup→eager DocModel→DocModel Block chunk→embed→index generation/S3 저장→watermark까지 끝에서 끝으로 처리하는 핵심 오케스트레이터. **FR-6 파이프라인 본체이자 U1 Corpus phase-1 빌드·정기 인제스천의 실현 주체.**
- **오케스트레이션 (워커 내부 비동기 흐름)**: `CorpusSourceAdapterSet.fetchMetadataPage/fetchFullTextCandidate`(arXiv HTML 우선/PDF 폴백, Semantic Scholar/OpenAlex PDF 후보) → `FullTextExtractionProcessor.validateLicense/extractFullText`(PDF는 transient GROBID, 원시 PDF 미저장) → `SourcePriorityDeduplicationGuard.deduplicate/canonicalize` → `DocModelBuildCoordinator.buildDocModel/storeDocModel` → `DocModelBlockChunker.chunkDocModel` → `EmbeddingGatewayAdapter.embedBatch`(공유 VectorSpec 공간) → `CorpusIndexWriter.prepareGeneration/upsert` → `CorpusRefreshScheduler.advanceWatermark`. 모든 단계 오류는 IngestionResilienceService로 위임(재시도/DLQ/경보). **단계 간은 워커 내부 비동기(DQ6 비동기 백본), 사용자 동기 경로와 완전 분리.**
- **Trace**: FR-6, FR-18, US-I1, NFR-R1, NFR-C1, QT-9

### RefreshOrchestrationService
- **책임**: source별 스케줄 갱신, phase-1 seed/backfill, DocModel/index 재생성을 통합 관리한다. **US-I2 최신성 갱신·US-I1 Corpus 빌드·RES-2 재구축 런북의 제어 평면.**
- **오케스트레이션 (event + schedule)**: `CorpusRefreshScheduler.onSchedule`이 arXiv/Semantic Scholar/OpenAlex source별 IngestionJob을 생성 → 각 source의 `sourceWatermark` 이후 페이지를 열거 → IngestionPipelineService에 분배(배치/동시성은 RES-8 쿼터 준수). `triggerBackfill`은 최근 AI/ML 1년 phase-1 Corpus를 비용 상한 안에서 진행하고, `triggerRebuild`는 DocModel/parser/index version 변경 시 재생성한다. 잡 단위 실패율·진행도·watermark 지연을 관측성 노출.
- **Trace**: FR-6, FR-18, US-I1, US-I2, RES-2, RES-7, RES-8, QT-9

### IngestionResilienceService
- **책임**: source/GROBID/DocModel/embedding/index 단계의 타임아웃·재시도/백오프·서킷·DLQ·쿼터와 실패·갱신 건강도 신호 발행. **US-I3 복원력 + US-I2 실패 경보의 횡단 서비스.**
- **오케스트레이션 (event)**: `IngestFailureHandler.classify` 분류 → 재시도 가능 시 `scheduleRetry`(source 쿼터/GROBID 처리량/임베딩 한도 인지) → 소진/영구 시 `sendToDLQ` → `emitFailureSignal`로 구조화 로그·경보 발행(운영 U6 라우팅, RES-7). CorpusSourceAdapterSet/FullTextExtractionProcessor/DocModelBuildCoordinator/EmbeddingGatewayAdapter/CorpusIndexWriter 외부 호출에 타임아웃·서킷 주입(RES-9). `(paperId, version)` 불일치나 Block anchor 결함은 cutover 전 차단한다(QT-9).
- **Trace**: FR-6, FR-18, US-I3, RES-7, RES-8, RES-9, NFR-R1, QT-9

---

## U2 — Discovery 서비스 (동기 읽기 경로의 주체)

### SearchOrchestrationService
- **책임**: U2 동기 읽기 경로 도메인 오케스트레이터. 질의 이해/확장 → 하이브리드 검색 → 랭킹 → **근거화 어댑팅(U6 후크 위임)** → 결과 조립의 단일 요청→응답 파이프라인을 순차 조정. 횡단 계층(U6)이 주입한 degradation/cost-circuit 신호를 각 단계 전파. **성공 응답 후 SearchExecuted 이벤트를 발행(FR-10 이력 생산자).** NFR-P1(P50<3s) 동기 경로의 주체.
- **오케스트레이션 (sync 순차)**: `QueryValidator.normalize` → `QueryUnderstandingExpander.expand`(공유 VectorSpec) → `HybridRetriever.retrieve` → `RelevanceRanker.rank` → `GroundingAdapter.toGroundingInput`(U6 게이트웨이 post-handler 단계가 `GroundingEnforcementHook.enforce` 적용) → `GroundingAdapter.mapDecision` → `ResultAssembler.assemble`. 각 단계 명시 타임아웃/폴백(RES-9); 저하 신호 시 LLM 확장·리랭킹 건너뛰고 lexical 경로(NFR-C1, US-R2/R3).
- **근거화 invocation 주석**: **U2는 enforce를 직접 호출하지 않는다.** 근거화 강제는 U6.GatewayPipelineService가 U2 라우트의 응답 엣지(post-handler)에서 단일 적용한다. U2는 후크 입력을 정형화하고 verdict를 결과/기권으로 매핑만 한다(이중 강제 방지).
- **이벤트 (off the blocking path)**: 성공 응답 후 `publishSearchExecuted(userId, query, timestamp, resultCount)` → 이벤트 백본(FR-10, NFR-P1 비차단). 관측성 스팬/메트릭은 ObservabilityHub로 emit. 할루시네이션 인시던트 신호는 U6 GroundingEnforcementHook→HallucinationDetector 경로가 단독 담당(U2 미발행).
- **Trace**: FR-1, FR-2, FR-3, FR-4, FR-5, FR-11, NFR-P1, NFR-C1, RES-9, QT-2, US-D1..D7

---

## U3 — Accounts/Auth 서비스

### SignupService (동기 입구 + 이벤트 발행)
- **책임**: 공개 셀프 가입 전체 흐름 — 입력 정책 검증·이메일 유일성·적응형 해싱 생성·계정 영속·가입 텔레메트리/남용 신호 발행. 평문 비밀번호 비저장·비로깅 불변식 보장(FR-7, SEC-12, SEC-3, US-A1).
- **오케스트레이션**: AccountController(sync) → `register`. 내부: `PasswordPolicy.evaluate`(유출 검사 포함, 위반 시 조기 반환) → `CredentialStore`(중복 검사+createCredential) → 계정 영속 → 이벤트 백본 `AccountCreated` 발행(event), 속도/중복 시 `SignupAbuseSignal`(event). 가입 레이트 리미팅 사전 강제는 게이트웨이(SEC-11)가 컨트롤러 진입 전 수행.
- **Trace**: FR-7, US-A1, SEC-11, SEC-12, SEC-3

### AuthenticationService (동기 입구 + 이벤트 발행)
- **책임**: 로그인/로그아웃 전체 흐름 — 자격증명 검증·세션 발급/무효화·무차별 대입 방어 신호·노후 해시 재해싱. 자격증명 존재 미노출(FR-7, SEC-12, US-A2).
- **오케스트레이션**: AccountController(sync) → `authenticate/revoke`. authenticate: `CredentialStore.verifyCredential` → 성공 시 `SessionManager.issue`(+needsRehash 시 `CredentialStore.rehash`) → 쿠키 머티리얼; 실패 시 `AuthFailureSignal` 발행(event) → 게이트웨이/U6 Ops가 락아웃·지연·CAPTCHA 강제. revoke: `SessionManager.invalidate`.
- **Trace**: FR-7, US-A2, SEC-12

### SessionAuthorizationService (동기 결정 경계)
- **책임**: 요청별 인증 검증(SessionVerifier)과 **객체 단위 소유권 인가(AuthorizationGuard — 시스템 단일 권위 결정점)** 를 묶어 게이트웨이·타 도메인(U4)에 제공. 기본 거부·fail closed 불변식(SEC-8, SEC-12, SEC-15).
- **오케스트레이션**: 게이트웨이(sync) → `SessionVerifier.verifyRequest` → `SessionManager.verify`(+`SessionStore.load`) → AuthenticatedPrincipal 컨텍스트 주입. **사용자 데이터 접근 시 U6.AuthnAuthzGuard·U4 도메인 서비스가 동기로 `AuthorizationGuard.authorize`(소유권 판정)에 위임** — U3가 유일 결정 권위. P50<3s 예산 내 경량 수행(NFR-P1).
- **Trace**: SEC-8, SEC-12, SEC-15, NFR-P1

### AccountDeletionService (비동기 상태 전이 및 캐스케이드 추적)
- **책임**: 계정 파기 요청 처리 및 GDPR 완전 삭제 캐스케이드(Defense-in-Depth). 사용자의 삭제 요청 시 계정을 소프트 비활성화하고 비동기 워커로 실제 삭제와 연계 시스템 데이터 삭제 보장을 오케스트레이션.
- **오케스트레이션**: AccountController(sync) → `requestDeletion` (status=DEACTIVATED 설정 후 `purgeJob` 백그라운드 큐). 비동기 워커가 `purgeJob` 실행: U3 DB 레코드 물리 삭제 → `AccountDeleted` 이벤트 발행 → 구독자(U2, U4)의 `AccountPurged` 완료 이벤트 수신 대기 및 추적. SLA 초과 시 `CascadeOverdue` 경보 트리거(GDPR 보장).
- **Trace**: FR-28, US-A6, SEC-8, GDPR

### PasswordResetService (동기 흐름 위임)
- **책임**: 비밀번호 분실 시 보안 인증 및 재설정 절차.
- **오케스트레이션**: AccountController(sync) → `requestReset` (토큰 생성/영속화) → 외부 Email 어댑터 발송 위임. `confirmReset` 시 토큰 검증, 신규 비밀번호 평가, 저장 및 진행 중인 모든 세션 무효화(`SessionManager.invalidate`).
- **Trace**: FR-26, BR-A8

### EmailVerificationService (계정 소유권 확인)
- **책임**: 계정 생성 후 이메일 유효성 확인 및 변경 시 소유권 양방향 승인.
- **오케스트레이션**: AccountController(sync) → `verifyEmail` 시도. 토큰 검증 성공 시 계정 상태 `ACTIVE`로 전환. `requestEmailChange` 시 기존/신규 이메일 양쪽으로 알림 발송 및 새 이메일 토큰 발송.
- **Trace**: BR-A5, BR-A10

### SocialLoginService (위임 인증 흐름)
- **책임**: Google OIDC 등 타사 인증 연동 및 계정 통합(Pre-Hijacking 방어).
- **오케스트레이션**: AccountController(sync) → `start` (OIDC 인가 URL 반환). 콜백 시 `callback` 실행하여 id_token 검증, 이메일 추출 후 매핑. 매핑 시 기존 계정과 병합 또는 거부 판단.
- **Trace**: FR-27, BR-A9

---

## U4 — Saved Searches & Library 서비스

> 공통: 모든 호출은 공유 미들웨어/게이트웨이(DQ5: authn/authz·rate-limit·observability) 통과 후 진입. rerun은 게이트웨이-프런티드 검색 계약으로 재진입.

### SavedSearchService (동기)
- **책임**: 검색 저장 save/list/delete/rerun 오케스트레이션 + SEC-8 소유권 강제(FR-8, US-L1).
- **오케스트레이션**: SavedSearchController(sync) → `UserDataRepository`(SavedSearch 포트, lib)로 owner-scoped 영속(소유권 결정은 U3.AuthorizationGuard 위임, 데이터 계층 owner-scoping은 백스톱) → **rerun 시 게이트웨이-프런티드 검색 계약(U6 ApiGatewayMiddleware 경유 → U2 SearchOrchestrationService, sync)으로 위임 — 근거화·비용·관측성 후크 통과** → 쓰기 시 SharedAuditLogger(공유 횡단)로 감사 이벤트(event).
- **Trace**: FR-8, US-L1, SEC-8, SEC-13, DQ4, DQ6

### LibraryService (동기)
- **책임**: 라이브러리 add/list/remove 오케스트레이션, 멱등성·메타 스냅샷·SEC-8 소유권(FR-9, US-L2).
- **오케스트레이션**: LibraryController(sync) → `UserDataRepository`(LibraryItem 포트, lib)로 owner-scoped 멱등 영속 → add/remove 시 SharedAuditLogger(event). 목록은 보존 메타 스냅샷만 반환(U2/인덱스 비의존, 가용성 격리).
- **Trace**: FR-9, US-L2, SEC-8, SEC-13, DQ4

### SearchHistoryService (쓰기 event · 읽기 sync 분리)
- **책임**: 이력 비동기 기록(write)과 동기 list/rerun/clear(read) 분리 오케스트레이션, SEC-8 소유권(FR-10, US-L3).
- **오케스트레이션 (쓰기 = event)**: **U2.SearchOrchestrationService가 발행한 SearchExecuted 이벤트를 공유 이벤트 버스(event)로 구독** → `UserDataRepository`(SearchHistory 포트, lib)에 비동기 기록(NFR-P1 검색 응답 비차단).
- **오케스트레이션 (읽기 = sync)**: SearchHistoryController(sync) → owner-scoped 조회; rerun은 게이트웨이-프런티드 검색 계약(U6 경유 → U2, sync)으로 위임.
- **Trace**: FR-10, US-L3, SEC-8, DQ6, NFR-P1

---

## U5 — Mobile Web Frontend 서비스

### SsrRenderService (서버측, 동기)
- **책임**: SSR 요청을 받아 라우트 해석·세션 부트스트랩·보안 헤더 부착·초기 데이터 프리패치를 거쳐 폰 우선 HTML 합성. PhoneMockupFrame+SecurityHeaderPolicy로 NFR-U2·SEC-4 동시 충족.
- **오케스트레이션**: SsrRequest 수신 → `SecurityHeaderPolicy.buildHeaders/buildCsp` → 세션 쿠키로 SessionState 부트스트랩 → 보호 라우트면 인증 가드(미인증 시 로그인) → 라우트별 초기 데이터 `ApiClient` 프리패치(sync) → `AppShell.render` → `PhoneMockupFrame.wrap` → SSRHtml + SecurityHeaders 응답.
- **Trace**: NFR-U1, NFR-U2, SEC-4, NFR-P1

### SearchInteractionService (클라이언트, 동기)
- **책임**: 검색 화면 상호작용 오케스트레이션 — 입력 검증→동기 검색→상태 전이를 단일 요청/응답으로 묶어 NFR-P1 지원·FR-11 상태 표면화. **히어로 첫 검색(US-H1) 흐름의 클라이언트 주체.**
- **오케스트레이션**: submitQuery → `SearchScreen.validateInput`(빈/≤500자) → 위반 시 인라인 메시지·중단(요청 미전송) → 통과 시 `StateView.renderLoading` → `ApiClient.search`(동기 REST) → 성공: `ResultList.render`(저하 메타 포함) / 빈: `StateView.renderEmpty` / 오류: `StateView.renderError`(fail closed) / 저하: `StateView.renderDegraded`.
- **Trace**: FR-1, FR-11, NFR-P1, US-H1, US-D1..D7

### SessionFlowService (클라이언트, 동기)
- **책임**: 가입·로그인·로그아웃·세션 수명주기 오케스트레이션 — 자격증명 검증·세션 쿠키 인증 상태 반영·레이트리밋/무차별대입 응답 표면화.
- **오케스트레이션**: 폼 제출 → AccountScreens 클라이언트 검증 → `ApiClient.signup/login` → 성공: AppShell 세션 컨텍스트 갱신·보호 라우트 리다이렉트 / 429·락아웃: `StateView.renderError` 비기술 메시지 → logout: `ApiClient.logout` → 세션 초기화·공개 라우트 전환.
- **Trace**: FR-7, SEC-12, SEC-11, FR-11

### UserDataService (클라이언트, 동기)
- **책임**: 저장 검색·라이브러리·이력 조회/재실행/추가/삭제 오케스트레이션. 모든 요청 현재 세션 사용자 범위로만 발행, 소유권 강제는 백엔드 인가 위임(SEC-8).
- **오케스트레이션**: 보호 라우트 진입(미인증 시 SessionFlow 위임) → `ApiClient.list*` 조회 → `LibraryHistoryScreens.render*` → rerun 시 SearchInteractionService로 질의 재실행 → saveSearch/addToLibrary/remove* 시 ApiClient 변이 후 목록 갱신 → 403 등은 `StateView.renderError`.
- **Trace**: FR-8, FR-9, FR-10, SEC-8

---

## U6 — Reliability & Operations 서비스

### GatewayPipelineService (동기 횡단 — DQ5 전용 미들웨어 계층)
- **책임**: 사용자 동기 REST 경로의 횡단 전처리/후처리를 단일 책임으로 묶어 도메인 모듈이 보안·검증·인가·관측성·근거화를 위임만 하도록 함. **응답 엣지 근거화 게이트의 단일 invocation site.**
- **오케스트레이션 (sync)**: 요청 수신 → `applySecurityHeaders` → `InputValidationGuard.validate`(SEC-5) → `AuthnAuthzGuard.authenticate`(U3.SessionVerifier 위임)/`authorize`(**U3.AuthorizationGuard 위임**, SEC-8/12) → `RateLimiter.checkLimit`(SEC-11) → `CostGuardCircuitBreaker.getBudgetState`(저하 분기 컨텍스트 NFR-C1) → 도메인 핸들러(U2/U3/U4) 동기 위임 → **U2 라우트 응답 직전 post-handler 단계에서 `GroundingEnforcementHook.enforce`(FR-5) 단일 적용** → `ObservabilityHub` 메트릭/로그/트레이스 제출 → 예외 시 `toProductionError`(fail-closed SEC-15). 모든 단계 sync.
- **의존성 방향 주석**: 게이트웨이가 호출자(U6 → U2 핸들러). 핸들러 내부의 근거화·비용 후크는 주입된 lib 의존(U2 → U6 hooks = kind:lib)으로, 인바운드 래핑 체인 + 주입 횡단 lib 구조이며 sync 순환이 아니다.
- **Trace**: SEC-4, SEC-5, SEC-8, SEC-9, SEC-11, SEC-12, SEC-15, NFR-O1, FR-5, FR-11

### CostGuardService (이벤트 소비 + 동기 조회)
- **책임**: 비용 상한(NFR-C1) 준실시간 텔레메트리·임계 평가·서킷 운용으로 상한 초과 이전 우아한 저하 + 비용 폭발 인시던트 신호 공급(RES-11(a)).
- **오케스트레이션**: 이벤트 백본의 usage/cost 이벤트 비동기 소비(event) → `recordSpend` 누적 → `evaluateCircuit` 임계 평가(80% 경보/100% 전 차단) → 임계 시 ObservabilityHub 경보 + CostExplosionDetector로 급증 신호(async) → 동기 경로는 `getBudgetState`로 저하 모드(LLM 리랭킹 비활성→lexical 폴백)를 U2에 노출(sync).
- **Trace**: NFR-C1, NFR-R2, RES-9, RES-11(a), US-R3, QT-3

### GroundingGuardService (동기 강제 + 이벤트 인시던트)
- **책임**: **FR-5/QT-1 엄격 근거화/기권을 동기 경로에서 강제하는 단일 권위 서비스.** 위반을 할루시네이션 인시던트로 전환, QT-1 평가셋 실행 진입점 제공.
- **오케스트레이션**: GatewayPipelineService가 U2 응답 직전 `enforce(candidate, retrieved)` 동기 호출(sync) → block/abstain 시 응답 차단·기권 강제 → 위반 신호를 HallucinationDetector로 전달(async 인시던트) → ObservabilityHub에 근거화 건강도 메트릭 → OP/팀 QT-1 평가셋은 `runEvalSet`으로 동일 후크 재사용.
- **Trace**: FR-5, QT-1, RES-11(b), NFR-R1, US-D5, US-D6, US-R1

### ObservabilityService (동기 제출 + 이벤트 팬아웃)
- **책임**: 메트릭·구조화 로그·트레이스·감사 로그 단일 수집·표준화, 대시보드/탐지기 공급(NFR-O1, RES-5, SEC-14).
- **오케스트레이션**: 도메인·미들웨어·워커가 `emitMetric/emitLog/startSpan/auditAppend` 동기 제출(sync) → 집계·PII 차단 정규화(SEC-3) → 텔레메트리를 이벤트 백본으로 팬아웃(event)해 AiIncidentDetectorSuite·OpsDashboardService 공급 → 임계 위반은 IncidentEventPublisher.publishAlert 라우팅(RES-7).
- **Trace**: NFR-O1, RES-5, RES-7, SEC-3, SEC-13, SEC-14

### HealthMonitoringService (동기 프로빙 + QT-3 평가)
- **책임**: 얕은·깊은 헬스 체크·합성 모니터링으로 비정상 인스턴스를 라우팅에서 제외·건강도 관측성 연동(RES-6). **ReliabilityEvalProbe를 통해 QT-3 신뢰성/우아한 저하 인수 평가셋 소유.**
- **오케스트레이션**: 라우터/LB가 `/health/shallow`·`/health/deep` 주기 프로빙(sync) → `deepCheck` 의존성 연결성 타임아웃 검증(RES-9) → 비정상 시 라우팅 제외 신호 + ObservabilityHub 건강도 메트릭(sync) → **OP/팀은 `ReliabilityEvalProbe.runReliabilityEvalSet`로 업스트림 장애·빈 결과·강제 저하 경로 동작을 검증·보고(QT-3, GroundingEnforcementHook.runEvalSet의 신뢰성 대응물)** → 인제스천/AZ/용량 이상은 ObservabilityService 경유 경보(RES-7).
- **Trace**: RES-6, RES-7, RES-9, QT-3, US-R5

### AiIncidentResponseService (전 구간 이벤트 드리븐 — 별도 워커 DQ1)
- **책임**: RES-11 AI 인시던트 탐지·분류·발행 — (a)비용 폭발 (b)할루시네이션 (c)반쪽짜리 결과를 탐지해 IR+COE로 라우팅.
- **오케스트레이션**: 별도 워커가 이벤트 백본에서 텔레메트리/근거화 위반/지출/완결성 이벤트 비동기 소비(event) → 각 탐지기(`CostExplosionDetector`/`HallucinationDetector`/`PartialResultDetector`)의 `onTelemetryEvent` 후보 평가 → `classify`로 클래스·심각도 부여 → `IncidentEventPublisher.publishIncident/publishAlert`로 인시던트·경보 이벤트 발행(event) → COE 후속 컨텍스트 첨부, OpsDashboardService가 상태 소비. **탐지·발행 전 구간 비동기.**
- **Trace**: RES-11(a/b/c), NFR-O1, US-R1, US-R2, US-R3, US-R4, QT-3(PartialResultDetector)

## U10 — Mypage
- `MypageController`
- `UserPreferencesService`
- `DataExportService`

---

## U11 — Evidence Formation Agent 서비스 (재인셉션 Phase 4 / requirements "[U4]")

> 공통: 모든 호출은 U6 게이트웨이(authn/authz·rate-limit·비용·관측성) 통과 후 진입. 스트리밍 응답(SSE)은 응답 엣지 근거화 게이트를 통과한다.

### EvidenceChatService (동기 스트리밍 — SSE)
- **책임**: 사용자 채팅 턴 오케스트레이션 — 세션 진입·생성, Agent 실행, 스트리밍 응답, 턴 영속(FR-36, FR-37, NFR-P6).
- **오케스트레이션**: `EvidenceChatController`(sync, SSE) → 세션 load/create(`EvidenceSessionRepository`) → `EvidenceAgentOrchestrator.run(request, ctx)` → 스트림 `EvidenceChunk` 반환 → 완료 시 `EvidenceSessionRepository.appendTurn`(turn 영속) → SSE 종료. 후속 질문은 `continueSession`(멀티턴 맥락 유지, Q7=A). 긴 분석은 `EvidenceJobService`로 오프로드(NFR-P6, Q9=A).
- **Trace**: FR-36, FR-37, NFR-P6, Q7=A, US-EV1, US-EV2, US-EV5

### EvidenceSessionManagementService (동기 CRUD)
- **책임**: 세션 목록·삭제·초기화 오케스트레이션 — owner-scoped SEC-8 소유권 강제(FR-38).
- **오케스트레이션**: `EvidenceChatController` → 소유권 확인(`U3.AuthorizationGuard` 위임) → `EvidenceSessionRepository.listSessions/deleteSession/resetAllSessions` → 응답. 타 소유자 세션은 NotFound 일반화(SEC-9, SEC-15).
- **Trace**: FR-38, SEC-8, SEC-9, SEC-15, US-EV7, US-EV8

### EvidenceJobService (비동기 잡 옵션 — 긴 다논문 분석)
- **책임**: 스트리밍 SLA를 초과하는 긴 다논문 분석을 비동기 잡으로 오프로드(NFR-P6, Q9=A, U7 잡 패턴 재사용).
- **오케스트레이션**: 요청 수신 → 즉시 `jobId` 응답(폴링 URL 포함) → `EvidenceAgentOrchestrator` 실행을 비동기 잡 큐에 발행(event) → 워커가 결과 완료 후 `EvidenceSessionRepository`에 저장 → 클라이언트는 `GET /api/evidence/jobs/:id`로 상태/결과 폴링.
- **Trace**: NFR-P6, Q9=A, US-EV9

---

## 2026-09-19 F01-F13 교정 서비스 개정

> **SUPERSEDED - 2026-09-19 UQRF1=B**: 아래 orchestration은 REM planning-overlay 전제의 이력이다. 네 장기 deployable remediation services의 runtime orchestration은 재개된 Application Design에서 다시 정의한다.
>
> RQ1=A: 아래 서비스는 기존 package/deploy boundary 안의 orchestration이다. REM 전용 runtime 서비스는 없다. 모든 destructive/live 단계는 isolated verification과 별도 실행 승인을 통과하기 전 호출되지 않는다.

### REM-1 - Platform and Contract Integrity

#### MigrationApplicationService (startup + CLI 공통)
- **책임**: backend startup과 migration CLI가 동일 ordered registry와 ledger identity를 사용하도록 한다. 빈 DB, 재실행, 실패 rollback에서 같은 결과를 보장한다.
- **오케스트레이션**: startup 또는 CLI → `OrderedMigrationRegistry.entries/validate` → validation 성공 시 기존 migration runner에 ordered specs 전달 → script별 transaction 안에서 DDL+ledger 기록 → 실패 시 해당 script transaction rollback. startup/CLI identity set 불일치는 실행 전 차단한다.
- **Trace**: F08, NFR-M1, RESILIENCY-04, PBT-04/05/06

#### ContractGenerationPipeline (build-time)
- **책임**: local JSON schema 전체를 offline fail-closed 방식으로 build-consumed Python/TypeScript binding으로 생성하고 CI drift gate를 제공한다.
- **오케스트레이션**: schema roots 자동 발견 → `$id -> local file` registry 구성 → local `$ref` closure 검증 → temporary output tree 생성 → 전체 target parse/typecheck 성공 → committed generated tree 원자 교체 또는 `checkDrift`; 어느 단계든 실패하면 non-zero로 종료하고 기존 tree를 보존한다.
- **Trace**: F13, SEC-5/13, NFR-M1, PBT-02/10

#### SupplyChainVerificationPipeline (build/deploy preflight)
- **책임**: production runtime, lock closure, container digest, advisory, SBOM을 deploy unit별로 검증한다.
- **오케스트레이션**: shared runtime compatibility manifest 로드 → native launchd/CI/local/Docker version 대조 → committed frozen lock audit → approved exception expiry/reachability 검증 → digest pin 검사 → deploy unit별 SBOM 생성/보관. 차단 finding이 남으면 build/deploy를 중지한다.
- **Trace**: F06, SEC-10, RESILIENCY-03/04

### REM-2 - Private Content and Generation

#### SummaryRequestOrchestrationService (기존 summarization orchestration 개정)
- **책임**: public/private namespace 격리, canonical source identity, cache lookup, durable async generation을 한 순서로 조정한다. 기존 `{status: "pending"}`와 repeat-request polling 외부 계약은 유지한다.
- **오케스트레이션**: authenticated public summary 요청 → `PublicPaperNamespacePolicy.requirePublicPaperRef` → `CanonicalSummarySourceResolver.resolveCanonicalSource/sourceIdentity` → source-bound cache key 구성 → cache hit 즉시 반환 → miss면 `SummaryGenerationJobRegistry.ensureJob` → active/new job은 enqueue 결과를 durable 기록하고 `pending` 반환 → repeat POST는 cache 또는 marker를 조회해 success/terminal failure/pending을 반환한다. client abstract는 canonical source 선택에 사용하지 않는다.
- **worker 흐름**: queue delivery → durable lease/running 기록 → model execution bounded timeout/visibility heartbeat → artifact write → succeeded marker; retriable failure는 attempt budget 안에서 redelivery, 소진/비재시도 오류는 terminal failure. enqueue 실패를 pending으로 위장하지 않는다.
- **Trace**: F01, F02, F05, FR-5/12/13, NFR-P2/R2, SEC-8/13/15, RESILIENCY-10

#### PrivateDocumentContextService (evidence/novelty context-bound)
- **책임**: authenticated owner가 이미 확정된 evidence attachment 또는 novelty manuscript 경로에서만 `userdoc:` DocModel/asset을 제공한다. public paper controller와 공유하지 않는다.
- **오케스트레이션**: context controller의 authenticated owner → `UserDocModelCoordinator.validateOwnedRef` → owner-bound object/asset read → caller domain에 block/stream 반환. mismatch와 missing은 동일 NotFound로 일반화한다. public summarization/DocModel/asset route는 이 서비스로 자동 전환하지 않고 `userdoc:`를 거부한다.
- **Trace**: F01, F07, FR-18/38, SEC-8/9/15

#### SameOriginAssetDeliveryService (authenticated sync stream)
- **책임**: paper asset의 auth, public namespace, license, manifest, object access와 browser same-origin relay를 묶되 storage endpoint/key를 외부에 노출하지 않는다.
- **오케스트레이션**: browser same-origin request → `SameOriginAssetProxy`가 session/trusted identity 전달 → `AuthenticatedPaperAssetController.streamAsset` → public namespace + license + manifest 검증 → backend-only object stream → BFF가 safe content/cache headers와 bytes를 relay. `userdoc:`는 public route에서 거부하고 private context service로만 읽는다.
- **Trace**: F07, SEC-4/8/9, RESILIENCY-10

### REM-3 - Owner Lifecycle and Edge Trust

#### DurableOwnerPurgeService (AccountDeletionService 개정)
- **책임**: SQL과 private objects/cache를 immutable manifest에 결속해 완전하고 멱등이며 재개 가능한 account purge를 수행한다.
- **오케스트레이션**: deletion grace 만료 → `OwnerPurgeRegistry.validateCoverage/inventoryOwner` → `PurgeManifestRepository.createManifest` commit → 기존 deterministic deletion event 발행/단계 기록 → manifest object/cache targets 삭제 → owner SQL+credentials transaction → `verifyResidue`로 대상 owner 0건과 비대상 owner 불변 확인 → complete. 실패는 stage/error를 기록하고 동일 manifest에서 resume한다. registry 누락과 zero-residue 실패는 complete를 금지한다.
- **Trace**: F04, FR-28/38, SEC-8, RESILIENCY-02/04/12/14, PBT-04/06

#### DigestLinkService (token-authorized public mutation)
- **책임**: 이메일의 실제 `/paper/{id}` link를 생성하고, exact public unsubscribe path에서 expiring signed grant로 opt-out을 원자 적용한다.
- **오케스트레이션**: digest render 시 route-safe paper ID와 실제 frontend route 생성 + `DigestLinkTokenVerifier.issue` → unsubscribe request는 gateway exact-path public exception → verifier가 signature/age/settings version 검증 → repository conditional update(owner, opted-in, settings version) → 이미 opted-out이면 동일 성공. concurrent settings 변경은 stale token으로 거부한다.
- **Trace**: F09, FR-47, SEC-5/8/12/13/15

#### TrustedEdgeIdentityService (BFF + ingress middleware)
- **책임**: Cloudflare tunnel 경계에서 검증한 한 client identity를 JSON/PDF/SSE 전 경로와 rate-limit/abuse control에 일관되게 공급한다.
- **오케스트레이션**: BFF가 browser-supplied internal header 제거 → production ingress의 단일 `CF-Connecting-IP` parse/canonicalize → private header overwrite → FastAPI ingress가 raw socket peer loopback 여부 검증 → `TrustedClientIdentityResolver`가 request-scoped identity 한 번 설정 → gateway `RateLimiter`와 accounts reCAPTCHA/email limiter가 같은 identity 소비. non-loopback private header와 malformed/multiple production identity는 거부한다.
- **Trace**: F10, SEC-2/11/15

### REM-4 - Corpus and Search Integrity

#### CorpusIntegrityAuditService (standalone read-only)
- **책임**: production corpus generation의 fixture, source metadata, 최근 AI/ML 365일 범위, generation identity를 mutation 없이 평가하고 immutable readiness report를 생성한다.
- **오케스트레이션**: `ProductionSeedGuard`로 production seed 차단 → operator/scheduled audit가 active alias/backing generation snapshot → `CorpusIntegrityAuditor.auditGeneration/writeReport` → report hash/freshness와 expected/indexed/missing/extra를 publish → `CorpusReadinessProvider`는 현재 generation과 report만 비교해 readiness reason을 노출한다. startup/readiness가 OpenSearch 문서를 수정하는 경로는 없다.
- **Trace**: F03, FR-2/5/6, QT-1/9, SEC-9, RESILIENCY-05/06/07

#### TargetedCorpusRepairService (standalone, approval-gated)
- **책임**: exact fixture fingerprint cleanup을 backup-first generation copy/cutover 방식으로 수행하고 rollback generation을 보존한다. full corpus rebuild는 이 서비스의 묵시적 fallback이 아니다.
- **오케스트레이션**: fresh audit report + verified backup → `CorpusRepairCoordinator.planRepair` dry-run manifest(count/IDs/hash/source+target/rollback alias) → 별도 repair authorization 확인 → fixture 제외 candidate generation 생성 → count/source/fixture 검증 → atomic alias cutover → post-audit. 실패 또는 post-check mismatch는 manifest로 alias rollback한다. 최근 1년 completeness가 rebuild를 요구하면 중지하고 별도 승인 게이트로 전환한다.
- **Trace**: F03, RESILIENCY-02/04/12/14

#### SearchOutcomeIntegrityService (sync read + frontend state)
- **책임**: degradation provenance와 no-match 의미를 backend response union부터 frontend view state까지 보존한다.
- **오케스트레이션**: retrieval 결과 0건 → `ResultAssembler.assembleEmpty(degradation, provenance)` → normal no-match는 empty page, known degradation은 empty degraded DTO → frontend `SearchStateClassifier.classifySearchResponse`가 degradation을 count보다 먼저 판정 → StateView가 degraded-empty/retry를 normal no-match와 구분해 렌더한다.
- **Trace**: F11, FR-11, NFR-R1/R2, SEC-15

#### RelevancePolicyService (offline calibration + sync enforcement)
- **책임**: fixture-free/source-verified generation에서 범위 밖 질의의 relevance floor를 측정하고 generation/model-bound 승인 정책만 검색 경로에 적용한다.
- **오케스트레이션**: fresh corpus audit → labeled in/out-of-scope eval set → `RelevanceFloorEvaluator.evaluateFloors`가 raw score, false-abstain, false-pass, retrieved IDs를 report → shadow mode 관측/승인 → `RelevanceFloorPolicy.loadPolicy`가 generation/model binding 검증 → search read가 `classifyBestMatch`로 match/no-match/abstain 결정. stale/malformed/zero policy는 조용히 비활성화하지 않고 readiness/config failure로 처리한다.
- **Trace**: F12, FR-5/11, QT-1, SEC-15

---

## 2026-09-19 Deployable Services and Public Jobs

**입력**: WPR2=A, DSRQ 결정, RJR1=A 및 RJS2=A. 아래 경계/불변식은 Application Design이며 정확한 상태 enum, transaction primitive, TTL/retry 수치와 schema는 Functional/NFR Design에서 확정한다. component ID와 typed port는 동명 companion 문서를 따른다.

### DS-1. Service bootstrap 및 platform integrity

- REM-1~4는 각각 독립 versioned artifact와 launchd daemon/worker/허용 one-shot 역할을 가진다. role별 자격증명과 resource budget을 구분한다.
- startup은 local CompatibilityManifest, 지원 schema/operation version, 단일 ordered migration registry/ledger, 필수 설정과 consumer binding을 검증한다. 누락을 silent module skip으로 정상 처리하지 않는다.
- REM-1 R1C는 evidence 조회만 수행한다. R1R은 명시적으로 실행된 build/CI/privileged runner이며 ordered migration apply, binding generation, dependency/pin/SBOM 검사와 승인된 promotion을 수행한다. 모든 local schema ref를 offline 해소하고 어떤 생성 실패도 전체 non-zero/미공개로 처리한다.
- 빈 DB provisioning과 migration은 승인 runner가 수행하고 API startup은 같은 registry의 완료/호환성을 확인한다. live daemon이 실행돼야 build/migration을 시작할 수 있는 bootstrap 순환을 만들지 않는다.
- **Trace**: F06/F08/F13, WPR2 G1, SECURITY-10/13, RESILIENCY-04.

### DS-2. Content job 접수·실행·publication

1. EDGE가 신뢰 ingress의 client identity, 현재 session/delegation, 입력과 rate-limit을 검증한다. public-paper와 owner-context route를 고정 dispatch하고 raw key/임의 URL을 routing 입력으로 사용하지 않는다.
2. R2A는 public `userdoc:`를 거부하고 private context는 원 domain의 AUTH binding을 확인한다. 요청 kind/options와 caller별 submission key를 검증해 RK에 OperationIntent를 넘긴다. 접수 검증은 내용 read/model 실행과 구분된다.
3. RK가 operation + outbox intent를 원자 저장한 후 AcceptedJobReceipt를 반환한다. broker publish 성공 자체가 접수의 유일 근거가 아니다. commit 여부가 불명확한 응답은 같은 submission으로 재조정하며 새 작업을 무작정 만들지 않는다.
4. dispatcher는 opaque operation/command reference와 version/correlation만 queue에 보낸다. worker는 메시지의 owner/payload를 신뢰하지 않고 자기 realm의 durable record와 current authority를 다시 확인한다. 원 session cookie나 오래된 signed envelope를 queue credential로 저장하지 않는다.
   - cross-domain command는 지정 recipient만 읽을 수 있는 immutable CommandProjection으로 입력을 해소한다. recipient가 자기 inbox에 받아 실행하고 자기 outbox로 receipt를 발행한다. 이 내부 view/copy도 owner/run fence와 보존/파기 분류를 따른다.
5. R2W는 server source를 해결하고 SourceIdentity를 최초 실행에서 고정한 뒤 GenerationIdentity로 cache를 검사한다. 재시도는 고정 source/version을 유지한다. 해당 revision을 더 이상 검증할 수 없으면 명시적 실패이며 다른 source로 조용히 바꾸지 않는다.
6. cache hit는 기존 artifact를 reuse하고 miss만 bounded U7 생성으로 처리한다. U1 source 준비가 필요하면 versioned 내부 BuildSource command/receipt에 맡기며 새로 생성된 private source도 원 context와 owner fence를 검증한다.
7. 결과 blob을 준비하고 EXEC의 현재 fence/permit 안에서 result reference + terminal event/state를 publish한다. publish되지 않은 staging object도 cleanup/purge inventory 대상이다. private write가 불명확한 실패는 성공으로 공개하지 않는다.
8. UI는 접수/진행과 domain 결과를 구분한다. queue/model 지연은 HTTP 요청을 계속 점유하지 않으며 실제 hang/retry 소진은 terminal failure로 공개한다.

**Trace**: F01/F02/F05/F07, RJ-AC01/03/05/06/07/08/12, US-RJ1/US-S5.

### DS-3. Queued status와 직접 관측·결과 전달

- 명시적 status 확인은 대상 업무의 current owner 검증 후 독립 StatusQuery operation으로 접수한다. worker가 한 target revision/observedAt의 JobObservation을 완료 결과로 publish한다. query operation을 다시 target으로 삼는 query-of-query와 자동 polling job 연쇄는 허용하지 않는다.
- DELIVERY는 이미 publish된 event/result를 제공한다. 연결/재연결은 새 업무를 실행하지 않는다. cursor는 actor/job/stream version에 결속되고 유효 보존 범위의 terminal 또는 알려진 진행을 재전달한다.
- 직접 result endpoint는 준비된 artifact 또는 안전한 NotReady/Expired 응답만 제공한다. 현재 source를 새로 계산하거나 live status의 business query를 수행하는 우회 경로가 아니다.
- 각 event dispatch/reconnect/result/asset open은 현재 권한을 검증한다. 권한을 더 확인할 수 없으면 추가 private 전달을 중지한다. binary response 시작 이후의 오류는 stream을 안전하게 종료하고 structured signal을 남기며 내부 오류를 bytes에 섞지 않는다.
- BFF는 safe response header 및 bytes/event를 같은 origin으로 중계한다. private/observer response는 공유 cache에 남기지 않는다. UI는 disconnect를 작업 실패로 단정하지 않고 중복/역순 event가 terminal 상태를 되돌리지 않도록 한다.
- **Trace**: RJ-AC02/03/04/05/08/12, F07/F11, US-RJ1~3.

### DS-4. Current authority와 writer fencing

- U3가 account/session/lifecycle authority를, 각 resource domain이 context/owner/license binding을 소유한다. REM은 검증된 read-only projection과 domain 정책을 소비한다. projection은 immutable revision과 current head/철회 여부의 일관된 조회이며 event-cache만으로 유효성을 보증하지 않는다.
- live delegation의 transport expiry와 실제 caller의 source grant를 구분한다. queue에는 검증된 intent/reference만 남기고 실행 시 unexpired source grant 및 current resource 권한으로 ExecutionPermit을 얻는다. 제출 시점 허가나 service identity만으로 만료된 사용자 권한을 연장하지 않는다.
- 계정 비활성화/session 무효화는 U3 직접 제어 경로다. revocation/deletion epoch의 durable 변경을 우선 적용해 session cache cleanup 또는 lifecycle event 전달이 늦어져도 새 private 작업이 허용되지 않게 한다. 알려지지 않은 authority 상태는 거부다.
- 모든 owner writer 및 결과 publication은 EXEC fence 계약에 참여한다. 일반 user 작업은 닫힌 epoch로 commit할 수 없고, system purge/repair는 별도 purpose-bound grant로만 해당 범위를 처리한다.
- admission 자체도 owner-bound write다. RK의 operation/outbox, opt-out suppression 및 recipient control copy는 commit 경계에서 현재 owner/run fence를 확인한다. 요청 초기에만 권한을 검사해 비활성화/파기와 경쟁하는 새 row를 뒤늦게 만드는 경로는 허용하지 않는다.
- **Trace**: F01/F04/F10, RJ-AC05/09/11, SECURITY-08/12/15.

### DS-5. Owner purge saga

1. U3의 유예 관리가 current lifecycle epoch에서 유예 취소/재활성화와 파기 진입을 원자적으로 조정하고 durable LifecyclePurgeDue를 발행한다. 취소된 이전 epoch의 신호는 거부하며 파기 진입이 확정된 epoch를 뒤늦은 재활성화가 덮어쓰지 못한다. REM-3 R3P는 current system purpose와 registry coverage를 검증한다. 기존 logging-only 이벤트 또는 부분 SQL 목록을 파기 완료의 근거로 사용하지 않는다.
2. R3P가 domain-owned EXEC에 QuiesceOwner를 보낸다. domain은 신규 write를 차단하고 진행 중 SQL/object/model 결과 publication을 정리한다. 불명확한 외부 I/O는 quiescence 완료로 응답하지 않으며 lease 만료만으로 완료를 추정하지 않는다.
3. quiescence 확인 후 SQL/object/cache 및 REM job/outbox/event/result/staging/observer data의 exact inventory를 manifest로 고정한다. purge 진행 중 생기는 자체 receipt/progress는 미리 선언한 purge-run control namespace로 한정하고 최종 정리 대상으로 둔다. 기존 도메인마다 manifest-bound ApplyPurge를 소비하고 자기 데이터만 삭제한다. 공유 public artifact와 다른 owner variant는 보존한다.
4. domain mutation과 receipt 발행 의도는 같은 domain의 durable 단위로 기록한다. REM-3는 command 전송/queue ack가 아니라 검증된 실행 receipt와 residue 증거를 집계한다. 재전달은 동일 command/manifest에 멱등이다.
5. 필요한 모든 domain receipt, 대상 0건 및 비대상 owner 보존이 확인돼야 완료한다. 누락/실패는 같은 manifest에서 재개하며 immutable inventory를 조용히 재계산하지 않는다. 범위가 바뀌면 별도 검증된 후속 manifest가 필요하다.
6. 마지막으로 command materialization/receipt의 run fence를 닫고 그 private I/O도 quiesce한다. REM-3 자체 manifest/intent/observer/receipt, recipient inbox/outbox의 private command copy 및 U3 lifecycle 잔여 데이터까지 정책에 맞게 삭제/비식별화해야 완료다. 완료 audit는 private payload와 재식별 owner 참조를 보존하지 않는다. 이후 늦은 메시지/receipt는 missing/closed parent와 authority로 거부하며 inbox upsert로 삭제된 작업/control data를 다시 만들지 않는다.

**Trace**: F04, RJ-AC09/11/12, US-A6/US-EV8, RESILIENCY-12/13/14.

### DS-6. Token unsubscribe와 즉시 발송 차단

1. 이메일의 `/paper/{id}` 및 `/unsubscribe` landing을 유지한다. token은 U15 규칙으로 서명/issued-at/expiry/consent revision을 검증하고 production key 부재 시 fail closed한다.
2. EDGE의 exact token-authorized 경로에서 R3C로 넘긴다. 로그인 session 대신 목적 제한 token actor를 사용하며 입력/사용량/요청 출처 검증은 생략하지 않는다.
3. R3C와 모든 U15 sender는 같은 ConsentBarrier 계약에 참여한다. valid revision을 확인하고 suppression intent + operation + outbox를 durable하게 수락하는 경계를 provider handoff와 직렬화한다. successful receipt 이후 새 handoff가 시작될 수 없다. 진행 중 handoff가 불명확하거나 fence를 얻지 못하면 성공 접수를 추정하지 않고 bounded 실패/재조정한다.
4. 수락된 suppression은 canonical settings의 비동기 반영보다 먼저 발송을 veto한다. 후속 ApplyOptOut은 그 suppression receipt/consent revision을 완결하는 목적 한정 System command로 U15 executor에 전달하고 version-bound receipt를 기다린다. 이미 수락된 효과의 완결 권한과 새 user/token admission 또는 결과 관측 권한은 별개이며 queue/worker 실패나 observer 만료가 suppression을 해제하지 않는다.
5. 사용자의 이후 명시적 opt-in/설정 변경도 U15 consent revision과 barrier에 참여한다. 오래된 token/command가 새 consent를 덮어쓰지 않으며, 새 opt-in의 처리 규칙과 idempotent 재전달은 U15 Functional Design에서 명세한다.
6. observer credential은 해당 해지와 허용된 status-query child만 관측한다. 일반 계정 정보나 다른 job으로 확대할 수 없다. 유효한 관측 권한으로 기존 receipt를 재전달할 수 있지만 만료된 token으로 새 suppression/권한을 발급하지 않는다.

**Trace**: F09, RJ-AC10, US-TN2, SECURITY-05/08/12/15.

### DS-7. Edge trust와 corpus 정책

- R3E는 versioned edge policy를 배포한다. 실제 Cloudflare ingress proof/단일 client identity 검증과 spoof header 제거는 BFF, authenticated BFF hop/raw peer 확인은 gateway, 동일 request identity 소비는 gateway/accounts limiter에서 수행한다. REM-3 daemon 응답을 매 요청의 필수 network hop으로 두지 않는다. origin proof의 실제 배선은 Infrastructure gate다.
- R4A는 production seed를 차단하고 current corpus generation/index identity를 read-only audit한다. source/fixture/completeness와 freshness가 포함된 immutable report를 발행한다. calibration은 검증된 generation/eval set에 결속하고 false-pass/false-abstain evidence를 남긴다.
- SEARCH/U6 health는 immutable report와 현재 generation/model head를 함께 확인한다. missing/stale/mismatch/잘못된 floor를 조용히 zero/off로 바꾸지 않는다. 알려진 장애가 있는 0건 결과는 정상 no-match와 분리한다.
- R4R은 exact manifest, source/target generation, verified backup/restore와 MutationApproval을 확인한 privileged U1 runner다. 새 admission/health/report read가 repair를 자동 시작하지 않는다. full rebuild/reparse/reembed/live alias cutover는 별도 승인이 필요하다.
- **Trace**: F03/F10/F11/F12, RJ-AC03/11/12, US-R2/4/5.

### DS-8. Deployment, failure isolation 및 복구

| 실패/전환 상황 | 외부 및 내부 동작 |
|---|---|
| durable store/authority 불가 | 새 요청은 accepted로 위장하지 않음. 기존 private 전달/쓰기의 권한 확인 불가 시 차단. 직접 health는 degraded/unready와 이유의 안전한 요약을 제공 |
| broker 유실/중단 | durable outbox/operation에서 재발행/재조정. UI는 접수 사실과 대기를 유지하되 한도 초과는 terminal로 판정. health/read-only evidence는 새 job 없이 응답 |
| worker crash/redelivery | operation/command lease와 멱등 effect/publication을 재확인. staged 결과를 조사하고 이미 성공한 효과를 중복 실행하지 않음 |
| REM-1/3/4 policy daemon 중단 | 검증된 local artifact/projection의 유효 범위에서 consumer가 동작. freshness/권한 증명 불가 시 해당 capability를 제한하며 arbitrary fallback은 없음 |
| observer 단절/순서 역전 | durable published event/result를 현재 권한으로 재전달. terminal 회귀 및 query job 연쇄 없음 |
| schema/operation version 비호환 | 지원 조합의 worker/observer를 유지하거나 명시적 보류/실패. 처리 불가 job을 drop하거나 unknown field로 권한을 확장하지 않음 |
| 부분 배포/rollback | expand-compatible schema와 frozen artifact, writer epoch 및 versioned route를 함께 전환. 같은 source namespace에 legacy/new worker를 동시에 writer로 두지 않음 |

기존 API에서 새 route를 켜기 전에 REM-2 데이터의 REM-3 purge coverage/즉시 제어 및 browser 인수를 검증한다. rollback도 같은 owner/source/삭제/해지 보호를 만족하는 artifact로만 수행한다. 안전한 호환 경로가 없으면 영향 route를 명시적으로 중지한다. backup/restore에는 새 operation/event/result/manifest가 포함되며 복구 후 accepted 작업을 재조정한다. gate는 WPR2 G0~G5를 따른다.

호환 기간의 legacy public controller/EDGE adapter도 동일한 namespace/current authority/canonical source 검증을 거친다. 검증된 기존 response 계약으로 표현할 수 있는 결과만 변환하고 202 접수를 완료 DTO로 cast하지 않는다. 지원하지 않는 조합은 명시적으로 거부/업그레이드 안내하며 old unsafe handler로 되돌아가지 않는다. 필요한 caller-bound compatibility link도 owner purge와 version inventory에 포함한다.
