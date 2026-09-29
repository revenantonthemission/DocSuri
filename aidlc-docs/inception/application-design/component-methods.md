# component-methods.md — 메서드 시그니처 (Application Design)

> **현재 승인 설계**: 하단 `2026-09-19 Deployable Services and Public Jobs`가 DAD1=A로 승인된 service/public job 계약이다. 기존 superseded 메서드는 이력으로 보존한다.

> 시그니처 + 목적 + 입출력 타입만 기술한다. **상세 비즈니스 규칙은 Functional Design 산출물**에서 명시한다.
> 잠금 결정 준수: 사용자向 디스커버리 READ는 동기(DQ6), 인제스천/운영 백본은 이벤트(DQ3/DQ6).

## 비평 반영 요약 (이 문서 관련)
- U2 `GroundingAbstainEnforcer.enforce` 제거 → 얇은 `GroundingAdapter`의 `toGroundingInput`/`mapDecision`으로 대체(독자 강제 없음).
- U2 `SearchOrchestrationService.publishSearchExecuted` **신설** — FR-10 이력 쓰기의 생산자 절반(SearchExecuted 발행).
- U6 `GroundingEnforcementHook.enforce`가 단일 권위 근거화 게이트 메서드.
- U6 `AuthnAuthzGuard.authorize`는 U3.AuthorizationGuard로 위임(재구현 아님).
- U6 `ReliabilityEvalProbe.runReliabilityEvalSet` 신설 — QT-3 평가 진입점.

---

## U1 — Ingestion

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| CorpusSourceAdapterSet | `fetchMetadataPage(source: SourceName, slice: CorpusSlice, cursor: PageCursor, sinceWatermark: Timestamp) -> MetadataPage` | 소스별 watermark 이후 메타데이터 페이지를 레이트 한도 준수 조회 | SourceName, CorpusSlice, PageCursor, Timestamp → MetadataPage{records[], nextCursor, hasMore} |
| CorpusSourceAdapterSet | `fetchFullTextCandidate(record: SourceMetadataRecord) -> FullTextCandidate \| RejectedRecord` | arXiv HTML 우선/PDF 폴백, Semantic Scholar/OpenAlex PDF 후보를 조회 | SourceMetadataRecord → FullTextCandidate{sourceTier, payloadRef, license} \| RejectedRecord{reason} |
| CorpusSourceAdapterSet | `sourceWatermark(source: SourceName) -> Watermark` | source별 incremental 기준점 조회 | SourceName → Watermark |
| FullTextExtractionProcessor | `extractFullText(candidate: FullTextCandidate) -> FullText \| RejectedRecord` | HTML 또는 transient PDF→GROBID 결과를 정규화 FullText로 변환 | FullTextCandidate → FullText{text, structureHints, provenance} \| RejectedRecord{reason} |
| FullTextExtractionProcessor | `validateLicense(candidate: FullTextCandidate) -> LicenseDecision` | OA/인덱싱 허용 여부를 fail-closed 판정 | FullTextCandidate → LicenseDecision{ALLOW \| REJECT, reason?} |
| FullTextExtractionProcessor | `normalizeSource(fullText: FullText) -> ParsedPaper` | 메타데이터+전문을 canonical ParsedPaper로 정규화 | FullText → ParsedPaper |
| SourcePriorityDeduplicationGuard | `deduplicate(records: Sequence[ParsedPaper]) -> DedupResult` | DOI → arXiv id → 정규화 title/author/year 순으로 중복 제거 | ParsedPaper[] → DedupResult{winners[], duplicates[]} |
| SourcePriorityDeduplicationGuard | `canonicalize(paper: ParsedPaper) -> CanonicalPaperRef` | canonical paperId/version/sourceTier 결정 | ParsedPaper → CanonicalPaperRef{paperId, version, sourceTier} |
| SourcePriorityDeduplicationGuard | `fingerprint(paper: ParsedPaper) -> ContentHash` | 변경 감지·멱등 키용 결정적 지문 생성 | ParsedPaper → ContentHash |
| DocModelBuildCoordinator | `buildDocModel(paper: ParsedPaper, ref: CanonicalPaperRef) -> DocModel` | 수집 시점 eager DocModel 완성형 생성 | ParsedPaper, CanonicalPaperRef → DocModel |
| DocModelBuildCoordinator | `storeDocModel(doc: DocModel) -> ObjectRef` | `(paperId, version)` 키로 DocModel 저장 | DocModel → ObjectRef |
| DocModelBuildCoordinator | `validateDocModel(doc: DocModel) -> ValidationResult` | schema roundtrip/negative validation과 provenance 검사 | DocModel → ValidationResult |
| DocModelBlockChunker | `chunkDocModel(doc: DocModel) -> ChunkSet` | DocModel Block 경계 기반 결정적 청크 생성 | DocModel → ChunkSet{chunks[] with blockId, sectionPath} |
| DocModelBlockChunker | `chunkId(paperId: PaperId, version: int, blockId: BlockId, ordinal: int) -> ChunkId` | version+Block 기반 멱등 chunk id 생성 | PaperId, int, BlockId, int → ChunkId |
| EmbeddingGatewayAdapter | `embedBatch(chunks: ChunkSet) -> EmbeddingBatch` | 청크 배치를 임베딩 게이트웨이로 벡터화(타임아웃·비용 텔레메트리 연동) | ChunkSet → EmbeddingBatch{vectors[] aligned to chunkId} |
| EmbeddingGatewayAdapter | `embeddingSchema() -> VectorSpec` | **공유 VectorSpec(차원·모델·거리 메트릭) 노출 — U2 reader와 동일 진실 원천 소비** | (none) → VectorSpec{dimensions, modelRef, distanceMetric} |
| CorpusIndexWriter | `prepareGeneration(spec: IndexGenerationSpec) -> IndexGenerationRef` | DocModel 기반 신규 index generation 생성 준비 | IndexGenerationSpec → IndexGenerationRef |
| CorpusIndexWriter | `upsert(records: IndexRecordBatch, generation: IndexGenerationRef) -> WriteResult` | 임베딩+lexical+DocModel Block anchor를 OpenSearch generation에 멱등 기록 | IndexRecordBatch, IndexGenerationRef → WriteResult{written, skipped, failed[]} |
| CorpusIndexWriter | `tombstone(paperId: PaperId, version: int, generation: IndexGenerationRef) -> WriteResult` | 철회/버전변경 논문 제거로 정합성 유지 | PaperId, int, IndexGenerationRef → WriteResult |
| CorpusIndexWriter | `indexStats(generation: IndexGenerationRef) -> IndexStats` | 인덱스 건강도·규모 통계와 cutover smoke 입력 제공 | IndexGenerationRef → IndexStats{docCount, vectorCount, lastWrite} |
| CorpusRefreshScheduler | `onSchedule(trigger: ScheduleTrigger) -> IngestionJob` | source별 증분 갱신 잡 생성·발행 | ScheduleTrigger → IngestionJob |
| CorpusRefreshScheduler | `advanceWatermark(source: SourceName, watermark: Timestamp) -> void` | 성공 처리 후 source watermark 단조 전진 | SourceName, Timestamp → void |
| CorpusRefreshScheduler | `triggerBackfill(scope: CorpusScope) -> IngestionJob` | phase-1 Corpus/backfill 잡 생성 | CorpusScope → IngestionJob |
| CorpusRefreshScheduler | `triggerRebuild(reason: RebuildReason) -> IngestionJob` | DocModel/index 재생성 잡 생성 | RebuildReason → IngestionJob |
| IngestFailureHandler | `classify(error: IngestError) -> FailureClass` | 오류를 재시도 가능/영구로 분류 | IngestError → FailureClass{RETRIABLE \| PERMANENT} |
| IngestFailureHandler | `scheduleRetry(item: IngestItem, attempt: int) -> RetryDecision` | 백오프·재시도 한도·쿼터 인지 재시도 결정 | IngestItem, int → RetryDecision{RETRY at delay \| EXHAUSTED} |
| IngestFailureHandler | `sendToDLQ(item: IngestItem, reason: FailureReason) -> void` | 소진/영구 실패 항목 DLQ 격리 | IngestItem, FailureReason → void |
| IngestFailureHandler | `emitFailureSignal(jobId: JobId, error: IngestError) -> void` | 실패를 관측성/경보 신호로 발행 | JobId, IngestError → void |

---

## U2 — Discovery/Search

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| QueryIntakeController | `search(request: SearchRequest, ctx: RequestContext) -> SearchResponse` | 동기 검색 진입: 검증→오케스트레이션→폰 DTO 직렬화. 종단 상태 명시 HTTP 매핑 | SearchRequest{query, options?}, RequestContext{authSession, degradationSignal, requestId} → SearchResultPageDTO \| AbstainDTO \| DegradedResultDTO \| ValidationErrorDTO |
| QueryValidator | `validate(rawQuery: string) -> ValidationResult` | FR-1/SEC-5 도메인 검증(길이·빈값·허용문자·새니타이즈) | string → ValidationResult{ok, reason?} |
| QueryValidator | `normalize(rawQuery: string) -> NormalizedQuery` | 결정적 정규화(트림·공백·유니코드)로 재현성 확보(PBT-02 라운드트립) | string → NormalizedQuery{text} |
| QueryUnderstandingExpander | `expand(query: NormalizedQuery, degradation: DegradationSignal) -> QueryPlan` | 질의를 임베딩 벡터+lexical 텀+필터 힌트로 확장; 저하 시 lexical-only(임베딩은 공유 VectorSpec 공간) | NormalizedQuery, DegradationSignal{llmEnabled, rerankEnabled} → QueryPlan{embeddingVector?, lexicalTerms, filterHints?, mode} |
| HybridRetriever | `retrieve(plan: QueryPlan, degradation: DegradationSignal) -> CandidateSet` | 벡터+lexical 후보 검색·병합·디덥(멱등, PBT-07); 장애 시 부분/폴백 | QueryPlan, DegradationSignal → CandidateSet{candidates[], retrievalMode} |
| RelevanceRanker | `rank(candidates: CandidateSet, plan: QueryPlan, degradation: DegradationSignal, topN: int) -> RankedResults` | 관련도순 상위 N 절단(순서 안정성 PBT-03); LLM 리랭킹 여부는 cost-circuit 결정 | CandidateSet, QueryPlan, DegradationSignal, int(제안 20) → RankedResults{ranked[], rankingMode} |
| **GroundingAdapter** | `toGroundingInput(results: RankedResults, plan: QueryPlan) -> GroundingInput` | **U6 근거화 후크 입력으로 후보+검색 레코드 정형화(독자 검사 없음)** | RankedResults, QueryPlan → GroundingInput{candidateResponse, retrievedRecords} |
| **GroundingAdapter** | `mapDecision(decision: GroundingDecision) -> GroundedResults \| AbstainResult` | **U6 후크 verdict를 종단 결과/기권으로 매핑(독자 차단·인시던트 발행 없음)** | GroundingDecision{verdict, violations[]} → GroundedResults{items[]} \| AbstainResult{reason} |
| ResultAssembler | `assemble(input: GroundedResults \| AbstainResult, degradation: DegradationSignal) -> SearchResponse` | 근거화 결과/기권을 폰 카드 DTO+상태 플래그로 조립(DTO 라운드트립 PBT-09) | GroundedResults \| AbstainResult, DegradationSignal → SearchResultPageDTO \| AbstainDTO \| DegradedResultDTO |

