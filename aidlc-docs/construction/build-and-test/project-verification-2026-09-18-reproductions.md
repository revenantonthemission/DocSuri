# 감사 반례 및 검증 기록 — 2026-09-18

기준 HEAD: `32a424d`. 종합 판정과 요구사항 추적은 [전체 검증 보고서](project-verification-2026-09-18.md)에 있다.

## 1. 격리 실행 구성

- detached worktree: `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/docsuri-verification-20260918`.
- Python 3.13.7, 프로젝트별 frozen lock 가상환경, Python PBT seed `20260918`.
- frontend pnpm 9.15.9 frozen install, Node 24.14.0.
- 운영 `.env` 대신 clean environment 사용. AWS metadata/credential discovery 비활성화.
- PostgreSQL 16 전용 컨테이너: `docsuri-audit-20260918-pg`, loopback 15439, 별도 audit database, tmpfs data. 실행 후 종료·자동 제거.
- WebKit은 임시 browser cache에 설치하고 compiled frontend를 loopback **3109**에서 실행했다.

브라우저 config는 기존 `playwright.config.ts`를 상속하고 다음 항목만 바꿨다:

```typescript
use: { ...base.use, baseURL: 'http://127.0.0.1:3109' },
workers: 1,
webServer: {
  command: 'node scripts/prepare-standalone-assets.mjs && node .next/standalone/server.js',
  url: 'http://127.0.0.1:3109',
  env: { PORT: '3109', HOSTNAME: '127.0.0.1' },
  reuseExistingServer: false,
  timeout: 30_000,
}
```

기존 `hero.spec.ts` 2개와 `agent-chat.spec.ts` 1개가 통과했다. 브라우저 테스트는 mock transport이고 실제 이메일/외부 로그인/LLM/Notion 검증을 대신하지 않는다.

## 2. 추가 회귀 인수 4건

아래는 모두 합성 데이터 또는 loopback 대역을 사용한 오프라인 검사다. 운영 사용자 데이터에 대한 접근 검사는 수행하지 않았다. 향후 수정에는 이 인수 조건을 정식 회귀 테스트로 편입한다.

### R1 — private 문서 소유권

- **요구**: authenticated caller와 private 문서 owner가 다르면 읽기를 거부한다.
- **사용한 실제 컴포넌트**: U7 router, `SummarizationOrchestrationService.doc_model`, `S3DocModelReader`.
- **대역**: 기존 `tests/test_docmodel_endpoint.py`의 fake S3/Request 및 `tests/stubs.py`의 orchestrator factory.
- **합성 fixture**: 현재 schema/parser version, PDF provenance를 가진 private DocModel. 본문은 `AUDIT owner A private manuscript`라는 검사 전용 문자열.
- **실제 결과**: 다른 합성 principal의 요청에 **200**, `status=ok`, 원고 sentinel 포함.
- **실패한 assertion**: 거부 상태여야 한다는 소유권 인수.
- **회귀 완료 조건**: owner는 정상 읽기, non-owner는 존재 여부를 노출하지 않는 거부, public corpus 읽기는 정상. source 선택·파생 캐시 읽기에도 동일한 격리.

### R2 — 신뢰할 수 없는 원문과 공유 생성물 분리

- **요구**: client-supplied 원문이 다른 사용자의 정식 논문 번역 결과를 결정하지 않는다.
- **사용한 실제 컴포넌트**: `SourceSelector`, cache-key builder, structured translator, summary orchestrator.
- **대역**: 기존 `StubStore`, 입력 내용을 구별 가능하게 번역하는 `StubLlm`.
- **합성 fixture**: 동일 논문/버전과 서로 다른 원문을 가진 두 사용자의 요청. 한쪽 입력에는 `CONTROLLED_OVERRIDDEN_SOURCE` sentinel을 넣었다.
- **실제 결과**: 정식 원문을 요청한 사용자의 응답이 **cached=true**이고 다른 입력의 sentinel을 포함했다.
- **실패한 assertion**: 공유 응답에 다른 입력의 sentinel이 없어야 한다는 데이터 무결성 인수.
- **회귀 완료 조건**: 서버의 canonical source가 우선하고, 서로 다른 source identity가 동일 공유 artifact로 합쳐지지 않는다. legitimate shared-cache 재사용과 glossary overlay는 유지한다.

### R3 — 생성 경로의 시간 예산

- **요구**: 로컬 모델에서 허용하는 정상 생성 완료 시간이 frontend transport 계층과 충돌하지 않는다.
- **사용한 실제 컴포넌트**: BFF POST handler 및 `HttpTransport`.
- **대역**: 임의의 빈 loopback port에 Node HTTP server를 만들고, **12초 뒤 유효한 200 JSON 응답**을 반환하도록 했다.
- **실제 결과**: BFF는 **약 10.02초에 504**를 반환했다.
- **실패한 assertion**: 정상 upstream 완료를 반환해야 한다는 인수.
- **회귀 완료 조건**: browser/BFF/API/worker 시간 예산을 정렬하고, 동기 예산을 넘는 요청은 pending/job 상태로 안전하게 전환한다. genuine hang은 여전히 bounded timeout으로 종료한다.

