# REM-1 — Logical Components

**단계**: CONSTRUCTION / NFR Design
**상태**: 작성·검증 및 R1NDR1=A 승인 완료 (2026-09-20; `../../plans/rem-1-platform-integrity-nfr-design-plan.md`).
**입력**: R1ND1~R1ND9=A 및 승인 FD/NFR
**Companion**: `nfr-design-patterns.md`의 PAT-R1-01~12/VAL-R1-01~18, `../nfr-requirements/`의 NFR-R1/TD-R1/EV-R1

## 1. 구성 원칙

계획의 14개 후보 책임을 **17개 내부 컴포넌트**로 구체화한다. cache와 dependency guard, critical audit와 일반 관측을 분리하고 목적별 signing helper를 명시해 권한/실패 경계를 드러냈다. 배포 단위는 계속 REM-1이며 helper/relay는 동일 승인 artifact의 제한된 내부 실행 역할이다.

core는 typed value/port와 pure rule을 사용한다. C2 adapter는 Postgres, filesystem, process, authority, Keychain/TLS, clock 및 U6 연결을 제공하고 C3가 역할별로 필요한 capability만 주입한다. 동일 Python module을 import할 수 있다는 사실이 credential/DB/file 권한을 부여하지 않는다.

## 2. Component catalogue

| ID | Component / 실행 표면 | 책임과 보유 상태 | 경계 / Pattern |
|---|---|---|---|
| LC-R1-01 | EvidenceReadFacade / R1C | 요청 검증, 현재 observation 권한, 8+2 admission, 총 3s budget, 안전한 evidence/compatibility 응답 | target/control mutation 및 privileged signing 없음; PAT-R1-01/12 |
| LC-R1-02 | CurrentGateEvaluator / pure C1 | required slots와 exact inputs/current facts/clock window로 GateEvaluation 계산 | I/O/캐시/authority 발급 없음; PAT-R1-01/07/08/11/12 |
| LC-R1-03 | ControlStateRepository / C2 | run/attempt/checkpoint/approval/evidence/head/CAS 및 scope-bound transaction/read snapshot | 원 domain 권한의 owner가 아님. validated transition/proof만 저장; PAT-R1-01/03/09/11 |
| LC-R1-04 | TargetMutationExecutor / protected helper | dedicated target connection/session lock, durable epoch, validated SQL/ledger transaction 및 resource observation | exact target/plan action만 허용; per-step atomicity/current guard; PAT-R1-02/03 |
| LC-R1-05 | BundlePublicationCoordinator / protected helper | helper-owned sealed generation, filesystem BindingHead, expected revision/atomic replace/durability, reader/backup pin·GC 계약 | actual head 권위는 filesystem; arbitrary copy/exec 없음; PAT-R1-02/04/10 |
| LC-R1-06 | BootstrapJournal / 제한된 recovery adapter | framed canonical append, sequence/previous digest/witness, integrity scan 및 멱등 control import | 일반 DB 장애 fallback/SQL replay 없음; PAT-R1-05 |
| LC-R1-07 | RunSupervisor / one-shot R1R | 명시 invocation, host slot/holder, child·helper lifecycle, 합산 RSS/output/disk, deadline/cancel/reconcile | target/signing secret 없이 scoped helper 요청; daemon auto-resume 없음; PAT-R1-06 |
| LC-R1-08 | ImmutableValidationCache / R1C local | immutable parsing/integrity result의 accounted LRU, 최대 64 MiB | current grant/key trust/head/eligible 보관 금지; PAT-R1-07 |
| LC-R1-09 | DependencyReadGuard / readonly adapter wrapper | dependency+operation별 bounded retry와 CLOSED/OPEN/HALF_OPEN generation/ticket | write/replay/model/tool 실행을 probe로 사용하지 않음; PAT-R1-07 |
| LC-R1-10 | CurrentAuthorityAndTrustPorts / owner adapter | non-renewing authority, current trust/철회, scope-bound CommitGuard 및 bootstrap 목적의 검증 | U3/운영 authority를 대체하는 자체 user policy 없음; PAT-R1-02/12 |
| LC-R1-11 | ClockHealthProvider / protected read adapter | UTC uncertainty window, continuous elapsed/boot/resume context, 신뢰 근거/age | 다른 R1 current gate를 자기 clock의 신뢰 근거로 역호출하지 않음; PAT-R1-08 |
| LC-R1-12 | CriticalAuditWriterAndRelay / 제한된 write/relay 역할 | control Tx의 immutable audit/outbox, delivery cursor와 verified archive receipt | application self-delete 금지, 일반 telemetry와 별도 durable 계약; PAT-R1-09/10 |
| LC-R1-13 | ObservationAdapter / OBS local | redacted structured log/metrics/trace, readiness summary, heartbeat/IR/COE 연계 | 일반 append를 critical durability receipt로 반환하지 않음; PAT-R1-12 |
| LC-R1-14 | BackupRestoreCoordinator / 명시 maintenance | quiesced capture/cut/coverage/pin/archive 및 새 incarnation/current trust 복구 | 다른 domain은 owner snapshot 계약 사용; 무승인 repair/자동 resume 없음; PAT-R1-10 |
| LC-R1-15 | SchemaBindingPipeline / unprivileged tool role | offline catalog/consumer/export 및 staged/sealed candidate 검증, actual import/build/fixtures | privileged publication/key 접근 없음; PAT-R1-04/11 |
| LC-R1-16 | SupplyChainPipeline / verify-only tool role | frozen inventory/lock/image/SBOM, bounded scanner/report/feed evidence/예외 입력 검증 | 자동 dependency repair 또는 예외 승인 없음; PAT-R1-11 |
| LC-R1-17 | PurposeSigningHelper / protected helper module·entry | 허용 record-kind의 canonical payload/provenance 및 현재 key-purpose 아래 Ed25519 발행 | raw bytes-signing oracle가 아님; approval/evidence/head/backup 목적별 권한 분리; PAT-R1-02/12 |

