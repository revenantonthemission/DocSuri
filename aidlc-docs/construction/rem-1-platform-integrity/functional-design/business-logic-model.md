# REM-1 — Business Logic Model

**단계**: CONSTRUCTION / Functional Design
**상태**: 작성·검증 및 R1FDR1=A 승인 완료 (2026-09-19; `../../plans/rem-1-platform-integrity-functional-design-plan.md`).
**결정**: R1FD1~R1FD6=A. Entity/value는 `domain-entities.md`, 규칙/속성은 `business-rules.md`를 따른다.

흐름은 논리적 알고리즘과 관측 가능한 보장을 정의한다. target I/O, atomic effect/ledger, fence 및 bundle activation의 실제 구현은 NFR/Infrastructure/Code에서 이 계약을 만족해야 한다.

공통 입력은 `domain-entities.md` §1의 safe schema/type/format/finite bounds를 먼저 통과한다. Operator/System의 현재 인증/권한은 기존 U3 및 승인된 운영 authority에서 확인하며 approval/evidence 문서 자체를 credential로 받지 않는다. admin 인증/MFA, session 철회와 service identity의 기존 제약을 계승하고 REM-1 전용 우회 로그인 경로를 만들지 않는다.

## FL-R1-01 — Read-only 관측과 registry/plan 검증

**입력**: 등록된 subject/consumer scope, RegistrySnapshot 후보, PolicySnapshot, 현재 관측 권한. **출력**: validated plan candidate 또는 명시적 validation/관측 실패.

1. 요청 action/scope를 검증하고 등록된 TargetRef/ArtifactRef로 해소한다. raw DSN/임의 path를 실행 대상으로 신뢰하지 않는다. CLI의 인자 부재, daemon startup/health 또는 check가 apply 선택으로 이어지지 않는다.
2. registry 전체의 stable ID/content/path binding, duplicate/alias collision, declared order/dependency, 허용 target selector를 검증한다. dependency cycle, order 위반, 존재하지 않는 필수 dependency는 target mutation 전에 거부한다.
3. 등록 root의 source inventory와 required module/capability manifest를 대조한다. unregistered/missing 파일과 consumer-required table/capability 누락을 보고한다. 명시적으로 제외한 항목은 owner/이유를 남기고 실행 대상으로 발견됐다고 자동 편입하지 않는다.
4. authoritative readonly adapter로 target incarnation, ledger 및 관련 pre/postcondition 관측을 얻는다. read error를 빈 ledger로 바꾸지 않는다. ABSENT는 UNINITIALIZED이며 이 read 단계에서 DDL/초기화를 수행하지 않는다.
5. FL-R1-02로 각 legacy/current claim의 assurance를 판정한다. 같은 identity의 changed content, 불명확 history, 이미 적용된 step의 불충족 prerequisite는 자동 apply로 보정하지 않는다.
6. 이미 만족된 항목과 pending step을 분리하고 pending을 declared order로 정렬한다. 독립 domain의 이미 적용된 항목이 전체 order의 연속 prefix일 필요는 없으나, 새 step은 모든 prerequisite가 검증된 기존 상태 또는 선행 pending step으로 충족돼야 한다.
7. 하나의 TargetRef/scope에 대해 frozen input refs, expected preconditions/checkpoints, effect class, 명시적 metadata bootstrap 및 recovery 요구를 ExecutionPlan으로 고정한다. live mutation에는 승인된 요구에 따라 격리 검증, exact dry-run/대상 범위, verified backup/restore 및 rollback/사후 검증 증거를 결속한다. 다른 target의 mutation을 scope 안에 몰래 추가하지 않는다.
8. startup/CLI/check는 동일한 registry+consumer scope+현재 관측에 동일한 판정을 반환한다. protected action에서 required gate가 비어 있거나 target이 불명확하면 성공 계획을 만들지 않는다.

**경계**: fresh target bootstrap은 별도 관측으로 기존 business schema/effect가 없음을 확인한 승인 plan의 명시 step이다. ledger가 없다는 사실만으로 기존 DB에 fresh migration을 재실행하지 않는다.

이미 실행된 step의 assurance/dependency 이력과 **현재** capability 요구를 구분한다. 뒤이은 검증된 migration으로 대체·제거된 과거 구조를 매 startup마다 복원하도록 요구하지 않는다. step 직후 postcondition은 그 commit의 증거이고, current readiness는 domain이 선언한 현재 schema/capability 및 호환 조합으로 판정한다.

