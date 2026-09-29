# application-design.md — 통합 개요 (AI/ML 논문 디스커버리)

> **현재 승인 설계**: §8 `2026-09-19 Deployable Services and Public Jobs` 및 companion 4문서의 동명 절을 참조한다. RJR1/RJS2/WPR2와 해소된 DSRQ 결정을 반영했고 DAD1=A로 승인됐다. §7의 RQ1=A remediation 설계는 superseded 이력이다.

> 본 문서는 DocSuri 유닛의 Application Design 통합 개요다. 잠금된 아키텍처 결정(DQ1–DQ7)을 준수하며 **기술 스택 미확정**(언어/프레임워크/구체 AWS 서비스는 NFR Requirements·Construction 단계 소관) — 모든 외부 의존성은 capability로 참조한다.
> 상세는 동봉 4문서를 참조: [`components.md`](./components.md) · [`component-methods.md`](./component-methods.md) · [`services.md`](./services.md) · [`component-dependency.md`](./component-dependency.md).

---

## 1. 아키텍처 스타일 (잠금 결정 — 설계 준수)

| DQ | 결정 | 설계 반영 |
|---|---|---|
| **DQ1=A** | 모듈형 모놀리스 API + **별도** 인제스천 워커 (마이크로서비스 아님) | U2/U3/U4는 프로세스 내 도메인 모듈; U1은 독립 배포 이벤트 드리븐 워커; U6는 미들웨어 + 별도 운영/탐지 워커. |
| **DQ2=A** | SSR 폰 우선 프런트엔드(Next.js-style) + 백엔드 API | U5 SSR 폰 우선 프런트엔드. |
| **DQ3=C** | 이벤트/스케줄 드리븐 인제스천 | U1 CorpusRefreshScheduler(schedule/backfill/rebuild) + 이벤트 백본. |
| **DQ4=C** | 하이브리드 조직: 도메인 모듈(유닛별) + 공유 레이어(공통 어댑터·횡단) | 도메인 모듈 U1–U4 + 공유 어댑터(벡터 스토어/임베딩 게이트웨이/오브젝트 스토리지/영속화) + U6 횡단. |
| **DQ5=A** | 횡단 관심사는 **전용 미들웨어/게이트웨이 계층** | U6가 비용 가드/서킷·**근거화 강제(단일 권위)**·관측성·authn/authz·레이트리밋 소유. |
| **DQ6=C→재조정** | 인제스천/인덱싱/비용·인시던트/운영 = **이벤트 백본**; 사용자 디스커버리 READ = **동기 REST**(NFR-P1 P50<3s) | U2 검색 요청→응답 전 단계 sync; 인제스천·이력 쓰기·인시던트·관측성 event. |
| **DQ7=A** | REST API | U2/U3/U4 컨트롤러·U6 게이트웨이·U5 ApiClient 전부 REST. |

기술-불가지 준수: 외부 의존은 capability("vector store", "embedding/LLM gateway", "event bus/backbone", "object storage", "managed DB/persistence adapter", "breach-dataset adapter", "DLQ", "scheduler/timer")로만 표기. 구체 제품/프레임워크 명칭 없음.

---

## 2. 유닛 요약 (핵심 U1~U6 + U11 Evidence Agent + U12 Novelty Agent)

| 유닛 | 역할 | 경로 종류 | 핵심 컴포넌트 |
|---|---|---|---|
| **U1 Ingestion** | arXiv·Semantic Scholar·OpenAlex AI/ML 논문을 수집하고 FullText→eager DocModel→DocModel Block 청크→임베딩하여 공유 Corpus 인덱스 생성·갱신(write-only 생산자) | 이벤트/스케줄 백본 | CorpusSourceAdapterSet, FullTextExtractionProcessor, SourcePriorityDeduplicationGuard, DocModelBuildCoordinator, DocModelBlockChunker, EmbeddingGatewayAdapter, CorpusIndexWriter, CorpusRefreshScheduler, IngestFailureHandler |
| **U2 Discovery** | 자연어 질의의 동기 검색 읽기 경로(read 소비자) | **동기 REST** | QueryIntakeController, QueryValidator, QueryUnderstandingExpander, HybridRetriever, RelevanceRanker, GroundingAdapter, ResultAssembler |
| **U3 Accounts/Auth** | 가입/로그인/세션·자격증명·**객체 소유권 인가 단일 결정점** | 동기 REST + 이벤트 신호 | AccountController, SignupService, AuthenticationService, SessionManager, SessionVerifier, AuthorizationGuard, CredentialStore, PasswordPolicy, SessionStore |
| **U4 Library** | 검색 저장·라이브러리·이력(소유자 비공개) | 동기 CRUD + 이력 쓰기 event | SavedSearch/Library/SearchHistory Controller·Service, UserDataRepository, UserDataDTOAndValidation |
| **U5 Frontend** | SSR 폰 우선 웹 UI | 동기 REST(프런트) | AppShell, PhoneMockupFrame, SecurityHeaderPolicy, SearchScreen, ResultList, ResultCard, AccountScreens, LibraryHistoryScreens, StateView, ApiClient |
| **U6 Reliability/Ops** | DQ5 전용 횡단 미들웨어/게이트웨이 + 운영(관측성·비용 가드·헬스·AI 인시던트) | 동기 게이트 + 이벤트 운영 백본 | ApiGatewayMiddleware, AuthnAuthzGuard, InputValidationGuard, RateLimiter, CostGuardCircuitBreaker, GroundingEnforcementHook, ObservabilityHub, HealthCheckService, ReliabilityEvalProbe, AiIncidentDetectorSuite(+3 detectors), IncidentEventPublisher, OpsDashboardService |
| **U11 Evidence Agent** *(재인셉션 Phase 4 / requirements "[U4]")* | 로그인 필수 대화형 다논문 문헌탐색·근거형성 Agent. LLM이 Search·DocModel 도구를 자율 오케스트레이션해 EvidenceItem(핵심 주장·방법·결과·한계) 추출·비교; 근거 없으면 기권(FR-5). EvidenceFormationPort(D5) 단일 구현자 | 동기 REST(SSE 스트리밍) + 비동기 잡 | EvidenceChatController, EvidenceAgentOrchestrator, EvidencePaperSearchTool, EvidenceDocModelTool, EvidenceExtractor, EvidenceComparisonAssembler, AttachmentDocModelAdapter, EvidenceSessionRepository, EvidenceFormationService |
| **U12 Novelty Agent** *(별도 인셉션 사이클 — 2026-06-29 / 번호 확정 2026-06-30)* | 차별화(novelty)/연구아이디어 형성 Agent: EvidenceFormationPort(U11)·U2 `full`·GitHub/데이터셋 외부 탐색을 소비해 유사 연구 정리·bounded 차별화 아이디어·실험 계획·원고 위험 신호·승인형 Notion export 생성(FR-30~35) | 비동기 잡(생성/폴링/취소) | 상세 컴포넌트·FD/NFR/Infra는 `construction/novelty-agent/` (코드/CDK 구 U11 네이밍 잔존) |
| **U13 Agent Chat Frontend** *(별도 프론트 사이클 — 2026-07-01)* | `/agent` 단일 route에서 U11/U12 Agent mode 선택, 세션 drawer, 멀티턴 채팅, 첨부, 탐구 과정 timeline, mock/real transport seam을 제공하는 프론트엔드 셸 | Next.js route + client state | 상세 컴포넌트는 `agent-chat-frontend-components.md`·`agent-chat-frontend-services.md` 참조 |

