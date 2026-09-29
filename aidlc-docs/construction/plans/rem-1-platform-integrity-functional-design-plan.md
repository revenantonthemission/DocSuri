# REM-1 Platform Integrity — Functional Design 계획

**단계**: CONSTRUCTION -> Functional Design
**유닛**: `rem-1-platform-integrity` (REM-1)
**일자**: 2026-09-19
**상태**: 세 Functional Design 산출물 작성·검증 및 R1FDR1=A 승인 완료 (2026-09-19)
**입력 승인**: UGR1=A, UGP1=A, DAD1=A, WPR2=A, RJR1=A, RJS2=A

이 단계는 REM-1의 domain model, 업무 규칙, 판정/변환/실행 흐름과 테스트 가능한 속성을 정의한다. 저장 엔진/프레임워크/crypto 알고리즘/port/수치형 TTL·timeout은 해당 NFR/Infrastructure 단계에서 확정한다.

## 1. Unit context

- **Primary components**: R1C(read-only PlatformEvidenceController), R1R(명시적 PlatformIntegrityRunner), OBS(공통 관측 규약).
- **Primary findings**: F06 dependency/lock/pin/SBOM, F08 ordered migration registry/ledger, F13 offline fail-closed build-consumed bindings.
- **Primary story/인수 조정**: US-R4, US-R5, RJ-AC12. REM-1은 G1 local 기반과 공통 증거/관측 규약을 제공하고, 후속 REM의 실제 failure/health/복구 인수는 G4/G5에서 통합한다.
- **Authority**: 기존 domain/shared owner가 schema/migration/business 의미를 소유한다. REM-1은 검증, 실행 조정 및 evidence를 소유한다.
- **Local 선행성**: 아래 platform Run/evidence 모델은 REM-1의 runner 상태다. REM-2/3/4의 public-job RK runtime이 먼저 구현돼야 G1을 완료할 수 있는 의존을 만들지 않는다.
- **주요 산출물 위치**: `aidlc-docs/construction/rem-1-platform-integrity/functional-design/`.
- **Frontend 적용성**: N/A. 이 unit의 frontend 변경은 contract/binding tooling이며 새 화면/상호작용 설계를 포함하지 않는다. 운영 evidence의 typed 출력은 정의하되 새로운 대시보드 UI를 추가하지 않는다.

## 2. 현재 코드 및 검증 근거

코드 관찰은 아래 파일의 현재 동작/구조를 읽어 확인한 것이다. 2026-09-18 보고서의 실제 실행 결과와 구분한다.

| Seam | 관찰 근거 | Functional Design에서 해결할 문제 |
|---|---|---|
| Migration ledger | `backend/migrations/__init__.py:20-25,52-68` — name/applied_at 기반, identity는 script basename이며 content digest가 없음 | canonical identity, legacy 기록의 보장 수준, 변경/충돌/미확인 이력 판정 |
| Migration check | 같은 파일 `74-84` — pending 조회도 tracking DDL과 commit 수행 | check/readiness/evidence 조회가 target을 변경하지 않는 관측 계약 |
| Migration entry points | `backend/app.py:127-163`, `backend/migrations/__main__.py:14-35` — 서로 다른 path 목록, startup mutation 및 CLI의 기본 apply | 단일 registry/scope, 명시적 실행, 상태/인수의 동치 |
| F08 reproduction | `project-verification-2026-09-18.md` F08 — 격리 fresh DB의 evidence/glossary 누락, CLI/startup 목록 차이 | 완전성 검증 및 fresh/restore target의 실제 요청 성공 조건 |
| Frontend bindings | `frontend/scripts/gen-types.mjs:18-50` — 5개 schema subset, drift용 출력과 실제 curated type 분리, 실패 skip 후 성공 exit 가능 | ConsumerManifest, offline ref closure, build-consumed 계약 및 실패 전파 |
| Python bindings | `shared/python/tools/generate.py:42-57,98-116,141-158` — staging/check는 있으나 publication은 기존 tree 삭제 후 copy | 검증된 candidate와 논리적 activation, publish 중단/불확정 효과 처리 |
| Local schema reference precedent | `shared/python/tests/test_schema_validity.py:25-65` — local ID registry와 cross-file validation/negative fixture | absolute ID를 로컬로 해소하는 registry 및 public/internal projection 속성 |
| Supply-chain CI | `.github/workflows/ci.yml:185-236` — PR 신규 dependency review, pyproject 재해석 후 Python audit | 실제 frozen production artifact/closure와 evidence의 결속, 누락/실패 판정 |
| Type guard CI | `.github/workflows/ci.yml:152-174` — generator + types diff, 실제 frontend build 별도 | exit code만으로 성공을 추정하지 않는 전체 target/consumer 검증 |
| F06/F13 observed findings | `project-verification-2026-09-18.md` F06/F13 | 기존 audit 결과는 당시 증거다. 새 artifact의 현재 적격성을 별도 검증하고 예외를 정확히 매칭해야 함 |