> **SearchOrchestrationService 메서드(서비스 레벨, services.md 참조)**: `executeSearch(...)` (동기 파이프라인 조정), **`publishSearchExecuted(userId, query, timestamp, resultCount) -> void`** — 성공 응답 후 `SearchExecutedEvent`를 이벤트 백본에 발행(FR-10 이력 쓰기 생산자, 비차단·P50<3s 경로 밖).

---

## U3 — Accounts/Auth

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| AccountController | `signup(req: SignupRequest, ctx: RequestContext) -> HttpResponse<SignupResult>` | 가입 요청 수신·검증·SignupService 위임·일반화 응답 | SignupRequest{email, password}, RequestContext{requestId, clientId} → HttpResponse<SignupResult{accountId}> \| 일반화 에러(409/400/429) |
| AccountController | `login(req: LoginRequest, ctx: RequestContext) -> HttpResponse<SessionCookie>` | 로그인 위임·성공 시 보안 세션 쿠키 설정 | LoginRequest{email, password}, RequestContext → HttpResponse w/ Set-Cookie(secure/httpOnly/sameSite) \| 인증 에러(401/429) |
| AccountController | `logout(ctx: AuthenticatedContext) -> HttpResponse<void>` | 현재 세션 서버측 무효화·쿠키 클리어 | AuthenticatedContext{principal, sessionHandle} → HttpResponse w/ cleared Set-Cookie |
| AccountController | `currentSession(ctx: AuthenticatedContext) -> HttpResponse<SessionInfo>` | 검증 세션 비민감 정보 반환(프런트 세션 동기화) | AuthenticatedContext{principal} → HttpResponse<SessionInfo{userId, expiresAt}> \| 401 |
| SignupService | `register(cmd: SignupCommand) -> Result<AccountId, SignupError>` | 정책·유일성 검증·해싱·영속·AccountCreated 발행 오케스트레이션 | SignupCommand{email, password, requestContext} → Result<AccountId, SignupError{POLICY_VIOLATION\|EMAIL_TAKEN\|BREACHED}> |
| AuthenticationService | `authenticate(cmd: LoginCommand) -> Result<IssuedSession, AuthError>` | 자격증명 검증·세션 발급, 실패 시 AuthFailureSignal 발행 | LoginCommand{email, password, requestContext} → Result<IssuedSession{token, cookieMaterial}, AuthError{INVALID_CREDENTIALS}> |
| AuthenticationService | `revoke(sessionHandle: SessionHandle) -> Result<void, AuthError>` | 로그아웃 시 세션 서버측 무효화 위임 | SessionHandle → Result<void, AuthError> |
| SessionManager | `issue(principal: Principal) -> IssuedSession` | 서버검증 세션 발급·보안 쿠키 머티리얼 생성 | Principal{userId} → IssuedSession{token, cookieMaterial, expiresAt} |
| SessionManager | `verify(token: SessionToken) -> Result<AuthenticatedPrincipal, SessionError>` | 토큰 서버측 검증해 주체 해석(fail closed) | SessionToken → Result<AuthenticatedPrincipal{userId, sessionHandle}, SessionError{INVALID\|EXPIRED}> |
| SessionManager | `invalidate(sessionHandle: SessionHandle) -> void` | 세션 서버측 즉시 무효화 | SessionHandle → void |
| SessionVerifier | `verifyRequest(rawToken: string, ctx: RequestContext) -> Result<AuthenticatedPrincipal, AuthRejection>` | 게이트웨이 요청별 인증 강제 시 경량 동기 검증 진입점 | string(쿠키/헤더), RequestContext → Result<AuthenticatedPrincipal, AuthRejection{UNAUTHENTICATED}> |
| **AuthorizationGuard** | `authorize(principal: Principal, action: Action, resourceOwner: UserId) -> Decision` | **객체 단위 소유권 인가 단일 권위 결정(기본 거부) — U6 게이트웨이·U4가 위임** | Principal, Action(enum), UserId → Decision{ALLOW\|DENY} |
| AuthorizationGuard | `authorizeAdmin(principal: Principal, action: AdminAction, mfaContext: MfaContext) -> Decision` | 관리자 역할+MFA 충족 결정 | Principal, AdminAction(enum), MfaContext{mfaVerified} → Decision{ALLOW\|DENY} |
| CredentialStore | `createCredential(accountId: AccountId, password: string) -> CredentialRef` | 적응형 해싱 자격증명 생성·영속(평문 미저장) | AccountId, password(평문, 비로깅) → CredentialRef{credentialId} |
| CredentialStore | `verifyCredential(email: string, password: string) -> CredentialVerification` | 상수시간 의도 검증·재해싱 필요 판정 | email, password(평문, 비로깅) → CredentialVerification{matched, principal?, needsRehash} |
| CredentialStore | `rehash(accountId: AccountId, password: string) -> void` | 노후 해시 파라미터 재해싱 | AccountId, password(평문, 비로깅) → void |
| PasswordPolicy | `evaluate(password: string, ctx: PolicyContext) -> PolicyResult` | 비밀번호 정책+유출 검사 평가 | password, PolicyContext{email?} → PolicyResult{ok, reasons[]} |
| SessionStore | `persist(record: SessionRecord) -> void` | 세션 레코드 영속 | SessionRecord{sessionHandle, userId, expiresAt} → void |
| SessionStore | `load(sessionHandle: SessionHandle) -> Option<SessionRecord>` | 세션 레코드 조회(서버측 검증용) | SessionHandle → Option<SessionRecord> |
| SessionStore | `remove(sessionHandle: SessionHandle) -> void` | 세션 레코드 삭제(무효화) | SessionHandle → void |

---

## U4 — Saved Searches & Library

