# REM-1 — Domain Entities

**단계**: CONSTRUCTION / Functional Design
**상태**: 작성·검증 및 R1FDR1=A 승인 완료 (2026-09-19; `../../plans/rem-1-platform-integrity-functional-design-plan.md`).
**입력**: UGR1 및 R1FD1~R1FD6=A. 설계 수준은 논리 entity/value/관계이며 DB schema나 framework type 정의가 아니다.
**Companion**: `business-logic-model.md`의 FL-R1-01~08, `business-rules.md`의 BR-R1-01~22 및 Testable Properties.

## 1. 공통 값과 identity

- **StableMigrationId**: `(domainOwner, declaredLocalId)`. filename/현재 디렉터리/실행 시각에서 유추하지 않는 명시적 영구 identity다. owner가 검토한 path 이동은 가능하지만 같은 ID의 실행 내용 변경은 허용하지 않는다.
- **TargetRef**: `(targetId, namespace, incarnation)`. credential/DSN 대신 등록된 opaque 참조를 사용한다. restore/교체로 identity가 바뀌면 새 incarnation이며 과거 적용/evidence를 자동 재사용하지 않는다.
- **Fingerprint**: `(fingerprintPolicyVersion, algorithmRef, digest)`. canonical metadata는 명시적으로 정렬된 key/set과 의미 있는 array 순서를 보존한다. source artifact 내용은 exact bytes fingerprint로 식별한다. hash/crypto 알고리즘은 NFR에서 정한다.
- **Instant / ValidityWindow**: 검증된 clock의 평가 시각과 `[validFrom, validUntil)` 구간. 경계 시각 `now == validUntil`은 만료다. clock를 신뢰할 수 없으면 시간 의존 eligibility는 확정하지 않는다.
- **ActorRef / Purpose / ScopeRef**: 현재 권한을 확인할 수 있는 actor 및 명시적 작업 목적/대상 범위. 승인 기록이나 증거 참조 자체는 실행 credential이 아니다.
- **SourceRef / OutputRef**: 허용된 source root/target namespace 안의 canonical locator와 fingerprint. path escape, collision, 다른 target으로의 alias 이동을 검증하며 외부 응답/로그에는 필요한 안전한 식별자만 투영한다.
- **CompatibilityManifest**: DAD1의 공통 versioned artifact를 계승한다. manifest version/digest, exact artifact/role 집합, 지원 schema/operation version 조합, writer epoch, registry/evidence refs, consumer/binding generation 및 필수 capability/config 선언을 담는다. 자기 선언만으로 호환이 입증되는 것은 아니며 trusted policy 및 실제 관측과 대조한다.
- **ExecutionScope**: action에 따라 TargetRef, publication namespace 또는 exact immutable artifact 집합을 식별한다. 관측/검사 run에 존재하지 않는 live DB target을 꾸며 넣지 않는다. mutable target이 있는 action만 해당 target fence를 요구한다.

`TargetRef`의 identity와 `SubjectSnapshot`의 관측 state fingerprint는 다르다. 정상 step 적용으로 state가 변해도 같은 target이다. 재시도는 전체 초기 state와의 단순 equality 대신 검증된 checkpoint 이후의 예상 state와 비교한다.

모든 외부 입력은 versioned safe schema의 type/format/허용값과 정책에 명시된 유한한 string/collection/payload/depth bounds를 통과해야 한다. 등록된 opaque ID와 locator를 구분하며 요청 문자열을 SQL/OS command로 이어 붙이지 않는다. 실행 SQL은 승인된 registry의 검증된 immutable source bytes이고 요청자가 삽입한 SQL이 아니다. 한도의 수치는 NFR에서 정하되 한도 부재를 무제한으로 해석하지 않는다.

## 2. Entity catalogue

필드는 논리적 최소 정보다. optional 값의 부재를 성공/빈 결과와 혼동하지 않는다.