## FL-R1-02 — Legacy assurance와 reconciliation

**입력**: LedgerObservation, registry alias 후보, 신뢰 가능한 release/execution evidence, target postcondition observations. **출력**: MigrationSatisfaction 또는 reconciliation 필요 사유.

read-only check/plan은 아래 assurance/후보 계산까지만 수행한다. canonical mapping/adoption의 저장은 별도 명시적 action이며 조회 권한이나 후보 존재만으로 시작하지 않는다.

1. legacy row의 원 name/applied_at/provenance를 보존하고 registry의 canonical 후보 집합을 만든다. filename 순서나 이름 유사성으로 한 후보를 임의 선택하지 않는다.
2. candidate가 하나이며 당시 exact content와 해당 target의 실제 committed execution을 증명하는 신뢰 가능한 evidence가 모두 있는 경우에만 VERIFIED_EXECUTION으로 연결한다. 과거 artifact가 존재하거나 시각이 비슷하다는 사실만으로 실행을 증명하지 않는다.
3. 증거가 없거나 여러 후보가 있으면 NEEDS_RECONCILIATION으로 표시한다. current 파일 digest는 현재 candidate의 fingerprint일 뿐 과거 executedDigest가 아니다.
4. domain owner가 현재 target 상태와 검증 가능한 postcondition/baseline 의미를 정의하고 mapping/assurance/한계를 담은 reconciliation candidate를 검토한다. 이후 migration으로 제거된 구조는 당시 효과를 다시 관측할 수 없음을 명시하고 검증한 현재 baseline의 의미로 다룬다.
5. adoption은 별도 목적의 현재 ApprovalBinding과 target fence 아래에서 수행한다. 관측 이후 target/registry/후보가 달라졌으면 다시 검토한다. FL-R1-03의 intent/권한/checkpoint 원칙을 적용해 승인된 adoption record와 canonical mapping을 원자적으로 기록한다. 원 legacy 행을 지우거나 당시 checksum/실행 시각을 새로 만들어 넣지 않으며, adoption 과정에서 migration SQL을 실행하지 않는다.
6. ADOPTED_BASELINE은 current baseline을 효과 만족으로 받아들인 기록이다. verifier/export/health는 이를 VERIFIED_APPLIED와 구분한다. 이후 검증된 migration checkpoint가 baseline을 전진시켜도 provenance를 유지하고, 설명되지 않는 target drift는 다시 reconciliation 대상이다.
7. 서로 충돌하는 mapping, unassigned ledger claim, changed-definition 또는 불충분한 postcondition 증거는 blocker다. 이름만으로 skip/reapply하는 fallback이 없다.

## FL-R1-03 — 명시 RunIntent와 step별 migration 적용

**입력**: validated ExecutionPlan, explicit invocation, 현재 actor/ApprovalBinding. **출력**: checkpoint/attempt/attestation 및 run의 완료·중지·재조정 상태.