### R4 — client별 rate-limit 식별

- **요구**: 신뢰된 ingress를 거친 서로 다른 사용자가 gateway에서 동일한 loopback client로 합쳐지지 않는다.
- **사용한 실제 컴포넌트**: BFF POST handler 및 `HttpTransport`의 header 구성.
- **대역**: upstream fetch recorder와 서로 다른 두 documentation-range client IP.
- **실제 결과**: 두 upstream request의 client IP header 관찰값이 **`[null, null]`**이었다.
- **실패한 assertion**: 두 클라이언트가 gateway에서 식별 가능해야 한다는 인수.
- **회귀 완료 조건**: 신뢰 경계에서 검증한 client identity만 전달하고, 클라이언트별 독립 bucket을 적용한다. 신뢰되지 않는 입력 header를 그대로 신뢰하는 수정은 인수 해소가 아니다.

### 실행 결과 원문 요약

```text
Python audit counterexamples: 2 failed in 0.17s
  private userdoc owner isolation: received 200 instead of rejection
  shared translation source isolation: cached response contained controlled sentinel

Frontend audit counterexamples: 2 failed
  slow valid generation: expected 200, received 504 (~10020ms)
  client identity forwarding: [null,null], expected distinct identities
```

## 3. 추가 통합 관찰

| 검사 | 기대/계약 | 실제 |
|---|---|---|
| 빈 Postgres startup migration | 배포 모듈의 필수 테이블 생성 | accounts/library/mypage 생성, evidence_sessions/evidence_turns/user_glossary 없음 |
| 실제 SQL owner purger + 합성 행 | 파기 대상 owner의 데이터 제거 | saved_searches만 0행, evidence/onboarding/trends 표본은 각각 1행 유지 |
| U7 asset presign + local endpoint | 원격 browser가 접근 가능한 승인된 URL | `http`, host `127.0.0.1`, port `9000`; 실제 HTML CSP에는 해당 host 없음 |
| empty result + lexical-only mode | 결과 0건이어도 저하 표시 보존 | `degraded=false`, `degradationMode=null` |
| library schema generation | schema fetch/resolve 실패 시 gate 실패 | 실패 메시지를 출력하고 schema skip 후 exit 0 |

Postgres 실제 asset writer/reader 검사는 별도 `DOCSURI_TEST_PG_DSN`을 지정했다:

```text
ingestion/tests/test_asset_store_real.py: 1 passed
summarization/tests/test_assets_rds_real.py: 2 passed
```

Reader 테스트 프로세스 종료 시 psycopg pool thread cleanup 경고가 있었다. assertion 성공과 종료 경고를 구분해 기록한다.

## 4. 라이브 읽기 증거

- 공개 BFF의 `transformer attention` 결과에 `Vision Transformers at Scale` / `D. Vision` / `2401.00003v1` 포함.
- 실제 [arXiv 2401.00003](https://arxiv.org/abs/2401.00003)은 `Generative Inverse Design of Metamaterials with Functional Responses by Interpretable Learning`이다.
- read alias `docsuri-corpus` → `docsuri-corpus-v3`; `_search` size=0 aggregation은 distinct paper IDs **11**을 반환했다.
- `_cat/indices`는 v3 **599 documents**를 반환했고, year terms aggregation에는 **2025/2026 bucket이 없었다**.
- 초기 임베딩은 timeout 후 회복했다. 회복 후 `banana cake recipe`가 no-match 대신 11개 후보를 반환했다.
- 무로그인 unsubscribe의 invalid-token 프로브는 gateway **401**이었다.
- 메일 생성 함수의 `/papers/1706.03762`는 공개 사이트 **404**, 실제 `/paper/1706.03762`는 **200**이었다.

운영 프로브의 결과를 정식 실 사용자 로그인·메일 발송·외부 export·부하/DR 검증으로 확대 해석하지 않는다.

## 5. 보존 정책

감사 전용 코드와 가상환경은 detached 임시 checkout에 만들었다. 주 checkout의 애플리케이션 소스/테스트는 변경하지 않았다. 재현 인수·구성·결과는 본 문서와 종합 보고서에 보존한다. 직접 만든 합성 테스트/config 4개만 untracked임을 확인한 뒤 임시 checkout을 제거했으며, PostgreSQL 컨테이너도 종료·자동 제거했다. 상세 정리는 최종 감사 로그에 기록했다.