---

## 3. 횡단 미들웨어 계층 (DQ5)

U6 ApiGatewayMiddleware는 모든 사용자向 동기 REST의 단일 진입이다. 전처리 체인: **보안 헤더(SEC-4) → 입력 검증(SEC-5) → 인증/세션(SEC-12) → 객체 단위 인가(SEC-8, U3.AuthorizationGuard 위임) → 레이트 리미팅(SEC-11) → 비용 상태(NFR-C1) → 도메인 핸들러 → [U2 라우트] 응답 엣지 근거화 강제(FR-5) → 관측성 → fail-closed 에러(SEC-15)**.

핵심 단일-소유자 규칙(비평 반영):
- **근거화/기권(FR-5/QT-1)**: U6.GroundingEnforcementHook가 단일 권위 런타임 게이트. U2.GroundingAdapter는 후크 입력/출력 정형화만(독자 강제·인시던트 발행 없음). invocation은 U6 GatewayPipelineService의 U2 라우트 post-handler 한 곳.
- **객체 단위 소유권(SEC-8)**: U3.AuthorizationGuard가 단일 권위 결정점. U6.AuthnAuthzGuard는 위임만, U4.UserDataRepository owner-scoping은 데이터 계층 백스톱.
- **인시던트 발행**: 실재 U6.IncidentEventPublisher/HallucinationDetector로 통일(팬텀 IncidentSignalPublisher 제거).

---

## 4. 이벤트 백본 vs 동기 읽기 (DQ6 재조정)

- **이벤트 백본(비동기·비차단)**: ① 인제스천(source별 스케줄/backfill/rebuild → U1 워커 → Corpus 인덱스), ② 이력 쓰기(U2 `SearchExecuted` → U4.SearchHistoryService), ③ 비용/인시던트 탐지(근거화 위반·지출 급증·완결성 → 탐지기 → IncidentEventPublisher), ④ 관측성 팬아웃·감사.
- **동기 읽기(NFR-P1 P50<3s)**: 사용자 검색 요청→응답(U5 → U6 게이트웨이 → U2 파이프라인 → 응답). U4 rerun도 게이트웨이-프런티드 검색 계약으로 동일 동기 경로 재진입(근거화·비용·관측성 후크 통과 — 백도어 금지).
- **생산자/소비자 정합**: U2가 `SearchExecuted` 생산자(신설 엣지), U4가 소비자. 공유 Corpus 인덱스는 U1 단일 writer·U2 단일 reader. 임베딩 VectorSpec은 공유 임베딩 게이트웨이 레이어가 단일 진실 원천으로 소유하고 U1 writer·U2 reader가 동일 계약 소비(벡터 공간 호환 불변식).

---

## 5. FR → 컴포넌트 추적 요약

| FR | 실현 컴포넌트(대표) |
|---|---|
| FR-1 자연어 질의 | U2.QueryIntakeController/QueryValidator, U5.SearchScreen, U6.InputValidationGuard |
| FR-2 시맨틱·하이브리드 검색 | U1.CorpusIndexWriter(쓰기), U2.QueryUnderstandingExpander/HybridRetriever(읽기) |
| FR-3 상위 N 랭킹 | U2.RelevanceRanker, U5.ResultList |
| FR-4 폰 결과 카드 | U2.ResultAssembler, U5.ResultCard |
| FR-5 엄격 근거화/기권 | **U6.GroundingEnforcementHook(단일 권위)**, U2.GroundingAdapter(어댑팅), U1.DocModelBlockChunker(추적 메타) |
| FR-6 Corpus 생성 파이프라인 | U1 전 컴포넌트 + IngestionPipelineService |
| FR-18 DocModel 리치뷰/eager 생성 | U1.DocModelBuildCoordinator, U1.DocModelBlockChunker, U1.CorpusIndexWriter |
| FR-7 계정 | U3 전 컴포넌트 |
| FR-8 저장 검색 | U4.SavedSearchController/Service |
| FR-9 라이브러리 | U4.LibraryController/Service, U5.ResultCard |
| FR-10 이력 | U4.SearchHistoryController/Service + **U2.SearchOrchestrationService(SearchExecuted 생산자)** |
| FR-11 빈/실패/저하 UX | U5.StateView, U2.QueryIntakeController/ResultAssembler |
| FR-36 근거형성 세션·멀티턴 | U11.EvidenceChatController, U11.EvidenceAgentOrchestrator, U11.EvidenceSessionRepository |
| FR-37 다논문 근거형성·추출·기권 | **U11.EvidenceFormationService(D5 단일 권위)**, U11.EvidenceAgentOrchestrator, U11.EvidenceExtractor, U11.EvidenceComparisonAssembler, U11.AttachmentDocModelAdapter |
| FR-38 근거형성 세션 영속·사용자 제어 | U11.EvidenceSessionRepository, U11.EvidenceChatController |
| NFR-P6 스트리밍 우선·비동기 잡 | U11.EvidenceChatController(SSE), U11.EvidenceJobService |
| QT-8 근거형성 근거화·불변식 | U11.EvidenceExtractor(C-2·FR-5), U11.EvidenceFormationService(D5 계약 테스트) |
| FR-30~35·NFR-P5/R3·QT-10 (novelty) [U12] | **별도 인셉션 사이클 — 컴포넌트 추적은 `construction/novelty-agent/functional-design/` 참조** (Evidence(U11) Tool 소비; novelty 전용 컴포넌트는 본 핵심 개요 밖) |
| FR-40~43·NFR-P7·QT-11 (Agent Chat Frontend) [U13] | U13.AgentRouteShell, AgentChatScreen, AgentModePicker, AgentSessionDrawer, AgentMessageList, AgentProgressTimeline, AgentComposer, AgentAttachmentDrawer, AgentTransportService, AgentChatReducer |

