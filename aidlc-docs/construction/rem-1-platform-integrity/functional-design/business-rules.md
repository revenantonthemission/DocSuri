# REM-1 — Business Rules and Testable Properties

**단계**: CONSTRUCTION / Functional Design
**상태**: 작성·검증 및 R1FDR1=A 승인 완료 (2026-09-19; `../../plans/rem-1-platform-integrity-functional-design-plan.md`).
**결정**: R1FD1~R1FD6=A. `domain-entities.md`의 E-R1-01~24 및 `business-logic-model.md`의 FL-R1-01~08과 함께 읽는다.

## 1. 규칙의 적용 범위

규칙은 REM-1의 migration/contract/supply-chain/evidence 의미를 정한다. 다른 domain의 업무 의미를 재정의하지 않는다. local G1, 후속 service-local 구현 및 전체 release의 G2~G5는 별도 scope다. 실제 framework, storage, crypto, TTL/timeout 값과 deployment wiring은 후속 설계에서 정한다.

## 2. Business Rules

| ID | 규칙 | 필수 판정 / 금지된 동작 | Flow / trace |
|---|---|---|---|
| BR-R1-01 | 명시적 authority와 read-only 경계 | daemon/check/plan/health는 target ledger/schema/published output을 바꾸지 않는다. action/권한이 없을 때 apply를 기본 선택하지 않는다. candidate 계산/report 출력과 target mutation은 다른 capability다. | FL-R1-01/08; DSRQ7, F08 |
| BR-R1-02 | Identity와 fingerprint 분리 | target incarnation, artifact digest, stable migration ID와 관측 state를 분리한다. source bytes의 exact digest와 canonical metadata fingerprint를 혼동하지 않는다. 현재 digest를 과거 실행 값으로 소급하지 않는다. | FL-R1-01/02; R1FD1 |
| BR-R1-03 | Registry 완전성/결정성 | ID/path/order/dependency/target 및 required capability coverage를 먼저 검증한다. 발견된 파일을 자동 실행하지 않고 unregistered/missing/cycle/order conflict를 blocker로 둔다. 동일 scope의 startup/CLI는 같은 registry와 CompatibilityManifest 지원 조합을 검증하며 필수 module을 silent skip하지 않는다. | FL-R1-01/06/08; F08 |
| BR-R1-04 | Ledger 관측의 진실성 | ABSENT/UNAVAILABLE/AVAILABLE/INCONSISTENT를 구분한다. missing ledger가 fresh target임을 증명하지 않으며, read/check가 tracking DDL을 실행하지 않는다. | FL-R1-01; F08 |
| BR-R1-05 | Legacy assurance 보존 | unique mapping과 당시 content/committed execution 증거가 모두 있어야 VERIFIED_EXECUTION이다. 그 외 adoption은 current target/domain/승인에 결속한 별도 보장 수준이다. 원 legacy 행과 불확실성을 보존하고 changed definition을 덮어쓰지 않는다. | FL-R1-02; R1FD1, F08 |
| BR-R1-06 | Frozen plan과 precondition | ExecutionPlan의 action/target/input/policy/order/recovery 의미를 digest로 동결한다. live mutation의 격리 검증·exact dry-run·backup/restore·rollback·사후 인수 증거를 결속하고 각 effect 경계에서 현재 상태를 대조한다. 설명되지 않는 drift를 계속 실행하지 않는다. | FL-R1-01/03; R1FD2/6 |
| BR-R1-07 | Step별 atomicity | ATOMIC_STEP은 효과와 canonical ledger를 같은 원자 단위로 commit한다. 첫 실패에서 중지하고 앞선 verified effect를 유지한다. 비원자/불가역 작업은 별도 실행/복구 계획 없이 이 loop에 포함하지 않는다. | FL-R1-03; R1FD2 |
| BR-R1-08 | Target별 직렬화/fencing | 한 target mutation scope에 유효한 holder만 commit할 수 있다. lease expiry/프로세스 부재만으로 기존 I/O 종료를 추정하지 않는다. stale holder 차단/실행 종료를 증명할 수 없으면 새 mutation을 보류한다. | FL-R1-03/07; F08, RJ-AC12 |
| BR-R1-09 | Matching satisfaction만 skip | 같은 target/identity/content의 유효한 VERIFIED 또는 허용된 ADOPTED proof만 효과 만족으로 사용한다. prerequisite/postcondition의 current 판정을 함께 확인하며 이름만 같은 이력으로 skip/reapply하지 않는다. | FL-R1-01/03; F08 |
| BR-R1-10 | Stable RunIntent | action/target/plan/artifact/policy/scope 의미가 같으면 같은 logical intent다. attempt/시각/승인 갱신은 별도 이력이다. 동일 submission key의 의미 변경은 conflict며 기존 성공/실패 이력을 새 의도로 다시 쓰지 않는다. | FL-R1-03/07; R1FD6 |
| BR-R1-11 | Unknown effect의 보수적 재조정 | effect 가능성을 열기 전 UNKNOWN checkpoint를 durable 기록한다. 실제 commit/no-effect/activation 증거 전에는 반복/성공/rollback을 단정하지 않는다. process exit 0, timeout, ledger row 부재, 파일 일부 존재는 단독 effect 증거가 아니며 재조정 자료를 cleanup으로 지우지 않는다. | FL-R1-03/04/07; R1FD6, RJ-AC12 |
| BR-R1-12 | 현재 승인 범위/expiry | 목적/target/incarnation/plan/artifact/policy와 유효 구간/철회를 확인한다. `now == validUntil`은 유효하지 않다. 이미 발생한 사실의 관측/기록과 새 mutation을 구분하며 자동 승인 연장/범위 확장은 없다. | FL-R1-02/03/07; SECURITY-06/08/12 |
| BR-R1-13 | Offline schema closure | 모든 선언 root/resource/fragment를 local registry에서 해소한다. duplicate ID, escape, unresolved/unsupported는 실패다. supported recursion은 visited closure로 유한하게 다루고 원격 fetch/skip-success fallback은 없다. | FL-R1-04; F13 |
| BR-R1-14 | 실제 consumer와 공개 범위 | wire type은 schema-generated target을 실제로 소비한다. view model은 명시 adapter/fixture로 검증한다. public/server/internal export closure를 분리하고 누락 consumer 또는 internal intent/grant/locator 노출을 blocker로 둔다. | FL-R1-04; R1FD3, F13 |
| BR-R1-15 | Candidate 전체 검증/재현성 | exact catalog/manifest/toolchain/template/profile이 같으면 output 집합/내용이 같다. 모든 선언 target의 parse/type/fixture/coverage가 완료돼야 VALIDATED다. 한 target 실패를 warning/exit-success로 숨기지 않는다. | FL-R1-04; F13 |
| BR-R1-16 | Atomic authoritative publication | consumer가 한 complete generation을 관측하도록 expected head와 fence를 검사해 activation한다. old tree 제거 후 partial copy를 정상본으로 노출하지 않는다. unmanaged 기존 tree는 자동 known-good이 아니며 check는 publish하지 않는다. | FL-R1-04/07; F13 |
| BR-R1-17 | Frozen inventory와 실제 검사 범위 | exact production artifact/closure/runtime/image/CI toolchain의 coverage·verified source·사용 근거·지원 상태를 확인한다. unlocked resolution, mutable pin, unvetted/확인된 불필요·abandoned dependency 또는 필수 scanner 누락/오류를 clean으로 보지 않는다. | FL-R1-05; F06 |
| BR-R1-18 | Finding 정규화의 무손실성 | trusted ID/alias/component binding으로 중복만 정규화하고 원 결과/영향 범위를 유지한다. severity 모순/unknown을 임의 낮추지 않으며 빈 finding 배열만으로 완료된 검사를 추정하지 않는다. | FL-R1-05; F06 |
| BR-R1-19 | Exact unreachable 예외 | 단일 exact artifact/closure/advisory/occurrence, 도달성 가정/정책/승인/expiry/revocation이 모두 맞아야 적용한다. 신규 artifact 자동 편입, wildcard ignore, 묵시적 재사용/갱신은 없다. finding을 삭제하지 않는다. | FL-R1-05; R1FD5, F06 |
| BR-R1-20 | Immutable fact와 current evaluation | attestation은 immutable이고 current eligibility는 trusted required slots/head/current facts/시각에 의해 파생된다. authoritative 재검사의 PENDING/실패/불능과 revision을 보존한다. 과거 PASS 또는 늦은 이전 attempt로 현재 결손/실패/stale를 덮지 않는다. | FL-R1-06; R1FD4 |
| BR-R1-21 | 관측/오류의 분리와 최소 노출 | liveness/실제 dependency readiness/subject gate 및 접수·대기·실행·전달·종단 시간을 분리한다. timestamp/level/correlation과 안전한 이유만 출력하며 민감정보/PII를 제외한다. critical 감사는 추가 전용으로 보호하고 기록 불능은 새 mutation을 막는다. 일반 telemetry 실패는 별도 signal이다. | FL-R1-08; US-R4/5, SECURITY-03/14/15 |
| BR-R1-22 | Local/통합 범위와 downstream 책임 | REM-1 local G1을 전체 release PASS로 확대하지 않는다. 후속 REM evidence가 필요한 scope는 미완료로 남긴다. core Run 모델이 REM-2 public-job RK 선행을 요구하지 않으며 실제 I/O/복구/소비 인수는 후속 gate로 추적한다. | FL-R1-06/08; WPR2, RJ-AC12 |