`ingestion/migrations/postgres/*.sql`은 registry scope 검토 대상이다. 반면 `ingestion/src/docsuri_ingestion/migrate.py`의 corpus reembed/cutover는 REM-4 및 별도 실행 gate에 속한다. 이름에 migration이 포함된 모든 도구를 REM-1 apply 목록으로 자동 편입하지 않는다.

## 3. 계승할 고정 제약

1. REM-1 daemon은 read-only evidence/compatibility를 제공한다. target migration/apply/promotion은 명시적인 runner action과 유효한 목적·target·plan-bound 권한이 있어야 한다. 인자/권한이 없을 때 mutation을 기본 실행하지 않는다.
2. check/plan/readiness는 target ledger/schema 및 published artifact를 변경하지 않는다. ledger 부재는 Uninitialized 같은 관측 결과다. 격리 candidate 계산과 명시적으로 허가된 evidence 산출은 target mutation과 구분한다.
3. migration registry는 명시적 identity/owner/path/order/dependency/scope를 갖고, startup/CLI는 같은 registry와 검증 규칙을 소비한다. 자동 discovery는 누락/중복 검사에 사용하며 실행 순서의 별도 권위가 아니다.
4. legacy 이름/시각은 원 이력으로 보존한다. 과거 digest가 없는데 현재 파일 digest를 과거 실행 증거로 꾸미지 않는다. 변경된 동일 identity와 모호한 legacy mapping은 자동 재실행/skip으로 처리하지 않는다.
5. 모든 local schema ID/ref를 network 없이 해소하고 duplicate ID, unresolved ref, target 누락을 실패로 보고한다. 지원되는 recursive ref는 유한한 registry resolution으로 다루며 미지원 변환을 skip 성공으로 처리하지 않는다.
6. public browser, server-only BFF, internal worker 계약을 분리한다. ClientJobSpec이 internal intent/grant/locator 타입으로 확대되지 않아야 한다.
7. candidate는 모든 선언된 target 검증 이후에만 publish한다. 실패/중단 중 authoritative consumer가 mixed/부분 bundle을 정상본으로 소비해서는 안 된다. check는 committed/build-consumed contract의 drift를 검출한다.
8. F06의 known critical/high는 수정하거나, 승인된 source-unreachable 근거와 만료를 가진 예외로만 처리한다. scanner 실패/미실행/누락은 clean이 아니다. 예외를 적용해도 원 finding과 승인 근거를 evidence에서 제거하지 않는다.
9. evidence는 artifact/target/정책/검사 범위에 결속된다. R1C 가용성 자체가 build/bootstrap 또는 사용자 요청의 실시간 선결조건이 아니며 검증된 local evidence도 같은 판정 규칙을 따른다.
10. 실제 효과가 불명확한 run은 성공이나 미실행으로 단정하지 않는다. 명시적 재조정 없이 destructive effect를 반복하지 않는다. daemon restart가 privileged mutation을 자동 재개하지 않는다.
11. 기존 single-Mac 예외, domain authority 및 WPR2 G0~G5를 계승한다. REM-1 local 완료와 최종 전체 service 인수는 구분한다.

## 4. 질문 범주 평가