1. action/target/plan/artifact/policy/scope의 semantic key로 RunIntent를 생성하거나 조회한다. 동일 request key에 다른 의미를 붙이면 conflict다. 현재 승인 instance/attempt/time은 semantic identity를 바꾸지 않는다.
2. 기존 SUCCEEDED intent이면 기존 receipt와 current evaluation을 제공하며 다시 mutation하지 않는다. 현재 target이 역사적 postcondition을 잃었으면 drift를 보고하고 새 plan/reconciliation을 요구한다.
3. 현재 권한/approval scope/expiry/revocation, 입력 artifact integrity 및 target precondition을 확인한다. 새 explicit attempt를 기록하고 target별 exclusive lease/fence를 획득한다. 첫 target effect 전에 durable intent/checkpoint 기록이 가능해야 한다.
4. fence를 얻은 뒤 target/ledger를 다시 읽는다. 다른 실행이 이미 완료한 matching step은 새 실행으로 세지 않는다. 초기 state와 다른 것은 검증된 checkpoint에 의해 설명돼야 하며 그렇지 않으면 멈춘다.
5. pending step마다 source bytes/fingerprint, prerequisite, 현재 승인 및 fence, precondition을 확인한다. 검증한 immutable bytes를 그대로 실행하며 mutable path를 다시 읽어 다른 내용으로 바꾸지 않는다. effect 실행 가능성을 열기 전에 해당 checkpoint의 UNKNOWN을 durable 기록한다. ATOMIC_STEP은 step effect와 matching canonical ledger proof를 같은 원자 단위로 commit한다. postcondition을 만족하지 못하면 그 step을 rollback하며 이미 검증된 앞선 step을 자동 역실행하지 않는다.
6. commit 확인 뒤 EffectCheckpoint/attestation을 누적한다. target commit 후 journal/응답 기록이 실패하면 실제 효과를 rollback했다고 주장하지 않고 FL-R1-07로 넘긴다.
7. 첫 실패에서 새 step 시작을 멈춘다. confirmed no-effect/partial verified는 PAUSED, 불명확 effect/lease는 RECONCILE_REQUIRED다. 재개는 같은 plan의 검증된 잔여 step에 한정하며 fresh 권한을 재확인한다.
8. EXPLICIT_NONATOMIC/되돌릴 수 없는 step은 일반 atomic loop에 섞지 않는다. 별도 execution/recovery plan, 권한 및 확인 수단이 정의된 경우에만 독립 action으로 실행한다.
9. 모든 planned effect와 필요한 검증/receipt가 완료되면 역사적 SUCCEEDED를 기록한다. schema readiness/local G1/전체 release gate는 FL-R1-06에서 별도로 평가한다.

**권한 경계**: 새 effect/activation은 현재 유효한 권한에서만 시작·확정한다. 승인 만료/철회를 commit 전에 알게 되고 atomic abort가 가능하면 abort한다. 이미 일어난 효과나 중단할 수 없는 I/O의 결과는 보수적으로 재조정하며, 만료 후 새로운 mutation을 이어가는 근거로 삼지 않는다. 관측/기존 사실 기록에는 해당 목적의 별도 현재 권한이 필요하다.

**중단 정리**: 외부 I/O 오류/timeout/cancellation은 상위 안전한 오류 경계에서 처리한다. 자기 connection/handle/미활성 임시물을 정책에 따라 정리하되 in-flight effect의 종료를 확인하지 않고 target fence를 안전하게 해제했다고 주장하지 않는다. 재조정에 필요한 evidence/candidate/receipt는 보존한다. 일반 cleanup 실패와 실제 commit/no-effect 보장은 별개다.

## FL-R1-04 — Offline schema와 actual-consumer binding pipeline

**입력**: frozen schema roots/bytes, ConsumerManifest, toolchain/template/policy identity, actual consumption inventory, expected publication head. **출력**: 실패 증거 또는 전체 검증된 BindingCandidate/Activation.

1. 선언 root의 모든 schema를 발견하고 canonical ID/resource/fragment registry를 만든다. duplicate ID, 경로 경계 위반, 지원하지 않는 dialect/feature를 진단한다. schema가 없는데 성공으로 처리하지 않는다.
2. 모든 local reference를 catalog 안에서 해소한다. absolute URL 형태의 ID도 등록된 local resource로만 해소한다. remote fallback은 없다. visited resource/fragment 집합으로 recursion을 종료하고 지원되는 recursive schema는 유효하게 취급한다.
3. 각 resource/export를 explicit consumer 또는 dependency-only 분류에 연결한다. 모든 실제 wire 소비 지점이 declared generated target을 사용해야 한다. 새 schema/consumer/export가 누락됐거나 수작업 wire type으로 우회하면 불완전한 manifest다.
4. public browser/server-only/internal worker의 export closure와 visibility를 검증한다. private intent/grant/locator를 이름만 바꿔 public output에 포함할 수 없다. 실제 UI/domain view model은 generated wire input에서 명시적 adapter로 변환하고 positive/negative fixture로 인수를 확인한다.
5. 격리 inactive namespace에 모든 target을 생성한다. exact input/toolchain/template/profile이 같으면 동일한 output 집합/내용이 나와야 한다. generator failure, parse/type/fixture 실패, target collision 또는 내부 타입 노출 중 하나라도 있으면 candidate 전체를 REJECTED로 두고 non-success를 반환한다.
6. check 모드는 candidate와 committed/build-consumed 계약의 내용·완전성·visibility·실제 소비를 비교한다. 별도 drift dump만 비교하거나 published tree를 바꾸지 않는다. 임시 계산물과 안전한 report 출력은 target mutation과 구분한다.
7. publish는 완전한 VALIDATED candidate만 대상으로 한다. current approval, frozen inputs, expectedOldHead 및 publication fence를 다시 확인하고 UNKNOWN checkpoint를 durable 기록한 뒤 logical atomic activation을 수행한다. consumer는 전체 generation에 pin하며 검증되지 않은 multi-target 부분 copy를 읽지 않는다.
8. 마지막 검증본은 새 generation이 활성화되기 전까지 유지한다. 최초 도입의 기존 unmanaged tree는 관측/복구 자료로 보존할 수 있지만 검증 없이 known-good으로 부르지 않는다. 관련 없는 수작업 파일을 임의 overwrite하지 않는다.
9. activation receipt가 불확정이면 FL-R1-07로 head/candidate를 조회한다. 이미 완전한 새 head이면 같은 효과의 확인만 기록하고, old head가 보존됐다는 명확한 증거가 있으면 재개 후보로 둔다. mixed/unknown head는 새 write를 막고 복구를 요구한다.