## 3. 오류 및 중지 의미

| 분류 | 대표 사유 | Target effect / 외부 판정 |
|---|---|---|
| ValidationRejected | 잘못된 scope/ID, registry coverage/order, unsupported schema/target | 새 effect 없음; BLOCKED 및 일반화된 이유 |
| ObservationUnavailable | target/evidence/current head/clock 미확인 | 부재/clean으로 변환하지 않음; INCOMPLETE/UNKNOWN |
| ReconciliationRequired | legacy ambiguity, history conflict, 불명확 이전 effect | 자동 skip/retry/apply 없음; operator/domain 검토 가능한 증거 제공 |
| AuthorizationRejected | 목적/target/plan mismatch, 만료/철회, trusted actor 부재 | 새 effect 없음; 현재 유효한 scope로만 새 명시 시도 가능 |
| ExecutionFailedKnown | 현재 step rollback/no-effect 또는 검증된 부분 완료 | 이미 검증된 step 보존; PAUSED와 실패 시점/잔여 범위 |
| EffectUnknown | commit/activation 응답 유실, mixed head, old holder 불명확 | RECONCILE_REQUIRED; 성공/rollback/안전한 재시도를 추정하지 않음 |
| EvidenceStale | subject/incarnation/policy/validity 변경 | history는 보존하고 current eligible=false |
| SupplyChainBlocked | 미수정/예외 미충족 known critical/high | 원 finding + 적용 불가 이유 보존; BLOCKED |