| 범주 | 적용 및 결정 질문 |
|---|---|
| Business Logic Modeling | registry 검증/적용, binding 생성/검증/publish, evidence 집계 및 중단 재조정 — R1FD1/2/3/4/6 |
| Domain Model | MigrationIdentity/LegacyObservation, ConsumerManifest, Attestation/Run/Approval 관계 — R1FD1/3/4/6 |
| Business Rules | legacy 채택, atomicity, 실제 consumer 권위, 예외의 허용 범위 — R1FD1/2/3/5 |
| Data Flow | raw 입력 -> 검증 snapshot -> candidate -> evidence/publication 및 current 판정 — R1FD3/4/6 |
| Integration Points | domain owner registry, Python/TS consumer, CI/artifact/daemon/runner의 동일 판정 — R1FD1/3/4/5 |
| Error Handling | dirty/missing/unknown ledger, 생성 실패, 부분 적용/효과 불명확, scanner 누락 — R1FD1/2/4/6 |
| Business Scenarios | 재시도/동시 run, 이미 실행된 step, artifact 변경 후 예외, approval 만료 — R1FD1/2/5/6 |
| Frontend Components | N/A. type tooling/evidence 계약이 범위이며 새 UI 기능은 없음. `frontend-components.md`는 생성하지 않음 |

## 5. 후보 domain model 및 흐름

아래는 답변을 구체화할 모델 후보이며 상세 엔티티/전이는 답변 검증 후 확정한다.

- **Target/Artifact/Policy snapshot**: 검사·실행 대상과 required gate 집합, fingerprint/revision을 식별한다.
- **MigrationSpec/RegistrySnapshot/LedgerObservation/LegacyReconciliation**: 명시 identity/order, 관측된 이력과 증거 수준, apply 가능 여부를 구분한다.
- **SchemaCatalog/ConsumerManifest/BindingCandidate/ActivationReceipt**: 로컬 ref closure, 실제 소비 target와 공개 범위, 전체 검증 및 마지막 publication을 연결한다.
- **DependencyInventory/AdvisoryObservation/ReachabilityException**: frozen 대상의 finding과 exact 예외/만료/승인 결속을 보존한다.
- **RunIntent/Attempt/EffectCheckpoint/ApprovalBinding**: 의도와 실행 시도, 실제 effect 확인, 중단 후 재조정 및 목적별 권한을 분리한다.
- **VerificationAttestation/GateEvaluation/SafeObservation**: immutable 증거와 현재 적격성/결손/오류 판정, daemon/readiness/CLI용 안전한 출력을 분리한다.

기본 흐름은 `입력 snapshot -> plan/validation -> 명시적 권한 확인 -> 실행/검사 -> candidate/effect 검증 -> evidence/publication -> gate 판정`이다. 단순 read/check는 mutation 단계로 진입하지 않는다.

## 6. 결정 질문

### R1FD1 - Legacy migration 이력의 채택 규칙

현재 ledger는 basename과 적용 시각만 가진다. 새 명시 registry의 stable identity 및 content fingerprint에 기존 이력을 어떻게 연결할까?

A) **증거 기반 자동 매핑 + 불명확 항목의 명시적 reconciliation**. 원 ledger 행은 보존한다. unique mapping과 신뢰 가능한 당시 artifact/실행 증거가 모두 있는 경우에만 verified 적용 이력으로 연결한다. digest/실행 증거가 없으면 candidate로만 제시하고, target 관측·domain 확인·승인에 결속한 별도 adoption record를 만든다. adoption을 과거 checksum 검증과 구분하며 이름만으로 skip/reapply하지 않는다. (권장)

B) 기존 ledger의 모든 행을 명시적 reconciliation manifest로 검토·승인한 뒤 새 identity에 연결한다. 자동화는 후보/충돌/관측 정보만 제공하고 증거가 충분한 unique 항목도 자동 채택하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 historical evidence/adoption 구분과 ambiguous mapping 처리 규칙을 기술)

[Answer]: A

### R1FD2 - Migration 실패 시 원자성 및 재개 단위

검증된 ordered plan의 일부 step이 실패하면 어떤 단위로 적용 결과를 유지할까?

A) **step별 원자 적용/ledger checkpoint**. 전체 plan을 먼저 검증하고 target별 실행을 직렬화한다. 각 step의 효과와 ledger를 함께 확정하며 첫 실패에서 멈춘다. 앞선 verified step은 유지하고 같은 plan 재개 시 검증된 미완료 step부터 진행한다. 되돌릴 수 없는/비원자 작업은 명시적으로 분리하고 별도 보상/복구 계획을 요구한다. (권장)