> **rerun 메서드 주석**: `rerun`은 게이트웨이-프런티드 검색 계약(U6 ApiGatewayMiddleware 경유 → U2)을 통해 재실행한다. 직접 U2 모듈 호출이 아니며 근거화·비용·관측성 후크를 동일하게 통과한다.

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| SavedSearchController | `createSavedSearch(authCtx: AuthContext, body: SavedSearchCreateDTO) -> HttpResponse<SavedSearchDTO>` | 새 검색 저장 생성·반환(동기 REST) | AuthContext{userId}, SavedSearchCreateDTO{query + label?} → HttpResponse<SavedSearchDTO>(201) \| 검증/인가 오류 |
| SavedSearchController | `listSavedSearches(authCtx: AuthContext, page: PageParams) -> HttpResponse<SavedSearchPageDTO>` | 사용자 소유 저장 검색 최근순 목록 | AuthContext, PageParams{limit, cursor} → HttpResponse<SavedSearchPageDTO>(200) |
| SavedSearchController | `deleteSavedSearch(authCtx: AuthContext, savedSearchId: Id) -> HttpResponse<void>` | 소유 저장 검색 삭제(타 소유는 NotFound 일반화) | AuthContext, Id → HttpResponse<void>(204) \| 404 |
| SavedSearchController | `rerunSavedSearch(authCtx: AuthContext, savedSearchId: Id) -> HttpResponse<SearchResultSetDTO>` | 저장 질의로 게이트웨이-프런티드 검색 동기 재실행 | AuthContext, Id → HttpResponse<SearchResultSetDTO>(200, U2 위임) |
| LibraryController | `addLibraryItem(authCtx: AuthContext, body: LibraryItemCreateDTO) -> HttpResponse<LibraryItemDTO>` | arXiv 논문 라이브러리 멱등 추가 | AuthContext, LibraryItemCreateDTO{arXivId + 메타 스냅샷} → HttpResponse<LibraryItemDTO>(201/200 멱등) |
| LibraryController | `listLibrary(authCtx: AuthContext, page: PageParams) -> HttpResponse<LibraryPageDTO>` | 사용자 소유 라이브러리 목록 | AuthContext, PageParams → HttpResponse<LibraryPageDTO>(200) |
| LibraryController | `removeLibraryItem(authCtx: AuthContext, itemId: Id) -> HttpResponse<void>` | 소유 라이브러리 항목 삭제 | AuthContext, Id → HttpResponse<void>(204) \| 404 |
| SearchHistoryController | `listHistory(authCtx: AuthContext, page: PageParams) -> HttpResponse<HistoryPageDTO>` | 최근 검색 이력 목록 | AuthContext, PageParams → HttpResponse<HistoryPageDTO>(200) |
| SearchHistoryController | `rerunHistoryEntry(authCtx: AuthContext, historyId: Id) -> HttpResponse<SearchResultSetDTO>` | 이력 질의로 게이트웨이-프런티드 검색 동기 재실행 | AuthContext, Id → HttpResponse<SearchResultSetDTO>(200, U2 위임) |
| SearchHistoryController | `clearHistory(authCtx: AuthContext) -> HttpResponse<void>` | 사용자 이력 전체 삭제 | AuthContext → HttpResponse<void>(204) |
| SavedSearchService | `save(userId: Id, spec: SavedSearchSpec) -> SavedSearch` | owner-scoped 영속·감사 이벤트 발행 | userId, SavedSearchSpec{query + label} → SavedSearch |
| SavedSearchService | `list(userId: Id, page: PageParams) -> Page<SavedSearch>` | 사용자 소유 저장 검색 페이지 조회 | userId, PageParams → Page<SavedSearch> |
| SavedSearchService | `delete(userId: Id, savedSearchId: Id) -> void` | 소유권 확인 후 삭제·감사 발행 | userId, Id → void(미소유 시 NotFound) |
| SavedSearchService | `rerun(userId: Id, savedSearchId: Id) -> SearchResultSet` | 소유권 확인 후 저장 query를 게이트웨이-프런티드 검색으로 재실행 | userId, Id → SearchResultSet(U2 반환 타입) |
| LibraryService | `addItem(userId: Id, paperRef: PaperRef) -> LibraryItem` | (userId, arXivId) 멱등 추가·메타 스냅샷 보존 | userId, PaperRef{arXivId + 메타 스냅샷} → LibraryItem(신규/기존 멱등) |
| LibraryService | `list(userId: Id, page: PageParams) -> Page<LibraryItem>` | 사용자 소유 라이브러리 페이지 조회 | userId, PageParams → Page<LibraryItem> |
| LibraryService | `removeItem(userId: Id, itemId: Id) -> void` | 소유권 확인 후 삭제·감사 발행 | userId, Id → void(미소유 시 NotFound) |
| SearchHistoryService | `recordSearch(event: SearchExecutedEvent) -> void` | **U2 발행 SearchExecuted 이벤트 구독해 비동기 기록(NFR-P1 비차단)** | SearchExecutedEvent{userId, query, timestamp, resultCount} → void |
| SearchHistoryService | `list(userId: Id, page: PageParams) -> Page<SearchHistoryEntry>` | 사용자 소유 이력 최근순 조회 | userId, PageParams → Page<SearchHistoryEntry> |
| SearchHistoryService | `rerun(userId: Id, historyId: Id) -> SearchResultSet` | 소유권 확인 후 게이트웨이-프런티드 검색 동기 재실행 | userId, Id → SearchResultSet |
| SearchHistoryService | `clear(userId: Id) -> void` | 사용자 소유 이력 전체 삭제 | userId → void |
| UserDataRepository | `insert<T>(userId: Id, entity: T) -> T` | owner 키 강제 포함 영속화 | userId, entity → 영속 엔티티 |
| UserDataRepository | `findByOwner<T>(userId: Id, key: Id) -> Optional<T>` | 소유자 범위 단건 조회(타 소유자 비가시, SEC-8 백스톱) | userId, key → Optional<T> |
| UserDataRepository | `listByOwner<T>(userId: Id, page: PageParams) -> Page<T>` | 소유자 범위 최근순 페이지 조회 | userId, PageParams → Page<T> |
| UserDataRepository | `deleteByOwner<T>(userId: Id, key: Id) -> boolean` | 소유자 범위 삭제·실제 삭제 여부 반환 | userId, key → boolean |
| UserDataDTOAndValidation | `validateAndMap(raw: RawRequest, schema: DTOSchema) -> Result<DTO, ValidationError>` | SEC-5 검증·새니타이즈·DTO 매핑 | RawRequest, DTOSchema → Result<DTO, ValidationError> |
| UserDataDTOAndValidation | `toDTO(entity: DomainEntity) -> DTO` | 도메인 엔티티→외부 DTO(내부 필드 비노출) | DomainEntity → DTO |

---

## U5 — Mobile Web Frontend

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| AppShell | `render(route: RouteContext, session: SessionState): SSRHtml` | 라우트·세션에 맞춰 SSR 루트 레이아웃·화면 트리 렌더(히어로 골격 포함) | RouteContext, SessionState → SSRHtml |
| AppShell | `navigate(to: RoutePath): void` | 클라이언트 라우트 전환·보호 라우트 가드 | RoutePath → void |
| AppShell | `useSession(): SessionState` | 하위 화면에 인증/세션 상태 제공 | (none) → SessionState |
| PhoneMockupFrame | `wrap(children: ViewTree, viewport: ViewportClass): FramedView` | 뷰포트별 폰 풀블리드/목업 프레임 감싸기 | ViewTree, ViewportClass → FramedView |
| PhoneMockupFrame | `classifyViewport(width: px): ViewportClass` | 뷰포트 폭을 phone/desktop-tablet 분류 | px → ViewportClass |
| SecurityHeaderPolicy | `buildHeaders(req: SsrRequest): SecurityHeaders` | SSR 보안 헤더 세트 구성(자기-프레이밍 예외 포함) | SsrRequest → SecurityHeaders |
| SecurityHeaderPolicy | `buildCsp(): CspDirectiveSet` | frame-ancestors=self만 허용·나머지 제한 CSP 생성 | (none) → CspDirectiveSet |
| SearchScreen | `submitQuery(input: QueryInput): void` | 검증 통과 시 ApiClient.search로 동기 검색 트리거·상태 전이(히어로 진입점) | QueryInput → void |
| SearchScreen | `validateInput(input: QueryInput): ValidationResult` | 빈/길이초과(≤500자) 클라이언트 검증 | QueryInput → ValidationResult |
| SearchScreen | `renderState(state: SearchScreenState): ViewTree` | 로딩/결과/빈/실패/저하 상태를 ResultList·StateView에 위임 렌더 | SearchScreenState → ViewTree |
| ResultList | `render(results: ResultCardVM[], meta: ResultMeta): ViewTree` | 정렬 순서 보존 상위 N건 카드·저하 배너 렌더 | ResultCardVM[], ResultMeta → ViewTree |
| ResultCard | `render(card: ResultCardVM): ViewTree` | 단일 논문 폰 최적화 카드(가로 스크롤 없음) | ResultCardVM → ViewTree |
| ResultCard | `onSaveToLibrary(paperId: PaperId): void` | 라이브러리 저장 액션을 ApiClient에 위임 | PaperId → void |
| AccountScreens | `submitSignup(form: SignupForm): void` | 검증 가입 폼을 ApiClient.signup 제출·상태 반영 | SignupForm → void |
| AccountScreens | `submitLogin(form: LoginForm): void` | 검증 로그인 폼을 ApiClient.login 제출·상태 반영 | LoginForm → void |
| AccountScreens | `logout(): void` | ApiClient.logout 호출·셸 세션 초기화 | (none) → void |
| LibraryHistoryScreens | `renderSavedSearches(items: SavedSearchVM[]): ViewTree` | 소유자 비공개 저장 검색 목록·재실행·삭제 UI | SavedSearchVM[] → ViewTree |
| LibraryHistoryScreens | `renderLibrary(items: LibraryItemVM[]): ViewTree` | 소유자 비공개 라이브러리 목록·삭제 UI | LibraryItemVM[] → ViewTree |
| LibraryHistoryScreens | `renderHistory(items: HistoryItemVM[]): ViewTree` | 소유자 비공개 이력 목록·재실행 UI | HistoryItemVM[] → ViewTree |
| LibraryHistoryScreens | `rerun(searchRef: SavedSearchId \| HistoryId): void` | 저장 검색/이력을 SearchScreen 검색 흐름으로 재실행 | SavedSearchId \| HistoryId → void |
| StateView | `renderEmpty(reason: EmptyReason): ViewTree` | 관련 논문 없음 등 빈 상태 비기술 메시지(날조 0건) | EmptyReason → ViewTree |
| StateView | `renderError(kind: UserFacingErrorKind): ViewTree` | fail closed 일반화 에러·내부정보 차단 | UserFacingErrorKind → ViewTree |
| StateView | `renderDegraded(mode: DegradationMode): ViewTree` | 저하 모드(리랭킹 비활성 등) 명시 렌더(QT-3 저하 UX) | DegradationMode → ViewTree |
| ApiClient | `search(req: SearchRequest): Promise<SearchResponse>` | 동기 REST 검색 요청·정규화 응답/오류 | SearchRequest → Promise<SearchResponse> |
| ApiClient | `signup(req: SignupRequest): Promise<SessionResult>` | 가입 요청·세션/레이트리밋 정규화 | SignupRequest → Promise<SessionResult> |
| ApiClient | `login(req: LoginRequest): Promise<SessionResult>` | 로그인 요청·세션/무차별대입 정규화 | LoginRequest → Promise<SessionResult> |
| ApiClient | `logout(): Promise<void>` | 로그아웃 요청·서버측 세션 무효화 | (none) → Promise<void> |
| ApiClient | `listSavedSearches(): Promise<SavedSearch[]>` | 사용자 저장 검색 목록 조회(소유권 서버 인가) | (none) → Promise<SavedSearch[]> |
| ApiClient | `saveSearch(req: SaveSearchRequest): Promise<SavedSearch>` | 검색을 비공개 목록에 저장 | SaveSearchRequest → Promise<SavedSearch> |
| ApiClient | `listLibrary(): Promise<LibraryItem[]>` | 사용자 라이브러리 항목 조회 | (none) → Promise<LibraryItem[]> |
| ApiClient | `addToLibrary(req: AddLibraryRequest): Promise<LibraryItem>` | 논문을 라이브러리에 추가 | AddLibraryRequest → Promise<LibraryItem> |
| ApiClient | `listHistory(): Promise<HistoryItem[]>` | 사용자 최근 검색 이력 조회 | (none) → Promise<HistoryItem[]> |

---

