# DocSuri 전체 기능·요구사항 검증 — 2026-09-18

## 1. 결론

**판정: 모든 기능이 올바르게 동작하거나 모든 요구사항을 충족한다고 승인할 수 없다.**

- 기존 테스트는 **Python 1,504개, frontend Vitest 338개, WebKit E2E 3개**가 통과했다. TypeScript, 기존 CI lint 레인, Python 계약 생성 검사, Next.js production build도 통과했다.
- 추가한 **합성 데이터 기반 감사 반례 4개는 실패**했다: 다른 사용자 userdoc 읽기, 공유 번역 캐시 오염, 느린 정상 요약의 10초 BFF timeout, 프록시 클라이언트 식별 전달 누락.
- 실제 공개 검색에는 **허구의 테스트 fixture 논문**이 노출된다. 현재 read alias의 코퍼스는 **599 chunks / 11 distinct paper IDs**이며, 연도 집계에 2025/2026 자료가 없다.
- 계정 파기, 이미지 서빙, 신규 DB 초기화, 다이제스트 링크/수신 해지, 실패 상태 표시, 계약 검사에도 확인된 결함이 있다.
- 의존성 스캔은 frontend production dependency tree에서 **critical 2 / high 22 / moderate 10** 항목을 보고했다. 이는 버전 기반 advisory 결과이며, 모든 항목의 실제 공격 가능성을 입증한 것은 아니다.

운영 헬스가 200이고 기존 테스트가 green인 것은 **프로세스 가동 및 해당 테스트 시나리오의 성공**을 뜻한다. 데이터 진실성, 전 사용자 격리, 모든 외부 서비스 연결, 성능/복구 목표의 충족을 보증하지 않는다.

### 기준과 범위

- 코드 기준: `develop`, HEAD `32a424d` (`chore: retire docsuri.org references after losing the domain`). 최초 작업 트리 clean.
- 요구사항: `aidlc-docs/inception/requirements/requirements.md`의 **활성 FR 47건**. FR-22~25는 폐기된 ID로 제외했다. 사용자 스토리, 유닛 레지스트리, 관련 후속 결정도 참고했다.
- 현재 런타임: `ops/server/README.md` 및 실제 프로브. 2026-08-17 AWS 폐기 이후 **Mac + launchd + OrbStack + Cloudflare Tunnel + Ollama** 방식이다.
- 테스트: 운영 checkout과 분리한 detached worktree, Python 3.13.7, pnpm 9.15.9, frozen lock 설치. Python PBT seed=`20260918`.
- 라이브 프로브: 헬스, 공개 검색, 익명 접근 거부, OAuth 시작 경로, 무효 unsubscribe token, 공개 URL 및 읽기 전용 코퍼스/스키마 메타데이터.
- 개인정보 관련 반례는 실제 사용자 데이터 대신 합성 데이터와 fake S3/LLM으로 실행했다.
- 계획: `aidlc-docs/construction/plans/project-verification-2026-09-18-plan.md`.

## 2. 프로젝트 이해

DocSuri는 AI/ML 연구자의 문헌 탐색을 돕는 폰 우선 연구 지원 애플리케이션이다. 자연어 검색을 중심으로 계정, 개인 라이브러리, 구조화 논문 읽기, 요약/한국어 번역, 인용 트리, 개인화, 근거형성 및 novelty 에이전트가 연결된다.

### 코드와 주요 흐름

| 영역 | 구현 | 역할 |
|---|---|---|
| U1 | `ingestion/`, `backend/modules/user_docmodel/` | 외부 논문/업로드 PDF → 정규화 DocModel·자산·청크·임베딩·인덱스 |
| U2 | `backend/modules/discovery/` | lite/full 검색, BM25/k-NN, 융합/재랭킹, U6 grounding seam |
| U3/U4 | `backend/modules/accounts/`, `library/` | 가입·인증·계정 라이프사이클, 저장 검색·라이브러리·이력 |
| U5/U13 | `frontend/` | Next.js/React/TypeScript, 폰 UI, BFF, 채팅·SSE·폴링 |
| U6 | `backend/middleware/`, `backend/modules/ops/`, `ops/` | 인증 주입, rate limit, 비용/근거화 계약, 관측/운영 |
| U7/U8 | `summarization/`, `citation_graph/` | 요약/구조화 번역, DocModel/자산 읽기, backward citation tree |
| U9/U10/U14 | `personalization/`, `mypage/`, `onboarding/` | 행동 이벤트·프로필·설정·관심사 시딩 |
| U11/U12 | `evidence/` 및 `evidence/sessions/`, `novelty/` | 문헌 근거형성, 다중 턴, 업로드, 비동기 분석, 승인형 Notion export |
| U15/U16 | `trends/`, `plans/` | 옵트인 다이제스트·팔로우 주제, free/plus 쿼터·관리자 부여 |
| 공유 계약 | `shared/dtos/`, `shared/events/`, `shared/python/` | JSON Schema, Python 생성 DTO, 포트, 벡터 공간 계약 |

주요 호출 흐름은 브라우저 → Next.js `/bff/*` → FastAPI gateway → 도메인 모듈이다. 긴 작업은 ElasticMQ의 SQS 호환 큐와 별도 워커를 사용한다. Postgres는 사용자/제어 데이터, Redis는 세션/캐시, OpenSearch는 코퍼스, MinIO는 S3 호환 아티팩트 저장소다. 현재 로컬 모델 어댑터는 bge-m3 임베딩과 qwen3:8b 생성 경로를 제공한다.

실측 인벤토리: `/readyz` **14 mounted / 0 skipped / 0 blocking**, OpenAPI **82 paths / 101 operations**. 이 숫자는 라우트 인벤토리이며 101개 operation 모두의 실서비스 성공을 뜻하지 않는다.

## 3. 실행 결과

### 3.1 기존 자동화