| ID | Entity | 논리 필드/관계 | 핵심 불변식 |
|---|---|---|---|
| E-R1-01 | SubjectSnapshot | subjectKind, artifactRef 또는 targetRef, relevantStateFingerprint, runtimeProfileRef, observedAt, observationProvenance | artifact digest와 target incarnation/state를 분리. 다른 subject의 증거를 대입할 수 없음 |
| E-R1-02 | PolicySnapshot / GateSpec | policyId/version, action/scope, requiredGateSlots, supportedFeatures, inputBounds, freshnessRules, applicabilityDecisions | caller가 required gate/입력 한도를 임의로 줄이거나 없앨 수 없음. N/A는 근거가 있는 policy 결정 |
| E-R1-03 | ApprovalBinding | approvalId, actor/authorityRef, purpose, targetRef, planDigest, artifactSetDigest, policyRef, validity, revocationRef | exact scope에만 적용. 갱신은 새 승인 기록이며 과거 승인 내용을 변경하지 않음 |
| E-R1-04 | MigrationSpec | migrationId, owner, sourceRef/exactDigest, declaredOrder, dependencyIds, targetSelector, effectClass, pre/postconditionSpecRefs | identity/content binding과 dependency/order는 명시적. ATOMIC_STEP과 EXPLICIT_NONATOMIC을 구분 |
| E-R1-05 | RegistrySnapshot | registryVersion/digest, MigrationSpec 집합, requiredCapabilityManifest, discovered/excluded source inventory, legacyAliasCandidates | scoped file/capability coverage가 완전하고 ID/path/order가 충돌하지 않아야 유효 |
| E-R1-06 | LedgerObservation | targetRef, readState, observedRevision/fingerprint, canonicalProofs, 원 legacy rows/name/time, readErrors | ABSENT/AVAILABLE/UNAVAILABLE/INCONSISTENT 구분. 조회 중 ledger를 만들거나 변경하지 않음 |
| E-R1-07 | MigrationSatisfaction | targetRef, migrationId, assurance, executedDigest 또는 adoptedAgainstDigest, executionReceiptRef 또는 adoptionRef, observedAt | VERIFIED_EXECUTION과 ADOPTED_BASELINE을 구분. adoption digest를 과거 executedDigest로 기록하지 않음 |
| E-R1-08 | LegacyReconciliationDecision | 원 observation/row refs, candidate mapping, ambiguity set, domain confirmation, target postcondition evidence, approvalRef, assurance/decision | 원 이력 보존. 당시 실행 증거가 없으면 verified 실행이라고 주장하지 않음 |
| E-R1-09 | ExecutionPlan | action, executionScope, registry/catalog/consumer/compatibility/policy digests, immutable input refs, ordered steps, expected preconditions/checkpoints, recoveryPlanRef | planDigest로 동결. 변경된 의미는 새 plan이며 미확인 효과 위에서 재계산하지 않음 |
| E-R1-10 | RunIntent | runId, semanticKey, planDigest, executionScope, artifactSetDigest, policyRef, createdBy, lifecycle, successorRef | semanticKey에 attempt/time/새 approval instance를 넣지 않음. 승인 갱신이 작업 범위를 바꾸지 않음 |
| E-R1-11 | RunAttempt | attemptId/ordinal, runId, explicit invocation, actor/applicable current approvalRef, applicable leaseRef, started/finishedAt, attemptOutcome, reasons | 한 번의 명시 실행 시도. process 재시작은 새 mutation 권한이 아님 |
| E-R1-12 | EffectCheckpoint | checkpointId/sequence, runId/stepId/attemptId, recordedAt, expectedBefore, proposedAfter, effectKind, fenceEpoch, effectAssurance, evidence/receiptRefs | append-only 관측 기록. NOT_STARTED/NO_EFFECT_CONFIRMED/COMMITTED/UNKNOWN 구분. UNKNOWN은 재실행의 허가가 아님 |
| E-R1-13 | TargetLease / Fence | target/scope, holderAttempt, epoch, validity, revocation/quiescence evidence | target별 mutation 직렬화. 만료만으로 이전 I/O가 끝났다고 가정하지 않음 |
| E-R1-14 | SchemaCatalog | catalogDigest, local resources by canonical ID, supported dialect/features, reference graph/closures, discovery coverage | remote fetch 없음. duplicate/unresolved/unsupported를 실패로 남기고 legal recursion은 유한하게 처리 |
| E-R1-15 | ConsumerManifest | manifestDigest, public/server/internal consumer scopes, schema roots/exports, generated wire targets, declared view adapters, actual-consumption inventory | wire 소비 지점은 generated contract를 사용. view model 명칭만 바꿔 검증을 피할 수 없음 |
| E-R1-16 | BindingCandidate | candidateId/digest, catalog/consumer/toolchain/template/policy refs, complete output set, validation/visibility proofs | immutable inactive candidate. target 하나라도 누락/실패하면 publish 가능 상태가 아님 |
| E-R1-17 | BindingActivation | publicationScope, expectedOldHead, newCandidateRef, activationVersion, fence/approval/effect receipt | 소비자는 완전한 generation에 pin. partially copied tree는 유효한 active bundle이 아님 |
| E-R1-18 | DependencyInventory | exact artifact/lock/runtime/image fingerprints, component occurrences/edges, source/provenance, coverage status | manifest 재해석 결과를 실제 frozen runtime inventory와 혼동하지 않음 |
| E-R1-19 | AdvisoryObservationSet | inventoryRef, trusted feed/scanner revisions, completed coverage, raw result refs, normalized findings/aliases/severity/occurrences | 중복 정규화 후에도 원 finding/provenance 보존. missing/error/unknown severity를 clean으로 바꾸지 않음 |
| E-R1-20 | ReachabilityException | exact artifact/closure/advisory/occurrence scope, proof/assumptions, policy, approver, validity/revocation | 단일 exact artifact/closure에만 적용. runtime 가정이 바뀌면 자동 재사용하지 않음 |
| E-R1-21 | VerificationAttestation | evidenceId/digest, gateSlot, subjectSnapshotRef, policy, verificationAttemptRef/selectionRevision, verifier/provenance, observedAt/validity, outcome/reasons, referenced proofs/exceptions | immutable fact. artifact/target/gate/정책 및 발행 revision 결속과 완전성을 검증해야 소비 가능 |
| E-R1-22 | EvidenceHeadSelection | subject/gate/policy binding, selectionRevision, verificationAttemptRef, selectionState, applicable evidenceRef, expectedPreviousRevision, authority | PENDING/RESOLVED 구분. latest 시각 또는 pass인 기록을 임의 선택하지 않음. head 경쟁/미완료/모순은 명시적 결손 |
| E-R1-23 | GateEvaluation | evaluationId, scope/requiredSlots, exact inputs/head versions, evaluationTime/current facts, verdict, reasonSets, eligible, exceptionRefs | 파생 판정. 역사적 attestation PASS만으로 현재 eligible을 주장하지 않음 |
| E-R1-24 | SafeObservation | eventTime, level/messageCode, service/role, trace/correlation 및 applicable request/job/event/run/step/gate refs, liveness, serviceReadiness, subjectGate summary, allowed reasons, phase durations/metrics, evidence refs | 프로세스 생존/증거 조회 가능/대상 적격성을 별도 표현. credential/raw SQL/private payload/PII는 제외 |