## U6 — Reliability & Operations

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| ApiGatewayMiddleware | `handle(request: HttpRequest, next: DomainHandler) -> HttpResponse` | 전처리 체인 적용→핸들러 위임; U2 라우트는 응답 엣지에서 GroundingEnforcementHook.enforce 적용; enforce에서 발생한 모든 예외는 명시적으로 catch하여 fail-closed(toProductionError) 처리함으로써 우회 차단 | HttpRequest, DomainHandler → HttpResponse(정상 \| 일반화 에러) |
| ApiGatewayMiddleware | `applySecurityHeaders(response: HttpResponse) -> HttpResponse` | 제한 CSP·보안 헤더 부착(frame-ancestors=self 카브아웃) | HttpResponse → HttpResponse |
| ApiGatewayMiddleware | `toProductionError(err: Throwable, requestId: RequestId) -> HttpResponse` | 내부 예외를 스택 트레이스 비노출 일반화 에러로 매핑(fail-closed) | Throwable, RequestId → HttpResponse(generic) |
| AuthnAuthzGuard | `authenticate(request: HttpRequest) -> Result<Principal, AuthError>` | 세션/토큰 서버측 검증(U3.SessionVerifier 위임) | HttpRequest → Result<Principal, AuthError> |
| AuthnAuthzGuard | `authorize(principal: Principal, resource: ResourceRef, action: Action) -> AuthzDecision` | **객체 단위 소유권 결정을 U3.AuthorizationGuard에 위임(재구현 아님); 미들웨어는 강제 이음새. 관리자 MFA 확인.** | Principal, ResourceRef, Action → AuthzDecision(allow \| deny) |
| InputValidationGuard | `validate(payload: RawPayload, schemaId: SchemaId) -> Result<ValidatedPayload, ValidationError>` | 선언적 스키마 검증·새니타이즈·인라인 에러 | RawPayload, SchemaId → Result<ValidatedPayload, ValidationError> |
| RateLimiter | `checkLimit(scope: LimitScope, key: ClientKey) -> LimitDecision` | 출처별 슬라이딩 윈도 한도 평가(검색·가입·남용 완화) | LimitScope, ClientKey → LimitDecision(allow \| throttle \| reject) |
| CostGuardCircuitBreaker | `getBudgetState() -> BudgetState` | 준실시간 임계 상태·권고 저하 모드 반환(동기 폴백 분기 지원). 원자적 카운터를 읽어 TOCTOU 경합을 제거함 | (none) → BudgetState{tier, degradeMode, circuitState} |
| CostGuardCircuitBreaker | `recordSpend(usage: UsageEvent) -> void` | 사용량/지출 누적(원자적 카운터 증분)·급증 신호화 트리거 | UsageEvent → void |
| CostGuardCircuitBreaker | `evaluateCircuit() -> CircuitTransition` | 비동기 주기적 실행으로 임계 도달 시 OPEN/반-개방/CLOSE 전이·저하 지시 갱신 | (internal snapshot) → CircuitTransition |
| **GroundingEnforcementHook** | `enforce(candidate: CandidateResponse, retrieved: RetrievedRecordSet) -> GroundingDecision` | **FR-5/QT-1 단일 권위 런타임 게이트. 실재 레코드 매핑·AI 텍스트 출처 검증·통과/차단/기권. 위반 시 HallucinationDetector로 신호.** | CandidateResponse, RetrievedRecordSet → GroundingDecision{verdict: pass\|block\|abstain, violations[]} |
| GroundingEnforcementHook | `runEvalSet(evalSet: GroundingEvalSet) -> GroundingEvalReport` | QT-1 평가셋 동일 후크로 실행·날조 0건/코퍼스 밖 기권 보고(OP/팀 소유) | GroundingEvalSet → GroundingEvalReport |
| **ReliabilityEvalProbe** | `runReliabilityEvalSet(evalSet: ReliabilityEvalSet) -> ReliabilityEvalReport` | **QT-3 신뢰성/우아한 저하 인수 평가 — 업스트림 장애·빈 결과 경로 동작 검증·보고** | ReliabilityEvalSet → ReliabilityEvalReport{cases[], degradedBehaviorOk} |
| ReliabilityEvalProbe | `verifyDegradedMode(mode: DegradationMode) -> DegradedModeReport` | 강제 저하 모드(LLM off/벡터 장애/부분 결과) 동작 검증 | DegradationMode → DegradedModeReport |
| ObservabilityHub | `emitMetric(name: MetricName, value: MetricValue, tags: TagSet) -> void` | 지연·에러율·처리량·근거화/검색 건강도·지출 메트릭 수집 | MetricName, MetricValue, TagSet → void |
| ObservabilityHub | `emitLog(entry: StructuredLogEntry) -> void` | 요청 ID 상관 구조화 로그 수집(PII/시크릿 차단) | StructuredLogEntry → void |
| ObservabilityHub | `startSpan(name: SpanName, context: TraceContext) -> Span` | 분산 트레이스 스팬 시작(동기 경로 지연 추적) | SpanName, TraceContext → Span |
| ObservabilityHub | `auditAppend(event: AuditEvent) -> void` | 핵심 변경·인가 결정 추가 전용 감사 로그(90일+) | AuditEvent → void |
| HealthCheckService | `shallowCheck() -> HealthStatus` | 프로세스 생존/준비성 반환(liveness/readiness) | (none) → HealthStatus |
| HealthCheckService | `deepCheck() -> DependencyHealthReport` | arXiv·LLM 게이트웨이·벡터 스토어 연결성 타임아웃 검증 | (none) → DependencyHealthReport |
| AiIncidentDetectorSuite | `onTelemetryEvent(event: TelemetryEvent) -> Option<IncidentSignal>` | 텔레메트리 소비해 세 인시던트 클래스 후보 평가 | TelemetryEvent → Option<IncidentSignal> |
| AiIncidentDetectorSuite | `classify(signal: IncidentSignal) -> ClassifiedIncident` | 후보를 RES-11 클래스(a/b/c)·심각도 분류 | IncidentSignal → ClassifiedIncident |
| IncidentEventPublisher | `publishIncident(incident: ClassifiedIncident) -> void` | 분류 인시던트 표준 스키마 발행·감사 기록 | ClassifiedIncident → void |
| IncidentEventPublisher | `publishAlert(alert: OpsAlert) -> void` | 운영 경보 IR/COE 라우팅 발행 | OpsAlert → void |
| OpsDashboardService | `getDashboard(window: TimeWindow) -> OpsDashboardView` | 지연·에러율·처리량·건강도·지출·서킷 상태 OP 뷰 모델 | TimeWindow → OpsDashboardView |
| OpsDashboardService | `listIncidents(filter: IncidentFilter) -> IncidentList` | 세 인시던트 클래스 상태·경보 이력 조회 | IncidentFilter → IncidentList |

---

## U11 — Evidence Formation Agent

> **스트리밍 주석**: `sendMessage`는 SSE 청크 스트림을 반환(NFR-P6). 긴 분석은 `EvidenceJobService`가 비동기 잡으로 처리하며 `getJobResult`로 폴링.

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| EvidenceChatController | `createSession(authCtx: AuthContext, body: SessionCreateDTO) -> HttpResponse<EvidenceSessionDTO>` | 새 근거형성 세션 생성 | AuthContext, SessionCreateDTO{title?} → HttpResponse<EvidenceSessionDTO>(201) |
| EvidenceChatController | `listSessions(authCtx: AuthContext, page: PageParams) -> HttpResponse<EvidenceSessionPageDTO>` | 소유자 세션 목록 조회 | AuthContext, PageParams → HttpResponse<EvidenceSessionPageDTO>(200) |
| EvidenceChatController | `getSession(authCtx: AuthContext, sessionId: Id) -> HttpResponse<EvidenceSessionResultDTO>` | 특정 세션 결과·이력 재열람 | AuthContext, Id → HttpResponse<EvidenceSessionResultDTO>(200) \| 404 |
| EvidenceChatController | `sendMessage(authCtx: AuthContext, sessionId: Id, body: EvidenceMessageDTO) -> StreamingResponse<EvidenceChunkDTO>` | 채팅 턴 전송 → 스트리밍 근거형성 응답(SSE) | AuthContext, Id, EvidenceMessageDTO{topic, scope?, paperIds?, attachments?} → SSE stream |
| EvidenceChatController | `deleteSession(authCtx: AuthContext, sessionId: Id) -> HttpResponse<void>` | 소유 세션 삭제(타 소유 NotFound) | AuthContext, Id → HttpResponse<void>(204) \| 404 |
| EvidenceChatController | `resetAllSessions(authCtx: AuthContext) -> HttpResponse<void>` | 전체 세션 초기화 | AuthContext → HttpResponse<void>(204) |
| EvidenceAgentOrchestrator | `run(request: EvidenceRequest, ctx: AgentContext) -> AsyncStream<EvidenceChunk>` | 첫 질문: 도구 자율 오케스트레이션 → 스트리밍 근거형성 | EvidenceRequest, AgentContext → AsyncStream<EvidenceChunk>(EvidenceResult \| EvidenceAbstainResult 종착) |
| EvidenceAgentOrchestrator | `continueSession(sessionId: Id, followUp: str, ctx: AgentContext) -> AsyncStream<EvidenceChunk>` | 후속 질문: 이전 턴 맥락 참조 → 스트리밍 | Id, str, AgentContext → AsyncStream<EvidenceChunk> |
| EvidencePaperSearchTool | `searchPapers(query: str, scope: EvidenceScope, paperIds?: str[]) -> IndexRecord[]` | Agent 호출 논문 검색 도구 | str, EvidenceScope, str[]? → IndexRecord[] |
| EvidenceDocModelTool | `fetchBlocks(paperId: str, recordRef: str, anchor?: str) -> DocModelBlock[]` | Agent 호출 DocModel 블록 읽기 | str, str, str? → DocModelBlock[] |
| EvidenceExtractor | `extractItems(blocks: DocModelBlock[], paperId: str, recordRef: str) -> EvidenceItem[]` | 블록에서 EvidenceItem 추출(추출 전용, C-2) | DocModelBlock[], str, str → EvidenceItem[](statement+supporting+conflicting, confidence 없음 Q3=B) |
| EvidenceComparisonAssembler | `assemble(items: EvidenceItem[], coverage: EvidenceCoverage) -> EvidenceResult` | EvidenceItems → 비교표+쟁점 오버레이 EvidenceResult | EvidenceItem[], EvidenceCoverage → EvidenceResult(state=ok) |
| EvidenceComparisonAssembler | `buildConflictOverlay(items: EvidenceItem[]) -> ConflictMatrix` | 지지/상충 출처 기반 쟁점 오버레이 계산 | EvidenceItem[] → ConflictMatrix |
| AttachmentDocModelAdapter | `processAttachment(handle: AttachmentHandle) -> DocModelBlock[]` | 첨부 문서 doc-model 파이프라인 일시 처리(원시 파일 미저장) | AttachmentHandle → DocModelBlock[] |
| EvidenceSessionRepository | `createSession(userId: Id, meta: SessionMeta) -> EvidenceSession` | owner 키 강제 포함 세션 영속화 | Id, SessionMeta → EvidenceSession |
| EvidenceSessionRepository | `loadSession(userId: Id, sessionId: Id) -> Optional<EvidenceSession>` | 소유자 범위 세션 단건 조회 | Id, Id → Optional<EvidenceSession> |
| EvidenceSessionRepository | `listSessions(userId: Id, page: PageParams) -> Page<EvidenceSession>` | 소유자 범위 세션 최근순 목록 | Id, PageParams → Page<EvidenceSession> |
| EvidenceSessionRepository | `appendTurn(sessionId: Id, turn: EvidenceTurn) -> void` | 세션 턴 추가 영속 | Id, EvidenceTurn → void |
| EvidenceSessionRepository | `deleteSession(userId: Id, sessionId: Id) -> boolean` | 소유자 범위 세션 삭제 | Id, Id → boolean(삭제 성공 여부) |
| EvidenceSessionRepository | `resetAllSessions(userId: Id) -> void` | 소유자 전체 세션 삭제 | Id → void |
| EvidenceFormationService | `async form_evidence(request: EvidenceRequest, ctx: Any) -> EvidenceResult \| EvidenceAbstainResult` | **EvidenceFormationPort(D5) 구현 — U12 Tool 진입점**. EvidenceAgentOrchestrator 라우팅; 긴 분석은 잡 오프로드 | EvidenceRequest, Any → EvidenceResult(state=ok) \| EvidenceAbstainResult(state=abstain) |