### 표준 QT / 스토리 커버리지 (비평 보강 반영)
| ID | 소유자 |
|---|---|
| **QT-1** 근거화 평가 | U6.GroundingEnforcementHook.runEvalSet |
| **QT-2** 관련도 평가 | U2.RelevanceRanker |
| **QT-3** 신뢰성/우아한 저하 평가 *(신설 소유자)* | **U6.ReliabilityEvalProbe.runReliabilityEvalSet**; 교차 트레이스: U2.HybridRetriever·U6.CostGuardCircuitBreaker·AiIncidentDetectorSuite.PartialResultDetector·U5.StateView |
| **QT-4 / PBT** 블로킹 ID | PBT-02 U2.QueryValidator.normalize(라운드트립); PBT-03 U2.RelevanceRanker(랭킹 순서 안정성); PBT-07 U2.HybridRetriever/U1.SourcePriorityDeduplicationGuard(디덥 불변식); PBT-08 U1.DocModelBlockChunker/U1.CorpusIndexWriter(멱등); PBT-09 U2.ResultAssembler·U4.UserDataDTOAndValidation(DTO 라운드트립) |
| **QT-9** U1 Corpus 품질/불변식 | U1.SourcePriorityDeduplicationGuard, U1.DocModelBuildCoordinator, U1.DocModelBlockChunker, U1.CorpusIndexWriter, U1.CorpusRefreshScheduler |
| **US-I1** Corpus 인제스천·인덱싱 *(U1 Corpus 개정)* | **U1.IngestionPipelineService·CorpusIndexWriter·CorpusRefreshScheduler.triggerBackfill/triggerRebuild** |
| **US-H1** 히어로 *(홈 정정)* | **U5.SearchScreen·AppShell**(프런트 표면), U2.QueryIntakeController(백킹 경로) |

> **RES-1 팬텀 트레이스 제거**: U1 source adapter 계층의 RES-1(워크로드 중요도·의존성 맵 문서화)을 삭제. 유효 트레이스(FR-6/C-1/RES-8/RES-9) 유지.

---

## 6. 참조 문서
- [`components.md`](./components.md) — 유닛별 컴포넌트 정의·책임·인터페이스·trace
- [`component-methods.md`](./component-methods.md) — 메서드 시그니처·목적·입출력(상세 규칙은 Functional Design)
- [`services.md`](./services.md) — 서비스 정의·책임·오케스트레이션(동기 vs 이벤트)
- [`component-dependency.md`](./component-dependency.md) — 의존성 매트릭스·통신 패턴·데이터 흐름·ASCII 흐름도
- [`agent-chat-frontend-components.md`](./agent-chat-frontend-components.md) — U13 Agent Chat Frontend 컴포넌트
- [`agent-chat-frontend-component-methods.md`](./agent-chat-frontend-component-methods.md) — U13 메서드·view model
- [`agent-chat-frontend-services.md`](./agent-chat-frontend-services.md) — U13 프론트 서비스 경계
- [`agent-chat-frontend-component-dependency.md`](./agent-chat-frontend-component-dependency.md) — U13 의존성·데이터 흐름

---

## 7. 2026-09-19 F01-F13 교정 통합 개정

> **SUPERSEDED - 2026-09-19 UQRF1=B**: 아래 RQ1=A 기반 planning-overlay 설계는 이력으로 보존하지만 현재 구현 권위가 아니다. 사용자가 REM-1~REM-4를 장기 독립 deployable services로 선택해 Workflow Planning과 Application Design을 재개했다. 새 Application Design 승인 전 이 절로 코드를 생성하지 않는다.
>
> **우선순위**: 이 절은 승인된 single-Mac production 재기준과 `verification-remediation-2026-09-18.md`에 한해 상단의 greenfield/기술-불가지 가정을 대체한다. 현재 runtime은 Cloudflare Tunnel -> Next.js BFF -> FastAPI, launchd, OrbStack data plane, local Ollama다. 본 절은 설계 완료 상태이며 runtime 결함 해소를 선언하지 않는다.

### 7.1 잠금된 교정 설계 결정