| 레인 | 결과 | 범위/제한 |
|---|---|---|
| shared Python | 73 passed | DTO/schema/vector/PBT; 생성 드리프트 검사 통과 |
| ingestion | 317 passed + 별도 Postgres 통합 1 passed | 자산 extra 포함 설치; 외부 수집/임베딩은 주로 대역 |
| discovery | 124 passed | api extra; fixture seed를 쓰는 OpenSearch 통합 모듈은 skip |
| summarization | 298 passed + 별도 Postgres 통합 2 passed | real extras 설치; live Bedrock/S3 통합 gate는 skip |
| ops | 53 passed | 비용·근거화·탐지·관측 로직 |
| backend app-shell | 451 passed | 실제 외부 citation provider contract 1 skip |
| root accounts/library | 185 passed | 인증/세션/라이프사이클/CRUD/SQL/PBT |
| frontend Vitest | 56 files / 338 passed | UI·transport·helper·fast-check 포함 |
| frontend WebKit | 3 passed | mock transport의 가입→로그인→온보딩 skip→검색, 익명 보호 route, novelty 채팅 |
| TypeScript / ESLint | PASS | `tsc --noEmit`, `pnpm run lint` |
| Python Ruff | PASS | 기존 CI의 shared/ingestion/discovery/summarization/ops/backend/root-suites 7 레인 |
| Next.js production build | PASS | isolated checkout에서 모든 route 컴파일; mock-default configuration |
| Python schema drift | PASS | `uv run --frozen --no-sync python tools/generate.py --check` |
| frontend type generation | **부분 실패를 exit 0으로 처리** | library schema 원격 `$ref` fetch 실패를 skip; F13 |

초기 Python 실행은 1,501 passed / 6 skipped였다. 격리 Postgres에서 skip 3건을 별도로 실행해 모두 통과했다. 나머지 세 gate는 citation 실 provider, OpenSearch fixture-seeding 통합 모듈, Bedrock/S3 실 통합이다. 운영 OpenSearch 읽기는 라이브 검색으로 별도 확인했다.

테스트 환경 문제는 제품 결함과 구분했다. 첫 Python codegen 호출의 PATH 누락은 문서화된 `uv run` 방식으로 해소했고, 첫 E2E의 WebKit 바이너리 누락은 임시 경로 설치 후 3/3 통과했다. 감사용 Node 테스트의 DOM setup 충돌도 별도 config로 해소한 뒤 실제 반례를 실행했다.

### 3.2 추가 반례

| 합성 시나리오 | 기대 | 실제 |
|---|---|---|
| 사용자 B가 사용자 A의 `userdoc:` ID를 DocModel route로 요청 | 403/404 또는 owner 검사 | **200 + A의 합성 원고 본문** |
| A가 임의 abstract로 생성 후 B가 같은 논문의 올바른 abstract로 번역 | B의 정식 원문에 근거한 결과 | **cached=true + A의 임의 본문 번역** |
| 짧은 논문의 정상 upstream 응답이 12초 소요 | 해당 비-SLA 생성 경로의 정상 완료 | **약 10초에 BFF 504** |
| 서로 다른 프록시 클라이언트 2명이 BFF를 통과 | gateway가 클라이언트를 구별 가능 | **두 요청 모두 전달 IP 없음** |

네 반례의 테스트 구성·인수 조건·실행 결과는 별도 [재현 문서](project-verification-2026-09-18-reproductions.md)에 보존한다. 기존 테스트 통과 수와 합산해 green으로 표시하지 않는다.

### 3.3 실제 서비스 관찰

| 프로브 | 관찰 |
|---|---|
| API/web/공개 BFF health | 200; 프로세스와 컨테이너 가동 |
| Postgres/Redis/OpenSearch/MinIO/ElasticMQ | 운영 컨테이너 가동; OpenSearch single-node green |
| 익명 `/auth/session`, `/library/items` | 401, 정상 거부 |
| Google OAuth start | 302; callback/실제 로그인은 미검증 |
| ORCID OAuth start | 503, 미설정 안내. 운영 runbook에도 feature off 기록 |
| 초기 검색 3건 | 각각 10.18 / 10.02 / 10.02초; 영어 결과 lexical-only, 한국어/음식 질의 empty |
| 초기 Ollama embedding 직접 프로브 | 15초 read timeout; 당시 `/api/ps`는 모델 없음 |
| 이후 공개 BFF 영어 검색 | 200, 약 3.22초, 정상 모드 11개 결과. 임베딩 회복 확인 |
| 이후 한국어 검색 | 200, 약 0.18초, 정상 모드 11개 결과 |
| 이후 `banana cake recipe` | 200, 약 0.05초, 정상 모드 **11개 논문**, no-match/abstain 아님 |
| 검색 데이터 진실성 | 공개 BFF가 mock fixture 제목·저자·ID 조합을 실제 논문처럼 반환 |
| 코퍼스 alias | `docsuri-corpus` → `docsuri-corpus-v3`, 599 chunks / distinct paper IDs 11 |
| corpus year aggregation | 2012/2013/2014/2017/2022/2023/2024만 존재; 2025/2026 없음 |
| 익명 `/trends/unsubscribe` | 무효 token에 인증 middleware **401**; 의도된 token 검증 400에 도달 못 함 |
| 다이제스트 링크 | `/papers/1706.03762`=404, 실제 route `/paper/1706.03762`=200 |
| HTML 보안 헤더 | CSP nonce, HSTS, nosniff, SAMEORIGIN, Referrer-Policy 확인 |

초기 임베딩 timeout을 지속 장애로 단정하지 않는다. 이후 정상/빠른 검색이 확인됐다. 표의 소수 샘플은 P50/P95 부하 검증이 아니며, cold-path 실패와 warm-path 회복을 보여 준다.

## 4. 우선순위별 확인 사항

P1은 사용자 격리·데이터 진실성·핵심 경로 문제로 우선 수정할 항목이다. P2는 특정 기능/배포/검증 경계 결함이다. 아래 원인과 재현은 현재 checkout 기준이다.

### F01 · P1 — private userdoc를 공용 DocModel route로 읽을 수 있음

- **근거**: `backend/modules/summarization/src/summarization/api/router.py:94-131`, `service/orchestrator.py:396-418`, `adapters/s3_docmodel.py:44-54`.
- route는 로그인 여부만 확인한 뒤 `paper_id`를 reader에 전달한다. 소유자 ID가 읽기 계층에 전달되지 않으며 `userdoc:` namespace를 거부하지 않는다.
- U1은 실제로 업로드 PDF를 같은 DocModel 저장 체계에 쓴다: `ingestion/src/docsuri_ingestion/application.py:177-274`.
- **재현**: private `userdoc:` JSON을 fake S3에 넣고 B의 principal로 요청하면 200과 A의 합성 본문이 반환된다. 조건은 공격자가 해당 ID를 알고 있고 DocModel viewer가 활성인 경우다.
- **영향**: SEC-8, FR-38 및 업로드 원고 owner isolation 위반. UUID의 추측 난이도는 객체 인가를 대체하지 않는다.
- **조치**: 공용 corpus endpoint에서 private namespace를 차단하고, 업로드 문서 읽기는 소유자 확인이 적용된 전용 경로를 사용한다. 요약/번역 source read에도 같은 경계를 적용한다.