## 3. 관계와 집계 경계

1. RegistrySnapshot은 domain-owned MigrationSpec을 모은다. LedgerObservation은 TargetRef의 원 이력을 읽고 MigrationSatisfaction과 LegacyReconciliationDecision의 입력이 된다.
2. LegacyReconciliationDecision은 하나 이상의 원 행/명시 identity를 연결할 수 있지만 각 canonical target+identity의 유효한 만족 증거는 충돌 없이 판정돼야 한다. baseline은 검증한 현재 postcondition 집합을 설명하며 과거 실행 순서를 발명하지 않는다.
3. ExecutionPlan의 immutable 입력과 의미가 RunIntent를 식별한다. RunIntent 하나에 여러 Attempt/EffectCheckpoint/승인 참조가 연결되며 이력은 누적한다.
4. SchemaCatalog + ConsumerManifest + 고정 toolchain/template/policy가 BindingCandidate를 결정한다. 모든 output이 검증된 candidate만 BindingActivation의 후보가 된다.
5. DependencyInventory와 AdvisoryObservationSet이 supply-chain gate 증거를 만든다. ReachabilityException은 finding을 삭제하지 않고 정확한 적용 근거로 연결된다.
6. gate별 immutable VerificationAttestation을 EvidenceHeadSelection이 선택하고 GateEvaluation이 current scope에서 판정한다. CompatibilityManifest의 지원 조합과 실제 artifact/schema/operation/writer 상태를 같은 입력에 결속한다. R1C/CLI/local startup은 같은 판정 함수를 소비한다.
7. SafeObservation은 허용된 actor에 대한 투영이다. REM-1 Run은 platform runner의 모델이며 REM-2/3/4 public-job RK 구현에 의존하지 않는다.