같은 run이 여러 사유를 가질 수 있다. 단일 표시 verdict가 모든 진단을 대체하지 않는다. 오류 응답/exit-code의 구체 encoding은 다음 설계 단계의 contract에 매핑한다.

입력은 `domain-entities.md` §1의 type/format/허용값/유한 bounds를 먼저 검증하며 metadata 조회는 parameter binding, 외부 process는 구조화된 인자를 사용한다. 권한 있는 immutable migration bytes와 요청 문자열을 구분한다. timeout/외부 오류/cancellation은 FL-R1-03의 정리 계약을 따르며, 권한이나 완료를 확인할 수 없을 때 임의 fallback하지 않는다.

## 4. Testable Properties (PBT-01)

아래는 **구현될 성질의 명세**다. generated test code 또는 실행 결과가 아니다. category는 PBT-01의 분류를 사용하고, stateful은 검증 전략으로 명시한다. property 검증은 실제 구현의 내부 branch 복제가 아니라 독립적인 symbolic ledger/head/required-slot model과 관측 가능한 결과를 비교한다.

| Property | Component / category | 생성할 입력 및 property 관계 | Oracle/중요 counterexample | Trace |
|---|---|---|---|---|
| PROP-R1-01 | R1C/R1R/OBS; Round-trip, Invariant | 유효한 entity/value의 serialize-parse가 의미와 assurance/scope/version을 보존한다. canonical metadata의 무의미한 key 순서 차이는 동일 fingerprint 입력을 만든다. 부적합 type/format/bounds는 검증된 값이 될 수 없다. | null/부재, ordered step 배열과 unordered 집합, Unicode/ID/크기 경계; 의미 있는 순서/값 변경은 구분 | E-R1-01~24, BR-R1-02 |
| PROP-R1-02 | R1R registry; Oracle, Invariant | 같은 명시 spec/order/dependency 집합의 입력 나열 순서가 달라도 같은 plan 또는 같은 오류 집합이다. 누락/중복/cycle/order 위반은 유효 plan이 될 수 없다. | 작은 독립 dependency/order model; 두 owner의 같은 basename, 누락 capability, 이미 적용된 step의 없는 prerequisite | BR-R1-03/09, F08 |
| PROP-R1-03 | R1R reconciliation; Invariant | name/time/current digest만으로 VERIFIED_EXECUTION을 만들지 않는다. approval/domain/target 증거가 있는 adoption도 ADOPTED assurance를 유지한다. | unique 후보지만 역사적 proof 없음, 복수 후보, 다른 incarnation의 receipt, 현재 파일을 과거 executedDigest로 복사하는 경우 | BR-R1-05, R1FD1 |
| PROP-R1-04 | R1C/R1R check; Invariant, Idempotence | observe/plan/check/evaluate 반복 전후 target ledger/schema/active bundle이 동일하다. 같은 입력/시각에 같은 판정이다. | ledger 없음, DB 읽기 실패, 생성 임시물 존재; 허가된 report 출력과 target effect를 별도 관측 | BR-R1-01/04, F08/F13 |
| PROP-R1-05 | R1R migration; Invariant | atomic step의 effect와 matching ledger는 함께 commit되거나 함께 부재다. 실패 이후 step은 실행되지 않고 앞선 verified effect는 보존된다. | stateful fail-before-effect/between-statement-and-ledger/before-commit/after-commit; symbolic transaction model | BR-R1-07, R1FD2 |
| PROP-R1-06 | R1R retry; Idempotence, Oracle | 같은 target/identity/content의 만족된 step과 동일 intent 재요청은 추가 business effect를 만들지 않는다. fresh 승인으로 재개해도 verified step을 반복하지 않는다. | 같은 key의 다른 intent, 성공 후 target drift, restore incarnation 변경, partial verified sequence | BR-R1-09/10, F08 |
| PROP-R1-07 | R1R authority/fence; Invariant | 잘못된 purpose/target/plan/artifact, 만료/철회 승인 또는 stale fence로 새 effect를 commit할 수 없다. | stateful two-holder race, expiry 경계, revoked approval, old I/O가 남은 lease 만료 | BR-R1-08/12 |
| PROP-R1-08 | R1R reconcile; Oracle, Invariant | 권위 있는 증거로 COMMITTED/NO_EFFECT_CONFIRMED를 구분할 수 없으면 UNKNOWN을 유지한다. durable UNKNOWN 없이 effect를 열 수 없고 불확정 상태는 mutation/성공으로 확대되지 않는다. | UNKNOWN 기록 전/후·dispatch 전/후 중단, exit 0+partial output, row 없음+in-flight TX, head/receipt 불일치 | BR-R1-11, RJ-AC12 |
| PROP-R1-09 | R1R schema catalog; Oracle, Induction | finite local ref graph의 지원 closure는 각 logical resource/fragment를 유한하게 방문해 해소한다. 불명확/외부/지원 불가 ref는 명시 실패이며 network lookup이 없다. | cycle/self-ref, absolute local ID, missing fragment, duplicate ID, path escape; 작은 reference graph evaluator | BR-R1-13, F13 |
| PROP-R1-10 | R1R consumer mapping; Invariant | 모든 실제 wire 소비가 generated target을 사용하고 별도 view 변환은 approved adapter에 연결되며 public export closure에 금지된 internal type/field가 없을 때만 candidate가 유효하다. | 새 소비 import 누락, raw dump만 갱신, internal grant의 public re-export, view-model 명칭으로 wire 우회 | BR-R1-14, F13 |
| PROP-R1-11 | R1R binding generation; Oracle, Invariant | 같은 frozen catalog/consumer/toolchain/template/profile은 같은 완전한 output 집합을 만든다. committed consumer drift/target 하나의 실패도 성공으로 숨기지 않는다. | root-less defs, 추가/제거 export, nondeterministic banner/time, generator 실패 후 exit-success | BR-R1-15, F13 |
| PROP-R1-12 | R1R activation; Invariant, Oracle | stateful stage/validate/activate/crash/reconcile에서 authoritative consumer는 검증된 old 또는 complete new generation만 본다. 검증본이 없으면 명시적 unready다. stale expected head가 새 head를 덮어쓰지 못한다. | 여러 target 중 일부만 copy, receipt 유실, unmanaged tree를 good으로 간주, concurrent publishers | BR-R1-16, F13/RJ-AC12 |
| PROP-R1-13 | R1R inventory/advisory; Oracle, Invariant | scanner raw 관측 순서/정확한 중복은 normalized finding 의미를 바꾸지 않는다. inventory/coverage/unknown severity가 빠지면 clean이 될 수 없다. | 같은 advisory 반복, 다른 occurrence, 위조 alias 관계, 빈 배열+scan error, unlocked closure와 다른 artifact | BR-R1-17/18, F06 |
| PROP-R1-14 | R1R/R1C exception matching; Invariant | exact artifact/closure/advisory/가정/policy/approval/clock/revocation이 모두 맞아야 예외가 적용된다. 범위 확장·만료 후 원 finding은 다시 blocker다. | 동일 package의 새 artifact, OS/feature 가정 변경, `now == validUntil`, revoked exception; finding count 보존 | BR-R1-19, R1FD5 |
| PROP-R1-15 | R1C/R1R gate evaluation; Oracle, Commutativity | 동일한 trusted required slots/heads/current facts/시각에서 record 나열 순서는 결과를 바꾸지 않는다. 필수 증거 제거/무효화/미지원 compatibility로 eligible이 될 수 없고 unrelated history는 영향이 없다. | stateful recheck-start/fail/crash/late-old-PASS, head conflict, 빈 required list, local G1의 확대, schema/operation/writer mismatch | BR-R1-03/20/22, R1FD4 |
| PROP-R1-16 | OBS/R1C safe observation; Invariant | 허용 필드/이유만 출력되고 secret/private sentinel은 로그/일반 오류에 나타나지 않는다. liveness=true가 subjectGate를 승격하지 않으며 duration은 유효값 또는 명시적 unavailable이다. | credential 포함 원 예외문, raw SQL/DSN, clock 이상, live daemon+blocked artifact, metrics 전송 실패 | BR-R1-21, US-R4/5 |