## 3. Port 계약과 입력/출력

표의 이름은 논리 계약이다. 구체 transport/schema/SQL 정의는 이 의미를 보존해 Infrastructure/Code에서 매핑한다. raw JSON을 검증된 내부 capability type으로 바로 cast하지 않는다.

| Component | 주요 port / method | 결과 및 오류 의미 |
|---|---|---|
| LC-R1-01 | `readEvidence(actor, ref, budget)`; `checkCompatibility(actor, manifest, budget)` | SafeEvidence/GateEvaluation 또는 opaque Denied/Unavailable/Invalid. read가 새 scan/run을 만들지 않음 |
| LC-R1-02 | `evaluate(requiredSlots, snapshots, authorityFacts, clockWindow)` | 순수 GateEvaluation. 모든 reason/선택 revision/평가 context 보존 |
| LC-R1-03 | `openReadSnapshot(scope)`; `beginControlTransaction(commandContext)`; `reserveVerification`/`resolveVerification`; `appendCheckpoint`; `importJournalFrame` | typed revision/receipt. conflict/missing/durability unknown을 성공으로 만들지 않음 |
| LC-R1-04 | `observeTarget`/`acquireTargetSession`; `executeAtomicStep(checkedStep, commitGuard, checkpointProof)`; `inspectEffect` | TargetEffectReceipt/Observation. lost COMMIT reply는 UNKNOWN이며 blind retry 없음 |
| LC-R1-05 | `sealCandidate`; `readHead`/`pinGeneration`; `activate(sealedRef, expectedHead, guard, checkpointProof)`; `inspectActivation`; `collectUnreferenced` | generation/head/protection handle 또는 conflict/UNKNOWN. verified source set 외 쓰기 없음 |
| LC-R1-06 | `appendAndAcknowledge(frame)`; `inspectIntegrity(witness)`; `importVerifiedPrefix(controlTx)` | durable journal receipt 또는 torn/gap/unknown. import는 metadata만 변경 |
| LC-R1-07 | `startExplicit(intent, invocation)`; `dispatchScopedWork`; `cancelOwnAttempt`; `inspectAndReconcile` | attempt/child/holder/resource observations. 기존 source grant를 갱신하지 않음 |
| LC-R1-08 | `getVerifiedImmutable(cacheKey)`; `admit(entry, conservativeWeight)`; `invalidateNamespace` | immutable value 또는 miss. unknown weight/mutability는 no-admit |
| LC-R1-09 | `readWithinBudget(operation, budget)`; `tryHalfOpenProbe` | 실제 bounded read 결과 또는 unavailable. 호출별 breaker generation과 terminal classification |
| LC-R1-10 | `readCurrentAuthority`/`readCurrentTrust`; `enterCommitGuard(binding, nativeBoundary, budget)`; `verifyGuardBinding`; `observeRevocation` | fresh witness/guard 또는 Denied/Unknown/Unsupported. guard는 serialized revoke/effect 계약을 포함 |
| LC-R1-11 | `readClockContext`/`deriveUtcWindow`; `continuousElapsed` | trusted window 또는 time-quality reason. UTC proof 부재와 elapsed timer 사용을 구분 |
| LC-R1-12 | `appendCritical(tx, event)`; `enqueueDelivery(tx, eventRef)`; `relayBoundedBatch`; `confirmArchive` | durable receipt 또는 불확정/거부. relay ack는 원 audit 수정이 아님 |
| LC-R1-13 | `recordSafeSignal(context, signal)`; `projectHealth` | redacted signal/degraded delivery 상태. target의 committed 사실을 재작성하지 않음 |
| LC-R1-14 | `captureApprovedCut`; `verifyRemoteArchive`; `restoreAndInspect`; `releaseVerifiedPins` | BackupManifest/RestoreObservation 또는 incomplete/quarantine |
| LC-R1-15 | `validateCatalogAndConsumers`; `generateInactive`; `validateSealedSnapshot` | CandidateManifest/ValidationEvidence 또는 전체 실패. write 활성화는 LC-R1-05 책임 |
| LC-R1-16 | `inspectFrozenInventory`; `runBoundedScanners`; `normalizeVerifiedReports`; `evaluateExactExceptions` | coverage/findings/exception-applied/unknown을 구분한 VerificationEvidence |
| LC-R1-17 | `issueAllowedRecord(verifiedBinding, signingContext)` | SignedEnvelope 또는 Denied/KeyUnavailable/InvalidProvenance. 임의 payload 서명 없음 |