---

## 2026-09-19 F01-F13 교정 메서드 개정

> **SUPERSEDED - 2026-09-19 UQRF1=B**: 아래 in-package method boundaries는 이력이다. 새 inter-service API/control-plane contracts 승인 전 구현에 사용하지 않는다.
>
> 아래 시그니처는 Application Design 수준의 포트다. field-level schema, transaction 경계, timeout/retry 수치, token cryptography, relevance threshold는 각 remediation unit의 Functional/NFR Design에서 확정한다.

### REM-1 - Platform and Contract Integrity

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| OrderedMigrationRegistry | `entries(scope: MigrationScope = BACKEND) -> Sequence[MigrationSpec]` | startup과 CLI가 동일한 ordered migration 목록을 조회 | MigrationScope → MigrationSpec[]{ledgerId, owner, packageRelativePath, order} |
| OrderedMigrationRegistry | `validate(entries: Sequence[MigrationSpec]) -> RegistryValidation` | DB 연결 전 duplicate ID/path, missing/unregistered file, order 오류를 fail closed 검증 | MigrationSpec[] → RegistryValidation{valid, violations[]} |
| OrderedMigrationRegistry | `identitySet(scope: MigrationScope) -> MigrationIdentitySet` | startup/CLI 동등성과 ledger identity 검증 표면 제공 | MigrationScope → MigrationIdentitySet |
| OfflineContractBindingGenerator | `discoverSchemas(roots: Sequence[Path]) -> LocalSchemaRegistry` | 모든 local schema를 결정적 순서로 발견하고 `$id` registry 구성 | Path[] → LocalSchemaRegistry{idToPath} |
| OfflineContractBindingGenerator | `resolveLocalRefs(registry: LocalSchemaRegistry) -> ResolutionReport` | network 없이 모든 `$ref` closure 검증 | LocalSchemaRegistry → ResolutionReport{resolved, failures[]} |
| OfflineContractBindingGenerator | `generate(registry: LocalSchemaRegistry, targets: Sequence[BindingTarget]) -> GeneratedTree` | 임시 tree에서 build-consumed bindings 전부 생성; 하나라도 실패하면 publish하지 않음 | Registry, BindingTarget[] → GeneratedTree \| GenerationFailure |
| OfflineContractBindingGenerator | `checkDrift(generated: GeneratedTree, committed: Path) -> DriftReport` | committed build contract와 재생성 결과 비교 | GeneratedTree, Path → DriftReport |
| RuntimeSupplyChainVerifier | `verifyRuntime(manifest: RuntimeCompatibilityManifest, observed: RuntimeInventory) -> VerificationReport` | production/CI/local/Docker runtime 버전 정합 검증 | manifest, inventory → VerificationReport |
| RuntimeSupplyChainVerifier | `auditLocks(units: Sequence[DeployUnit], exceptions: Sequence[AdvisoryException]) -> DependencyAuditReport` | committed lock closure의 critical/high advisory와 예외 만료 검증 | DeployUnit[], AdvisoryException[] → DependencyAuditReport |
| RuntimeSupplyChainVerifier | `verifyImagePins(images: Sequence[ImageRef]) -> PinReport` | mutable tag와 unapproved digest를 거부 | ImageRef[] → PinReport |
| RuntimeSupplyChainVerifier | `emitSbom(unit: DeployUnit) -> SbomArtifact` | deploy unit별 재현 가능한 SBOM 생성 | DeployUnit → SbomArtifact |

### REM-2 - Private Content and Generation

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| PublicPaperNamespacePolicy | `requirePublicPaperRef(raw: str) -> Result<PublicPaperRef, PublicNotFound>` | public API에서 `userdoc:`와 invalid/private namespace를 동일 응답으로 거부 | str → PublicPaperRef \| generalized rejection |
| UserDocModelCoordinator | `validateOwnedRef(owner: UserId, ref: UserDocModelRef) -> Result<OwnedUserDocRef, NotFound>` | owner context와 `paperId/objectKey/recordRef` 결속 검증 | UserId, UserDocModelRef → OwnedUserDocRef \| generalized NotFound |
| UserDocModelCoordinator | `loadOwnedDocModel(owner: UserId, ref: UserDocModelRef) -> Optional<DocModel>` | evidence/novelty owner-bound 경로에서만 private DocModel 읽기 | UserId, UserDocModelRef → Optional<DocModel> |
| UserDocModelCoordinator | `loadOwnedAsset(owner: UserId, ref: UserDocAssetRef) -> Optional<AssetStream>` | owner-bound private context에서만 파생 asset stream 열기 | UserId, UserDocAssetRef → Optional<AssetStream> |
| CanonicalSummarySourceResolver | `resolveCanonicalSource(request: SummaryRequest, paper: PublicPaperRef) -> CanonicalSource` | server metadata/DocModel로 trusted source 선택 및 digest 계산 | SummaryRequest, PublicPaperRef → CanonicalSource{paperId, revision, kind, contentDigest, source} |
| CanonicalSummarySourceResolver | `sourceIdentity(source: CanonicalSource) -> SourceIdentity` | cache와 job이 공유하는 결정적 identity 생성 | CanonicalSource → SourceIdentity |
| SummaryGenerationJobRegistry | `ensureJob(identity: GenerationIdentity) -> JobEnsureResult` | cache miss에서 durable job marker를 원자적으로 생성/조회 | GenerationIdentity → JobEnsureResult{created \| active \| terminal, jobRef} |
| SummaryGenerationJobRegistry | `recordEnqueue(job: JobRef, result: EnqueueResult) -> JobState` | enqueue 성공/중복/실패를 durable state에 반영 | JobRef, EnqueueResult → JobState |
| SummaryGenerationJobRegistry | `recordRunning(job: JobRef, lease: WorkerLease) -> JobState` | worker attempt와 visibility/lease 상태 기록 | JobRef, WorkerLease → JobState |
| SummaryGenerationJobRegistry | `recordTerminal(job: JobRef, outcome: GenerationOutcome) -> JobState` | succeeded/failed/retry-exhausted terminal 결과 기록 | JobRef, GenerationOutcome → JobState |
| AuthenticatedPaperAssetController | `streamAsset(auth: AuthContext, paper: PublicPaperRef, version: Version, assetId: AssetId) -> HttpStreamResponse` | manifest/license 검증 후 safe header와 object bytes stream 반환 | AuthContext, paper/version/assetId → authenticated binary response \| generalized error |
| SameOriginAssetProxy | `proxyAssetStream(request: BffRequest, path: AssetPath) -> WebStreamResponse` | session과 trusted edge headers를 전달하고 safe response headers만 relay | BffRequest, AssetPath → same-origin WebStreamResponse |

### REM-3 - Owner Lifecycle and Edge Trust

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| OwnerPurgeRegistry | `registeredTargets() -> Sequence[PurgeTargetSpec]` | owner-scoped SQL/object/cache target SSOT 조회 | none → PurgeTargetSpec[] |
| OwnerPurgeRegistry | `validateCoverage(inventory: ApplicationDataInventory) -> CoverageReport` | known owner stores 대비 registry 누락/중복/불명확 binding 검증 | ApplicationDataInventory → CoverageReport |
| OwnerPurgeRegistry | `inventoryOwner(owner: UserId) -> PurgeInventory` | SQL 삭제 전에 exact row/object/cache target 수집 | UserId → PurgeInventory |
| PurgeManifestRepository | `createManifest(owner: UserId, inventory: PurgeInventory) -> PurgeManifest` | immutable inventory와 hash를 durable 저장 | UserId, PurgeInventory → PurgeManifest{manifestId, hash, stage} |
| PurgeManifestRepository | `advanceStage(manifest: ManifestId, expected: PurgeStage, next: PurgeStage) -> StageResult` | compare-and-set으로 단계 단조 전진 | ManifestId, expected, next → StageResult |
| OwnerPurgeCoordinator | `planPurge(owner: UserId) -> PurgeManifest` | registry 검증과 pre-delete inventory snapshot 수행 | UserId → PurgeManifest |
| OwnerPurgeCoordinator | `resumePurge(manifest: ManifestId) -> PurgeProgress` | 저장된 manifest/stage에서 object/cache/SQL purge 재개 | ManifestId → PurgeProgress |
| OwnerPurgeCoordinator | `verifyResidue(manifest: ManifestId) -> ResidueReport` | 대상 owner 0건 및 비대상 owner 불변 검증 | ManifestId → ResidueReport |
| DigestUnsubscribeController | `unsubscribe(token: str, request: PublicRequestContext) -> HttpResponse<UnsubscribeResult>` | exact anonymous endpoint에서 token-only authorization으로 idempotent unsubscribe 수행 | token, context → 200 generic result \| 4xx invalid/expired |
| DigestLinkTokenVerifier | `issue(owner: UserId, settingsVersion: Version, issuedAt: Timestamp) -> SignedDigestToken` | settings version과 issued-at이 포함된 link token 생성 | UserId, Version, Timestamp → SignedDigestToken |
| DigestLinkTokenVerifier | `verify(token: str, now: Timestamp) -> Result<VerifiedDigestGrant, TokenError>` | signature, age, owner/settings version 검증 | str, Timestamp → VerifiedDigestGrant \| TokenError |
| EdgeClientIdentityForwarder | `trustedClientHeaders(inbound: Headers, mode: RuntimeMode) -> Result<Headers, EdgeIdentityError>` | `CF-Connecting-IP` 단일값을 canonicalize하고 internal header를 overwrite | Headers, RuntimeMode → sanitized Headers \| rejection |
| TrustedClientIdentityResolver | `resolveClientIdentity(peer: SocketAddress, headers: Headers) -> Result<ClientIdentity, IdentityError>` | loopback peer에서만 private header를 신뢰 | SocketAddress, Headers → ClientIdentity \| rejection |
| TrustedClientIdentityResolver | `attachRequestIdentity(request: HttpRequest, identity: ClientIdentity) -> void` | gateway/accounts가 함께 쓰는 request-scoped identity 설정 | HttpRequest, ClientIdentity → void |