### Component별 속성 및 I/O 구분

- **R1R**: registry/assurance/run/effect/binding/inventory/exception/evidence 변환에 PROP-R1-01~15를 적용한다. input generator는 valid/invalid domain 객체와 boundary/stateful sequence를 함께 만든다.
- **R1C**: 조회/투영 및 pure current/compatibility evaluator에 PROP-R1-01/04/14/15/16을 적용한다.
- **OBS**: 안전한 projection, 분리된 health/gate 의미와 명시적 시간 입력에는 PROP-R1-01/16이 있다.
- **No PBT properties identified for transport-only glue itself**: 실제 DB connection, 파일 이동 primitive, scanner process 실행, log/HTTP transport만으로는 독립 도메인 변환 성질을 주장하지 않는다. 그 경계의 atomicity/fencing/consumer 관측 보장은 위 model property와 별도 example/integration/fault-injection으로 검증한다. I/O라는 이유로 연계된 도메인 불변식을 생략하지 않는다.
- 입력 예시는 owner/domain IDs, stable migration IDs와 alias, artifact/target incarnation, order/dependency graph, proof/assurance, clock/revocation, visibility-qualified schema graph, consumer imports, package occurrences/advisory alias 등이다. 임의 primitive만 생성하는 방식으로 대체하지 않는다.
- 후속 Code Generation은 shrinking과 재현 seed를 유지하고, F06/F08/F13 및 중단/경쟁 counterexample을 영구 example regression으로 고정한다. 참조 모델은 구현의 내부 분기와 별도로 관측 ledger/effect/head/required-slot 의미를 표현한다.
- stateful model은 빈 sequence부터 apply/fail/crash/revoke/fence/reconcile/resume/activate/recheck/late-result의 유효한 sequence를 생성하고 **각 command 직후** 실제 observable state와 대조한다. 잘못된 명령은 명시적 rejection 경로로 생성한다. migration 효과는 `(target, identity, content)`별 실제 효과/ledger, publication은 complete head와 소비 bundle, evidence는 required slot/revision/outcome/reason set이 독립 oracle의 관측값이다.
- 동치는 semantic field/assurance, 의미 있는 순서와 reason/finding 집합의 일치를 뜻한다. 새 diagnostic ID/측정 duration을 업무 효과로 세지 않으며 시간 의존 판정은 clock를 명시적으로 고정한다. bytes 재현성이 요구된 binding 출력은 exact byte/set 비교다. metadata canonicalization은 원 source bytes를 Unicode 정규화하거나 바꿀 수 없다.
- **Category 적용성**: Round-trip/Invariant/Idempotence/Commutativity/Oracle/Induction을 위 표에 식별했다. Easy verification은 이번 unit에서 별도 성질로 추가하지 않는다. complete output/receipt 검증은 이미 invariant/oracle에 포함되며, 독립 solver/optimizer는 범위에 없다.