### 공유 계약의 핵심 필드

- **CommandContext**: actor/service identity, source authority/purpose, run/attempt, target/scope/incarnation, exact plan/artifact/policy, request correlation. 원 cookie/secret을 durable 작업 입력으로 저장하지 않는다.
- **BudgetContext**: 원 action/attempt monotonic deadline, input/output/RSS/disk budget, 남은 readonly retries, clock context와 승인/fence의 더 이른 경계. 하위 component가 새 전체 budget으로 reset하지 않는다.
- **CommitGuard**: source authority/revocation revision, exact effect/target/plan, target fence epoch, validity/deadline, native boundary 및 단일 finalization 증거. caller가 만든 struct나 저장된 signature만으로 발급하지 않는다.
- **CheckpointProof**: control transaction/journal의 durable UNKNOWN sequence/ref/hash와 해당 effect binding. durable receipt 없이 effect를 dispatch하지 않는다.
- **EffectObservation**: target/epoch/native receipt/current postcondition, evidence source와 관측 시각/품질. actual COMMITTED와 authorized/verified run completion을 별도 판정한다.
- **GenerationPin / BackupPin**: exact generation/manifest/reference closure와 보호 주체·기간/retirement 조건. protected existing lease/배포 registry로 제공하며 R1C가 새 metadata 파일/DDL을 생성하지 않는다.
- **SignedEnvelope**: PAT-R1-12의 kind/version/purpose/subject/policy/payload digest/provenance 및 kind별 validity. source bytes digest와 JCS metadata digest의 형식을 구분한다.

## 4. 실행 역할과 credential 경계

| 역할 | 허용 capability | 보유하지 않을 권한 |
|---|---|---|
| R1C reader | control/evidence/공개 verification material readonly, 자기 TLS identity, 안전한 OBS 제출 | target DDL/ledger/head 변경, approval/attestation signing key |
| R1R supervisor | scoped Run coordination, host admission/child 관측, bounded 작업 dispatch, 검증된 결과 기록 | target mutation/signing credential의 ambient 상속 |
| generator/validator/scanner | frozen 입력/허용 staging 및 필요한 scoped egress, bounded tool 실행 | active head/sealed bytes 수정, Keychain privileged key, 일반 DB write |
| target helper | exact approved target의 허용 step/ledger, 현재 guard/epoch 및 receipt | 임의 DSN/SQL/namespace, 다른 owner의 일반 data write |
| bundle helper | helper-owned seal, expected-head 전환 및 pin/GC 계약 | unvalidated tool 실행/부분 generation 공개 |
| signing helper | 허용 purpose/record-kind/key의 발행 및 provenance 검증 | caller가 고른 arbitrary bytes/issuer/key-purpose 서명 |
| audit append / relay | immutable event insert, delivery state 및 approved archive 확인 | app의 audit UPDATE/DELETE/DDL, 임의 retention 단축 |
| backup/retention | approved capture/cut/pin/restore/정리 | source owner의 무제한 mutation, old grant 자동 활성화 |