| 결정 | 확정안 | 설계 결과 |
|---|---|---|
| RQ1=A | 기존 도메인 패키지 소유 + 최소 shared/build 경계 | 새 runtime remediation service/deployable 없음. ordered migration registry, offline contract generator, supply-chain verifier만 공통 경계로 둔다. |
| RQ2=A | public route는 `userdoc:` 거부, private read는 owner context 전용 | public paper controller와 `UserDocModelCoordinator`를 분리하고 범용 private document endpoint를 만들지 않는다. |
| RQ3=A | 기존 `pending` + repeat-request polling 유지 | canonical source/cache identity 기반 durable job marker를 내부 추가하되 public `jobId` endpoint는 추가하지 않는다. |
| RQ4=A | immutable durable purge manifest | SQL 삭제 전에 object/cache/row inventory를 동결하고 같은 manifest/stage에서 재개한다. |
| RQ5=A | BFF canonical identity + loopback-only backend trust | JSON/PDF/SSE가 공통 edge helper를 사용하고 FastAPI는 raw socket peer가 loopback일 때만 private header를 수용한다. |
| RQ6=A | standalone corpus audit/repair + report-only readiness | startup/readiness는 corpus를 수정하지 않는다. targeted repair와 full rebuild는 자동 fallback이 아니다. |
| RQ7=A | explicit ordered migration registry | startup/CLI가 같은 registry/ledger IDs를 사용하고 repository 자동 discovery는 completeness test에만 사용한다. |

### 7.2 Remediation unit과 소유 경계

| Unit | Finding | 기존 소유 경로 | 핵심 설계 경계 |
|---|---|---|---|
| **REM-1 Platform and Contract Integrity** | F06, F08, F13 | `shared`, `backend.migrations`, frontend generation, locks/CI/images/ops preflight | ordered migration SSOT, offline atomic build-consumed binding generation, runtime/lock/image/SBOM gate |
| **REM-2 Private Content and Generation** | F01, F02, F05, F07 | summarization, user_docmodel, discovery metadata port, BFF binary path, frontend viewer | deny-by-default namespace, canonical source identity, durable repeat-poll job state, authenticated same-origin stream |
| **REM-3 Owner Lifecycle and Edge Trust** | F04, F09, F10 | accounts purge, owner-domain registrations, trends, BFF, ingress middleware/rate limiters | immutable purge manifest, token-authorized exact public mutation, one spoof-resistant client identity |
| **REM-4 Corpus and Search Integrity** | F03, F11, F12 | ingestion audit/repair, ops readiness, discovery assembler/eval, frontend state | read-only generation audit, approval-gated repair, degraded-empty preservation, generation-bound relevance policy |

### 7.3 Finding -> component/service traceability

| Finding | Component owner | Service/data-flow realization |
|---|---|---|
| F01 | PublicPaperNamespacePolicy, UserDocModelCoordinator | public path rejects private namespace; authenticated owner-context path validates bound ref before read |
| F02 | CanonicalSummarySourceResolver | canonical server source and content digest are resolved before cache/job identity; client source cannot determine shared output |
| F03 | ProductionSeedGuard, CorpusIntegrityAuditor, CorpusRepairCoordinator, CorpusReadinessProvider | fixture fence -> read-only report -> verified backup/exact manifest -> approved candidate generation/cutover/rollback |
| F04 | OwnerPurgeRegistry, PurgeManifestRepository, OwnerPurgeCoordinator | inventory commit precedes deletion; object/cache and SQL stages resume from one immutable manifest; residue/non-owner checks gate completion |
| F05 | SummaryGenerationJobRegistry | cache miss creates/reads durable marker, records enqueue/worker terminal state, and returns existing pending/repeat-poll contract |
| F06 | RuntimeSupplyChainVerifier | deploy-unit runtime/lock/advisory/image/SBOM checks block build/deploy on unapproved critical/high findings |
| F07 | AuthenticatedPaperAssetController, SameOriginAssetProxy | same-origin authenticated stream with backend-only storage key, public namespace/license/manifest checks, restrictive CSP |
| F08 | OrderedMigrationRegistry | startup and CLI consume identical ordered specs; duplicate/missing/unregistered identity fails before DB mutation |
| F09 | DigestUnsubscribeController, DigestLinkTokenVerifier | actual `/paper/{id}` links; exact public unsubscribe path; expiring versioned token and conditional settings update |
| F10 | EdgeClientIdentityForwarder, TrustedClientIdentityResolver | Cloudflare IP validation/overwrite at BFF; loopback-only trust and shared request identity at FastAPI |
| F11 | ResultAssembler, SearchStateClassifier | known degradation/provenance survives zero results and is rendered separately from normal no-match |
| F12 | RelevanceFloorEvaluator, RelevanceFloorPolicy | verified generation evaluation -> shadow -> approved generation/model-bound floor -> no-match/abstain enforcement |
| F13 | OfflineContractBindingGenerator | all local refs resolved offline; any failure is non-zero; generated tree covers every build-consumed contract |

### 7.4 Critical sequencing and execution gates

1. REM-1 establishes migration/contract/runtime integrity before schema and data changes.
2. REM-2 blocks public private-data access before correcting source/cache identity, durable generation, and asset delivery.
3. REM-3 consumes the complete schema/object inventory for purge, then fixes digest and edge identity.
4. REM-4 fences production fixtures and preserves degraded-empty before corpus audit/repair and relevance calibration.
5. All code changes require failing example regressions first; state/cache/registry/authorization transitions also receive applicable Full-mode property tests.
6. Live mutation requires isolated stores, verified backup/restore, exact dry-run counts/hash, rollback command, and post-change invariants.
7. Full corpus rebuild, bulk reparse/reembed, or unplanned alias cutover remains blocked pending separate explicit approval.

### 7.5 Application Design extension compliance

이 표는 **설계 산출물의 규칙 반영**을 평가한다. 실제 runtime compliance는 Code Generation과 Build and Test 이후에만 판정한다.

#### Security Full