## 5. 결정 및 인수 추적성

| 입력 | Entity / Flow | Rules / Properties |
|---|---|---|
| R1FD1=A | E-R1-04~08, FL-R1-01/02 | BR-R1-02~05/09, PROP-R1-02/03/04 |
| R1FD2=A | E-R1-09~13, FL-R1-03/07 | BR-R1-06~09/11, PROP-R1-05~08 |
| R1FD3=A | E-R1-14~17, FL-R1-04 | BR-R1-13~16, PROP-R1-09~12 |
| R1FD4=A | E-R1-01/02/21~24, FL-R1-06/08 | BR-R1-20~22, PROP-R1-15/16 |
| R1FD5=A | E-R1-18~20, FL-R1-05/06 | BR-R1-17~20, PROP-R1-13/14/15 |
| R1FD6=A | E-R1-03/09~13/17, FL-R1-03/04/07 | BR-R1-08/10~12/16, PROP-R1-06~08/12 |
| F06 | inventory/advisory/exception/attestation, FL-R1-05/06 | BR-R1-17~20; zero unapproved critical/high 또는 유효한 exact 예외 |
| F08 | registry/ledger/legacy/step effect, FL-R1-01~03/07 | BR-R1-01~12; fresh target/복구/schema 요청 및 startup/CLI 동치 |
| F13 | catalog/consumer/candidate/activation, FL-R1-04 | BR-R1-13~16; offline full closure와 실제 소비 타입, non-success/atomic publication |
| US-R4/US-R5 | SafeObservation 및 GateEvaluation, FL-R1-06/08 | BR-R1-20~22, PROP-R1-15/16; 생존/조회 가능/대상 적격성 구분 |
| RJ-AC12 | run/reconcile/compatibility evidence | REM-1의 local checkpoint/관측 규약; 실제 REM-2/3/4 fault/recovery는 G4/G5 통합 |