### REM-4 - Corpus and Search Integrity

| 컴포넌트 | 시그니처 | 목적 | 입력 → 출력 |
|---|---|---|---|
| ProductionSeedGuard | `assertSeedAllowed(mode: RuntimeMode, target: IndexRef) -> SeedDecision` | production/unknown target의 fixture seed 실행을 거부 | RuntimeMode, IndexRef → SeedDecision |
| CorpusIntegrityAuditor | `auditGeneration(target: CorpusGenerationRef, policy: CorpusScopePolicy) -> CorpusAuditReport` | generation identity, fixture, source metadata, 최근 범위 completeness read-only 평가 | CorpusGenerationRef, CorpusScopePolicy → immutable CorpusAuditReport |
| CorpusIntegrityAuditor | `writeReport(report: CorpusAuditReport) -> ReportRef` | report hash/expiry와 함께 검증 report publish | CorpusAuditReport → ReportRef |
| CorpusRepairCoordinator | `planRepair(report: ReportRef, backup: VerifiedBackupRef) -> RepairManifest` | exact candidate IDs/count/hash, source/target generation, rollback alias를 dry-run manifest로 생성 | ReportRef, VerifiedBackupRef → RepairManifest |
| CorpusRepairCoordinator | `applyApprovedRepair(manifest: RepairManifest, authorization: RepairAuthorization) -> RepairResult` | 명시 승인된 targeted generation repair와 atomic cutover 수행 | RepairManifest, RepairAuthorization → RepairResult |
| CorpusRepairCoordinator | `rollbackRepair(manifest: RepairManifest) -> RollbackResult` | 이전 backing generation으로 alias 복원 | RepairManifest → RollbackResult |
| CorpusReadinessProvider | `readCorpusReadiness(active: CorpusGenerationRef, now: Timestamp) -> ReadinessDetail` | 최근 report의 freshness/generation/fixture/completeness reason만 해석 | CorpusGenerationRef, Timestamp → ReadinessDetail |
| ResultAssembler | `assembleEmpty(degradation: DegradationSignal, provenance: RetrievalProvenance) -> SearchResponse` | normal empty와 degraded empty를 union에서 구분 | DegradationSignal, RetrievalProvenance → SearchResultPageDTO(cards=[]) \| DegradedResultDTO(cards=[]) |
| SearchStateClassifier | `classifySearchResponse(response: SearchResponse) -> SearchViewState` | degradation metadata를 count보다 우선 판정 | SearchResponse → normalEmpty \| degradedEmpty \| results \| abstain \| error |
| RelevanceFloorEvaluator | `evaluateFloors(generation: CorpusGenerationRef, evalSet: ScopeEvalSet, candidates: Sequence[float]) -> FloorEvaluationReport` | candidate floor별 false-abstain/false-pass와 retrieved ID 기록 | generation, eval set, float[] → FloorEvaluationReport |
| RelevanceFloorPolicy | `loadPolicy(active: CorpusGenerationRef, model: EmbeddingModelRef) -> Result<RelevancePolicy, PolicyError>` | 승인 report가 active generation/model과 맞을 때만 정책 활성화 | generation, model → RelevancePolicy \| readiness error |
| RelevanceFloorPolicy | `classifyBestMatch(score: float, policy: RelevancePolicy) -> MatchDecision` | shadow/enforce mode에서 best score를 match/no-match로 결정 | float, RelevancePolicy → MatchDecision |

---

## 2026-09-19 Deployable Services and Public Jobs

**설계 수준**: 공개/internal resource 경계와 typed port의 입출력/목적을 정의한다. JSON Schema 필드 확정, SQL/상태 전이, crypto algorithm, TTL/timeout/retention 수치는 Functional/NFR Design 산출물이다. component ID는 `components.md`의 동명 절을 따른다.

### 공통 계약 타입

| 타입 | 의미와 binding |
|---|---|
| ActorContext | 검증된 User, RestrictedToken, Operator 또는 System actor. service identity와 caller identity는 별개이며 purpose/audience/resource scope를 포함한다. |
| ClientJobSpec | browser가 제출할 수 있는 allowlisted kind/업무 옵션/공개 resource selector만 포함한다. actor/owner 권한, authority reference, queue/storage locator 및 내부 실행 grant를 받지 않는다. |
| DelegationEnvelope | live hop의 짧은 signed caller 전달 증거. issuer/audience/expiry/service binding 검증 필수. 저장된 envelope를 큐에서 나중에 credential로 재사용하지 않는다. |
| AuthoritySnapshot / ExecutionPermit | domain 소유 current revision과 unexpired source grant를 확인한 결과. operation/resource/purpose/owner epoch에 결속된 제한된 허가이며 제출 시점 허가만으로 새로 발급하지 않는다. |
| OperationIntent | 서버가 검증 후 만드는 내부 intent: allowlisted 업무 kind, caller/resource context, 요청한 revision/옵션, 동일 제출 key, authority reference와 contract version. ClientJobSpec을 그대로 이 타입으로 신뢰하거나 browser binding으로 노출하지 않는다. |
| CommandProjection | sender가 publish한 recipient/purpose/parent/version/manifest에 결속된 immutable 내부 command view. 지정 domain executor만 읽고 자기 inbox에 처리 증거를 기록한다. user cookie/token을 포함하지 않으며 private view/copy도 purge inventory에 포함한다. |
| AcceptedJobReceipt | 해당 service realm의 opaque operation reference와 관측/결과 링크, request correlation 및 계약 version. durable operation/outbox 성공 후 반환하며 업무 성공을 뜻하지 않는다. |
| StatusQuerySpec / JobObservation | 대상 업무 operation을 읽는 별도 job 입력 / 관측 대상·revision·observedAt·안전한 상태를 담은 완료 결과. status query를 다시 query하는 재귀는 허용하지 않는다. |
| PublishedJobEvent / PublishedResultRef | operation/stream revision과 순서가 결속된 안전한 진행/terminal event 및 공개 가능한 결과 참조. domain의 abstain/degraded/no-match를 보존한다. |
| PreparedArtifact | 검증된 source revision, immutable object version 또는 content identity, public/owner-bound 분류와 무결성 증거를 가진 내부 결과. storage locator는 public projection에서 제외한다. |
| ObserverGrant | actor, service realm, 원 operation 및 허용 observation child, purpose, expiry에 결속. 익명 해지용 grant는 일반 session/다른 job 권한이 아니다. |
| SourceIdentity / GenerationIdentity | server-verified paper/context revision과 content digest / source에 allowlisted 생성 옵션·관련 domain policy 및 필요한 owner scope를 결속한 identity. |
| OwnerFence / WriteFence / QuiescenceCertificate | U3 lifecycle epoch / owner-bound 여부와 artifact/deployment writer epoch를 결속한 write 경계 / domain writer의 폐쇄·진행 중 I/O 종료 증거. 늦은 publication/purge를 조정하며 단순 lease timeout과 다르다. |
| PurgeManifest / DomainReceipt | exact owner-bound targets, revision/hash와 단계 / 해당 목적·manifest·fence·command에 결속된 멱등 실행 증거. 파기 완료 공개 전에 owner 식별 control data 정리를 검증한다. |
| SuppressionReceipt | 검증된 consent revision에 대한 durable 발송 차단과 job 접수가 함께 성립했다는 증거. settings 반영 완료와 구분한다. |
| OptOutReceipt | SuppressionReceipt와 AcceptedJobReceipt를 묶은 서버측 접수 결과. observer credential은 별도 보호 채널로 설정하며 public JSON에 raw token/secret을 포함하지 않는다. |
| CorpusEvidence / MutationApproval | generation/index identity, model/parser/policy revision, freshness/hash와 검증 결과 / exact manifest, backup/restore 증거 및 승인 범위에 묶인 mutation 권한. |
| CompatibilityManifest | artifact/schema/operation version 지원 조합, writer epoch 및 migration registry evidence. 배포/rollback 판단 입력이며 runtime service 호출을 요구하지 않는 versioned artifact다. |

### 공개 HTTP 계약

표는 gateway 경로다. browser는 같은 origin의 BFF를 통해 접근한다. API path의 service 영역은 서버의 고정 allowlist로 routing하며 client가 URL/host/queue 이름을 지정할 수 없다. 새 schema namespace는 기존 응답을 덮어쓰지 않고 versioned bindings로 제공한다.