## 4. 상태 및 보장 수준

### 4.1 Migration의 파생 만족 상태

| 상태 | 의미 | 처리 |
|---|---|---|
| VERIFIED_APPLIED | 동일 target incarnation/identity/content의 신뢰 가능한 실행+ledger 증거 | 현재 요구 postcondition/호환 확인 후 재실행 없이 사용 |
| ADOPTED_BASELINE | 당시 checksum 증거 대신 승인된 현재 baseline을 채택 | assurance를 그대로 노출하며 policy가 허용한 범위에서만 효과 만족으로 사용 |
| PENDING | 알려진 초기화 상태와 검증된 precondition에서 아직 효과가 필요 | 승인 plan/직렬화 아래 실행 가능 |
| NEEDS_RECONCILIATION | legacy 후보 모호/실행 증거 불충분/현재 상태와 이력 불일치 | 명시적 reconciliation 전 자동 skip/apply 금지 |
| CHANGED_DEFINITION | 같은 canonical identity의 내용 fingerprint가 달라짐 | 새 migration 또는 명시 수정 계획 필요; 기존 proof 덮어쓰기 금지 |
| UNKNOWN | target/current facts를 읽거나 신뢰할 수 없음 | 조회 실패와 실제 부재를 분리하고 mutation/eligibility 보류 |

Ledger ABSENT는 그 자체로 빈 DB 증거가 아니다. fresh target임을 별도 관측/검증할 수 있을 때만 승인된 bootstrap plan을 만들며, 기존 schema/effect가 있으면 reconciliation 대상으로 둔다.

### 4.2 RunIntent와 attempt

| Run lifecycle | 진입/전이 의미 |
|---|---|
| PLANNED | immutable plan/intent 기록. mutation 허가를 의미하지 않음 |
| READY | 현재 precondition/권한을 확인한 실행 후보. 실제 effect 경계에서 재확인 |
| RUNNING | 명시 attempt가 실행 중. mutable target effect는 유효한 target fence가 필요하며 read-only 검사는 관측 권한만 사용 |
| PAUSED | 효과가 알려진 중지/실패/승인 부재. 동일 plan의 검증된 잔여 step만 새 명시 attempt로 재개 가능 |
| RECONCILE_REQUIRED | 효과/activation/lease 종료 여부 불명확. 관측으로 확인하기 전 새 mutation 금지 |
| SUCCEEDED | 모든 계획된 효과/검증이 완료됐다는 역사적 사실. 이후 target/policy 변경은 별도 current evaluation을 무효화할 수 있음 |
| SUPERSEDED | 의미가 다른 후속 plan/intent로 대체되거나 명시 폐기됨. 기존 효과를 지우거나 같은 record를 새 의도로 재사용하지 않음 |

- attempt outcome은 VERIFIED_COMPLETE, FAILED_NO_EFFECT, PARTIAL_VERIFIED, EFFECT_UNKNOWN, REJECTED_BEFORE_EFFECT로 구분한다. 실패를 오래된 pending 뒤에 숨기지 않는다.
- PAUSED/RECONCILE_REQUIRED에서 재개하려면 effect 확인, 현재 권한, 같은 plan의 유효성 및 fence를 다시 검증한다. terminal history를 변경하지 않고 새 attempt를 추가한다.
- SUCCEEDED 재요청은 과거 receipt와 현재 상태를 구분해 반환한다. 현재 target이 그 postcondition을 잃었으면 drift를 보고하고 새 plan/reconciliation을 요구한다.

### 4.3 EffectCheckpoint 전이