B) 하나의 plan을 all-or-nothing 단위로 적용한다. 포함된 모든 step이 그 원자성 조건을 충족할 때만 실행하며 실패 시 전체를 되돌린다. 조건을 충족하지 않는 step은 plan에서 분리해 별도 승인된 실행 단위로 다룬다.

X) 기타 (아래 `[Answer]:` 뒤에 실패/이미 적용된 step/비원자 effect의 처리 단위를 기술)

[Answer]: A

### R1FD3 - 실제 소비되는 wire contract의 표현 방식

현재 TypeScript raw 생성물과 실제 curated types가 분리돼 있다. 새 guard가 실제 consumer를 검증하도록 어떤 방식을 사용할까?

A) **wire contract는 schema에서 생성하고 view model은 명시적 adapter로 분리한다.** public/server/internal ConsumerManifest를 두고 실제 wire import가 검증된 생성물을 사용하게 한다. 사람이 작성하는 UI/domain view model은 별도 변환 계약과 positive/negative fixture로 검증한다. 누락 target이나 생성 실패는 전체 run 실패다. (권장)

B) TypeScript wire type의 curated 표현을 유지하되 authoritative schema와의 양방향 conformance 및 positive/negative fixture를 실제 build 소비 지점에 강제한다. Python 생성 및 모든 local ref/target 검증은 유지하며 drift용 dump만으로 합격하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 authoritative schema와 실제 public/server/internal consumer의 동치 검증 방법을 기술)

[Answer]: A

### R1FD4 - Evidence와 gate 판정의 구성 단위

registry, bindings, supply-chain 결과를 R1C/CLI/startup/배포가 같은 의미로 소비하도록 evidence를 어떻게 묶을까?

A) **subject/gate별 immutable attestation + scope별 derived evaluation**. artifact/target/policy에 결속된 증거를 개별 보존하고 required gate 집합으로 현재 판정을 계산한다. 위반, 누락, stale/불일치는 각각 근거를 남기고 성공으로 합치지 않는다. REM-1 local G1 scope와 전체 release scope를 분리한다. (권장)

B) 요청 scope마다 모든 required gate 결과를 하나의 immutable evaluation bundle로 발행한다. 부분 gate 결과는 진단용이고 authoritative 판정은 완전한 bundle에만 둔다. local G1과 전체 release는 서로 다른 scope/bundle이며 변경 시 새 bundle을 발행한다.

X) 기타 (아래 `[Answer]:` 뒤에 subject/version binding, 결손/실패/stale 판정 및 local/통합 scope 구분을 기술)

[Answer]: A

### R1FD5 - Source-unreachable advisory 예외의 범위

이미 허용된 근거·만료·승인 요건을 유지하면서 예외를 어떤 대상 집합에 결속할까?

A) **한 exact artifact/dependency closure별 예외**. advisory와 도달성 근거, 해당 artifact/정책/만료/승인을 결속한다. 관련 artifact나 closure가 바뀌면 재검토하며 묵시적 재사용/자동 갱신은 없다. 원 finding과 예외 적용 사실을 모두 보고한다. (권장)

B) 하나의 예외가 명시적으로 열거된 유한한 artifact/closure 집합을 포함할 수 있다. 각 구성원의 도달성 근거와 정확한 fingerprint를 승인 record에 포함하고, 새 artifact 자동 편입이나 범위 밖 재사용은 허용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 승인된 source-unreachable 조건을 유지하는 scope/변경/만료 규칙을 기술)

[Answer]: A

### R1FD6 - 중단된 runner의 identity와 재조정

runner가 effect/결과 기록 사이에 중단되거나 같은 요청을 다시 받으면 어떻게 추적하고 재개할까?

A) **stable RunIntent 아래 attempt/checkpoint를 누적한다.** action/target/plan/artifact 의미가 같은 재요청은 같은 logical run을 조회·재조정한다. 실제 ledger/output/evidence로 effect를 확인하기 전 mutation을 반복하지 않는다. 의미가 바뀌면 새 intent이고, 같은 intent 재개도 유효한 현재 권한/승인 범위를 확인한다. 만료된 승인은 자동 연장하지 않는다. (권장)