| Rule | Status | Application Design evidence |
|---|---|---|
| SECURITY-01 | Compliant | private objects/backups remain behind storage adapters; encryption verification is assigned to NFR/Infrastructure gates. |
| SECURITY-02 | Compliant | F10 defines one validated edge identity and request-scoped audit/access-log identity. |
| SECURITY-03 | Compliant | purge/job/repair/dependency flows expose structured state/error references without private payload logging. |
| SECURITY-04 | Compliant | F07 uses authenticated same-origin streaming and removes direct object-storage browser dependency. |
| SECURITY-05 | Compliant | namespace, token, IP, asset ID, migration spec, manifest, schema ref inputs have explicit validators. |
| SECURITY-06 | Compliant | storage, migration, repair, CI/SBOM responsibilities are separated into least-privilege adapters/pipelines; concrete permissions defer to Infrastructure Design. |
| SECURITY-07 | Compliant | Cloudflare/BFF/FastAPI and loopback data-plane trust boundaries are explicit; non-loopback internal-header trust is prohibited. |
| SECURITY-08 | Compliant | context-bound private reads and manifest-complete owner purge are deny-by-default; non-owner responses are generalized. |
| SECURITY-09 | Compliant | production seed guard, object-key non-disclosure, report-only readiness, and approved repair path prevent test/debug leakage. |
| SECURITY-10 | Compliant | frozen lock, critical/high audit, digest pin, SBOM, evidence/expiry exception gate has a single verifier owner. |
| SECURITY-11 | Compliant | spoof-resistant canonical client identity feeds both gateway and accounts abuse limiters. |
| SECURITY-12 | Compliant | existing authentication remains required; unsubscribe is an exact-path, token-authorized narrow exception. |
| SECURITY-13 | Compliant | canonical source/cache identity and offline fail-closed contract generation protect data/contract integrity. |
| SECURITY-14 | Compliant | durable purge/job/repair stages and dependency exceptions expose auditable transitions and ownership. |
| SECURITY-15 | Compliant | invalid namespace, stale policy/report, enqueue failure, registry drift, degraded-empty, and missing signing/runtime config fail closed. |

#### Resiliency Custom Single-Mac Profile

| Rule | Status | Application Design evidence |
|---|---|---|
| RESILIENCY-01 | Compliant | four remediation units and their critical dependencies/owners are explicit. |
| RESILIENCY-02 | Compliant | immutable purge/repair manifests and verified backup references support approved RPO/RTO recovery. |
| RESILIENCY-03 | Compliant | lock/schema/migration/data changes retain reviewable, unit-ordered change boundaries. |
| RESILIENCY-04 | Compliant | migration rollback, atomic generated tree, purge resume, alias rollback, and deploy blocking gates are designed. |
| RESILIENCY-05 | Compliant | job/purge/corpus/dependency state and readiness reasons have observability surfaces. |
| RESILIENCY-06 | Compliant | corpus readiness reads generation-bound audit evidence; runtime and storage health remain separately probed. |
| RESILIENCY-07 | Compliant | stale audit, backup failure, queue/job terminal failure, advisory expiry, and policy mismatch are alertable conditions. |
| RESILIENCY-08 | N/A | user-approved single-Mac single fault domain; no multi-zone/multi-region component is introduced. |
| RESILIENCY-09 | N/A with compliant replacement | horizontal autoscaling is replaced by bounded worker concurrency, queue backpressure, visibility leases, and saturation/capacity gates. |
| RESILIENCY-10 | Compliant | end-to-end generation and stream paths have durable async/timeout/visibility isolation boundaries. |
| RESILIENCY-11 | Compliant | backup-first repair and manifest-based rollback align with the single-host restore strategy. |
| RESILIENCY-12 | Compliant | owner-private objects, SQL, cache, and corpus generation are included in backup/restore-aware flows. |
| RESILIENCY-13 | Compliant | runtime manifest/preflight and report/manifest rollback inputs support reinstall/restore/traffic-resume runbooks. |
| RESILIENCY-14 | Compliant | purge stage, worker retry, migration rollback, restore, repair cutover, and identity spoof fault tests have explicit seams. |
| RESILIENCY-15 | Compliant | F01-F13 correction ownership, audit transitions, stop conditions, and residual rebuild gate are explicit. |

#### Property-Based Testing Full

| Rule | Status | Application Design evidence |
|---|---|---|
| PBT-01 | N/A at Application Design | Enforcement begins in Functional Design. This amendment identifies cache/job identity, authorization, purge, migration, token, degradation, and relevance surfaces to analyze there. |
| PBT-02 | N/A at Application Design | Enforcement begins in Code Generation. Schema bindings, source identity, token, manifests, and reports are carried forward as round-trip candidates. |
| PBT-03 | N/A at Application Design | Enforcement begins in Code Generation. Owner isolation, preservation, monotonic stages, degradation, and generation binding are carried forward as invariants. |
| PBT-04 | N/A at Application Design | Enforcement begins in Code Generation. Migration reapply, job redelivery, purge resume, unsubscribe repeat, and repair rollback are identified idempotency surfaces. |
| PBT-05 | N/A at Application Design | Enforcement begins in Code Generation. Migration order, purge coverage, fixture classification, and floor selection expose model/oracle seams. |
| PBT-06 | N/A at Application Design | Enforcement begins in Code Generation. Migration/job/purge/repair transitions expose stateful model seams. |
| PBT-07 | N/A at Application Design | Enforcement begins in Code Generation. Owner/resource/object key/IP/schema/corpus record domain inputs are identified for reusable generators. |
| PBT-08 | N/A at Application Design | Enforcement begins in Code Generation/Build and Test. Fixed or logged seeds and shrinking remain binding downstream requirements. |
| PBT-09 | N/A at Application Design | Enforcement occurs in NFR Requirements. Existing Hypothesis and fast-check choices will be reconfirmed there. |
| PBT-10 | N/A at Application Design | Enforcement begins in Code Generation. Every F01-F13 path already carries a focused example-regression requirement downstream. |

### 7.6 상세 문서

