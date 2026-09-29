# unit-of-work-dependency.md — 유닛 의존성 매트릭스

> **현재 산출물**: 하단 `2026-09-19 REM Dependency Model`이 UGP1=A/DAD1/WPR2에 따른 현재 모델이다. 상단의 배포·통신 설명은 이전 product 구성을 기록한 이력이며, 새 모델은 merge/source/runtime/data/activation 의존을 구분한다.

**단계**: INCEPTION → Units Generation · **일자**: 2026-06-15
**근거**: `application-design/component-dependency.md`. 종류: **sync**(동기 호출/REST), **event**(이벤트 백본, 비동기), **lib**(빌드 시 공유 계약/인터페이스 의존).

---

## 의존성 매트릭스 (from → to)

| from \\ to | U1 | U2 | U3 | U4 | U5 | U6 | U7 | U8 | U9 | shared |
|---|---|---|---|---|---|---|---|---|---|---|
| **U1 Ingestion** | — | — | — | — | — | event(인시던트/관측 발행) | — | — | — | lib(VectorSpec·DocModel schema·이벤트) |
| **U2 Discovery** | (Corpus 인덱스 read = capability, 코드 의존 아님) | — | — | event(SearchExecuted 발행) | — | lib(근거화·비용 후크 via `shared/ports`) | — | — | sync(프로필 read) + event(search/open) | lib(VectorSpec·DTO) |
| **U3 Accounts** | — | — | — | — | — | — | — | — | — | lib(DTO) |
| **U4 Library** | — | event(SearchExecuted 소비) | sync(인가 결정 위임) | — | — | — | — | — | event(library add/remove) | lib(DTO) |
| **U5 Frontend** | — | sync(REST, 게이트웨이 경유) | sync(REST) | sync(REST) | — | sync(게이트웨이 진입) | sync(REST, 게이트웨이 경유) | sync(REST, 상세보기 경유) | sync(설정/삭제/출처 앵커 event) | lib(DTO) |
| **U6 Reliability/Ops** | event(인제스천 신호 소비) | sync(게이트웨이→U2 핸들러 호출) | sync(authz 위임 호출) | sync(게이트웨이→U4 핸들러) | — | — | sync(게이트웨이→U7 핸들러) | sync(게이트웨이→U8 핸들러) | sync(게이트웨이→U9 핸들러) | lib(이벤트·ports) |
| **U7 Summarization** | (DocModel/FullText S3 read = capability, 코드 의존 아님) | — | — | — | — | lib(근거화·비용 후크 via `shared/ports`) + event(관측/비용 발행) | — | sync(요약 출처에서 각주 트리 열기) | sync(기본값/profile read) + event(summary/translation/glossary) | lib(DTO·ports) |
| **U8 Citation Graph** | — | — | sync(로그인/인가 경로) | sync(노드 저장) | — | lib(레이트리밋·관측 포트) + event(관측 발행) | — | — | — | lib(DTO·events) |
| **U9 Personalization** | — | — | sync(로그인/인가 경로) | — | — | lib(관측 포트) + event(저하/집계 신호) | — | — | — | lib(DTO·events) |
| **shared** | — | — | — | — | — | — | — | — | — | — (leaf) |