B) 명시적 runner 재호출마다 별도 immutable attempt/run record를 만들고 이전 시도를 parent로 연결한다. 실행 전 공통 effect ledger/target evidence로 중복을 막고, 이전 효과가 불명확하면 새 실행을 보류한다. 각 재호출은 현재 유효한 권한을 요구한다.

X) 기타 (아래 `[Answer]:` 뒤에 retry identity, effect 불확정, 동시 실행 및 승인 만료의 규칙을 기술)

[Answer]: A

두 선택 모두 daemon restart가 privileged 작업을 자동 실행하는 의미는 아니다. publication 도중 old output 제거/일부 copy처럼 효과가 불확정한 상태도 같은 재조정 원칙에 포함한다.

## 7. Testable Properties 분석 계획 (PBT-01)

Functional Design 산출물에는 다음 후보를 실제 entity/규칙/flow에 연결한 **Testable Properties** 절을 포함한다. 이 표는 property 식별의 출발점이며 테스트 구현은 Code Generation에서 수행한다.

| 후보 | Category | 확인할 성질 / 입력 영역 | Trace |
|---|---|---|---|
| Registry identity/order | Invariant, Oracle | stable identity 유일성, declared dependency/order의 결정성, missing/duplicate/changed-content 거부; domain/path/ledger 조합 | F08, R1FD1/2 |
| Legacy evidence assurance | Invariant | name-only 이력이 verified checksum 증거로 승격되지 않음; ambiguous candidate는 mutation/skip 근거가 되지 않음 | F08, R1FD1 |
| Apply/retry equivalence | Idempotence, Stateful | verified step 재실행의 무효과, 실패/재시작/동시 요청의 ledger-effect 일치와 안전한 resume | F08, R1FD2/6 |
| Offline catalog/ref closure | Round-trip, Oracle | Catalog/ConsumerManifest serialize-parse 보존; local ID/fragment resolver의 reference-model 동치, recursive ref의 유한 처리, 원격 lookup/누락 target의 실패 | F13, R1FD3 |
| Public contract boundary | Invariant | public consumer에 internal intent/grant/locator가 새지 않음, 실제 소비 wire/view 변환 동치 | F13, R1FD3 |
| Candidate publication | Stateful, Invariant | 생성/검증/publish 실패 시 authoritative consumer에 mixed bundle을 노출하지 않음; check의 target 비변경 | F13, R1FD3/6 |
| Evidence evaluation | Oracle, Invariant | 같은 subject/policy/required-gate/명시적 평가 시각에 같은 판정; missing/failed/stale가 pass로 합쳐지지 않음 | F06/F08/F13, R1FD4 |
| Exception matching | Invariant, Boundary | exact scope/근거/expiry가 모두 충족될 때만 적용; 새로운 artifact/만료/철회에 대한 비확대 | F06, R1FD5 |
| Runner reconciliation | Stateful, Idempotence | lost receipt/unknown effect/권한 만료/재시도가 중복 mutation이나 묵시적 승격을 만들지 않음 | R1FD6, US-R4/5, RJ-AC12 |

Entity serialize/parse, canonical identity 및 evidence reference에는 round-trip 후보를 추가한다. 관측 시각/외부 scanner 결과처럼 변하는 입력은 명시적인 모델 입력으로 다룬다. 순수 규칙과 external I/O glue를 구분하고 속성 미적용 부분에는 이유와 example/integration 검증을 기록한다.

## 8. 실행 체크리스트