동일 binary의 코드 공유와 실제 권한 공유를 혼동하지 않는다. C3는 readonly/write/helper port의 서로 다른 view와 credential provider를 주입한다. OS UID/Keychain ACL/DB role/file owner가 실질적으로 분리돼야 한다. metadata coordination role은 임의 SUCCESS/evidence head를 raw CRUD로 설정할 수 없고 검증된 transition/proof 및 DB permission 경계를 따른다.

helper는 명시적 protected invocation의 작은 trusted code surface다. routine supervisor/tool 역할에서 arbitrary helper command나 `.env` 전체를 전달하지 않는다. 같은 native finalization 안에서 signature가 필요하면 live guard binding에 제한된 signing context를 사용하며, nested signing이 새로운 광범위 권한을 발급하거나 같은 lock을 역순 재취득하지 않는다.

## 5. Transaction·보호 경계와 순서

### 5.1 Control 및 target 조정

1. orchestrator는 LC-R1-03의 scoped control transaction handle을 열고 control change와 LC-R1-12의 critical event/outbox를 같은 handle에 기록한다. audit writer가 상위 orchestrator를 역호출하지 않는다.
2. checkpoint/audit durable acknowledgement 뒤 resource helper를 호출한다. helper는 exact checked input/current authority/native guard를 결합해 effect를 수행한다.
3. helper가 반환한 resource proof를 새 control transaction으로 기록한다. 두 commit 사이 실패는 UNKNOWN이며 분산 원자성을 주장하지 않는다.
4. observer/reconciler는 현재 observe 목적 권한으로 과거 사실을 기록할 수 있다. 이것이 만료된 mutation grant의 갱신이나 다음 step의 실행 허가는 아니다.

### 5.2 Exclusion과 revocation의 경합

| 경계 | 수명 / 순서 | 오류 처리 |
|---|---|---|
| host-heavy slot | child dispatch 전 claim, quiescence 증거 뒤 회수 | OS lock 해제만으로 stale holder를 삭제하지 않음 |
| target migration session lock / publication exclusion | 하나의 canonical target/scope; migration은 attempt의 physical connection 유지 | 새 writer의 취득 전 old I/O/epoch를 재조정 |
| finalization authority guard | expensive 준비 뒤, 실제 native effect 경계에 최대한 가깝게 취득 | revocation/expiry와 함께 선형화; 단순 stale snapshot은 거부 |
| short control/audit transaction | target 실행 전에 UNKNOWN 기록, 실행 뒤 result 기록 | 장시간 tool/네트워크/target lock 대기 중 control transaction을 열어 두지 않음 |
| generation reader/backup protection | exact immutable 참조를 사용 중인 동안 유지 | GC는 protection/quiescence 미확인 시 삭제하지 않음 |

기본 순서는 host admission -> target exclusion -> finalization guard -> native effect/receipt다. revocation은 새 guard를 즉시 막고 기존 finalizer의 종료/불확정을 추적한다. revoker가 guard를 잡은 채 상위 supervisor/target session lock을 역순 대기하는 구현은 허용하지 않는다. 장기 SQL 전체 동안 사용자 session/권한 row를 잠가 즉시 lifecycle 제어를 지연시키지 않는다.

guard를 source owner/native target과 결합할 수 없는 adapter는 readonly 진단만 가능하다. 권한 check와 commit 사이 경합을 줄였다는 이유로 atomic currentness를 주장하지 않는다. 필요한 source-side revoke/fence 참여는 G1 provider 인수의 필수 조건이며 REM-2 RK 구현을 기다리는 placeholder로 남기지 않는다.

### 5.3 Artifact pipeline의 권한 이동

- LC-R1-15/16은 frozen input으로 비권한 작업/검증 자료를 만든다. LC-R1-07이 resource budget과 실행 provenance를 관리한다.
- LC-R1-05의 helper-owned seal 뒤 LC-R1-15의 별도 unprivileged validator가 exact sealed digest를 검사할 수 있다. pipeline은 publisher/controller를 import하거나 privileged key로 생성물을 실행하지 않는다.
- LC-R1-17은 검증된 kind/subject/policy/producer 증거와 현재 발행 권한에 한해서 envelope를 발행한다. signing만으로 target effect 또는 active head가 생기지 않는다.
- LC-R1-05의 guarded activation과 LC-R1-03의 verification head CAS를 구분한다. late verifier/old binding receipt가 현재 head의 대체 권위가 될 수 없다.