> U5 사용자 경로는 **U6 게이트웨이를 단일 진입**으로 U2/U3/U4/**U7/U8/U9** 핸들러에 도달한다(표의 U5→U2/U3/U4/U7/U8/U9 sync는 게이트웨이 프런티드).
> **U7은 U2와 동일 의존 패턴**: U1 DocModel/FullText는 capability read(코드 의존 아님), U6 근거화·비용 후크는 `shared/ports` 인터페이스 의존(U6 구현) → U7↔U6 코드 순환 없음.
> **U8은 로그인 필수 상세보기 보조 경로**: U3/U6 인증·게이트웨이 경로를 통과하고, 노드 저장은 U4 Library 계약을 호출한다. 외부 citation API는 U8 내부 어댑터 뒤에 둔다.
> **U9는 비차단 개인화 보조 경로**: U2/U4/U7/U5 성공 경로가 의미 이벤트를 기록하거나 프로필을 읽지만, 실패해도 본 기능은 기본 비개인화 경로로 계속된다.
> **연구 에이전트(2026-06-28)**: 구 통합 U11은 폐기·2유닛 분리(차터 §4).
>
> **U10~U16 의존 요약 (2026-08-03 유닛 재구성 — 매트릭스는 U1~U9 원본 보존, 이후 유닛은 본 요약이 SSOT)**:
> - **U10 MyPage** → U3 sync(세션/인가·계정 메뉴 위임), U16 sync(플랜 표시 값 — mock 구독 대체 예정). 관심 논문·로그아웃은 FE가 U4/U3 직접 호출(U10 코드 의존 없음).
> - **U11 Evidence** → U2 sync(검색)·U1 capability(DocModel S3 read + `user_docmodel` 포트)·U6 lib(`shared/ports` 근거화·비용)·U7 배관 재사용. 세션 셸(`evidence/sessions/`, 구 research)은 U11 내부 — 외부 의존 동일.
> - **U12 Novelty** → U11 lib(`EvidenceFormationPort`)·U2 `full`·U1 `user_docmodel` 포트·외부 탐색(GitHub/데이터셋).
> - **U13 Agent Chat FE** → U11 sync(REST/SSE `/api/research`)·U12 sync(novelty 잡 API). 코드 의존은 DTO lib뿐(타 유닛 비차단).
> - **U14 Onboarding** → U9 event(관심사 시딩 — 직접 프로필 기록 금지 C-7)·U3 sync(가입/로그인 경로).
> - **U15 Trends** → U1 capability(코퍼스 임베딩 read)·U6 lib(email 경로·관측).
> - **U16 Plans** → U6 lib(CostGuard에 쿼터 값 공급 — 계약 불변, NFR-C1).
> - **U1 `user_docmodel` 포트(2026-08-03)**: U11/U12는 `docsuri_shared.ports.UserDocModelCoordinatorPort`로 주입 소비(의존성 역전, U11↔U6 패턴) — **코드 DAG 비순환 유지**.

## 통신 패턴
- **동기 REST**(NFR-P1 읽기 경로): U5 → U6 게이트웨이 → U2/U3/U4/U9 핸들러 → 응답. U4 rerun도 동일 경로 재진입(백도어 금지).
- **온디맨드 상세보기 REST**(NFR-P2/P3): U5 논문 상세보기 → U6 게이트웨이 → U7/U8 핸들러 → 응답. 검색 NFR-P1 비대상.
- **개인화 이벤트/프로필**(비차단): U2/U4/U7/U5 성공 경로 → U9 event recorder/profile API; 실패 시 기본 기능 유지.
- **이벤트 백본**(비동기): source별 스케줄/backfill/rebuild → U1; U2 `SearchExecuted` → U4(이력); 탐지기(비용/할루시네이션/반쪽짜리) → IncidentEventPublisher; U9 저하/집계 신호; 관측성 팬아웃.
- **lib(의존성 역전)**: 횡단 후크(근거화·비용) 인터페이스는 `shared/ports`에 정의, U6가 구현, U2가 인터페이스에 의존 → **코드 순환 없음**.

## 비순환 검증 (코드 의존 그래프)
- `shared`는 leaf(무의존). U1/U2/U3/U4/U5는 `shared`에만 lib 의존.
- U4 → U3: 인가 결정 위임(sync, 단방향). **(#167, 2026-07-07 back-sync)** 인가 *계약*(`Principal`·`Action`·`Decision`·`AccountId`·`UserRole` + stateless `AuthorizationGuard`)은 `docsuri_shared.authz`로 이전됨 — U4/U6/U8은 이제 accounts 내부가 아니라 `shared`에만 코드 의존(위 leaf 불변식 충족). U3는 정의 소유자로 남아 `accounts.{models,guard}`에서 재노출(re-export). 가드가 stateless라 계약을 shared에 두어도 위임 의미(단일 권위 U3) 유지.
- U6 → U2/U3/U4: 게이트웨이가 핸들러 호출(런타임 호출, 단방향). U2 → U6는 **코드 의존이 아님**(U2는 `shared/ports` 인터페이스에 의존; U6가 구현) → U2↔U6 코드 순환 없음.
- U2 ↔ U4: `SearchExecuted`는 **event**(비동기) — 코드 순환 아님.
- U2 → U1: Corpus/OpenSearch 인덱스는 **공유 capability**(런타임 데이터 의존), 코드 의존 아님(U1 단일 writer, U2 단일 reader).
- **U7 → U1**: DocModel/FullText는 **공유 capability**(S3 read, 런타임 데이터 의존), 코드 의존 아님(U1 단일 writer, U7 reader). U7 → U6도 `shared/ports` 인터페이스 의존(U6 구현) → U7↔U6 코드 순환 없음(U2와 동형). U6 → U7은 게이트웨이가 핸들러 호출(런타임, 단방향).
- **U8 → U4/U3/U6**: U8은 인증/인가 경로(U3/U6)와 저장 계약(U4)을 런타임 호출한다. U4는 U8을 호출하지 않으므로 코드 순환 없음. U7→U8은 요약 출처에서 각주 트리를 여는 선택적 런타임 호출이며 U8→U7 역호출 없음.
- **U9 → U3/U6**: U9는 로그인/인가 경로(U3/U6)와 관측 포트(shared/U6 구현)에 의존한다. U2/U4/U7/U5는 U9를 호출하지만 U9가 이들을 역호출하지 않아 코드 순환 없음.
- **결론**: 코드 의존 그래프 비순환(DAG) — U7/U8/U9 추가 후에도 유지. 런타임 호출/이벤트는 단방향 또는 비동기로 순환 없음. (연구 에이전트 2유닛은 신규 인셉션 사이클에서 의존·비순환 재검증.)

## ASCII 흐름도

### 동기 디스커버리 읽기 (NFR-P1)
```text
U5 ──REST──> U6 게이트웨이 ──> U2(질의→검색→랭킹→근거화어댑터→조립) ──> 응답
                  │  (authz는 U3 위임, 근거화/비용 후크 주입)
                  └──> [응답 엣지] U6 GroundingEnforcementHook (단일 권위)
```
### 온디맨드 요약/번역 (U7, NFR-P2 — 검색 SLA 비대상)
```text
U5 ──REST──> U6 게이트웨이 ──> U7(STORE 조회→비용게이트→전문 fetch→정제→LLM→근거화→저장)
                  │  (authz는 U3 위임, 근거화/비용 후크 주입)
                  ├──> [캐시 HIT] Redis/S3 즉시 반환 (LLM 0콜)
                  ├──> [비용게이트 OPEN] 요약 일시 기권(FR-11)
                  └──> [응답 엣지] U6 GroundingEnforcementHook (근거 없으면 기권)
U7 전문 read <── 공유 capability(S3, U1 writer) ;  U7 결과 ──> S3 영구 + Redis 핫
```
### 논문 상세보기 각주 트리 (U8, NFR-P3 — 검색 SLA 비대상)
```text
U5 논문 상세보기 ──REST──> U6 게이트웨이 ──> U8(로그인 확인→snapshot 캐시→citation API→ID 해소→트리 조립)
                                   │
                                   ├──> [캐시 HIT] citation snapshot 즉시 반환
                                   ├──> [API 실패/쿼터] 캐시 우선, 없으면 "인용 정보를 불러올 수 없음"
                                   └──> [노드 저장] U4 Library 저장 계약 재사용
U8 ──관측 event──> U6(조회 수·캐시 적중·429·unresolved 비율·노드 수·지연)
```
### 개인화 이벤트와 프로필 (U9, NFR-P4 — 비차단)
```text
U2/U4/U7/U5 성공 경로 ──event/sync──> U9(이벤트 기록→프로필 집계→설정/삭제/초기화)
                                      │
                                      ├──> [프로필 있음] U2 검색 boost / U7 기본값 제안
                                      ├──> [사용자 off/delete/reset] 비개인화 기본 경로
                                      └──> [U9 실패] 기본 기능 유지 + 저하 신호(U6)
```
### 인제스천 (이벤트/스케줄)
```text
source별 스케줄/backfill/rebuild ──> U1 워커 ──> (source fetch→FullText/GROBID→DocModel→Block chunk→embed) ──> 공유 Corpus 인덱스(write)
                                                                                                             └─실패─> DLQ/재시도/경보(U6 관측)
```
### 이력·인시던트 (이벤트 백본)
```text
U2 ──SearchExecuted(event)──> U4 SearchHistory
U2/U6 ──근거화 위반/비용 급증/반쪽짜리(event)──> U6 탐지기 ──> IncidentEventPublisher ──> Ops 대시보드
```

---

## 2026-09-19 REM Dependency Model

**입력**: UGP1=A, DAD1=A 및 WPR2=A. unit 정의와 component primary는 `unit-of-work.md`, story/finding/인수 책임은 `unit-of-work-story-map.md`의 현재 절을 따른다.

**상태**: 생성·검증 및 UGR1=A 승인 완료 (2026-09-19). 승인 기록은 `../plans/unit-of-work-plan.md`다.

### 의존 종류

| Kind | 의미 |
|---|---|
| C - contract/build | schema/port/binding 및 frozen artifact 지원 version 의존. REM-1이 조정하지만 REM-1 daemon HTTP 가용성에 의존한다는 뜻은 아님 |
| M - merge/integration | 승인된 선행 merge 및 isolated integration checkpoint |
| R - runtime sync | bounded 접수, 인가/직접 control, 준비된 event/result/asset/health 요청. 업무 완료를 기다리는 RPC가 아님 |
| E - durable async | operation/outbox/worker, domain command/receipt 및 lifecycle signal. parent/version/grant에 결속 |
| D - data/projection | domain-owned current authority/context, immutable source/report/command projection 등 읽기 의존 |
| A - activation | public route/정책 집행을 켜기 위한 안전 조건. source import나 merge 선행과 별개 |

### Merge / isolated integration matrix

행 unit이 열 unit의 checkpoint를 선행 조건으로 소비한다. 표시한 전이/전이적 의존은 모두 낮은 순서에서 높은 순서로 전진한다.

| Consumer | REM-1 | REM-2 | REM-3 | REM-4 |
|---|---|---|---|---|
| REM-1 | — | — | — | — |
| REM-2 | G1 | — | — | — |
| REM-3 | G1 | REM-2 isolated integration/신규 data inventory | — | — |
| REM-4 | G1 | 선행 integration | REM-3 isolated integration | — |

순서는 **REM-1 -> REM-2 -> REM-3 -> REM-4**다. 공통 계약이 동결된 독립 구현은 병렬 조정할 수 있다. 각 unit은 자신의 Functional/NFR Requirements/NFR Design/Infrastructure/Code loop와 리뷰를 완료하고, 실제 provider를 미구현 상태로 남긴 mock 성공을 integration 완료로 인정하지 않는다.

### Contract, runtime 및 data edges

| Consumer | Provider | Kind | 계약 및 경계 |
|---|---|---|---|
| REM-2/3/4, 기존 backend/frontend | shared/domain 계약 및 REM-1 검증 artifact | C | public/server/internal DTO, registry/compatibility, offline build-consumed bindings |
| U5/U13 frontend | BFF -> U6/U3 gateway -> 고정 REM-2/3 route | R | 접수/직접 SSE/result/asset relay. browser의 REM/store 직접 접근과 임의 proxy target 금지 |
| REM-2 content workers | U1 source/build/asset 및 U7 business core | C/D/E | source current/immutable version 소비, 필요 build는 durable command/receipt |
| REM-2 private context | U11/U12 context authority 및 U1 user_docmodel | D | 기존 owner context를 검증하며 public `userdoc:` fallback 없음 |
| 모든 REM 및 기존 owner writer | U3/resource owner의 AUTH, EXEC 계약 | C/D | current grant/owner/run fence. stale event-cache 또는 gateway 역호출로 대체하지 않음 |
| REM-3 purge | U3 직접 lifecycle producer | E/D | 유예/재활성화/파기 epoch의 목적 한정 신호. 계정 비활성화/session 철회는 직접 U3 경로 |
| REM-3 purge | 각 owner domain 및 REM-2/4 EXEC | E/D | quiesce/manifest-bound purge/receipt/residue. recipient는 자기 store와 inbox만 수정 |
| Domain executor | 지정 recipient의 CommandProjection | D/E | immutable 입력 읽기, 자기 receipt 발행. sender 일반 mutable table write/임의 callback 없음 |
| REM-3 opt-out | U15 consent/settings/sender | C/D/E | 직접 suppression/공통 handoff barrier, 후속 ApplyOptOut/receipt. observer 권한과 System completion 목적 분리 |
| U5/U6/U3 ingress | REM-3의 versioned edge policy | C/D | 로컬 identity/limiter 집행. 매 request의 REM-3 API 호출 의존이 아님 |
| REM-4 audit/repair | U1 corpus read/fenced mutation | D/E/목적 한정 실행 | 읽기/검증은 worker, mutation은 exact approval/backup 증거가 있는 runner |
| U2/U5/U6 SEARCH/health | REM-4 report 및 current generation head | D | generation/model/freshness 검증 후 로컬 집행. 검색 hot path의 REM-4 RPC 없음 |
| 모든 entry/worker | U6 OBS 계약 및 자기 local instance | C/R/E | 구조화 correlation, redaction, 단계 latency, queue와 독립된 health |
| REM-1 daemon/runner | domain-owned schemas/registry/lock/evidence | C/D/목적 한정 실행 | daemon은 read-only; runner만 명시 승인 작업. bootstrap의 live daemon 순환 없음 |

### 초기 provider와 공동 activation

- REM-2의 AUTH/current projection 및 write-fence provider는 REM-2의 U3/U1 등 원 domain 변경으로 함께 제공한다. EXEC의 전체 통합 primary가 REM-3이라는 이유로 초기 provider 구현을 미루지 않는다.
- REM-2 public job 활성화는 REM-3의 lifecycle/consent/identity 보호와 G4 browser/compatibility 검증 이후다. REM-3가 REM-2 operation/event/result inventory를 소비하는 역방향 관계는 E/D/A이며 M 순서를 뒤집지 않는다.
- REM-1의 G1은 기반의 local 완료다. US-R4/5와 RJ-AC12의 service-local 구현 및 최종 integration은 후속 REM과 통합 Build and Test에서 확인한다. 전체 인수 pending을 기반 작업의 미착수 전제로 해석하지 않는다.
- 초기 schema/core envelope 이후의 domain 계약 변경은 원 owner와 REM-1 shared review를 거쳐 versioned artifact로 배포한다. 사용자 권한 의미를 공유 toolkit 코드의 임의 변경으로 바꾸지 않는다.

### Activation 및 별도 data gate

| 활성화 대상 | 필요한 증거 | 의존 종류 |
|---|---|---|
| REM-1 evidence/runner 기능 | G1, 역할별 credential/registry/compatibility, mutation의 별도 권한 | A |
| REM-2 public job 및 asset/result | G2 + REM-3 보호(G3) + 관련 browser/신구 contract 인수(G4) | A |
| REM-3 opt-out/purge | G3, U15 sender barrier 및 전체 domain EXEC/REM state inventory, 관련 G4/G5 | A/D |
| REM-4 relevance enforcement | 검증된 corpus generation/audit/calibration 및 shadow/정책 증거 | A/D |
| safe targeted live repair | 격리 검증, G5 backup/restore, exact count/hash/manifest, rollback 및 사후 불변식 | A/D |
| full rebuild/bulk reparse/reembed/live alias cutover | 별도 명시 실행 승인 | 별도 실행 gate |

### Dependency 검증 모델

1. **M graph**는 위 matrix의 순서로 비순환이다. A의 REM-2/3 공동 보호를 역방향 M edge로 합치지 않는다.
2. **Source graph**의 import 방향은 DAD1의 C3 composition -> C2 adapters/C1 domain-core/C0 contracts, C2 -> C1/C0, C1 -> C0다. 상위가 하위를 소비하고 domain이 다른 REM controller/entry point를 import하지 않는다.
3. **Sync graph**는 browser/BFF/gateway -> 고정 service -> local core/projection/I/O 방향이다. AUTH/consent adapter가 gateway를 역호출하거나 health끼리 순환 probe하지 않는다.
4. **E feedback**은 의도된 outbox/worker/publication 및 command/receipt 흐름이다. 전체 runtime 통신을 DAG라고 선언하지 않는다. parent/run fence 및 version/grant 검증으로 새로운 사용자 job/재귀 status chain이 생기지 않게 한다.
5. 공유 physical store는 cross-domain admin write를 허용하지 않는다. ordinary writer와 domain-owned privileged executor, immutable projection의 권한을 구분한다.
6. 이 모델의 검증은 설계/분해의 정합성이다. 실제 import/consumer/queue/role/version 및 failure behavior는 per-unit Construction과 G0~G5에서 입증한다.