- [x] UGR1 승인과 REM-1 scope/component/story/finding을 확인했다.
- [x] migration entry/ledger, Python/TS generation 및 CI/advisory 근거를 대조했다.
- [x] 8개 질문 범주를 평가하고 frontend artifact N/A 근거를 기록했다.
- [x] R1FD1~6 질문 및 PBT-01 후보/추적성을 작성했다.
- [x] 질문 6개/빈 답변 6개/기타 선택지 6개, 8개 범주 및 scope/근거를 검증했다. Prettier debug-check와 tracked/new-file whitespace 검사가 통과했다.
- [x] 모든 답변을 수집하고 미정/혼합/모순을 분석했다. R1FD1~6은 모두 A이며 DAD1/UGR1의 경계 및 서로의 정책과 정합적이다.
- [x] `domain-entities.md`에 공통 value, E-R1-01~24 entity/관계, migration assurance, run/attempt 및 activation/gate 상태를 작성했다.
- [x] `business-logic-model.md`에 FL-R1-01~08의 readonly 관측/registry, legacy assurance, step apply, bindings, advisory/예외, gate 평가, effect 재조정 및 관측 알고리즘을 작성했다.
- [x] `business-rules.md`에 BR-R1-01~22, 오류/중지 의미, 결정/인수 추적성과 확장 적용 근거를 작성했다.
- [x] **Testable Properties** PROP-R1-01~16을 category/input/oracle/counterexample 및 component/규칙/trace에 연결하고 transport-only glue의 적용성을 구분했다.
- [x] Security/Resiliency/PBT의 40개 규칙을 현 단계에 맞게 검토하고 local G1/후속 통합 gate 정합성을 검증했다. 적용 규칙의 미해결 blocking finding 없음.
- [x] 생성한 3개 산출물, plan/state/audit와 R1FDR1 완료 리뷰를 준비했다. Markdown parsing, ID/참조/추적성 및 tracked/new-file whitespace 검사가 통과했다.
- [x] 사용자 `R1FDR1: A` 승인으로 Functional Design을 완료하고 **REM-1 NFR Requirements**를 시작했다 (2026-09-19).

## 답변 방법

R1FD1~R1FD6 및 산출물 승인 R1FDR1은 모두 A로 확정됐다. 이후 결정 질문은 REM-1 NFR Requirements 계획에서 다룬다.

## 답변 분석 - 2026-09-19

- 사용자 원문: `Use A for R1FD1–R1FD6`.
- R1FD1=A: 증거가 충분한 unique legacy mapping만 verified로 연결하고, 나머지는 명시적 adoption/reconciliation으로 구분한다.
- R1FD2=A: 전체 plan 사전 검증 + target별 직렬 실행 + step별 effect/ledger 원자 checkpoint 및 첫 실패 중지다.
- R1FD3=A: 실제 wire type은 schema에서 생성하고 수작업 view model은 검증된 adapter로 분리한다.
- R1FD4=A: subject/gate별 immutable attestation을 보존하고 current scope/required gates에 따라 판정을 계산한다.
- R1FD5=A: source-unreachable 예외는 단일 exact artifact/closure/근거/정책/만료/승인에 결속한다.
- R1FD6=A: stable RunIntent에 attempt/checkpoint를 누적하고 효과를 재조정한 뒤 유효한 권한으로만 명시 재개한다.
- 여섯 답변은 single-writer/명시 실행, read-only check, atomic publication, local G1/전체 release 구분과 충돌하지 않는다. 추가 명확화가 필요한 혼합/미정 답변은 없다.

## 9. Functional Design 검증 및 완료 리뷰 - 2026-09-19

| 산출물 | 검증된 내용 |
|---|---|
| `../rem-1-platform-integrity/functional-design/domain-entities.md` | E-R1-01~24, 공통 identity/CompatibilityManifest/ExecutionScope, assurance/run/effect/activation/evidence 상태 |
| `../rem-1-platform-integrity/functional-design/business-logic-model.md` | FL-R1-01~08, 15개 기능/실패 시나리오, DAD1 port와 상세 모델 연결 |
| `../rem-1-platform-integrity/functional-design/business-rules.md` | BR-R1-01~22, PROP-R1-01~16, 여섯 정책 결정/F06/F08/F13/US-R4/5/RJ-AC12 추적성 및 40개 확장 규칙 적용표 |

### 정합성 검토 및 보정