| Method / resource | 경로 종류와 runtime | 입력 / 출력 및 권한 |
|---|---|---|
| `POST /api/v1/rem/content/papers/{paperId}/jobs` | queued 업무, REM-2 | authenticated public-paper summary/translation/DocModel/asset-preparation spec -> AcceptedJobReceipt. `userdoc:`는 storage 조회 전 일반화 거부 |
| `POST /api/v1/rem/content/contexts/{contextKind}/{contextId}/jobs` | queued private 업무, REM-2 | 등록된 evidence-attachment/novelty-manuscript context의 read/preparation spec -> AcceptedJobReceipt. owner는 session/context domain에서 결정하며 raw object key나 임의 private paper 조회를 받지 않음 |
| `POST /api/v1/rem/content/jobs/{operationRef}/status-queries` | queued status, REM-2 | 현재 owner 권한 + 대상 업무 참조 -> 조회 job의 AcceptedJobReceipt |
| `GET /api/v1/rem/content/jobs/{operationRef}/events` | 직접 관측, REM-2 DELIVERY | current authorization + job-bound cursor -> bounded SSE PublishedJobEvent stream. 구독/재연결 자체가 새 job을 만들지 않음 |
| `GET /api/v1/rem/content/jobs/{operationRef}/result` | 직접 결과, REM-2 DELIVERY | PublishedResultRef가 가리키는 준비된 결과만 전달. 일반 업무 live read/status를 이 endpoint 안에서 실행하지 않음 |
| `GET /api/v1/rem/content/jobs/{operationRef}/assets/{assetRef}` | 직접 bytes, REM-2 DELIVERY | prepared result의 asset manifest 및 현재 owner/license 검증 -> safe binary stream. storage URL/key 대신 이 same-origin 주소를 사용 |
| `POST /api/v1/rem/digest/unsubscribe-jobs` | 공개 token-authorized 접수, REM-3 | signed expiring digest token -> SuppressionReceipt + AcceptedJobReceipt. 정상 사용자 로그인은 요구하지 않되 exact path에서 token 검증/입력 제한/rate-limit 집행 |
| `POST /api/v1/rem/digest/unsubscribe-jobs/{operationRef}/status-queries` | 제한된 queued status, REM-3 | 해당 해지의 ObserverGrant -> 원 해지 job만 관측하는 child query receipt |
| `GET /api/v1/rem/digest/unsubscribe-jobs/{operationRef}/events` 및 `/result` | 제한된 직접 관측/결과, REM-3 | 해당 해지 또는 허용된 observation child에 묶인 ObserverGrant로 일반화된 결과만 전달. public allowlist는 이 exact route family로 한정 |
| 기존 account delete/logout 및 일반 search/library/agent 경로 | 기존 직접 제어/업무 계약 | U3 비활성화/session 무효화와 ingress 제한은 직접 수행. 전체 제품 API를 새 job 계약으로 전환하지 않음 |

- **접수 의미**: 신규 async 요청은 `202 Accepted`와 typed receipt/관측 링크를 반환한다. 동일 제출의 재시도는 같은 operation을 확인한다. 캐시 결과가 있어도 이관 업무는 job으로 접수하고 worker가 재사용한다.
- **오류 의미**: 입력 400/422, 미인증 401, private non-owner/missing은 동일 404, state/version 충돌 409, 용량 제한 429, dependency/접수 불능 503을 기본으로 한다. durable commit 여부가 불명확하면 accepted를 꾸미거나 미접수를 단정하지 않고 동일 제출로 재조정하도록 안내한다. field-level error DTO는 shared 계약에서 확정한다.
- **직접 결과의 한계**: 유효하게 인가된 job의 아직 publish되지 않은 결과는 NotReady(409), 알려진 보존 만료는 Expired(410)로 전달할 수 있다. 인가 전에는 이 차이를 노출하지 않는다. 결과 조회가 model/source 작업을 실행하거나 queued status를 대체하지 않는다.
- **관측**: SSE cursor는 operation/actor scope/stream version에 결속되고 오래된 event가 terminal을 되돌리지 않는다. 연결은 허가/connection lifetime 안에서만 유지하고 갱신 시 fresh delegation과 current authority로 재연결한다. 연결 단절은 업무 실패로 확정하지 않는다. event, private result 및 observer 응답은 shared cache에 저장하지 않는다.
- **익명 해지**: BFF는 job/purpose-scoped HttpOnly observer credential을 보관/전달하고 일반 account session을 발급하지 않는다. raw token/grant를 result URL, event cursor, 로그 또는 generic job API 권한으로 사용하지 않는다. 기존 `/unsubscribe` 화면과 실제 `/paper/{id}` 이메일 link를 사용한다.

### Internal 및 운영 표면

| 표면 | 역할 / 허가 |
|---|---|
| `POST /internal/v1/rem/{service}/operations` | REM-2/3/4의 고정 command-kind allowlist. service identity와 목적/actor 권한을 검증하며 HTTP 응답은 접수 결과까지다. REM-1 daemon에는 mutation endpoint를 두지 않는다. |
| `GET /internal/v1/rem/{service}/operations/{ref}/events` 및 `/result` | 해당 service의 준비된 내부 결과/receipt 관측. 일반 사용자와 system maintenance 권한을 구분하며 외부 generic proxy로 노출하지 않는다. |
| `GET /internal/v1/rem/platform/evidence/{ref}` | REM-1 read-only evidence/compatibility. build/runner는 로컬 versioned artifact도 같은 validator로 소비 가능 |
| `GET /internal/v1/rem/corpus/reports/{ref}` | REM-4의 immutable report 직접 조회. generation/freshness 실패는 readiness에 반영 |
| service별 `/healthz`, `/readyz` | queue와 독립된 bounded 직접 관측. shallow와 dependency/compatibility readiness 분리; 상세 운영 정보는 내부 권한 경계 |
| REM-1/REM-4의 명시적 runner entry | Operator/System + MutationApproval. migration/repair/cutover는 daemon startup/health에서 호출 불가 |

### Component port 시그니처

`Result<T, E>`는 성공/실패의 구분이며 business 상태 전이의 완전한 schema를 뜻하지 않는다.