**논리 원자성**: 여러 output 경로를 물리적으로 어떤 순서로 저장하든 consumer가 관측하는 authoritative generation은 하나의 완전한 bundle이어야 한다. 이 계약을 제공하지 않는 adapter는 publish capability를 ready로 표시하지 않는다.

## FL-R1-05 — Frozen inventory, advisory 및 exact 예외

1. 검사 scope의 exact artifact/lock/installed runtime/container image provenance를 수집하고 inventory coverage를 검증한다. unlocked manifest 재해석, mutable image tag 또는 일부 package만 조사한 결과를 frozen production closure의 증거로 사용하지 않는다.
   - build/CI toolchain도 pin/verified-source 범위에 포함한다. dependency는 공식/검증된 source와 integrity를 확인하며 role별 사용 근거/지원 상태를 검사한다. 확인된 불필요·abandoned dependency 또는 unvetted source를 유지한 채 해당 gate를 통과시키지 않고 수정 대상으로 반환한다. 검사 자체가 설치/업데이트/삭제를 수행하지 않는다.
2. 해당 ecosystem/대상에 필수인 scanner/feed 검사를 실행하거나 policy가 허용하는 현재의 동일-binding 증거를 확보한다. process exit 외에 실행 완료, coverage, 지원 schema, feed/tool revision 및 원 결과의 완전성을 검증한다.
3. trusted advisory ID/alias 및 component occurrence에 따라 중복 관측을 정규화한다. 원 row/provenance와 영향을 받는 경로는 유지한다. ID 문자열이 유사하다는 이유로 서로 다른 advisory를 합치지 않는다. severity 모순은 보수적으로 처리하며 알 수 없으면 clean이 아니다.
4. known critical/high finding마다 현재 matched ReachabilityException을 판정한다. artifact digest, closure, advisory/occurrence, proof의 runtime 가정, policy, approver 권한, 유효 구간 및 revocation이 모두 일치해야 한다.
5. 변경/만료/철회/미확인 proof의 예외는 적용하지 않는다. 단일 exact scope 밖으로 복제하지 않으며 재검토·새 승인 record를 요구한다. 일반 위험 수용이나 package 전체 ignore로 대체할 수 없다.
6. 모든 finding을 보존한 결과에 blocking/exception-applied/nonblocking/unknown을 구분한다. matched exception이 있어도 raw finding count를 0으로 만들지 않는다. 필수 검사 미완료와 실제 finding 없음은 다른 결과다.
7. artifact/inventory/report/exception refs를 묶은 immutable attestation을 발행한다. SBOM, pins, actual inventory 및 advisory evidence의 서로 다른 subject가 섞이면 eligible 증거로 사용할 수 없다.

first-party source 등 advisory DB의 대상이 아닌 분류도 inventory에서 사라지지 않는다. 해당 분류의 source/provenance/review 등 필요한 증거와 적용 사유는 PolicySnapshot에 명시하며, scanner 제외 자체가 보안 합격 근거는 아니다.

## FL-R1-06 — Immutable evidence의 current gate 평가

**입력**: trusted scope/GateSpec, current subject facts, selected evidence heads, immutable attestations, current approvals/revocations, 명시적 평가 시각. **출력**: GateEvaluation 및 안전한 observation.