- [`components.md`](./components.md#2026-09-19-f01-f13-교정-컴포넌트-개정) - remediation component ownership and responsibilities.
- [`component-methods.md`](./component-methods.md#2026-09-19-f01-f13-교정-메서드-개정) - high-level method contracts and input/output types.
- [`services.md`](./services.md#2026-09-19-f01-f13-교정-서비스-개정) - orchestration, sync/event/build-time boundaries, stop gates.
- [`component-dependency.md`](./component-dependency.md#2026-09-19-f01-f13-교정-의존성-개정) - dependency matrix, prohibited edges, remediation data flows, acyclicity.

---

## 8. 2026-09-19 Deployable Services and Public Jobs

**상태**: Application Design 산출물 승인 완료 - DAD1=A (2026-09-19). 승인 기록은 `../plans/application-design-plan.md` DAD1이다.
**권위 입력**: UQRF1=B, WPR2=A, DSRQ1/2/3/5/6/7=A, DSRQ4=C, DSRQF1/2=A, RJR1=A 요구사항 및 RJS2=A story/persona.
**범위**: F01~F13과 FR-52/NFR-R4/QT-12/C-13/RJ-AC01~12. 기존 product/domain business authority를 유지하면서 네 REM의 독립 배포/운영 및 사용자 job 계약을 정의한다.

### 8.1 결정의 실현

| 결정 | 설계 실현 |
|---|---|
| 네 장기 service / DSRQ1=A | REM-1~4 각각 독립 versioned artifact와 launchd daemon/worker/허용 one-shot 역할. 기존 BFF/API/domain/ingestion 배포가 함께 연계됨 |
| Domain authority / DSRQ2=A | U1~U16이 business rule/schema/data 의미를 소유하고 REM이 transport/orchestration/운영 state를 소유. REM-3는 다른 domain 데이터의 일반 writer가 아님 |
| Physical share / DSRQ3=A | Postgres/Redis/OpenSearch/MinIO/ElasticMQ를 물리 공유하되 logical realm/credential/single-writer와 domain read/maintenance 계약으로 분리 |
| Public jobs / DSRQ4=C + DSRQF1=A | REM 이관 업무 read/명시적 status를 job으로 접수하고 U5 UI가 접수/완료/실패를 구분. 캐시 hit도 cache-backed job으로 처리 |
| Direct exceptions / DSRQF2=A | 접수 확인, SSE 구독/재연결, 준비된 result/asset bytes, health/evidence는 새 업무 job 없는 bounded 직접 경로 |
| Delegated identity / DSRQ5=A | service identity + 짧은 audience-bound envelope. 실행/전달에는 현재 source grant/resource/owner epoch를 재검증하며 old queue credential 재사용 금지 |
| Gateway/versioned cutover / DSRQ6=A | Cloudflare -> BFF -> gateway -> 고정 REM route. 신구 계약을 지원하는 artifact/worker 조합과 단일 writer epoch로 수동 전환 |
| REM-1 authority / DSRQ7=A | read-only evidence daemon과 별도 명시적 runner. startup은 registry/compatibility 검증만 수행하고 migration/dependency repair/promotion을 자동 시작하지 않음 |

### 8.2 Service 및 기존 domain 관계

- **REM-1**: F06/F08/F13의 platform evidence와 승인된 tooling/runner. 기존 shared/domain schema와 ordered registry의 의미를 재정의하지 않고 동일한 검증 artifact를 build/startup/CLI가 소비한다.
- **REM-2**: public/private namespace 분리, owner-context content jobs, canonical cache/generation, 인가된 SSE/result/asset 전달. U1 source writer와 U11/U12 context authority를 유지하고 U7 생성 writer는 전환된 namespace에서 REM-2에 단일화한다.
- **REM-3**: U3 직접 비활성화 이후의 purge saga, U15 suppression 접수 및 목적 한정 consent 반영, versioned edge policy. U3 계정/session 직접 제어와 U15 canonical settings writer를 유지한다.
- **REM-4**: read-only corpus audit/calibration/report와 승인된 U1 repair runner. 일반 검색/저하/정책 집행은 U2/U5/U6의 기존 경계에서 수행한다.
- **EDGE/UI**: 기존 BFF/gateway 및 frontend가 public admission, queued status, 직접 결과/관측을 묶는다. 기존 전체 agent lifecycle을 이관하지 않고 REM 하위 작업에만 적용한다.

### 8.3 핵심 경계와 일관성

1. **Operation과 artifact를 분리한다.** caller별 job/observer 권한은 shared canonical artifact와 별도다. source identity는 server가 고정하며 같은 source를 재사용해도 다른 caller의 job metadata는 공유하지 않는다.
2. **접수와 완료를 분리한다.** operation/outbox durable commit 이후의 202는 접수 증거다. queue ack/연결 성공은 실행 완료가 아니며 결과는 fenced publication 후에만 관측된다.
3. **Status query와 관측을 분리한다.** 명시적 status는 queued 작업의 시점별 결과다. SSE/reconnect/result는 이미 publish된 정보만 전달하며 query-of-query 또는 model 재실행을 유발하지 않는다.
4. **현재 권한을 재검증한다.** authoritative current head와 immutable domain projection을 함께 읽는다. 오래된 event snapshot/accepted row/service identity만으로 user 권한을 재발급하지 않는다. 권한 확인 불가는 fail closed다.
5. **즉시 보호와 비동기 정리를 분리한다.** 계정 비활성화/session 철회는 U3 직접 제어, 해지 suppression은 R3C의 durable 접수 경계다. 후속 purge/consent 반영은 목적 한정 System grant로 수행하되 일반 사용자/observer 권한을 연장하지 않는다.
6. **파기 완료 전에 write가 정지됐음을 증명한다.** domain executor의 quiescence/receipt와 zero-residue, coordinator 자체 control-data 정리를 요구한다. lease 만료나 command 전송만으로 파기 완료를 선언하지 않는다.
7. **독립 배포와 business ownership은 별개다.** source imports 및 synchronous call은 계층 DAG로 제한한다. async command/receipt/publication은 의도된 feedback이며 명시적 parent/version/grant에 결속된다.

### 8.4 장애, 복구 및 배포

- `components.md`에 REM-1 High, REM-2/3 Critical, REM-4 High의 중단 영향을 정의했다. 단일 host/NFR-A1 best-effort와 RES-2 RPO ≤24h/수 시간 RTO를 계승하며 다중 AZ나 자동 host failover를 주장하지 않는다.
- queue 장애는 durable operation/outbox에서 복구하고, current authority 장애는 private 실행/전달을 차단한다. health/evidence는 queue와 독립적으로 bounded 응답한다. 처리 불능/호환 실패는 terminal 또는 명시적 보류이며 silent success/drop이 아니다.
- service별 frozen artifact/credential/역할을 정의하고, 기존 editable 경로를 독립 release 보증으로 사용하지 않는다. schema 확장 -> supported consumer/worker -> 검증된 frontend/BFF -> route 전환 순서와 진행 중 job 복구를 G0~G5로 검증한다.
- rollback은 동일한 owner/source/삭제/해지 보호를 만족하는 artifact와 writer epoch로만 수행한다. 이전의 취약 경로로 자동 fallback하지 않는다.
- 새 operation/event/result/manifest/control data는 backup/restore/retention/owner purge에 포함한다. full corpus rebuild, bulk reparse/reembed 및 live alias cutover는 별도 명시 승인 대상이다.

### 8.5 F01~F13 추적성

| Finding | Component | Orchestration / 검증 표면 |
|---|---|---|
| F01 | R2A, AUTH, DELIVERY | DS-2/3/4; public `userdoc:` 거부, owner context/current grant, 일반화 404 |
| F02 | R2W, RK, EXEC | DS-2; canonical source/version/digest 고정, source-bound cache, caller job 격리 |
| F03 | R4A, R4R, SEARCH, OBS | DS-7; production fixture fence, source/completeness report, 승인된 exact repair |
| F04 | R3P, EXEC, AUTH | DS-4/5; complete registry, quiescence, manifest/receipt, residue/control-data cleanup |
| F05 | RK, R2W, EDGE, UI | DS-2/3/8; durable 접수, bounded worker, HTTP와 분리된 결과 전달 |
| F06 | R1R, R1C | DS-1; patched locks, audit/pin/SBOM, frozen artifact/예외 만료 |
| F07 | DELIVERY, EDGE, AUTH | DS-3; 현재 owner/license, prepared asset manifest, same-origin bytes/CSP |
| F08 | R1R, R1C | DS-1; single ordered registry와 ledger, 명시 runner apply/startup 검증 동치 |
| F09 | R3C, EXEC, EDGE | DS-6; expiring token, 실제 `/paper/{id}`, exact public scope, 즉시 suppression |
| F10 | R3E, EDGE, AUTH | DS-7; trusted origin/BFF hop, canonical client identity, 접수 전 동일 limiter identity |
| F11 | SEARCH, UI, DELIVERY | DS-3/7; 0건에도 degradation/provenance 및 domain outcome 보존 |
| F12 | R4A, SEARCH | DS-7; verified generation/eval report, shadow/approved floor 및 no-match |
| F13 | R1R, EDGE, UI | DS-1; local refs offline, all-or-nothing generation, 실제 Python/TS build-consumed drift |

### 8.6 RJ-AC 및 story 추적성

| 인수 | Component / flow | Story / checkpoint |
|---|---|---|
| RJ-AC01 | EDGE/R2A/R3C/RK, DS-2/6 | US-RJ1, G2/G4: durable 접수와 실패/불확정 구분 |
| RJ-AC02 | RK/R2W/DELIVERY, DS-3 | US-RJ1/2, G0/G2/G4: queued status 및 비재귀 결과 |
| RJ-AC03 | UI/SEARCH/RK, DS-2/3/7 | US-RJ1/US-S5/US-R2, G4: terminal/domain outcome |
| RJ-AC04 | DELIVERY/UI, DS-3/8 | US-RJ2, G2/G4: replay/reconnect/order/expiry |
| RJ-AC05 | AUTH/EDGE/DELIVERY/EXEC, DS-4 | US-RJ3, G2/G3/G4: 현재 권한/비노출 |
| RJ-AC06 | RK/R2W/DELIVERY, DS-2/3 | US-RJ1/3, G2/G3: 같은 제출 멱등성, caller 격리 |
| RJ-AC07 | R2W/EXEC, DS-2 | US-S1/2/5, G2/G4: canonical cache-backed job |
| RJ-AC08 | DELIVERY/EDGE/AUTH, DS-3 | US-RJ3/US-S3, G2/G4: 직접 결과/bytes, same-origin |
| RJ-AC09 | R3P/EXEC/AUTH, DS-5 | US-A6/US-EV8, G3/G5: late write 차단/전체 파기 |
| RJ-AC10 | R3C/EXEC/DELIVERY, DS-6 | US-TN2, G3/G4: 목적 제한 observer와 suppression |
| RJ-AC11 | EDGE/AUTH/EXEC, DS-4/7 | US-RJ1/US-A6, G3/G4: 직접 인가/계정/session 보호 |
| RJ-AC12 | RK/OBS 및 모든 service, DS-8 | US-RJ2/US-R2/4/5, G2/G4/G5: crash/queue loss/복구/직접 health |

### 8.7 Application Design 확장 준수

아래는 새 설계의 책임/경계/검증 seam을 평가한다. 실제 설정과 runtime 검증은 per-service Construction에서 수행한다.

| Security 규칙 | 상태 | 설계 근거 |
|---|---|---|
| SECURITY-01 | Compliant | store/backup adapter가 operation/event/result/source의 at-rest encryption 및 TLS 경계 담당; NFR/Infrastructure/G5로 연결 |
| SECURITY-02 | Compliant | EDGE의 origin/client identity 및 BFF/gateway/service listener access logging 책임 |
| SECURITY-03 | Compliant | OBS의 correlation/structured redacted log; token/key/private payload queue/log 비노출 |
| SECURITY-04 | Compliant | EDGE/UI의 same-origin event/asset, safe header/CSP 및 private no-shared-cache |
| SECURITY-05 | Compliant | 고정 route/kind/version, namespace/context/token/cursor/manifest 검증, typed ports |
| SECURITY-06 | Compliant | domain별 ordinary writer와 purpose-bound maintenance, daemon/runner/observer credential 분리 |
| SECURITY-07 | Compliant | browser->BFF->gateway만 공개; private service/store와 고정 routing; 임의 proxy target 금지 |
| SECURITY-08 | Compliant | AUTH의 current grant와 전 경계 object 검증, private 비노출, exact token observer scope |
| SECURITY-09 | Compliant | production seed/default key/debug fallback 차단, 일반화 오류 및 내부 locator 비노출 |
| SECURITY-10 | Compliant | R1R의 lock/pin/audit/SBOM/예외 expiry 및 재현 artifact gate |
| SECURITY-11 | Compliant | EDGE의 접수 전 identity/rate-limit, RK의 status 재귀/중복/용량 보호 |
| SECURITY-12 | Compliant | 짧은 signed delegation과 현재 source grant 재검증, U3 session 철회, operator/system 목적 구분 |
| SECURITY-13 | Compliant | canonical SourceIdentity, fenced publication, immutable manifest/receipt/report 및 offline bindings |
| SECURITY-14 | Compliant | OBS의 권한/queue/backup/worker/정책 경보와 추가 전용·비식별 완료 감사 |
| SECURITY-15 | Compliant | authority/접수 불확정/호환 실패의 fail-closed, stream cleanup, 명시적 오류/terminal 상태 |

| Resiliency 규칙 | 상태 | 설계 근거 |
|---|---|---|
| RESILIENCY-01 | Compliant | component 배포/중요도/중단 영향과 sync/async dependency matrix |
| RESILIENCY-02 | Compliant | 기존 NFR-A1/RES-2 목표를 네 service와 새 persistent state에 연결 |
| RESILIENCY-03 | Compliant | 기존 GitHub review/git-flow, domain owner/shared contract sign-off 경계 |
| RESILIENCY-04 | Compliant | CompatibilityManifest, independent artifacts, writer epoch 및 진행 중 job 보존 rollback |
| RESILIENCY-05 | Compliant | OBS 단계별 latency/trace/log 및 UI 접수/완료 구분 |
| RESILIENCY-06 | Compliant | queue 독립 shallow/deep/compatibility health와 synthetic probe 경계 |
| RESILIENCY-07 | Compliant | queue/result lag, 미확정 write, stale policy/report, backup와 saturation 관측 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | horizontal autoscale N/A; bounded admission/worker/observer/health 격리 및 backpressure |
| RESILIENCY-10 | Compliant | 긴 작업은 durable async, source/model/stream의 bounded I/O 및 직접 safety control 격리 |
| RESILIENCY-11 | Compliant | 기존 backup-and-restore 전략과 명시 repair/rollback 흐름 |
| RESILIENCY-12 | Compliant | operation/outbox/event/result/manifest의 backup/retention/purge 및 verified restore 입력 |
| RESILIENCY-13 | Compliant | consumer/operation 재조정, domain receipt resume, artifact/schema-aware 복구 순서 |
| RESILIENCY-14 | Compliant | 권한 철회/crash/redelivery/quiescence/partial deploy/reconnect 및 restore 검증 seam |
| RESILIENCY-15 | Compliant | OBS/OP/RES-11 COE, 실패 기록과 별도 corpus gate의 명시적 잔여 판정 |

| PBT 규칙 | 단계 적용 | 후속 설계/검증 표면 |
|---|---|---|
| PBT-01 | N/A - Application Design | Functional Design에서 operation/authority/consent/purge/report property 식별 |
| PBT-02 | N/A - Application Design | typed job/event/grant/manifest/schema round-trip |
| PBT-03 | N/A - Application Design | owner 격리, terminal/namespace/source/fence/generation 불변식 |
| PBT-04 | N/A - Application Design | submit/redelivery/publication/consent/purge/migration 멱등성 |
| PBT-05 | N/A - Application Design | registry/현재 권한/상태/consent/ref classifier reference model |
| PBT-06 | N/A - Application Design | admit/revoke/write/purge/reconnect/dispatch/rollback 시퀀스 |
| PBT-07 | N/A - Application Design | purpose/owner/job/version/cursor/context/manifest domain generator |
| PBT-08 | N/A - Application Design | downstream shrinking/seed 재현성 및 CI 실패 보존 |
| PBT-09 | N/A - Application Design | NFR Requirements의 기존 Hypothesis/fast-check service별 적용 |
| PBT-10 | N/A - Application Design | F01~F13/RJ-AC01~12 예시 회귀와 property 병행 |

### 8.8 상세 문서와 Construction 이월

- `components.md` 동명 절: 17개 component, 네 deployable 및 canonical owner/ordinary writer/privileged executor 배치.
- `component-methods.md` 동명 절: public/internal route, actor/operation/result/authority 타입과 typed port, HTTP/SSE 및 command/receipt 의미.
- `services.md` DS-1~8: durable 접수/publication, current authority, queued status/직접 전달, purge/consent barrier, platform/corpus 및 장애/전환 흐름.
- `component-dependency.md` 동명 절: source/sync DAG, 의도된 async feedback, data-flow diagrams/text 및 금지 edge.
- Functional Design은 상세 state machine/schema, idempotency key, projection/fence/consent의 transaction·quiescence 증명과 삭제 순서를 명세한다. NFR/Infrastructure는 TTL/보존/timeout/자원·crypto/TLS·origin proof/credential·port/launchd/backup 배치를 확정한다.
- 이들 세부 사항이 구현·검증돼야 WPR2 G1~G5를 통과할 수 있다. 설계 승인 이후 Units Generation에서 REM/product owner/story/finding을 매핑하고 각 Construction loop로 진행한다.
