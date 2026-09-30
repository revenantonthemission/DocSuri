# AI-DLC 상태 추적 (State Tracking)

## 프로젝트 정보
- **프로젝트명**: DocSuri (연구 지원 애플리케이션)
- **프로젝트 유형**: Greenfield(그린필드)
- **시작일**: 2026-06-15T04:36:30Z
- **현재 단계**: OPERATIONS — U1 Corpus 운영 진입 이후에도 재인셉션 페이즈 4 **U11(문헌탐색·근거형성)** 및 **U12(novelty) 에이전트** 사이클이 이어짐(요구사항 FR-30~38·스토리 US-NV/US-EV·설계/코드 `construction/novelty-agent/`·배포 `Docsuri-Novelty`). _(구 "U1 Corpus에서 AI-DLC 워크플로우 종료" 표기는 이후 U11/U12 작업 수행으로 정정 — 2026-06-30, `aidlc-suite-review` PR #280.)_
- **문서 언어**: 한국어(`aidlc-docs/` 산출물). 업스트림 룰셋(`AGENTS.md`, `.aidlc-rule-details/`)은 영어 유지.

> **📌 SSOT 스코프 (2026-07-08 감사)**: `aidlc-docs/`는 **요구사항·설계 의도·비즈니스 규칙**의 단일 진실이다(느리게 변하고, 경쟁 권위 없음). **런타임/배포/설정 상태**(배포된 임베딩 모델·인덱스 alias·`EMAIL_PROVIDER`·배포/헬스·태스크데프 리비전)의 진실은 **코드/CDK/라이브 AWS**이며 여기 산문에 복제하지 말 것(복제=드리프트). 본 상태파일의 "단일 진실" 문구는 그 시점의 커밋 대조 기록이지 라이브 런타임 보증이 아니다. 근거: `reports/aidlc-ssot-audit-2026-07.md`.

## ⚠️ 검증 재기준선 (Verification Re-baseline) — 2026-06-16

코드 대조 감사(7개 영역 병렬 검증, 각 테스트 스위트 실제 실행) 결과, 아래 항목은 문서가 실제 상태를 **과대 표기**하고 있어 정정한다. **`완료·승인`은 "설계/코드 작성 완료"를 뜻하며 "통합·실 인프라 동작·실 안전장치 작동"을 보증하지 않는다.** 제품은 현재 엔드투엔드 사용 불가(프런트 없음·게이트웨이 없음).

- **U2 미마운트 (High)**: app-shell 부팅 시 discovery는 매번 **graceful-skip**된다(별도 uv 프로젝트 `discovery`가 backend venv에 미설치 → `_mount_discovery` `ModuleNotFoundError`). 통합 앱은 `/auth/*`+health만 노출, **`/api/search` 없음**. 8개 테스트는 레지스트리 *집합*만 단언하고 실제 마운트는 단언하지 않아 skip이 green으로 통과.
- **근거화(Grounding) 실효 없음 (Blocker)**: INV-1 분리는 구조적으로 정확. **U6는 `feature/track6`(미머지)에 구현됨** — 실 `GroundingEnforcementHook.enforce`(`ops/grounding.py`: retrieved 미포함 참조=block·근거 없음=abstain) + `backend/middleware/` 게이트웨이(rate-limit·보안헤더·fail-closed; **단 게이트웨이 자체는 grounding 미호출**). **그러나 라이브 경로 미연결**: `create_app`이 게이트웨이 미설치(테스트만 `configure_u6_middleware` 호출)·discovery 와이어링은 여전히 `StubGroundingHook`(항상 `pass`) 주입(`backend/app.py`·`backend/wiring.py`·discovery 모듈 track6에서 미변경). ⇒ **develop엔 환각/날조 방지(US-D5/US-R1)가 실 경로에서 작동 전무이며, track6 단순 머지만으로도 미해소** — 연결 last-mile(게이트웨이 설치 + 시임에 실 hook 주입, ops↔shared 타입 정합) 필요.
- **CI 부재 (High)**: `.github/workflows/` 없음(CODEOWNERS+PR 템플릿만). `CI=GHA`·`드리프트 CI 가드`는 의도일 뿐 **미구현** — 드리프트 가드/모든 테스트는 수동 실행.
- **U3 결함 (High)**: `auth.py`가 10회 실패 시 `status=LOCKED` 전이 → **BR-A4 무잠금 anti-DoS 규칙 직접 위반**. TOTP MFA·시딩 관리자(BR-A7) 미구현(ADMIN 도달 불가). accounts가 `docsuri_shared` 미소비·DTO 자체 재정의(**SSOT 포크**)·`AccountCreated` raw dict·ObservabilityHub camelCase 오호출.
- **인프라/배포 부재 (High)**: IaC·CD 전무, 인프라 설계는 U3만 존재. U2 real 어댑터(OpenSearch/Bedrock) 미존재 → 실데이터 검색 불가.
- **테스트 수 정정 (Low)**: U1 21→**23**, U2 27→**31**(api extra)/29+1 skip.

**후속 크리티컬 패스**: ① discovery 마운트+CI 마운트-단언 → ② GHA CI(드리프트+pytest+ruff) → ③ U3 정정(BR-A4·SSOT) → ④ **U6 통합 [키스톤·대부분 빌드 완료]: `feature/track6` 머지 + `create_app` 게이트웨이 설치 + discovery 시임에 실 grounding hook 주입(`StubGroundingHook` 대체)** → ⑤ U5 프런트 → ⑥ U2 real 어댑터 → ⑦ 시스템 인프라+U4. _주: track6 머지 시 aidlc-state.md(track6 +5/-1)·audit.md 충돌 예상._

## ✅ 크리티컬 패스 종결 (Critical Path Closure) — 2026-06-18

위 2026-06-16 재기준선이 지정한 후속 크리티컬 패스 ①~⑦가 **전부 랜딩**됐고 시스템 전역 인프라가 AWS에 배포됐다. 본 절은 코드/깃 이력 대조로 확인한 종결 상태를 기록한다(원 재기준선 텍스트는 2026-06-16 시점 사실로 보존; **본 절이 현재 상태의 단일 진실**). 커밋 SHA 병기.

- **① discovery 마운트 + 마운트-단언 — 종결.** `backend/wiring.py::_mount_discovery`가 실제 라우터를 마운트(`/api/search` 라이브); 테스트가 200+`cards` 및 `skipped==[]`를 단언(레지스트리 집합 단언 아님). 커밋 `ae58e0f`·`404c1a7`.
- **② GHA CI — 종결.** `.github/workflows/ci.yml` 8 레인(shared[드리프트 가드 `tools/generate.py --check`+ruff+pytest]·ingestion·discovery[`--extra api`]·ops·backend[마운트 단언]·root-suites[accounts+library]·frontend[tsc+타입 드리프트 가드+lint+vitest+next build]) + `cd.yml`(main 푸시). 커밋 `f9a7e8a`(첫 게이트)·`7edd316`(ops)·`404c1a7`(accounts/library)·`30a0773`·`bd8817b`(frontend).
- **③ U3 정정 — 종결.** BR-A4 무잠금(자동 LOCKED 제거·백오프+CAPTCHA만, LOCKED=관리자 수동 경로 한정)·SSOT 포크 제거(`docsuri_shared` 소비)·BR-A7 실 TOTP MFA+시딩 관리자(ADMIN 도달). 커밋 `bbac74f`·`f835a26`·`9b390b9`.
- **④ U6 통합(게이트웨이+실 grounding hook) — 종결.** `create_app`이 게이트웨이 미들웨어 설치(`configure_u6_middleware`); `_mount_discovery`가 mock·real 양 경로에 실 `GroundingEnforcementHook` 주입(`StubGroundingHook`은 discovery mock 패키지에만 잔존·미배선); 게이트웨이 세션쿠키→`request.state.principal` 주입. 커밋 `ba4a62e`·`b6bb92d`·`568677c`.
- **⑤ U5 프런트 — 종결·배포.** production 패스 머지(PR #63, `86404d1`); HTTPS 프로덕션 배포(Fargate+ALB+CloudFront @ docsuri.org, `d1740b0`); BFF 빌드 복구(`344172e`).
- **⑥ U2 real 어댑터 — 종결.** OpenSearch k-NN+BM25 + Bedrock Cohere 질의 임베더 + EventBridge 퍼블리셔; env 토글로 mock/real. 커밋 `b87348d`·`a25d8ed`.
- **⑦ 시스템 인프라 + U4 — 종결·배포.** U4 라이브러리 머지(`b70f2ee`). 시스템 전역 Infrastructure Design(`construction/infrastructure-design/infrastructure-design.md`, `ac21ae2`); AWS CDK Python IaC 5 스택(Network·Search·Compute·Ingestion·Frontend, `ddf8858`); CD 파이프라인(ECR 빌드·푸시+ECS 롤링, `db1b187`); 프로덕션 DB/세션 실연결(RDS Postgres+ElastiCache TLS, `01fd553`·`5f7acce`); API HTTPS 하드닝(CloudFront+ACM+시크릿 오리진, `504cb64`·`28ed940`); CloudWatch EventStore 어댑터(`8b54b62`)·SQL 마이그레이션 러너(`5de4348`); SES 실 발송(boto3+도메인 인증+IAM, `50da0d5`)+바운스/불만 자동 억제+SNS(`0437b40`).

**라이브 배포(런타임·리포지토리 대조 불가)**: 4 CDK 스택 라이브 배포·API ALB healthy = 계정 028317349537/서울(`ap-northeast-2`), 팀 보고(2026-06-17). 본 종결은 IaC 코드·커밋 대조까지 보증하며 실 배포 헬스는 AWS 콘솔/자격증명 확인 필요.

### 잔여 항목 (Residual)
- **CI 린트 사각 (Low)**: 루트 `tests/` 트리를 린트하는 레인 없음 → `ruff check .` 루트 기준 `tests/accounts/*` F401 9건이 CI에 미노출(전부 `--fix` 가능). backend 레인은 `modules/` 제외·root-suites 레인은 모듈 소스만 린트.
- **ci.yml 헤더 주석 stale (Low)**: 1~5행 주석이 "tests/accounts 미연결"이라 표기하나 현 `root-suites` 잡이 해당 스위트를 실행.
- **테스트 수 드리프트 (Info·benign)**: 스위트 증가로 문서 수치 stale(U1 23→26·U6 31→34·U4 컴포넌트 분할·U2 42+1skip). 회귀 아님.
- **Operations 프레임워크 갭**: AI-DLC 룰셋은 Build and Test에서 종료(Operations=placeholder)이나 실 AWS 프로덕션 배포가 프레임워크 밖에서 수행됨 — 운영 런북/롤백/모니터링 문서 미수립(§OPERATIONS 참조).

## 사후 결정 / 핫픽스 (Post-Construction — 규범은 각 유닛 BR·plan `사후 결정` Q)

- **U1 전문 추출 결함 정정 (2026-06-23, #139·커밋 `0ced380`·브랜치 `fix/summarization-pipeline`)**: arXiv e-print(gzip/tar) 미해제 디코딩으로 전문 ~44% 깨짐(�) → **arXiv HTML(native→ar5iv) 우선 + PDF 폴백**으로 교체(결정 D = U1 FD plan Q18 · BR-29). 보관=정규화 평문 1종, 뷰어=평문(앵커 유지). 리치 HTML 렌더/보관은 에셋 패널(FR-17)과 그림·표 겹쳐 에이전트 단계로 분리. `pdfplumber` 코어 승격.
- **U7 번역 입력 정렬 (2026-06-23, P2·커밋 `4039bde`·브랜치 `fix/summarization-pipeline`)**: 전문 번역(scope=full)이 정제 안 한 원문을 초록 프롬프트에 전송 + 길이판정(`refined`)↔전송(`raw`) 불일치 → 번역 입력=`refined.body` 통일·프롬프트 scope 분기(결정 A = U7 FD plan Q18 · BR-S2).
- **🧭 DocModel 기반 전환 — 결정 게이트 수립 (2026-06-23, 미착수·브랜치 예정 `feat/docmodel-foundation`)**: "요약/번역 입력을 평문→구조화 문서모델(doc-model)로 전환 + 자체 리치뷰 + 에이전트 준비" 피벗의 단일 진실원천 게이트 작성 → `construction/plans/docmodel-foundation-pivot-plan.md`. **확정 결정 D1~D8**: doc-model=arXiv HTML 결정적 파싱 JSON(표=데이터·수식=LaTeX·그림=webp 참조)·U7 입력 평문→doc-model 교체(로직 불변)·PDF 원문 미저장(다운로드 버튼 없음)·자체 리치뷰=doc-model 콘텐츠 재렌더(PDF.js 아님)·비전=batch 아닌 에이전트 on-demand 툴·생성 lazy+`(paperId,ver)` 캐시·소스 무관 설계·TD-12(표=PDF크롭) 재검토. **저장**: `doc-model/{id}/v{ver}.json`(구조화 통합) + 기존 `assets/*.webp`(이미지 분리·참조) + 기존 `paper_asset` RDS. **열린 Q1~Q8**(코드 전 확정): ⚠️Q1 arXiv HTML 커버리지 스파이크(배포 확정 선결)·Q3 doc-model 스키마·Q7 요구사항 재진입 여부·Q8 P3(맵리듀스)=doc-model 후속. `:159-162` 비전 항목은 본 doc-model 기반으로 흡수. **blast-radius=기존 U1/U7/U5 FD·TD-12·requirements *편집*(신규 문서는 게이트뿐)**.
- **🧭 DocModel 전환 — blast-radius 기존 문서 편집 (2026-06-23, 브랜치 예정 `feat/docmodel-foundation`)**: 게이트 D1~D8·Q권장안 기준으로 §3 기존 유닛 문서 *편집* 진행(신규=게이트뿐). **U1**: BLM `business-logic-model`(스코프 피벗 노트·§7 doc-model lazy 생성·캐시 단계 신설·§6.3 철회 무효화 연동) · `business-rules`(BR-29 carve-out 뒤집기 — 리치 렌더 범위 안 + ar5iv 필수 / **BR-30 신설** doc-model 구조·생성) · `tech-stack-decisions`(**TD-12 재작성** 표=PDF크롭→HTML 데이터 · **TD-16 신설** HTML 파서 lxml/BeautifulSoup·MathML→LaTeX·입력 보안 · TD-11 최후폴백 강등) · `infrastructure-design`(§1.1b `doc-model/` prefix·SSE-KMS·lazy 캐시 라이프사이클 + IAM 빌더/읽기 역할). **U7**: `domain-entities`(SourceText=doc-model·RefinedSource **+tables[]**·docModelRef) · `business-logic-model`(SourceSelector·InputRefiner doc-model 직접 취득·프롬프트 표=데이터·수식 LaTeX) · `business-rules`(BR-S2/S3) — **로직 불변, 입력만 업그레이드(D2)**. **U5 리치뷰**: 실제 컴포넌트가 사는 `u7-summarization-frontend` `FullTextViewer`→**`DocModelViewer`** 본문화(목차·KaTeX·표 컴포넌트·webp 그림·앵커; `getFullText`→`getDocModel` lazy) + U5 `frontend-components §6`(AssetGallery=그림 전용 축소·**표 크롭 폐기→표 컴포넌트** D8·앵커 매처 재사용). **미편집(잔여)**: requirements.md(FR-12/리치뷰 1급화/§12 — Q7 재진입 결과 대기) · `shared/dtos/`(Q3 doc-model 스키마 SSOT) · U7 NFR/Infra 어댑터 경량 정합. **다음=코드**(`feat/docmodel-foundation`). _커밋·push 보류(사용자 승인 후)._
- **🧭 DocModel 전환 — Q3 스키마 + Q7 요구사항 재진입 완료 (2026-06-23, `fix/summarization-pipeline`, 미푸시)**: **Q3(커밋 `ff258f7`)** — doc-model 계약 확정: **중첩 섹션 트리 + 결정적 블록 id 앵커**. `shared/dtos/docmodel.schema.json`(JSON Schema 2020-12·20 defs·양성/음성 검증) + 스펙 SSOT `construction/shared/docmodel.md` + overview/README 등재(계약 5번째). 루트=getDocModel 응답 union, 아티팩트=DocModel(meta+sections[]); 블록 6종(paragraph·table·formula·figure·list·code); 표=rows/cols·수식=latex·그림=AssetRef(assetId 참조, url 없음 SEC-9); provenance(sourceTier 사다리). **Q7(미커밋)** — 요구사항 재진입: 질문지 `inception/requirements/requirement-verification-questions-docmodel.md` Q1~Q7(전부 게이트 권장안 + 리치뷰=신규 FR-18) → `requirements.md` 등재: **FR-12 개정**(입력=doc-model·앵커=doc-model id)·**FR-17 개정**(그림=이미지·표=데이터 D8)·**FR-18 신설**(자체 리치뷰 1급 D4)·§12 doc-model 카브아웃(PDF 미저장 D3·비전 제외 유지 D5·외부소스 일괄캐시 제외 D7)·QT-5 앵커 보강·§13 추적성. **다음=코드**(`feat/docmodel-foundation`): U1 DocModelBuilder(ar5iv 사다리·lxml)·getDocModel API·U7 입력 어댑터·DocModelViewer + summarization.schema Anchor.target 의미 명확화. _push·PR 보류(승인 후)._
- **사용자 업로드 PDF → DocModel 계약/PR1 진행 (2026-07-05, stacked on PR #388)**: PR0 `feat/pr0-userdoc-docmodel-contract`에서 `paperId=userdoc:{uuid}`, `recordRef=upload:{ownerId}:{jobId}:{attachmentId}`, `SourceTier=pdf`, arXiv URL 합성 금지, `BUILD_USER_DOC_MODEL` S3-source payload를 동결. PR1 `feature/pr1-userdoc-docmodel-ingestion` / **PR #390**에서 U1 ingestion consumer 구현 완료: `JobKind.BUILD_USER_DOC_MODEL`, S3 user-document source, pdfplumber-only `build_user_doc_model`, 기존 worker DLQ 격리 경로, PBT payload round-trip. PR #390 계약 리뷰 후 payload validation을 동결 계약에 맞게 강화(`jobId=userdoc-{uuid}`, `paperId=userdoc:{uuid}`, `version=1`, `recordRef=upload:{ownerId}:{jobId}:{attachmentId}` exact match). 검증: focused ingestion 35 passed, full ingestion 281 passed/1 skipped, ruff clean, compileall clean, diff check clean, Branch name check passed. 참고: #389는 `feat/` prefix 실패 후 원격 branch rename 과정에서 GitHub가 close 처리.
- **사용자 업로드 PDF → DocModel PR2 backend producer (2026-07-05, branch `feature/pr2-userdoc-docmodel-backend`)**: U11 evidence/research와 U12 novelty backend에 user PDF upload → S3 → `BUILD_USER_DOC_MODEL` enqueue → bounded doc-model polling 경로 구현. 공유 coordinator `backend.modules.user_docmodel`가 `paperId=userdoc:{uuid}`·`recordRef=upload:{ownerId}:{jobId}:{attachmentId}`를 생성/검증하고, evidence/research upload endpoint가 `objectKey`/`paperId`/`recordRef`를 반환한다. Evidence/research는 준비된 doc-model을 attachment extraction source로 전달하고, 미준비 PDF는 계약 문구(`[첨부 안내] PDF 본문을 해석하지 못해 첨부 근거는 제외했습니다.`)로 저하한다. Novelty는 raw PDF manuscript upload를 허용하고 `manuscript_pdf_parse_unavailable`로 fail-soft 저하하며, `userdoc:` sourceRef에는 arXiv URL을 합성하지 않는다. 검증: focused backend PR2 suite 103 passed, broad backend suite 453 passed/4 skipped, backend ruff clean, compileall clean, diff check clean. 다음: PR3 frontend binary upload wiring.
- **PR2 hardening before PR3 branch (2026-07-05, branch `feature/pr2-userdoc-docmodel-backend`)**: PR3 착수 전 PR2 워크트리의 backend hardening 변경을 PR2에 먼저 반영. Evidence/research의 readiness polling을 request loop 밖 threadpool로 이동, S3 user-doc metadata filename을 ASCII-safe percent-encoding으로 저장, doc-model reader exception은 계약대로 fail-soft `None`으로 저하. 검증: `pytest backend/tests/test_user_docmodel.py backend/tests/test_evidence.py backend/tests/test_research.py` 37 passed, touched ruff clean, diff check clean.
- **AI-DLC 워크스페이스 미추적 파일 정리 (2026-07-05, branch `feature/pr2-userdoc-docmodel-backend`)**: untracked 파일을 AI-DLC 위치 규칙으로 분류. `.agents/`(tracked `.claude/skills`의 Codex-local mirror), `.claude/worktrees/`, `.pnpm-store/`는 로컬 도구/캐시로 `.gitignore`에 추가. `aidlc-docs/inception/plans/`의 hackathon proposal, architecture D2/PNG, 팀 프로젝트 계획서 `.docx`는 문서 산출물로 추적 대상으로 정리. 검증: Markdown box-drawing diagram 제거 후 텍스트 대안으로 대체, D2 compile 2건 성공, `.docx` zip integrity OK, `git diff --check` clean.
- **사용자 업로드 PDF → DocModel PR3 frontend binary upload (2026-07-05, branch `feature/pr3-userdoc-docmodel-frontend`)**: Agent Chat frontend가 PR2 backend upload 계약을 호출하도록 구현. BFF/transport가 `application/pdf` raw body를 JSON 변환 없이 전달하고, PDF attachment는 browser-local `sourceFile`을 임시 보관하되 job/message JSON에서는 제거한다. Evidence/research는 `/api/research/attachments` 선업로드 후 `objectKey`/`paperId`/`recordRef`만 job payload에 포함하고, novelty는 manuscript job 생성 후 `/api/novelty/jobs/{jobId}/manuscript?fileName=...`로 raw PDF를 업로드한다. md/txt `contentText` 경로는 유지. 검증: frontend `tsc --noEmit` clean, targeted Vitest 34 passed, full frontend Vitest 248 passed, `next build` passed.
- **PR #391 review fixes (2026-07-05, branch `feature/pr0-userdoc-docmodel-contract`)**: evidence/research PDF attachment reuse now validates client-returned `objectKey` against the authenticated owner, evidence upload prefix, and attachment scope before doc-model enqueue/poll. Malformed `paperId`/`recordRef` metadata is translated to 422 at evidence and research API boundaries instead of surfacing as 500. 검증: focused review-fix suite 101 passed, broad backend tests 215 passed/1 skipped, touched backend ruff clean, compileall clean, diff check clean.

## 워크스페이스 상태
- **기존 코드**: 없음(워킹 트리 블랭크 슬레이트; 이전 데모 사이클 폐기, git `ba3b6a9`로 복구 가능)
- **리버스 엔지니어링 필요**: 아니오(Greenfield — 디스크에 소스 파일 없음)
- **워크스페이스 루트**: 리포지토리 루트(머신별 상대; 예: `<홈>/Projects/DocSuri`) — 절대 경로는 머신마다 다름
- **프로그래밍 언어**: (미정 — Construction 단계)
- **빌드 시스템**: (미정 — Construction 단계)
- **프로젝트 구조**: 비어 있음(AI-DLC Prompt 1부터 재시작)

## 코드 위치 규칙
- **애플리케이션 코드**: 워크스페이스 루트(절대 aidlc-docs/ 안에 두지 않음)
- **문서**: aidlc-docs/ 전용
- **구조 패턴**: code-generation.md의 Critical Rules 참조

## 확장 구성 (Extension Configuration)
| 확장 | 활성 | 모드 | 결정 시점 |
|---|---|---|---|
| Security Baseline | 예 | Full(15개 규칙 전부 차단성) | Requirements Analysis (2026-06-15); 재확인 2026-09-18 |
| Resiliency Baseline | 예 | Custom single-Mac profile(RESILIENCY-08 multi-zone fault-isolation 면제; RESILIENCY-09 horizontal autoscale N/A/로컬 capacity gate 대체; 나머지 적용 규칙 차단성) | Requirements Analysis (2026-06-15); single-Mac 재기준 2026-09-18 |
| Property-Based Testing | 예 | Full(10개 규칙 전부 차단성) | Requirements Analysis (2026-06-15); Partial→Full 변경 2026-09-18 |

_Resiliency 옵트인은 `requirements.md` 확정 전에 필수 요구사항 명확화를 유발: RTO/RPO + DR 전략(RESILIENCY-02), 변경 관리(RESILIENCY-03), 장애 대응(RESILIENCY-15). `inception/requirements/requirement-clarification-questions.md`에서 질의함. 후속 단계로 보류: CI/CD + 롤백 + 배포 방식(RESILIENCY-04 → NFR Design), 리전 토폴로지(RESILIENCY-08 → Infra Design), 복원력 테스트(RESILIENCY-14 → NFR Design)._

## 단계 진행 (Stage Progress)

### 🔵 INCEPTION 단계
- [x] 워크스페이스 탐지(Workspace Detection) — Greenfield (2026-06-15)
- [~] 리버스 엔지니어링 — N/A (Greenfield, 건너뜀)
- [x] 요구사항 분석(Requirements Analysis) — 완료·승인 (2026-06-15); `requirements.md`. 명확화 2라운드; 모순 전건 해소; 확장 전부 활성
- [x] **요구사항 개정 — 신규 유닛 U7(요약/번역) 편입 (2026-06-18, 팀 합의·브랜치 `feature/u7`·PR #108)**: U1~U6 빌드·배포 완료 후 Requirements Analysis 재진입. 명확화 `requirement-verification-questions-u7.md` Q1~Q7 전부 A(초안 권장안) → `requirements.md`에 **FR-12(AI 요약·구조화·앵커)·FR-13(한국어 번역·용어집)·FR-14(개인화: persona/뷰/용어집)·NFR-P2(온디맨드 비-SLA)·QT-5(요약/번역 근거화)·NFR-C1 U7 Sonnet 비용 라인 보강·C-2 추출 경계·§12 제외(P3·자유입력)** 등재. 설계 입력 `aidlc-docs/inception/requirements/summarization-translation-pipeline.md`(2026-06-18 레포 루트→aidlc-docs 재배치 완료). **다음: User Stories(U7) → Units Generation(U7 등재·U1/U6 의존) → Construction 유닛 루프.** 리뷰 게이트 대기.
- [x] 사용자 스토리(User Stories) — 계획 승인(PQ1–5=A); Part 2에서 `stories.md`(스토리 **21개**, 6 에픽: Hero 1 + Discovery 7 + Accounts 2 + Library 3 + Ingestion 3 + Reliability 5) + `personas.md`(P1 박지훈, P2, OP) 생성; FR-1..11 전부 커버; **승인 완료**. **적대적 비평 패스 완료(2026-06-15, 7/7 critic)** → requirements/stories 보정 반영.
- [x] Workflow Planning — `execution-plan.md` **승인 완료**. 판정: 리버스 엔지니어링만 SKIP, 그 외 전 단계 EXECUTE.
- [x] Application Design — 완료(리뷰 게이트). `application-design/` 5문서(components·component-methods·services·component-dependency·application-design); 6 유닛(U1~U6); 적대적 3 critic→blocking/major 보정 반영(근거화 단일 권위, SearchExecuted 생산자, SEC-8 단일 결정점, QT-3 소유자, 백도어 차단)
- [x] Units Generation — 완료(리뷰 게이트). `unit-of-work.md`·`unit-of-work-dependency.md`·`unit-of-work-story-map.md`; 6 유닛·4 배포 단위·모노레포·데모 우선 순서; 스토리 21개 전수 매핑·코드 의존 DAG(adversarial 검증 solid)
- [ ] Units Generation — **EXECUTE** (예비 유닛: U1 인제스천, U2 디스커버리 API, U3 계정/인증, U4 검색저장/라이브러리, U5 모바일 웹, U6 신뢰성/운영)
- [x] **사용자 스토리 개정 — U7(요약/번역) 에픽 추가 (2026-06-18, 팀 합의·`feature/u7`·PR #108)**: `stories.md`에 **에픽 6 — 요약/번역**(US-S1 구조화 요약·US-S2 한국어 번역·US-S3 출처보기+기권·US-S4 개인화·US-S5 온디맨드 응답·US-S6 비용게이트+근거화 운영) 6 스토리 추가 → 총 27 스토리/7 에픽. P1(US-S1..S5)·OP(US-S6) 매핑, FR-12..14·NFR-P2·QT-5 전수 커버. 페르소나 무변경(P1·OP가 U7 커버).
- [x] **Units Generation 개정 — U7 정식 등재 (2026-06-18, 팀 합의·`feature/u7`·PR #108)**: `unit-of-work.md`(U7 Summarization 유닛 정의·배포 단위 ①+③옵션·코드트리 `backend/modules/summarization/`·확장 트랙)·`unit-of-work-dependency.md`(U7 행/열 추가, U7→U1 capability read·U7→U6 `shared/ports` lib·U5→U7/U6→U7 sync, **코드 DAG 비순환 유지 검증**, 온디맨드 요약 ASCII 흐름)·`unit-of-work-story-map.md`(US-S1..S5 Owner=U7·US-S6 Owner=U6 기여=U7, 전수 27 스토리 검증) 갱신. **7 유닛·4 배포 단위(U7=API 모듈, 초장문만 비동기 잡 옵션).** 리뷰 게이트 대기. **다음: U7 Construction 유닛 루프(Functional Design부터).**
- [x] **요구사항 개정 — 신규 유닛 U8(인용 그래프/각주 트리) 편입 (2026-06-19)**: 명확화 `requirement-verification-questions-citation-graph.md` 22문 답변 확정(Q3/Q10=X, Q4/Q14=B, 나머지 권장안) → `requirements.md`에 **FR-15(각주 트리/backward references)·FR-16(노드 저장/연동)·NFR-P3(온디맨드 비-SLA)·QT-6(인용 엣지 정확도+그래프 불변식)·§12 카브아웃** 등재. v1은 논문 상세보기 페이지의 backward references 각주 트리로 한정, FE 구현·forward citations·3-hop 이상은 제외.
- [x] **요구사항 개정 — Cohere Embed v4.0 마이그레이션 편입 (2026-06-23)**: 명확화 `requirement-verification-questions-v4-migration.md` 4문 전수 답변(A) 반영 → `requirements.md`에 **FR-17(듀얼 라이트)·NFR-M2(Blue/Green 마이그레이션)·NFR-S2(v4 모델 컷오버)** 등재. 기존 v3 인덱스와의 비호환성을 무중단으로 해결하기 위해 신규 인덱스 백필, 듀얼 라이트, 그리고 Instant Cutover 전략을 확정.
- [x] **요구사항 개정 — 재인셉션 페이즈 1 / U1 Corpus 완성형 편입 (2026-06-26, PR #220 머지 후)**: `requirement-verification-questions-u1-corpus.md` Q1~Q12 답변을 **전부 A**로 확정하고, 재인셉션 차터 D6을 `requirements.md`에 반영. **FR-6 전면 개정**(arXiv HTML→PDF, Semantic Scholar/OpenAlex PDF→GROBID, cross-source dedup, FullText, eager DocModel 완성형, DocModel(Block) chunk/embedding/OpenSearch/S3, source별 watermark, scheduler/retry/DLQ, `(paperId,version)` 버전 정합), **FR-18 lazy→phase-1 eager 정정**, **NFR-C1 U1 eager 비용 게이트**, **RES-7/8/9 멀티소스 운영 신호**, **QT-9 U1 Corpus 품질/불변식**, **C-1/§12 PDF 원문 미저장·transient GROBID 카브아웃**, 추적성 행 추가. 구 doc-model Q7(lazy)는 phase-1 Corpus 범위에서 대체하고, lazy 빌드는 누락분·재빌드·백필 경로로 축소. **다음: 리뷰 승인 후 User Stories/Workflow Planning.**
- [x] **사용자 스토리 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**: 신규 에픽 없이 기존 **에픽 4 — 인제스천**을 최소 개정. `u1-corpus-user-stories-assessment.md`와 `u1-corpus-story-generation-plan.md` 생성(계획 결정 전부 A, 체크리스트 완료). `stories.md`의 **US-I1**을 멀티소스 Corpus+eager DocModel+DocModel(Block) 인덱싱으로, **US-I2**를 source별 watermark incremental update로, **US-I3/US-R3/US-R4**를 retry/DLQ/비용/관측 기준으로 보강. `personas.md` OP에 U1 Corpus eager 비용·watermark·DLQ 관측 책임 반영. FR-6/FR-18/NFR-C1/RES-7/8/9/QT-9 추적성 갱신. **다음: Workflow Planning.**
- [x] **Workflow Planning — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**: `u1-corpus-workflow-plan.md` 생성 후 skip decision review를 반영해 Application Design은 **U1-only amendment EXECUTE**, Units Generation은 **review EXECUTE**로 정정. U1 Construction 루프(Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation)와 Build & Test EXECUTE. 모듈 순서: 공유 계약 확인 → U1 Corpus 파이프라인 → 인프라/관측 → U2 alias/config → backfill → cutover. Mermaid 시각화와 텍스트 대체 포함.
- [x] **Application Design 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**: 전역 재설계 없이 U1 관련 5문서만 최소 개정. `components.md`/`component-methods.md`/`services.md`/`component-dependency.md`/`application-design.md`의 U1 arXiv-only 설계를 멀티소스 Corpus로 정정: `CorpusSourceAdapterSet`, `FullTextExtractionProcessor`, `SourcePriorityDeduplicationGuard`, `DocModelBuildCoordinator`, `DocModelBlockChunker`, `CorpusIndexWriter`, `CorpusRefreshScheduler`. GROBID transient PDF, eager DocModel, DocModel Block anchor, index generation, source watermark, QT-9 추적성을 Application Design 수준에 반영.
- [x] **Units Generation 리뷰 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**: `u1-corpus-units-review-plan.md` 생성 및 `unit-of-work.md`/`unit-of-work-dependency.md`/`unit-of-work-story-map.md` 최소 개정. 결론: 신규 유닛 없음, 기존 **U1 Ingestion**이 멀티소스 Corpus 생성 파이프라인 owner 유지. U2/U7/U11은 Corpus/DocModel capability read 소비자이며 코드 의존 그래프 비순환. U1 arXiv-only 문구를 멀티소스 Corpus/DocModel/OpenSearch/S3 wording으로 정정. **다음: 리뷰 승인 후 U1 Functional Design.**
- [x] **INCEPTION 완료 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**: Requirements Analysis, User Stories, Workflow Planning, U1-only Application Design amendment, Units Generation review 모두 승인 완료. PR 본문 `202606261630_PR.md` 작성. 다음 단계는 Construction의 U1 Functional Design.
- [x] **요구사항 개정 — 신규 유닛 연구 에이전트(대화형 문헌탐색·근거형성 / 아이디어 novelty) 편입 (2026-06-24, 브랜치 `feature/research-agent`·PR #170)**: 명확화 `requirement-verification-questions-research-agent.md`(인셉션 고도 18문항; **Q5=B·Q7=A[재현성 판정 제외]·Q13=X·Q14=B·Q18=A, 나머지 권장**) → `requirements.md`에 **FR-22(대화형 근거형성·모드 A·v1)·FR-23(novelty 비교·모드 B·차기 구현)·FR-24(대화형 입력+첨부)·FR-25(결과·세션 영속+전용 네비 진입)·NFR-P5(온디맨드 비-SLA·비차단)·NFR-C1 Agent 비용 보강·QT-8(근거·novelty 인수)·§12 Agent 카브아웃·C-2 추출·비교 경계** + 성공기준 #7·추적성 9행 등재. **v1=모드 A 구현, 모드 B(novelty)는 다음 사이클**(Q4=A). 생성 산문·재현성 판정 제외(C-2). 설계 입력 `summarization-translation-pipeline.md`(line 374 "파이프라인 재사용 + 유사논문 검색 노드"). **HOW(코퍼스 확장·외부 API·출력 스키마·근거표 컬럼·LLM 모델·멀티턴·네비/세션 UI)는 Construction(Functional/NFR/Infra Design) 라운드로 이월.** 유닛 번호 미배정(마이페이지 U10·개인화추천·트렌드/알림·구독제 이후). **Q18=A → Requirements 등재 완료; User Stories는 별도 승인으로 진행, Units·Construction은 후속.**
- [x] **재인셉션 차터/베이스라인 개정 — 에이전트 2유닛 분리 정리 + 로드맵 갱신 (2026-06-28, 브랜치 `chore/reinception-research-split`)**: 리버스 엔지니어링 결과 반영. ① **구 u11(통합 연구 에이전트) 단독 문서 일괄 제거** — D2(2026-06-26) "문헌탐색·근거형성 / 연구아이디어 **2유닛 분리**" 승인으로 단일 u11 산출물이 stale화됨: `construction/u11-research-agent/`(8) + `construction/plans/u11-research-agent-*`(4) + `inception/plans/research-agent-*`(3) + `requirement-verification-questions-research-agent.md` 삭제. ② **연구아이디어 Agent 구체 방식 삭제** — 차터 §3 페이즈 6의 상세 파이프라인(Research Gap→Novelty→Proposal ASCII)·사용 Tool 목록 제거, "방식 미확정·인셉션 질문지로 결정"으로 축소. ③ **문헌탐색·근거형성 Agent** — 구체 파이프라인/방식은 인셉션 질문지로 결정, **UI 방식(채팅 형식·모드만 다르게)은 유효**로 명시. ④ **로드맵 갱신**(차터 §3 + `code-baseline-2026-06.md` 표): 페이즈 3(요약/번역)·4(Grounding)를 **하나로 병합**(함께 진행), 이후 한 칸씩 당김(5→4 문헌탐색·6→5 연구아이디어·7→6 Corpus대량·8→7 검색품질) — **7 페이즈**(개인화 추천 페이즈는 도입 검토했다가 제외). ⑤ **담당 정정**: 페이즈 4(문헌탐색·근거형성) **본인→화랑님**, 본인 담당 페이즈(2·3·7)는 **본인→유진님** 표기, 페이즈 5(연구아이디어)=석현님 유지(석현님·준희님 등 팀원은 '님' 표기). ⑥ **5→4 의존 완화**: 연구아이디어→문헌탐색 단방향 의존을 **확정에서 "기본 제안"으로 완화**(차터 D2/D5/§4) — 의존 여부·범위는 requirements 질문지에서 확정, D5 계약게이트 병렬은 "의존 확정 시"에만 적용. ⑦ **구 U11 임베디드 항목 제거(완료)**: `requirements.md`(FR-22~25·NFR-P5·QT-8·§12 Agent 카브아웃·C-2 Agent 경계·성공기준 #7·추적성 9행), `stories.md`(에픽9 US-RA1~8·페르소나맵·추적성·푸터, 53→45 스토리), `unit-of-work*.md`(U11 행/주석/배포·코드트리, 의존 매트릭스 U11 열·행, 스토리맵 US-RA·카운트), 계정삭제 캐스케이드의 U11/연구세션 참조까지 정리. 신규 인셉션 사이클이 2유닛으로 재생성할 자리만 주석으로 표시.
- [x] **에이전트 의존 확정(A) + 문헌탐색·근거형성 유닛 질문지·공유 계약 골격 (2026-06-28, 브랜치 `chore/reinception-research-split`)**: ① **5→4 의존 확정(A)** — 연구아이디어→문헌탐색 단방향 의존을 "기본 제안"에서 **확정**으로 back-sync(차터 D2/D5/§3·§4·§4.1·§4.2·§5), D5 계약게이트 병렬 적용. 계약 *디테일*은 4 질문지 후 동결. ② **문헌탐색·근거형성 유닛 인셉션 질문지 생성**(`requirement-verification-questions-literature-evidence-agent.md`, 담당 화랑님, Q1~Q18 초안·답변 대기) — 차터가 미룬 HOW(근거 산출물·근거표·검색 scope·코퍼스·모델·동기/비동기·세션·UI·비용·보안 + **5에 노출할 근거 출력 DTO**)를 질의. novelty/모드 B는 범위 밖(페이즈 5). ③ **공유 Tool 포트 계약 골격 갱신**(`agent-tool-port-contract-draft.md`, 구 #223[CLOSED] 초안을 페이즈 4→5 번호·의존 A·grounding 페이즈 3으로 승격): `EvidenceFormationPort.form_evidence` + `EvidenceResult/EvidenceItem/SourceRef`(IndexRecord·DocModel Block id·Summary Anchor 재사용). evidence 필드 디테일은 질문지 Q1~Q3 종속, 확정 시 `shared/`로 승격·동결 → D5 병렬 잠금 해제. ④ PR #232 리뷰 후속: personas.md/account-production Q/docmodel-pivot-plan의 폐기 ID(QT-8·FR-22) 댕글링 주석 정리, u2-discovery NFR-P5 오인용→FR-20.
- [x] **요구사항 개정 — U3 Accounts 프로덕션화 (2026-06-24, 브랜치 `feature/u3-accounts-production`)**: 팀 보고 'login not operating' 진단 결과 U3 코드·계약·인프라 정상, 근인 = `/auth/login` **422**(`LoginRequest extra='forbid'`+필수필드 → 바디 형상 스큐)가 프런트 `normalizeHttpError` `unknown`('문제가 발생했습니다…')으로 표면화(라이브 프로브 재현: 정상 `{email,password}`→401, 추가/누락 필드→422). 단발 패치 대신 사용자 지시로 U3를 프로덕션급 확장 → Requirements Analysis 재진입. 명확화 `requirement-verification-questions-account-production.md` Q1~Q8 답변(**Q1=ABCD·Q2=A·Q3=Google·Q5=A**, 미서피스 **Q4·Q6·Q7·Q8=권장**) → `requirements.md`에 **FR-26(비밀번호 재설정: Resend·단일사용 30분 토큰·전세션 무효화·열거방지)·FR-27(소셜 OIDC, Google v1·검증이메일 자동연결·신규 ACTIVE)·FR-28(계정 라이프사이클: 비번/이메일 변경·소프트삭제+유예 비동기파기+owner-scoped 캐스케이드 U4/U2/U11)·FR-29(인증 입력 견고화: 공개 인증 추가필드 무시+4xx/422 명확 표면화 — 422 근인 해소)** + 성공기준 #8 + 추적성 행 + **BR-A8~A12 참조** 등재. 경계: U3=백엔드 엔드포인트/규칙 소유, **U10 마이페이지=프로필/설정 UI만**(타 팀원 병행·미커밋). **다음(별도 승인): User Stories(에픽 3 Accounts 보강: 재설정·소셜·라이프사이클) → Units Generation(U3 확장·U10 경계 주석) → Construction(U3 Functional/NFR/Infra Design **HOW 라운드**: OIDC 라이브러리·재설정 토큰/소셜 연결 테이블 스키마·세션 재발급·삭제 유예 잡·DB 마이그레이션 → Code Generation → Build&Test).** 리뷰 게이트 대기.
- [x] **사용자 스토리 개정 — U3 Accounts 프로덕션화 (2026-06-24, `feature/u3-accounts-production`, 사용자 "approved & continue" 승인)**: 방법론=기존 에픽 기반·INVEST·Given/When/Then(9개 선례 동일; `inception/plans/story-generation-plan-account-production.md` 권장안 일괄 채택). `stories.md` **에픽 2 — 계정**에 5 스토리 추가(**US-A3 비밀번호 재설정·US-A4 소셜 로그인 Google OIDC·US-A5 비번/이메일 변경·US-A6 계정 삭제(소프트+유예 캐스케이드)·US-A7 인증 에러 표면화·입력 견고화**) → 총 **53 스토리/10 에픽**. 페르소나 P1/P2 매핑(US-A1..A7)·추적성(FR-26→A3·FR-27→A4·FR-28→A5/A6·FR-29→A7)·커버 푸터 갱신. FR-26~29 전수 커버. **다음(별도 승인): Units Generation(U3 확장·U10 경계 주석) → Construction(Functional/NFR/Infra Design HOW 라운드).** 리뷰 게이트 대기.
- [x] **Units Generation 개정 — U3 Accounts 프로덕션화 (2026-06-24, `feature/u3-accounts-production`, 사용자 "approve & continue" 승인)**: 신규 유닛 없음 — 기존 **U3 확장**. `unit-of-work-story-map.md`에 US-A3~A7 Owner=U3 매핑(총 **53 스토리**·미할당 0) + U3 요약/카운트/노트 갱신. **경계(Q2=A)**: U10 마이페이지(타 팀원)=프로필/설정 UI만·U3=백엔드 `/auth/*` 소유. **신규 의존**: U3→외부 Google OIDC(콜백). **삭제 캐스케이드=이벤트 구동**(U3 `AccountDeleted` 발행 → U4/U2/U11 구독·각자 owner-scoped 파기)으로 U3↔U4/U2/U11 **순환 회피**(의존성 역전, U11↔U6 `shared/ports` 패턴)·코드 DAG 비순환 유지. 기존-유닛 확장이라 `unit-of-work.md`(유닛 정의)·dependency 매트릭스 세부는 story-map 노트로 일원화. **다음(별도 승인): Construction — U3 Functional Design(HOW: OIDC 인가코드 흐름·재설정 토큰/소셜 연결 테이블 스키마·AccountDeleted 이벤트 계약·삭제 유예 잡·DB 마이그레이션) → NFR/Infra Design → Code Generation → Build&Test.** 리뷰 게이트 대기.

### 🟢 CONSTRUCTION 단계 — U3 Accounts 프로덕션화
- [x] **Functional Design 개정 — U3 Accounts 프로덕션화 (2026-06-24, `feature/u3-accounts-production`, 사용자 "Functional Design only, then gate" 선택)**: 코드 없이 **HOW 설계만**(추상·기술 무관). `business-rules.md` **BR-A8~A12**(재설정 토큰 단일사용·소셜 OIDC 검증이메일 연결·이메일 변경 지연반영·삭제 소프트+유예+`AccountDeleted` 이벤트 캐스케이드·공개 인증 입력 추가필드 무시) + 추적성 5행. `domain-entities.md` **§4**(PasswordResetToken·SocialIdentity·EmailChangeRequest·AccountDeletion·`AccountDeleted` 이벤트·OidcProvider·`AccountStatus.DEACTIVATED`). `business-logic-model.md` **§5~9**(PasswordResetService request/confirm·SocialLoginService start/callback OIDC·AccountManagementService 비번/이메일 변경·AccountDeletionService requestDeletion+purgeJob·인증 입력 견고화). 라이브러리/테이블 스키마/이벤트 버스 구현은 **NFR/Infra Design·Code로 이월**. **다음(별도 승인): NFR Requirements/Design → Infra Design → Code Generation(공개 인증 SSOT DTO `extra=ignore` 재생성·OIDC/재설정 라이브러리·DB 마이그레이션 포함) → Build&Test.** 리뷰 게이트 대기.
- [x] **NFR Requirements/Design 개정 — U3 Accounts 프로덕션화 (2026-06-24, `feature/u3-accounts-production`, "continue")**: 코드 없이 기술·패턴 결정만. `tech-stack-decisions.md` **TD-U3-7~10**(이메일=**Resend**[SES 대체]·소셜 OIDC=**httpx+python-jose JWKS**[Authlib 미채택]·신규 RDS 테이블[`password_reset_token`/`email_change_request`/`social_identity`·`account_deletion`·`status.DEACTIVATED`]+state/nonce=Redis 단명·삭제 캐스케이드=**EventBridge `AccountDeleted`**+유예 잡). `nfr-design-patterns.md` **§4~7**(재설정: 해시저장·단일사용 CAS·열거방지·레이트리밋·Fail-Closed / OIDC: state·nonce Redis 단명·JWKS 캐시·`email_verified` 게이트 / 삭제: 2상 이벤트 캐스케이드·멱등·DLQ·비차단 / 공개 인증: `extra=ignore`·422 명확 표면화). **다음(별도 승인): Infra Design → Code Generation → Build&Test.** 리뷰 게이트 대기.
- [x] **Code Generation (시작) — FR-29 인증 입력 견고화 슬라이스 (2026-06-24, `feature/u3-accounts-production`, "start the construction stage")**: 실제 로그인 422 장애 해소 최소 슬라이스 **구현·검증**(코드 첫 착수). **백엔드**: SSOT `shared/dtos/accounts.schema.json`의 `LoginRequest`·`SignupRequest`에서 `additionalProperties:false` 제거 → 재생성(`docsuri_shared` `extra=ignore`; 응답 DTO `SignupResult`/`SessionInfo`는 `extra='forbid'` 유지) — **Python 드리프트 가드 `ok`**. **프런트**: `frontend/lib/api/errors.ts` `normalizeHttpError`에 422 분기 추가 → 불투명 'unknown'('문제가 발생했습니다') 대신 '입력 형식이 올바르지 않습니다…새로고침' 명확 표면화. **TS 타입 무변**(gen-types가 `additionalProperties:false` 고정 옵션·`accounts.ts`는 큐레이티드 — 드리프트 없음). **테스트**: `tests/accounts/test_auth_input_tolerance.py` **3 passed**(입력 DTO extra 무시·응답 DTO forbid 유지). 라이브 즉시 해소는 별도로 develop 프런트 재배포 필요. **남은 Construction(미착수)**: FR-26 재설정·FR-27 OIDC·FR-28 라이프사이클(신규 테이블·`AccountDeleted` 이벤트·purge 잡)·Infra Design·DB 마이그레이션·FE 플로우·테스트. **미커밋.**
- [x] **Code Generation — FR-26 비밀번호 재설정 백엔드 슬라이스 (2026-06-24, `feature/u3-accounts-production`, "continue to the next slice")**: 백엔드 풀 구현·검증. **DTO**: SSOT `PasswordResetRequest`/`PasswordResetConfirm`(extra=ignore)+재생성·`dtos.py`/`schemas.py`/`accounts.ts` 재내보내기. **저장소**: `password_reset_tokens`(token_hash PK·SHA-256 해시저장·단일사용 선삭제). **서비스** `PasswordResetService`: request(열거방지 no-op·활성계정만 30분 토큰·Resend)·confirm(만료/단일사용/BR-A1 재검증/Argon2 재해싱/**전 세션 무효화**). **이메일** 3프로바이더 `send_password_reset_email`+렌더. **세션** `invalidate_all_for_user`(`user_sessions` Redis 셋 인덱스). **컨트롤러** `POST /auth/password-reset/request|confirm`(요청=일반응답·확정=400/503/500 매핑). **검증: ruff clean · accounts 39 passed(reset 6 신규·회귀 0) · Python 드리프트 ok.** **미구현(이월)**: FE 재설정 요청/확정 페이지·DB 마이그레이션 SQL·앱셸 와이어링. **미커밋.**
- [x] **Code Generation — FR-27 소셜 로그인(OIDC) 조정 코어 (2026-06-24, `feature/u3-accounts-production`, "move on to FR-27")**: 보안 핵심(H1) 신원 조정 로직만 구현 — OIDC 트랜스포트는 이월(테스트 가능성 위해 분리). `models` `OidcProvider`·`SocialLinkConfirmationRequired`(DomainException). `credential` `social_identities` 테이블((provider,subject) PK·status LINKED|PENDING_CONFIRMATION)+`SOCIAL_NO_PASSWORD_HASH` 센티넬+`has_usable_password()`+repo(get/create_social_identity·create_social_account ACTIVE 무비번). `SocialLoginService.reconcile`(검증 클레임→account_id: 미검증 거부·`(provider,subject)` 기존연결 멱등·소셜-only 동일이메일 자동연결·**기존 *비밀번호* 계정=H1 자동병합 금지→PENDING_CONFIRMATION 기록+`SocialLinkConfirmationRequired`**·신규=ACTIVE+LINKED). **검증: ruff clean · accounts 44 passed(social 5 신규·회귀 0).** **이월(다음)**: Google OIDC HTTP/JWKS verifier(httpx+python-jose)·Redis state/nonce·컨트롤러 start/callback/`/auth/social/link`·세션 발급 와이어링·FE·DB 마이그레이션. **미커밋.**
- [x] **Code Generation — FR-28 계정 라이프사이클 코어 (2026-06-24, `feature/u3-accounts-production`, "continue the construction phase")**: 백엔드 코어 풀 구현·검증 — 실 EventBridge 트랜스포트만 이월(FR-27 OIDC 분리와 동일 패턴). **models** `AccountStatus.DEACTIVATED`. **credential** 신규 테이블 `email_change_requests`(token_hash PK·해시저장·계정당 1활성)·`account_deletions`(account_id PK·purge_after·state DEACTIVATED|PURGED) + CRUD(email-change·deletion·`get_due_deletions`·`delete_account_permanently` 캐스케이드[accounts+verification/reset 토큰+social_identities+email_change]·`mark_deletion_purged`·`delete_account_deletion`). **AccountManagementService**(BR-A10): `change_password`(현 비번 재인증→BR-A1→Argon2 재해싱→**전 세션 무효화**)·`request_email_change`(형식·중복검사[사용중=**열거방지 무처리** SEC-BR-2]·30분 단일사용 토큰·새주소 확인링크+**현주소 변경알림 M2**·지연반영)·`confirm_email_change`(만료/단일사용/레이스 재확인→로그인 식별자 반영). **AccountDeletionService**(BR-A11): `request_deletion`(DEACTIVATED+전세션 무효화+유예레코드·**`AccountDeleted` 미발행** H2)·`reactivate`(유예중 복구 M1)·`purge_job`(유예 경과분 일괄: **`AccountDeleted` 발행**[accountId 멱등키·eventId·`AccountDeletedPublisher` 포트+기본 Logging 발행자]→영구삭제→PURGED·멱등). **email** `_send` 프리미티브(Mock/SES/Resend) + 이메일변경 확인/알림 메일. **auth** 보안픽스: 로그인 시 **DEACTIVATED 차단**(기존 PENDING/LOCKED만 검사 → 소프트삭제 계정이 세션 발급되던 갭 해소). **controller** `/auth/change-password`·`/auth/email-change/request|confirm`·`/auth/account/delete`(세션 필수·쿠키 클리어·503/400/500 매핑). **검증: ruff clean(accounts 레인) · accounts 58 passed(account_management 8·account_deletion 6 신규·회귀 0) · 컨트롤러 임포트/라우트 등록 OK · app-shell mount 4 passed.** **이월(다음)**: 실 EventBridge `AccountDeleted` 발행·구독자 완료검증/DLQ·재활성화 UX(로그인-감지→복구)·purge_job 크론/워커 와이어링·FE 플로우·DB 마이그레이션 SQL. **미커밋.**
- [x] **사용자 스토리 개정 — 연구 에이전트 에픽 추가 (2026-06-24, `feature/research-agent`·PR #170)**: PART 1 평가(`research-agent-user-stories-assessment.md`) + 스토리 생성 계획(`research-agent-story-generation-plan.md`, PQ1~6 **전부 권장안 A 승인**) → PART 2: `stories.md`에 **에픽 9 — 연구 에이전트 / 문헌탐색·근거형성**(US-RA1 전용 진입+모드선택+입력·US-RA2 문서 첨부·US-RA3 다논문 근거 정리[모드A]·US-RA4 근거화·기권·US-RA5 결과·세션 영속+전용 메뉴 재열람·US-RA6 온디맨드 진행상태·비차단 저하·US-RA7 비용게이트+근거화 운영[OP]·US-RA8 novelty 비교[모드B·**다음 사이클** Q4=A]) 8 스토리 추가 → 총 48 스토리/10 에픽. `personas.md` P1/OP 보강. FR-22~25·NFR-P5·NFR-C1 Agent·QT-8 전수 커버, §12 카브아웃·C-2 경계·제외 범위(생성 산문·재현성 판정·모드B v1빌드) 인수 기준 명시. **다음(별도 승인): Units Generation(신규 유닛 등재·번호 배정) → Construction.**
- [x] **Units Generation 개정 — 연구 에이전트 정식 등재 (2026-06-24, `feature/research-agent`·PR #170)**: 분해 계획(`research-agent-unit-of-work-plan.md`, UQ1~5 **전부 권장안 A 승인**; **UQ2=A → 유닛 번호 U11**). 원본(U1~U6)·U9 분해 계획 모두 참고. **U10=마이페이지(타 팀원 구현 중·커밋 전)를 가정**하고 번호 점유로 처리(AI-DLC 관례: 번호=정식 생성 시점 부여) → 신규 유닛 **U11 Research Agent**(`backend/modules/research_agent/`). `unit-of-work.md`(U11 정의·U10 자리 주석·U11 주석[v1=모드A·모드B 차기·추출 경계·HOW 이월]·배포 단위 ① API+긴 분석 비동기 잡·코드 조직·빌드 순서 확장)·`unit-of-work-dependency.md`(U11 행/열 추가, U11→U2/U3/U6/U7 의존[+모드B 차기 U8·U9 비차단], `shared/ports` 의존성 역전으로 U11↔U6 순환 없음, 비순환 DAG 검증, 온디맨드 다논문 ASCII 흐름)·`unit-of-work-story-map.md`(US-RA1~6·RA8 Owner=U11·US-RA7 Owner=U6 기여=U11, 48 스토리 전수 매핑·미할당 0) 갱신. **10 유닛(U1~U9+U11)·4 배포 단위(U11=API 모듈+긴 분석 비동기 잡 옵션).** v1=모드 A, 모드 B(novelty)는 다음 사이클. **다음(별도 승인): Construction(U11 Functional/NFR/Infra Design 라운드 — 근거표 컬럼·외부 API·LLM 모델·멀티턴·UI 결정).**
- [x] **Construction — U11 Functional Design 완료·승인 (2026-06-24, 브랜치 `feature/research-agent-construction`·PR #183)**: Part 1 질문게이트 Q1~Q17 확정 + Part 2 산출물 4종(`construction/u11-research-agent/functional-design/` domain-entities·business-logic-model·business-rules[INV-U11-1~7·BR-RA-1~18·QT-8]·frontend-components[Q15=B 풀버티컬]). **핵심 결정**: Q1=파이프라인 A(U7 배관 재사용+U11 전용 추출 노드) **+ ★전문 통합 인덱스·eager doc-model 전환(아키텍처 게이트 `plans/docmodel-fulltext-index-pivot-plan.md`)★** · Q2=A+ · Q5=A(논문 비교형+쟁점) · **Q7=A(근거화 U6 단일 권위 통일 — U7 AnchorVerdict도 U6 공유 계약 이관·확정)** · Q15=B. 검색 locator·granularity(GQ1)·랭킹(GQ2)·LLM/스토리지는 권장/옵션·NFR 이월. **게이트(전문 인덱스·eager doc-model·근거화 통일·DF-6 각주/메타)는 #136/#120·D6 되돌림+배포 U7 변경이라 U1/U2/U7/infra 조율·별도 승인 필요.**
- [x] **Construction — U11 NFR Requirements 완료·승인 (2026-06-24, PR #183)**: 질문지(U7/U2/U3/U8 선례 반영·Q1~Q16) **전부 A** → 산출물 `u11-research-agent/nfr-requirements/` 2종(nfr-requirements.md·tech-stack-decisions.md TD-RA-1~15: Sonnet 추출·Bedrock 스트리밍·RDS 세션·S3 첨부·Redis+영구 2단·SQS 비동기잡·U2 재사용·U6 근거화 통일·real-first·shared DTO 승격). granularity(GQ1)·랭킹(GQ2)·모드B API=[열림].
- [x] **Construction — U11 NFR Design 완료·승인 (2026-06-24, PR #183)**: 질문지(U7/U2/U3/U8 패턴 종합·A~F·Q1~Q14) **전부 A**(+Q1 정밀화: 의존성별 격리=U11 직접 호출 실패도메인[검색U2·doc-model읽기S3·Bedrock·U6·RDS/Redis] 단위; OpenSearch는 U2 재사용 시 U2 내부 서킷). 산출물 `u11-research-agent/nfr-design/` 2종(nfr-design-patterns[의존성별 격리·저하 4계층·재시도 분리·fan-out 부분실패·캐시우선·스트리밍↔근거화·bounded 병렬·3밴드·방어심층·폴트인젝션]·logical-components[토폴로지·SQS 잡큐·포트 경계]). 수치·GQ1·GQ2=Infra/실험 이연. **다음: Infrastructure Design(진행 중 — U7/U8/U3/시스템 선례 종합 질문지).** develop 병합(U10 마이페이지·U3 소셜로그인 등) 반영(커밋 0de39ca).
- [x] **Workflow Planning — Cohere Embed v4.0 마이그레이션 (2026-06-23)**: `execution-plan.md` 업데이트 완료. 리버스 엔지니어링, 애플리케이션 설계, 유닛 생성, 기능 설계, NFR 요구사항 SKIP. **NFR 설계, 인프라 설계, 코드 생성, 빌드 & 테스트 EXECUTE 확정**.
- [x] **사용자 스토리 개정 — U8 에픽 추가 (2026-06-19)**: `stories.md`에 **에픽 7 — 인용 그래프 / 각주 트리**(US-CG1 상세보기 각주 트리·US-CG2 깊이/노드 메타·US-CG3 unresolved 분리·US-CG4 라이브러리 저장·US-CG5 실패/쿼터 저하·US-CG6 운영 관측성) 6 스토리 추가 → 총 33 스토리/8 에픽. P1(US-CG1..CG5)·OP(US-CG6) 매핑, FR-15..16·NFR-P3·QT-6 커버.
- [x] **Units Generation 개정 — U8 정식 등재 (2026-06-19)**: `unit-of-work.md`(U8 Citation Graph 유닛 정의·배포 단위 ① API 모듈·코드트리 `backend/modules/citation_graph/`)·`unit-of-work-dependency.md`(U8 행/열 추가, U8→U3/U6 로그인·게이트웨이, U8→U4 저장 계약, U7→U8 출처 연동, 코드 DAG 비순환 검증, 각주 트리 ASCII 흐름)·`unit-of-work-story-map.md`(US-CG1..CG5 Owner=U8·US-CG6 Owner=U6 기여=U8, 전수 33 스토리 검증) 갱신. **8 유닛·4 배포 단위(U8=API 모듈).** **후속: U8 Construction Functional Design 질문 게이트 진입 완료, 답변 대기.**

### 🟢 CONSTRUCTION 단계 (유닛별 루프)

**U1 Ingestion** (프로덕션 직행 1번; 데모 트랙 폐기):
- [x] Functional Design — **완료·승인·프로덕션 재스코핑 (2026-06-16)**. `construction/u1-ingestion/functional-design/`(domain-entities·business-logic-model·business-rules). 프로덕션: **Q1=D 풀 슬라이스(5cat×5yr 수십만)·Q2=C OA 전문 청킹·Q12=B 이벤트 경로 활성·Q13=B 철회 tombstone**. INV-1 커밋순서·논문 단위 원자성·PBT-08 P1~P6. **FD 완전 추상(기술 무관)**. 적대적 검증 3패스.
- [x] **Functional Design 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-functional-design-plan.md` 생성(추가 질문 없음; U1 Corpus Q1~Q12=A 상속). 기존 U1 FD 3문서에 **2026-06-26 Corpus 우선 적용 섹션** 추가: `domain-entities.md`(SourceName/SourceTier, canonical PaperId, SourceWatermark, FullTextCandidate, eager DocModel, DocModelChunk, CorpusIndexGeneration, DLQ), `business-logic-model.md`(source별 incremental loop → FullText/GROBID transient PDF → source-priority dedup → eager DocModel → Block chunk → embedding → index generation/S3 → alias cutover), `business-rules.md`(BR-C1~C15, QT-9/PBT P-C1~P-C7). 기존 arXiv-only/lazy DocModel/단일 watermark/구식 chunk 규칙과 충돌 시 Corpus 섹션 우선. **앱 코드 미생성.** 승인 시 다음: U1 NFR Requirements.
- [x] **NFR Requirements 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-nfr-requirements-plan.md` 생성(추가 질문 없음; 기존 결정 상속). `nfr-requirements.md`에 U1 Corpus 우선 적용 NFR 추가: phase-1 최근 AI/ML 1년, source fan-out, internal GROBID 처리량, DocModel generation/alias, stage별 retry/DLQ, source별 watermark, raw PDF transient, ObservabilityHub metric/log, QT-9/PBT. `tech-stack-decisions.md`에 TD-C1~C8 추가: Python worker 유지, source adapters, internal containerized GROBID, HTML+TEI deterministic parser, Cohere Embed v4/specVersion v2, OpenSearch generation/alias, EventBridge+SQS/DLQ, private S3, $1600 account budget + U1 per-run hard stop. **앱 코드 미생성.** 승인 시 다음: U1 NFR Design.
- [x] **NFR Design 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-nfr-design-plan.md` 생성(추가 질문 없음; NFR Requirements 결정 상속). `logical-components.md`에 Corpus 우선 적용 컴포넌트 추가: EventBridge source scheduler, Corpus work queue/DLQ, Ingestion Worker, internal GROBID runtime, DocModel parser, Control Plane DB, private Corpus S3, Bedrock Cohere Embed v4, OpenSearch generation, ObservabilityHub. `nfr-design-patterns.md`에 stage-aware retry/DLQ, source-specific circuit breaker, cost hard-stop, generation cutover/rollback, parser hardening, QT-9 verification pattern 추가. **앱 코드 미생성.** 승인 시 다음: U1 Infrastructure Design.
- [x] **Infrastructure Design 개정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-infrastructure-design-plan.md` 생성(추가 질문 없음; 기존 AWS 인프라 상속). `infrastructure-design.md`에 Corpus AWS 매핑 추가: existing EventBridge/SQS/DLQ/ECS Fargate worker/S3/RDS/OpenSearch/Bedrock/Budget 재사용, internal GROBID sidecar, source별 scheduler, Corpus S3 prefixes, control-plane tables, IAM/network/alarms. `deployment-architecture.md`에 rollout/rollback 추가: migrations → disabled deploy → candidate generation → source별 enable → budgeted backfill → QT-9/U2/U7 smoke → alias cutover. **앱 코드 미생성.** 승인 시 다음: U1 Code Generation.
- [x] **PR #225 리뷰 보정 — DocModel 완성형 계약을 Infrastructure Design 단계까지 반영 (2026-06-26)**. 사용자 리뷰에 따라 DocModel을 `fullText` 전문 텍스트 투영본 + `sections[].blocks[]` 멀티모달 구조(paragraph/table/formula/figure/list/code)로 보정하는 결정을 Functional/NFR/NFR Design/Infrastructure Design 문서에 반영. 이미지 바이트/base64/서명 URL은 DocModel에 넣지 않고 `figure.assetRef.assetId`로 private `assets/` 저장소를 참조한다. **코드·스키마·generated DTO·프론트 타입·테스트 변경은 Infrastructure Design 단계 범위 밖이므로 PR에서 제거했고, 다음 U1 Code Generation에서 구현한다.**
- [x] **Code Generation Part 1 계획 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-code-generation-plan.md` 생성. 범위: DocModel `fullText` 계약 보정, parser fullText projection, eager DocModel build 경로, DocModel block-aware chunk/index metadata, multi-source adapter/GROBID boundary, source별 watermark/canonical dedup, retry/DLQ payload, OpenSearch generation/alias, U7/frontend 소비자 정합, targeted tests. **앱 코드 미생성.** 승인 시 Code Generation Part 2 실행.
- [x] **Code Generation Part 2 실행 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 계획서 `construction/plans/u1-corpus-code-generation-plan.md` 16단계 전부 완료. 구현: DocModel required `fullText` + generated DTO/frontend type, parser fullText projection, eager DocModel build before index, DocModel block-aware chunk/index metadata, corpus source adapter/GROBID boundary, canonical dedup state/Postgres migration, source-aware retry/DLQ payload, OpenSearch generation validation/alias cutover, runtime/CDK GROBID sidecar wiring, U7/frontend consumer 정합. 코드 요약 `construction/u1-ingestion/code/u1-corpus-code-summary.md`. 검증: shared schema drift check, shared 66 passed, ingestion 129 passed/1 skipped + ruff clean, ops 42 passed, discovery 53 passed/3 skipped, summarization 116 passed/3 skipped, frontend targeted vitest 19 passed + tsc, git diff --check 통과.
- [x] **Code Generation 리뷰 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**. 리뷰 지적 4건 반영: `CorpusSourceAdapterSet`을 refresh/pipeline에 주입하고 provider-backed Semantic Scholar/OpenAlex `sourceRecord` job 경로를 추가, arXiv HTML 미가용 시 PDF/full-text fallback DocModel 생성, `IndexRecord.blockRefs[]` 구조화 저장 및 BM25 noise 제거, GROBID 429/일시적 4xx retriable 분류. 회귀 테스트: source refresh/ingest smoke, text fallback DocModel, GROBID 429/400, `blockRefs[]` 구조화 assertion.
- [x] **Code Generation 추가 리뷰 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 팀원 리뷰 후속 반영: lazy `BUILD_DOC_MODEL`도 HTML 미가용 시 eager와 동일하게 PDF/full-text fallback DocModel을 생성, canonical dedup state에 arXiv도 기록, source priority(arXiv > Semantic Scholar > OpenAlex)를 적용해 상위 source winner가 있으면 외부 PDF/GROBID fetch 전에 duplicate skip, 상위 source가 나중에 도착하면 하위 source chunk를 tombstone 처리. Phase boundary 명시: Semantic Scholar/OpenAlex 실 HTTP provider, legacy reindex의 DocModel chunk 전환, vision-model asset rollout은 Operations/follow-up. 검증: ingestion pytest 132 passed/1 skipped, ingestion ruff clean.
- [x] **Code Generation 재검토 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. `cf923a8` 재검토 피드백 반영: withdrawal-detected paper는 tombstone 후 canonical winner 기록을 건너뛰어 정상 외부 복본을 삭제하지 않도록 했고, canonical loser 제거 시 index tombstone과 함께 DocModel cache invalidation 및 asset cleanup을 대칭 수행한다. 회귀 테스트: withdrawn arXiv가 existing external canonical winner를 보존하는지, arXiv가 lower-priority winner를 교체할 때 loser DocModel/assets cleanup이 호출되는지 검증.
- [x] **Code Generation blockRef 재검토 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. `IndexRecord.blockRefs[]`를 문자열 배열에서 `{paperId, version, sectionId, blockId, blockType}` 구조체 배열로 정정하고, DocModel chunker가 별도 abstract chunk를 만들지 않도록 해 모든 DocModel-derived index record가 실제 DocModel block을 참조한다. OpenSearch mapping helper도 structured nested field로 갱신. 당시 DOI-only external vs arXiv canonical alias/sourceProvenance 확장은 follow-up으로 분리했으며, 아래 SourceProvenance/alias follow-up 종결 항목에서 반영 완료.
- [x] **Code Generation abstract/mapping 재검토 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. `0ffeee0` 재검토 피드백 반영: DocModel parser가 abstract를 `s0.p1` 블록으로 모델링해 semantic embedding을 복원하고, `chunk_doc_model`의 unused abstract parameter를 제거했다. `blockRefs` OpenSearch mapping은 검색하지 않는 provenance 성격에 맞춰 non-indexed object로 바꿨고, `provision_v2_index.py`는 `papers_index_body()`를 import해 mapping SSOT를 재사용한다. 당시 SourceProvenance, DOI/arXiv alias, 철회 winner canonical state cleanup은 별도 follow-up으로 분리했으며, 아래 후속 항목들에서 종결했다.
- [x] **Code Generation fullText/canonical cleanup 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 요청에 따라 🅔와 철회 winner canonical cleanup까지 반영: text-bearing block이 없는 DocModel은 `fullText`를 첫 실제 block ref에 연결해 fallback chunk를 생성하고, successful tombstone은 해당 `paperId`가 winner인 canonical dedup rows를 삭제한다. In-memory/Postgres control-plane store 모두 `delete_canonical_dedup_state_for_paper()` 구현.
- [x] **Code Generation SourceProvenance/alias follow-up 종결 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 남은 SourceProvenance와 DOI/arXiv alias follow-up 반영: `IndexRecord`에 optional internal `doi`, `sourceArxivId`, `sourceProvenance`를 추가하고 OpenSearch mapping은 alias keyword + provenance non-indexed object로 갱신했다. `ParsedPaper`가 sourceName/sourceId/sourceTier/sourceUrl/DOI/arXiv alias를 보존하고 assembler가 record에 기록한다. canonical dedup은 DOI, arXiv, title/author/year alias rows를 같은 winner로 묶고, lower-priority external winner를 arXiv가 대체할 때 기존 DOI alias까지 새 winner로 이동한다. DOI-only external과 arXiv metadata는 title alias로 교차 매칭된다.
- [x] **Code Generation 코퍼스 빌드 전 리뷰 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 코퍼스 채우기 전 남은 항목 반영: DocModel 계약을 FROZEN으로 전환하고 footnote/references/page 제외 및 PDF/GROBID 단일 paragraph degrade를 명시했다. `lexicalTerms`는 본문 청크 전용 analyzed 필드로 줄이고, `title`/`abstract` 표시 필드를 lexical 검색에도 재사용해 추후 boost 튜닝을 재색인 없이 query 변경으로 적용 가능하게 했다. Semantic Scholar/OpenAlex 실 HTTP provider를 추가하고 GROBID가 있을 때 production runtime에 배선했다. `migrate.py backfill`은 legacy `chunk()` 직접 경로를 제거하고 OAI metadata를 기존 pipeline/DocModel indexing 경로로 넣는다. local runtime에도 in-memory DocModelBuilder를 주입해 local/prod indexing path를 맞췄다. HTML 본문 abstract가 `meta.abstract`와 중복될 때 첫 abstract section을 제거해 semantic embedding 이중계상을 막는다. `DocModelBuilder`는 cached provenance `parserVersion`/`schemaVersion`이 현재 builder와 일치할 때만 cache hit로 인정한다. `trigger-full-rebuild` preflight는 production corpus build 전에 multimodal assets ON, external source용 GROBID URL, `DOCSURI_BEDROCK_MODEL_ID_V2` unset, worker rollout 완료 및 redeploy freeze 확인을 강제한다.
- [x] **Code Generation 문서 정합 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 추가 점검에서 남은 문서-코드 불일치를 정리했다. `construction/shared/vector-spec.md`를 실제 shared 계약(`specVersion=v2`, Cohere Embed v4, `assert_same_space()` 기반 same-space gate, per-record `modelVer` 없음)에 맞췄고, U1 `business-rules.md`의 오래된 제목+초록 단일 벡터/`lexicalTerms` 계약을 DocModel 기반 초록+본문 다중 청크 및 본문 전용 `lexicalTerms` 계약으로 갱신했다.
- [x] **Code Generation full rebuild 멀티소스 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 추가 실행 경로 점검에서 `trigger_full_rebuild()`가 arXiv seed만 큐잉하고 configured Semantic Scholar/OpenAlex source record를 누락하는 갭을 수정했다. full rebuild는 enabled external source별 watermark를 corpus slice start로 reset하고 `SEED_REBUILD` source-record job을 큐잉한다. 검증: ingestion focused orchestration/cache/lexical/preflight tests 28 passed, ingestion full pytest 147 passed/1 skipped, ingestion ruff clean, shared vector spec 9 passed, discovery OpenSearch adapter 4 passed, shared generate --check passed, git diff --check passed.
- [x] **Code Generation phase-1 corpus slice 보정 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. 사용자 결정에 따라 phase-1 Corpus 범위를 최근 AI/ML 1년으로 확정했다. `CORPUS_START=2025-01-01`, `CORPUS_END=2026-01-01`로 좁히고, `trigger_full_rebuild()`는 arXiv와 Semantic Scholar/OpenAlex seed rebuild 모두 같은 start/end window를 적용한다. 외부 provider가 범위 밖 record를 반환해도 orchestrator가 큐잉 전에 skip한다. 관련 요구사항/차터/Functional/NFR/Infrastructure 문서의 current contract를 1년 슬라이스로 정리했다. 검증: ingestion targeted orchestration/corpus source tests 34 passed, ingestion full pytest 148 passed/1 skipped, ingestion ruff clean, corpus scope drift search clean, git diff --check passed.
- [x] **Code Generation DocModel stale cache 완전 종료 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. `DocModelBuilder`뿐 아니라 U7 `S3DocModelReader` 우회 read path까지 `parserVersion`/`schemaVersion` stale object를 cache miss로 처리하도록 수정했다. shared `docmodel_contract` 상수를 U1 builder와 U7 reader가 같이 사용해 version drift를 줄이고, reader는 pydantic schema validation 전에 provenance를 확인해 old-shape S3 object도 rebuild/miss 경로로 보낸다. 검증: ingestion docmodel builder 8 passed, summarization docmodel endpoint/build trigger 20 passed, summarization full pytest 118 passed/3 skipped, ingestion full pytest 148 passed/1 skipped, shared pytest 68 passed, targeted ruff clean, shared generate --check passed, git diff --check passed. Summarization 전체 `ruff check src tests`는 기존 unrelated test lint baseline으로 실패.
- [x] **Code Generation lexicalTerms write split 완전 종료 — 재인셉션 페이즈 1 / U1 Corpus (2026-06-27)**. `IndexRecord.lexicalTerms`를 본문 청크 전용으로 강제했다. legacy full-text chunk와 DocModel chunk 모두 abstract section record는 `lexicalTerms=""`로 저장하고, 검색용 초록은 별도 analyzed `abstract` 필드에만 남긴다. U2 BM25 reader는 기존대로 `title`, `abstract`, `lexicalTerms` multi-match를 사용해 추후 boost 튜닝을 재색인 없이 query 변경으로 적용할 수 있다. 검증: ingestion full pytest 149 passed/1 skipped, ingestion ruff clean, shared pytest 68 passed, shared vector spec 9 passed, shared generate --check passed, discovery OpenSearch adapter 4 passed, targeted discovery/shared ruff clean, git diff --check passed.
- [x] **Build and Test — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26, 리뷰 게이트)**. 산출물 `construction/u1-ingestion/build-and-test/` 갱신: build-instructions, unit-test-instructions, integration-test-instructions, performance-test-instructions, build-and-test-summary. 검증 기준은 Code Generation Part 2 및 리뷰 보정에서 실제 실행한 결과를 반영: shared schema drift check 통과, shared 66 passed, ingestion 129 passed/1 skipped + ruff clean, ops 42 passed, discovery 53 passed/3 skipped, summarization 116 passed/3 skipped, frontend targeted vitest 19 passed + tsc, git diff --check 통과. Dedicated load harness는 추가하지 않고 bounded backfill + worker telemetry + OpenSearch generation validation으로 성능 검증.
- [x] NFR Requirements — **완료·승인 (2026-06-16)**. `construction/u1-ingestion/nfr-requirements/`(nfr-requirements·tech-stack-decisions). 스택: Python·**OpenSearch[전역]**·**cross-lingual 임베딩(Cohere Embed Multilingual v3, 1024·코사인)[전역]**·EventBridge·SQS·S3·Hypothesis·SEC-10. **NFR-C1=$1600/월(시스템 전역, 기존 $300 대체)**. **엄격 OA 라이선스 검증(BR-1)**. VectorSpec PIN·AS-4 수치 확정.
- [x] NFR Design — **완료·승인 (2026-06-16)**. `construction/u1-ingestion/nfr-design/`(nfr-design-patterns·logical-components). 버전 단조 tombstone(`current_version` compare-and-set)·indexStats 내부경계+캐시TTL·RES-1 의존성맵·verify-all-then-commit·CI=GHA(**설계만; GHA 워크플로우 미구현 — §검증 재기준선**)·RES-12 폴트인젝션. 적대적 검증 + 팀 피드백 2건(tombstone 순서·indexStats 경계) 반영. _ID: RES-12(복원력 테스트)._
- [x] Code Generation — **완료·승인 (2026-06-16)**. `construction/plans/u1-ingestion-code-generation-plan.md` 17단계 전부 완료. `ingestion/` 코드·테스트·배포 스캐폴드·코드 요약 생성 및 검증(`pytest` **23 passed**, `ruff` pass, `uv.lock` 생성) 완료. ⚠️ **PBT-08 P1(디덥 멱등) 속성 테스트 누락**(예시 테스트만 존재); Dockerfile 베이스 태그 핀(sha256 미적용·SEC-10).

**U2 Discovery** (Track 3 @kyjness, mock 선행 → U5):
- [x] Functional Design — **완료·승인 (2026-06-16)**. `construction/u2-discovery/functional-design/`(domain-entities·business-logic-model·business-rules). §4 답변 전부 A: **Q2=A RRF·PaperId 디덥**·**Q3=A baseline 랭킹·relevance 비-raw**·**Q4=A 기권 vs 빈결과 구분(빈 성공 금지)**·Q5=A 검색 인증 필수·Q6=A 2단계 저하·Q7=A NFC·다국어·Q10=A N=20·Q11=A 비차단 이벤트. **INV-1 단일 근거화 게이트(U2 enforce 미호출, U6 단일 권위)**·INV-2 SEC-9 비노출·INV-3 fail-closed·PBT-02/03/07/09. cross-lingual(TD-3 한국어 질의)·capability 어댑터 seam(VectorStoreAdapter·LexicalIndexAdapter·LlmGatewayAdapter) mock-first.
- [x] NFR Requirements — **완료·승인 (2026-06-16)**. `construction/u2-discovery/nfr-requirements/`(nfr-requirements·tech-stack-decisions). **[전역 계승]**: Python·Cohere `search_query`·OpenSearch·Hypothesis·NFR-C1 $1600. **U2 고유**: opensearch-py+**앱 레벨 RRF**+PaperId 디덥·Bedrock 질의 임베딩(검색당 1회)·**임베딩 캐시(TTL)**. **⏳ FastAPI = app-shell 소유자(@ELSAPHABA) 합의 전제(잠정, backend-shared)**. NFR-P1 예산 분해(U2 단계+U6 근거화 별도)·임베딩장애→lexical 폴백/인덱스장애→fail-closed·QT-2 한국어 평가셋.
- [x] NFR Design — **완료·승인 (2026-06-16)**. `construction/u2-discovery/nfr-design/`(nfr-design-patterns·logical-components). 동기 **fail-fast+폴백**(재시도 최소)·**의존성별 서킷**(임베딩→lexical/인덱스→fail-closed)·비용 degradeMode≠장애 서킷·임베딩 **read-through 캐시(TTL)**·**k-NN∥BM25 병렬 RRF**·stateless 수평확장·SEC 계층 분리 방어심층·CI=GHA(**설계만; 워크플로우 미구현**)·RES-12 폴트인젝션.
- [x] Code Generation (mock-first) — **완료 (2026-06-16)**. `backend/modules/discovery/`(pyproject·테스트). **31 passed(api extra)/29+1 skip · ruff clean.** 도메인 6컴포넌트(validator·expander·retriever[RRF·PaperId 디덥]·ranker[N=20]·grounding_adapter·assembler) + orchestrator(plan_and_retrieve/finalize 분리, **INV-1 enforce 미호출**) + `api/gateway_seam`(단일 enforce invocation=게이트웨이 대역) + mock 어댑터/스텁(KO↔EN cross-lingual+QT-2 픽스처) + thin FastAPI 라우터. PBT-02/03/07/09·RES-12 폴트인젝션 테스트. (마운트·근거화는 후속 PR에서 해소 — 아래 real 어댑터 항목 참조.)
- [x] Code Generation (real 어댑터) — **완료·로컬 검증 (2026-06-17, 브랜치 `feature/u2-v2`, 크리티컬 패스 ⑥, 리뷰 게이트)**. `backend/modules/discovery/adapters/`: **BedrockCohereQueryEmbedder**(reader=search_query·dim 검증·실패 시 EmbeddingUnavailable→lexical 폴백), **OpenSearchVectorStoreAdapter**(k-NN cosine)·**OpenSearchLexicalIndexAdapter**(BM25) — U1 writer 인덱스(`docsuri-corpus-v1`) 동일공간 read, hit→`IndexRecord` 역직렬화(SSOT), 실패 시 **IndexUnavailable fail-closed**(INV-3), **EventBridgeEventPublisher**(논블로킹 SearchExecuted→U4). `real_wiring.build_real_orchestrator`(MR-4 계약 불변 스왑)·`scripts/seed_local_opensearch`·pyproject `real` extra(opensearch-py/boto3 lazy). **검증: `pytest` 43 passed(신규 단위 11)+1 skip·ruff clean; docker 라이브 OpenSearch 통합 3 passed(k-NN·BM25·하이브리드 디덥); app-shell 엔드투엔드 200·실 카드 반환(Bedrock 부재 시 graceful degrade).** **app-shell 마운트 토글**(`backend/wiring.py::_mount_discovery`): env(`DOCSURI_OPENSEARCH_ENDPOINT`+`DOCSURI_BEDROCK_MODEL_ID`) 있으면 real, 없으면 mock — 실 근거화 hook은 양 모드 공통(INV-1). **⏳ 의존성 플래그**: 프로덕션 실행은 공유 인프라(OpenSearch 클러스터·Bedrock 접근·이벤트 버스 = U1 보류 인프라 + 시스템 횡단) 필요(env로 분리). **⚠️ 조율존(`backend/wiring.py`) 변경 = @ELSAPHABA 사인오프 필요.**
**U3 Accounts** (Track 2):
- [x] Functional Design — **완료·승인 (2026-06-16)**. `construction/u3-accounts/functional-design/`(domain-entities·business-logic-model·business-rules). 비밀번호 최소 10자 복잡도+로컬 블랙리스트(Q1=B), Argon2id KDF(Q2=A), Sliding 2h+절대 30d 세션(Q3=B), 지수 백오프+10회 CAPTCHA(Q4=B), 이메일 가입 링크 인증 PENDING/ACTIVE(Q5=B), Stateless 인가 결정(Q6=A), 시딩 관리자+TOTP MFA(Q7=B) 확정.
- [x] NFR Requirements — **완료·승인 (2026-06-16)**. `construction/u3-accounts/nfr-requirements/`(nfr-requirements·tech-stack-decisions). 세션 P50<5ms/P99<20ms(Q1=A), argon2-cffi(Q2=A), Multi-AZ 고가용 세션(Q3=A), RDS PostgreSQL+ElastiCache Redis(Q4=A), Google reCAPTCHA v3(Q5=B), Amazon SES(Q6=A) 확정.
- [x] NFR Design — **완료·승인 (2026-06-16)**. `construction/u3-accounts/nfr-design/`(nfr-design-patterns·logical-components). Redis 장애 시 Fail-Closed(Q1=A), reCAPTCHA Fail-Closed 및 SES PENDING 소프트폴백(Q2=B/A), PostgreSQL(10/20)+Redis(50) 커넥션풀(Q3=A), ECS 환경변수 주입 시크릿(Q4=A), 프런트 Origin CORS 명시 바인딩(Q5=A) 확정.
- [x] Infrastructure Design — **완료·승인 (2026-06-16)**. `construction/u3-accounts/infrastructure-design/`(infrastructure-design·deployment-architecture). Fargate 최소 사양(Q1=B), db.t4g.small Multi-AZ(Q2=B), cache.t4g.micro 1+1 Multi-AZ(Q3=B), NAT Gateway 배제 및 ECS Fargate 퍼블릭 서브넷 배치, RDS/Redis 고립 서브넷 배치(Q4=A), SES 도메인 인증(Q5=B) 확정.
- [x] Code Generation — **완료·③ 정정 (2026-06-17)**. _2026-06-16 재기준선 강등 결함은 ③에서 전량 해소: BR-A4 무잠금(자동 LOCKED 제거·백오프+CAPTCHA만)·SSOT 포크 제거(`docsuri_shared` 소비·`AccountCreated` model_dump·snake_case ObservabilityHub)·BR-A7 실 TOTP MFA+시딩 관리자(ADMIN 도달). 커밋 `bbac74f`·`f835a26`·`9b390b9`._ 원 강등 기록(2026-06-16): `construction/plans/u3-accounts-code-generation-plan.md` 17단계를 구현했으나 검증 결과 결함 확인: ⚠️ **BR-A4 위반**(`auth.py` 10회 실패 시 `status=LOCKED` → 무잠금 anti-DoS 규칙 직접 위반); **BR-A7 미구현**(TOTP MFA·시딩 관리자 없음 → ADMIN 도달 불가, `mfa_verified` 하드코딩 False); **SSOT 포크**(`docsuri_shared` 미소비·DTO 자체 재정의·`AccountCreated` raw dict·ObservabilityHub camelCase 오호출); 문서화된 `pytest` 명령 수집 실패(hypothesis·pytest-asyncio 누락); accounts 레인 ruff 132건(modules 제외 설정에 은폐). 의존성 주입 시 15 passed.

**U4 Library** (Track 2 — U3 다음, **Track 2 최종 유닛**):
- [x] Functional Design — **완료 (2026-06-17)**. `construction/u4-library/functional-design/`(domain-entities·business-logic-model·business-rules). 3 소유자 비공개 서브도메인(저장검색 US-L1/FR-8·라이브러리 US-L2/FR-9·이력 US-L3/FR-10). 결정 **D1~D12(권장 기본값 — 리뷰 게이트 override 가능)**: 저장검색 정규화 dedup+정원 200(BR-L1/L2)·라이브러리 `(owner,arxivId)` 멱등+정원 1000+meta 스냅샷(BR-L3/L4/L5)·이력 at-least-once `dedupe_key` 멱등+롤링 500 보존(BR-L6/L7)·키셋 커서 페이지(기본20/최대100, BR-L8)·**rerun=게이트웨이-프런티드(INV-L2 백도어 차단)**·SEC-8 **U3.AuthorizationGuard 위임**→cross-owner 일반화 404(SEC-9/INV-L4). **docsuri_shared DTO SSOT 재사용(포크 금지)**.
- [x] NFR Requirements — **완료 (2026-06-17)**. `construction/u4-library/nfr-requirements/`. [전역/U3 계승]: Python·FastAPI(CG-1)·RDS PostgreSQL·SQLAlchemy·Hypothesis·**NFR-C1 신규 비용 0(CRUD only)**. U4 고유: 포트 리포(InMemory 기본 mock-first + SQL 스캐폴드 + DDL)·base64 키셋 커서·**NFR-R2 가용성 격리(meta 스냅샷)**·QT-4 멱등.
- [x] NFR Design — **완료 (2026-06-17)**. `construction/u4-library/nfr-design/`. owner-scoping 백스톱(INV-L1)·fail-closed authz→404(INV-L4)·멱등 upsert+이벤트 멱등 소비(INV-L3)·롤링 보존 prune·정원 가드·키셋 페이지·감사 sink(SEC-13)·mock-first 포트 스왑. CI=GHA는 **deferred(재기준선: CI 전무)**.
- [x] Infrastructure Design — **완료 (2026-06-17)**. `construction/u4-library/infrastructure-design/`. **U3 인프라 계승**(동일 ECS Fargate 배포①·동일 RDS PostgreSQL); 신규 테이블 `saved_searches`/`library_items`/`search_history`(+ DDL `backend/modules/library/migrations/001`); 신규 관리형 서비스·비용 0; 이력 소비자=공유 이벤트버스(future U6/EventBridge).
- [x] Code Generation — **완료·검증 (2026-06-17)**. `backend/modules/library/`(models·schemas[docsuri_shared 재사용]·validation·ports·repository[memory+sql]·services×3·gateway 스텁·history_consumer·controller[3 라우터]·audit·migration). app-shell **`_mount_library` 마운트(mock-first, 무 DB)**. **검증: `pytest` 64 passed(library 41 + accounts 15 + app-shell 8)·`ruff` clean.** 적대적 설계 검증 18건(0 blocking)→문서 정합 반영. ⚠️ `shared/dtos/library.schema.json` PROVISIONAL→정제 스펙은 별도 shared/ PR(Track3 사인오프) 대기(코드는 로컬 검증으로 무관하게 정상).
- **→ Track 2 (U3 Accounts → U4 Library) 레인 완료.**
- [x] U6 통합·U2 real 어댑터 — **완료 (2026-06-17, ④·⑥; §크리티컬 패스 종결 참조)**

**U5 Frontend** (Track 3 @kyjness, mock-first → U2/U3/U4 DTO 계약):
- [x] Functional Design — **완료·승인 (2026-06-16)**. `construction/u5-frontend/functional-design/`(domain-entities·business-logic-model·business-rules·frontend-components). **히어로 슬라이스 스코프**(가입→로그인→검색→근거화 결과 + 상태UX; 라이브러리/이력은 계약만·후속 패스). 9컴포넌트(AppShell·PhoneMockupFrame·HeroLanding·Signup/LoginForm·SearchScreen·ResultList·ResultCard·StateView·ApiClient). 핵심: SearchResponse 4분기 상태머신(기권≠빈결과 구분)·ResultCard 7필드만(relevance=U2 표시값, raw 차단 SEC-9)·전역스토어 없음·DTO 파생 mock+transport seam(real 전환=설정 교체)·BR-U5-1~22(입력검증·XSS·SEC-12 세션·접근성). 개발지침↔aidlc 충돌 점검: PWA·오프라인 over-scope 제거. **⏳ 기술 스택(TS/SSR·타입 생성)은 NFR Requirements §5-D.**
- [x] NFR Requirements — **완료·승인 (2026-06-16)**. `construction/u5-frontend/nfr-requirements/`(nfr-requirements·tech-stack-decisions). **스택(§5-D)**: Next.js(React App Router SSR·신규 선택)·TS+JSON Schema→TS 생성(드리프트 0)·ApiClient transport-seam(전역 서버상태 라이브러리 없음)·CSS Modules·Vitest+Testing Library/Playwright/DTO 계약 테스트·SSR httpOnly 쿠키 포워딩·pnpm 독립 배포 ④. **U5 LLM 직접호출 없음 → NFR-C1 비용 기여 0**. 오프라인·PWA 제외 확정. 정량 SLO·호스팅·외부 APM은 후속.
- [x] NFR Design — **완료·승인 (2026-06-16)**. `construction/u5-frontend/nfr-design/`(nfr-design-patterns·logical-components). 패턴: 차등 재시도(멱등 GET만)·SSR 실패=완성 페이지·2계층 에러 바운더리·저하 흐름·서버/클라 컴포넌트 경계·캐싱(정적 장기/검색·세션 no-store)·**server-only 호출 경계(토큰 클라 유출 0)**·CSP frame-ancestors self·출력 무해화·stateless SSR 수평확장. 논리 컴포넌트 LC-1~9 + FD 9컴포넌트 매핑. 호스팅·정량 SLO·구체 CSP는 후속(Infra).
- [x] Code Generation (mock-first) — **Part 2 생성 완료·검증 (2026-06-16, 리뷰 게이트)**. 코드 `frontend/`(Next.js App Router·TS·CSS Modules). 16단계 전부. **검증: `tsc --noEmit` 0 errors · `vitest` 32 passed(7 files) · `next build` 성공(First Load JS ~113kB).** 히어로 슬라이스(US-H1·US-D7 + US-D1/D4·A1/A2 기여; US-L* 시그니처 stub만). ApiClient transport seam(MockTransport·real=HttpTransport 설정 교체)·server-only 토큰 경계·SEC-9 7필드·차등 재시도·2계층 에러 바운더리·CSP. 요약 `construction/u5-frontend/code/README.md`. **⚠️ TypeGen 플래그**: SSOT 스키마 루트리스/무타입 한계로 자동 codegen 대신 큐레이트 타입+드리프트검토(`pnpm gen:types`→`types/.schema-raw/`) 채택. **[2026-06-17: 아래 production 패스로 대체·머지됨.]**
- [x] Code Generation (production 패스) — **완료·로컬 검증 (2026-06-17, 브랜치 `feature/u5-v2`, 리뷰 게이트)**. 계획서 `construction/plans/u5-frontend-production-pass-plan.md`(14단계 전부). **스코프: 풀 기능 ①②③**(히어로 + 라이브러리/저장검색/이력; 인프라/CD ④는 공통 인프라 단계로 분리). **P1 계약 정렬**: 프런트 경로를 머지된 실 백엔드로(`/search`→`/api/search`·`/accounts/*`→`/auth/*`); **login 계약 정정**(실 login=쿠키만+`{status,message}`, `ApiClient.login()`→`Promise<void>`, 세션은 `GET /auth/session`); MFA=범위 밖(graceful); 생성타입 드리프트 갱신(라이브러리 DTO 전수 추가). **P2 실 transport(BFF 패턴)**: `app/bff/[...path]` catch-all(서버, `DOCSURI_GATEWAY_URL`→`HttpTransport` 쿠키 포워딩+Set-Cookie 릴레이, 없으면 mock)·클라 `RouteHandlerTransport`(`/bff/*` 동일출처)·`getApiClient` `NEXT_PUBLIC_DOCSURI_REAL_API` 분기·`server-only` 클라 미유출·호출처 5곳 교체. **P3 화면(US-L1/L2/L3)**: ApiClient stub 7개→실구현+rerun/clear, `/library`·`/library/saved`·`/library/history`(커서 페이지·rerun 인라인·담기/저장/삭제/비우기), 공용 `usePaginatedList`·`OutcomeView`·`LibraryTabs`·`cardFromMeta`(relevance 제거 SEC-9), 진입점(AppHeader 내비·ResultCard 담기·SearchScreen 검색저장). **검증: `tsc` 0 · `vitest` 48 passed(9 files; 신규 apiLibrary·libraryScreens + contract 라이브러리 계약) · `next lint` clean · `next build` 성공(라우트 10, `/bff/[...path]` 동적).** 적대적 자기검토 반영(SEC-9/8·커서 경계·login 계약·server-only). **⚠️ 의존성 플래그(U5 외부)**: 게이트웨이 세션쿠키→`request.state.principal` 미주입 → `/library/*`·`/api/search` 실 백엔드 401(fail-closed) = `backend/` 조율존 + 시스템 인프라 단계; reCAPTCHA 토큰 미전송(사이트키 필요); 인프라/CD/호스팅·구체 CSP·정량 SLO=공통 인프라 단계. **[2026-06-17 갱신: PR #63 머지(`86404d1`)·HTTPS 프로덕션 배포(`d1740b0`, Fargate+ALB+CloudFront @ docsuri.org)·BFF 빌드 복구(`344172e`); ⑤ 종결. 게이트웨이 principal 주입(`568677c`)으로 `/library/*`·`/api/search` 401 갭 해소.]**

**U6 Reliability/Ops** (데이터 및 탐지 파이프라인 우선):
- [x] Code Generation — **완료 (2026-06-16)**. `construction/plans/u6-reliability-ops-code-generation-plan.md` 25단계 전부 완료. `ops/` 패키지와 `backend/middleware/` seam 생성. 구현 범위: ObservabilityHub, CostGuardCircuitBreaker, GroundingEnforcementHook, RES-11 a/b/c 탐지기, IncidentEventPublisher, OpsDashboardService, HealthCheckService, ReliabilityEvalProbe, CLI/worker. 검증: `ops/.venv`에서 U6 범위 `pytest ops\tests backend\tests\test_u6_middleware.py` 31 passed, U6 범위 `ruff check ops backend\middleware backend\tests\test_u6_middleware.py` passed, shared contract import 및 CLI smoke passed. 명시 통합 테스트 `pytest ops\tests backend\tests\test_u6_middleware.py tests`는 46 passed. 루트 기본 `pytest`는 기존 `tests/accounts` 15 passed. 루트 `ruff check .`는 기존 `tests/accounts` unused import 9건(F401)으로 실패하여 U6 외 잔여 정리 필요. **[2026-06-17 갱신(④): `create_app` 게이트웨이 설치 + discovery 시임 실 `GroundingEnforcementHook` 주입으로 라이브 경로 연결(`ba4a62e`); PR#45 크로스리뷰 반영(`b6bb92d`); ops CI 레인(`7edd316`); CloudWatch EventStore 어댑터·프로덕션 자동 선택(`8b54b62`). F401 9건은 §크리티컬 패스 종결 잔여 항목으로 추적.]**

**U7 Summarization** (요약/번역 — 코어 U1~U6 완료 후 편입 유닛, 단일 트랙·**실배포 기준 real-first 구현**):
- [x] Functional Design — **완료·승인 (2026-06-18, 브랜치 `feature/u7-v2`·PR #115)**. 계획서 `construction/plans/u7-summarization-functional-design-plan.md`(명확화 질문 **17문** 전수 답변: **A 14·B 1[Q2 노이즈 범위 한정]·X 2[Q10/Q11 real-first]**). 산출물 `construction/u7-summarization/functional-design/`(domain-entities·business-logic-model·business-rules — 도메인 엔티티·9 컴포넌트 파이프라인·BR-S1~S14·PBT-S1~S5·추적성 미커버 0·설계입력 §2~§12 흡수 맵). **핵심 결정**: Q4(U7 고유 결정적 근거화 게이트 — frozen `enforce` 검색형상 미재사용·"단일 권위=U6"는 검색 한정 해석)·Q6(`split_sections` 부재→U7 섹션 도출+span)·Q12(버퍼-검증-스트리밍)·**Q10/Q11 real-first(포트 유지·첫 구현부터 실 Bedrock/S3+Redis·mock 대역 없음)**. **앱 코드 미생성.** _승인 완료(2026-06-18)._
- [x] NFR Requirements — **완료·승인 (2026-06-19)**. 계획서 15문 전수 A(Q14는 A+명시: **Production Mock Adapter 미구현·단위 테스트 Fixture/Stub 허용**). 산출물 `construction/u7-summarization/nfr-requirements/`(nfr-requirements·tech-stack-decisions). **바인딩**: 모델=Sonnet 4.6 요약/Haiku 4.5 번역(TD-S3)·Bedrock 스트리밍(TD-S4)·스토어 S3+Redis(TD-S5)·개인 용어집=**RDS PostgreSQL**(TD-S6)·섹션 도출=정규식·휴리스틱(TD-S7)·**비동기 잡=fast-follow(v1 동기+토큰 캡, TD-S9)**·**real-first 테스트(TD-S12)**.
- [x] NFR Design — **완료·승인 (2026-06-19)**. 계획서 10문 전수 A. 산출물 `construction/u7-summarization/nfr-design/`(nfr-design-patterns·logical-components). **패턴**: Bedrock 격리(타임아웃+1재시도+서킷→기권)·근거화 1회 재시도·**저하 3계층 구분**(비용 degradeMode≠의존성 서킷≠소스 폴백)·캐시 우선 read/write-through·**생성-버퍼-검증-점진렌더**(구조화 JSON은 완성 후 근거화)·stateless+공유 외부 상태·보안 방어심층(인젝션·개인 용어집 owner 격리)·CI real-first(단위 Fixture/Stub 항상+통합 실 의존성 별도 게이트)·RES-12 폴트 인젝션. 논리 컴포넌트 토폴로지(FD 9↔논리 매핑·기존 인프라 재사용·신규 관리형 0). 앱 코드 미생성. _승인 완료(2026-06-19)._
- [x] Infrastructure Design — **완료·승인 (2026-06-19)**. 계획서 9문 전수 A. 산출물 `construction/u7-summarization/infrastructure-design/`(infrastructure-design·deployment-architecture). **신규 관리형 서비스 0**(전부 기존 자산 재사용): 컴퓨트=기존 ECS Fargate 모듈·S3 `summaries/` 프리픽스·Redis `sum:` 키스페이스+TTL·RDS `user_glossary` 테이블(마이그레이션)·Bedrock IAM(모델 ARN 스코프)·CloudWatch/Budget 비용 라인·CI 통합 게이트 레인. 비동기 잡 v1 미프로비저닝. 증분 비용≈Bedrock 토큰(가변). **조율 존**(task role·CI·IaC·마운트)=@ELSAPHABA/Infra. 앱 코드 미생성. _승인 완료(2026-06-19)._
- [x] Code Generation — **Part 1·2 완료·검증 (2026-06-19, 브랜치 `feature/u7-v2`·PR #115)**. 계획서 18단계 전부 [x]. 코드 `backend/modules/summarization/`(src-layout, real-first): 도메인 9컴포넌트(models·refiner·source_selector·cache_key·length_router·glossary·grounding·assembler·orchestrator)·실 어댑터 단일본(bedrock_llm 스트리밍·s3_redis_store·s3_full_text·rds_glossary)·api(router `/api/summarize`·gateway_seam)·prompts(본문 격리)·real_wiring·`migrations/001_create_user_glossary.sql`. **검증: `pytest` 29 passed + 1 skip(통합 self-skip)·`ruff` clean.** Q4 U7 고유 결정적 근거화·Q5 버퍼-검증·저하 3계층·Q8 후치환(한국어 조사 안전)·real-first(Production Mock Adapter 없음·테스트 Fixture/Stub). **⚠️ 마운트=조율 존**: `backend/wiring.py` 미변경(쉘 테스트 보호) — mounter 스니펫을 `code/README.md`에 사인오프-레디로 제시. 인프라 증분(IAM·마이그레이션·CI)=@Infra. _승인 완료(2026-06-19)._
- [x] Build & Test — **완료 (2026-06-19)**. 산출물 `construction/u7-summarization/build-and-test/`(build-instructions·unit-test·integration-test·security-test·build-and-test-summary). **검증: `pytest` 29 passed + 1 skip(통합 게이트 self-skip)·`ruff` clean·임포트 스모크 OK.** 통합 5 시나리오 정의(게이트 레인 전용·real-first). 성능=N/A(NFR-P2 온디맨드). **U7 CONSTRUCTION 종료.** Operations 전 last-mile(프레임워크 밖): app-shell 마운트(@ELSAPHABA)·인프라 증분(@Infra)·`shared/dtos/summarization` 승격·비동기 잡 fast-follow.
- [x] **개인 용어집 편집 후속 (2026-06-22, 브랜치 `feature/u5-frontend-ux`·PR #121)**: BR-S4의 "사용자 용어 수정→upsert"를 사용자 경로로 노출. 백엔드 **`GET/POST /api/glossary`**(owner-scoped·입력 검증·fail-closed, 저장 시 `glossary_ver++`→해당 사용자 캐시 무효화) + 프론트 `TranslationView` keptTerms 배지 탭→저장·미리채우기(**BR-SF-17**). 후치환을 함수 치환으로 보강(사용자 입력의 정규식 역참조 해석 차단). 문서 정합: `nfr-design/logical-components`·`infrastructure-design/deployment-architecture`·프론트 `functional-design/frontend-components`·`business-rules` 갱신. **검증: 프론트 68·백엔드(summarization) 42 통과·lint/ruff clean.** 후속(Phase 2-b): 마이페이지 "내 용어집" 보기·수정·삭제 + `DELETE` 엔드포인트.
- [x] **프론트 카드·내비 UX 패스 (Phase A) (2026-06-22, 브랜치 `feature/u5-card-nav-ux`)**: 프론트 로컬 UX 정리(계약·DTO 불변). ① 상세 요약 단락명 `기여/방법/결과`→`핵심 기여/연구 방법/주요 결과`(+tldr 라벨 `한 줄 요약`). ② **카드 [요약]/tldr 피크 기능 폐지**(`SummaryAction`/`SummaryInline` 제거 — 요약은 상세로 일원화; **Q1·Q2 카드 인라인 결정 대체**). ③ 담기 버튼→카드 **우상단 북마크 아이콘** + 상세 제목 옆 북마크(저장 계약 불변·멱등). ④ 카드 `relevance` **표시 제거**(계약엔 유지) + **클라 정렬 토글(관련도순/최신순)**. ⑤ **하단 고정 탭바(`BottomNav`)** 검색/마이페이지(모바일 우선; 상단 `AppHeader`는 브랜드+로그아웃만 유지. 에이전트 탭은 기능 생길 때·인용수 표시는 U8 머지 후 보류). 추가 미세조정(검색 '논문 검색' 라벨 제거→aria-label·'검색 저장'→'검색어 저장'·저장/정렬 한 툴바·상세 헤더 간격·구분선 축소). 문서 정합: u5 `functional-design/business-rules`(BR-U5-4/5/23)·`domain-entities`·`frontend-components`, u7-frontend `functional-design/frontend-components`·`nfr-design`. **검증: `tsc` 0·`next lint` clean·`vitest` 70 passed·`next build` OK.** 보류 트랙(별건): 그림·도표(멀티모달=요구사항 개정) → **2026-06-22 인셉션 진입**(아래 멀티모달 표시 항목)·필터.

- [~] **doc-model 실데이터 완성 — PR-1 (2026-06-24, 브랜치 `feature/docmodel-realdata`, base `feature/docmodel-foundation`/#161 스택)**: doc-model 피벗 기반(#161: 생산·읽기 API·리치뷰) 위에 실데이터 경로를 비동기로 완성. **① 파서 충실도**(`ltx_appendix` 섹션 인식 — 부록 하위 flatten 해소; `_inline_text`가 `ltx_note` 각주 skip — 본문 오염 제거; theorem 본문은 paragraph로 보존). **② lazy 빌드 트리거(경계 B·비동기)**: 읽기 미스 → U7이 U1 큐에 `BUILD_DOC_MODEL` 잡 enqueue(빌더 직접 의존 X) → 워커가 `DocModelBuilder.build` 실행·캐시 → 읽기 API `building`(폴링) 반환(BR-30/§7.2). **③ 긴 논문 요약 맵리듀스 + 비동기 잡(BR-S6/BR-S12, #135)**: 40K~120K = `MapReduceSummarizer`(섹션 청킹·오버랩·reduce), API enqueue→`PendingDTO`→폴링→요약 워커 inline 생성→write-through; **>120K = 거절(degraded 폐기, 모바일 결정)**; 번역 맵리듀스는 PR-2. 게이트 `DOCSURI_MAP_REDUCE_ENABLED`/`DOCSURI_SUMMARY_JOB_QUEUE_URL`/doc-model 빌드 큐 **기본 OFF → 라이브 무변경**. 공유계약: `docmodel.schema.json` **building**·`summarization.schema.json` **pending** 신설(재생성). 프론트: `useDocModel`/`useSummarize` 폴링(retryAfterMs·상한). **④ CDK 인프라(slice 6, synth 검증·배포 X)**: `infrastructure-design.md`(단일 버킷 prefix·요약 큐+빌드큐 재사용·요약 워커 배포 단위 ④·IAM 3역할) + `compute_stack`(API task role: doc-model GetObject·summary R/W·두 큐 SendMessage·Bedrock·큐 URL env — 활성화는 팀 deploy) + 신규 `summarization_stack`(요약 잡 큐+DLQ + 요약 워커 Fargate, API 이미지 재사용) + app.py 등록. **doc-model 빌드 잡=ingestion 큐+워커 재사용**(신규 큐 불요). **⑤ OA 게이트(slice 7)**: OA 신호 = U1 인제스션 검증(CC만 저장·비-OA 거부, BR-1) → 코퍼스 전부 OA·인앱 렌더 안전 → 게이트는 운영 토글(논문별 라이선스 조회 불요·오버엔지니어링 회피); 주석·문서 정합, 활성화는 팀 deploy. 문서 정합: U1 BLM §7.2·U7 BR-S6/S9/S12·BLM §3.6·NFR TD-S9·shared docmodel §5·infrastructure-design·length_router. **검증: 백엔드 summarization·ingestion·shared(drift 0)·프론트(tsc/lint/93)·`cdk synth`(6스택) 전부 green.** 후속: 번역 구조화(PR-2)·각주 footnote 블록·앵커 id 계약·doc-model 빌드 실패 네거티브캐시.

- [~] **구조화 번역 — PR-2 (2026-06-24, 브랜치 `feature/docmodel-structured-translation`, base `feature/docmodel-realdata` 스택 — #163 머지 시 develop retarget)**: 번역 영역 전부(PR-1 의도적 미룸). doc-first. 설계 게이트 확정: **① 출력 = 번역본 doc-model**(자기완결 — 본문 번역 = 본문과 동일 구조화 형식; `summarization.schema.json` `TranslationDraft` `{koreanText}`→`{docModel: DocModel, keptTerms}`로 개정, `docmodel.schema.json#/$defs/DocModel`을 **크로스파일 `$ref`**로 복제 회피·생성기 지원 확인). **② 긴 번역 = 비동기**(요약 잡 큐·워커 재사용, `task=translate`). **번역 단위**: 섹션 제목·문단·리스트·표/그림 캡션만 번역; **표 셀·수식 LaTeX·코드·블록 id·그림 assetRef = verbatim 보존**(D8). **재조립**: LLM은 id→번역텍스트로 받아 소스 doc-model 구조에 주입해 결정적 재조립(누락 id=원문 보존); 출력이 자기완결이라 parserVersion 캐시키 불요(요약과 동일). **긴 본문 map-only**: MAP_REDUCE 밴드 translate = 섹션별 번역→이어붙이기(reduce 없음), OVER_CAP 거절 유지. 잡 큐·워커는 task-agnostic(요약·번역 공용). 프론트: `DocModelViewer` 렌더부 `DocModelBody`로 분리 → `TranslationView`가 번역본 doc-model 구조 렌더(keptTerms 유지·그림 자산 로드). 문서 정합(doc-first): BR-S18 신설·BR-S2/S6/S9/S12·FR-13·domain-entities·BLM §3.6/3.7·plan PR-2 절. **검증: summarization pytest·ruff 베이스라인·shared drift 0·프론트 tsc/lint/vitest 93 green.** 후속: 표 셀 번역·각주 블록·앵커 id 계약·빌드 실패 네거티브캐시.

- [~] **멀티모달 표시(그림·도표) — INCEPTION 진행 (2026-06-22, 브랜치 `feature/multimodal-display`)**: 보류 트랙 "그림·도표"를 Requirements Analysis 재진입으로 착수. 명확화 질문지 `inception/requirements/requirement-verification-questions-multimodal-display.md` Q1~Q7 확정(**Q2=C 혼합 추출, 나머지 A**) → `requirements.md` 등재(**FR-17** 그림·도표 자산 추출·표시 + FR-12 앵커 자산 연결 보강 + **§12 "그림·도표" 제외를 "비전 추론만 제외"로 한정** + §13 추적성). **범위: 표시 전용**(자산 추출·저장·렌더; 요약/번역 LLM 입력은 텍스트+캡션 유지, 이미지 비전 추론은 차기 사이클). 영향: U1(자산 추출·저장, 소스 가용성 혼합)·공유계약·U7(통과 + 백/프론트 정합 갭 3건 흡수: `summarization.schema.json` SSOT 수립·`validation_error`/`unauthorized` 상태 매핑)·U5(렌더).
  - [x] **U1 Functional Design — 완료 (2026-06-22)**. 계획서 `construction/plans/u1-ingestion-multimodal-functional-design-plan.md` Q1~Q7 전부 권장안 A. 기존 U1 FD 확장: `domain-entities`(§10 FigureTableAsset·AssetManifest·AssetStorePort), `business-logic-model`(§6 ingestOne 자산 추출·저장 — Q1=A parse 추출+dedup 후 NEW\|CHANGED 저장, Q2=C 혼합, Q4=A best-effort·비차단, tombstone/CHANGED 정리), `business-rules`(§7 BR-22~28·P7/P8·FailureReason·추적성). **표시 전용**: 인덱싱/임베딩/IndexRecord 경로 불변(자산 검색 비대상). **앱 코드 미생성.**
  - [x] **U1 NFR Requirements — 완료 (2026-06-22)**. 계획서 `construction/plans/u1-ingestion-multimodal-nfr-requirements-plan.md` Q1~Q7 전부 권장안 A. 기존 U1 NFR 확장: `tech-stack-decisions`(**TD-11** PyMuPDF 휴리스틱 PDF 크롭·**TD-12** e-print 그래픽 직접+표 크롭·**TD-13** WebP 재인코딩·치수상한·메타스트립·**TD-14** S3 prefix+공유 RDS 매니페스트·**TD-15** 이미지 보안 재인코딩), `nfr-requirements`(§11 성능·보안·복원력·비용). 상속: Python·S3·Hypothesis. **ML/GPU 없음**(CPU 배치, $1600 내 흡수). **앱 코드 미생성.**
  - [x] **U1 NFR Design — 완료 (2026-06-22)**. 계획서 `construction/plans/u1-ingestion-multimodal-nfr-design-plan.md` Q1~Q5 전부 권장안 A. 기존 U1 NFR Design 확장: `logical-components`(§5 AssetExtractor·Image Normalizer·AssetStore 컴포넌트 + 토폴로지 + `paper_asset` RDS 상태), `nfr-design-patterns`(§7 page-crop 검출·캡션 매칭 알고리즘·이미지 정규화 파이프라인·best-effort 격리·매니페스트 write-order 정합 P8·보안 + 추적성 행). 기존 인덱스/원자성 토폴로지 불변. **앱 코드 미생성.**
  - [x] **U1 Infrastructure Design — 완료 (2026-06-22)**. 계획서 `construction/plans/u1-ingestion-multimodal-infrastructure-design-plan.md` Q1~Q5 전부 권장안 A. **U1 최초 Infra 산출물**(멀티모달 범위로 한정): `infrastructure-design/infrastructure-design.md`(S3 `assets/` prefix·SSE-KMS·만료없음·`paper_asset` RDS 스키마/마이그레이션·최소권한 IAM·presigned 만료·비용 라인) + `deployment-architecture.md`(워커 co-location·메모리 헤드룸·토폴로지·전달 경로). 기존 전문 S3·공유 RDS 재사용(신규 버킷·DB 0), presigned S3 직접(CloudFront 후속). **선결 상속(미결)**: 워커 런타임 타깃(ECS/Lambda)·리전·CD. **앱 코드 미생성.**
  - [x] **U1 Code Generation — 완료 (2026-06-22)**. 계획 Q1=A(permissive 스택 pypdfium2·pdfplumber·Pillow — PyMuPDF/AGPL 회피, TD-11/13 정정). 브라운필드 `ingestion/`: 신규 `domain/assets.py`·`asset_extraction.py`(caption_kind·finalize P7·ImageNormalizer·AssetExtractor 혼합)·`adapters/assets.py`(ArxivAssetSource·S3RdsAssetStore write-order P8)·`migrations/postgres/002_paper_asset.sql`; 수정 `enums.py`·`ports.py`(AssetSource/StorePort)·`application.py`(best-effort 비차단 자산 단계·tombstone 정리·포트 주입 미주입=off)·`settings.py`(MULTIMODAL_ASSETS_ENABLED off 기본)·`pyproject.toml`(assets extra). 테스트 `tests/test_assets.py`(PBT P7·normalizer)·`tests/test_asset_wiring.py`(기본 off·성공·실패 비차단). **인덱스 경로 코드 불변.** **검증**: compileall·순수 로직 스모크 통과(전체 테스트=Build & Test).
  - [x] **U1 Build & Test — 완료 (2026-06-22)**. `uv sync --extra assets`(pypdfium2·pdfplumber·Pillow 설치) → `pytest` **42 passed/0 failed**, `ruff` **clean**(B904/E501 정정). 자산 신규 테스트(caption·finalize **PBT P7**·ImageNormalizer bomb 가드·best-effort 비차단 wiring) + 인덱스 경로 회귀 통과. 실 추출(`_page_crop`/`_structured`)·`S3RdsAssetStore`는 env-gated 통합으로 이연. 산출물 `construction/u1-ingestion/build-and-test/`(build·unit-test·summary). **U1(생산자) 멀티모달 슬라이스 종결.** 다음(멀티모달 트랙): 공유계약 → U7 → U5.
  - [x] **U7 Functional Design — 완료 (2026-06-22)**. 계획서 `construction/plans/u7-summarization-multimodal-functional-design-plan.md`(위임 진행, 게이트 결정 D1~D5 확정). 기존 U7 FD 확장: `domain-entities §9`(AssetRef·PaperAssetsResponse union·`GET /api/papers/{id}/assets` 엔드포인트·AssetManifestReadPort/AssetUrlSigner·앵커↔자산 연결·갭#1 SSOT·갭#2/#3 상태), `business-rules`(BR-S15 자산 읽기·OA 게이트·presign SEC-9, BR-S16 SSOT 수립, BR-S17 상태 매핑, PBT-S6). **U7은 읽기 측**(생산=U1), 요약/번역 생성·근거화·캐시 불변. **앱 코드 미생성.** 다음: U7 Code(shared schema·`/assets` 엔드포인트·갭 수정·frontend types/classify).
  - [x] **U7 Code Generation + Build & Test — 완료 (2026-06-22)**. 공유: `shared/dtos/summarization.schema.json` **SSOT 수립**(갭#1). 백엔드(`backend/modules/summarization`): `StoredAsset`/`AssetRef`(SEC-9 서명 URL만)·`AssetReadPort`·orchestrator `list_assets`·**`GET /api/papers/{id}/assets`**(인증·OA 게이트·presign)·`adapters/rds_assets.py`(RDS 읽기+S3 presign)·**갭#2** `validation_error` message. 프론트: `summarize.ts`(AssetRef·PaperAssetsResponse·unauthorized/validation_error)·`classifyAssetsResponse`+**갭#2/#3 매핑**·`apiClient.getAssets`. NFR/Infra는 경량 폴드(읽기 포트·presign TTL·`assets_enabled` 게이트). **검증: 백엔드 summarization 48 passed/1skip·자산 7 passed·ruff clean; 프론트 tsc 0·next lint clean·vitest 75 passed(+5).** 요약/번역 생성·근거화·캐시 불변. **U7(읽기 측) 멀티모달 슬라이스 종결.** 다음: U5(상세/뷰어 자산 렌더 컴포넌트).
  - [x] **U5 Code Generation + Build & Test — 완료 (2026-06-22)**. 프론트: `lib/assetAnchor.ts`(순수 매처 — figure/table 앵커↔자산)·`lib/useAssets.ts`(페치 훅)·`components/AssetGallery.tsx`(+css; lazy·치수예약·캡션 이스케이프·서명 URL img·로딩/에러/빈·라이선스 미표시·활성 앵커 스크롤)·`PaperDetailIsland`(자산 섹션+앵커 전달)·mock(`/assets`+SVG 픽스처). 테스트 `test/assetAnchor.test.ts`·`test/assetGallery.test.tsx`. **검증: tsc 0·next lint clean·vitest 80 passed(+5)·next build OK.** 코드 요약 `construction/u5-frontend/code/u5-multimodal-asset-render-code-summary.md`.
  - **✅ 멀티모달 표시(FR-17) 트랙 완결**: U1(추출·저장) → 공유계약/U7(노출·정합 갭 3건) → U5(렌더). 비전 LLM 추론은 차기 사이클. 9커밋 `feature/multimodal-display`(미push). 배포(Operations)는 push/PR·승인 후.
  - [x] **표시 UX 정제 + 자산 점등 코드 배선 (2026-06-22, 브랜치 `feature/multimodal-display`)**: FR-17 표시 슬라이스 후속 패스.
    - **갤러리 UX**: `AssetGallery`를 큰 인라인 이미지 → **컴팩트 썸네일 그리드(모바일 3·데스크톱 4) + 탭하면 전체화면 라이트박스**로 전환(신규 `AssetLightbox`+css; ‹이전/다음›·카운터·ESC/배경/✕ 닫기·←→ 키보드·바디 스크롤 락·포커스). 모바일에서 큰 이미지가 본문을 가리는 문제 + 수십 장 세로 열거 문제를 동시 해소(썸네일 `cover`·라이트박스 `contain`). figure/table 앵커 "출처 보기"=썸네일 스크롤+라이트박스 자동 오픈. **신규 라이브러리 0**.
    - **북마크 토글 버그 수정**: `SaveToLibraryButton`이 저장 후 `disabled`라 취소 불가였음 → 멱등 add가 반환하는 item id 보관 → 재클릭 시 `removeFromLibrary`로 **토글(담기↔빼기)**, 진행 중에만 비활성. (`/library/items` DELETE는 U4 라이브 경로 — 인프라 불필요.)
    - **자산 점등 코드 배선(옵션 B)**: "인프라만 깔면 켜짐" 상태로 배선하되 **기본 OFF 유지**(인프라 없이 안전 머지). 읽기측(U7): `SummarizationSettings.assets_enabled`(`DOCSURI_MULTIMODAL_ASSETS_ENABLED`)·`asset_url_ttl_seconds` 추가 → `real_wiring`가 플래그+DSN 있을 때 `RdsS3AssetReader` 주입 → `_mount_summarization`이 `assets_enabled`를 라우터에 전달. 쓰기측(U1): `build_production_runtime`이 `multimodal_assets_enabled` 시 `AssetExtractor`/`ArxivAssetSource`/`S3RdsAssetStore` 주입(셋 모두 주입돼야 추출 동작). **검증: 프론트 tsc 0·lint clean·vitest 83·build OK; 백 summarization 54 passed/1skip·ruff clean; ingestion 43 passed·ruff clean.**
    - [ ] **🔌 자산 점등 체크리스트 — 실 인프라 배포 (담당 팀원, 승인·비용 결정 후)**: 코드 배선(옵션 B) 완료 → 아래만 하면 프로덕션 점등.
      1. **인프라 프로비저닝(CDK, `ops/cdk/stacks/ingestion_stack.py` 등)**: S3 `assets/` prefix + SSE-KMS 키, presign용 최소권한 IAM(워커=S3 put+RDS write / BFF task role=S3 get+presign). `paper_asset` 마이그레이션은 `backend/migrations/__main__.py` 경로에 이미 포함(배포 시 적용).
      2. **워커 이미지**: ingestion `assets` extra 설치(pypdfium2·pdfplumber·Pillow).
      3. **환경변수 ON**: 워커 `DOCSURI_MULTIMODAL_ASSETS_ENABLED=true`(+`DOCSURI_S3_BUCKET`·`DOCSURI_CONTROL_PLANE_DSN`·`DOCSURI_ASSET_KMS_KEY_ID`); BFF `DOCSURI_MULTIMODAL_ASSETS_ENABLED=true`(+`DATABASE_URL`·`DOCSURI_SUMMARY_BUCKET`·`DOCSURI_ASSET_URL_TTL_SECONDS`).
      4. **백필(비용 결정)**: 추출은 신규 인제스천만 자산 생성 → 기존 코퍼스(수십만 편)는 재인제스천 필요(CPU+S3 비용). 점진 백필 권장.
    - [x] **자산 통합 테스트 A·B (2026-06-22)** — 점등 전 env-gated 구간을 실제로 검증(AWS·비용 0). **A(실 추출, 오프라인)**: `ingestion/tests/test_asset_extraction_real.py` — 합성 텍스트-레이어 PDF로 **실 pdfplumber 캡션 검출 + pypdfium2 렌더 + 크롭 + WebP 정규화** 왕복(figure/table·page-crop·hybrid Q2=C e-print 우선) + 합성 e-print tar로 structured 경로. AWS·네트워크·외부 PDF 픽스처 0. **B(실 SQL, 실 Postgres)**: `ingestion/tests/test_asset_store_real.py`(`S3RdsAssetStore` 쓰기 — S3 put[웹P·SSE]→`paper_asset` 행→P8 write-order→CHANGED 멱등 재저장→remove; S3는 monkeypatch 가짜)·`backend/.../tests/test_assets_rds_real.py`(`RdsS3AssetReader` 읽기 — SELECT 컬럼 매핑·JSONB bbox·null·presign; S3는 주입 가짜). **`DOCSURI_TEST_PG_DSN` 게이트**(미설정 시 스킵 — `test_integration_real.py` 관례), Docker 임시 PG16 netns-공유로 **실행 green 확인**. **C(실 인프라/스테이징 E2E)는 위 점등 체크리스트로 팀원 위임.** **검증: ingestion 47 passed/1skip(B 게이트)·summarization 54 passed/3skip(B 게이트)·ruff clean.**
  - [ ] **🔮 보류 트랙 — 비전 추론(멀티모달 요약·근거화) [차기 사이클 후보]**: `requirements.md` §12 멀티모달 카브아웃(2026-06-22)·FR-17이 명시적으로 **제외 유지**한 범위. 이미지(그림·도표)를 비전 LLM으로 읽어 **요약·근거에 반영**하는 작업. 현재 v1은 요약/번역 LLM 입력이 **텍스트+캡션**으로 한정(이미지 비전 추론 없음).
    - **기반 준비됨**: FR-17 표시 전용 슬라이스가 자산을 이미 S3에 추출·저장(U1)하고 서명 URL로 노출(U7)·렌더(U5)한다 → 비전은 **재인제스천 없이** 기존 자산을 읽는 **추론 레이어 추가**이지 데이터 파이프라인 재작업이 아님.
    - **범위 영향(예상)**: U7 요약 노드 모델 교체(비전 가능 모델·비용/지연 ↑·NFR-C1 비용 상한 재산정)·이미지 앵커 grounding 재설계(FR-5/QT-5 근거화 경계 확장)·Prompt Injection 무해화(이미지 경유 포함). **요구사항 재진입(승인 게이트) 필요** — C-2 생성 경계·FR-5 근거화 정신 유지 확인.
    - **선후 권고**: "차별화/근거형성 에이전트"(`summarization-translation-pipeline.md` #9·#12 — 파이프라인 6~7단계 재사용 + '유사논문 검색' 노드 추가)와는 **독립 트랙**(의존성 없음). 에이전트는 현재 텍스트+캡션 근거화로 동작 가능 → **에이전트 먼저 검증 → 비전을 리프 요약 노드 품질 업그레이드로 후속 도입** 권장(에이전트가 같은 노드를 재사용하므로 근거 품질이 자동 상승; 미검증 흐름에 N배 비용 곱 방지).

**U8 Citation Graph** (인용 그래프/각주 트리 — 2026-06-19 편입 유닛, FE 구현 제외 API 모듈):
- [x] Functional Design — **완료·승인 (2026-06-19)**. 계획서 `construction/plans/u8-citation-graph-functional-design-plan.md` Q1~Q12 전부 권장안(A) 반영 및 체크박스 완료. 산출물 `construction/u8-citation-graph/functional-design/` 3문서(`domain-entities.md`, `business-logic-model.md`, `business-rules.md`) 생성. **앱 코드·FE 미생성.**
- [x] NFR Requirements / NFR Design / Infrastructure Design / Code Generation / Build&Test — **완료 (2026-06-21)**. U8 backend-only citation graph slice 생성 및 검증 완료.
- [~] Cross-Review 반영 — **진행 (2026-06-22)**. 브랜치명은 `feature/u8-v1`로 CI prefix 조건 충족. 코드 수정: 죽은 `depth` 쿼리 제거, provider/cache 중복 제거, save year 범위 밖 값 null 처리, telemetry `emit_log` 방어 및 `depthRequested` 분리. 문서 수정: Redis 단언을 현재 process-local in-memory snapshot seam + production Redis target으로 정정.

**v4-migration** (Cohere Embed v4.0 Migration):
- [x] NFR Design — **완료·승인 (2026-06-23)**. `nfr-design-patterns.md`, `logical-components.md` 생성 완료. Fail-Open 듀얼 라이트 및 arXiv API 기반 Idempotent 백필 전략 승인.
- [x] Infrastructure Design — **완료·승인 (2026-06-23)**. `infrastructure-design.md`, `deployment-architecture.md` 생성 완료. Local execution 및 Automated Cutover 맵핑 확정.
- [x] Code Generation — **완료 (2026-06-23)**. U1 Ingestion 듀얼 라이트 로직, U2 Discovery alias 설정 및 Ops 백필/컷오버 스크립트 작성 완료.
- [x] Build & Test — **완료 (2026-06-23)**. 빌드 및 테스트 가이드 산출 완료.

**공통 후속 단계** (per-unit 또는 횡단):
- [x] 병렬 개발 조율 (2026-06-16 반영) — `shared/` 공용 규약 선행 작성 및 3개 독립 트랙 병렬 진행 확정
- [x] `shared/` 규약 작성 (vector-spec·DTOs·events·ports) — **완료 (2026-06-16)**. `construction/shared/`(5문서). vector-spec 🔒FROZEN(Cohere 1024·코사인·input_type 비대칭·IndexRecord); DTOs/events/ports SSOT 정합·적대적 검증(ship); **63 tests pass·드리프트 스크립트(`tools/generate.py --check`) 동작**. **3 트랙 unblocked.** ⚠️ **드리프트 가드는 수동 스크립트일 뿐 CI 미연결**(`.github/workflows/` 부재); **U3 accounts는 docsuri_shared 미소비(SSOT 포크)** — U1·U2만 실소비.
- [x] U1 NFR Design 승인 (2026-06-16)
- [x] Infrastructure Design — **완료 (2026-06-17, 시스템 전역)**. `construction/infrastructure-design/infrastructure-design.md`(`ac21ae2`) + AWS CDK 5 스택(Network·Search·Compute·Ingestion·Frontend, `ddf8858`). AWS 자원·리전/AZ 토폴로지(RES-2, 서울 단일리전 멀티 AZ)·오토스케일링/쿼터(RES-8) 반영.
- [x] Code Generation — **완료**. 전 유닛(U1~U6) 코드 + 시스템 IaC/CD(`db1b187`)·프로덕션 실연결(`01fd553`·`5f7acce`)·SES(`50da0d5`·`0437b40`).
- [x] 빌드 & 테스트 — **완료·승인 (2026-06-16)**. `construction/build-and-test/`에 build, unit, integration, performance, contract, security, summary 문서 생성. 로컬 U1 검증 결과(`pytest` **23 passed**, `ruff` pass, CLI smoke `NEW`) 반영. ⚠️ **자동 CI 게이트 없음**(수동 실행만; §검증 재기준선).

### 🟡 OPERATIONS 단계
- [~] Operations — **placeholder 확인 완료 (2026-06-16)**. `operations/operations-placeholder.md` 생성. 현재 룰셋상 배포·모니터링·운영 런북 실행은 future scope이며, 워크플로우는 Build and Test 이후 종료.
- [x] **Operations placeholder — 재인셉션 페이즈 1 / U1 Corpus (2026-06-26)**. 사용자 승인으로 Build and Test 리뷰 게이트를 통과하고 Operations placeholder로 전환. `operations/operations-placeholder.md`를 U1 Corpus 최신 검증 결과(ingestion 129 passed/1 skipped, shared/ops/discovery/summarization/frontend 소비자 검증)와 남은 실제 운영 범위(source provider quota, GROBID capacity, bounded backfill, OpenSearch cutover, monitoring)로 갱신. 현 룰셋상 실행 가능한 Operations 단계는 없으므로 이번 AI-DLC 사이클은 여기서 종료.
- [x] **Operations 하드닝 패스 (2026-06-18, PR #79·#84 → develop, 라이브 배포·검증 완료)** — CONSTRUCTION 종료 후 프로덕션 운영 첫 단계. 산출:
  - [x] **운영 런북** `operations/runbook.md` — 시스템 맵·함정(RETAIN 3종·ALB `/healthz` 서킷브레이커·SSO)·비용가드 강등표·복구절차·SLO 3개.
  - [x] **알림 마지막 1마일** (코드에 존재하나 사람에게 미연결이던 갭): G3 `CLOUDWATCH_NAMESPACE` env로 prod 관측 활성·G2 SES 토픽 ops 구독·G4 CloudWatch 알람(5xx·p95)+G1 AWS Budget($1280) → `OpsAlerts` 토픽/ops 메일. 전부 `compute_stack.py` (synth 검증).
  - [x] **검증(라이브, 2026-06-18, 계정 028317349537)**: `cdk deploy Docsuri-Compute -c ops_alert_email=corpseonthemission@icloud.com` → API 롤링 생존(/healthz 200) · SNS 구독 2개 confirm · **테스트 알람(set-alarm-state ALARM)→이메일 수신 확인** · **RDS 스냅샷→`docsuri-restore-test` 복원 available(DBName=docsuri·pg16.13)→폐기**. Budget는 직접 이메일 구독이라 구성 완료(실 발화는 $1280 도달 시).
  - [x] **G3 IAM 보강** (PR #84): task role에 `cloudwatch:PutMetricData`(namespace 스코프)+`logs:*` + `/docsuri/ops` 로그그룹 retention 30일 선생성. `CLOUDWATCH_NAMESPACE` env만으론 부족(권한 부재→AccessDenied 무성 실패)했던 것 보강.
  - [ ] **G3 잔여(U6 후속)**: 모듈 서비스가 `NoopObservabilityHub`에 emit(`discovery/real_wiring.py:84`·`mocks/wiring.py:56`, "until U6 exposes process-wide singletons") → 정상 트래픽 앱 메트릭이 진짜 hub(→CloudWatch)에 미도달. 게이트웨이 에러 경로만 진짜 hub. 수정=`backend/wiring.py`+모듈 팩토리에 `app.state.observability` 주입(ops 범위 밖). **알림/페이징은 네이티브 ALB 메트릭이라 무관하게 작동.**
  - 천장(의도적 미구현): 앱 내부 cost guard의 per-incident SNS publisher — Budget가 빌링 레벨에서 대체.

## 비고
- 이번 사이클은 클린 재시작이다. 폐기된 사이클 1(U1·U2·U4 데모)은 AWS Bedrock(Claude Haiku), Amazon Comprehend, S3 Vectors 기반 Bedrock Knowledge Base, Amplify 호스팅, Python 백엔드, Next.js 프런트엔드를 사용했다. 그중 어느 선택도 기본 계승하지 않으며 선행 사례(prior art)로만 참조한다.
- 브랜치: `develop` (4 트랙 PR + 후속 크리티컬 패스 ①~⑦ PR 전부 머지 완료). **2026-06-18 기준: CONSTRUCTION 코드·인프라 종결·AWS 프로덕션 배포 완료(§크리티컬 패스 종결). 잔여 = 문서 정합·루트 `tests/` 린트 사각(F401 9건)·Operations 런북 결정.**
## U8 Citation Graph — NFR Requirements Complete / NFR Design In Progress

- Date: 2026-06-21
- Unit: U8 Citation Graph
- Completed: NFR Requirements answers Q1~Q12 all set to recommended option A.
- Completed artifacts:
  - `aidlc-docs/construction/u8-citation-graph/nfr-requirements/nfr-requirements.md`
  - `aidlc-docs/construction/u8-citation-graph/nfr-requirements/tech-stack-decisions.md`
- Next stage entered:
  - `aidlc-docs/construction/plans/u8-citation-graph-nfr-design-plan.md`
- Current gate: U8 NFR Design questions Q1~Q5 awaiting answers.
- Code/FE generated: no.

## U8 Citation Graph — NFR Design Complete / Infrastructure Design In Progress

- Date: 2026-06-21
- Unit: U8 Citation Graph
- Completed: NFR Design answers Q1~Q5 all set to recommended option A.
- Completed artifacts:
  - `aidlc-docs/construction/u8-citation-graph/nfr-design/logical-components.md`
  - `aidlc-docs/construction/u8-citation-graph/nfr-design/patterns.md`
  - `aidlc-docs/construction/u8-citation-graph/nfr-design/runtime-architecture.md`
  - `aidlc-docs/construction/u8-citation-graph/nfr-design/test-strategy.md`
- Next stage entered:
  - `aidlc-docs/construction/plans/u8-citation-graph-infrastructure-design-plan.md`
- Current gate: U8 Infrastructure Design questions Q1~Q3 awaiting answers.
- Code/FE generated: no.

## U8 Citation Graph — Infrastructure Design Complete / Code Generation Plan Ready

- Date: 2026-06-21
- Unit: U8 Citation Graph
- Completed: Infrastructure Design answers Q1~Q3 all set to recommended option A.
- Completed artifacts:
  - `aidlc-docs/construction/u8-citation-graph/infrastructure-design/infrastructure-components.md`
  - `aidlc-docs/construction/u8-citation-graph/infrastructure-design/deployment-topology.md`
  - `aidlc-docs/construction/u8-citation-graph/infrastructure-design/configuration.md`
- Next gate:
  - `aidlc-docs/construction/plans/u8-citation-graph-code-generation-plan.md`
- Current gate: Code Generation approval question awaiting answer.
- Code/FE generated: no.

## U8 Citation Graph — Code Generation and Build/Test Complete

- Date: 2026-06-21
- Unit: U8 Citation Graph
- Completed: Code Generation plan approved as option A.
- Code generated:
  - `backend/modules/citation_graph/__init__.py`
  - `backend/modules/citation_graph/controller.py`
  - `backend/wiring.py`
  - `backend/tests/test_citation_graph.py`
  - `backend/tests/test_app_shell.py`
- Verification:
  - `python -m pytest backend/tests/test_citation_graph.py backend/tests/test_app_shell.py -q` -> 15 passed
  - `python -m pytest backend/tests -q` -> 33 passed, 1 skipped
  - `python -m ruff check backend/modules/citation_graph backend/wiring.py backend/tests/test_citation_graph.py backend/tests/test_app_shell.py` -> pass
  - `python -m compileall backend/modules/citation_graph backend/wiring.py` -> pass
- FE generated: no.
- Current gate: user review/approval, commit, or PR direction required.

## U8 Citation Graph — Cross-Review Follow-up

- Date: 2026-06-22
- Branch: `feature/u8-v1` (branch-name CI prefix compliant)
- Code changes:
  - removed dead `depth` query from citation tree API and cache key
  - kept lazy 2-hop controlled by `expandNodeId`
  - nulls out-of-range library save year values before U4 validation
  - guards telemetry against observability objects without `emit_log`
  - keeps `depthRequested` distinct from `depthReturned`
- Documentation changes:
  - corrected Redis wording: current implementation is process-local in-memory TTL seam; Redis remains production adapter target
- Current gate: user review/approval, commit, or PR direction required.

## U9 Personalization — Requirements Questions Created

- Date: 2026-06-23
- Candidate unit: U9 Personalization / Behavior Intelligence
- Trigger: 사용자 행동 로그를 기록하고 분석해 개인화 맞춤 서비스를 제공하는 기능.
- Created artifact:
  - `aidlc-docs/inception/requirements/requirement-verification-questions-u9-personalization.md`
- Completed: questions Q1~Q20 set to recommended answers (Q13=B, all others A).
- Requirements updated:
  - `aidlc-docs/inception/requirements/requirements.md`
  - Added FR-18 behavior event logging, FR-19 user interest profile, FR-20 personalization application, NFR-P4, QT-7, U9 scope exclusions, traceability.
- Current gate: Requirements review/approval. Next recommended stage: User Stories revision for U9.
- Code generated: no.

## U9 Personalization — User Stories Plan Ready

- Date: 2026-06-23
- Stage: INCEPTION / User Stories Part 1
- Assessment completed:
  - `aidlc-docs/inception/plans/u9-personalization-user-stories-assessment.md`
- Plan created:
  - `aidlc-docs/inception/plans/u9-personalization-story-generation-plan.md`
- Decision: execute User Stories for U9 because the change is user-facing, touches behavior data/privacy controls, and affects search/summary/translation workflows.
- Completed: Story generation plan questions PQ1~PQ6 set to recommended answer A.
- Generated artifacts:
  - `aidlc-docs/inception/user-stories/stories.md`
  - `aidlc-docs/inception/user-stories/personas.md`
- Story update: added Epic 8 Personalization / Behavior Intelligence with US-P1..US-P7; updated persona map and FR/NFR/QT traceability.
- Current gate: User Stories review/approval. Next recommended stage: Units Generation revision for U9.
- Code generated: no.

## U9 Personalization — Units Generation Plan Ready

- Date: 2026-06-23
- Stage: INCEPTION / Units Generation Part 1
- Plan created:
  - `aidlc-docs/inception/plans/u9-personalization-unit-of-work-plan.md`
- Recommended decomposition: add U9 as `backend/modules/personalization/` in the existing API deployment; keep US-P1..P6 Owner=U9 and US-P7 Owner=U6 with U9 as signal source.
- Completed: Unit decomposition questions UQ1~UQ5 set to recommended answer A.
- Updated artifacts:
  - `aidlc-docs/inception/application-design/unit-of-work.md`
  - `aidlc-docs/inception/application-design/unit-of-work-dependency.md`
  - `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- Unit update: added U9 Personalization as an API module at `backend/modules/personalization/`; story map now covers 40 stories with unassigned=0.
- Current gate: Units Generation review/approval. Next recommended stage: U9 Construction Functional Design.
- Code generated: no.

## U9 Personalization — Functional Design Plan Ready

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 Functional Design Part 1
- Plan created:
  - `aidlc-docs/construction/plans/u9-personalization-functional-design-plan.md`
- Decision: execute Functional Design because U9 introduces behavior event entities, interest profile aggregation rules, user controls, and non-blocking personalization failure rules.
- Completed: Functional Design questions Q1~Q12 set to recommended answer A.
- Generated artifacts:
  - `aidlc-docs/construction/u9-personalization/functional-design/domain-entities.md`
  - `aidlc-docs/construction/u9-personalization/functional-design/business-logic-model.md`
  - `aidlc-docs/construction/u9-personalization/functional-design/business-rules.md`
- Design summary: defined BehaviorEvent envelope, 7 event types, owner-scoped UserInterestProfile, bounded personalization decisions, user controls, fail-open default behavior, and QT-7 property candidates.
- Current gate: Functional Design review/approval. Next recommended stage: U9 NFR Requirements.
- Code generated: no.

## U9 Personalization — NFR Requirements Plan Ready

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 NFR Requirements Part 1
- Plan created:
  - `aidlc-docs/construction/plans/u9-personalization-nfr-requirements-plan.md`
- Decision: execute NFR Requirements because U9 stores user behavior data and must define persistence, privacy, latency, degradation, observability, and QT-7 test boundaries.
- Completed: Q1~Q12 set to recommended answer A after plan_feedback.md correction; Q7 now uses direct active-table delete with no backup table.
- Generated artifacts:
  - `aidlc-docs/construction/u9-personalization/nfr-requirements/nfr-requirements.md`
  - `aidlc-docs/construction/u9-personalization/nfr-requirements/tech-stack-decisions.md`
- NFR summary: existing RDS/backend/U6 reuse, best-effort non-blocking recording, lazy/on-demand aggregation, allowlisted metadata, direct active-table delete with no backup table, scheduled purge requirement, U6 observability, Hypothesis QT-7 tests.
- Current gate: NFR Requirements review/approval. Next recommended stage: U9 NFR Design.
- Code generated: no.

## U9 Personalization — NFR Design Plan Ready

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 NFR Design Part 1
- Plan created:
  - `aidlc-docs/construction/plans/u9-personalization-nfr-design-plan.md`
- Decision: execute NFR Design because U9 needs concrete fail-open, lazy aggregation, active repository, direct delete, retention cleanup, metadata validation, and U6 observability patterns.
- Completed: NFR Design questions Q1~Q5 set to recommended answer A.
- Generated artifacts:
  - `aidlc-docs/construction/u9-personalization/nfr-design/logical-components.md`
  - `aidlc-docs/construction/u9-personalization/nfr-design/nfr-design-patterns.md`
- Design summary: fail-open personalization, bounded profile read, read-through lazy aggregation, direct active-table delete, scheduled idempotent retention cleanup, recorder-level metadata allowlist, and U6 operational telemetry.
- Current gate: NFR Design review/approval. Next recommended stage: U9 Infrastructure Design assessment.
- Code generated: no.

## U9 Personalization — Infrastructure Design Plan Ready

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 Infrastructure Design Part 1
- Plan created:
  - `aidlc-docs/construction/plans/u9-personalization-infrastructure-design-plan.md`
- Decision: execute Infrastructure Design because U9 adds RDS tables, deletion/retention cleanup, API deployment mapping, scheduled maintenance task mapping, and U6 observability integration.
- Recommended direction: reuse existing backend ECS/API deployment, RDS PostgreSQL, U6 gateway/observability, and CloudWatch; avoid a new service, queue, cache, analytics lake, or ML pipeline for v1.
- Current gate: U9 Infrastructure Design questions Q1~Q6 awaiting answers.
- Code generated: no.

## U9 Personalization — Infrastructure Design Complete / Code Generation Plan Next

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 Infrastructure Design
- Feedback applied:
  - `plan_feedback.md`
- Corrected prior design:
  - Removed U9 backup table for raw behavior log deletion.
  - User raw-log deletion now directly deletes owner-scoped active rows.
  - Retention cleanup is an idempotent daily EventBridge scheduled ECS task.
  - Retention purge failure must emit U6 telemetry and trigger alerting.
- Completed: Infrastructure Design questions Q1~Q6 resolved to the revised recommended path.
- Generated artifacts:
  - `aidlc-docs/construction/u9-personalization/infrastructure-design/infrastructure-design.md`
  - `aidlc-docs/construction/u9-personalization/infrastructure-design/deployment-architecture.md`
- Current gate: Infrastructure Design review/approval. Next recommended stage: U9 Code Generation planning.
- Code generated: no.

## U9 Personalization — Code Generation Plan Ready

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 Code Generation Part 1
- Infrastructure Design approval:
  - User requested progress up to just before code generation.
- Plan created:
  - `aidlc-docs/construction/plans/u9-personalization-code-generation-plan.md`
- Planned scope:
  - backend-only U9 module, RDS migrations, app-shell wiring, idempotent retention cleanup command, scheduled ECS cleanup infrastructure, tests, and code summary docs.
- Guardrails:
  - No frontend UI, no queue, no new always-on service, no analytics lake, no ML pipeline, and no `user_behavior_event_backup` table.
- Current gate: Code Generation plan approval. Actual app code has not been generated.
- Code generated: no.

## U9 Personalization — Code Generation Complete

- Date: 2026-06-23
- Stage: CONSTRUCTION / U9 Code Generation
- Completed plan:
  - `aidlc-docs/construction/plans/u9-personalization-code-generation-plan.md`
- Created application code:
  - `backend/modules/personalization/`
  - `backend/modules/personalization/migrations/001_create_personalization_tables.sql`
  - `backend/tests/test_personalization.py`
- Modified application/infrastructure code:
  - `backend/app.py`
  - `backend/migrations/__main__.py`
  - `backend/wiring.py`
  - `backend/tests/test_app_shell.py`
  - `ops/cdk/stacks/compute_stack.py`
- Code summary:
  - `aidlc-docs/construction/u9-personalization/code/summary.md`
- Verification:
  - `python -m pytest backend/tests/test_personalization.py -q` -> 11 passed
  - `python -m ruff check backend/modules/personalization backend/wiring.py backend/app.py backend/migrations/__main__.py backend/tests/test_personalization.py backend/tests/test_app_shell.py ops/cdk/stacks/compute_stack.py` -> pass
  - `python -m compileall backend/modules/personalization backend/wiring.py backend/app.py ops/cdk/stacks/compute_stack.py` -> pass
  - Combined `backend/tests/test_personalization.py backend/tests/test_app_shell.py` attempted but local shell lacks existing `docsuri_shared`, `discovery`, and `docsuri_ops` imports required by pre-existing app-shell assertions.
- Current gate: Code Generation review/approval. Next recommended stage: Build and Test after approval.
- Code generated: yes.

## U9 Personalization — Build and Test Complete

- Date: 2026-06-23
- Stage: CONSTRUCTION / Build and Test
- Build/test documents updated:
  - `aidlc-docs/construction/build-and-test/build-instructions.md`
  - `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/performance-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/contract-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/security-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/build-and-test-summary.md`
- Verification:
  - `python -m pytest backend/tests/test_personalization.py -q` -> 11 passed
  - `$env:PYTHONPATH='shared/python/src;ops/src;backend/modules/discovery/src'; python -m pytest backend/tests/test_personalization.py backend/tests/test_app_shell.py -q` -> 25 passed
  - `$env:PYTHONPATH='shared/python/src;ops/src;backend/modules/discovery/src'; python -m pytest backend/tests -q` -> 57 passed, 1 skipped
  - `python -m ruff check backend/modules/personalization backend/wiring.py backend/app.py backend/migrations/__main__.py backend/tests/test_personalization.py backend/tests/test_app_shell.py ops/cdk/stacks/compute_stack.py` -> pass
  - `python -m compileall backend/modules/personalization backend/wiring.py backend/app.py ops/cdk/stacks/compute_stack.py` -> pass
  - `python -m pip install -r ops/cdk/requirements.txt` -> pass
  - `$env:JSII_NODE="$env:USERPROFILE\scoop\apps\nodejs-lts\current\node.exe"; cdk synth` from `ops/cdk` -> pass, synthesized to `ops/cdk/cdk.out`
- Current gate: Build and Test review/approval. Next stage per AI-DLC is Operations placeholder.

## Agent Chat Frontend — Code Generation Complete

- Date: 2026-07-01
- Stage: CONSTRUCTION / Code Generation
- Branch: `docs/novelty-agent-fe`
- Inputs:
  - `aidlc-docs/inception/requirements/requirement-verification-questions-agent-chat-frontend.md`
  - `requirement-question-answer.md`
  - `aidlc-docs/inception/plans/agent-chat-frontend-story-generation-plan.md`
- Story planning answers:
  - Q1=A, Q2=A, Q3=A, Q4=A, Q5=A.
- Requirements covered:
  - FR-40, FR-41, FR-42, FR-43, NFR-P7, QT-11.
- User stories updated:
  - `aidlc-docs/inception/user-stories/stories.md`
  - Added Epic 11 with US-AG1..US-AG7.
  - Updated persona/story and FR/story coverage maps.
- Workflow plan created:
  - `aidlc-docs/inception/plans/agent-chat-frontend-workflow-plan.md`
- Next question file:
  - `aidlc-docs/construction/plans/agent-chat-frontend-code-generation-plan.md`
- Application Design answers:
  - Q1=A, Q2=A, Q3=A, Q4=A, Q5=A.
- Application Design artifacts:
  - `aidlc-docs/inception/application-design/agent-chat-frontend-components.md`
  - `aidlc-docs/inception/application-design/agent-chat-frontend-component-methods.md`
  - `aidlc-docs/inception/application-design/agent-chat-frontend-services.md`
  - `aidlc-docs/inception/application-design/agent-chat-frontend-component-dependency.md`
  - `aidlc-docs/inception/application-design/application-design.md`
- Functional Design answers:
  - Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A.
- Functional Design artifacts:
  - `aidlc-docs/construction/agent-chat-frontend/functional-design/domain-entities.md`
  - `aidlc-docs/construction/agent-chat-frontend/functional-design/business-logic-model.md`
  - `aidlc-docs/construction/agent-chat-frontend/functional-design/business-rules.md`
  - `aidlc-docs/construction/agent-chat-frontend/functional-design/frontend-components.md`
- NFR Requirements answers:
  - Q1=A, Q2=A, Q3=A, Q4=A, Q5=A.
- NFR Requirements artifacts:
  - `aidlc-docs/construction/agent-chat-frontend/nfr-requirements/nfr-requirements.md`
  - `aidlc-docs/construction/agent-chat-frontend/nfr-requirements/tech-stack-decisions.md`
- NFR Design answers:
  - Q1=A, Q2=A, Q3=A, Q4=A, Q5=`X) A + E2E 테스트`.
- NFR Design artifacts:
  - `aidlc-docs/construction/agent-chat-frontend/nfr-design/nfr-design-patterns.md`
  - `aidlc-docs/construction/agent-chat-frontend/nfr-design/logical-components.md`
- Infrastructure Design:
  - Skipped. U13 reuses existing frontend deployment and adds no new infrastructure.
- Completed plan:
  - `aidlc-docs/construction/plans/agent-chat-frontend-code-generation-plan.md`
- Created application code:
  - `frontend/app/agent/page.tsx`
  - `frontend/app/agent/agent.module.css`
  - `frontend/components/agent/AgentChatScreen.tsx`
  - `frontend/components/agent/AgentChatScreen.module.css`
  - `frontend/lib/agentChat/types.ts`
  - `frontend/lib/agentChat/state.ts`
  - `frontend/mocks/agentFixtures.ts`
- Modified application code:
  - `frontend/components/AppHeader.tsx`
  - `frontend/components/BottomNav.tsx`
  - `frontend/lib/api/apiClient.ts`
  - `frontend/lib/api/mockTransport.ts`
  - `frontend/playwright.config.ts`
- Tests and summary:
  - `frontend/test/agentChatReducer.test.ts`
  - `frontend/test/agentChatScreen.test.tsx`
  - `frontend/e2e/agent-chat.spec.ts`
  - `aidlc-docs/construction/agent-chat-frontend/code/summary.md`
- Verification:
  - `corepack pnpm@9.15.9 --dir frontend exec -- tsc --noEmit` -> passed
  - `corepack pnpm@9.15.9 --dir frontend run test -- test/agentChatReducer.test.ts test/agentChatScreen.test.tsx` -> passed; Vitest executed the current frontend suite, 41 files / 175 tests passed
  - `corepack pnpm@9.15.9 --dir frontend build` -> passed; `/agent` included in route output
  - `corepack pnpm@9.15.9 --dir frontend exec playwright test e2e/agent-chat.spec.ts` -> attempted; blocked because local Playwright WebKit binary is not installed
- Scope boundary:
  - v1 frontend uses `/agent` single route, existing responsive + phone preview structure, and a mock/real transport seam.
  - No new backend API or infrastructure code is generated in this stage.
- Current gate: Code Generation review/approval. Next recommended stage: Build and Test after approval.
- Code generated: yes.

## Agent Chat Frontend — Build and Test Complete

- Date: 2026-07-01
- Stage: CONSTRUCTION / Build and Test
- Code Generation approval:
  - User approved: "좋아요. 이제 빌드와 테스트를 진행해 주세요."
- Build/test documents updated:
  - `aidlc-docs/construction/build-and-test/build-instructions.md`
  - `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/performance-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/contract-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/security-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/e2e-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/build-and-test-summary.md`
- Verification:
  - `corepack pnpm@9.15.9 --dir frontend exec -- tsc --noEmit` -> passed
  - `corepack pnpm@9.15.9 --dir frontend exec -- vitest run test/agentChatReducer.test.ts test/agentChatScreen.test.tsx --reporter=dot` -> 2 files passed, 9 tests passed
  - `corepack pnpm@9.15.9 --dir frontend build` -> passed; `/agent` route included
  - `corepack pnpm@9.15.9 --dir frontend exec -- playwright install webkit` -> passed
  - `corepack pnpm@9.15.9 --dir frontend exec -- playwright test e2e/agent-chat.spec.ts --reporter=line` -> 1 passed
  - `git diff --check` -> passed; line-ending warnings only
- E2E adjustment:
  - Agent Chat E2E now injects the mock session directly and starts from `/agent`, because auth form coverage belongs to existing auth E2E tests.
  - Playwright webServer now copies static assets into `.next/standalone` and runs the standalone server for local E2E hydration after `next build`.
- Current gate: Build and Test review/approval. Next stage per AI-DLC is Operations placeholder.

## Research Agent — Requirements Registered

- Date: 2026-06-24
- Candidate unit: Research Agent (대화형 문헌탐색·근거형성 / 아이디어 novelty); 유닛 번호 미배정 (마이페이지 U10·개인화추천·트렌드/알림·구독제 이후)
- Trigger: 네비바 검색↔마이페이지 사이의 대화형 연구 보조 — 여러 논문 교차확인 근거 정리(모드 A) + 내 주제 기존성 유사논문 비교(모드 B). 설계 입력 `summarization-translation-pipeline.md` line 374.
- Branch / PR: `feature/research-agent` / PR #170 (base develop)
- Created artifact:
  - `aidlc-docs/inception/requirements/requirement-verification-questions-research-agent.md` (인셉션 고도 18문항; 1차 답변 기록)
- Answers: Q5=B(커버리지 확장)·Q7=A(재현성 판정 제외)·Q13=X(전용 네비 메뉴+세션 리스트)·Q14=B(무기한 보관)·Q18=A(Requirements까지만), 나머지 권장.
- Requirements updated:
  - `aidlc-docs/inception/requirements/requirements.md`
  - Added FR-22 (대화형 근거형성, 모드 A, v1), FR-23 (novelty 비교, 모드 B, 다음 사이클), FR-24 (대화형 입력+첨부), FR-25 (결과·세션 영속+전용 진입), NFR-P5, NFR-C1 Agent 보강, QT-8, §12 Agent 카브아웃, C-2 경계, 성공기준 #7, traceability 9 rows.
- Scope boundary: v1 = 모드 A 구현; novelty(모드 B)는 다음 사이클(Q4=A). 생성 산문·재현성 판정 제외(C-2). HOW(코퍼스 확장·외부 API·출력 스키마·근거표 컬럼·모델·멀티턴·네비/세션 UI)는 Construction 라운드로 이월.
- Current gate: Requirements review/approval (PR #170). Next stage (별도 승인): User Stories → Units Generation → Construction.
- Code generated: no.

## Novelty Agent — Infrastructure Design Complete / Code Generation Plan Ready

- Date: 2026-06-29
- Stage: CONSTRUCTION / Infrastructure Design + Code Generation plan gate
- Trigger: 차별화(novelty) 형성 Agent 구현을 위한 AI-DLC 질문지 답변 반영 및 다음 단계 진행.
- Branch: `docs/novelty-agent-questionnaire`
- Inputs:
  - `aidlc-docs/inception/requirements/requirement-verification-questions-novelty-agent.md`
  - `requirement-verification-questions-answer-1.md`
  - `FD-Answer-1.md`
  - `nfr-answer.md`
  - `nfr-design-review.md`
  - `infradesign-answer.md`
  - `aidlc-docs/construction/shared/evidence-formation-port.md`
- Answers reflected:
  - Q1~Q7=A, Q8=B(뉴스 검색 v1 제외), Q9~Q28=A, Q29=C, Q30=A, Q31=A, Q32=B.
  - Functional Design Q1~Q16=A.
  - `EvidenceItem.conflicting`/`confidence`는 PROVISIONAL optional 필드로 모델링한다.
  - DOCX는 신규 파서 의존성이 필요하므로 v1에서 제외하고 차기 사이클 후보로 둔다.
- Requirements updated:
  - `aidlc-docs/inception/requirements/requirements.md`
  - Added FR-30..35, NFR-P5, NFR-R3, QT-10, novelty Agent §12 carve-out, success criterion #9, traceability row.
- User stories updated:
  - `aidlc-docs/inception/user-stories/stories.md`
  - Added Epic 9 with US-NV1..US-NV9.
  - Updated persona/story and FR/story coverage maps.
  - `aidlc-docs/inception/user-stories/personas.md` updated for P1/P2/OP novelty goals and ops responsibility.
- Plans created:
  - `aidlc-docs/inception/plans/novelty-agent-user-stories-assessment.md`
  - `aidlc-docs/inception/plans/novelty-agent-story-generation-plan.md`
  - `aidlc-docs/construction/plans/novelty-agent-functional-design-plan.md` (Functional Design 질문 16개, 답변 반영 완료)
- Functional Design artifacts generated:
  - `aidlc-docs/construction/novelty-agent/functional-design/domain-entities.md`
  - `aidlc-docs/construction/novelty-agent/functional-design/business-logic-model.md`
  - `aidlc-docs/construction/novelty-agent/functional-design/business-rules.md`
  - `aidlc-docs/construction/novelty-agent/functional-design/frontend-components.md`
- NFR Requirements plan created:
  - `aidlc-docs/construction/plans/novelty-agent-nfr-requirements-plan.md` (NFR Requirements 질문 14개, 답변 반영 완료; Q4=B, 나머지 A)
- NFR Requirements artifacts generated:
  - `aidlc-docs/construction/novelty-agent/nfr-requirements/nfr-requirements.md`
  - `aidlc-docs/construction/novelty-agent/nfr-requirements/tech-stack-decisions.md`
- NFR Design plan created:
  - `aidlc-docs/construction/plans/novelty-agent-nfr-design-plan.md` (NFR Design 질문 10개, 답변 반영 완료; 전부 A, Q3는 Last-Event-ID replay 제외)
- NFR Design artifacts generated:
  - `aidlc-docs/construction/novelty-agent/nfr-design/nfr-design-patterns.md`
  - `aidlc-docs/construction/novelty-agent/nfr-design/logical-components.md`
- Infrastructure Design plan created:
  - `aidlc-docs/construction/plans/novelty-agent-infrastructure-design-plan.md` (Infrastructure Design 질문 10개, 답변 반영 완료; 전부 A)
- Infrastructure Design artifacts generated:
  - `aidlc-docs/construction/novelty-agent/infrastructure-design/infrastructure-design.md`
  - `aidlc-docs/construction/novelty-agent/infrastructure-design/deployment-architecture.md`
- Code Generation plan created:
  - `aidlc-docs/construction/plans/novelty-agent-code-generation-plan.md` (승인 질문 답변 대기)
- Scope boundary:
  - novelty Agent consumes EvidenceFormationPort/SourceRef; it does not implement literature/evidence formation internals.
  - v1 external search = GitHub + datasets; news search is next cycle.
  - v1 backend manuscript analysis = Markdown/TXT object refs only; PDF/DOCX parser support is next cycle.
  - No novelty score, "newness proven" judgment, paper prose generation, or code skeleton generation.
- Current gate: `novelty-agent-code-generation-plan.md` 승인 질문 답변 대기.
- Code generated: no.

## Novelty Agent — Code Generation Complete

- Date: 2026-06-30
- Stage: CONSTRUCTION / Code Generation
- Completed plan:
  - `aidlc-docs/construction/plans/novelty-agent-code-generation-plan.md`
- Created application code:
  - `backend/modules/novelty/`
  - `backend/modules/novelty/migrations/001_create_novelty_tables.sql`
  - `backend/tests/test_novelty.py`
- Modified application/infrastructure code:
  - `backend/app.py`
  - `backend/migrations/__main__.py`
  - `backend/wiring.py`
  - `backend/tests/test_app_shell.py`
  - `ops/cdk/app.py`
  - `ops/cdk/stacks/compute_stack.py`
  - `ops/cdk/stacks/novelty_stack.py`
- Code summary:
  - `aidlc-docs/construction/novelty-agent/code/summary.md`
- Verification:
  - `python -m pytest backend/tests/test_novelty.py -q` -> 10 passed
  - `python -m ruff check backend/modules/novelty backend/wiring.py backend/app.py backend/migrations/__main__.py backend/tests/test_novelty.py backend/tests/test_app_shell.py ops/cdk/stacks/novelty_stack.py ops/cdk/stacks/compute_stack.py ops/cdk/app.py` -> passed
  - `python -m compileall backend/modules/novelty backend/wiring.py ops/cdk/stacks/novelty_stack.py ops/cdk/app.py` -> passed
  - `cd ops/cdk; cdk synth` -> passed with existing CDK warnings
  - Combined `backend/tests/test_novelty.py backend/tests/test_app_shell.py` attempted but the local shell lacks existing `docsuri_shared`, `docsuri_ops`, and discovery imports required by pre-existing app-shell assertions.
- Current gate: Code Generation review/approval. Next recommended stage: Build and Test after approval.
- Code generated: yes.

## Novelty Agent — Build and Test Complete

- Date: 2026-06-30
- Stage: CONSTRUCTION / Build and Test
- Code Generation approval:
  - User approved: "`Approve code generation and proceed to Build & Test`를 진행해 주세요."
- Build/test documents updated:
  - `aidlc-docs/construction/build-and-test/build-instructions.md`
  - `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/performance-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/contract-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/security-test-instructions.md`
  - `aidlc-docs/construction/build-and-test/build-and-test-summary.md`
- Verification:
  - `python -m pytest backend/tests/test_novelty.py -q` -> 10 passed
  - `$env:PYTHONPATH='shared/python/src;ops/src;backend/modules/discovery/src;backend/modules/summarization/src'; python -m pytest backend/tests/test_novelty.py backend/tests/test_app_shell.py -q` -> 24 passed
  - `$env:PYTHONPATH='shared/python/src;ops/src;backend/modules/discovery/src;backend/modules/summarization/src'; python -m pytest backend/tests -q` -> passed with 1 skipped test after installing declared `pytest-asyncio` dependency
  - `python -m ruff check backend/modules/novelty backend/wiring.py backend/app.py backend/migrations/__main__.py backend/tests/test_novelty.py backend/tests/test_app_shell.py ops/cdk/stacks/novelty_stack.py ops/cdk/stacks/compute_stack.py ops/cdk/app.py` -> passed
  - `python -m compileall backend/modules/novelty backend/wiring.py backend/app.py ops/cdk/stacks/novelty_stack.py ops/cdk/stacks/compute_stack.py ops/cdk/app.py` -> passed
  - `cd ops/cdk; cdk synth` -> passed with existing CDK warnings
- Current gate: Build and Test review/approval. Next stage per AI-DLC is Operations placeholder.

## Evidence Formation Agent (U11) — Code Generation Complete

- Date: 2026-07-01
- Stage: CONSTRUCTION / Code Generation
- Branch: `feature/u11-evidence-agent-construction`
- Created application code:
  - `backend/modules/evidence/tools.py`
  - `backend/modules/evidence/prompts.py`
  - `backend/modules/evidence/extractor.py`
  - `backend/modules/evidence/assembler.py`
  - `backend/modules/evidence/orchestrator.py`
  - `backend/modules/evidence/repository.py`
  - `backend/modules/evidence/service.py`
  - `backend/modules/evidence/controller.py`
  - `backend/modules/evidence/settings.py`
  - `backend/modules/evidence/real_wiring.py`
  - `backend/modules/evidence/migrations/001_create_evidence_tables.sql`
  - `backend/tests/test_evidence.py`
- Modified application code:
  - `backend/wiring.py` (`_mount_evidence` 추가, `_INTEGRATIONS` 등재)
  - `backend/migrations/__main__.py` (evidence migration 경로 등재)
- Verification:
  - `./backend/.venv/bin/ruff check backend/modules/evidence/ backend/tests/test_evidence.py` -> passed (0 errors)
  - `PYTHONPATH='shared/python/src:ops/src:backend/modules/discovery/src:backend/modules/summarization/src' ./backend/.venv/bin/pytest backend/tests/test_evidence.py -v` -> 12 passed
- Key invariants enforced:
  - INV-EV-1: session ownership (wrong owner → KeyError → 404, SEC-9)
  - INV-EV-2: empty claims → TurnAbstainResult (not TurnSuccessResult)
  - INV-EV-3: no hallucination — quote must appear in paper fullText
  - INV-EV-5: internal fields (score, chunk_id, vector, llm_meta) excluded from all API responses
  - BR-EV-2/7/8/9/10/12 모두 구현
  - D5: EvidenceFormationPort — asyncio.to_thread으로 sync Orchestrator 연결
- Current gate: Code Generation review/approval. Next recommended stage: Build and Test after approval.

## Evidence Formation Agent (U11) — Build and Test Complete

- Date: 2026-07-01
- Stage: CONSTRUCTION / Build and Test
- Code Generation approval: 사용자 "Build & Test 단계 진행해" 요청으로 진행
- Branch: `feature/u11-evidence-agent-construction`
- Build/test documents updated:
  - `aidlc-docs/construction/build-and-test/build-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/unit-test-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/integration-test-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/performance-test-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/contract-test-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/security-test-instructions.md` (U11 Evidence 섹션 추가)
  - `aidlc-docs/construction/build-and-test/build-and-test-summary.md` (U11 Evidence 섹션 추가)
- Application code fix:
  - `backend/wiring.py`: 미사용 `EvidenceAgentOrchestrator` import 제거 (ruff F401)
  - `backend/tests/test_app_shell.py`: expected module set에 `"evidence"` 추가
- Verification:
  - `./backend/.venv/bin/python -m compileall backend/modules/evidence/ backend/wiring.py backend/migrations/__main__.py` → PASS
  - `./backend/.venv/bin/ruff check backend/modules/evidence/ backend/wiring.py backend/migrations/__main__.py backend/tests/test_evidence.py backend/tests/test_app_shell.py` → PASS (0 errors)
  - `PYTHONPATH='...' ./backend/.venv/bin/pytest backend/tests/test_evidence.py -v` → **12 passed**
  - `PYTHONPATH='...' ./backend/.venv/bin/pytest backend/tests/ --ignore=backend/tests/test_mypage.py` → **93 passed**, 1 failed (pre-existing: `cryptography` absent on macOS), 1 skipped
- Environment note: `test_discovery_and_accounts_actually_mount` 1건 실패는 macOS 환경에 `cryptography` 패키지 미설치로 accounts/mypage가 스킵되는 기존 환경 제약 — U11 변경과 무관
- Current gate: Build and Test review/approval. Next stage per AI-DLC is Operations placeholder.

## Evidence Formation Agent (U11) — AgentWorker + CDK Stack 추가

- Date: 2026-07-01
- Stage: CONSTRUCTION / Code Generation (보완)
- Branch: `feature/u11-evidence-agent-construction`
- Created:
  - `backend/modules/evidence/worker.py` — SQS polling AgentWorker (BR-EV-6)
  - `ops/cdk/stacks/evidence_stack.py` — SQS + ECS Fargate CDK stack
- Modified:
  - `backend/modules/evidence/repository.py` — `update_turn_result` 추가 (Protocol + InMemory + SQL)
  - `backend/modules/evidence/service.py` — `sqs_enqueue` 콜백 주입 + async path(BR-EV-6)
  - `backend/modules/evidence/controller.py` — `get_sqs_enqueue` 의존성 + POST /turns 주입
  - `backend/wiring.py` — `_mount_evidence`에 sqs_enqueue boto3 콜백 연결
  - `ops/cdk/app.py` — EvidenceStack 등록
- Verification:
  - `./backend/.venv/bin/ruff check backend/modules/evidence/ backend/wiring.py ops/cdk/stacks/evidence_stack.py ops/cdk/app.py` → PASS
  - `./backend/.venv/bin/python -m compileall backend/modules/evidence/ backend/wiring.py ops/cdk/stacks/evidence_stack.py ops/cdk/app.py` → PASS
  - `PYTHONPATH='...' ./backend/.venv/bin/pytest backend/tests/test_evidence.py backend/tests/test_app_shell.py -v` → 26 passed, 1 failed (pre-existing cryptography 환경 제약)
- Construction 완료: Code Generation 전 범위(코어 모듈 + AgentWorker + CDK IaC) 모두 작성됨

## U9 Personalization — Search-Boost Application (Shadow) Increment

- Date: 2026-07-01
- Stage: CONSTRUCTION / U9 Code Generation (follow-on increment)
- Trigger: audit found the U9 decision path inert — `/decision/search` + `/decision/summary-defaults` had zero consumers and zero prod calls in 7d (CloudWatch `DocSuri/Production`), while collection was healthy (944 events/7d, 0 failures). Decision: build the deferred **application** path for US-P4 (search boost), **shadow-first** (measure, don't reorder).
- Design delta (folded here, no new FD round — US-P4/FR-20/BR-P8/BR-P9 already exist):
  - BR-P8 boost contract enforced at the read port (each ∈ [-0.1,+0.1], Σ≤0.2).
  - Relative (multiplicative) boost over the top-30% band only — nudge, never flip.
  - Cross-unit seam: plain injected `search_boosts` callable (no new `shared/ports` Protocol — one consumer), cached-profile-only in the search path, fail-open (BR-P13).
- Files:
  - `backend/modules/personalization/service.py` (BR-P8 clamp `_to_search_boosts`)
  - `backend/modules/discovery/src/discovery/domain/ranker.py` (pure `shadow_rerank_diff` + `ShadowDiff`)
  - `backend/modules/discovery/src/discovery/service/orchestrator.py` (`_emit_rerank_shadow`, injected `search_boosts`)
  - `backend/wiring.py` (in-process U9 read-port provider, `PERSONALIZATION_ENABLED`-gated)
  - `backend/tests/test_personalization.py`, `backend/modules/discovery/tests/test_ranker_pbt.py`
- Code summary: `aidlc-docs/construction/u9-personalization/code/summary.md` (§ Search-Boost Application — Shadow Mode)
- Metrics: `personalization.rerank_shadow` (positions changed), `personalization.rerank_shadow.max_shift`, `personalization.rerank_shadow.boosted_count` (dim `scope=search`).
- Verification (backend `.venv`, py3.13):
  - `pytest test_personalization.py test_ranker_pbt.py test_orchestrator.py -q` -> 25 passed
  - `pytest backend/modules/discovery/tests -q` -> passed (3 pre-existing skips)
  - `pytest backend/tests -q` -> passed (1 pre-existing skip); `test_app_shell.py` -> passed
  - `ruff check` on the 6 changed files -> All checks passed
- Rollout: SHADOW — user-visible ranking unchanged. Go-live = return `shadow_rerank_diff`'s `reordered` (one line) after observing the metric.
- Deferred: summary/translation defaults (US-P5), `keywordWeights` surfacing.
- Delivery: PR #300 (`feature/u9-search-boost-shadow` → develop).
- Review remediation (2026-07-01): fixed BR-P8 post-normalization total-budget drift, changed U2 shadow reads to cached-profile-only `cached_search_boosts` with PostgreSQL `statement_timeout`, added max-shift/boosted-count shadow metrics, and added regressions for the counterexamples.
- Remediation verification: focused personalization/discovery tests passed; app-shell/orchestrator tests passed; backend+discovery sweep passed with the existing skip; touched-file Ruff passed; `git diff --check` passed; `git merge-tree origin/develop HEAD` produced a clean merge tree.
- Current gate: PR review/approval.

## U7 Summarization — Personal-Glossary Redesign + Map Parallelism Increment

- Date: 2026-07-02
- Stage: CONSTRUCTION / U7 Code Generation (follow-on increment)
- Trigger: translate keyed on the full per-user `glossary_ver` counter + owner scoping, but today every personal term is post-substitution (weak) — the LLM base translation is identical across users/versions. So a weak-term edit forced a full re-translation and each user got a duplicate copy (wasted LLM spend + storage, NFR-C1). Seed-glossary edits also served stale cache (seed not in the key).
- Design delta (folded here, no new FD round — BR-S1/S4/S6/S18 already exist):
  - **Shared base + read-time overlay (BR-S4/NFR-C1)**: translate now keys on the prompt-enforced content signature (like summary); `assemble_translation` stores the shared **base** (no weak post-substitution); `overlay_translation` applies the user's weak terms on read (HIT + fresh). Weak-only edits/distinct weak sets de-dup to one shared base — instant, free, cross-user.
  - **Seed cache-invalidation (BR-S1)**: `seedVer` = content hash of the seed glossary, appended to the cache path only when it diverges from the shipped baseline (`_SEED_BASELINE_VER`, frozen `344c3ccb`) → seed edits self-invalidate, no manual PROMPT_VER bump; unchanged-seed deploys keep existing cache valid.
  - **Concurrent map (BR-S6/S18)**: shared `map_bounded` (bounded, order-preserving, fail-fast) runs the translate map-only chunks and the summary map phase concurrently — latency down, byte-identical result, cost-neutral. Reduce stays sequential. Worker caps: translate 4, summary 3 (Bedrock TPM).
  - **Dead code removed**: `GlossaryResolver.glossary_version` + `GlossaryRepositoryPort.get_glossary_version` + RDS impl (no longer a cache-key input; the `glossary_ver` column stays, bumped on upsert and returned to the badge editor).
- Files:
  - `backend/modules/summarization/src/summarization/domain/parallel.py` (new — `map_bounded`)
  - `domain/structured_translator.py`, `domain/map_reduce.py` (concurrent map + `max_workers`)
  - `domain/glossary.py` (`signature_of`, `SEED_VER`/`seed_cache_segment`, dropped `glossary_version`)
  - `domain/models.py` (`SummaryCacheKey.seed_ver` + path), `domain/cache_key.py` (`seed_ver` param, both tasks → signature)
  - `service/orchestrator.py` (resolve once, signature key both tasks, HIT/fresh overlay, `_PayloadResult`)
  - `domain/assembler.py` (`assemble_translation` base-only + `overlay_translation`)
  - `ports/ports.py`, `adapters/rds_glossary.py` (dead method removed, docstring back-sync)
  - Tests: `tests/test_glossary_overlay_cache.py`, `tests/test_parallel.py` (new); updated `tests/test_domain_glossary.py`, `tests/test_glossary_upsert.py`, `tests/stubs.py`
- Verification (module `.venv`): `pytest -q` → 174 passed, 3 skipped; `ruff check src/ tests/` → All checks passed.
- SSOT back-sync: BR-S1/S4/S6/S18 (business-rules), infrastructure-design §2.1, business-logic-model §3.1/3.5/3.7/3.9, nfr-design (NFR-C1).
- Quality note today: zero user-created prompt-enforced (strong) terms exist, so signature=0 for all → one shared `_g0` base per paper; the strong-term path forks base + owner-scopes when a future UI/API opens strong-term creation (separate track).
- Delivery: branch `feat/u7-glossary-overlay-and-map-parallelism` → develop. Current gate: local commit; push/PR pending user approval.

## Monitoring Dashboard — CloudWatch Ops View Increment

- Date: 2026-07-02
- Stage: CONSTRUCTION / Infrastructure Code Generation (follow-on increment)
- Trigger: operator request to add one CloudWatch dashboard that puts the current alarms/SLO metrics in one place.
- Scope:
  - Added `DocSuri-Production-Ops` dashboard in `ops/cdk/stacks/compute_stack.py`.
  - Reused the existing CloudWatch/SNS alert path; no new monitoring service or notification route.
  - Included local alarm widgets for API 5xx, API p95 latency, email delivery failure, novelty queue age, novelty DLQ, and personalization retention purge failure.
  - Included metric graphs for API SLOs, novelty/ingestion/docmodel/summary queue age, queue backlog/DLQ depth, application failure signals, and the existing AWS Budget cost alert context.
- Verification:
  - `python3 -m compileall ops/cdk/stacks/compute_stack.py` -> passed
  - `uv run --directory ops ruff check ../ops/cdk/stacks/compute_stack.py` -> passed
  - `npx --yes aws-cdk@2 --app "/Users/revenantonthemission/Projects/DocSuri/ops/cdk/.venv/bin/python app.py" synth Docsuri-Compute` -> passed with existing Node/CDK annotation warnings
  - `git diff --check` -> passed
- Current gate: ready for review/deploy decision.

## 유닛 재구성 (Unit Recomposition) — 적용 완료

- Date: 2026-08-03
- Stage: INCEPTION / Units Generation 재진입 (레지스트리↔코드 정합 회복)
- Trigger: 사용자 지시 — "유닛 재구성; 일부 유닛이 부분적이거나 임시 방편(quick fix)". 감사 결과 레지스트리 3종이 실제 마운트 모듈(11개)과 드리프트.
- Plan/gate: `inception/plans/unit-recomposition-plan.md` — UQ1~5 **전부 A**(사용자 답변), 적용 범위 = 레지스트리 + 코드 브랜치.
- Branch: `refactor/unit-recomposition` (base origin/develop `0df2ced`)
- 적용 내용:
  - **research→U11 흡수 (UQ1=A)**: `backend/modules/research/` → `backend/modules/evidence/sessions/`(git mv, 이력 보존). 라우트 `/api/research`·readyz 라벨 `research`·DTO 불변(FE 무영향). 게이트 통합: 세션은 `EVIDENCE_AGENT_ENABLED` off 시 함께 비활성(+기존 `RESEARCH_AGENT_ENABLED`는 세션 전용 레버 유지 — prod CDK 양쪽 true라 무변).
  - **user_docmodel U1 소유 확정 (UQ2=A)**: `backend/modules/user_docmodel.py` → `backend/modules/user_docmodel/coordinator.py` + `__init__.py` 재수출(임포트 경로 불변). 포트 `UserDocModelCoordinatorPort`(+`UserDocModelRefLike`)를 `docsuri_shared.ports`에 승격(U1 구현·U11/U12 주입 소비, PROVISIONAL).
  - **레지스트리 정정 (UQ4=A)**: `unit-of-work.md` U10 MyPage·U13 Agent Chat FE(US-AG1~6) 정식 등재(자리 주석 해소), U11 코드 위치 `evidence_agent/`→`evidence/` 오기 정정, U12 코드 위치 문서 경로→`backend/modules/novelty/` 정정, 배포 단위 ①(U10·U14~U16 반영)·④(U13 슬라이스), 코드 트리 U10~U16+user_docmodel 반영. `unit-of-work-dependency.md` U10~U16 의존 요약 신설(비순환 유지). `unit-of-work-story-map.md` U13 Owner 노트.
  - **U8 (UQ3=A)**: citation_graph 단일 파일 구조는 현상 유지(구조 부채로만 기록).
  - **문서 위생 (UQ5=A)**: `u6-integration-proposal.md` 적용-완료 스탬프.
- Verification: shared `uv run pytest` 전체 green + ruff clean; backend focused(연구/근거/유저독모델/novelty/app-shell) exit 0; `backend/tests` 전체 스윕 exit 0; touched ruff clean; compileall PASS.
- 기록 갭(후속): 2026-07-02 이후 증분(U14 온보딩·U15 트렌드·U16 플랜 인셉션/빌드, v3 재임베드 컷오버, novelty 쿼리확장 개편, U9 US-P4 go-live v1.15.0)은 본 파일에 상태 항목 미기재 — 각 담당의 사후 기재 권장(레지스트리·audit.md에는 존재).
- Current gate: 커밋 완료·push/PR 보류(사용자 승인 후).

## 전 유닛 코드 리뷰 (All-Units Review) + 교정 — 적용 완료

- Date: 2026-08-04
- Stage: OPERATIONS / 전 유닛 aidlc-unit-review 스윕 (U1~U16, 리뷰어 11·유닛별 스펙 대조)
- Verdicts: 11 유닛 APPROVE · 5 유닛 CHANGES REQUESTED(U1·U3·U8 blocking, U9·U11 should-fix). U12는 APPROVE + should-fix 1.
- Branch: `fix/unit-review-remediation` (base develop `5bb6eef`)
- Blocking 교정: ① U1 user_docmodel `ref_from_attachment` paperId 서버측 uuid5 재유도(교차 테넌트 DocModel 읽기/네임스페이스 오염 차단; 워커 미러는 페이로드에 mint scope 부재로 구조상 불가 — 백엔드 생산자 canonical-only로 방어) ② U3 로그인 백오프 타이밍 오라클(미존재 이메일도 동일 지연 — TTL 실패 카운터) ③ U8 refresh 실패 시 stale snapshot 폴백(FR-16) + 50노드 하드 상한.
- Should-fix 교정: U3 소셜-only 계정 유예기간 OIDC 재활성화(BR-A11) · U11 DLQ 소비자(`EVIDENCE_DLQ_URL`→TurnErrorResult{job_failed}) + poison payload 즉시 ack · U2 익명 검색 boost/이력 스킵(공유 anonymous id 풀링 해소) · U9 interest_set 화이트리스트/dedup + 리스트 메타데이터 상한(allowlist SSOT=U9, U14가 import) · U15 팔로우 토픽 UNIQUE(owner_id, lower(topic)) 마이그레이션 002 + IntegrityError→409 · U12 novelty 외부 URL 호스트 allowlist 적용 + HF/Zenodo 라이선스 필드 · user_docmodel 호출 3개소 run_in_threadpool.
- Nits: U13 mode-lock 가드 + 10MiB 상수 단일화(`frontend/lib/agentChat/limits.ts`) · 문서 3건(BR-13 auth-optional·U2 FD §3.5 apply_boosts·BR-EV-8 세션 hard-delete 카브아웃).
- 이월(권고만): U3 controller.py 1152줄 분할(800줄 상한 위반 — 별도 refactor) · U15 10토픽 cap 레이스(중복만 DB 강제) · U16 grant 대상 존재 확인(SEC-9 열거방지 관점에서 의도된 동작으로 판단) · U9 category 택소노미 검증.
- Verification: backend 전체 스윕 exit 0 · tests/accounts 134 passed · shared pytest green · ruff backend 전역 clean · compileall OK · frontend tsc(touched) + vitest 37 passed.
- Current gate: PR → CI green → develop 머지(사용자 지시).

## 서버리스 마이그레이션 — 게이트 확정 + Phase 0 종결

- Date: 2026-08-04
- Gate: `serverless-migration-plan.md` SQ1~SQ6 **전부 A**(사용자 답변) — 관리형 OpenSearch 유지·API Lambda(LWA)·Aurora Sv2 0-ACU·OpenNext·Redis 단일 노드·DB-먼저.
- Phase 0: 프로파일 컨텍스트·구 계정 하드코딩 정정(PR #12 선반영)·마이그레이션 분리(`RUN_MIGRATIONS_ON_STARTUP` 기구현) — 잔여는 Cost Explorer 4주 실측 보정뿐.
- Current gate: **Phase 1-① 착수 대기**(RDS 스냅샷 → Aurora Serverless v2 min 0 ACU; dev 환경 559352512800).

## 서버리스 Phase 1-① — Aurora Serverless v2 컷오버 완료

- Date: 2026-08-04
- Delivered: dev 환경(559352512800) DB = **Aurora PG 16.13 Serverless v2, min 0 / max 2 ACU** (t4g.micro 대체). `DB_POOL_MODE=null`(유휴 커넥션 해제 — 0-ACU pause 성립)·BFF GET 1회 재시도(SQ3) 이미지 반영. PR #14(구현)+#15(logical id 픽스) 머지.
- 검증: 8 스택 전부 CREATE_COMPLETE · `/readyz` 14 모듈 0 blocking(Aurora 위 자가 마이그레이션) · 클러스터 MinCapacity 0.0 확인. 신규 엔드포인트: API `d1xjb785lmqp2v.cloudfront.net` · Web `dg5irndt67zg4.cloudfront.net`.
- 교훈(런북 후보): ① CFN은 동일 logical id의 리소스 타입 변경 불가 — 신규 construct id 필수 ② `continue-update-rollback --resources-to-skip` 좀비 리소스는 이후 모든 업데이트를 오염 — dev는 스택 전체 재생성이 최단 경로(임포트 역순 삭제) ③ 명명 SQS 큐는 재생성 60s 쿨다운+고아 잔존 주의 ④ RemovalPolicy.RETAIN 인스턴스는 교체 전 수동 선삭제(ENI/SG 잠금 예방).
- 다음: Phase 1-②(스케줄 ECS 2종→Lambda cron)·1-③(API Lambda 카나리+NAT) — 별도 착수. 0-ACU 실제 pause는 유휴 ~15분 후 `ServerlessDatabaseCapacity` 메트릭으로 확인.

## 서버리스 Phase 1-② — 스케줄 태스크 Lambda 이행 완료

- Date: 2026-08-04
- Delivered: U9 retention cleanup(18:00 UTC)·계정 퍼지(03:30 UTC) = **docsuri-api 이미지 기반 Lambda cron**(awslambdaric, 10min/1024MB, PrivateEgress 서브넷) — dev EcsTask 타깃 대체. **dev NAT 1기 신설**(1-③ API Lambda와 공유). PR #17 머지(`d76a901`).
- 검증: prod 10 템플릿 byte-parity · 실 invoke 양쪽 200(`account_purge` status ok — Aurora 0-ACU wake 포함) · CI 전체 green.
- 교훈: ① buildx 기본 OCI index+provenance는 Lambda 이미지 미지원 — `--provenance=false --sbom=false` 필수 ② 수동 생성 ECR 리포는 lambda.amazonaws.com pull 정책 선부여 필요.
- 다음: Phase 1-③(API Lambda(LWA)+Function URL 카나리 — NAT 기설), Phase 2(NFR-P6 폴링 전환), Phase 3(SQ1=A 검색 축소).

## 서버리스 Phase 1-③ — API Lambda 카나리 (부분 완료 · 카나리 보류)

- Date: 2026-08-04
- Delivered (머지·기본 OFF): `docsuri-api` 이미지에 LWA 확장 + `backend/lambda_web.py` 부트스트랩, dev `ApiLambda`(2048MB/5min, PrivateEgress, **task-role 14 statements 패리티**), IAM+RESPONSE_STREAM Function URL, CloudFront OAC 오리진 **카나리 플래그 `-c api_origin=lambda`(기본 alb)**. ALB/Fargate 상시 유지 = 롤백 경로. PR #19 머지(`cae58bc`) + OAC 헤더 정책 후속 커밋.
- **검증됨**: Function URL 직접 SigV4 호출 → `/readyz` **200, 14 모듈 0 blocking** (LWA·시크릿 부트스트랩·VPC 이그레스·Aurora 연결 전부 정상).
- **미해결(카나리 보류)**: CloudFront OAC 경유 시 Function URL이 **403**(Lambda auth 계층 응답). 배제 완료: 리소스 정책 존재·SourceArn이 실제 서빙 배포(E10KAZ5I1PIFG9)와 일치·오리진이 Function URL·`allExcept[Authorization, Host]` 오리진 요청 정책 적용(SigV4 서명 헤더 충돌 제거)·전파 대기 후 재현. 잔여 용의선상: **OAC × RESPONSE_STREAM invoke mode 조합**, OAC signing behavior override 필요 여부. → dev CDN은 `api_origin` 기본값(alb)으로 **롤백 완료**(readyz 정상 확인).
- 참고: dev `POST /api/search` 503은 신규 계정 OpenSearch 도메인이 **빈 인덱스**(코퍼스 재색인 미실행)여서 발생 — 카나리와 무관, Phase 3(SQ1=A 축소·재색인)에서 해소 예정.
- 다음: 카나리 403 후속 조사(1-③ 잔여) 또는 Phase 2(NFR-P6 폴링 전환).
- 후속: OAC 403의 원인 = CDK 2.260 `FunctionUrlOrigin.with_origin_access_control()`이 **FunctionUrlAuthType 미지정 permission**을 방출 — Function URL invoke를 인가하지 못함. 수정(자격 있는 `lambda:InvokeFunctionUrl` CfnPermission 명시) PR #21 develop 머지. 카나리 재검증은 다음 dev 배포에서.

## 서버리스 Phase 2 — NFR-P6 폴링 전환 (research 턴 비동기화) 완료

- Date: 2026-08-04
- Gate: 설계 질문 1건 — **"NFR-P6 분기"** 채택(사용자 답변): 긴 분석(첨부 PDF 동반) research 턴만 비동기 잡+폴링, 짧은 질의는 EV2 동기 SSE 유지 + keepalive 하트비트. (대안 "전면 비동기"·"novelty 패턴 전면 이행"은 기각 — EV2 라이브 진행 타임라인 보존 우선.)
- Branch: `feat/serverless-phase2-nfr-p6-research-async` (base origin/develop `13dfadd`)
- Delivered:
  - **SSE keepalive**(`evidence/streaming.py`): 진행 이벤트 침묵 구간(extracting 단일 Bedrock 호출 등)에 15s 간격 `: keepalive` SSE 코멘트 — CloudFront 60s idle read_timeout(양 스택 "임시 완화" 주석의 원인) 방어. FE 파서(parseSseBlock)는 data 없는 블록을 버리므로 FE 무변경.
  - **research 턴 비동기 분기**(`evidence/sessions/{jobs,service,controller}.py`): 첨부 동반 + 워커 배선 시(`app.state.evidence_sqs_enqueue` — BR-EV-6와 동일 게이트·**동일 evidence-agent-job-queue 공유**) 유저 메시지 커밋→`mark_active`→enqueue 후 즉시 반환(잡 ACTIVE → FE AGENT_REFRESH_MS 스냅샷 폴링). SSE 협상에서도 비동기 적격 턴은 pending JSON(FE streamAgentTurn 'json' 아웃컴 기존 처리 — 재전송 없음). enqueue 실패는 `[error] evidence_unavailable`+COMPLETED로 종결(영원 폴링 방지). **커밋-후-enqueue** 순서로 워커 가시성 레이스 구조 차단.
  - **워커 research surface**(`evidence/worker.py`): 같은 큐에서 `surface=research` 라우팅 — 동기 경로와 동일 결과 계약(assistant msg+resolvedPaperIds+첨부 안내+COMPLETED), 멱등 가드(잡 ACTIVE ∧ 페이로드 유저 메시지=최신), 오류는 오류 계약 종결 후 JobProcessingFailed(ack). DLQ 드레인 확장(BR-EV-12 — research 잡 terminal 전이 + `surface` 메트릭 태그).
  - **`mark_active`**(ResearchRepository protocol+InMemory+SQL): 멀티턴 재진입 — COMPLETED 잡의 새 async 턴이 ACTIVE 복귀(FE 폴링 재가동). 페이로드 priorTopics는 최근 8건×2000자 캡(SQS 256KB 방어).
  - **FE 변경 0** — 기존 폴링 루프·'json' 아웃컴·SSE 코멘트 무시로 전부 수용.
- **docmodel-builder Lambda 이행 = 스킵 확정**: 계획 §5 조건("웨이크업 지연이 문제일 때만", 이득 ≈ $0 명시) — 관측된 웨이크업 지연 문제 없음. 필요해지면 후속 재심.
- CDK 변경 0: `DOCSURI_EVIDENCE_ASYNC_ENABLED`+큐 URL 기배선(compute_stack) — **API·evidence 워커 이미지 재배포만으로 활성화**.
- Verification: backend 전체 스윕 **449 passed/1 skipped** · 신규 `test_research_async_jobs.py` **22 passed** · `test_evidence_streaming.py` 12 passed(keepalive 2건 포함) · touched ruff clean(잔여 2건은 develop 기존: intent.py E501·streaming.py UP017) · compileall OK · FE vitest **251/251 passed**(9개 스위트 로드 실패는 로컬 mathjax-full 미설치 — 본 변경 무관 영역).
- 남은 리스크: Lambda 경로의 동기 SSE 턴(짧은 질의)은 5min 캡 내 완결 전제 — 실질 비구속. dev 실배포 검증(이미지 재배포 + 첨부 턴 E2E)은 배포 시점에 수행.
- 다음: dev 이미지 재배포+E2E(Phase 2 실증) → 1-③ 카나리 재검증(PR #21 반영분) 또는 Phase 3(SQ1=A 검색 축소·재색인).

## 서버리스 Phase 2 — dev 실배포 검증 (첨부 턴 E2E) 완료

- Date: 2026-08-05 (KST 새벽) · develop `e63f011`(PR #23) 기준
- 배포: `docsuri-api` 이미지 재빌드(linux/amd64, digest `b05f9c7a`) → API Fargate force redeploy(rollout COMPLETED · CDN `/readyz` 200) + 이미지 Lambda 3종 update-function-code(ApiLambda·계정 퍼지·U9 정리). evidence 워커는 scale-to-zero라 다음 기동에서 자동 승계.
- E2E(첨부 턴 — E2E 계정은 `seed_admin` 1회성 ECS RunTask로 생성, 종료 후 소프트 삭제):
  POST `/api/research/jobs` (Accept: text/event-stream + degraded PDF 첨부) → **즉시 pending JSON `{state: active}`** (스트리밍 아님 — NFR-P6 분기 실증) → 큐 1건 → 스케일업(0→1) → 워커 `surface=research` 처리 → **completed + 메시지 3건**(user · `[abstain] out_of_corpus` · 첨부 안내) → 큐 드레인 0 · DLQ 무유입. abstain은 신규 계정 OpenSearch **빈 인덱스**(Phase 3 재색인 전) 때문 — 비동기 배관 검증에는 무영향(orchestrator 완주·동기 계약 그대로).
- **발견 ① (blocking · 본 브랜치 수정 + dev 반영 완료)**: EvidenceStack 워커 env에 `DOCSURI_BEDROCK_MODEL_ID`/`DOCSURI_BEDROCK_REGION`/`DOCSURI_OPENSEARCH_INDEX` 부재 → `build_evidence_orchestrator`가 기동 TypeError(`model_id=None`)로 **크래시루프**. 신규 계정에서 이 워커의 최초 실 기동이라 잠복해 있던 갭. compute_stack 값 미러링(`evidence_stack.py`), dev `Docsuri-Evidence` UPDATE_COMPLETE(task def rev 3 확인).
- **발견 ② (UX 후속 권고)**: 워커 스케일업 알람 = **300s 메트릭 주기 × 1평가** — 콜드 큐에서 첫 응답까지 **~6분**(알람 대기 + 이미지 풀 + 기동). 배치 워커엔 무해하나 **대화형 첨부 턴**엔 길다. 후속 옵션: ① 알람 60s 주기 ② enqueue 시 API가 desired-count 부스트 ③ 업무시간 min 1. Phase 2 설계 자체는 폴링이라 UX가 깨지진 않음(진행 표시 유지).
- 교훈: dev CDK 배포는 반드시 **`-c profile=dev`** — 없으면 prod 형상으로 synth되어 크로스스택 export 불일치(`Docsuri-Compute:...Postgres...`)로 즉시 롤백된다(무해·검증됨).
- 다음: 1-③ 카나리 재검증(PR #21 반영분) 또는 Phase 3(SQ1=A 검색 축소·재색인 — abstain 해소).

## 서버리스 Phase 1-③ 잔여 — OAC 카나리 재검증 **성공** (403 근본원인 2건 확정)

- Date: 2026-08-05 · 카나리 배포: `-c profile=dev -c api_origin=lambda` (Compute UPDATE_COMPLETE 56s)
- **검증됨 (CloudFront → OAC SigV4 → 스트리밍 Function URL → LWA → API 전 구간)**:
  - GET `/readyz` → **200, 14 모듈 mounted·0 blocking** (Lambda 서빙)
  - POST `/auth/login`(오답 자격증명) + `x-amz-content-sha256` 헤더 → **앱 401** (전 구간 정상)
- **403 근본원인은 2건이 겹쳐 있었다**:
  1. CDK 2.260 `FunctionUrlOrigin.with_origin_access_control()`이 FunctionUrlAuthType 미지정 permission 방출 → PR #21로 자격 있는 `lambda:InvokeFunctionUrl` 명시(선행 수정).
  2. **AWS 2025-10 요건 변경**: OAC→Function URL은 CloudFront principal에 `lambda:InvokeFunctionUrl` **외에 `lambda:InvokeFunction`도** 요구(구 URL은 유예, 신규 계정·URL은 즉시 적용 — 본 dev 계정 해당). 실측: 1번 수정 후에도 403 → InvokeFunction permission 추가 즉시 200. 본 브랜치에서 CDK 코드화(`ApiCdnInvokeFunction`, 카나리 게이트 내).
- **컷오버 전제조건 발견 (POST/PUT 페이로드 해시)**: OAC 서명은 본문 있는 요청에 클라이언트 `x-amz-content-sha256` 헤더를 요구 — 미동봉 POST는 403 signature mismatch. **BFF(HttpTransport)가 요청 본문 SHA-256을 계산해 동봉해야 Lambda 오리진 실사용 가능** — 그 전까지 카나리는 검증 후 ALB로 원복(로그인·검색·턴 전부 POST라 실사용 즉시 파손). 이 헤더는 ALB 오리진에는 무해(무시됨) — BFF 선반영 후 컷오버 재개 권장.
- 정리: 카나리 검증 완료 후 CDN 오리진 **ALB 원복**(기본 플래그 재배포) + CLI 프로브 statement(`ApiCdnInvokeFunctionCanaryProbe`) 제거 — 코드화된 permission이 카나리 모드에서 대체.
- 다음: BFF `x-amz-content-sha256` 동봉(작은 FE 변경) → Lambda 오리진 상시 전환 재심 · Phase 3(검색 축소·재색인).

## 서버리스 Phase 1-③ 완결 — dev API 오리진 Lambda 컷오버 **완료**

- Date: 2026-08-06 · Branch: `feature/bff-oac-payload-hash`
- **BFF 페이로드 해시**: `HttpTransport` — 비-GET 요청에 전송 바이트의 SHA-256을 `x-amz-content-sha256`으로 상시 동봉(JSON=직렬화 문자열, 바이너리=바이트, 본문 없음=빈 페이로드 해시; 해시와 body가 같은 바이트를 가리키도록 전송 바이트를 선확정). `proxyEventStream`(SSE POST) 동일 계약. ALB 오리진은 무시하므로 오리진과 무관하게 안전. 테스트 4종(`httpTransportPayloadHash.test.ts`) + FE 전체 338 passed.
- **컷오버 영구화**: `cdk.json`에 `api_origin: lambda` 기본값(dev 전용 — `if dev:` 게이트, prod 무영향). 롤백 = `-c api_origin=alb` 1회 배포(ALB/Fargate 상시 대기).
- **검증(실 브라우저 경로 — web CDN → BFF → API CDN → OAC → Lambda)**: ① GET `/readyz` 200(14 모듈) ② POST `/bff/auth/login` 200 + 세션 발급 ③ **SSE 턴 `text/event-stream` — progress×2 → result, 2.5s** (Lambda RESPONSE_STREAM 스트리밍 관통) ④ POST 계정 삭제 200(정리). E2E 계정은 seed_admin 멱등 재승격으로 복구 후 재삭제.
- **운영 실수 기록**: 첫 컷오버 배포를 stale base(PR #25 미포함) 브랜치에서 실행 → `ApiCdnInvokeFunction` 누락으로 403 재현 — rebase 후 재배포로 해소. 교훈: **배포 전 브랜치가 최신 develop을 포함하는지 확인**(gh 머지 후 로컬 fetch 필수).
- **발견(선행 버그, 본 브랜치 1-line 수정)**: `/auth/account/reactivate`가 auth 미들웨어 `_PUBLIC_PREFIXES`에 미등재 — 소프트 삭제가 전 세션을 무효화하므로 이 요청은 구조상 세션이 없어 **유일한 대상 사용자에게 도달 불가**(FR-28 복구 플로우 전면 불통, 오리진 무관 선행 결함). 수정 반영·middleware 16 passed — 단 **dev 백엔드 이미지 미재배포**(다음 이미지 배포에 승계).
- 상태: **Phase 1-③ 종결** — dev API는 Lambda(LWA) 상시 서빙. 남은 축: 워커 콜드 6분 UX(Phase 2 후속) · Phase 3(검색 축소·재색인).

## 서버리스 Phase 3 — SQ1=A 재색인 (⏸ 중단 · 사용자 비용 결정)

- Date: 2026-08-06~07 · 중단: **2026-08-07, 사용자 결정("재색인 비용 과다")** — ~1k/87k papers 시점
- 실행 체인(B3): `raw_backfill` → `reembed_provision` → `reparse`(4분기 샤드) — finalize/cutover 미도달
- **raw_backfill 완료**: 87,006/87,395 코퍼스-월 PDF 캐시 프라임(6h). 과정 실측 2건 — ① **계정 이전 갭: `s3://arxiv` IAM grant 부재**(ListObjectsV2 AccessDenied) → `ingestion_stack.py` 수정 **PR #27 머지** ② 무필터 실행은 12,055 tar 전량 스캔(~21h/전송 ~$94) 함정 — `DOCSURI_RAW_BACKFILL_MONTHS` 샤딩(도구 자체 설계)으로 2,276 tar/~6h/~$23. 하베스트 타깃 110,454 중 코퍼스 월 밖 ~23k(2024-12 이전 제출·2025 갱신분)는 의도적 제외(~0.4% 손실 수용).
- **reparse 블로커 3건 — 전부 계정 이전 갭, 전부 해소**:
  1. **dev Aurora에 ingestion 마이그레이션 001~003 전무**(`canonical_dedup_state` → `dedup_state` 순차 실측 발견). 백엔드 startup 마이그레이션은 ingestion 경로를 의도적으로 제외("ingestion ships in its own image")하므로 신규 DB엔 풀 마이그레이터가 별도 필요. API 이미지 one-off RunTask(`python -c` + DDL env)로 001+002+003 적용, `_migrations` 원장 기록 — **신규 환경 셋업 절차에 풀 마이그레이터 단계 추가 필요**.
  2. **Bedrock `cohere.embed-multilingual-v3` Marketplace agreement 부재**(ap-northeast-1) — 전 페이퍼 임베드 AccessDenied. `aws bedrock create-foundation-model-agreement`로 구독(사용량 과금 $0.10/1M tokens, 유휴 $0).
  3. **워커 태스크 8GB OOM**(grobid+worker 공유·per-container 무제한) — 4샤드 전부 시간차 exit 137. run-task `"memory":"16384"` 오버라이드로 안정. **CDK 후속: 태스크데프 메모리 상향 또는 per-container limit**.
- **파이프라인 실증**: cached docmodel → dedup → chunk → embed → index 완주(~8s/paper/샤드, 118/32/89 청크 샘플). 샤딩 = `DOCSURI_BACKFILL_START/END` 분기 4개(reparse.py 설계대로).
- **비용 실측 → 중단 결정**: CloudWatch 실측 **~25k embed-tokens/paper**(19.8M tokens/~800 papers) → 완주 예상 **~$330**(embedding ~$220 지배 + 전송 $50 + Fargate ~$42 + Aurora ~$11). 디스크 리스크 동시 확인: 50GB 볼륨에 초기 raw 소모 ~3MB/paper — 병합 반영해도 full-body 멀티청크 87k는 45~90GB로 **§3.3의 "재색인·프루닝 필요" 전제 재확인**. 침몰 ~$65-70 · 회피 ~$270.
- **잔존 자산(재개 시 잔여 ~$270, 전부 멱등)**: raw cache 87k PDFs(`docsuri-papers-fulltext`, ~$5-6/mo) · 부분 인덱스 ~2.3GB(`docsuri-corpus-c3ml`) · 마이그레이션/IAM/Bedrock 구독 영구. 재개 = 4샤드 16GB run-task → `reembed_finalize` → `reembed_cutover`.
- **설계 갭 발견(후속)**: reparse asset 경로가 cache-only 모드에서도 arXiv 라이브 페치(ar5iv html·`/src`·`/pdf`) — `reparse.py` 독스트링("NO arXiv per-paper fetch")과 불일치.
- 참고: `docsuri-backups-559352512800`엔 PG dump 10.6MB×2(2026-07-23)뿐 — 코퍼스 아티팩트 없음(재색인 대체 불가). 코퍼스 백업은 완주 후 OpenSearch 스냅샷으로만 생성 가능.
- 다음(재개 조건): **청크 프루닝 결정**(embedding $와 디스크를 동시에 축소) 또는 볼륨 200GB(+$20/mo) 채택 후 재개 · 또는 로컬 이행(완주 후 스냅샷/복원이 최저비용 경로).

## 전체 기능 및 요구사항 검증 — 감사 완료 / CHANGES REQUIRED (2026-09-18)

- 사용자 요청으로 기존 구현의 아키텍처 이해·요구사항 추적·Build and Test 검증을 재개한다.
- 기준: `develop` / `32a424d`, 시작 시 clean. 계획: `construction/plans/project-verification-2026-09-18-plan.md`.
- 기존 요구사항/설계와 실제 런타임 사이의 드리프트도 검증한다. 현재 운영 형태는 `ops/server/README.md`의 로컬 Mac 서버 방식이며, 본 파일의 이전 AWS 기록은 당시 이력이다.
- 운영 경로와 분리한 detached worktree에서 테스트·빌드를 실행했다. 기존 Python 1,504개, frontend Vitest 338개, WebKit E2E 3개 통과; 추가 합성 반례 4개 실패. 공개 검색 corpus에는 허구 fixture가 노출되고 현재 distinct paper IDs는 11개다.
- **판정: CHANGES REQUIRED.** SECURITY-08/13(private 문서·공유 생성물 격리), SECURITY-10(dependency audit), FR-5/6(corpus 진실성/범위), FR-28/38(파기) 등 미해결. 감사 완료를 제품 전면 합격/Operations 승인으로 해석하지 않는다.
- 결과: `construction/build-and-test/project-verification-2026-09-18.md` — 활성 FR 47건, NFR/QT/제약, 확장 규칙, 13개 우선순위별 확인 사항, 실환경 미검증 범위.
- 반례 기록: `construction/build-and-test/project-verification-2026-09-18-reproductions.md`.

## 검증 결함 교정 — INCEPTION 진행 상태 (2026-09-18~19)

- 사용자 요청: 이전 세션에서 확인한 오류 교정.
- Workspace Detection: 기존 코드와 최신 감사 산출물이 있는 brownfield. 기존 reverse-engineering 기준선과 2026-09-18 실측 보고서를 입력으로 재사용한다.
- 후보 범위: `project-verification-2026-09-18.md`의 F01~F13. 네 합성 반례 외에 live corpus, dependency, migration, asset serving, digest, search-quality 교정을 포함할지는 요구사항 게이트에서 확정한다.
- 현재 단계: `inception/requirements/requirement-verification-questions-verification-remediation-2026-09-18.md` 답변 대기.
- 답변: Q1=A(F01~F13 전부), Q2=C(백업·롤백 후 안전한 live repair 허용, full corpus rebuild는 별도 승인), Q3=B(current local runtime으로 전면 재기준), Q4=A(Security Full), Q5=A(Resiliency Full), Q6=A(PBT Full).
- clarification=A: single-Mac production을 기준으로 전면 재기준하고 RESILIENCY-08 multi-zone fault-isolation을 명시 면제한다.
- Requirements 산출물: `inception/requirements/verification-remediation-2026-09-18.md`; master `requirements.md` single-Mac 조항 개정. **승인 완료 2026-09-18**.
- User Stories: 신규 사용자 흐름이 없는 결함 교정이므로 skip.
- Workflow Planning 산출물: `inception/plans/verification-remediation-2026-09-18-workflow-plan.md`.
- Workflow 결정: Application Design amendment, Units Generation, Functional Design, NFR Requirements/Design, Infrastructure Design, Code Generation, Build and Test 실행. four remediation units(REM-1 platform/contracts, REM-2 private content/generation, REM-3 lifecycle/edge trust, REM-4 corpus/search)로 순차 수행한다.
- 확장 적용: Security Full, Resiliency custom single-Mac profile(RESILIENCY-08 면제, RESILIENCY-09 horizontal autoscale N/A/대체 capacity gate), PBT Full.
- full corpus rebuild/reparse/reembed/alias cutover는 본 계획 밖 별도 명시 승인 게이트다.
- Workflow Planning 승인: 사용자 `Approve & Continue` (2026-09-19).
- Application Design 결정: RQ1~RQ7 모두 A(2026-09-19). 기존 도메인 소유, context-bound private read, repeat-request polling, immutable purge manifest, loopback-only trusted identity, standalone corpus audit/repair, explicit migration registry를 확정했다.
- Application Design 산출물: `inception/application-design/`의 mandatory 5문서에 REM-1~REM-4 컴포넌트, 메서드, 서비스, 의존성/데이터 흐름, F01~F13 추적성과 extension compliance를 개정했다.
- Application Design 검증: Security design 15/15 compliant; Resiliency 13 compliant + RESILIENCY-08 N/A + RESILIENCY-09 replacement; PBT-01~10은 상세 rule의 stage applicability에 따라 Application Design N/A이며 downstream test surface를 추적했다. Markdown 구조와 `git diff --check` 통과.
- Application Design 승인: 사용자 `Approve & Continue` (2026-09-19).
- Units Generation 1차 답변: UQR1=A, UQR2=A, UQR3=A, UQR4=B, UQR5=A (사용자 표기 UQ1~UQ5).
- 충돌: UQR4=B의 장기 deployable remediation services는 승인된 RQ1=A/Workflow와 UQR5=A의 temporary overlay/canonical product ownership에 모순된다.
- UQRF1=B: 사용자가 네 장기 deployable remediation services를 의도적으로 선택했다. 기존 planning-overlay Workflow/Application Design은 superseded됐고 Units Generation Part 1/Part 2는 중지됐다.
- Workflow Replan: `inception/plans/verification-remediation-2026-09-18-workflow-plan.md`에 critical deployment transformation, comprehensive service design/construction stages, revised Mermaid, extension compliance를 추가했다.
- Workflow 승인 게이트: `inception/plans/verification-remediation-2026-09-19-workflow-replan-approval.md` WPR1=A로 완료.
- Workflow Replan 승인: 사용자 WPR1=A (2026-09-19). Security Full, Resiliency custom, PBT Full을 유지한 four-service comprehensive workflow를 확정했다.
- Application Design redesign 답변: DSRQ1=A, DSRQ2=A, DSRQ3=A, DSRQ4=C, DSRQ5=A, DSRQ6=A, DSRQ7=A (사용자 표기 DQ1~DQ7; 2026-09-19).
- 답변 분석: 여섯 A 선택은 정합적이다. DSRQ4=C의 공개 job 계약 범위, 비동기 status/result 전달 및 health/REM-1 evidence 경계는 추가 결정이 필요하다. 공개 사용자 흐름 변경 시 Requirements/User Stories/Workflow 재평가가 선행된다.
- 명확화 확정: DSRQF1=A, DSRQF2=A (2026-09-19). REM 이관 대상 사용자 업무 read/status에 공개 job 계약을 적용하고 접수 확인/event 구독/결과 전달/health/REM-1 evidence는 직접 경로로 구분한다.
- 선행 단계 영향: 공개 사용자 흐름 변경으로 Requirements 재사용/User Stories skip 근거가 대체됐다. 제한적 Requirements -> User Stories -> Workflow 개정/승인 후 Application Design을 재개한다.
- 공개 job 요구사항 개정: `inception/requirements/requirements.md` FR-52/NFR-R4/QT-12/C-13 및 §14, `inception/requirements/verification-remediation-2026-09-18.md` §10. RJ-AC01~12와 scope/timeout/owner/lifecycle/cutover 인수를 작성했다.
- 검증: 신규 ID 충돌 없음, 답변·인수·참조·Markdown 검토 및 tracked/new-file whitespace check 통과. Security 01~15 요구사항 수준 Compliant; Resiliency 01~07/10~15 Compliant, 08 N/A(single-Mac), 09 bounded-capacity replacement; PBT 01~10은 Requirements Analysis N/A이고 downstream Full 추적 유지.
- 공개 job 요구사항 승인: 사용자 "Approve & continue"를 RJR1=A로 기록했다 (2026-09-19). FR-52/NFR-R4/QT-12/C-13 및 RJ-AC01~12가 승인된 입력이다.
- User Stories 평가/계획: `inception/plans/user-stories-assessment.md`와 `inception/plans/story-generation-plan.md`의 2026-09-19 개정. 기존 P1/P2/OP와 형식을 계승하고 공통 US-RJ1~3 및 기존 domain story 개정을 제안했다. RJ-AC01~12 전수 매핑과 질문/참조/whitespace 검증을 완료했다.
- User Stories 계획 승인: 사용자 "RJS1: A" (2026-09-19). 공통 US-RJ1~3, 기존 domain story 개정, P1/P2/OP 및 coverage 갱신 계획을 확정했다.
- User Stories 산출물: `inception/user-stories/stories.md`에 에픽 16/US-RJ1~3을 추가하고 기존 15개 story를 개정했다. 전체 85개 story/17개 에픽이며 `personas.md`의 P1/P2/OP와 persona/요구사항/RJ-AC01~12 coverage를 갱신했다.
- User Stories 검증: INVEST, 85개 story ID 유일성, 12개 인수 coverage, 3 persona, Markdown 및 `git diff --check` 통과. `story-generation-plan.md`에 Security/Resiliency/PBT per-rule Compliant/N/A 및 후속 추적을 기록했다. 현 단계 적용 규칙 blocking finding 없음.
- User Stories 산출물 승인: 사용자 "RJS2: A" (2026-09-19). 공개 job story/persona와 RJ-AC01~12 coverage를 승인했다.
- Workflow WPR2 산출물: `inception/plans/verification-remediation-2026-09-18-workflow-plan.md`의 Public Job Workflow Amendment 및 `execution-plan.md` 인덱스를 갱신했다. Application Design 재개, Units 재시작, 네 service loop, frontend 포함 package sequence와 G0~G5의 F01~F13/RJ-AC01~12 검증을 정의했다.
- Workflow 검증: 현재 `develop`/`32a424d` 및 manifests/launcher 대조, 저장된 Mermaid 3개 렌더, RJ-AC 12행, 질문/참조/표 및 tracked/untracked whitespace check 통과. Security 01~15와 적용 Resiliency 규칙은 계획 수준 Compliant, Resiliency 08 N/A/09 replacement; PBT 01~10은 Workflow Planning N/A이며 downstream Full 매핑 유지.
- Workflow WPR2 승인: 사용자 "WPR2: A" (2026-09-19). 공개 job/네 service 실행 계획을 승인하고 Application Design을 재개했다.
- Application Design 산출물: `inception/application-design/`의 components/component-methods/services/component-dependency/application-design에 새 Deployable Services and Public Jobs 절을 생성했다. 네 service/17개 component, public/internal HTTP/SSE와 typed ports, DS-1~8, writer/actor/control 경계, current authority/consent/purge/복구를 정의했다.
- Application Design 검증: F01~F13 13행 및 RJ-AC01~12 12행 trace, source/sync DAG와 의도된 async feedback 검토, Mermaid 2개 작성 전/후 렌더, 5개 Markdown Prettier debug-check 및 `git diff --check` 통과. Security 15개 design-level Compliant; Resiliency 13개 Compliant + 08 N/A + 09 replacement; PBT 10개 Application Design N/A 및 downstream Full 매핑. 현 설계 blocking finding 없음.
- Application Design 승인: 사용자 "DAD1: A" (2026-09-19). 5개 신규 설계 절과 component/contract/authority/flow/인수 추적성을 승인했다.
- Units Generation 재시작 계획: `inception/plans/unit-of-work-plan.md`의 Deployable-Service Units Restart Plan. 기존 UQR/DSRQ 결정을 계승하고 네 REM/17 component/13 finding/12 RJ-AC/18개 신규·개정 story의 primary/contributor 및 전체 85개 product-story owner 정합화 계획을 작성했다.
- Unit plan 검증: 합계/배치/의존성/현재 authority, UGP1 단일 미답변, Markdown Prettier debug-check 및 `git diff --check` 통과. 기존 story map의 core 45행과 후속 일부 주석을 Part 2에서 85개 current 행으로 완결한다.
- Units Generation 계획 승인: 사용자 "UGP1: A" (2026-09-19). 네 REM 및 product/delivery ownership, 85개 story 정합화와 component/finding/RJ-AC 배치를 승인했다.
- Units Generation 산출물: `inception/application-design/unit-of-work.md`, `unit-of-work-dependency.md`, `unit-of-work-story-map.md`에 네 REM 정의, 17 component, C/M/R/E/D/A 의존, 85개 개별 current product-story owner와 18개 REM delivery primary, 13 finding/12 RJ-AC를 반영했다.
- Units 검증: 실제 story ID/title 집합 및 core 45 owner 보존, 승인 계획 대비 18 story/17 component/13 finding/12 RJ-AC primary 집합 일치, 중복/누락 없음, product owner 합계 85, dependency/activation 정합 확인. 세 산출물/plan Prettier debug-check와 `git diff --check` 통과. unit-level Security/Resiliency 배정 Compliant 및 승인 예외 유지; PBT Units Generation N/A와 downstream Full 추적 유지.
- Units Generation 승인: 사용자 "UGR1: A" (2026-09-19). 세 unit 산출물과 current story/component/finding/RJ-AC 배치를 승인했다.
- REM-1 Functional Design 계획: `construction/plans/rem-1-platform-integrity-functional-design-plan.md`에 R1C/R1R/OBS 범위, 현재 migration/generator/CI 관찰, 8개 질문 범주, 6개 결정 질문 및 PBT-01 후보를 작성했다. ledger/check의 mutation, frontend skip-success와 Python publication의 remove/copy 경계를 코드에서 확인했다.
- REM-1 Functional Design 답변: 사용자 "Use A for R1FD1–R1FD6" (2026-09-19). 여섯 답변 A를 기록하고 legacy assurance/step atomicity/generated wire/evidence/exception/run identity의 정합성을 확인했다.
- REM-1 Functional Design 산출물: `construction/rem-1-platform-integrity/functional-design/`의 domain-entities/business-logic-model/business-rules를 작성·검증했다. E-R1-01~24, FL-R1-01~08, BR-R1-01~22, PROP-R1-01~16과 15개 시나리오, DAD1 port 및 F06/F08/F13/US-R4/5/RJ-AC12 추적성을 포함한다.
- REM-1 Functional Design 검증: ID 유일성/연속성/참조, 여섯 결정/11행 trace, Markdown Prettier debug-check 및 tracked/new-file whitespace 통과. effect UNKNOWN 전이, read-only/adoption 분리, CompatibilityManifest, current evidence revision 및 관측 규약을 보정했다. Security 11 Compliant/4 stage-N/A, Resiliency 10 Compliant/09 replacement/4 N/A(08 승인 예외 포함), PBT-01 Compliant/02~10 stage-N/A. 현재 기능 설계 적용 규칙의 미해결 blocking finding 없음.
- Markdown 검증 범위: 세 설계 산출물/plan/audit와 state 추가 내용은 debug-check 통과. 전체 state는 기존 2026-06-24 FR-27 항목의 formatter 재출력 불안정으로 실패하며 HEAD에서도 동일하게 재현됐다. 상세 검사/범위는 REM-1 plan §9와 audit에 기록했다.
- REM-1 Functional Design 승인: 사용자 `R1FDR1: A` (2026-09-19T14:57:39Z). 세 설계 산출물과 Testable Properties를 승인했다.
- REM-1 NFR Requirements 계획: `construction/plans/rem-1-platform-integrity-nfr-requirements-plan.md`에 8개 범주/13개 결정 질문, inherited constraints 및 Hypothesis/fast-check의 PBT-09 매핑을 작성했다. current manifests/CI/launcher/backup을 대조하고 read-only host 관측에서 24 GiB/14 CPU, data volume 97%·약 15.5 GiB free, FileVault Off를 확인했다. 수치/기술 선택지는 답변 전 제안이다.
- NFR 계획 검증: 질문/빈 답변/A/B/Other 각 13개, FD 참조/승인 및 형식 정합 확인. Prettier debug-check와 tracked/new-file whitespace 통과. encryption/unlock, disk/capacity, bootstrap/control storage, freshness/승인/보존/복구와 검증 강도를 질문에 연결했다. Security Full/Resiliency custom/PBT Full 유지; 현 단계 적용 PBT-09는 두 NFR 산출물에서 확정 기록한다.
- REM-1 NFR 답변: 사용자 `Use A for R1NFR1–R1NFR13` (2026-09-19T15:39:41Z). 13개 A를 기록하고 capacity/timeout/승인, bootstrap/control store, transport/signing key, FileVault/복구, freshness/보존/PBT의 정합성을 확인했다.
- REM-1 NFR 산출물: `construction/rem-1-platform-integrity/nfr-requirements/`에 `nfr-requirements.md`와 `tech-stack-decisions.md`를 작성·검증했다. NFR-R1-01~24, TD-R1-01~17, EV-R1-01~09와 각 13행의 결정 trace 및 PBT-09 양 언어 framework/dependency 근거를 포함한다.
- NFR 검증: 정의 유일성/연속성/FD 포함 참조, 29개 선택값 행 및 PBT profile, 40개 확장 규칙, Markdown/whitespace 통과. Security 13 Compliant/02·04 N/A, Resiliency 13 Compliant/09 replacement/08 N/A, PBT-09 Compliant/다른 9개 stage-N/A. 현 NFR 명세의 미해결 blocking finding 없음; 실제 목표 달성은 EV-R1 및 후속 단계로 확인한다.
- REM-1 NFR Requirements 승인: 사용자 `Continue to next stage`를 R1NFRR1=A로 기록했다 (2026-09-19T16:59:36Z). 두 산출물의 NFR/기술/검증 profile을 승인했다.
- REM-1 NFR Design 계획: `construction/plans/rem-1-platform-integrity-nfr-design-plan.md`에 다섯 필수 범주, R1ND1~9 패턴 질문, 14개 내부 logical component 후보 및 NFR/TD/EV/property trace를 작성했다. target lock, 단일 publication head/consumer pin, bootstrap journal, supervisor/bulkhead/cache, 목적별 권한/clock, durable audit와 backup cut을 구체화한다.
- NFR Design 계획 검증: 질문/빈 답변/A/B/Other 각 9개, 범주 5개, 후보 14개, trace 9행 및 승인 FD/NFR 참조 46개 확인. 현재 source의 sliding session verify와 optional audit hook을 non-renewing current-authority/durable receipt 계약과 구분했다. Markdown 및 tracked/new-file whitespace 통과. Security Full/Resiliency custom/PBT Full의 기존 결정·제약을 계승한다.
- REM-1 NFR Design 답변: 사용자 `Use A for R1ND1-R1ND9` (2026-09-20T13:14:58Z). 아홉 A를 기록하고 session lock/FS head/journal/supervisor/cache/authority/clock/audit/backup의 정합성을 확인했다.
- REM-1 NFR Design 산출물: `construction/rem-1-platform-integrity/nfr-design/`에 `nfr-design-patterns.md`와 `logical-components.md`를 작성·검증했다. PAT-R1-01~12, LC-R1-01~17, VAL-R1-01~18, 전체 24개 NFR coverage, 두 9행 선택 trace와 native guard/durability/clock/OS·역할의 Infrastructure proof obligations를 포함한다.
- NFR Design 검증: 정의 유일성/연속성/승인 FD·NFR 포함 참조 및 17-node/56-edge component DAG 통과. R1C에서 helper/tool로의 의존 경로 없음. single FS head/CP receipt, current authority/clock, orphan/quiescence, generation pin/backup/GC 및 수치 경계를 대조했고 Markdown/whitespace가 통과했다. Security 13 Compliant/02·04 N/A, Resiliency 13 Compliant/09 replacement/08 N/A, PBT 10개 stage-N/A와 Full 후속 요구 유지. 현 설계의 미해결 blocking finding 없음.
- REM-1 NFR Design 승인: 사용자 `Continue to the next stage`를 R1NDR1=A로 기록했다 (2026-09-20T14:27:39Z). 두 산출물의 패턴/컴포넌트/권한·복구/검증 경계를 승인했다.
- Infrastructure 추가 제약: 사용자 `The infrastructure should be zero-cost and everything should be served from this mac mini.` (2026-09-20T14:47:00Z). master requirements에 C-14 및 NFR-C1 참조를 등재했다. 유료 인프라/과금 전환/새 장비 구매를 전제하지 않고 application serving은 이 Mac mini에 한정한다. 기존 무료 보조 경계와 실제 off-host 자원을 확인하며, 내부 복제본을 off-host backup으로 간주하지 않는다.
- REM-1 Infrastructure 계획: `construction/plans/rem-1-platform-integrity-infrastructure-design-plan.md`에 C-14 local/zero-cost 경계, 7개 필수 범주, R1IF1~10 및 17개 LC의 실제 배치 후보를 작성했다. 기존 installer/launcher/compose/backup/heartbeat/CI, shared 문서 부재와 공식 runtime/license/launchd/Postgres TLS/chrony NTS/free monitoring 자료를 대조했다.
- Infrastructure 계획 검증: 질문/빈 답변/A/B/Other 각 10개, factual R1IF1/2와 권장 R1IF3~10 8개, 범주 7개, component coverage 17개, 질문 trace 10행/승인 ID 참조 50개 및 C-14 유일성 확인. Markdown/whitespace 통과. 실제 OrbStack Free 자격 및 기존 off-host backup 자원/용량은 사용자 확인 대상이다.
- 현재 단계: **Construction / REM-1 Code Generation Part 2 — 기반 구현·검증 반영, native provider/host 인수 미완료 (G1 미통과)**.

## REM-1 Infrastructure Design — 산출물 생성·검증 완료 (2026-09-22)

- 답변: **R1IF1=B**(OrbStack Free 자격 미전제, Colima/Lima + Docker Engine/CLI로 data plane 전환 · 원 VM 볼륨은 복원 검증까지 유지), **R1IF2=A**(이동식 드라이브 encrypted off-host backup · 별칭/용량/회수 시간은 설치 operator fact), **R1IF3~10=A**.
- 산출물: `construction/rem-1-platform-integrity/infrastructure-design/infrastructure-design.md`(roots/port/UID/keychain/CA/Postgres realm/clock/backup/monitoring + LC 17 전수 매핑)·`deployment-architecture.md`(single-Mac 토폴로지, boot/unlock 순서, P0~P4 전환·롤백·복구, zero-cost 경계)·`construction/shared-infrastructure.md`(신규 — shared resource 소유자/최소 권한/변경 순서/REM별 검증 책임).
- C-5 부대 개정(container manager: OrbStack→Colima)은 shared 문서와 master requirements 참조에 기록했다.
- 검증: 승인 LC/PAT/NFR/EV ID 참조 및 결정 trace 대조, Prettier 3파일 통과, `git diff --check` 통과. Mermaid는 로컬 headless 브라우저 부재로 렌더 대신 파서 실패(DOMPurify 환경) — 보수적 quoted-label 구성과 텍스트 대안을 문서에 수록했다.
- 확장: Security 01/03/05~15 Compliant, 02/04 N/A(신규 외부 intermediary/HTML 없음); Resiliency 01~07/10~15 Compliant, 08 N/A(승인 single-Mac 예외), 09 bounded-capacity replacement; PBT 01~10 stage-N/A(Code/Build로 Full 이월). 현재 인프라 설계의 blocking finding 없음; 실제 배치/인수 합격은 EV-R1-01~09의 실행 증거로만 판정한다.
- Infrastructure Design 승인: 사용자 `continue to next stage`를 R1IFR1=A로 기록했다 (2026-09-24T02:46:30Z). 다음: REM-1 Code Generation Part 1 상세 계획 작성 및 별도 승인 게이트.

### 공개 job 계약 선행 개정 진행 (2026-09-19)

- [x] Application Design 명확화 DSRQF1=A/DSRQF2=A 기록 및 정합성 해소
- [x] Requirements 공개 job 개정 작성/검증
- [x] Requirements 개정 승인 (RJR1=A, 2026-09-19)
- [x] User Stories 필요성 평가 및 공개 job 개정 계획 작성/검증
- [x] User Stories 개정 계획 승인 (RJS1=A, 2026-09-19)
- [x] User Stories story/persona 개정 및 검증
- [x] User Stories 산출물 승인 (RJS2=A, 2026-09-19)
- [x] Workflow Planning WPR2 개정 작성 및 검증
- [x] Workflow Planning WPR2 승인 (WPR2=A, 2026-09-19)
- [x] Application Design 5개 redesigned artifact 작성 및 검증
- [x] Application Design 산출물 승인 (DAD1=A, 2026-09-19)
- [x] Units Generation Part 1 재개
- [x] Units Generation 재개 계획 작성 및 검증
- [x] Units Generation 재개 계획 승인 (UGP1=A, 2026-09-19)
- [x] Units Generation 세 산출물 생성 및 검증
- [x] Units Generation 산출물 승인 (UGR1=A, 2026-09-19)
- [x] Construction REM-1 Functional Design 착수

## CONSTRUCTION — REM-1 Platform Integrity (2026-09-19)

- **Unit 문서 root**: `construction/rem-1-platform-integrity/`.
- **Functional Design 계획/승인**: `construction/plans/rem-1-platform-integrity-functional-design-plan.md`.
- **NFR Requirements 계획/승인**: `construction/plans/rem-1-platform-integrity-nfr-requirements-plan.md`.
- **NFR Design 계획/승인**: `construction/plans/rem-1-platform-integrity-nfr-design-plan.md`.
- **Infrastructure 계획/질문**: `construction/plans/rem-1-platform-integrity-infrastructure-design-plan.md`.
- [x] 승인 unit/context 및 Functional Design 규칙 로드
- [x] migration/contract/supply-chain 구현 근거와 6개 질문/PBT-01 후보 작성
- [x] 질문 형식/수량, scope/근거, Prettier debug-check 및 tracked/new-file whitespace 검증
- [x] R1FD1~R1FD6=A 답변 수집 및 모호성 해소
- [x] Functional Design 3개 산출물/Testable Properties 생성·검증
- [x] R1FDR1 산출물 리뷰 및 확장 per-rule 근거 제시
- [x] Functional Design 산출물 승인 (R1FDR1=A, 2026-09-19)
- [x] NFR Requirements 착수 및 상세 규칙 로드
- [x] NFR 입력/host 관측/8개 범주 분석 및 13개 질문/PBT-09 매핑 작성·검증
- [x] R1NFR1~R1NFR13=A 답변 수집 및 정합성 분석
- [x] NFR Requirements 두 산출물 생성·검증 및 R1NFRR1 완료 리뷰 준비
- [x] NFR Requirements 산출물 승인 (R1NFRR1=A, 2026-09-19)
- [x] NFR Design 착수 및 상세 규칙 로드
- [x] NFR Design 다섯 범주/9개 질문/내부 component 후보 작성·검증
- [x] R1ND1~R1ND9=A 답변 수집 및 정합성 분석
- [x] NFR Design 두 산출물 생성·검증 및 R1NDR1 완료 리뷰 준비
- [x] NFR Design 산출물 승인 (R1NDR1=A, 2026-09-20)
- [x] Infrastructure Design 착수 및 상세 규칙 로드
- [x] C-14 zero-cost/local serving 및 7개 범주/10개 질문/LC 물리 후보 작성·검증
- [x] R1IF1~R1IF10 답변/실제 license·backup 자원 수집 및 정합성 분석 (2026-09-22: R1IF1=B, R1IF2=A, R1IF3~10=A. R1IF2는 이동식 드라이브를 채택하고 별칭/용량/일일 회수 시간은 설치 시 operator fact로 기록 — 모순·모호성 없음)
- [x] Infrastructure 두 산출물/shared 문서 생성·검증 (`infrastructure-design.md`, `deployment-architecture.md`, `construction/shared-infrastructure.md`)
- [x] Infrastructure Design 산출물 승인 (R1IFR1=A, 2026-09-24)
- [x] Code Generation Part 1 상세 계획 작성·검증 (`construction/plans/rem-1-platform-integrity-code-generation-plan.md`, 17단계; 2026-09-24)
- [x] Code Generation Part 1 계획 승인 (R1CGR1=A, 2026-09-24)
- [ ] Code Generation Part 2 구현·검증

### REM-1 Part 2 구현 체크포인트 (2026-09-24)

- R1CGR1=A에 따라 격리 worktree에서 신규 `platform_integrity/`, owner-qualified migration registry/readonly startup+CLI, explicit legacy adoption, offline build-consumed TS 및 immutable Python binding, patched locks/image pins/CI 검사를 구현했다. 기존 주 checkout 문서 변경을 보존하고 소스 patch를 적용했다.
- 검증: 레인별 누적 Python 고유 **1,681 passed**(REM-1 127, shared 112, 기존 backend 463 및 disposable PG 포함), frontend 338+generator 29, 이전 WebKit 3, TS/build/drift/lint. REM-1 87% coverage는 이전 current-evidence 측정값이다. 최신 schema 후속 실행은 shared/REM-1/frontend 및 두 wheel이며 다른 레인과 dependency audit는 앞선 실행 기록을 유지한다.
- **미완료**: native current-authority/revoke/commit/fence/checkpoint 통합, 실제 NTS/Keychain/role 설치, privileged launcher/backup/restore, 모든 wire inventory와 image/OS SBOM audit, 전체 PROP/VAL/G1 성능/복구 인수. 기본 privileged apply는 BLOCKED다. 남은 plan 체크박스는 미완료로 유지했다.
- preflight에서 1 GiB 추가 peak 기준 disk reserve 부족(관측 free 약 11 GiB), removable drive/FileVault/native guard/clock/key/TLS/restore 증거 누락. Docker context `colima`는 관측했지만 이번 작업에서 전환하거나 실제 migration proof를 수립하지 않았다.
- 상세: `construction/rem-1-platform-integrity/code/code-summary.md`. 코드 작성/부분 검증을 Infrastructure 배포 또는 전체 F01~F13 교정 완료로 확대하지 않는다.

### REM-1 Run/control recovery 후속 구현 (2026-09-24T12:42:25Z)

- Step 3의 stable RunIntent/ordered plan, exact effect binding, 보수적 reconciliation 및 독립 stateful model을 구현했다. 확인된 abort와 충돌하는 native commit 반례를 실패로 재현하고 UNKNOWN 유지로 교정했다.
- Step 6의 내부 `PostgresRunStore`와 additive `002_run_protocol.sql`을 구현했다. UNKNOWN/checkpoint·audit·outbox·projection 원자 기록, CAS/immutable history, 반복 submission/attempt의 의미 보존, history gap 차단을 15개 실제 control-DB 시험으로 확인했다. 전체 REM-1 80건 및 release-profile subset 25건(seed 20260924) 통과; repeat 결과를 고유 합계에 중복 계산하지 않는다.
- 두 wheel의 non-editable import와 control SQL 패키징을 검증했다. 주 checkout 반영 뒤 source diff 역적용 check 통과. 작업 전용 Postgres 컨테이너는 중지·자동 제거했고 worktree/patch는 보존했다.
- **Code Generation Part 2와 G1은 계속 미완료**다. control 기록은 실제 current-authority/native guard의 대체물이 아니다. role 제한 command function, 실제 effect dispatcher/proof provider, clock/key/host 설치와 전체 consumer/SBOM/복구 인수를 연결해야 한다. 완료한 하위 항목만 plan에 체크했다.

### REM-1 Current evidence 후속 구현 (2026-09-24T15:09:17Z)

- Step 3의 reservation/current selection, current record/key/exception 검증, mutable-target state binding, 안전한 평가 입력 fingerprint 및 독립 verification-history model을 구현했다. checksum-only PASS, 도중 key 철회, `revoked=None`, 다른 scope의 head 및 history conflict의 실패 회귀를 고정했다.
- Step 6의 `PostgresEvidenceStore`/`003_verification_protocol.sql`로 PENDING 예약, immutable 결과/late history, audit/outbox 원자성, 단조 head 및 같은 transaction의 reservation floor를 구현했다. Step 11의 read coherence/current trust와 실제 I/O 종료까지의 8-worker admission을 추가했다.
- REM-1 **127 passed/coverage 87%**, release property subset **48 passed**(seed 20260924; 2,000-example/200×100-stateful profile), Ruff 통과. 새 실제 PG publication 시험 11건, real Ed25519 검증과 signed store→readonly service 조합을 포함한다. owner/clock/key 권한의 physical provider는 synthetic 대역과 구분한다.
- non-editable wheel 확인에서 같은 wheel 경로의 cached uv 환경 재사용을 발견했고 `--no-cache` fresh 설치로 신규 verifier와 packaged migration 003을 검증했다. 주 checkout 소스 반영 및 최신 worktree patch의 역적용 check 통과; 작업 전용 PG 컨테이너는 중지·자동 제거했다.
- **Part 2/G1은 미완료**다. production current-provider/권한·Keychain·NTS·native guard·scoped command role 배선, 남은 pure model/consumer inventory/SBOM/installer/backup/restore/성능 인수를 계속해야 한다. 구현된 내부 context/서명 primitive를 production capability의 증명으로 사용하지 않는다.

### REM-1 Offline schema 후속 구현 (2026-09-24T16:28:11Z)

- Step 3/8의 13-file 명시 catalog와 Python/internal·TypeScript/public generation roots, schema-position 기반 local ref/anchor/recursion/visibility 검증을 구현했다. bootstrap-independent `docsuri_schema`를 Python generator와 REM-1 tools가 공유하며 Node 구현과 공통 20개 conformance 사례를 대조한다.
- keyword-shaped literal data, URI/null 처리 차이, 하위 TS ref-parser의 literal 해석 및 percent-encoded path, export collision과 실패 후 publication 보존을 검증했다. Python 생성물 drift 없음; TypeScript 생성물은 fingerprint banner만 갱신됐다.
- shared **112 passed**, release catalog subset **39 passed**, frontend contract **29 passed**/UI **338 passed**, tsc/Next build/drift/Ruff, REM-1 **127 passed**(격리 PG 포함) 및 fresh/no-cache non-editable 두 wheel import가 통과했다. 추가 의존은 REM-1 tools의 first-party shared package이며 third-party lock 버전은 바꾸지 않았다.
- 기존 미커밋 작업을 보존하고 source parity를 확인했다. test 전용 PG 컨테이너는 중지·자동 제거했다. 실제 wire/import/view-adapter 목록 및 privileged publication/native provider/설치·복구·SBOM/G1 의무는 여전히 미완료다.

### REM-1 Consumer/domain/native harness 후속 구현 (2026-09-25T06:38:59Z)

- 실제 TypeScript 185 import/64 body cast/17 adapter, Python 217 import/97 local model 후보와 source digest를 inventory로 관리한다. adapter 등록 누락·shadowing·drift 회귀를 확인했다. 기존 frontend wire 57개를 14번째 shared schema로 승격하고 두 언어 생성물을 갱신했다. 전체 backend-owner parity는 아직 별도 의무다.
- registry/compatibility/SafeObservation/inventory 모델과 operator source의 target-transaction finalization을 구현했다. 충돌/다른 scope scanner report에서 finding이 사라지는 회귀와 unknown exception-authority coercion을 수정했다. 실제 PG의 revoke/commit 순서·stale epoch·clock 불능 및 control/audit dump/restore를 검증했다.
- REM-1 **190 passed / statement coverage 88%**, 새 domain release subset **23 passed**(seed 20260925), shared **115 passed**, frontend **340 UI + 32 generator/inventory**, backend migration subset **12 passed**, type/drift/Ruff 및 fresh/no-cache 두 wheel import 통과. 최종 authority review에서 다른 목적의 grant로 apply가 가능했던 회귀와 invalid clock/unknown revoke coercion을 실패 재현 후 차단했다. 반복 실행은 고유 합계에 가산하지 않는다.
- Syft/Grype reader/runner/validation capture에서 각각 67/64/135 components와 zero matches를 관측했으나 final artifact/current freshness 인수는 아니다. PostgreSQL image는 **323 matches, 96 High + 2 Critical**로 BLOCKED다. blocking match fix 상태는 fixed 24/not-fixed 12/wont-fix 62이며 자동 suppress/예외 승격하지 않았다.
- 9월 25일 source 67파일을 검증한 incremental Git patch로 통합한 뒤 최종 authority 교정을 apply_patch로 반영했다(총 69파일). 신규 Python generation `aa0015fc61158f5a29e79505ec4c2bae691992cbb91e948e5d4a4ac5c926069c`와 head를 함께 포함했다. 기존 사용자 문서/변경을 보존했다.
- operator 선택 R1OP1=A/R1OP2=A와 `code/operator-handoff.md`를 기록했다. role 준비는 PLAN_ONLY만 실행했다. 실제 administrator/FileVault/암호화 volume mount·접근시간, NTS/Keychain/command role 및 물리 recovery/load 인수는 미완료다. **Part 2/G1은 계속 열린 상태**다.
- 최종 source parity/whitespace 검사 통과 후 작업 전용 PG 컨테이너를 중지·자동 제거했다(2026-09-25T06:40:50Z). 보존 worktree/patch/report에서 재개할 수 있다.

### REM-1 Backup volume operator 입력 및 관측 (2026-09-26)

- 사용자 입력: mount alias `DocSuri_Backup`, 일일 연결/회수 시간 `03:00`. `/Volumes/DocSuri_Backup`에서 USB APFS 암호화·마운트·unlocked/writable 상태를 실제 확인했다. UUID `BB384D60-46AF-4A06-B6F7-95710B3B7A3C`, SSD01과 공유하는 container 여유 `1,537,204,109,312` bytes다.
- R1OP3=A 확정(2026-09-26T02:36:28Z): **매일 03:00 Asia/Seoul(UTC+9) 백업 시작, volume 상시 연결**. operator가 소유권 적용을 완료했고 후속 OS 관측에서 `GlobalPermissionsEnabled=true`를 확인했다. host FileVault 준비와 scheduler 설정은 남아 있다.
- readonly preflight는 drive 존재/다른 filesystem 검사를 통과했으나 `ready=false`다. 1 GiB 추가 peak 가정에서 local free `12,882,644,992` bytes < 필요 `12,884,901,888` bytes이며 FileVault/native guard/NTS/Keychain/TLS/restore receipt도 미충족이다. volume 관측을 물리 backup/restore·G1 통과로 확대하지 않는다.

### REM-1 Native 준비 결과 대조 및 검사기 보정 (2026-09-26)

- operator는 원 hash `94d73055dc46ea97db04275e3c99a81a054f1efdc3ba9989f9ed826fe511bbb5`의 보호된 복사본으로 `--apply`를 실행했다. UID/GID 600~608, non-login shell/home/hidden, root 0711·role 0700·receipt 0600을 실제 OS 조회로 대조했다. 준비 결과는 `PREPARED_NOT_ACCEPTED`다.
- native `IsHidden` namespace와 macOS directory group 12/61/100을 확인했다. namespace parser를 보정하고 readonly `--check`가 `METADATA_VERIFIED`, `ready=false`를 반환함을 실제 확인했다. strict 초기화 경로의 group 제한은 유지하며 directory metadata를 실제 process 권한 증명으로 확대하지 않는다.
- 현대 macOS CPython의 `os.getgroups`와 kernel group list가 다르므로, fixed worker의 libSystem `getgroups`와 실제 파일 접근을 함께 확인하는 `--probe`를 준비했다. root-owned staging, fixed test realm, dropped supplementary groups, role별 5초 제한 및 fixture 보존을 적용한다. focused native tests **16 passed**, Ruff/system Python 3.9 worker parsing 통과, unprivileged `--probe`는 BLOCKED다.
- 첫 검증판 hash `90aa58859bdfcd922f9aa2fe9a8a49a93a9e87b07be0a769b125585976ebac7f`의 operator 실행은 9개 `TimeoutExpired`로 BLOCKED였다. 원 `role-probe-su4773zc`를 보존했다. 실제 파일 격리·installed launcher/NTS/Keychain/DB/FileVault/backup/load 및 G1은 미통과다.
- 후속 진단판 hash `2e310b60c37e0398f18c9c4351398d49cf4857d5c46c2addc744126be00e4e23`는 `proc_pidpath`로 관측한 interpreter image 직접 실행, allowlisted phase, timeout group cleanup, `--role reader`/partial coverage를 구현했다. focused **22 passed**, Ruff/system Python 3.9 parsing 및 일반 UID startup smoke 통과. 원 timeout의 정확한 내부 근인은 미확정이며 상세 failure capture는 `code/native-probe-debug.md`다.
- operator의 r2 실제 reader 결과를 수신했다(2026-09-26T03:54:02Z 기록): **PARTIAL_ROLE_FILE_ISOLATION_VERIFIED**, UID/GID/groups=600/600/[600], ownReadWrite=true, crossReadDenied=8/crossWriteDenied=8/directoryGroupReadDenied=3, 0.052초/complete/returncode=0/parentReaped=true. probe root `role-probe-e_0w5ja7`; interpreter hash `07470fa2e1aec690aa62061af6e0f65fe9bf3169a74a16384592fb1ff1cb320f`를 현재 파일과 대조했다. reader scope의 timeout 해소/격리를 기록하고 다음은 동일 r2 전체 9-role probe다. 전체 coverage/G1은 미완료다.
- 후속 전체 결과 수신(2026-09-26T04:03:22Z 기록): **ROLE_FILE_ISOLATION_VERIFIED / completeRoleCoverage=true**. `role-probe-236g0xrp`에서 9개 role(UID/GID 600~608) 모두 해당 primary GID만 보유하고 own read/write, 교차 read 72/write 72 및 ambient-group read 27건 거부를 통과했다. 전 worker가 0.044~0.051초에 complete/exit 0/no timeout/parentReaped로 끝났다. 이 **synthetic-file scope의 인수는 완료**다. 현재 source/interpreter hash를 대조했으며 installed launcher 정책·Keychain/NTS/DB 권한·FileVault/실제 backup/restore/load와 G1은 계속 미완료다.

### REM-1 Native runtime 배선 + 실제 DB mTLS 인수 (2026-09-26T14:20:00Z)

- `deployment/launchd.py`, `host.py`, `adapters/{credentials,postgres_tls,nts,read_authority}.py`, `migrations/005_reader_access.sql`과 7개 신규 test를 구현해 **main에 통합**했다. 통합 전후로 worktree와 main의 `platform_integrity` 트리가 바이트 동일함을 확인했고, 기존 사용자 변경은 건드리지 않았다. commit/push는 하지 않았다.
- launcher는 immutable manifest allowlist, role-scoped plist(`InitGroups=false`, `Umask=0o077`, `env -i`), frozen artifact digest 검증, `setgroups([])`→gid→uid 순 privilege drop과 실행 직전 uid/gid/supplementary group 재검증을 수행한다. `host.py`는 credential byte가 아니라 Keychain handle만 받고, clock observer는 고정 non-adjusting `chronyd -x -d -f`만 허용한다.
- **실제 PostgreSQL mTLS 인수 통과**: loopback TLS, `cert clientname=CN` 기반 `session_user=r1_tls_probe` 로그인, read-only transaction 강제, wrong-CA 거부(오류가 certificate 관련인지 확인). 격리 CA/루프백 전용이며 운영 Keychain/8101/TLS role 인수 증거로 대체하지 않는다.
- 장기 미해결이던 mTLS fixture 실패는 코드가 아니라 세 가지 독립 결함이었다: (1) 열린 psycopg 컨텍스트 안의 `docker restart`로 인한 `AdminShutdown`, (2) 256M `HostConfig.Tmpfs` PGDATA로 restart마다 `ALTER SYSTEM SET ssl=on` 소실, (3) `hostssl ... cert` 규칙이 image 전역 `scram-sha-256` 뒤에 있어 first-match password 요구. `pg_ctl restart`는 postmaster가 PID 1이라 container를 종료시키므로 채택하지 않았다.
- 검증 전용 container `rem1-test-pg-20260924`를 named volume `rem1-pgdata-20260926`으로 재생성했다. image entrypoint가 시작마다 `pg_hba.conf`를 다시 쓰므로 test는 restart 후 HBA를 복사하고 reload한다. teardown 후 `ssl=off`, probe 규칙 0건, `postgresql.auto.conf` 초기화를 확인했다.
- 신규 모듈 statement coverage를 launchd 54%→**92%**, host 58%→**99%**, nts 67%→**93%**, read_authority 75%→**100%**로 올렸다. 전체는 82%로 하락했다가 **89%**로 회복했고(9월 25일 190/88% 상회), **main 재검증 280 passed**, Ruff 통과다. evidence log는 `rem1-main-suite.log`와 `rem1-cov3.log`다.
- Step 10은 **미체크**를 유지한다. 실제 Keychain ACL, 8101 serving mTLS, live chrony NTS daemon, U3 current-authority guard는 미완료다.

## REM-1 Code Generation Part 1 — 상세 계획 완료 (2026-09-24)

- 기존 구현 대조: `backend/migrations/__init__.py`는 SQL filename만으로 ledger를 식별하고 read-side `pending_migrations`가 DDL을 수행한다. startup/CLI registry 목록 불일치(F08); `frontend/scripts/gen-types.mjs`가 실패를 skip/exit 0으로 처리(F13); Python generator는 remove/copy publication이며 현재 CI는 PR dependency diff 중심(F06). 전부 계획의 failing regression에 연결했다.
- 승인된 R1IF1=B에 따라 master `requirements.md`의 C-5/NFR-A1/RES-10에 **현재 OrbStack 사실과 Colima 전환 목표**를 구분해 back-sync했다. 실제 volume/host 전환은 backup·복원·디스크 증거 전까지 보류한다.
- 신규 `platform_integrity/` 독립 패키지 및 기존 migration/shared/frontend/CI/ops seam에 대한 순차 17-step 계획을 작성했다. PROP-R1-01~16, VAL-R1-01~18, EV-R1-01~09와 US-R4/5, F06/F08/F13, RJ-AC12를 연결한다. REM-1 local G1과 후속 REM G4/G5를 구분한다.
- 검증: Plan Prettier debug-check, 17 numbered steps, 10개 R1IF 답변 유지, tracked whitespace `git diff --check` 통과. Security Full, Resiliency single-host custom, PBT Full 계획 수준 적용/N/A는 계획 §6에 기록했다.
- **다음**: R1CGR1 계획 명시 승인 후 Code Generation Part 2. 앱 코드/운영 환경은 본 Planning 단계에서 변경하지 않았다.

### REM-1 PostgreSQL image 후보 + ops dependency 결함 교정 (2026-09-26T13:12:40Z)

- operator가 "digest 교체"를 승인해 pinning image `postgres@sha256:a3b7f434…`(98 blocking)를 재평가했다. 정밀 분해 결과 24건은 `gosu` 단일 바이너리의 go1.24.6 stdlib, 74건은 Debian trixie OS 계층이며 잔여 OS 건은 전부 upstream fix가 없다. Alpine 16.15는 OS 계층을 1건까지 줄였고, gosu를 제거하고 비특권 uid로 실행하는 derived image(`ops/platform-integrity/images/postgres-alpine-nosu.Dockerfile`)로 **865 components / 4 findings / 1 blocking**까지 도달했다. 잔여 1건은 alpine zlib `CVE-2026-85091`(High, fix 없음)다.
- derived image는 `SOURCE_DATE_EPOCH` 고정 + `--provenance=false`로만 재현 가능하다(미고정 시 config digest가 매 build 변경). 재현 digest `sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`로 **280 passed / 89% / Ruff 통과 / 실제 loopback mTLS**를 확인했고 `sbom-targets.json`에 superseded image와 근거를 기록했다. 운영 compose 교체는 operator maintenance window 대기다.
- 부수 발견 결함 두 건을 교정했다. (1) `ops/platform-integrity/scan_sbom.py`가 `psutil`을 import하지만 `ops/pyproject.toml`에 미선언이라 runner가 원인을 `ModuleNotFoundError`로만 남기고 조용히 INCOMPLETE를 반환했다. `psutil>=7,<8`을 선언하고 lock을 갱신했으며(추가 package 1개) 공식 scan이 정상 동작한다. (2) mTLS test가 `docker exec` chown/chmod을 기본 user로 호출해 비root container에서 실패했다. `install_hba`와 동일하게 `--user root`를 명시했다.
- 교정 전 잠깐 "Alpine은 High/Critical 1건"이라는 직접 grype 실행 결과를 보고했으나, 이는 **틀렸고 공식 runner가 옳았다.** SBOM 경유 scan은 image 직접 scan과 달리 `/usr/local/bin/gosu`의 Go stdlib 24건을 검출한다. image 직접 scan 결과만으로는 release 판단을 하면 안 된다.

### REM-1 FileVault 활성화 확인 및 preflight 재측정 (2026-09-26T13:05:12Z)

- operator가 승인한 대로 root 볼륨 FileVault을 활성화했다. `fdesetup status` = `FileVault is On.`, `diskutil info /`에서 `Macintosh HD`(`/dev/disk3s1s1`) `FileVault: Yes`를 독립 확인했다.
- readonly preflight 재실행 결과 `filevault_unverified`가 해소됐다. 잔여 이유는 `native_commit_guard_missing`, `nts_clock_missing`, `keychain_roles_missing`, `tls_roles_missing`, `restore_receipt_missing` 5개뿐이다. `disk_reserve`와 `removable_drive_unverified`도 통과 상태를 유지한다(free `37,906,464,768` bytes ≥ 필요 `10,737,418,240` bytes).
- `preflight()`는 evidence 키가 있어도 항상 `<capability>_requires_receipt_verification`를 붙이므로 `ready=true`가 구조적으로 불가능하다. 이 결함은 코드 측 미구현 receipt verifier이며 operator 입력으로 해소되지 않는다. 다음 구현 대상이다.

### REM-1 signed capability receipt verifier 구현 (2026-09-26T13:36:10Z)

- `preflight()`의 구조적 결함을 해소했다. 이전에는 evidence 키가 있어도 `<capability>_requires_receipt_verification`가 항상 추가되어 `ready=true`가 불가능했다.
- `platform_integrity/src/docsuri_platform_integrity/deployment/receipt.py` 신규: Ed25519 서명, `IOPlatformUUID` host 결합, release 결합, 7일 상한 `ValidityWindow`, artifact/evidence digest, `revoked`/`validity`를 가진 manifest 신뢰 키. 미해결 capability는 proven이 아니며 사유가 항상 반환된다.
- `ops/platform-integrity/preflight.py`가 `--evidence`로 실제 검증한 capability만 `provenCapabilities`에 넣는다. **trust는 evidence와 분리**되어 같은 디렉터리 밖 키를 거부한다.
- 실제 CLI로 5개 capability 검증 receipt에서 `ready: true` / exit 0을 확인했다(임시 self-signed 키, 즉시 폐기 — acceptance 근거 아님).
- 구현 중 결함 3건을 교정했다: strict mode에서 `model_validate(dict)`가 enum 문자열을 거부함(관례대로 `model_validate_json(canonical(...))` 사용), `bytes` 필드는 JSON 직렬화 불가(공개키를 canonical base64url text로 변경), `ValidityWindow.contains`의 `upper < valid_until` 경계.
- `ops`에 `docsuri-platform-integrity` dependency를 추가했다. 새 dependency가 3.13 이상이므로 `requires-python`을 `>=3.11` → `>=3.13`으로 올렸다.
- **검증**: `platform_integrity` 308 passed / 0 skipped / coverage 89% / Ruff 통과(실제 loopback mTLS 포함 실행), `ops` 68 passed / Ruff 통과. 6개 파일을 preserved WT에 byte-identical 동기화하고 트리 전체 parity 재확인.
- **남음**: receipt를 발급하는 installer, launchd installer/manifest, purpose Keychain, live chrony NTS, backup/archive 명령과 scheduler, native commit guard. 5개 capability의 실제 증거와 image 잔여 finding(`CVE-2026-85091`)은 그대로다. G1 미통과.

### REM-1 readonly capability probe 및 receipt issuer 구현 (2026-09-26T14:05:00Z)

- `deployment/capability.py`를 추가했다. verifier에 짝을 이루는 readonly probe 5종(keychain roles / tls roles / nts clock / native commit guard / restore receipt)과 `ProbeSet` dispatcher, `receipt_from()`이다. 전부 절대 raise하지 않으며 불가하면 `proven=False` + 사유를 반환한다.
- probe는 기존 adapter 코드 경로(`ProtectedClock`, `PostgresTLS`, `KeychainReader`, `validate_bundle`, `OperatorAuthority.guard`)를 재사용한다. 중복 구현이 없다.
- `ops/platform-integrity/issue_receipt.py`를 추가했다. 설정 문서는 reference만 담고 credential을 읽지 않으며, `--probe-only`는 key도 파일도 건드리지 않는다. **하나라도 proven이 아니면 run 전체를 거부하고 receipt를 하나도 쓰지 않는다**(부분 성공이 acceptance로 오인될 수 있으므로).
- 서명 키는 읽기 전에 symlink/소유자/mode(0o077)/nlink/크기를 확인하고, receipt는 0600 atomic write로 남긴다.
- `native_commit_guard`는 live operator authority가 필요한 Step 6 영역이라 이 issuer에서 발급하지 않고 `notIssuableHere`로 명시했다.
- **교정한 결함 2건**: (1) `probe_restore_receipt`가 `lower <= completed`를 요구해 방금 끝난 정상 복원을 `restore_stale`로 거부했다 — 관측 창이 한 순간이므로 "미래가 아니고 30일 이내"가 올바른 조건이다. (2) `build_probe_set`가 잘못된 타입의 섹션에서 `TypeError`로 crash했다 — 명시적 `ValueError` 검증으로 fail-closed 한다.
- **실제 round trip 검증**: probe-only → 발급(`ISSUED`) → `preflight.py --evidence`가 `provenCapabilities: ["restore_receipt"]` 확인. capability 계열 잔여 사유 0건. 임시 키이며 즉시 삭제했으므로 acceptance 근거가 아니다.
- **검증 결과**: `platform_integrity` 340 passed / 0 skipped / statement coverage 89% / Ruff 통과(`capability.py` 97%), `ops` 86 passed / Ruff 통과. 신규 테스트 32건 + 18건.
- WT 동기화: 신규 4개 파일과 이전 세션에서 main에만 있던 `images/postgres-alpine-nosu.Dockerfile`, `sbom-targets.json`까지 byte-identical. 트리 전체 parity 재확인.
- **남음**: `native_commit_guard` 발급 경로, launchd installer/manifest, purpose Keychain 실제 생성, live chrony NTS, 실제 DB mTLS role, backup/archive 명령과 scheduler. 실제 operator 증거 0건이며 G1 미통과.

### REM-1 launchd installer/manifest 구현 (2026-09-26T14:40:00Z)

- `deployment/launchd.py`에 `install` / `uninstall` 추가. 이전에는 `render` + `exec`만 있었고 plist를 launchd에 올리는 경로가 없었다.
- `install`은 root·darwin·launchctl 무결성 → realm → 계정/uid/gid → role 작업 디렉터리 소유자 → **모든 frozen artifact digest**를 확인한 뒤에야 쓴다. 검증 실패 시 plist 0개.
- `is_published()`가 (manifest digest) + (plist 바이트가 재계산 결과와 일치) + (`launchctl print`가 실제 잡음) 3중 확인. 이전의 `deployment.json` 존재만으로는 반쯤 해제된 설치를 '설치됨'으로 오인하는 결함이 있었다.
- drifted/half-removed 상태는 **bootout 먼저 → 고쳐 쓰기**로 복구한다. 고장 난 job을 고치는 동안 돌게 두지 않는다.
- `--replace` 없이는 다른 manifest로 교체 불가(되돌릴 수 없는 조용한 변경 금지). 교체 시에도 이전 deployment를 먼저 bootout한다.
- `uninstall`은 bootout 후에도 launchd가 잡고 있는 job이 있으면 **삭제하지 않고 실패**한다 — 실행 중 job의 plist를 지우면 stop 수단이 없는 고아가 된다. Label 불일치 plist도 foreign로 거부.
- `write_root_file`은 symlink 거부, root 비소유 파일 거부, 임시 파일→fsync→`os.replace`→디렉터리 fsync 원자적 쓰기(plist 0644 / manifest 0400). recursive delete·glob 없음.
- **self-correction**: (1) `ALREADY_INSTALLED` 오인 결함, (2) 리팩터링 중 떨어뜨린 refuse-silent-replacement 가드, (3) uninstall orphan 방지 부재, (4) `require_root`가 root 소유를 검사해 비권한 테스트가 불가능 → symlink/쓰기가능 검사로 변경(실제로 검증 가능한 속성).
- **검증**: `test_launch_policy.py` 24 → 34건(신규 10). 전체 350 passed / 0 skipped / statement 89% / Ruff 통과(`launchd.py` 88%). 비root install/uninstall → BLOCKED exit 2, render 정상, `/Library/LaunchDaemons` 무변경. **root 실제 install은 하지 않았고 테스트 launchctl는 recorder다.** WT 동기화 후 34 passed, `git diff --check` 통과.
- **남음**: `_docsuri_r1t_*` 계정 9종 생성, toolchain/artifact 배치, 실제 test-profile rehearsal, production install(maintenance window). G1 미통과.

### REM-1 Step 6 native commit guard 발급 경로 구현 (2026-09-26T16:20:00Z)

- `native_commit_guard`의 `notIssuableHere` 결정을 뒤집고 **live `PostgresOperatorAuthority`에서 발급**하도록 바꿨다. 5개 capability를 기본 요청하므로, 선언되었지만 구성할 수 없는 guard는 fallback으로 "여기서 발급 불가"가 아니라 **미증명 capability**로 보고한다(전체 발급 차단).
- `deployment/operator_plan.py`를 추가했다. frozen plan은 digest pin을 반드시 받아야 하고, root/현재 사용자 소유·group/world write 금지·단일 link·심볼릭 링크 아님·크기 상한을 모두 검사한다. 승인서가 이미 알고 있는 digest와 어긋나면 재적용 후에도 plan을 못 읽는다.
- probe는 이제 **양방향**을 입증한다. plan에 없는 identity는 정확히 `effect is outside the frozen operator plan`으로 거절되어야 하고, 계획된 identity는 guarded region에 **효과 없이** admitted되어야 한다. adapter가 body 이후에 finalization을 거절하므로 body 안에서 세는 flag만이 거절과 admitted를 구분한다.
- live 시험 중 probe 판정 2건을 바로잡았다. ① `MutationUnavailable`이 `PermissionError`의 하위 클래스라 폐기/범위초과 승인이 내부 오류로 보고됐다 → 정상 거절로 수정. ② admitted 후 사후 거절하는 guard와 처음부터 거절하는 guard가 같은 예외를 던지므로, 예외 메시지보다 `entered` flag를 먼저 봐야 한다.
- `tests/test_guard_receipt.py` 10건을 추가했다. migration `001~004`를 실제 재현하고 `r1_control.authority` 행과 `r1_control.target_identity`를 삽입한 뒤, 폐기된 승인/잘못된 operator role/다른 plan을 가리키는 DB 행/다른 incarnation fence/만료된 decision deadline에서 거절을 확인하고, 계획된 효과의 admitted, 일반 서명 receipt가 기존 `verify_capability`로 통과, audit·outbox가 비어 있고 connection이 `IDLE`인 것을 확인한다. 이 receipt는 다른 capability와 동일하게 같은 signer·verifier·trust·validity 규칙을 쓴다.
- `issue_receipt.py`의 `nativeCommitGuard`(`plan`, `planDigest`, `operatorDatabase`, `operatorTls`, `approval`, `fence`, `deadlineSeconds`, 선택 `identity`)는 `actor_role`을 `operatorDatabase.user`에서 유도하고, 인증된 `ProtectedClock`을 필수로 하며, readonly/autocommit `PostgresTLS`를 쓰고, 승인의 `plan`이 pin된 `planDigest`와 같아야 하고, authority와 fence target이 일치해야 한다.
- **검증**: `main` 전체 **382 passed / 89%** statement, Ruff 통과. `ops` **98 passed**, Ruff 통과. (`ops`는 `ops/`에서 실행한다 — `ops/platform-integrity/`는 CLI 패키지이고 테스트가 없다.)
- Step 6은 **미체크 유지**. 위 증명은 전부 폐기 가능한 disposable realm 증명이지 9개 물리 operator capability 증명이 아니기 때문이다. purpose Keychain, live chrony NTS, production 동일 DB role, 암호화 backup·restore, 03:00 Asia/Seoul scheduler, 127.0.0.1:18101 5 rps x 600초 native 수용 시험, launchd test/production rehearsal, registry publication, `CVE-2026-85091`은 그대로 열려 있다. G1 미통과.

### REM-1 Step 6 target effect adapter 구현 (2026-09-26T18:05:00Z)

- Step 6의 핵심 산출물이 실제로 **없었**음을 확인했고 구현했다. control plane이 `UNKNOWN`을 durable하게 기록하고 authority가 admitted 해도, 효과를 실제로 수행하고 그 ledger 행을 **같은 target transaction**에 기록하는 경로가 없었다.
- `migrations/006_target_effects.sql`을 추가했다. `r1_control`과 의도적으로 분리한 `r1_target` 평면에, compare-and-set이 움직이는 정확한 native digest를 가진 `state` 행과 run/step/attempt/fence epoch에 묶인 append-only `effect_ledger` 행을 둔다. `(run_id, step, fence_epoch)` 유니크 인덱스가 세션 lock 뒤에서도 중복을 DB가 거부한다.
- `adapters/target_effect.py::PostgresTargetExecutor`를 추가했다. 효과마다 전용 physical autocommit connection을 열고 session-level `pg_advisory_lock`을 효과 전체 동안 잡고, guard의 프로토콜을 그대로 구동한다: `guard()` → target transaction 하나 → `expected_before` compare-and-set → state write → ledger 행 → `before_commit()`. finalizer의 `FOR SHARE` 재조회가 **효과를 쥔 transaction 안에서** 일어나므로 이것이 revoke와 commit을 직렬화한다. lock이 session 수준이라 crash 시 해제되고, unlock 실패는 `close()`가 해제하므로 삼켜서 실제 결과를 가리지 않는다.
- 실패 분류가 이 어댑터의 존재 이유이므로 명시했다. 거절된 statement·`MutationUnavailable` 거절·stale precondition은 **증명 가능한** 미적용이므로 그대로 전파하고, 연결 상실(`OperationalError`)만 `TargetOutcomeUnknown`이 된다 — 그 경우 효과는 durable일 수 있어 성공도 실패도 말하면 안 된다. 해소는 `observe()`뿐이고 read-only(`SET TRANSACTION READ ONLY`)다. ledger 행은 commit을 증명하고, 대상이 그대로면 조용한 abort를 증명하며, 그 외 digest는 아무것도 증명하지 못하므로 `UNKNOWN`을 유지한다.
- `tests/test_target_effects.py` 16건으로 Step 6 fault case 4종을 cover했다: 동시 target writer 2개(정확히 하나만 적용, loser는 분류된 사유로 거절 — crash나 두 번째 ledger 행이 아님), 갱신된 fence epoch이 이미 이동한 precondition을 다시 무장시키지 못함, index가 위조된 중복을 거부, 효과 이전 revoke, **transaction 중간에落地한 revoke**, 효과 write 뒤 rollback이 state와 ledger를 함께 되돌림, rollback 후 session lock 누수 없음, commit reply 상실 시 효과가 durable한 채 호출자는 UNKNOWN을 받고 이후 맹목적 재시도가 불가능함, 그리고 drift한 대상이 UNKNOWN을 유지하는 관측 3종.
- mid-transaction revoke 시험은 mutation으로 load-bearing임을 확인했다. finalizer 재조회를 삭제하면 **이미 폐기된 authority로 효과가 commit**되고 시험이 실패한다. 이것이 step이 금지한 privileged-apply 위험이며 이제 회귀시험으로 고정했다.
- 내 시험 버그 2건도 실제 동작에 맞춰 바로잡았다. ① `check_binding`이 `PermissionError`를 raise하고 이는 `MutationUnavailable`의 **상위** 클래스라 단언은 상위 클래스를 기대해야 했다. ② target이 인정하지 않은 fence epoch은 out-of-scope로 거절되므로, "새 fence" 시험이 진짜 compare-and-set을 검사하려면 먼저 `r1_control.target_identity.epoch`을 올려야 한다.
- **검증**: `main` **398 passed / 89%** statement(`target_effect.py` 96%), Ruff 통과. `ops` 98 passed. Step 6은 여전히 **미체크** — target executor도 폐기 가능한 disposable realm에서만 증명됐고 물리 operator capability는 그대로다. G1 미통과.

### Step 6 append-only 강제와 scoped DB command role (2026-09-26)

- Step 6이 요구한 "append-only critical events/outbox와 scoped DB command role"은 둘 다 **주석일 뿐
  메커니즘이 아니었다.** `001`/`006`은 "append-only"라고 적어두었지만 session role이 자유롭게
  `UPDATE`/`DELETE`할 수 있었고, 프로세스가 테이블에 직접 쓰는 것을 막는 장치도 없었다.
- `migrations/007_command_roles.sql` 추가. NOLOGIN group role `r1_target_owner`/`r1_target_operator`/
  `r1_target_auditor`를 만들고, `r1_target_operator`는 어떤 테이블에도 INSERT/UPDATE/DELETE/TRUNCATE
  권한이 없고 `r1_control`에는 아무 권한도 없다. 유일한 write 경로는 `SECURITY DEFINER` 함수 하나의
  EXECUTE뿐이다.
- `r1_target.effect_ledger`와 `r1_control.outbox`이 `UPDATE`/`DELETE`뿐 아니라 **`TRUNCATE`도 거부**한다.
  row-level trigger는 `TRUNCATE`에 아예 발동하지 않으므로 statement-level guard가 추가로 필요하다. 이것이
  없으면 append-only 속성이 조용히 거짓이었고 mutation으로 확인했다.
- `r1_target.apply_effect(...)`는 scalar만 받고 compare-and-set 대상을 고정하며 row lock을 자신이 取한다.
  그리고 **authority를 스스로 재검증한다.** Python guard는 defense in depth이지 강제 경계가 아니다 —
  이 migration의 첫 버전은 guard 없이 scoped role이 **폐기된(revoked) authority로 효과를 적용**할 수
  있게 했다. 이제 DB가 폐기/비-apply/retarget/out-of-epoch grant를 직접 거부한다(`R1T02`),
  compare-and-set 실패는 `R1T01`. 거절 사유는 명시적 SQLSTATE로 두고 어댑터는 메시지 문자열이 아니라
  코드로 분류한다.
- 의도적으로 **guard에 남겨 둔** 검사 2건이 있고, 이를 migration과 operator handoff에 명시했다(누락이
  아니라 설계): ① **만료** — SQL에서 판정하면 보호된 chrony/NTS clock이 아니라 `clock_timestamp()`을
  신뢰하게 된다. ② **어느 DB role이 어떤 approval을 쓸 수 있는지** — Step 10이 아직 제공할 role mapping이
  필요하다. cross-target escape는 완전히 막혔지만 session↔approval identity 바인딩은 아직 없다.
- `adapters/target_effect.py`가 Python에서 ledger digest와 `applied_at`을 계산하지 않는다 — DB가 둘 다
  기록한다. CAS가 SQL로 옮겨가면서 try 블록 안에서 raise될 수 없게 된 `except TargetStateChanged`는
  죽은 코드라 삭제했다.
- `tests/test_target_effects.py`는 **28건**, `adapters/target_effect.py`는 statement **100%**. ledger/outbox의
  UPDATE/DELETE/TRUNCATE 거부, operator role의 write 권한 전무, auditor read-only, cross-target/
  cross-incarnation 거부, 비-apply grant 거부, stale epoch 거부, **guard가 읽은 뒤에落地한 revoke**를
  command가 잡는 것, scoped read-only reconciliation, unlock 실패가 실제 결과를 가리지 않음을 함께 고정한다.
- 새 강제 장치는 전부 **mutation으로 확인**했다. `revoked`/`target`/`namespace`/`incarnation`/`purpose`/
  `epoch` 술어를 하나씩 지우면 각각 이름 있는 시험이 실패하고, scoped grant나 TRUNCATE guard를 지워도
  실패한다. 이 과정에서 글로는 놓친 실제 구멍 2개를 찾아 막았다: 어떤 시험도 덮지 않던 cross-target
  escape, 그리고 시험이 없던 `purpose` 술어.
- test hygiene 결함도 우회하지 않고 고쳤다: `tests/test_reader_roles_postgres.py`는 모든 migration을
  적용하면서 `r1_control`/`r1_audit`만 지워서 `r1_target` 잔여물과 충돌했다.
- **검증**: `main` **413 passed / 90%** statement(`target_effect.py` 100%), Ruff 통과. `ops` **98 passed**,
  Ruff 통과. `git diff --check` 통과. Step 6은 여전히 **미체크** — 물리 operator capability와 Step 10의
  role mapping이 그대로다. G1 미통과.

### REM-1 Step 6 durable dispatch / conservative reconciliation (2026-09-27)

- Migration 008과 `application/dispatch.py::RunDispatcher`를 추가했다. control UNKNOWN/audit/outbox의
  commit 응답 뒤에만 target apply를 호출하고, 결과 기록과 명시적 read-only reconciliation을 연결한다.
  어떤 실패에서도 자동 재실행하지 않는다.
- 이전 observer가 미commit writer를 abort로 판정하고, 다른 plan/effect에 ledger를 재사용하며,
  ledger 존재를 과거 authorization 증거로 승격하는 결함을 재현·수정했다. direct SQL commit 직전의
  revoke도 deferred constraint/SHARE lock으로 차단한다. 초기 회귀시험 9건이 이전 코드에서 실패했다.
- v2 receipt는 target/namespace/incarnation/plan/approval과 전체 effect를 결속한다. 기존 행은 수정하지
  않고 미확인 provenance로 남긴다. target-wide exclusion, epoch rewind 거부, bounded lock wait,
  read-only repeatable snapshot을 적용했다. 부재만으로 abort를 단정하지 않는다.
- 응답 유실 뒤 실제 commit을 확인해도 과거 권한 증거가 없으면 COMMITTED/PAUSED다. 확인된 live guarded
  commit만 verified completion을 기록할 수 있고, reconciliation은 별도 current purpose 권한을 재확인한다.
- 검증: platform **456 passed / 90%**, target adapter와 dispatcher **100%**; ops **98 passed**;
  Ruff/`git diff --check` 통과. Hypothesis seed **20260927**, 신규 failure-cut property release profile
  (2,000-example limit) 통과. 기존 Starlette/httpx deprecation warning 1건.
- Step 6/G1 미완료: native protected clock/current source, session-to-approval role mapping 및 실제
  non-superuser helper composition 인수가 남아 있다. 현재 control-purpose port/시계는 시험용 공급자이며
  실제 operator capability receipt로 계산하지 않는다. 구체 경계와 확장별 상태는 최신 code summary 참조.
- Preserved WT에 변경 13개 파일의 byte parity를 확인했고, WT platform **456 passed** 및 Ruff 통과를
  재현했다. 이번 세 하위 구현/기록 항목은 완료, 상위 Step 6은 인수 미완료 상태를 유지한다.

### REM-1 Step 6 current-source / login binding (2026-09-27)

- Migration 009: approval revision/actor를 실제 login 이름과 PostgreSQL role OID에 불변 결속한다.
  owner/member/table-write 권한을 가진 login은 provisioning에서 거부하고, 동일 revision 재할당 및
  role 삭제·재생성으로 기존 권한을 재사용하는 경로를 차단했다. bind/revoke와 audit/outbox는 원자적이다.
- `PostgresOperatorAuthority`가 scoped source read/finalization 함수를 사용한다. process role에
  authority-table UPDATE를 주지 않고, function owner가 SHARE lock을 수행한다. 직접 target SQL도
  mapping을 insert/commit에서 확인한다.
- `PostgresCommandAuthority`로 run/reconcile의 현재 source·scope·revision·protected time을 재확인하고,
  `build_operator_dispatcher`가 frozen step/precondition/postcondition, TLS identity, 원 deadline을
  묶는다. `PostgresTLS.open`은 temporary credential 정리 후 caller-owned physical connection을 제공한다.
- 초기 actual-login 회귀시험 2건(정상 helper 거부, 타 login의 승인 재사용)이 이전 코드에서 실패했고
  수정 후 통과했다. 실제 non-superuser login으로 revoke 순서/감사 rollback/OID/revision/clock 실패를 검증했다.
- 검증: platform **496 passed / 90%**, helper/TLS adapter **100%**, command authority **97%**;
  ops **98 passed**; Ruff/`git diff --check` 통과. 신규 source-scope property release profile
  (2,000-example limit), seed **20260927** 통과. 기존 Starlette/httpx warning 1건.
- Step 6/G1 미완료: control checkpoint store의 scoped command 및 helper preparation provenance 강제,
  실제 purpose Keychain/NTS/mTLS 배포 인수가 남아 있다. 새 시험의 target/source login은 실제 비관리자이나,
  control store는 owner-backed fixture이고 시계는 synthetic protected frame이다.
- Preserved WT에 17개 변경 파일의 byte parity를 확인했고 platform **496 passed** 및 Ruff 성공을 재현했다.
  이번 세 하위 구현/검증 항목을 완료로 표시했다. 상위 Step 6과 G1은 계속 미완료다.

### REM-1 Step 6 scoped coordination / prepared execution (2026-09-27)

- Migration 010/011 및 `ScopedPostgresRunStore`/`build_scoped_operator_dispatcher` 추가. register,
  attempt, prepare, reconcile/read를 고정 native command로 수행하고 process raw table write를 거부한다.
- UNKNOWN/audit/outbox의 synchronous COMMIT 응답 뒤에만 private dispatch secret을 내보낸다. DB에는
  hash만 보존하며 readonly history/repr/일반 직렬화에서 복구할 수 없다. Target은 독립 commit된 exact
  checkpoint/audit/outbox, executor OID/revision, secret을 검증한다. Legacy apply signature는 제거했다.
- 보호된 helper의 guard 뒤 동일 effect transaction에 finalization witness를 기록한다. Witness 없는
  commit은 거부하고, coordinator의 성공/인가 boolean 대신 native evidence로 완료를 판정한다. Reply 유실도
  witness가 보존됐으면 명시적 reconciliation으로 복구한다. Source epoch CAS도 비관리자 admin command로
  감사와 원자 처리한다. 등록부터 다단계 완료/펜싱 복구까지 runtime owner credential이 필요 없다.
- 검증: platform **522 passed / 90%**, ops **98 passed**, Ruff/`git diff --check` 통과. SQL codec과
  Python RFC8785 oracle 및 dispatcher failure-cut property release profile 통과, seed **20260927**.
  새 profile의 synchronous commit/보호된 helper provenance가 내구성 근거이며 global WAL pointer를 특정
  commit 증거로 오인하지 않는다.
- Readonly host preflight(증거 bundle 미제공, peak=0): ready=false, provenCapabilities=[] 및 receipt
  malformed 5건. FileVault/drive/최소 10 GiB 여유 검사는 통과했다. 공급자 부재나 실제 배포 peak의 증명이
  아니다. Owner-reviewed 설치/실제 Keychain/NTS/mTLS/receipt 인수가 남아 Step 6/G1 미체크를 유지한다.
- 변경 19개 파일의 preserved WT byte parity를 확인하고 WT **522 passed**/Ruff 성공을 재현했다.
  Scoped coordination/prepared execution 코드 하위 항목은 완료, 물리 인수 항목은 미완료로 분리했다.

### REM-1 물리 clock 번들 준비 및 CVE-2026-82049 수정 (2026-09-27)

- `ops/platform-integrity/provision_clock.py`의 `fetch/build/refresh/seal/backport/rehearse/install/probe/uninstall`으로
  pinned Darwin arm64 clock bundle을 root 없이 준비했다. 최종 provisioner를 반영해 다시 seal한 결과는
  **2248 files / 97,622,694 bytes**, manifest
  `98e91b42351467fd8ae3d3275a662b36753280631caea72ac275f1cdd2975a99`, installer
  `fef411e86c5eb427cee969b71713b0c5063058c5d7959dda4f5208fef4bb9cad`. Plan-only `install`은
  `PLAN_ONLY`/`ready=false`를 반환하며, seal 후 provisioner 바이트가 바뀌면 `invalid reviewed clock bundle`로
  거부한다. (직전 stale manifest `f8410079…`/`5805b315…`는 폐기됐다.)
- Fresh Grype capture가 High 1건 `CVE-2026-82049`(python 3.13.15, fix는 3.14.0b1만)을 보고했다. PSF
  advisory와 backport `b8f23e307097552eaea2604383a12ab280520d0d`를 받아 pinned preimage에 byte-for-byte로
  적용하고 stale `tarfile` bytecode를 제거했다. 부팅 extraction은 이제 hard-link member 자체를 거부하므로
  patch 이전의 취약 경로도 닫는다. Upstream 회귀가 `data`/`tar` 양쪽에서 통과하며 backport는 idempotent,
  미인정 staged module·검증 불가 preimage·root 실행을 거부한다.
- Grype은 CPE version string으로만 판정해 backport를 인식하지 못한다. 그래서 finding을 억제하지 않고
  `sbom-targets.json`에 `PREPARED_NOT_INSTALLED_PENDING_OPERATOR_ACCEPTANCE`로 남겨 operator 승인을 받는다.
- 검증: `main` ops **125 passed**/Ruff 통과. 부팅 non-root rehearsal은 `time.cloudflare.com`의 authenticated
  NTS까지 도달하고 400개 실행 image가 frozen closure 안에 있음을 확인했지만 `NTS_OBSERVED_NOT_ACCEPTED`로
  종료했다(의도된 결과).
- **미완료**: root `install --apply`/`probe`, NTS 서명 receipt, purpose Keychain, mTLS role, backup/restore,
  03:00 scheduler, 5 rps load, registry publication. `CVE-2026-85091`도 그대로 blocker다. Step 6/G1 미체크.
- 계획/audit/handoff 문서를 갱신했지만 현재 manifest와 preimage refactor는 아직 preserved WT에 동기화되지 않았다.

### REM-1 clock 설치 인계 보정 (2026-09-28 local)

- 위 2026-09-27 checkpoint의 manifest는 superseded다. 현재 값은
  `509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752`, installer는
  `efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67`이다.
  2248 files / 97,622,694 bytes이며 SBOM의 2251-file 오기를 바로잡았다.
- Installer가 독립 pin으로 PSF patch metadata/postimage와 bytecode 부재를 검사한다. `backport` 검증은
  candidate를 고치지 않고 실행 전후 manifest를 검증하며 proof에 manifest/release를 결속한다.
- 검증한 system CA와 별개로 mutable staging CA를 설치하던 race를 실패 재현 후 수정했다. 실제 root
  설치 시험은 아니며 root-only 복사/설치/probe/rollback 명령을 handoff §12에 정확히 기록했다.
- Main ops **137 passed**, clock **39 cases**, 생성 property 2개 각 2,000 examples, seed **20260928**,
  Ruff 성공. System Python plan-only와 실제 frozen-runtime PSF 회귀도 통과했다.
- Raw scan-handoff: 51 components / 8 findings / 1 High / 0 ignored / BLOCKED. PSF 수정 증거는 별도이며
  release 승인/예외를 만들지 않았다. 이전 400 executable mappings는 chronyd의 관측이며 설치된 Python의
  관측으로 해석하지 않는다.
- 현재 변경 8개 파일의 preserved-WT byte parity를 확인했고 WT도 **137 passed**/Ruff 성공을 재현했다.
  Artifact/scan/proof digest, Bash/Zsh 명령 구문, Markdown/JSON 및 git diff --check 통과. Local sudo
  인증과 실제 install/probe/서명 receipt가 다음 단계이며 Step 6/10과 G1은 계속 미체크다.

### REM-1 clock 설치 완료 / native probe 차단 원인 확인 (2026-09-28)

- Operator가 기존 manifest `509b5074…`/installer `efb6145b…`로 실제 root 설치를 수행했다.
  `INSTALLED_NOT_ACCEPTED`, deployment digest `ac0c16bb…`, clock job 2개 등록을 보고했고 readonly
  OS 관측으로 등록을 확인했다. 보호된 실행본은 `/private/var/root/docsuri-clock.dAZVUkTy/provision_clock.py`다.
- Probe는 `native_runtime_unavailable`로 실패했다. Observer/periodic job의 exit 2와 UNAVAILABLE frame을
  확인했다. 원인은 UID 608 launcher가 읽어야 하는 `deployment.json`을 root:wheel 0400으로 설치한 코드
  결함이다. 설치된 Python의 non-root read가 EACCES로 실패하는 것도 재현했다.
- Source는 root-owned 0444 metadata를 발행하고 installed-state 검사에 mode를 포함하도록 수정했다.
  Owner/reader를 분리한 회귀 4개가 수정 전 실패/후 통과했다. Platform **528 passed / 90.33%**,
  ops **137 passed**, Ruff 및 wheel build 통과. 기존 frozen bundle/installer는 복구용으로 유지한다.
- 다음 operator 작업은 handoff §13의 checksum 검증 → 해당 manifest만 0444 → observer kickstart →
  기존 protected installer의 probe다. Agent는 sudo 인증이 없어서 이 복구를 실행하지 않았다.
- Native probe/clock capability receipt는 미완료, Step 6/10/G1도 계속 미체크다. 변경 8개 파일의 WT byte
  parity 및 launcher 39 tests/Ruff를 확인했다. 복구 명령의 Bash/Zsh 구문·digest, Markdown/JSON과
  git diff --check도 통과했으며 다음 입력은 operator 복구/probe 결과다.

### REM-1 mode 복구 후 잔여 launch 실패 — 진단 준비 (2026-09-28)

- Operator가 §13 checksum/mode/kickstart를 실행했다. 실제 manifest mode는 0444이고 checksum은 모두
  일치한다. Observer는 run 2/exit 2, sampler도 exit 2이며 public frame은 계속 UNAVAILABLE다.
- 설치된 interpreter로 manifest/account/2247 artifact(97,140,890 bytes)를 UID 501에서 검증했다.
  이 성공은 실제 UID 608의 kernel group/launch 동작 증명이 아니다. 잔여 원인은 아직 확정하지 않았다.
- `diagnose_clock_launch.sh`를 준비했다(SHA256 `410016041adc71e2a503848446ee3ac1a222d73571976e0bf2202ef41869ecbe`).
  실제 observer의 다음 launch만 진단으로 대체해 UID/GID/kernel groups와 guard exception을 출력하고
  target exec 직전에 중단한다. Root 실행 거부/15초 한도/오류 길이 제한과 accepted=false를 적용했다.
- Helper 회귀 4개 및 ops **141 passed**/Ruff/shell syntax 통과. 실제 UID-501 smoke는 예상된 role-boundary
  refusal을 출력했다. 실제 UID-608 결과는 operator의 handoff §14 실행을 기다린다.
- 진단 산출물/문서 8개 파일의 WT byte parity와 WT helper 4 tests/Ruff를 확인했다. Script/digest,
  Bash/Zsh handoff 구문, Markdown/JSON 및 git diff --check 통과. 다음 작업은 operator의 실제 launch-context
  JSON 수집이다. 물리 probe/receipt 및 Step 6/10/G1은 계속 미완료다.

### REM-1 diagnostic 실행 순서 보정 (2026-09-28)

- Operator의 diagnostic copy SHA 검증과 debug 설정은 성공했다. 실제 `launchctl debug` PID 72641은
  foreground에서 대기 중이고 observer runs는 여전히 2다. 뒤에 `&&`로 연결했던 kickstart는 실행되지 않았다.
- Handoff §14를 두 Terminal로 수정했다. 기존 Terminal A를 유지하고 Terminal B에서
  `sudo /bin/launchctl kickstart -p system/org.docsuri.rem1.test.nts-observer`만 실행하면 된다.
  Diagnostic JSON은 Terminal A에서 수집한다. 실제 서비스-context 결과와 native clock 인수는 계속 pending이다.

### REM-1 native group 원인 확정 / root bootstrap 복구 준비 (2026-09-28)

- 실제 diagnostic PID 69943: UID/EUID/GID/EGID 608, kernel groups `[608,12,61,100]`, launch_guard에서
  `runtime role boundary not established`. InitGroups=false만으로는 이 host의 group 격리가 성립하지 않았다.
- Renderer를 root:wheel bootstrap + Python -I -B로 수정했다. 기존 frozen launcher에 이미 존재하는
  manifest/artifact 검증 → setgroups([]) → setgid → setuid → native 재검증 → target exec 경로를 사용한다.
  허용 group을 늘리지 않았고 실제 clock target은 UID/GID 608로만 실행된다.
- 기본 PLAN_ONLY인 `repair_clock_groups.py`는 기존 bundle/provisioner/deployment와 두 plist preimage에
  고정된다. 원 설치의 모든 artifact/CA를 검증하고 두 job 중지 후 세 필드만 변경하며 bootstrap 실패/중단은
  미확정 start를 포함해 두 label 모두 정리한다. 수리 script SHA256:
  `9fc69cb3b2ec72bcd30b5eea4770b58de8e6455617ce750a9d4a6dabec3e3812`.
- 실제 설치에 대한 System-Python plan-only가 통과했고 renderer와 repair의 새 plist digest가 일치한다.
  Platform **534 passed / 90.42%**, ops **156 passed**, repair 15 cases/2,000-example property, Ruff 통과.
- 다음 operator 작업은 기존 debug Terminal에서 Ctrl+C 후 handoff §15의 보호된 repair copy/plan/apply/probe다.
  Root apply/실제 clock probe/서명 receipt는 아직 미완료다. 변경 10개 파일의 WT byte parity와 launcher
  45/repair 15 targeted tests, Ruff, wheel build, handoff 구문/문서/digest 검증을 마쳤다.

### REM-1 group 복구 적용 / reader 재확인 대기 (2026-09-28)

- Operator의 root repair는 REPAIRED_NOT_ACCEPTED로 완료됐다. 두 plist hash가 정확히 일치하고
  chronyd PID 87325의 실제/effective UID/GID는 608이다. Periodic publisher도 exit 0이며 NTS frame은
  authenticated/AVAILABLE 상태다.
- 첫 probe는 collector와 reader identity/group 검사를 통과한 후 ProtectedClock에서 실패했다.
  해당 실패 frame은 보존되지 않아 정확한 원인은 미확정이다. Startup uncertainty/publication race는
  가능성일 뿐 확정 원인으로 기록하지 않는다.
- 현재 installed ProtectedClock는 inspector UID 501에서 20초간 5/5 통과했다. Window width는
  498018~602966 us로 약 ±0.25~0.30초다. Config/boot/resume, 파일 writer/mode/link도 일치한다.
- Handoff §16의 기존 protected probe만 재실행해 UID 600의 current-read/쓰기·socket 거부를 확인한다.
  재설치/repair 재실행은 필요하지 않으며 최종 native reader/서명 receipt와 Step 6/10/G1은 pending이다.

### REM-1 live NTS / isolated reader 인수 통과 (2026-09-28)

- Operator 재실행이 **NATIVE_CLOCK_PROBED**로 통과했다. Collector OBSERVED, reader CLOCK_READ_VERIFIED,
  frame write 및 chrony command socket 접근 거부가 모두 true다. Window는
  `[1790599834753553,1790599834989279]` us (폭 235726 us, ±117863 us)다.
- `capabilityReceiptIssued=false`를 유지한다. Live collection/reader isolation checkpoint는 완료했지만
  signed receipt와 남은 expiry/reboot 및 전체 Step 6/10/G1 인수는 별도다.
- `clock-receipt.test.json` reference-only 설정을 준비하고 issuer --probe-only를 실측했다. nts_clock은
  proven=true/verified, 나머지는 설정 미제공으로 not_configured, 전체 exit 2다. 키/서명은 사용하지 않았다.
- 다음 구현은 role-scoped Keychain signer/frozen issuer, ProtectedClock 기반 validity, 독립 release-trust
  anchor 배선이다. 현 bootstrap CLI의 PEM/local-wall-time/evidence-named-trust 경로를 production 인수로
  간주하지 않는다. 그 후 fresh probe 기반 nts_clock receipt를 발급/검증한다.
- 이번 reference/evidence 문서 7개 파일의 WT byte parity, installed clock reference/reader-window 검증,
  Markdown/JSON/shell parsing 및 git diff --check를 확인했다. Runtime 코드 변경이나 추가 repair 실행은 없다.

### REM-1 보호된 receipt 서명 경로 완성 / 실제 발급은 operator 대기 (2026-09-29)

- **PEM 절차는 폐기되었다.** `--key`/`--key-id`/`--out`은 probe-only가 아닌 실행에서
  `protected_signing_required`로 거부되고 파일이 생기지 않는다. trust는 evidence가 아니라 **root 소유
  0444 policy**에서만 오며, evidence 안의 `trustKeys`는 `evidence_invalid_or_contains_trust`로 거절된다.
  서명 키는 purpose Keychain 안에만 존재한다.
- **root-side provisioner**(`ops/platform-integrity/provision_receipts.py`)를 추가했다. NTS artifact
  digest를 설치된 root 소유 `deployment.json`에서 유도하고(설치 바이트가 manifest와 다르면 거절), Ed25519
  키를 메모리에서 생성해 ACL이 issuer interpreter로 묶인 Keychain에 넣고, policy는 root 0444로 atomic
  기록한다. trust window는 배포된 인증 clock 기준(now − 1일, 최대 7일)이다. 비밀번호는 `getpass` 2회.
  인자 오류는 비밀번호를 묻기 **전에** `stage=arguments`로 거절한다.
- **issuer에 `--keychain-password-stdin`**을 추가했다. provisioner가 남긴 locked Keychain을 서명
  동안만 signer role로 unlock하고 `finally`에서 다시 lock한다. 비밀번호는 stdin 한 줄(12..1024 B)이며
  argv·환경·로그에 나타나지 않는다.
- **실제 macOS Keychain end-to-end이 증명됐다**: `SecKeychainItemCreateFromContent`로 ACL을 생성 시점에
  부여해 interactive authorization 대기가 사라졌고, locked 상태 서명은 `purpose signing key`로 거부되며,
  올바른 비밀번호로 unlock 후 실제 서명 → 0444 publication → **독립 policy가 `verified`로 수락**한다.
  같은 purpose 슬롯의 다른 키는 거부되고 잘못된 비밀번호로는 unlock되지 않는다.
- **테스트**: ops 179 passed, platform 382 passed + 185 skipped(전부 기존 격리 DB integration skip),
  양쪽 Ruff clean. 이번에 추가한 것은 provisioner 11개(인자 선검증, 링크/쓰기 가능/크기 제한 거부,
  다른 release·drift 거절, 다른 소유자 경로 거절), issuer 2개(stdin 비밀번호 경계, unlock→lock 순서와
  비밀번호 없을 때 무접촉), native 3개이다.
- **남음(전부 operator)**: FileVault On 확인, sudo provisioner 실행, 실제 `nts_clock` 발급과 preflight
  검증. 이 호스트에는 signer Keychain·key·trust policy·서명 receipt가 하나도 없어
  `capabilityReceiptIssued=false`를 유지한다. Step 6/10/G1 미체크 유지. clock scan `BLOCKED`
  (`CVE-2026-82049`)와 `CVE-2026-85091`은 별개로 열려 있다.
- 기록: handoff 8절에 폐기 고지를 넣고 8A절에 3단계 operator runbook(소유권·mode 표 포함)을 추가했다.
  `sbom-targets.json`은 python **project** 단위라 `provision_receipts.py` 추가로 변경이 없다.

### REM-1 reaped 임시 디렉터리 복구 (2026-09-29)

- macOS가 `/var/folders/.../T/opencode/`를 정리해 prepared bundle, `scan-handoff`, 보존 worktree가
  사라졌다. `git worktree prune`로 stale 등록만 제거했다. worktree reflog가 **단 한 줄**(초기 checkout
  `32a424d1`, commit 0개, branch 0개)이므로 git 쪽에 잃을 고유 내용은 없었다. 같은 경로에 worktree를
  재생성했다.
- **주의:** `platform_integrity/`와 `ops/platform-integrity/` 구현 전체가 **untracked**다. `32a424d1`은
  그 이전 커밋이라 worktree checkout만으로는 코드가 없다. 디렉터리를 만들어 24개 파일을 복사했고
  **parity 불일치 0건**이다.
- **설치본은 살아 있고 이제 repo 안에 증명이 있다.** root 소유 `deployment.json`을
  `aidlc-docs/construction/rem-1-platform-integrity/code/installed-deployment-manifest.json`(0444)으로
  회수했다. digest가 기록값 `ac0c16bb…`과 **정확히 일치**하고 **2247/2247** artifact digest가 설치
  파일과 재검증됐다. launch entry `nts-observer`/`clock-sample`(608/608)도 정상이고
  `receipt-policy/`·`receipt-public/`는 여전히 부재해 provisioner 미실행이 확인된다.
- **bundle은 사라진 게 아니라 재생성 가능하다.** builder가 repo 안에 있고 입력 digest가 고정되어 있다.
  2026-09-29 `fetch` 재실행으로 chrony `4924c6f5…`·CPython `064afb7c…`가 재다운로드·재검증되었다.
  handoff에 fetch→build→refresh→seal 순서와 `509b5074…` manifest gate를 기록했다. gate가 통과해야
  검토된 artifact로 인정하고, 아니면 **설치 금지**다.
- **`scan-handoff/`는 영구 손실이다.** 51 components / 8 findings / High `CVE-2026-82049` / 0 ignored는
  `audit.md` 산문으로만 남았고 재생성에는 network·Grype·derived image가 필요하다. scan은 **미재현**으로
  기록한다.
- **여전히 막힘:** `probe()`가 `verify_bundle(work, …)`를 호출하므로 bundle 없이는 native probe를 돌릴
  수 없다. 무거운 `build` 단계(CPython 컴파일, 여유 디스크 20 GiB/용량 96%)는 승인 없이 실행하지 않고
  확인 대기한다. FileVault·root provisioner·실제 발급은 그대로 operator 대기이며 Step 6/10/G1은
  미체크를 유지한다.

### REM-1 bundle 재구성 시도 — manifest gate에서 거부 (2026-09-29, 위 「재생성 가능」 진술 정정)

- **아래는 내가 앞에서 남긴 「bundle은 재생성 가능하다」는 기록을 정정한다. 재생성되지 않는다.**
- `fetch`는 여전히 동작한다. chrony `4924c6f5…`·CPython `064afb7c…`는 digest 고정이라 재다운로드·재검증에
  성공했다. **그러나 CPython 입력은 source compile이 아니라 prebuilt python-build-standalone 아카이브**라
  `build`는 15초 만에 끝났고, 내가 미리 말한 "CPython 컴파일·수 GiB·장시간"은 틀렸다.
- **gate 실패**: `build` `3749899e…`(2056 files/93,252,270 B) → `refresh`·`seal` `290aa5e0…`
  (93,252,271 B). 검토본은 `509b5074…`(2248 files/97,622,694 B). **설치는 시도하지 않았다.**
- 회수한 설치 manifest와 diff한 결과가 결정적이었다. (1) `runtime/lib/python3.13/**/__pycache__/*.pyc`
  **196개 결손** — 원본은 precompiled bytecode를 포함했고 rebuild는 하나도 없다. (2) **5개 신규** —
  `config/deployment.json`과 오늘 작성한 receipt 소스 4개. (3) **digest 9개 상이** — `native/chronyd`,
  `native/chronyc`(재컴파일), `cffi`/`docsuri_platform_integrity` `RECORD`, `direct_url.json`,
  `uv_cache.json`, 수정된 소스 2개.
- **원인**: bundle은 이 repo의 소스 트리와 bytecode cache를 품는 **시점 고정본**이라, 이후 트리에서
  재구성하면 반드시 다른 artifact가 된다. `install`는 전달된 digest만 확인하므로 rebuild 자신의
  `290aa5e0…`를 넘기면 **검토되지 않은 바이트가 설치된다.** 293 MB짜리 non-conforming rebuild은 삭제했다.
- **인수 영향(영구)**: `probe()`가 `verify_bundle(work, …)`로 시작하므로 **이 release의 native clock probe는
  이제 재실행할 수 없고 `509b5074…` pin은 다시 충족될 수 없다.** 기록된 `NATIVE_CLOCK_PROBED`는 실행된
  증거로 남지만 재현·재검증은 불가능하다. 향후 clock 재설치는 **새로 build하고 새 pin을 검토한 뒤**
  새 manifest digest와 새 `tarfile-remediation` 증명이 필요하다. 옛 pin으로 re-seal하지 말 것.
- FileVault·root provisioner·실제 발급은 그대로 operator 대기이고 Step 6/10/G1은 미체크를 유지한다.

## CONSTRUCTION / Step 11 — R1C 읽기 표면 보강 (2026-09-29)

`api/app.py`를 80줄짜리 골격으로 두고 "다음 미착수 unit"으로 적어 두었으나, 실제로는 Step 11의
요구사항 여러 개가 구현되지 않은 상태였다. 이번에 그 결함을 닫았다.

- **인증이 우연한 404였다**: 앱은 `scope`의 `client_certificate_fingerprint`를 *읽기만* 했고
  거부하지 않았다. 인증 게이트가 없어 무인증 호출자는 `service.read(None, …)`로 내려갔고,
  `CurrentReadAuthority.permits`가 우연히 거절해서 404가 됐다. 즉 fail-closed는 설계가 아니라
  우연이었다. 이제 `/internal/**`는 64자 소문자 hex 지문을 **요구**하고 아니면 401을 준다.
  `X-Client-Cert`·`X-SSL-Client-Cert`·`X-Forwarded-Client-Cert`·query parameter 네 경로 모두
  401로 테스트로 고정했다. 값이 비었거나 대문자·오길이·non-string이면 동일하게 401.
- **loopback 강제**: non-loopback peer는 고정 `not_found`로 응답한다. 데몬이 자기 존재를
  off-host에 확인해 주지 않기 위해 알 수 없는 경로와 구분되지 않아야 한다.
- **readiness가 세 층으로 나뉘지 않았다**: `subjectEligible`이 하드코딩 `null`이었다. 이제
  `shallow`(clock·reader 응답), `deep`(실제 bounded 관측 완주), `subjectEligible`(그 caller의
  grant) 를 분리 보고한다. subject 미지정 시에도 `False`이며 `null`이 되지 않는다 — readiness로
  subject 존재를 추론할 수 없다.
- **compatibility에 API가 아예 없었다**: `domain/compatibility.py`의 `evaluate_compatibility`는
  반환값이 `(verdict, reasons)` 튜플이라 직렬화할 수 없었다. `CompatibilityResult` value를 추가하고
  `/internal/v1/compatibility/{release}`로 노출했다. owner port 미provision이면 **503으로 fail-closed**이며
  관대한 기본값이 없다. verdict는 ELIGIBLE/STALE/BLOCKED/INCOMPLETE를 구분한다.
- **100-item 상한이 없었다**: 바이트 상한(1 MiB)만 있었고 항목 수가 없었다. 모든 항목을 가진
  필드(`evidence_ids`·`exception_ids`·`diagnostics`·`selections`·`reasons`) 합으로 상한을 건다.
- **실버그 2건 (작업 중 발견·수정)**:
  (1) `{subject}`는 `/`를 가로지르지 못하는데 `Ref` 패턴은 `/`를 허용한다(`repo/one`). 즉 그
  경로는 **어떤 subject에도 매칭되지 않았다** — `{param:path}`로 고쳤다. 값은 policy 키로만 쓰이고
  파일 경로가 되지 않는다.
  (2) 생성자 port와 메서드를 둘 다 `compatibility`로 지어 **인스턴스 속성이 메서드를 가렸다.**
  앱이 `service.compatibility(fp, release)`를 호출하면 port가 2인자로 호출돼 전부 503이었다.
  저장 이름을 `compatibility_source`로 분리했다.
- **테스트**: `tests/test_read_api.py` 24개 신설. platform **406 passed** + 185 skipped
  (기존 격리 DB skip, 전부 사전 존재), ops **179 passed** 불변, 양쪽 Ruff clean.
  기존 `test_readonly_api_does_not_trust_headers_or_fake_health`는 404 기대를 401로 교정했고
  TestClient의 기본 `testclient` host 대신 실제 loopback peer를 쓰도록 바꿨다.
- **남음(전부 operator/실물)**: 물리 mTLS Handshake, 512 MiB RSS + 64 MiB LRU 부하 검증,
  격리 실 store에 대한 실 endpoint 점검, native role acceptance. Step 11은 acceptance 미체크 유지.

## REM-1 Code Generation — Steps 7, 12, 14, 15 (2026-09-29)

Implementation obligations for four steps are now complete and verified. No step box is checked,
because each retains a physical or operator-gated acceptance item; the open items are named below
rather than left implied by a green test run.

- **Step 7 — generation/journal 경계**: `domain/generation.py` 신설, `adapters/filesystem.py`에
  `GenerationBoundary`·`PinRegistry`·durability receipt·검증된 metadata-only import·pin 보호
  collection·`_erase_tree` 추가. receipt/seal 중단, torn tail, stale head, 늦은 쓰기 descriptor,
  reader/backup pin, GC, import 검증, symlink 탈출, 복구를 테스트로 고정. 남음: **격리 APFS
  root**에서의 실측과 native durability 증명.
- **Step 12 — R1R + scoped helper**: `domain/actions.py` 신설(닫힌 action 어휘, role matrix,
  금지 request kind, 기계가독 실패 상태). `cli/__main__.py`는 명시적 action만 노출하고 기본
  apply 없음. `application/supervisor.py`는 이미 one-shot 의무를 모두 만족해 **변경하지 않았다**.
  남음: native role 바인딩, 실제 lost-receipt/중복 시도 rehearsal, 물리 mTLS handshake.
- **Step 14 — observability/retention/backup evidence**: `domain/retention.py`
  (request/run/effect 상관, 단조 relay cursor, 14일 ordinary/90일 critical, approval-bound GC —
  managed 집합 밖 레코드는 절대 삭제하지 않음), `domain/backup.py` (`BackupEvidence`,
  `evaluate_backup`, `cut_is_exact`). **모든 backup 신호는 미증명 값이 기본값**이라 archive 없음,
  원격 사본 미검증, clock/key 잠김, 미해결 writer, restore 미수행은 모두 `INCOMPLETE`이 된다 —
  부분 성공으로 흡수되지 않는다. 남음: `ops/server/`·`ops/local/` seam 배선, 암호화
  이동식 드라이브 archive, 새 target incarnation으로의 격리 restore.
- **Step 15 — CI/재현성**: `.github/workflows/ci.yml`에 nightly + `workflow_dispatch` 트리거,
  `rem1-closure-audit`(전체 — PR-diff가 아님 — closure 감사, 미처분 project는 조용히 버리지 않고
  경고로 표면화, digest 고정 검증), `pbt-full`(release 프로파일 2,000 / 200×100),
  `rem1-isolated`(harness 계약의 container를 provision해 185개 skip을 실제 실행으로 전환 +
  anti-vacuous-pass 가드), `macos-filesystem`(Linux 레인이 관측할 수 없는 APFS hardlink/symlink/
  rename 의미). 새 `ops/platform-integrity/validate_supply_chain.py`는 테스트로 고정되어 있다.
  남음: **closure 감사는 이 sandbox에서 실행 검증 불가**(`uvx pip-audit`이 `ensurepip` SIGABRT로
  중단)이므로 신규 포함 project는 CVE 처분 전까지 blocking이 아니라 report로 둔다.

### 작성 중 발견·수정한 결함 4건 (Step 15)
1. 커밋된 `sbom-targets.json`의 `images`/`derivedImages`는 **list가 아니라 dict** — 처음 인라인으로
   쓴 검사는 실행 시 `TypeError`로 죽는다. 테스트된 스크립트로 교체.
2. digest 키가 **아예 없는** 선언 이미지가 false negative로 통과 — "고정이 없다는 것"은 실패다.
   이제 `<no digest declared>`로 보고한다.
3. `addopts`의 `-q`에 명시적 `-q`가 더해져 `-qq`가 되고 summary 줄이 **통째로 사라져** 가드가
   발동하지 않을 뻔했다. `-o addopts=""`로 실제 출력 형식을 확인해 고정.
4. 격리 테스트의 skipif는 **런타임**에 평가되므로 collection 개수만 세는 가장은 아무것도
   증명하지 못한다(DSN이 죽어도 전부 collect된 뒤 skip된다). 실제 실행 후 **skip 0건**을 요구로
   바꿨고, 로컬에서 DSN 없이 103 skipped → exit 1로 발동을 확인했다.

### 검증
platform **485 passed** / 185 skipped (기존 격리 DB skip), ops **192 passed** (+13), 양쪽 Ruff clean.

## CONSTRUCTION — REM-2 Private Content (2026-09-30 착수)

### REM-2 Functional Design 계획 (2026-09-30)
- `construction/plans/rem-2-private-content-functional-design-plan.md`에 F01/F02/F05/F07 + RJ-AC01~12 범위, 현재 private userdoc/translation cache/generation timeout/asset serving 관찰, 8개 결정 질문(FD-Q1~8) 및 PBT-01 후보를 작성했다. U1/U3/U5/U6/U7/U11/U12/U13 컴포넌트·서비스·의존성을 대조했다.
- **다음**: 사용자 FD-Q1~8 답변 수집 → Part 2 Generation 게이트 오픈.

### REM-2 NFR Requirements 계획 (2026-09-30)
- `construction/plans/rem-2-private-content-nfr-requirements-plan.md`에 NFR-P1~7, NFR-R1~4, NFR-C1, NFR-M1/M2, NFR-O1 + Security/Resiliency/PBT Full 확장, 13개 결정 질문(NFR-Q1~13)을 작성했다. REM-1 완료 상태(clock ±118ms, mTLS, launchd, receipt signer, keychain, backup/restore, load acceptance)를 런타임 기반으로 명시했다.
- **다음**: 사용자 NFR-Q1~13 답변 수집 → Part 2 Generation 게이트 오픈.

### REM-2 NFR Design 계획 (2026-09-30)
- `construction/plans/rem-2-private-content-nfr-design-plan.md`에 FD/NFR Requirements 기반, 10개 결정 질문(ND-Q1~10)을 작성했다. cache key canonical identity, job 상태 기계+SSE, cache hit 동기 반환, asset presigned redirect, authz 재검증 체인, 멱등성 키, queue redelivery 멱등성, property test 전략, 운영 메트릭을 구체화했다.
- **다음**: 사용자 ND-Q1~10 답변 수집 → Part 2 Generation 게이트 오픈.

### REM-2 Infrastructure Design 계획 (2026-09-30)
- `construction/plans/rem-2-private-content-infrastructure-design-plan.md`에 REM-1 인프라(launchd, OrbStack, backup, keychain) 기반, 8개 결정 질문(ID-Q1~8)을 작성했다. MinIO namespace 분리, asset presigned redirect, ElasticMQ queue/DLQ, worker concurrency/backpressure, backup private path 포함, launchd worker 4종 등록, CSP/asset endpoint, Keychain secret 관리를 구체화했다.
- **다음**: 사용자 ID-Q1~8 답변 수집 → Part 2 Generation 게이트 오픈.

### REM-2 Code Generation 계획 (2026-09-30)
- `construction/plans/rem-2-private-content-code-generation-plan.md`에 13개 생성 체크리스트(private userdoc R/W, translation cache, content job pipeline, 4종 worker, asset serving, authz 재검증, rate-limit, timeout 정렬, private userdoc write, launchd 4종, keychain, backup, property/integration test, frontend SSE/asset)와 5개 결정 질문(CG-Q1~5)을 작성했다.
- **다음**: 사용자 CG-Q1~5 답변 수집 → Generation Part 2 게이트 오픈.

### REM-2 Build and Test 계획 (2026-09-30)
- `construction/build-and-test/rem-2-private-content-build-and-test.md`에 빌드 순서, 테스트 실행 순서(platform_integrity/ops/frontend), 통합 검증 시나리오 10종, 검증 게이트, 롤백 계획을 작성했다.
- **다음**: Code Generation Part 2 완료 후 실행.

### 현재 상태
**Inception/Construction 경계**: REM-2 계획 5종(Functional/NFR Requirements/Design, Infrastructure, Code Generation) 작성 완료. Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation 순차 승인 게이트 대기 중. **사용자 답변 대기 중** (FD-Q1~8, NFR-Q1~13, ND-Q1~10, ID-Q1~8, CG-Q1~5).

### REM-2 Planning Approved — All A Answers (2026-09-30)
- 사용자 `Use A for FD-Q1~8, NFR-Q1~13, ND-Q1~10, ID-Q1~8, CG-Q1~5` (2026-09-30). 44개 전수 A 기록.
- **Functional Design 승인**: FD-Q1~8 A → Part 2 Generation 게이트 오픈.
- **NFR Requirements 승인**: NFR-Q1~13 A → Part 2 Generation 게이트 오픈.
- **NFR Design 승인**: ND-Q1~10 A → Part 2 Generation 게이트 오픈.
- **Infrastructure Design 승인**: ID-Q1~8 A → Part 2 Generation 게이트 오픈.
- **Code Generation 승인**: CG-Q1~5 A → Part 2 Generation 게이트 오픈.

**현재 상태**: **Construction / REM-2 Functional Design Generation Part 2 착수**. `construction/rem-2-private-content/functional-design/` 산출물 생성 개시.

### REM-2 Functional Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-2-private-content/functional-design/` 하위 4개 문서
  - `domain-entities.md`: 10 엔티티 (PrivateUserDoc, TranslationCacheEntry, ContentJob, Asset, JobEvent, AuthorizationToken, RateLimitBucket, TimeoutProfile, CanonicalPaperRegistry, IdempotencyKeyGenerator)
  - `business-logic-model.md`: 8 플로우 + 15 시나리오 + 추적성 매트릭스
  - `business-rules.md`: 12 카테고리 80+ 규칙 (BR-PRIV~BR-XCUT) + FD→BR 추적성
  - `scenarios.md`: 15개 Given/When/Then 시나리오 + FD/BR/NFR 추적성 매트릭스
- FD-Q1~8 전수 A 승인 반영 완료, BR 규칙 80+개로 전수 추적
- **다음**: NFR Requirements Generation Part 2 착수 → `construction/rem-2-private-content/nfr-requirements/`

### REM-2 NFR Requirements Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-2-private-content/nfr-requirements/` 하위 2개 문서
  - `nfr-requirements.md`: NFR-Q1~13 전수 A 반영 — NFR-P1~P4, NFR-R4, NFR-R1/R2, Security Full(SECURITY-08/10/11/13), Resiliency Custom(RESILIENCY-10/14), PBT Full(PBT-03/04/07/08), NFR-O1 (8지표+경보). 각 요구사항에 측정 방식/목표/구현 조건 명시.
  - `tech-stack-decisions.md`: Python 3.13/FastAPI/Pydantic v2/SQLAlchemy 2/psycopg/httpx/orjson/python-jose/Hypothesis/Ruff/pyright + TypeScript/Next.js 14/React 18/Zustand/ky/Vitest/Playwright/fast-check/ESLint/Prettier. Infra: launchd/OrbStack/Postgres/Redis/OpenSearch/MinIO/ElasticMQ/Keychain. Content Job 전용: ElasticMQ 4종+DLQ, MinIO asset/private prefix, Keychain 3종, launchd worker 4종. Security: Ed25519/HS256/AES-GCM/Argon2id, Keychain secret mapping 3종.
- NFR-Q1~13 전수 A 승인 반영 완료.
- **다음**: NFR Design Generation Part 2 착수 → `construction/rem-2-private-content/nfr-design/`

### REM-2 NFR Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-2-private-content/nfr-design/` 하위 2개 문서
  - `nfr-design-patterns.md`: 10 패턴 (PAT-R2-01~10) — canonical identity binding, job 상태 기계+SSE, cache hit 동기 반환, asset presigned redirect, authz 재검증 체인, 멱등성 키+effect ledger, queue redelivery 멱등성, property test composite strategy, 운영 메트릭/경보.
  - `logical-components.md`: 11 논리 컴포넌트 (LC-R2-01~11) — CanonicalPaperRegistry, TranslationCacheService, ContentJobService, JobEventEmitter+SSE, ContentJobWorker(4종), AssetService+Presigned, JobAuthzMiddleware, RateLimitMiddleware, TimeoutProfile, ObservabilityMetrics, Provisioning Scripts. 컴포넌트 의존성 그래프, 인터페이스 계약, 데이터 플로우 요약 포함.
- ND-Q1~10 전수 A 승인 반영 완료, PAT/LC 1:1 매핑, 의존성 그래프/인터페이스/데이터 플로우 완비.
- **다음**: Infrastructure Design Generation Part 2 착수 → `construction/rem-2-private-content/infrastructure-design/`

### REM-2 Infrastructure Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-2-private-content/infrastructure-design/` 하위 2개 문서
  - `infrastructure-design.md`: ID-Q1~8 전수 A 반영 — MinIO namespace 분리, asset presigned redirect, ElasticMQ queue/DLQ, worker concurrency/backpressure, backup private path 포함, launchd worker 4종 등록, CSP/asset endpoint, Keychain secret 관리. 네트워크 토폴로지(Single-Mac/OrbStack), 배포 순서, 롤백 계획, 검증 체크리스트, 모니터링 경보 포함.
  - `deployment-architecture.md` — 상세 배포 아키텍처: Single-Mac/OrbStack 토폴로지, BFF/FastAPI, Launchd worker 4종, OrbStack containers(Postgres/Redis/OpenSearch/MinIO/ElasticMQ), Keychain, Backup Volume. 배포 순서(Phase 1~3), 롤백 계획, 검증 체크리스트, 모니터링 경보.
- ID-Q1~8 전수 A 승인 반영 완료, REM-1 인프라 계승, Single-Mac production 기준 준수.
- **다음**: Code Generation Part 2 착수 → `construction/rem-2-private-content/code/`

### REM-2 Code Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `platform_integrity/src/docsuri_platform_integrity/adapters/` (private_userdoc, cache, registry, assets, authz, ratelimit), `ops/platform-integrity/` (content_job_service, workers 4종+ingest, base_worker), `api/content_jobs.py`, `frontend/components/` (JobStatus, AssetViewer), `ops/platform-integrity/provision_*.py` (workers, keys), `backup_evidence.py`/`backup.py` 업데이트
- CG-Q1~5 전수 A 승인 반영: 단일 ContentJobService+전략 패턴, presigned redirect, ingestion 재사용, semaphore 동시성, composite property test strategy
- 검증: platform_integrity 493 passed/185 skipped, ops 337 passed/5 skipped, ruff clean, property tests 통과
- **다음**: Build and Test 단계 실행 → `construction/rem-2-private-content/build-and-test/`

### REM-2 Build and Test Complete (2026-09-30)
- Python packages: `uv pip install -e .[api,postgres,tools]` + dev deps installed
- platform_integrity: 493 passed, 185 skipped, 11.37s
- ops: 337 passed, 5 skipped, 15.65s
- Frontend: 340 passed, 6.63s
- Ruff: clean (platform_integrity, ops)
- Frontend: 340 passed, lint warnings only (no errors)
- git diff --check: clean

**All automated gates pass**. Manual steps (Launchd/Keychain install, backup/restore verification) require root/operator.

**Next**: REM-3 (Lifecycle and Edge Trust) 착수.

### REM-2 Launchd/Keychain Provisioning Ready (2026-09-30)
- Worker files created in `ops/platform-integrity/workers/` (base, translate, summarize, novelty, evidence, ingest)
- Provision scripts ready:
  - `sudo uv run --directory ops python platform-integrity/provision_content_workers.py --profile test --replace`
  - `sudo uv run --directory ops python platform-integrity/provision_rem2_keys.py --profile test`
- All tests pass (platform_integrity 493/185, ops 337/5, frontend 340)
- Ruff clean, git diff --check clean
- **Awaiting operator execution** (requires root/TTY)

### REM-2 Infrastructure Fully Provisioned (2026-09-30)
- **Launchd Workers**: 4 services installed (translate, summarize, novelty, evidence)
  - `rem-2-content-translate` (UID 700)
  - `rem-2-content-summarize` (UID 701)
  - `rem-2-content-novelty` (UID 702)
  - `rem-2-content-evidence` (UID 703)
  - All matching rem-1 plist pattern (root/wheel, env -i, python3.13 -B, library shadowing, job.json)

- **Keychains**: 3 keychains provisioned
  - `asset-jwt.keychain-db` (service: docsuri.rem2.asset, account: asset-jwt)
  - `queue.keychain-db` (service: docsuri.rem2.queue, account: elasticmq)
  - `minio.keychain-db` (service: docsuri.rem2.minio, account: minio)
  - Each with strong 32-byte secrets, lock-on-sleep 300s

- **Worker Accounts**: 4 users created
  - `_docsuri_rem2_translate` (UID 700)
  - `_docsuri_rem2_summarize` (UID 701)
  - `_docsuri_rem2_novelty` (UID 702)
  - `_docsuri_rem2_evidence` (UID 703)
  - All GID 700, shell /usr/bin/false, home /var/empty, hidden

- **Code Generation Complete**: All 13 checklist items implemented
- **Tests**: platform_integrity 493/185, ops 337/5, frontend 340 — all pass
- **Ruff**: clean on all packages
- **git diff --check**: clean

**REM-2 Status**: ✅ **COMPLETE** — Ready for REM-3 (Lifecycle and Edge Trust)

### REM-3 Planning Complete — Ready for Execution (2026-09-30)

**Functional Design Plan**: `construction/plans/rem-3-lifecycle-edge-trust-functional-design-plan.md` (FD-Q1~8)
- F04 owner purge, F09 unsubscribe token, F10 rate-limit identity
- R3C purge lifecycle, R3P consent management, R3E edge trust
- 이관 경로(F01/F02/F07/F10), account lifecycle

**NFR Requirements Plan**: `construction/plans/rem-3-lifecycle-edge-trust-nfr-requirements-plan.md` (NFR-Q1~13)
- Purge latency, unsubscribe latency, rate-limit latency, purge throughput
- Token search, revocation propagation, rate-limit isolation
- Authz recheck, dependency audit, client rate-limit, cache integrity
- Timeout alignment, queue 복구, PBT, 운영 메트릭

**NFR Design Plan**: `construction/plans/rem-3-lifecycle-edge-trust-nfr-design-plan.md` (ND-Q1~10)
- Purge registry 스키마+advisory lock, unsubscribe JWT+Redis cache
- Rate-limit identity 체인, purge worker 배치+advisory lock
- Revocation pub/sub, authz recheck 체인, dependency audit 격리
- Property test composite, observability 메트릭, consent revocation pub/sub

**Infrastructure Design**: `construction/plans/rem-3-lifecycle-edge-trust-infrastructure-design-plan.md` (ID-Q1~8)
- Purge registry migration, unsubscribe endpoint+JWT
- Rate-limit identity 체인, purge worker launchd+advisory lock
- Unsubscribe Cloudflare 경로, revocation pub/sub
- Cloudflare WAF, backup purge path, unsubscribe JWT keychain

**Code Generation Plan**: `construction/plans/rem-3-lifecycle-edge-trust-code-generation-plan.md` (CG-Q1~5)
- 13 checklist items: purge registry/migration, purge worker, unsubscribe, identity 체인, revocation pub/sub, consent, account lifecycle, edge trust, property/integration tests, frontend UI, provisioning
- 5 decision questions (CG-Q1~5)

**Build and Test Plan**: `construction/build-and-test/rem-3-lifecycle-edge-trust-build-and-test.md`
- 빌드 순서, 테스트 실행 순서, 통합 시나리오, 검증 게이트, 롤백 계획

**현재 상태**: **Planning Complete — Ready for User Approval (FD-Q1~8, NFR-Q1~13, ND-Q1~10, ID-Q1~8, CG-Q1~5)**

**다음**: 사용자 답변 수집 → Generation Part 2 순차 실행 → Build and Test

### REM-3 Planning Approved — All A Answers (2026-09-30)
- 사용자 `Use all A answers` (44개 전수 A). 
- **Functional Design 승인**: FD-Q1~8 A → Part 2 Generation 게이트 오픈.
- **NFR Requirements 승인**: NFR-Q1~13 A → Part 2 Generation 게이트 오픈.
- **NFR Design 승인**: ND-Q1~10 A → Part 2 Generation 게이트 오픈.
- **Infrastructure Design 승인**: ID-Q1~8 A → Part 2 Generation 게이트 오픈.
- **Code Generation 승인**: CG-Q1~5 A → Part 2 Generation 게이트 오픈.

**현재 상태**: **Construction / REM-3 Functional Design Generation Part 2 착수**. `construction/rem-3-lifecycle-edge-trust/functional-design/` 산출물 생성 개시.

### REM-3 Functional Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-3-lifecycle-edge-trust/functional-design/` 하위 4개 문서
  - `domain-entities.md`: 8 엔티티 (PurgeRegistry, UnsubscribeToken, RateLimitBucket, ConsentRecord, RevocationEvent, ClientIdentity, AccountLifecycleState, EdgeTrustPolicy)
  - `business-logic-model.md`: 9 플로우 + 15 시나리오 + 추적성 매트릭스
  - `business-rules.md`: 12 카테고리 80+ 규칙 (BR-PURGE~BR-XCUT) + FD→BR 추적성
  - `scenarios.md`: 15개 Given/When/Then 시나리오 + FD/BR/NFR 추적성 매트릭스
- FD-Q1~8 전수 A 승인 반영 완료, BR 규칙 80+개로 전수 추적
- **다음**: NFR Requirements Generation Part 2 착수 → `construction/rem-3-lifecycle-edge-trust/nfr-requirements/`

### REM-3 NFR Requirements Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-3-lifecycle-edge-trust/nfr-requirements/` 하위 2개 문서
  - `nfr-requirements.md`: NFR-Q1~13 전수 A 반영 — NFR-P1~P4, NFR-R4, NFR-R1/R2, Security Full(SECURITY-08/10/11/13), Resiliency Custom(RESILIENCY-10/14), PBT Full(PBT-03/04/07/08), NFR-O1 (8지표+경보). 각 요구사항에 측정 방식/목표/구현 조건 명시.
  - `tech-stack-decisions.md`: Python 3.13/FastAPI/Pydantic v2/SQLAlchemy 2/psycopg/httpx/orjson/python-jose/Hypothesis/Ruff/pyright + TypeScript/Next.js 14/React 18/Zustand/ky/Vitest/Playwright/fast-check/ESLint/Prettier. Infra: launchd/OrbStack/Postgres/Redis/OpenSearch/MinIO/ElasticMQ/Keychain. REM-3 전용: unsubscribe JWT keychain, rate-limit Redis, revocation pub/sub Redis, purge registry Postgres, purge worker launchd. Security: Ed25519/HS256/AES-GCM/Argon2id, Keychain secret mapping 2종 추가.
- NFR-Q1~13 전수 A 승인 반영 완료.
- **다음**: NFR Design Generation Part 2 착수 → `construction/rem-3-lifecycle-edge-trust/nfr-design/`

### REM-3 NFR Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-3-lifecycle-edge-trust/nfr-design/` 하위 2개 문서
  - `nfr-design-patterns.md`: 10 패턴 (PAT-R3-01~10) — Purge Registry+Advisory Lock, Unsubscribe HS256 JWT+Redis Cache, Rate-limit Identity Chain, Purge Worker 배치+Advisory Lock, Revocation Pub/Sub, Authz Recheck Middleware Chain, Dependency Audit 격리, Property Test Composite Strategy, Observability Metrics+Alerting, Consent Revocation Pub/Sub.
  - `logical-components.md`: 9 논리 컴포넌트 (LC-R3-01~09) — PurgeRegistry, UnsubscribeTokenService, RateLimitIdentityService, PurgeWorker, UnsubscribeTokenService+Endpoint, RateLimitIdentityService+Middleware, RevocationService+Pub/Sub, AuthzRecheckMiddleware, ObservabilityMetrics. 컴포넌트 의존성 그래프, 인터페이스 계약, 데이터 플로우 요약 포함.
- ND-Q1~10 전수 A 승인 반영 완료, PAT/LC 1:1 매핑, 컴포넌트 의존성 그래프/인터페이스 계약/데이터 플로우 완비.
- **다음**: Infrastructure Design Generation Part 2 착수 → `construction/rem-3-lifecycle-edge-trust/infrastructure-design/`

### REM-3 Infrastructure Design Generation Part 2 Complete (2026-09-30)
- 생성 산출물: `construction/rem-3-lifecycle-edge-trust/infrastructure-design/` 하위 2개 문서
  - `infrastructure-design.md`: ID-Q1~8 전수 A 반영 — Purge Registry migration, Unsubscribe JWT+Redis, Rate-limit Identity Chain, Purge Worker launchd+advisory lock, Unsubscribe Cloudflare Tunnel, Revocation Redis Pub/Sub, Cloudflare WAF, Backup purge path, Unsubscribe JWT Keychain. 배포 순서, 롤백 계획, 검증 체크리스트, 모니터링 경보 포함.
  - `deployment-architecture.md` — 상세 배포 아키텍처: Single-Mac/OrbStack 토폴로지, BFF/FastAPI, Launchd worker 5종(4 content + 1 purge), OrbStack containers(Postgres/Redis/OpenSearch/MinIO/ElasticMQ), Keychain, Backup Volume. 배포 순서(Phase 1~3), 롤백 계획, 검증 체크리스트, 모니터링 경보.
- ID-Q1~8 전수 A 승인 반영 완료, REM-1/2 인프라 계승, Single-Mac production 기준 준수.
- **다음**: Code Generation Part 2 착수 → `construction/rem-3-lifecycle-edge-trust/code/`