**증거 발행 경계**: R1R의 명시적 authoritative 검증 run은 해당 subject/gate/policy의 새 selectionRevision/attempt를 PENDING으로 먼저 기록한다. 완료 시 immutable attestation과 그 revision의 RESOLVED 선택을 일관되게 publish한다. 실패/오류도 결과로 기록하고 오래된 PASS head를 유지하는 이유로 삼지 않는다. 이전 attempt의 지연된 결과는 current head를 교체하지 못한다. 단순 preview/check와 R1C/local evaluator는 이 write 경로를 호출하지 않는다.

명시적 새 검증은 기준 head revision/검증 입력을 새 plan에 결속한다. 해당 검증의 retry/resume는 원 RunIntent와 예약된 selectionRevision을 유지하며, 현재 시각이나 process 재시작만으로 새 검증을 예약하지 않는다.

1. action/consumer/release의 trusted policy에서 required slots를 계산한다. 요청자가 gate를 줄여 eligibility를 만들 수 없다. local REM-1 G1 scope와 전체 release scope를 구분한다.
2. 각 slot의 authoritative EvidenceHeadSelection과 record를 확인한다. 가장 최근 시각의 기록 또는 pass인 기록을 임의 선택하지 않는다. 같은 binding의 head 충돌/미확인/PENDING 또는 head와 attestation revision 불일치는 결손으로 남긴다. 서로 다른 revision의 pointer와 record를 섞어 한 번의 관측인 것처럼 판정하지 않는다.
3. provenance/integrity, subject/target incarnation/state, policy/tool/coverage binding 및 validity를 검증한다. current facts를 얻을 수 없으면 역사적 PASS를 현재 PASS로 바꾸지 않는다. 오래된 기록은 history로 유지한다. CompatibilityManifest는 실제 artifact/role/schema/operation version 및 current writer epoch, registry 만족 상태, active binding/required capability/config와 대조한다. 지원되지 않는 조합은 BLOCKED, 확인 불가는 INCOMPLETE, 오래된 결속은 STALE이며 필수 module 누락을 silent skip으로 통과시키지 않는다.
4. slot별로 확인된 위반, missing/error/unknown, expired/mismatched/stale 사유를 모두 수집한다. N/A는 policy가 해당 scope에 명시한 applicability 이유가 있을 때만 가능하다.
5. verdict는 BLOCKED -> INCOMPLETE -> STALE -> ELIGIBLE_WITH_EXCEPTIONS -> ELIGIBLE 우선순위로 계산하되 다른 reason set도 지우지 않는다. 마지막 두 상태에서만 eligible=true다. 예외 목록/원 finding은 결과에 계속 표시한다.
6. 결과에 input refs/head revisions/current facts/evaluationTime을 결속해 재현 가능하게 한다. gate 판정 시 target/ledger/active outputs/approval을 수정하지 않는다.
7. local G1이 eligible이어도 후속 REM-2/3/4의 G2~G5 필수 evidence가 없으면 전체 release는 INCOMPLETE다. runtime admission/data-plane이 REM-1 daemon RPC를 기다리도록 재구성하지 않는다.

## FL-R1-07 — Interrupted effect의 재조정

1. 명시적 reconcile/resume 요청에서 동일 RunIntent와 마지막 durable EffectCheckpoint를 찾고 current observation 권한을 검증한다. assurance는 `domain-entities.md` §4.3을 따른다. 다른 intent/target/incarnation의 기록을 가져오지 않는다.
2. 이전 holder가 더는 effect를 commit할 수 없다는 fence 또는 quiescence를 확인한다. lease 만료/프로세스 부재만으로 외부 I/O 종료를 추정하지 않는다.
3. migration ledger/effect proof, publication head/candidate fingerprint 또는 해당 action의 authoritative receipt를 read-only로 대조한다.
4. 다음 분류를 적용한다. 외형이 비슷하거나 단순히 row가 없다는 이유로 결론을 만들지 않는다.