## 6. Source/동기 의존 DAG

표는 상위 component가 직접 소비하는 하위 component다. C0 port/typed handle과 native C2 adapter는 별도 최하위 seam이며 이 표 밖의 역방향 service callback을 만들지 않는다.

| From | Direct dependencies |
|---|---|
| LC-R1-01 | LC-R1-02/03/08/09/10/11/13 |
| LC-R1-02 | 없음 (pure rules) |
| LC-R1-03 | 없음 (scoped SQL adapter/transaction port) |
| LC-R1-04 | LC-R1-03/06/10/11/17 |
| LC-R1-05 | LC-R1-03/06/10/11/17 |
| LC-R1-06 | LC-R1-10/11/17 |
| LC-R1-07 | LC-R1-03/04/05/06/09/10/11/12/13/14/15/16/17 |
| LC-R1-08 | 없음 (bounded immutable state) |
| LC-R1-09 | LC-R1-11 |
| LC-R1-10 | LC-R1-11 |
| LC-R1-11 | 없음 (protected host/time-source adapter) |
| LC-R1-12 | LC-R1-09/10/11 |
| LC-R1-13 | LC-R1-11 |
| LC-R1-14 | LC-R1-03/04/05/06/09/10/11/12/13/17 |
| LC-R1-15 | LC-R1-11/13 |
| LC-R1-16 | LC-R1-09/11/13 |
| LC-R1-17 | LC-R1-10/11 |

- BackupRestoreCoordinator는 주입된 scoped HostAdmissionPort를 사용하며 RunSupervisor를 역호출하지 않는다. 해당 port는 하위 resource adapter이며 supervisor/controller의 callback이 아니다.
- tool pipeline은 주입된 bounded ToolExecutionPort를 사용한다. LC-R1-07의 정책 facade를 재진입하지 않는다. authority adapter도 gateway/R1C를 역호출하지 않고 원 owner의 current port를 소비한다.
- control Tx handle 공유는 LC-R1-03과 LC-R1-12의 상호 service 호출이 아니다. outbox acknowledgement, resource receipt 및 revocation signal은 version/scope에 결속한 의도된 data feedback이다. 전체 비동기 데이터 흐름을 DAG라고 부르지 않는다.

## 7. Failure containment와 readiness

| 실패 | 외부 관측 / 내부 격리 |
|---|---|
| control DB/critical audit 불가 | 일반 새 mutation 거부, evidence currentness INCOMPLETE. 제한된 bootstrap 목적 외 local fallback 없음 |
| source authority/키 trust/ClockHealth 불가 | 해당 current 권한/eligibility 실패. cached grant/PASS 또는 plaintext/default key 사용 없음 |
| target session/commit 응답 유실 | Run/target UNKNOWN, actual lock/ledger/receipt/종료 확인까지 새 effect 보류 |
| child crash/RSS/disk/deadline 초과 | 새 dispatch 중지, scoped cancel/reap, host holder 및 외부 I/O 확인. R1C health는 별도 budget |
| BindingHead mismatch/내구성 불명확 | current filesystem head 관측 및 unready/UNKNOWN; DB receipt로 대체하지 않음 |
| breaker open | bounded unavailable 및 reason. half-open 대표 readonly probe 외 새 의존 호출 제한 |
| telemetry/relay 전송 장애 | critical 원장은 보존하고 backlog/운영 저하 기록. 과거 target effect의 사실은 유지 |
| FileVault/Keychain locked, restore incompleteness | unlock/현재 trust/새 incarnation 인수 전 mutation-ready 아님; privileged 자동 재개 없음 |

서비스 생존, 증거 서비스의 처리 가능성, subject gate는 별도 필드다. 최소 liveness와 보호된 상세 진단의 인증/노출 범위를 명시하며 TLS/현재 권한 실패를 관측 편의를 이유로 우회하지 않는다. clock 미신뢰는 로그의 time-quality로 표시할 수 있으나 current expiry 판정의 증거로 삼지 않는다.

## 8. Infrastructure/Code handoff와 proof obligations