`PREPARED`라는 별도 assurance enum은 두지 않는다. 효과를 준비하는 단계와 효과 발생의 보장 수준을 아래와 같이 구분한다. checkpoint는 덮어쓰는 단일 행이라는 가정 없이 append-only 이력으로 표현하고 현재 assurance를 파생한다.

| 전이 | 필요한 사실 | 중단 시 의미 |
|---|---|---|
| 미생성 -> NOT_STARTED | plan/attempt/checkpoint가 durable하고 해당 effect 실행권을 아직 넘기지 않음 | 이 상태에서 effect 실행 경로가 열리지 않았음을 확인할 수 있어야 함 |
| NOT_STARTED 또는 NO_EFFECT_CONFIRMED -> UNKNOWN | 현재 권한/fence/precondition 확인 후 실행 가능성을 열기 **전에** UNKNOWN을 durable 기록 | 기록 직후 실제 실행 전 중단돼도 no-effect를 추정하지 않고 재조정 |
| UNKNOWN -> COMMITTED | exact target/step/content의 authoritative commit/activation 및 요구 postcondition 증거 | 성공 사실을 기록하고 동일 effect를 반복하지 않음 |
| UNKNOWN -> NO_EFFECT_CONFIRMED | 이전 실행의 fencing/quiescence와 authoritative abort/no-effect 증거, expectedBefore 일치 | 새로운 명시 attempt와 현재 권한 아래 재개 후보 |
| UNKNOWN -> UNKNOWN | 증거 누락/불일치/진행 중 I/O 가능성 | 재실행/성공/rollback 추정 금지 |

관측된 COMMITTED 이력은 뒤늦은 target drift나 오래된 응답으로 미실행 상태로 돌아가지 않는다. 실패한 결과 기록을 보정할 때도 원 attempt/증거를 보존한다. 효과를 열기 전 UNKNOWN 기록에 실패하면 effect를 시작하지 않는다.

### 4.4 Publication과 gate

- BindingCandidate: STAGED -> VALIDATED 또는 REJECTED. VALIDATED만 활성화할 수 있다. activation이 불명확하면 candidate 자체의 validation을 취소하는 대신 activation/effect를 UNKNOWN으로 분리한다.
- Publication head: UNMANAGED/UNINITIALIZED, VERIFIED_ACTIVE, UNCONFIRMED. 기존 tree가 존재한다는 이유로 VERIFIED_ACTIVE로 채택하지 않는다. 마지막 검증본이 있으면 다음 candidate가 완성되기 전까지 유지한다.
- Gate verdict: BLOCKED(확인된 위반), INCOMPLETE(필수 증거/관측 결손), STALE(일치/유효성 상실), ELIGIBLE_WITH_EXCEPTIONS, ELIGIBLE. 여러 원인은 모두 보존하고 표시 우선순위는 이 순서다.
- `eligible`은 마지막 두 verdict에서만 true다. scope별 required slots를 모두 확인해야 하며 빈/생략 목록을 근거로 pass를 만들지 않는다.
- authoritative 재검사는 권한 있는 publisher가 해당 slot의 새 monotonic selectionRevision을 PENDING으로 기록한 뒤 시작한다. 완료는 같은 revision/attempt에 결속한 immutable 성공/실패/검사 불능 attestation으로 RESOLVED한다. 이전 revision의 늦은 결과는 history일 뿐 새 head를 덮을 수 없다. PENDING/결과 기록 실패는 INCOMPLETE이며 이전 PASS로 fallback하지 않는다. 단순 check/조회/preview는 이런 publication을 실행하지 않는다.

## 5. Functional Design 경계

- entity는 논리 모델이며 SQL/파일 배치/lock 구현/crypto 알고리즘을 확정하지 않는다. 실제 atomic effect+ledger, fencing, immutable bundle activation을 제공하지 못하는 adapter는 해당 기능을 사용 가능하다고 선언할 수 없다.
- 보존/expiry의 값은 NFR에서 정하되 interval 비교, scope 무확대, immutable history 및 privileged 실행의 현재 권한 확인은 본 단계의 고정 규칙이다.
- frontend-components는 N/A다. schema-generated wire와 수작업 view model의 경계는 ConsumerManifest와 검증 규칙으로 다룬다.