| 관측/증거 | 분류 | 다음 동작 |
|---|---|---|
| 정확한 effect key/identity/content/target의 commit 증거 및 일관된 postcondition | COMMITTED | receipt/checkpoint의 기존 사실을 기록. 같은 effect를 반복하지 않음 |
| 이전 실행이 fenced/quiescent이고 authoritative abort/no-effect 증거와 expectedBefore 일치 | NO_EFFECT_CONFIRMED | 같은 plan의 재개 후보. 새 mutation 전에 fresh 권한/조건 재확인 |
| 서로 충돌하는 ledger/head, mixed outputs, 변경된 target, 진행 중일 수 있는 I/O | UNKNOWN/CONFLICT | RECONCILE_REQUIRED 유지. 새 mutation/성공 판정 금지 |
| target/policy/artifact 의미가 새 scope로 바뀜 | PLAN_CHANGED | 새 plan/intent를 요구하고 기존 이력/효과를 보존 |

5. 관측/기존 사실 기록은 mutation 승인 갱신이 아니다. 만료된 승인으로 다음 step을 실행하지 않는다. 같은 intent에 대한 새 유효 승인 record는 가능하지만 target/plan 범위를 바꿀 수 없다.
6. resume는 새 명시 attempt이며 검증된 잔여 step부터 수행한다. daemon restart는 historical/effective status를 읽을 뿐 privileged 실행을 자동 재개하지 않는다.

## FL-R1-08 — R1C/CLI/startup/OBS의 관측 계약

- R1C는 허용 actor/scope의 immutable evidence 및 derived evaluation만 제공한다. evaluator 자체는 pure 판단이고 현재 사실은 권한 있는 readonly observation port로 얻는다. 해당 사실이 없으면 currentness를 확정하지 않는다.
- local startup/CLI는 같은 registry/policy/evidence/CompatibilityManifest 함수를 사용할 수 있다. service 생존, evidence 조회 가능성, 대상 artifact/schema eligibility를 서로 다른 필드로 표시한다. 살아 있는 daemon이 취약하거나 미완료인 artifact를 ready로 승격하지 않는다. readiness는 해당 role의 실제 필수 dependency를 bounded read-only probe하며 timeout/미확인은 UNKNOWN/unready로 표시한다.
- check/health/조회 요청이 ledger bootstrap, migration, binding activation 또는 dependency repair를 실행하지 않는다. 대상 부재/미초기화/읽기 실패를 안전한 사유로 구분한다.
- OBS는 timestamp/level/messageCode, service/role, plan/step/gate/run/subject의 안전한 식별자, trace/correlation, 단계별 duration 및 허용 reason code만 투영한다. raw SQL, credential/DSN, token, private input/PII, 내부 경로를 일반 로그/공개 오류에 삽입하지 않는다. 허용 ID 필드도 검증된 opaque 참조만 받으며 원 오류 문자열을 그대로 복사하지 않는다.
- 공통 phase 규약은 접수, queue 대기, 실행, 결과 전달 및 사용자 종단 완료를 분리한다. REM-1에 존재하지 않는 job/queue phase는 N/A로 두고 0초 완료를 꾸미지 않는다. 각 REM의 요청/성공/실패/권한 거부/불확정 effect/미완료·stale evidence 수와 지연·처리량·포화도를 기존 RES-5/7/11 관측/경보/COE에 연결한다. 공유 규약의 실제 service-local 계측과 dashboard/경보 배선은 각 unit 및 G4/G5에서 확인한다.
- intent/approval/effect/audit는 actor의 opaque 참조, 시각, 목적/대상, before/after fingerprint와 outcome을 추가 전용 또는 tamper-evident 경로로 기록한다. 일반 application role이 자기 감사 이력을 지우거나 바꾸지 못한다. auth failure/권한 거부·범위 확장 시도, unknown effect 및 dependency/backup/capacity 저하는 구분된 경보 신호다. 보존/라우팅 수치는 NFR에서 확정한다.
- critical intent/effect/approval evidence의 durable 기록이 준비되지 않으면 새 mutation을 시작하지 않는다. 일반 metrics 전송 실패는 target 성공을 실패/성공으로 재작성하는 근거가 아니며 별도 관측 오류로 남긴다.
- check/관측과 runner/scanner가 서로의 자원 pool을 무제한 점유하지 않도록 policy의 유한한 workload/input/dependency budget을 확인한다. capacity 부족은 명시적 busy/unavailable이며 privileged mutation 자동 queue/retry나 health의 긴 작업 대기로 바꾸지 않는다. 구체 상한/timeout/pool·회로 차단 배치는 NFR 단계다.
- 실행/검사 실패는 machine-readable non-success와 일반화된 진단으로 전달한다. 구체 CLI 숫자/HTTP error mapping 및 물리 logging 구현은 다음 설계 단계에서 정한다.