- `PREPARED`라는 미정의 assurance 대신 NOT_STARTED/UNKNOWN/COMMITTED/NO_EFFECT_CONFIRMED의 명시적 전이를 사용한다. effect를 열기 전 durable UNKNOWN, 실제 증거 기반 재조정 및 append-only checkpoint를 정합화했다.
- legacy check의 후보/assurance 계산과 별도 승인 adoption 저장을 분리했다. 현재 capability와 과거 step 직후 postcondition을 혼동해 이미 대체된 구조를 복원하지 않도록 했다.
- CompatibilityManifest의 artifact/schema/operation/writer epoch 및 registry/consumer/binding/capability 검증을 R1C/CLI/startup의 같은 판정에 연결했다.
- authoritative 재검사의 PENDING/RESOLVED revision과 immutable 결과를 결속했다. 실패/중단 또는 이전 attempt의 늦은 PASS가 과거 성공을 current로 유지/복구하지 못한다.
- bounded 입력/I/O, 비변경 health, 현재 권한, 민감정보 비노출, 추가 전용 감사와 phase/종단 관측을 US-R4/5 및 기존 DAD1/보안/복원력 요구와 대조했다.
- R1FD1~6=A의 뜻과 UGR1의 세 component/세 finding 배치를 유지한다. REM-1 local G1과 후속 service의 실제 통합 인수는 별도이며 공개 job RK 선행 구현 의존을 만들지 않는다.

### 검증 결과

- E/FL/BR/PROP 정의는 각각 **24/8/22/16개**이며 ID가 유일하고 연속이다. 세 문서의 축약/range 포함 참조가 모두 정의된 ID로 해소된다.
- 여섯 결정, F06/F08/F13, US-R4/US-R5, RJ-AC12 추적성 11행과 승인된 단위/port/요구사항의 연결을 검토했다.
- 세 설계 산출물/plan/audit의 Markdown은 Prettier `--debug-check`로 parsing/재출력 정합성을 확인했다. 이 단계는 텍스트/표로 표현해 별도 Mermaid/ASCII diagram이 없다.
- `aidlc-state.md` 전체 debug-check는 기존 2026-06-24 FR-27 항목에서 `prettier(input) !== prettier(prettier(input))`로 실패했다. `git show HEAD:aidlc-docs/aidlc-state.md`도 동일하게 실패해 기존 formatter 재출력 문제임을 확인했다. 이번 state 추가 내용은 diff에서 추출해 stdin으로 같은 debug-check를 실행했고 통과했다. 새 Functional Design 내용의 미해결 검증 실패는 없다.
- tracked state/audit는 `git diff --check`, 새 문서/plan은 개별 `git diff --no-index --check -- /dev/null <file>`로 whitespace를 확인했다.
- 이는 설계 산출물 검증이다. PROP-R1 테스트 구현과 실제 target/consumer/scanner/장애 인수는 Code/Build 단계로 추적한다.

### 확장 준수 요약

per-rule 근거와 N/A 사유는 `business-rules.md` §6에 있다.

- **Security**: SECURITY-03/05/06/08~15 기능 설계 수준 Compliant(11개). SECURITY-01/02/07은 physical 설정 단계 N/A, SECURITY-04는 새 HTML/UI 없음으로 N/A(4개).
- **Resiliency**: RESILIENCY-01/03~07/10/13~15 Compliant(10개), RESILIENCY-09는 승인된 bounded-capacity replacement Compliant. RESILIENCY-02/11/12는 수치/물리 DR·backup 설계/실행 단계 N/A, RESILIENCY-08은 승인된 single-Mac 예외(총 N/A 4개).
- **PBT**: PBT-01 Compliant(16개 속성 및 component별 category/input/oracle/counterexample). PBT-02~10은 상세 규칙의 Functional Design 적용표상 N/A이며 후속 Full 요구를 유지한다.

### R1FDR1 - Functional Design 산출물 승인

위 세 산출물과 R1FD1~6의 반영, 기능/실패 규칙 및 Testable Properties를 승인하고 **REM-1 NFR Requirements**로 진행할까?

A) **Continue to Next Stage** — Functional Design을 승인하고 REM-1 NFR Requirements로 진행한다.

B) **Request Changes** — 수정할 entity/flow/rule/property 또는 추적성 내용을 지정한다.

X) 기타 (아래 `[Answer]:` 뒤에 리뷰 의견을 기술)

[Answer]: A

**승인 기록**: 사용자 원문 `R1FDR1: A`, 2026-09-19T14:57:39Z. 세 Functional Design 산출물을 승인하고 REM-1 NFR Requirements의 입력 분석/계획을 시작한다.