| Component | 시그니처 | 목적 / 입력 -> 출력 |
|---|---|---|
| EDGE | `verifyIngress(peer: PeerIdentity, originProof: OriginProof, headers: Headers) -> Result<VerifiedClientIdentity, IngressDenied>` | 신뢰 tunnel ingress 및 BFF hop의 증거를 검사하고 canonical client identity 생성. loopback만으로 추가 local service를 BFF로 신뢰하지 않음 |
| EDGE | `admitRequest(route: RouteId, credential: PresentedCredential, spec: ClientJobSpec, key: SubmissionKey) -> Result<AcceptedJobReceipt, AdmissionError>` | 입력/권한/rate-limit을 먼저 집행하고 고정 service에 audience-bound delegation 전달. caller 권한은 payload에서 받지 않음 |
| EDGE | `relayObservation(route: RouteId, credential: PresentedCredential, cursor: EventCursor) -> EventStream` / `relayResult(route: RouteId, credential: PresentedCredential) -> SafeResponseStream` | 현재 인가된 event/JSON/bytes를 같은 origin으로 중계; 안전한 header만 허용 |
| UI | `submit(spec: ClientJobSpec, key: SubmissionKey) -> SubmissionView` / `observe(receipt: AcceptedJobReceipt, cursor: EventCursor) -> ObservationView` | 공개 입력만 제출하며 접수/불확정 접수와 완료를 구분하고 같은 제출 재시도/재연결 연결 |
| UI | `applyEvent(view: JobView, event: PublishedJobEvent) -> JobView` / `openResult(ref: PublishedResultRef) -> ResultView` | 순서/terminal/domain outcome 보존; 준비된 결과를 새 업무로 제출하지 않음 |
| AUTH | `currentAuthority(actorRef: ActorRef, resourceRef: ResourceRef, purpose: Purpose) -> Result<AuthoritySnapshot, Denied>` | domain의 current head/expiry/revocation와 immutable binding을 일관되게 읽음. stale/missing/읽기 실패는 거부 |
| AUTH | `authorizeExecution(intent: OperationIntent, snapshot: AuthoritySnapshot, now: Timestamp) -> Result<ExecutionPermit, Denied>` | 유효한 source grant와 현재 owner epoch로만 실행 허가. old envelope/accepted row만으로 grant 생성 불가 |
| AUTH | `authorizeDelivery(actor: ActorContext, operation: OperationRef, artifact: PublishedResultRef) -> Result<DeliveryPermit, OpaqueDenied>` | 현재 job/context/asset/license 권한을 확인하고 비소유·미존재를 일반화 |
| RK | `accept(actor: ActorContext, intent: OperationIntent, key: SubmissionKey) -> Result<AcceptedJobReceipt, AdmissionError>` | operation + publication intent 원자 저장, 같은 caller/purpose/request retry dedupe |
| RK | `claim(operationRef: OperationRef, workerIdentity: ServiceIdentity) -> Result<OperationLease, ClaimError>` | 지원되는 operation version과 실행 권한 확인, bounded claim/attempt |
| RK | `publish(lease: OperationLease, permit: ExecutionPermit, outcome: DomainOutcome, artifacts: PreparedArtifact[]) -> Result<PublicationReceipt, PublicationError>` | fenced outcome/result/event publication. artifact의 준비/무결성을 확인한 후 완료를 공개 |
| RK | `observeStatus(queryIntent: StatusQuerySpec, permit: ExecutionPermit) -> JobObservation` | 한 번의 권한 있는 target snapshot을 조회 job의 결과로 publish. target은 업무 operation이며 query-of-query 금지 |
| RK | `reconcile(actor: SystemActor, now: Timestamp) -> RecoveryReport` | 자기 realm의 미발행 outbox/lease/terminal publication 재조정. queue 메시지는 진실원천이 아님 |
| DELIVERY | `subscribe(actor: ActorContext, operationRef: OperationRef, cursor: EventCursor) -> EventStream` | 이미 publish된 safe event replay/live, 현재 권한 재검증 및 bounded 종료 |
| DELIVERY | `openPublishedResult(actor: ActorContext, operationRef: OperationRef) -> Result<ResultStream, DeliveryError>` | 준비된 결과 또는 NotReady/Expired/OpaqueDenied. business handler 호출 없음 |
| DELIVERY | `openAsset(actor: ActorContext, operationRef: OperationRef, assetRef: AssetRef) -> Result<AssetStream, DeliveryError>` | accepted context와 prepared manifest에 결속된 object만 현재 권한으로 열기 |
| EXEC | `beginWrite(permit: ExecutionPermit, fence: WriteFence) -> Result<WritePermit, Fenced>` | 실제 write/publication까지 owner/deployment epoch 보호 적용 |
| EXEC | `quiesce(scope: OwnerScope, fence: OwnerFence) -> Result<QuiescenceCertificate, Incomplete>` | 모든 해당 producer/in-flight I/O의 종료/차단 증명. 증명 불가능하면 incomplete |
| EXEC | `executeMaintenance(command: MaintenanceCommand, grant: MaintenanceGrant, manifest: VerifiedManifest) -> DomainReceipt` | domain-local allowlist/owner/manifest 검증 후 멱등 delete 또는 승인 mutation |
| EXEC | `verifyResidue(scope: OwnerScope, manifest: PurgeManifest) -> ResidueReport` | 대상 0건과 다른 owner 보존 증거, 알려진 새 저장소 coverage 확인 |
| R1C | `readEvidence(actor: ActorContext, ref: EvidenceRef) -> PlatformEvidence` / `checkCompatibility(manifest: CompatibilityManifest) -> CompatibilityVerdict` | read-only version/registry/audit 증거 제공 |
| R1R | `verifyRegistry(specs: MigrationSpec[], ledger: MigrationLedgerView) -> RegistryVerdict` | ordered registry의 duplicate/missing/legacy ID 및 startup/CLI 동치 검사 |
| R1R | `runApproved(kind: PlatformOperationKind, approval: MutationApproval, manifest: CompatibilityManifest) -> PlatformRunReceipt` | 명시적 mutation 권한과 backup/rollback 경계 안의 migration/promotion |
| R1R | `generateBindings(schemaRoots: SchemaRoot[], targets: BindingTarget[]) -> BindingEvidence` | local ref offline resolution, 임시 생성물 전체 검증 후 atomic publish; 실패 non-zero |
| R1R | `verifySupplyChain(artifacts: ArtifactRef[], exceptions: AdvisoryException[]) -> SupplyChainEvidence` | patched lock closure/pin/audit/SBOM 및 예외 근거/만료 확인 |
| R2A | `acceptPublic(actor: ActorContext, paperRef: PublicPaperRef, spec: ClientJobSpec, key: SubmissionKey) -> Result<AcceptedJobReceipt, AdmissionError>` / `acceptPrivate(actor: ActorContext, contextRef: ContextRef, spec: ClientJobSpec, key: SubmissionKey) -> Result<AcceptedJobReceipt, AdmissionError>` | namespace/current owner-context 검증 후 서버측 OperationIntent를 만들어 RK에 접수. generation identity 확정은 worker의 canonical resolver |
| R2A | `acceptStatusQuery(actor: ActorContext, targetRef: OperationRef, key: SubmissionKey) -> Result<AcceptedJobReceipt, AdmissionError>` | target owner 확인 후 typed StatusQuery intent 생성 |
| R2W | `executeContent(lease: OperationLease, permit: ExecutionPermit, intent: OperationIntent) -> ContentOutcome` | SourceIdentity 고정, source-bound cache lookup, 필요한 U1 command 또는 U7 생성, fenced 결과 |
| R2W | `executeStatusQuery(lease: OperationLease, permit: ExecutionPermit, targetRef: OperationRef) -> JobObservation` | 대상 업무 상태를 관측 시점과 함께 조회 결과로 반환 |
| R3C | `acceptOptOut(token: str, requestContext: VerifiedIngressContext, key: SubmissionKey) -> Result<OptOutReceipt, TokenOrAdmissionError>` | U15 token/consent 검증 + send barrier 안의 suppression/operation/outbox 원자 수락 |
| R3C | `issueObserverGrant(receipt: OptOutReceipt) -> ObserverGrant` / `recordConsentReceipt(receipt: DomainReceipt) -> PublicationReceipt` | 익명 observation 권한 최소화 및 U15 settings 반영 결과 공개 |
| R3P | `startPurge(lifecycleGrant: LifecyclePurgeDue) -> AcceptedJobReceipt` / `resumePurge(manifestRef: ManifestRef, systemGrant: SystemGrant) -> PurgeProgress` | registry/유예/현재 lifecycle epoch 검증, domain command/receipt saga 재개 |
| R3P | `finalizePurge(manifestRef: ManifestRef, receipts: DomainReceipt[]) -> Result<SanitizedPurgeReceipt, Incomplete>` | 모든 target/quiescence/residue와 coordinator 자체 control data 정리 검증 |
| R3E | `publishEdgePolicy(policy: EdgePolicy, approval: PolicyApproval) -> PolicyRef` / `validateEdgePolicy(ref: PolicyRef) -> PolicyVerdict` | versioned trust policy 검증/배포. request-path enforcement는 EDGE/U3 로컬 |
| R4A | `acceptAudit(actor: ActorContext, generation: GenerationRef) -> AcceptedJobReceipt` / `acceptCalibration(actor: ActorContext, evidence: CorpusEvidence, evalSet: EvalSetRef) -> AcceptedJobReceipt` | operator/system 작업만 허용; 검증된 generation에 한해 평가 수행 |
| R4A | `readReport(actor: ActorContext, ref: ReportRef) -> CorpusEvidence` | immutable evidence의 hash/generation/freshness를 보존한 직접 조회 |
| R4R | `planRepair(evidence: CorpusEvidence, verifiedBackup: VerifiedBackupRef) -> RepairManifest` / `runApprovedRepair(manifest: RepairManifest, approval: MutationApproval) -> RepairReceipt` | exact dry-run 및 승인된 U1 mutation. 별도 승인 없는 alias cutover/full rebuild 없음 |
| SEARCH | `loadVerifiedPolicy(head: GenerationHead, evidence: CorpusEvidence) -> PolicyVerdict` / `assembleOutcome(retrieval: RetrievalResult, degradation: DegradationSignal) -> SearchOutcome` / `classifyOutcome(outcome: SearchOutcome) -> SearchView` | current generation/model-bound 정책 및 0건 저하/무매치 구분 |
| OBS | `health() -> Liveness` / `readiness() -> ReadinessReport` / `recordSignal(context: TraceContext, signal: ServiceSignal) -> void` | queue 독립 health, dependency/compatibility 판정, structured redacted 관측/감사 |

### Domain 교차 계약과 versioning

- U3는 직접 `deactivateAndRevoke` 및 current authority projection을 소유하고, 유예 파기를 위한 durable `LifecyclePurgeDue`를 발행한다. 일반 user grant의 만료와 system purge grant의 목적을 혼동하지 않는다.
- U15 `ConsentBarrier`는 R3C의 suppression 접수와 모든 sender의 `beginHandoff`를 조정한다. U15 `ApplyOptOut` executor는 기대 consent revision에만 조건부 적용하고 receipt를 발행한다. token 검증, suppression, worker settings 반영 사이의 revision 경쟁은 같은 barrier 계약으로 다룬다.
- 성공한 suppression의 후속 settings 반영은 그 receipt/consent revision에만 묶인 System command다. 만료된 token으로 새 사용자 권한을 만드는 경로가 아니며, token/observer 만료 후에도 이미 수락된 발송 차단을 해제하지 않는다.
- U1 `BuildSource`, domain별 `QuiesceOwner`, `ApplyPurge`, `VerifyResidue`, U15 `ApplyOptOut`은 durable command/receipt 계약이다. 목적/grant/manifest/operation version을 검증하고 receipt는 새 사용자 job이 아니라 기존 부모 operation의 진행 증거다.
- cross-domain queue reference는 recipient-scoped CommandProjection으로 해소한다. 일반 mutable sender table이나 gateway callback을 조회하지 않는다. recipient는 현재 parent/fence를 확인한 뒤 자기 inbox/receipt를 기록하며 종료된 parent로부터 control copy를 다시 생성하지 않는다.
- operation/event/schema에는 version이 있으며 consumer 지원 범위 밖이면 실행하지 않고 명시적 오류/보류로 처리한다. 신구 consumer 지원 및 deprecation 기간은 NFR/전환 계획에서 확정한다. Python/TS build-consumed bindings와 positive/negative contract fixtures를 같은 schema 원천에서 만든다.
- schema/binding target은 public browser, server-only BFF, internal worker 계약을 분리한다. offline ref/드리프트 검증은 전체 적용하되 public bundle에 내부 intent/grant/locator 타입을 그대로 노출하지 않는다.

| Domain port | 고수준 시그니처 | 제어/결과 계약 |
|---|---|---|
| U3 lifecycle | `deactivateAndRevoke(actor: ActorContext, owner: OwnerRef) -> OwnerFence` | 직접 비활성화/철회와 current epoch 확정. 후속 queue 성공을 기다리지 않음 |
| U3 lifecycle | `issuePurgeDue(owner: OwnerRef, expectedEpoch: Epoch) -> Result<LifecyclePurgeDue, LifecycleConflict>` | 유예 만료/재활성화 경쟁을 원자 판정한 뒤 목적 한정 신호/outbox 발행 |
| U15 consent | `acceptSuppression(grant: VerifiedDigestGrant, intent: OperationIntent, key: SubmissionKey) -> OptOutReceipt` | R3C의 suppression/접수를 send barrier와 결속 |
| U15 sender | `beginHandoff(sender: SystemActor, consent: ConsentRevision) -> Result<HandoffPermit, Suppressed>` | 현재 consent/suppression과 직렬화된 provider handoff 허가. 후속 불명확 I/O는 barrier에 남겨 추적 |
| U1 source | `executeBuild(command: BuildSource, permit: ExecutionPermit) -> DomainReceipt` | 원 source/context/revision에 맞는 준비 결과 또는 실패. 별도 domain outbox로 receipt 발행 |
| 각 domain maintenance | `apply(command: MaintenanceCommand, grant: SystemGrant, manifest: PurgeManifest) -> DomainReceipt` | 자기 owner data에만 목적 제한 실행; receipt는 실제 commit/검증 뒤 생성 |

`OwnerRef`, `Epoch`, `ConsentRevision`, `SubmissionKey`, `EventCursor` 등은 opaque/versioned value type이다. 상세 형식과 허용값은 schema 단계에서 정하고 client 입력을 검증된 actor/context type으로 직접 신뢰하지 않는다.