## Functional scenario 검증 표면

| 사례 | 기대 결과 | Flow / trace |
|---|---|---|
| ledger 없는 신규 target의 check | UNINITIALIZED 관측, target 변경 0 | FL-R1-01, F08 |
| basename만 같은 여러 registry 후보 | 자동 skip/apply 없음, reconciliation | FL-R1-02, F08 |
| 같은 ID의 SQL bytes 변경 | CHANGED_DEFINITION, 원 proof 보존 | FL-R1-01/03, F08 |
| N번째 atomic step 실패 | 앞선 verified 효과 유지, 현재 step rollback, 이후 미실행 | FL-R1-03, F08 |
| commit 후 receipt 유실 | 기존 commit 확인 후 기록 재조정, 재실행 없음 | FL-R1-07, RJ-AC12 |
| 생성 중 하나의 local ref/consumer 실패 | 전체 candidate 실패, published generation 비변경 | FL-R1-04, F13 |
| activation 후 확인 응답 유실 | head가 exact valid candidate인지 확인, blind remove/copy 금지 | FL-R1-04/07, F13 |
| scanner가 오류와 빈 finding 목록을 반환 | INCOMPLETE 또는 BLOCKED, clean 아님 | FL-R1-05/06, F06 |
| exact artifact 예외가 만료/범위 이탈 | 예외 미적용, 원 finding과 사유 유지 | FL-R1-05, F06 |
| local G1만 완료 | local 평가와 전체 release INCOMPLETE를 구분 | FL-R1-06/08, US-R4/5 |
| effect dispatch 전후 runner 중단 | UNKNOWN durable 기록 없이 실행 불가; dispatch 전 UNKNOWN 이후 중단도 재조정 | FL-R1-03/07, RJ-AC12 |
| 구 artifact와 미지원 schema/operation/writer 조합 | current compatibility 실패, module silent skip/이전 취약 handler fallback 없음 | FL-R1-06/08, F08/RJ-AC12 |
| 입력 한도 초과 또는 검사 pool 포화 | validation/busy 실패와 독립된 bounded health, target 변경 없음 | FL-R1-01/08, US-R4/5 |
| 과거 artifact의 성공 후 새 release를 판정 | 새 subject/closure/manifest의 필수 증거 없이는 INCOMPLETE/STALE, 과거 PASS 재사용 금지 | FL-R1-05/06, F06/F13 |
| 새 authoritative 재검사 실패/중단 또는 이전 attempt의 늦은 PASS | current slot은 실패 또는 INCOMPLETE; old PASS로 되돌리지 않음 | FL-R1-06, R1FD4 |

## Approved port에서 상세 모델로의 연결

| DAD1 port / contract | REM-1 상세 모델 및 flow |
|---|---|
| R1C.readEvidence / checkCompatibility | E-R1-21~24와 CompatibilityManifest, FL-R1-06/08. actor/scope는 인증된 호출 경계에서 검증 |
| R1R.verifyRegistry | E-R1-04~09, FL-R1-01/02; 조회는 metadata bootstrap을 포함하지 않음 |
| R1R.runApproved / MutationApproval / PlatformRunReceipt | E-R1-03/09~13의 approval/plan/run/attempt/checkpoint 및 FL-R1-03/07; generic receipt는 이 증거의 안전한 투영 |
| R1R.generateBindings / BindingEvidence | E-R1-14~17/21, FL-R1-04; generation/check와 승인된 activation의 capability 분리 |
| R1R.verifySupplyChain / SupplyChainEvidence | E-R1-18~21, FL-R1-05/06; current exception과 scope별 평가 |
| OBS.health / readiness / recordSignal | E-R1-24 및 FL-R1-08; 각 REM local instance와 실제 의존/trace를 연결 |

이 mapping은 기존 port의 목적을 세분화하며 다른 REM의 data ownership이나 public-job 범위를 바꾸지 않는다. REM-1 High 중요도, 중단 영향 및 upstream/downstream은 승인된 `unit-of-work.md`와 DAD1 §8.2~8.4를 계승한다.