## 6. 확장 준수 — Functional Design 수준

Compliant는 현재 기능 모델/규칙/속성에 대한 판정이다. N/A인 물리 설정/실행 검증은 승인된 요구를 유지한 채 다음 단계에 배정한다.

| Rule | 상태 | 근거 또는 N/A 사유 |
|---|---|---|
| SECURITY-01 | N/A | 저장/전송 암호화 설정은 NFR/Infrastructure 대상. subject/proof 참조의 민감성 분리와 원 요구 유지 |
| SECURITY-02 | N/A | network intermediary logging 설정 단계가 아님. OBS correlation은 BR-R1-21에 정의 |
| SECURITY-03 | Compliant | SafeObservation의 timestamp/level/messageCode/correlation, 민감정보/PII 비노출과 기존 중앙 관측 연결; logging 설정은 NFR/Infrastructure |
| SECURITY-04 | N/A | REM-1의 새 HTML/UI component 없음. 기존 web header/CSP 요구는 유지 |
| SECURITY-05 | Compliant | 공통 safe schema/type/format/finite bounds, parameter binding 및 immutable SQL과 요청 입력 분리; BR-R1-02~06/13~15 |
| SECURITY-06 | Compliant | observe/plan/record/mutate 목적 분리 및 exact approval/fence BR-R1-01/12 |
| SECURITY-07 | N/A | listener/firewall/egress 설정은 Infrastructure 대상. DAD1 private topology 유지 |
| SECURITY-08 | Compliant | R1C/runner의 현재 actor/목적/target/plan 범위와 expiry/revocation 확인 |
| SECURITY-09 | Compliant | 무인자 default apply 금지, 일반화 오류, uncertain/unsupported의 fail-closed |
| SECURITY-10 | Compliant | frozen inventory/lock/pin/SBOM/실제 coverage, trusted source·사용/지원 상태 및 exact 예외 BR-R1-17~19 |
| SECURITY-11 | Compliant | 잘못된 scope/중복 요청/동시 실행/묵시적 승격 오용을 rule/시나리오로 제한; 물리 rate 수치는 NFR |
| SECURITY-12 | Compliant | 기존 U3/운영 authority의 인증·admin MFA/session 철회 계승, credential/approval 구분 및 유효 권한 확인; credential 배치는 NFR |
| SECURITY-13 | Compliant | immutable input/attestation/assurance 및 atomic ledger/activation, 실제 consumer drift 검증 |
| SECURITY-14 | Compliant | self-delete 금지 감사, auth/권한/unknown/dependency 신호와 기존 경보/COE 연결. retention/경보 설정은 NFR |
| SECURITY-15 | Compliant | 안전한 최상위 오류/timeout/cancellation 경계, 자기 자원 정리와 미확정 효과 증거 보존; 첫 실패 중지/UNKNOWN 차단 |
| RESILIENCY-01 | Compliant | DAD1/UGR1의 REM-1 High/중단 영향/의존을 계승하고 R1C/R1R/OBS와 target/scoped gate 역할 구분 |
| RESILIENCY-02 | N/A | 수치 RTO/RPO/가용성은 NFR Requirements 대상. 승인된 single-host 목표 계승 |
| RESILIENCY-03 | Compliant | 기존 GitHub review/git-flow와 domain/shared owner sign-off에 immutable plan/reconciliation 이력 결속 |
| RESILIENCY-04 | Compliant | 승인된 versioned 수동 전환/rollback의 CompatibilityManifest, step rollback, complete-generation activation 및 명시 resume |
| RESILIENCY-05 | Compliant | phase/종단 duration, 지연·오류·처리량·포화, trace/correlation의 공통 관측 규약. 실제 dashboard/배선은 NFR/각 REM |
| RESILIENCY-06 | Compliant | read-only check, liveness/evidence readiness/subject gate 분리 |
| RESILIENCY-07 | Compliant | UNKNOWN/STALE/INCOMPLETE/권한 실패/coverage 누락 및 dependency/backup/capacity 저하 신호 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | target mutation 직렬화/fencing, finite workload/input budget, 포화 시 busy/backpressure. physical capacity 수치는 NFR |
| RESILIENCY-10 | Compliant | target check/verification/mutation의 역할·pool 분리, bounded dependency I/O, unknown effect 중지/재조정. 수치/패턴 배치는 NFR |
| RESILIENCY-11 | N/A | DR 전략 신규 선택 단계가 아님. 기존 backup-and-restore 및 명시 recovery plan 입력 유지 |
| RESILIENCY-12 | N/A | 실제 backup/restore/retention 설정과 drill은 NFR/Infrastructure/Build 대상 |
| RESILIENCY-13 | Compliant | FL-R1-07의 authoritative effect 확인과 fresh-authority 재개 |
| RESILIENCY-14 | Compliant | 16개 속성과 failure/경쟁/복구 scenario를 후속 test seam으로 정의 |
| RESILIENCY-15 | Compliant | immutable 실패/승인/보정 이력과 SafeObservation을 기존 COE에 연결 |
| PBT-01 | Compliant | Testable Properties 16개, component별 category/input/oracle/counterexample 및 I/O 적용성 식별 |
| PBT-02 | N/A - Functional Design 실행 | round-trip 명세는 PROP-R1-01, 테스트 구현은 Code 단계 |
| PBT-03 | N/A - Functional Design 실행 | invariant 명세는 PROP-R1 전반, 테스트 구현은 Code 단계 |
| PBT-04 | N/A - Functional Design 실행 | replay/재개 멱등성은 PROP-R1-04/06, 테스트 구현은 Code 단계 |
| PBT-05 | N/A - Functional Design 실행 | independent oracle 표면을 PROP-R1-02/08/09/11/13/15에 정의 |
| PBT-06 | N/A - Functional Design 실행 | effect/authority/publication의 stateful 전략을 명시; 테스트 구현은 Code 단계 |
| PBT-07 | N/A - Functional Design 실행 | domain generator 요구를 명시; 구현은 Code 단계 |
| PBT-08 | N/A - Functional Design 실행 | shrinking/seed 요구 유지; 실행 검증은 Code/Build 단계 |
| PBT-09 | N/A | framework 세부 선택/매핑은 NFR Requirements 대상 |
| PBT-10 | N/A - Functional Design 실행 | example regression과 property 병행 명세, 실제 테스트는 Code/Build 단계 |

## 7. 다음 설계 단계의 확정 항목

- NFR Requirements: role별 처리량/동시성/timeout·approval/evidence freshness/보존 값, recovery/관측 목표, stack/toolchain 및 PBT framework 매핑.
- NFR/Infrastructure Design: 실제 target identity/current-facts 수집, atomic effect/ledger와 lease fence 구현, complete-bundle activation/consumer pin, storage/encryption/credential 및 audit/backup 배치.
- Code Generation 계획은 PROP-R1-01~16을 명시적으로 참조해 test step/담당 구현과 연결한다. F06/F08/F13 영구 failing example regression부터 수정하며, F08의 fresh/restore DB에서 모든 mounted module 및 evidence/glossary 실제 요청 성공, F13의 실제 Python/TS build 소비, F06의 최종 patched artifact/lock/pin/SBOM을 검증한다. model PBT와 별개로 실제 DB/filesystem/scanner/consumer/중단 복구 integration을 포함한다. Functional Design 승인이 mutation 실행 승인을 대신하지 않는다.