### F02 · P1 — 사용자 입력 abstract가 공유 번역 캐시를 오염시킴

- **근거**: summarization `api/router.py:202-223`, `domain/source_selector.py:31-40`, `domain/cache_key.py:35-72`, `service/orchestrator.py:154-201`.
- source selector는 서버의 논문 메타데이터보다 요청의 `abstract`를 우선한다. 기본 glossary signature=0인 캐시 키에는 owner나 원문 내용 hash가 없다. 캐시 hit는 source 검증보다 먼저 반환된다.
- **재현**: A가 실제 논문 ID와 임의 abstract로 번역 생성 → B가 같은 ID/버전에 정식 abstract로 요청 → `cached=true`와 A의 임의 번역 반환. LLM은 test-only faithful translator이며 공유 캐시/selector/오케스트레이터는 실제 구현이다.
- **영향**: FR-5/13, QT-5, 데이터 무결성 및 사용자 간 내용 분리.
- **조치**: 공유 생성물의 원문은 서버가 신뢰하는 메타데이터/DocModel로 결정하고, 검증된 source identity에 캐시를 결속시킨다.

### F03 · P1 — 공개 검색에 허구 fixture 논문이 노출되고 코퍼스 범위가 미충족

- **실측**: `https://docsuri.rvnnt.dev/bff/api/search`에서 `transformer attention` 질의가 `Vision Transformers at Scale`, 저자 `D. Vision`, ID `2401.00003v1`을 반환했다. 다른 fixture 4개도 같은 공개 응답에 포함됐다.
- **대조**: [실제 arXiv 2401.00003](https://arxiv.org/abs/2401.00003)의 제목은 **Generative Inverse Design of Metamaterials with Functional Responses by Interpretable Learning**이며, 해당 fixture와 다른 논문이다.
- **코드 지문**: `backend/modules/discovery/src/discovery/mocks/fixtures.py:69-113`와 제목/저자/ID가 일치한다. 인덱스 레코드에 존재한다는 검증만으로 원 출처의 진실성을 보장하지 못한다.
- **추가 실측**: 현재 read alias의 distinct paper ID는 11개, 2025/2026 연도 bucket은 없다. FR-6의 최근 AI/ML 1년 코퍼스 완료 상태로 볼 수 없다. 과거 대량 재색인 중단 결정은 `aidlc-state.md:1018-1032`에 존재한다.
- **영향**: FR-2/5/6, QT-1/QT-9, US-H1/D5/D6.
- **조치**: 운영 코퍼스에서 test fixtures를 제거하고 신뢰 가능한 원 출처로 검증된 코퍼스를 구축한다. 배포 검증에 fixture 오염·source metadata 일치·코퍼스 완성도 검사를 포함한다.

### F04 · P1 — 계정 영구 파기가 신규 owner-scoped 테이블을 누락

- **근거**: `backend/modules/accounts/services/owner_data_purge.py:32-50`; 호출 지점 `services/account_deletion.py:219-230`.
- `evidence_sessions`, `evidence_turns`, `onboarding_status`, `followed_topics`, `digest_settings`, `digest_send_log`가 purge registry에 없다. 해당 migration에는 accounts로의 `ON DELETE CASCADE`도 없다.
- **재현**: 동일 owner의 위 테이블과 `saved_searches`에 합성 행을 넣고 실제 `SqlOwnerDataPurger.purge()` 호출 → saved_searches=0행, 나머지는 각각 1행 유지.
- 현재 로컬 운영은 `ACCOUNT_EVENTS_BUS=none` + SQL backstop 방식으로 문서화되어 있어 누락분을 삭제할 EventBridge 구독자를 전제할 수 없다.
- **영향**: FR-28/38, 사용자 데이터 파기 계약. plan/spend 및 object storage의 별도 보존/파기 정책도 명시적으로 점검해야 한다.
- **조치**: owner 데이터 registry를 현재 전체 도메인에 맞추고, 실제 계정 purge와 private object 삭제까지 검증하는 통합 테스트를 둔다.

### F05 · P1 — 짧은 요약/번역의 정상 생성 시간이 frontend 10초 예산과 충돌

- **근거**: `frontend/lib/api/apiClient.ts:415,443-451`, `frontend/app/bff/[...path]/route.ts:47-69`, `frontend/lib/api/httpTransport.ts:81`.
- summarize 요청에는 별도 timeout override가 없어 browser API client와 BFF→API 모두 기본 10초다. 반면 로컬 LLM adapter는 read timeout 300초이고, 6,000 token 이하 입력은 inline 생성할 수 있다: summarization `adapters/openai_llm.py:44-49`, `service/orchestrator.py:249-280`.
- **재현**: 정상 JSON을 12초 뒤 반환하는 loopback upstream과 실제 BFF POST handler → 약 10.02초에 **504**.
- **영향**: FR-12/13, NFR-P2, US-S5. 캐시된 결과는 별도이며, 모든 요약 요청이 실패한다는 뜻은 아니다.
- **조치**: 로컬 모델 특성에 맞는 async/poll 전환과 browser/BFF/API/worker의 일관된 시간 예산을 적용한다.

### F06 · P1 — pinned dependency tree의 취약점 게이트 실패

- `pnpm audit --prod --audit-level high`: **34 advisory 항목** — critical 2, high 22, moderate 10. `next@15.5.19`, sharp, PostCSS, nanoid, browserslist, xmldom 등이 포함됐다.
- Next.js critical advisory: `GHSA-p293-qw3h-jr36`(Windows-hosted server 조건), `GHSA-2xp9-vwfh-vxw4`(AVIF image optimization 조건), scanner의 patched range는 **15.5.24 이상**이다. **Windows 전용 조건은 현재 macOS 호스트에 해당하지 않는다.** 다른 항목도 실제 사용 경로/입력 도달성을 별도 검토해야 한다.
- backend `pip-audit`: `cryptography 49.0.0`, 고유 `PYSEC-2026-3552`, fix 50.0.0. scanner가 같은 ID를 두 행으로 출력했다.
- ingestion `pip-audit`: 4개 패키지에서 30개 출력 항목(중복 포함). cryptography, Pillow 12.2.0(fix 12.3.0), pydantic-settings 2.14.1(fix 2.14.2), soupsieve 2.8.4(fix 2.9.0).
- ops `pip-audit`: 알려진 취약점 없음. first-party editable package는 audit 대상에서 제외되고 실제 소스 리뷰/테스트로 확인했다.
- **영향**: SEC-10. 버전 기반 scanner finding이며 exploit 성공 판정은 아니다. 검사 대상은 frozen lock으로 만든 격리 환경이다.
- **조치**: 호환되는 patched dependency/lock으로 갱신하고 source-reachable advisory부터 검증한다. 라이브 venv/image 버전도 별도 대조한다.

### F07 · P2 — private MinIO URL이 브라우저 이미지 URL로 노출되는 서빙 불일치

- **근거**: summarization `adapters/rds_assets.py:54-58,89-100`, `frontend/components/DocModelViewer.tsx:493-497,544-552`, `frontend/middleware.ts:37-40`.
- MinIO endpoint를 사용해 presign하면 `http://127.0.0.1:9000/...`와 같은 URL이 만들어진다(합성 credential로 재현, signature 비출력). 프론트는 이 URL을 `<img src>`에 직접 사용한다.
- 현 서버 구성은 port 3000만 tunnel로 공개하고 MinIO 9000은 loopback 전용이다(`ops/server/README.md:27-30`, `backend/docker-compose.yml:94-105`). 실 HTML CSP도 AWS Seoul S3 image host만 허용한다.
- **영향**: FR-17/18의 그림/표 이미지가 원격 사용자 브라우저에서 접근 불가능한 구성이다. 인증된 실제 논문 화면의 개별 이미지 fetch까지 실행한 것은 아니다.
- **조치**: 현재 인증 경계를 유지하는 same-origin asset serving 경로를 마련하고, 원격 브라우저에서 그림 렌더를 검증한다.

### F08 · P2 — 신규 DB startup migration이 evidence와 glossary 테이블을 만들지 않음

- **근거**: `backend/app.py:149-162`의 startup path 목록에 `backend/modules/evidence/migrations` 및 `backend/modules/summarization/migrations`가 없다.
- **재현**: 빈 격리 Postgres에 `_apply_startup_migrations()` 실행 → accounts/library/mypage 존재, **evidence_sessions/evidence_turns/user_glossary 부재**.
- CLI migrator(`backend/migrations/__main__.py:14-25`)도 startup과 목록이 다르며 glossary를 포함하지 않는다.
- **영향**: 새 설치/DB 복구 시 U11 영속 경로 및 U7 용어집 사용 실패. 현재 운영 DB에는 해당 테이블이 있음을 별도 metadata 조회로 확인했으므로 현재 테이블 부재로 오인하면 안 된다.
- **조치**: 배포 단위의 migration registry를 일원화하고 fresh-database 실제 요청까지 검증한다.

### F09 · P2 — 다이제스트의 수신 해지와 논문 링크가 끊김

- 무로그인 해지를 선언한 controller: `backend/modules/trends/controller.py:4-6,160-180`.
- 그러나 `backend/middleware/auth.py:21-45` public allowlist에 `/trends/unsubscribe`가 없어 세션이 없는 요청은 **401**이다. 무효 token 라이브 프로브로 middleware 차단을 확인했다. 유효 token도 route 도달 전에 같은 검사를 통과해야 한다.
- `backend/modules/trends/service.py:248-262`는 `/papers/{id}` 링크를 생성하나 실제 Next route는 `/paper/{id}`다. 라이브 404/200으로 확인했다.
- **영향**: FR-47, US-TN2/TN3. daily harvest 중단은 별도의 명시적 운영 보류이며 이 두 구현 결함의 원인이 아니다.
- **조치**: token 인증 endpoint의 gateway 예외를 정확히 적용하고, 메일 URL을 실제 프론트 route와 같은 계약에서 생성한다.

### F10 · P2 — BFF가 client IP를 버려 gateway rate-limit bucket을 공유시킴

- **근거**: `frontend/app/bff/[...path]/route.ts:78-80,231-238`, `frontend/lib/api/httpTransport.ts:53-81`, `backend/middleware/gateway.py:123-151`.
- 일반 BFF는 reCAPTCHA header만 추가 전달하고 client IP를 전달하지 않는다. gateway는 principal이 아니라 forwarded IP 또는 socket peer로 key를 만든다.
- **재현**: 서로 다른 proxy-stamped IP 2개로 실제 BFF handler 호출 → 두 upstream 모두 IP header 없음(`[null,null]`). 현재 native BFF→API topology에서는 peer가 loopback으로 합쳐진다.
- **영향**: 서로 다른 사용자가 같은 gateway 제한을 소모한다. 기본 설정은 60 requests/60s(`backend/config.py:65-66`); 실제 limit override 및 동시 부하 영향은 측정하지 않았다.
- **조치**: 신뢰된 ingress에서 검증한 client identity를 BFF→gateway에 일관되게 전달하고 여러 클라이언트의 독립 limit을 통합 검증한다.

### F11 · P2 — empty 결과 조립이 알려진 저하 상태를 삭제

- **근거**: discovery `domain/assembler.py:63-65,91-95`.
- `assemble(NoMatchResult(), LEXICAL_ONLY)`도 무조건 `degraded=false`, `degradationMode=null`을 반환한다.
- **재현**: 순수 함수 호출과 초기 live 한국어 검색에서 동일 출력 확인. 임베딩 실패로 영어 lexical fallback이 빈 경우 사용자는 정상 검색의 무결과로 오인한다.
- **영향**: FR-11, NFR-R1/R2, QT-3의 실패/저하 구분.
- **조치**: 결과 0건에서도 degradation provenance를 보존하고 해당 UI 상태를 검증한다.

### F12 · P2 — 의미적으로 범위 밖인 질의의 no-match 인수가 충족되지 않음

- **실측**: 임베딩 회복 뒤 `banana cake recipe`가 모든 11개 후보를 정상 응답으로 반환했다.
- **근거**: `backend/wiring.py:252-261`, discovery `service/orchestrator.py:265-276`. no-match k-NN floor는 기본 0=off이며, 임계 미설정이면 nearest-neighbor 후보가 있는 한 계속 결과를 반환한다.
- **영향**: FR-5/11, QT-1, US-D6. 높은 검색 recall과 관련 없는 질의의 기권은 별도 요구다. F03의 fixture 오염과도 별개의 문제다.
- **조치**: 검증된 코퍼스로 관련/범위 밖 질의 평가셋을 만들고 floor/기권 정책을 보정한다. FR-3의 정량 ranking 평가 유예 결정과 이 필수 no-match 동작을 구분한다.

### F13 · P2 — frontend 계약 생성 실패가 성공으로 보임

- **근거**: `frontend/scripts/gen-types.mjs:18-24,40-49`, `shared/dtos/library.schema.json:186-190`.
- library의 absolute `$ref`를 원격 URL에서 fetch하다 실패한다. generator가 catch 후 skip하고 non-zero exit를 설정하지 않아 **실패 메시지 뒤 exit 0**, `git diff --exit-code types/`도 통과했다.
- 이 파일은 다섯 schema만 대상으로 삼으며 build-consumed curated types는 별도다. 따라서 현재 guard를 전 계약 자동 정합 검증으로 해석하면 안 된다.
- **영향**: 공유 계약 드리프트 검증 및 NFR-M1/SEC-13.
- **조치**: 외부 `$id`를 로컬 SSOT 파일로 해소하고 생성 실패를 게이트 실패로 전파한다.

## 5. 기능 요구사항 추적표 — 활성 47건

상태: **L**=해당 구현의 로컬 자동화 확인, **P**=부분 검증/실환경 미검증, **F**=확인된 인수 위반, **H**=과거 migration/후속 결정에 따른 재기준 필요. L도 모든 입력·모든 runtime 조건에 대한 완전 증명은 아니다.

표의 `BTests`는 `backend/tests/`, `FTests`는 `frontend/test/`를 뜻한다.

| 요구사항 | 상태 | 구현·시험 증거 및 잔여 |
|---|---|---|
| FR-1 | L | discovery validator, FTests `validate/searchScreen`, hero E2E; 자연어 입력/빈 값/길이 검증 |
| FR-2 | P | discovery real adapters/orchestrator 124 tests + live 한국어/영어 검색; cold timeout·F03/F12로 품질 인수 미충족 |
| FR-3 | P | ranker/reranker·fail-soft·예산 gate 테스트; 실제 ranking 품질 정량 평가는 기존 결정대로 보류 |
| FR-4 | P | FTests `resultCard/paperDetailSource`, phone WebKit; 360~430 전 폭 및 desktop 전체 시각 검증 미실행 |
| FR-5 | F | U6 grounding/도메인 tests는 통과하나 F02/F03/F12로 엄격 근거화 인수 실패 |
| FR-6 | F | ingestion 318 tests, source/dedup/DocModel/queue 로직 존재; F03의 현 코퍼스는 요구된 1년 범위 미충족 |
| FR-7 | P | root accounts tests + mock signup/login/logout E2E; live 이메일 전달/실 계정 로그인 완료 미검증 |
| FR-8 | L | library saved-search service/controller/pagination/SQL + FTests `apiLibrary/libraryScreens` |
| FR-9 | L | library add/remove/idempotency/owner isolation + FTests `saveToLibrary/libraryScreens` |
| FR-10 | L | history service/event consumer/rerun, direct publisher·anonymous guard, library tests |
| FR-11 | F | 에러 UI 및 다수 fault tests 통과; F11의 empty/degraded 구분 실패 |
| FR-12 | F | summarization/grounding/anchor + FTests summary suites; F05의 cold inline 생성 시간 예산 충돌 |
| FR-13 | F | structured translator/DocModel-preserving tests 통과; F02 캐시 오염, F05 timeout |
| FR-14 | P | glossary/persona/cache overlay tests; 실제 개인 용어집 persistence는 신규 DB에서 F08 영향 |
| FR-15 | P | BTests `test_citation_graph*`, FTests `citationTreePanel`; live provider 계약 gate는 skip |
| FR-16 | P | citation save/stale snapshot/failure tests; 실제 외부 citation→저장 사용자 여정 미검증 |
| FR-17 | F | 자산 writer/reader 실제 PG 통합 3개 및 renderer tests 통과; 원격 MinIO image serving은 F07 |
| FR-18 | F | DocModel builder/viewer/anchor tests; F01 private namespace 격리, F07 이미지 서빙 |
| FR-19 | P | BTests `test_personalization`, retention purge 함수/설정·초기화 tests; 현재 launchd installer의 retention-job 배선/주기 실증 미확인 |
| FR-20 | P | bounded boost·fallback·default API + FTests personalization; 인증된 live 개인화 적용 효과 미검증 |
| FR-21 | H | 과거 v4 dual-write/migration 요구. 현재 local read alias v3 및 모델 전환 결정과 요구사항 정합 필요 |
| FR-26 | P | password reset 단일사용/만료/세션 무효화 및 reset UI tests; 실제 메일 수신 미검증 |
| FR-27 | P | Google/ORCID state/nonce/JWKS/identity tests; live Google start 302까지만, ORCID start는 503/off |
| FR-28 | F | credential lifecycle 테스트 통과; F04의 evidence 및 신규 owner 데이터 파기 누락 |
| FR-29 | L | `test_auth_input_tolerance/test_controller_http`, frontend 422/입력 에러 처리 tests |
| FR-30 | P | novelty job/PDF coordinator/worker tests; 실 원고→큐→모델 전체 분석 미검증, F01 격리 문제 |
| FR-31 | P | novelty U2 full/Evidence port/external adapter tests; 실제 GitHub/dataset 도구 호출 미검증 |
| FR-32 | P | novelty artifact/source-ref/quality-gate tests; 실제 모델의 bounded 제안 품질은 미검증 |
| FR-33 | P | experiment-plan 필수 field/source validation tests; 실 모델 출력 인수 미검증 |
| FR-34 | P | manuscript similarity/warning tests; 실제 표절/AI어투 false-positive 품질 평가는 미검증 |
| FR-35 | P | progress/cancel/persistence/Notion 승인·token tests + UI; 실제 사용자 Notion export 미실행 |
| FR-36 | P | research/evidence multi-turn/SSE/polling/session tests; 실제 모델 다중 턴 사용자 여정 미검증 |
| FR-37 | P | evidence scope/tools/extractor/quality gates/tests; F03 코퍼스 입력 문제 및 실제 주장 충실도 평가 잔여 |
| FR-38 | F | session owner/삭제 tests 통과; F01 private DocModel 우회 읽기, F04 계정 파기 누락 |
| FR-39 | P | behavior record/dedup/failure tests 통과; 운영 90일 retention 실행 근거는 미확인 |
| FR-40 | L | FTests `agentChatScreen/agentChatReducer`, WebKit agent 탭/모드 진입 |
| FR-41 | L | 세션 drawer/목록/멀티턴 frontend 및 backend repository tests |
| FR-42 | L | timeline ordering/reducer fast-check/SSE parsing tests; mock browser timeline 확인 |
| FR-43 | P | PDF/MD/TXT allowlist·binary BFF·실패/저하 UI tests; 실제 PDF ingestion까지 browser E2E는 미실행 |
| FR-44 | L | onboarding gate/UI/backend tests; WebKit 첫 로그인 picker 노출·skip 확인 |
| FR-45 | L | onboarding event-only seed, U9 category/keyword aggregation/boost tests |
| FR-46 | P | ORCID suggestion derivation/failure tests; 현재 ORCID 신규 로그인 entry는 off |
| FR-47 | F | digest opt-in/empty suppression/send tests 통과; F09 unsubscribe 인증 벽·404 링크, harvest 재개는 의도적 보류 |
| FR-48 | L | topic CRUD/owner isolation/cap/duplicate/settings tests + FTests trends settings |
| FR-49 | P | scholarly web-reference URL/host/noop/claims 분리 tests; 실제 provider 응답과 UI 전체 연결 미검증 |
| FR-50 | L | plans/quota resolver/agent quota tests + FTests `apiPlans/planSection`; 실 결제는 범위 밖 |
| FR-51 | L | admin grant/revoke/월말 계산/만료/paid-through-period tests; 신규 live grant는 미실행 |

## 6. 비기능·품질·범위 정합

### 6.1 NFR 및 운영

| 요구사항 | 판정 |
|---|---|
| NFR-P1 | cold 샘플 10초대, warm 샘플 0.05~3.22초. P50/P95 및 50-user 부하는 미측정; SLA 충족 승인 불가 |
| NFR-P2 | F05의 10초/300초 시간 예산 충돌. 큰 입력의 async 구현만으로 작은 inline 입력 문제가 해소되지 않음 |
| NFR-P3 | citation cache/provider 실패 로직 테스트; live cache P50<500ms 미측정 |
| NFR-P4 | 비차단 event/profile fallback 테스트; 운영 latency 증분은 미측정 |
| NFR-P5/P6/P7 | job/SSE/keepalive/poll/reconnect/UI tests 존재. 실제 모델·큐·브라우저 전체 지연 미검증 |
| NFR-S1 | single-host 현재 구조의 동시 50명·수천 계정 처리 용량 미검증; F10 shared limiter도 해결 필요 |
| NFR-S2/NFR-M2 | 문서는 v4 migration, 현재 runtime은 local model + v3 alias. 후속 결정으로 요구사항 baseline 정리 필요 |
| NFR-C1 | CostGuard/쿼터 로직 tests 통과; 현재 local 모델의 자원/비용 운영 한도 재정의 필요. master 문서의 $300/$1,600 혼재도 정리 대상 |
| NFR-A1 / C-4 | 단일 Mac + single-node stores는 문서의 single-region multi-AZ 형태를 충족하지 않음. 현재 호스팅 결정에 맞는 가용성 목표 재기준 필요 |
| NFR-R1/R2 | 다수 fault paths 통과. F05/F11에서 정상 완료·저하 표시 계약 실패 |
| NFR-R3 | novelty per-source degraded/failure 테스트; live 외부 source 장애 조합은 미검증 |
| NFR-U1/U2 | phone E2E 및 phone-frame 구현 확인. 모든 화면/폭/desktop 시각 검증 미실행 |
| NFR-X1 | 접근성 관련 unit assertions 일부; 전체 WCAG AA 감사 미실행(기존 비차단 목표) |
| NFR-O1 | heartbeat/상태 명령 동작. 전체 metrics/traces/dashboard/alert 전달·90일 audit 보존은 입증되지 않음 |
| NFR-M1 | 모듈/공유 계약 구조 확인. F08 migration registry와 F13 type guard가 정합성 결함 |

운영 runbook의 알려진 gap은 현재 사실과 구분했다. 예를 들어 runbook에는 Google login도 off라고 쓰여 있으나 이번 실측 start는 302였다. registration/email 비활성 문구는 현재 발송을 직접 검증하지 않아 확정 장애로 승격하지 않았다.

호스트 `fdesetup status`는 **FileVault Off**였다. 이는 자체로 모든 하드웨어 저장 암호화의 부재를 증명하지 않지만, 승인된 managed-key/저장소 암호화 요건의 충족 증거도 아니다. Compose의 datastore transport는 loopback HTTP/plain TCP이며, 기존 TLS 요건과의 차이는 명확하다.

### 6.2 품질 요구사항

| 요구사항 | 증거/판정 |
|---|---|
| QT-1 | **실패**: F03의 잘못된 실제 논문 식별자/메타, F12 범위 밖 질의의 결과 노출 |
| QT-2 | 구조적 ranking tests는 통과. 실제 held-out Recall@10/nDCG/MRR는 미검증; FR-3 후속 결정의 정량 평가 유예를 존중 |
| QT-3 | **부분 실패**: F11이 장애를 정상 empty로 표시 |
| QT-4 | Hypothesis/fast-check 실행. Python 이번 실행은 fixed seed, CI 전체 seed 고정/로깅은 미충족 |
| QT-5 | 도메인 grounding tests 통과와 별개로 F02가 신뢰할 수 없는 입력을 다른 사용자의 논문 번역으로 유통 |
| QT-6 | citation graph depth/node/cycle/DTO PBT 및 tests 통과. 실 provider contract 미실행 |
| QT-7 | 개인화 DTO/dedup/owner/reset/aggregation tests 통과. 운영 retention 실행 확인 잔여 |
| QT-8 | evidence quality/owner/session tests 통과. 공용 U7 route로 private 입력을 읽는 F01과 삭제 F04는 횡단 인수 실패 |
| QT-9 | ingestion/DocModel/version/dedup tests 통과. 현 운영 코퍼스 완성도·진실성은 F03으로 미충족 |
| QT-10 | novelty artifact/state/source/Notion 경계 tests 통과. 실제 LLM 품질·위험 신호 오탐 평가 미실행 |
| QT-11 | frontend helper/reducer/UI/transport tests + agent browser smoke 통과. 실제 backend PDF/LLM multi-turn 통합 잔여 |

### 6.3 제약/결정의 정합

- C-1/§12의 PDF 미저장 문구는 이후 arXiv raw-cache 및 사용자 업로드 PDF 결정과 함께 정리해야 한다. 현재 구현을 단순히 "무허가 저장"으로 판정하지 않았다.
- C-2의 생성 산문 경계는 evidence/novelty 후속 설계와 실 모델 산출물로 재검증할 필요가 있다. bounded artifact 구조 테스트만으로 모든 생성 내용의 충실도를 증명할 수 없다.
- C-3 phone web, C-7 event-only seeding, C-11 웹 metadata 링크백/noop 경계, C-12 결제 제외는 코드/테스트에서 확인했다.
- C-4 multi-AZ는 현재 local host 토폴로지와 불일치한다. C-5 AWS 지향 문구도 현재 runtime과 정합이 필요하다.
- FR-6 최근 1년 코퍼스의 실 데이터 인수는 F03으로 실패했다. C-6의 AI/ML 분야 정합은 fixture 메타데이터만으로 승인할 수 없으며 원 출처별 검증이 필요하다.
- C-8/C-10은 개발 순서 결정이며 실행 기능의 정상 여부를 대신하지 않는다. C-9 daily harvest 중단은 명시된 보류 결정이다.

## 7. 활성 확장 규칙 평가

Security/Resiliency Full, PBT Partial 결정을 계승했다. 아래 `미검증`은 적용 대상이나 전체 기준의 증거가 부족하다는 뜻으로 **준수 통과로 계산하지 않는다**. N/A는 명시된 적용 경계에만 사용한다. 확인된 blocking finding이 있어 Operations/전면 준수 승인은 불가하다.

### Security

| 규칙 | 상태 | 근거 |
|---|---|---|
| SECURITY-01 | 미충족/일부 미검증 | datastore 간 TLS 요건과 현재 plain loopback 구성 불일치; managed-key at-rest 미입증 |
| SECURITY-02 | 미검증 | 현 Cloudflare/tunnel access-log 중앙 보존 정책 미확인 |
| SECURITY-03 | 부분 검증 | 로그/비밀 redaction tests 존재; `backend/app.py:49` 기본 format은 timestamp/request ID 없는 일반 로그이며 중앙 수집 전체 미확인 |
| SECURITY-04 | 확인 범위 충족 | 라이브 HTML의 요구 보안 헤더와 nonce 확인 |
| SECURITY-05 | 부분 검증 | DTO bounds/negative tests 통과; 요약 입력/source 신뢰 경계는 F02 |
| SECURITY-06 | 미검증 | 현재 OS/DB/MinIO 최소 권한 미감사; AWS IAM는 폐기 runtime에 N/A |
| SECURITY-07 | 확인 범위 충족 | 운영 datastore host ports가 loopback 한정; tunnel 단일 public ingress |
| SECURITY-08 | **미충족** | F01 교차 사용자 private 문서 읽기, F04 파기 누락 |
| SECURITY-09 | **미충족** | F03 production fixture 노출; 실제 hardening baseline 재정립 필요 |
| SECURITY-10 | **미충족** | F06 dependency audit 실패; production Compose에도 latest/mutable image 태그 존재 |
| SECURITY-11 | **미충족** | F10 client별 gateway bucket 정합 실패 |
| SECURITY-12 | 부분 검증 | adaptive hashing/admin MFA/session/cookie/brute-force tests 통과; 외부 로그인/메일 실경로 미검증 |
| SECURITY-13 | **미충족** | F02 입력/공유 산출물 무결성, F13 계약 실패 은폐 |
| SECURITY-14 | 미충족/일부 미검증 | local rotate/truncate 기반 로그는 90일 append-only audit 보존을 보장하지 않음; 외부 alarm 전달 미확인 |
| SECURITY-15 | **미충족** | F11 실패 provenance 소실; 정상 경로 예외 처리 tests만으로 전체 fail-safe 보장 불가 |

### Resiliency

| 규칙 | 상태 | 근거 |
|---|---|---|
| RESILIENCY-01 | 부분 검증 | 유닛/의존 관계 및 실패 경계 확인; cloud→single-host 영향의 공식 baseline 정리 필요 |
| RESILIENCY-02 | 미충족/미검증 | multi-AZ 목표 불일치; RTO/RPO/availability 실측 미실행 |
| RESILIENCY-03 | 확인 범위 충족 | 기존 git-flow/PR 규약 유지; 감사는 지정 HEAD에서 수행 |
| RESILIENCY-04 | 부분 검증 | install/rebuild/restart 스크립트 존재; rollback/DB restore 실제 연습 미실행 |
| RESILIENCY-05 | 미검증 | 현재 전체 metrics/logs/traces 수집·dashboard·alert delivery 입증 부족 |
| RESILIENCY-06 | **미충족** | readyz는 mount 목록, heartbeat는 shallow health; embedding timeout 중에도 ready/healthy |
| RESILIENCY-07 | 미검증 | 운영 용량/replication/backup failure 경보 전체 미확인 |
| RESILIENCY-08 | **미충족** | single-host/single-node이며 승인 문서의 multi-zone 구성 아님 |
| RESILIENCY-09 | 미충족/미검증 | 현재 고정 host 토폴로지에 기존 auto-scaling 요건 재기준 필요; 용량 부하 미측정 |
| RESILIENCY-10 | **미충족** | F05 browser/BFF/API 시간 예산 충돌, F11 저하 표시 유실 |
| RESILIENCY-11 | 부분 검증 | local backup/rebuild runbook 존재; 복구 목표와 대조한 restore 실행 미확인 |
| RESILIENCY-12 | 부분 검증 | DB backup periodic job last exit 0 확인; 아티팩트 offsite 백업/restore integrity 미검증 |
| RESILIENCY-13 | 미검증 | 실제 장애 복구/검증 drill 미실행 |
| RESILIENCY-14 | 부분 검증 | unit fault-injection 및 이번 고장 반례 수행; 운영 failover/DR drill은 별도 |
| RESILIENCY-15 | 부분 검증 | incident/heartbeat runbook 존재; 외부 호출/실제 알림 전달까지 미검증 |

### PBT

| 규칙 | 상태 | 근거 |
|---|---|---|
| PBT-01 | N/A(이번 설계 변경) / 기존 일부 확인 | 새 functional design을 생성하지 않은 검증 작업; 기존 속성/설계 문서 참고 |
| PBT-02 | 부분 검증 | DTO/직렬화 round-trip PBT 실행. 모든 역함수 쌍의 완전 커버리지는 주장하지 않음 |
| PBT-03 | 부분 검증 | ranking/dedup/graph/event invariants 실행; 횡단 F01/F02는 기존 suite가 놓친 인수 |
| PBT-04 | 권고·부분 검증 | idempotence tests 존재; global Partial에서는 비차단 |
| PBT-05 | 권고·미검증 | 전체 oracle/model coverage 전수 평가 미실행 |
| PBT-06 | 권고·부분 검증 | state transitions/reducer tests 존재; 전체 stateful model 전수검증 아님 |
| PBT-07 | 부분 검증 | 구조화 도메인 generator 사용 확인; 전 generator 품질 감사 미실행 |
| PBT-08 | **CI 기준 미충족** | 이번 Python은 fixed seed 실행. CI pytest 명령 및 frontend property test에는 전 run seed 고정/로깅 정책이 없음 |
| PBT-09 | 확인 범위 충족 | Python Hypothesis, TS fast-check가 선언·설치·실행됨 |
| PBT-10 | 권고·부분 검증 | 예시/PBT 보완 구조 확인; 모든 critical path 양쪽 커버리지 증명은 아님 |

Agent Chat의 별도 Full PBT 요구도 기존 테스트 전수 통과만으로 완전 충족 처리하지 않았다.

## 8. 재현 명령과 남은 검증

### 기존 검사 재실행

모든 명령은 운영 `.env`와 분리한 checkout에서 실행한다. 작업 디렉터리를 각 표의 경로로 설정한다.

| 작업 디렉터리 | 명령 |
|---|---|
| `backend` | `uv sync --frozen --python 3.13` 후 `uv run --frozen --no-sync pytest --hypothesis-seed=20260918 -ra` |
| `shared/python` | 위와 같은 설치/pytest 및 `uv run --frozen --no-sync python tools/generate.py --check` |
| `ingestion` | `uv sync --frozen --python 3.13 --all-extras` 후 pytest |
| `backend/modules/discovery` | `uv sync --frozen --python 3.13 --extra api` 후 pytest |
| `backend/modules/summarization` | `uv sync --frozen --python 3.13 --all-extras` 후 pytest |
| `ops` | `uv sync --frozen --python 3.13` 후 pytest |
| repo root | `backend/.venv/bin/python -m pytest tests -c pytest.ini --hypothesis-seed=20260918 -ra` |
| 각 Python 레인 | 해당 `.venv/bin/ruff check . --output-format=concise` |
| repo root | `backend/.venv/bin/ruff check backend/modules/accounts backend/modules/library backend/modules/ops tests --output-format=concise` |
| `frontend` | `corepack pnpm@9.15.9 install --frozen-lockfile`, `tsc --noEmit`, `pnpm run lint`, `vitest run --maxWorkers=2`, `next build` |
| `frontend` | `node scripts/gen-types.mjs` 및 `git diff --exit-code -- types/` — 현재 F13 때문에 exit 0만으로 성공 판정 금지 |
| `frontend` | WebKit E2E는 별도 port 3109 config 사용; [재현 문서](project-verification-2026-09-18-reproductions.md) 참조 |

실제 실행 환경은 `env -i`로 HOME/PATH/LANG만 기본 전달하고 Python 검사는 `AWS_EC2_METADATA_DISABLED=true`, `AWS_CONFIG_FILE=/dev/null`, `AWS_SHARED_CREDENTIALS_FILE=/dev/null`을 사용했다. 브라우저 다운로드/가상환경/합성 테스트는 임시 디렉터리에 격리했다.

추가 PG 검사: 전용 Postgres 16 / `127.0.0.1:15439`, 별도 database/user를 준비하고 `DOCSURI_TEST_PG_DSN`을 지정해 `ingestion/tests/test_asset_store_real.py`, `summarization/tests/test_assets_rds_real.py` 실행. 운영 DB와 분리했으며 검사 후 컨테이너 종료·자동 제거했다.

의존성 감사: frontend `pnpm audit --prod --audit-level high`; Python `uvx pip-audit --path <isolated-project>/.venv/lib/python3.13/site-packages --skip-editable --progress-spinner off`.

### 미검증 인수

- 실 가입 이메일·재설정 이메일 수신, 실제 Google/ORCID callback 완료, 실제 사용자 Notion 연결/export.
- 실제 PDF 업로드에서 워커/모델을 거쳐 전체 evidence/novelty 결과가 브라우저에 도달하는 인증된 end-to-end 여정.
- 실제 LLM 요약/번역/근거/novelty의 held-out 내용 충실도와 위험 신호 false-positive 품질.
- 모든 화면의 360~430px/desktop layout, 전체 WCAG AA.
- NFR-P1 P50/P95, 50-user concurrency, 장시간 stability, RTO/RPO 및 restore/DR drill.
- current host의 최소 권한·모든 로그/backup 경로·알람 전달. archived AWS CDK 재배포는 현재 runtime 검증 대상이 아니다.
- 함수별 line/branch coverage와 모든 가능한 입력 조합. 이번 테스트 통과 수를 100% 기능/요구사항 coverage로 환산하지 않는다.

## 9. 권장 수정 순서

1. **F01/F02**: private source의 owner 인가와 canonical source/cache 경계를 먼저 고친다.
2. **F03/F06**: 운영 corpus 진실성과 patched dependency baseline을 복구한다.
3. **F04/F08**: 계정 데이터 전수 파기와 fresh-install/restore migration을 일원화한다.
4. **F05/F07/F09/F10/F11**: 생성 timeout, 원격 자산, digest 링크/무로그인 해지, client별 limiter, 빈 저하 결과를 실제 통합 경로에서 보강한다.
5. **F12/F13**: no-match 품질 gate와 실패를 숨기지 않는 계약 생성 gate를 확립한다.
6. 현재 local deployment에 맞춰 요구사항·가용성/복구/비용/보존 baseline을 정리하고 미검증 실환경 인수를 수행한다.

**검증 결과는 CHANGES REQUIRED다.** 이 보고서의 완료는 감사 수행 완료이며 제품 전체 합격/Operations 승인이 아니다.