| Capability | 필수 증명 / 담당 경계 | 검증 |
|---|---|---|
| dedicated session/epoch/authority commit guard | physical connection lifetime, canonical target lock, source revoke 참여, native finalization/time/fence, script atomic class 및 최소 role | VAL-R1-01~03/13, EV-R1-03/06 |
| filesystem sealed activation | protected roots/UID, no late writable descriptor 영향, same-filesystem atomic replace 및 directory durability, one-generation consumer pin | VAL-R1-05~07/15, EV-R1-04 |
| bootstrap journal | append-only access, framed bounds/hash chain, durability/floor witness, torn tail 격리 및 metadata-only import | VAL-R1-08/16, EV-R1-03/07 |
| host/child resource control | host singleton, durable holder/launch witness, boot/PID-start identity, child aggregate RSS/output, scoped cancel·orphan 확인 | VAL-R1-04/18, EV-R1-02 |
| protected clock | source health/offset·uncertainty/drift의 실제 근거, 30s age/±1s와 continuous elapsed/resume invalidation | VAL-R1-12, EV-R1-02/06/07 |
| Keychain/TLS/current authority | 목적별 key/UID/ACL/DB role, non-renewing source port, certificate validation/rotation/current trust, minimal environment | VAL-R1-02/10/13/16, EV-R1-06 |
| immutable cache/breaker | 64 MiB accounting, currentness 분리, generation/ticket 동시성, 3-failure/10s/single-probe 제어 | VAL-R1-10/11/18, EV-R1-02/09 |
| critical audit/outbox/retention | control Tx 결속, app self-delete 거부, relay/cursor 분리, 90일+ 및 참조·archive 검증 | VAL-R1-09/15, EV-R1-06/07 |
| consistent backup/restore | quiesced R1 writers, owner snapshot 계약, exact cut/coverage/pin, encrypted remote 회수/restore, 신뢰 floor 및 새 incarnation | VAL-R1-14~16, EV-R1-07 |
| actual contract/SCA pipeline | 전체 local ref/consumer/visibility, frozen closure/provenance/coverage/예외 및 현재 verification CAS | VAL-R1-05/17/18, EV-R1-01/04/05 |

Infrastructure는 실제 package path/launchd role/OS UID/port/Keychain/CA/volume/off-host destination 및 운영 window를 매핑한다. 제공할 수 없는 capability를 Boolean 설정이나 mock 성공으로 ready 처리하지 않는다. G1에 필요한 최소 authority/guard/consumer provider는 함께 구현·검증하며 후속 REM primary라는 이유로 생략하지 않는다.

Code 계획은 C0 계약/codec -> pure rule/상태 model -> C2 실제 adapter -> 역할별 C3 composition 및 F06/F08/F13 회귀 순서로 패턴/컴포넌트/VAL/EV/PROP를 연결한다. Hypothesis/fast-check의 선정된 PR/release/nightly profile, 실제 isolated integration 및 월간/변경 시 restore를 유지한다. REM-1 local G1 뒤의 US-R4/5/RJ-AC12 최종 통합은 후속 REM 및 G4/G5에서 확인한다.

## 9. 결정 추적성

| 선택 | 주 component | Pattern / 인수 |
|---|---|---|
| R1ND1=A | LC-R1-03/04/10/11/12 | PAT-R1-02/03, EV-R1-03/06 |
| R1ND2=A | LC-R1-05/07/10/15/17 | PAT-R1-04, EV-R1-01/04 |
| R1ND3=A | LC-R1-03/06/10/12 | PAT-R1-05, EV-R1-03/07 |
| R1ND4=A | LC-R1-01/07/09/10/11/13 | PAT-R1-06, EV-R1-02/03/09 |
| R1ND5=A | LC-R1-01/02/08/09/10/11 | PAT-R1-07, EV-R1-02/05/09 |
| R1ND6=A | LC-R1-04/05/10/17 | PAT-R1-02/12, EV-R1-06 |
| R1ND7=A | LC-R1-02/07/10/11 | PAT-R1-08, EV-R1-02/06/07 |
| R1ND8=A | LC-R1-03/06/12/13 | PAT-R1-09, EV-R1-06/07/09 |
| R1ND9=A | LC-R1-03~07/10~14/17 | PAT-R1-10, EV-R1-07/09 |

24개 NFR 및 40개 확장 규칙의 설계 연결은 `nfr-design-patterns.md`에 있다. 이 문서의 component/DAG/port는 실제 배포나 권한·내구성 인수 완료의 증거가 아니다. 두 NFR Design 산출물 승인 후 Infrastructure Design으로 진행한다.
