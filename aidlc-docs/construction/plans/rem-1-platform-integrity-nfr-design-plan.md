# REM-1 Platform Integrity — NFR Design 계획

**단계**: CONSTRUCTION -> NFR Design
**유닛**: `rem-1-platform-integrity` (REM-1)
**일자**: 2026-09-19
**상태**: 두 NFR Design 산출물 작성·검증 및 R1NDR1=A 승인 완료 (2026-09-20)
**입력 승인**: R1NFRR1=A, R1NFR1~13=A, R1FDR1=A, UGR1=A, DAD1=A, WPR2=A

이 단계는 승인된 NFR을 충족할 **패턴·논리 컴포넌트·권한/내구성 경계**를 결정한다. 기존 NFR 수치/stack을 계승하며 아래 R1ND1~9는 모두 A가 선택됐다. 실제 port/UID/Keychain ACL/volume/CA/off-host destination 및 launchd 설정은 Infrastructure Design에서 매핑한다.

## 1. 승인 입력과 코드 근거

- `../rem-1-platform-integrity/nfr-requirements/nfr-requirements.md`: NFR-R1-01~24, EV-R1-01~09, 29개 capacity/input/deadline 값 및 보존/복구/PBT profile.
- `../rem-1-platform-integrity/nfr-requirements/tech-stack-decisions.md`: TD-R1-01~17, independent release, Postgres/files/journal, crypto/role, SCA, OBS/backup 및 framework.
- `../rem-1-platform-integrity/functional-design/`: E-R1-01~24, FL-R1-01~08, BR-R1-01~22, PROP-R1-01~16과 상태/assurance/unknown-effect 의미.
- DAD1의 R1C/R1R/OBS, current authority 및 C3 -> C2/C1/C0 의존 방향, WPR2 G0~G5와 UGR1 local/전체 인수 구분을 계승한다.

다음은 source read로 확인한 구현 seam이다. 기존 코드의 실제 배포 설정 또는 새 패턴의 검증 합격을 뜻하지 않는다. 아래 코드 경로는 workspace root 기준이다.

| Seam | 확인한 코드 | 설계 연결 |
|---|---|---|
| migration transaction | `backend/migrations/__init__.py:43-69`는 한 connection에서 script+ledger를 step별 commit하지만 명시 target lock/fence 계약이 없음 | R1ND1: connection 수명/직렬화/epoch 및 current-authority commit 경계 |
| migration read | 같은 파일 `74-83`은 pending 조회에도 tracking DDL/commit 수행 | 관측 adapter와 mutation executor capability 분리 |
| Postgres lock 선례 | `backend/modules/summarization/src/summarization/adapters/rds_glossary.py:61-67`의 per-user transaction advisory lock | lock 사용 선례는 있으나 whole-attempt/복구 fencing 증거를 대신하지 않음 |
| bundle publication | `shared/python/tools/generate.py:107-116`은 old tree 제거 후 copy | R1ND2: complete-generation head와 consumer pin, crash reconciliation |
| tool process | 같은 파일 `60-95`는 subprocess capture를 사용하고 명시 deadline/process-group/resource guard가 없음 | R1ND4: runner supervisor, bounded output/cancel 및 자식 합산 |
| 기존 DB pool | `backend/db.py:31-49`의 10+20 connection/3s acquire 및 환경 기반 pool 전환 | R1C 8+2/총 3s 예산에 맞는 전용 bulkhead/pool 필요 |
| session authority | `backend/modules/accounts/services/session_manager.py:49-99`는 verify 중 last_active_at을 갱신·저장하고 보관된 role/MFA를 복원 | runner/background 검증에는 source grant를 갱신하지 않는 current-authority port 필요 |
| observability/audit | `ops/src/docsuri_ops/observability.py:113-125`의 append_audit는 optional; `ports.py:19-21`은 일반 append 계약 | R1ND8: critical durable receipt와 일반 telemetry 계약 분리 |
| local event store | `ops/src/docsuri_ops/adapters/local.py:20-36`의 audit는 memory list | interface 이름만으로 90일 감사/내구성/self-delete 보호를 충족했다고 판단하지 않음 |

## 2. 고정 제약과 설계 범위

1. R1C는 read-only evidence/compatibility, R1R은 명시적 verify/mutation이다. health/startup/restart가 privileged action을 시작하지 않는다. control realm 최초 bootstrap/recovery 이외의 일반 DB outage에는 local journal write fallback이 없다.
2. R1C 조회 8개+독립 health 2개, R1R host-heavy lane 1개, 512 MiB/2 GiB RSS와 `free >= 10 GiB + 2 × estimated additional peak`를 유지한다. process 수로 상한을 곱하거나 기존 host workload의 여유를 독점했다고 가정하지 않는다.
3. 관측 총 3s, DB connect/read 1s/2s, read-only network의 최대 2회 추가 retry, codegen/scanner 10분/15분, migration lock/step/attempt 5s/5분/30분을 유지한다. 승인/source grant/fence의 더 이른 deadline이 우선한다.
4. step effect+target ledger는 원자 commit한다. control DB/파일/target 사이에 분산 transaction이 있다고 가정하지 않는다. lease/PID 부재/timeout만으로 no-effect/quiescence를 증명하지 않는다.
5. 현재 권한 검증과 effect의 보호 경계를 명시한다. effect 전 조회만 하고 revocation/epoch 변경을 무시하는 TOCTOU는 허용하지 않는다. 각 adapter는 guard의 선형화 지점과 revoke/cancel/expiry 경쟁을 입증해야 한다.
6. U3/승인된 운영 authority가 caller 권한을 소유한다. runner의 background/retry 검증은 session의 idle/absolute lifetime을 늘리지 않는다. mTLS service identity, 저장된 승인 또는 signature는 현재 caller 권한을 대체하지 않는다.
7. SHA-256/JCS/Ed25519, Keychain, TLS 1.2+/mTLS, FileVault와 operator preboot unlock은 확정이다. R1C transport key와 privileged signing/mutation key를 구분한다.
8. signed record-kind/schema/purpose/subject/policy 결속, safe I-JSON/lossless identity codec, trust-key rotation/revocation 및 clock 불확정 처리를 설계한다. 알 수 없는 clock/key/current head는 current eligibility가 아니다.
9. wire는 schema-generated이며 view adapter를 검증한다. codegen resolver는 offline이다. SCA 도구의 allowlisted network/현재 advisory snapshot과 분리된 capability로 다룬다.
10. immutable candidate를 모두 검증/봉인한 후 activate하고 consumer는 complete generation에 pin한다. current active head의 권위는 하나다. 파일과 DB가 다른 것을 가리키면 PASS를 임의 선택하지 않는다.
11. critical audit/증거는 최소 90일, 일반 log/metrics 14일, 미참조 실패 candidate 7일이며 active/unresolved/현재 target 증거의 참조가 우선한다. application role의 자기 감사 수정/삭제를 금지한다.
12. RPO ≤24h/RTO ≤4h, 정상 host/dependency 조건의 daemon readiness 60s를 유지한다. backup/restore는 새 incarnation/current 권한/unknown run을 검증하고 privileged run을 자동 재개하지 않는다.
13. 기존 GitHub review/git-flow, versioned 수동 전환/호환 rollback, 경량 IR/COE 및 R1NFR13=A의 CI/월간·변경 시 격리 restore를 계승한다. RESILIENCY-04/14/15의 이미 답변한 과정/주기를 다시 묻지 않는다.
14. logical component는 R1C/R1R/OBS 내부 모듈/port/보호된 실행 역할이다. 새 REM service나 사용자 job API를 추가하지 않고 REM-2 RK의 선행 구현을 요구하지 않는다.

## 3. 질문 범주 평가

| 필수 범주 | 적용 근거 | 해당 질문 |
|---|---|---|
| Resilience Patterns | effect/receipt 불확정, control bootstrap, 취소/중단, critical audit 및 consistent restore | R1ND1/3/4/8/9 |
| Scalability Patterns | host-heavy singleton, 8+2 bulkhead, 합산 RSS/disk 및 bounded cache | R1ND4/5 |
| Performance Patterns | 250ms/100ms 목표와 총 3s 안의 immutable parsing/current reads, dependency failure | R1ND4/5/7 |
| Security Patterns | source-grant 비연장, key/DB 권한 분리, 현재 revoke/expiry/clock 및 audit 변조 방지 | R1ND1/6/7/8 |
| Logical Components | target guard, content/head, bootstrap journal, supervisor, authority adapter, audit/restore coordinator | R1ND1~9 |

다섯 범주는 모두 적용한다. 기존 수치/framework/boot 정책은 위 고정 입력이며 질문은 남은 패턴 차이에 한정한다.

## 4. 패턴 결정 질문

### R1ND1 - Migration의 target 직렬화와 connection 수명

step별 원자성은 확정됐다. 여러 step 및 process 중단에 걸친 target exclusion을 어떤 패턴으로 제공할까?

A) **전용 connection의 session advisory lock + durable fence epoch**. attempt 동안 target-scoped lock을 같은 physical connection에 유지하고 step마다 별도 transaction으로 effect+ledger를 commit한다. lock을 보유한 connection을 다른 요청에 반환하거나 transaction-pooling으로 교체하지 않는다. current permit/epoch/deadline을 effect 경계에서 확인한다. connection/commit 확인이 끊기면 UNKNOWN이며 target의 lock/실제 종료를 확인하기 전 다음 writer를 허용하지 않는다. (권장)

B) **target mutex row의 transaction lock + durable fence epoch**. 각 step에서 명시 mutex row를 잠그고 current permit/epoch와 effect+ledger를 같은 transaction에서 검증한다. step 사이에는 lock을 풀되 다음 step에서 전체 현재 조건/이력을 재검증한다. bootstrap mutex 생성과 다른 attempt의 끼어듦도 명시적으로 처리한다.

두 안 모두 lock만으로 source 권한을 증명하지 않으며 R1ND6의 current-authority guard를 결합한다. lock 범위는 alias/겹치는 namespace를 검증한 physical target에 매핑하고, 5s lock 예산을 지킨다. 이 protocol 밖 writer가 남아 있으면 target exclusion을 완료로 선언하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 lock/epoch/step transaction 및 old-holder 처리 패턴을 기술)

[Answer]: A

### R1ND2 - Binding activation의 authoritative head

검증된 immutable generation은 파일에 저장한다. 어떤 단일 head를 consumer와 reconciliation의 권위로 사용할까?

A) **filesystem head + generation pin**. candidate files/manifest와 필요한 directory durability를 확인한 뒤 publication lock/expected-head guard 아래 하나의 head record를 atomic replace한다. consumer는 build/start 시 head를 한 번 해소해 exact immutable generation 경로/manifest에 pin한다. control DB의 receipt/index는 그 실제 head를 대조하는 기록이며 별도 competing active head가 아니다. (권장)

B) **Postgres head + generation pin**. files/manifest를 먼저 durable하게 봉인한 뒤 control DB의 head를 expected revision 조건으로 transaction 변경한다. 정상 activation/새 head 선택은 control DB 가용성을 요구하고 consumer는 해소된 generation을 pin한다. 파일의 current link는 파생 projection이며 권위가 아니다.

어느 안도 여러 output path를 순차 copy한 상태를 정상본으로 노출하지 않는다. 같은 build/import 중 current link를 다시 따라가 서로 다른 generation을 섞지 않는다. 이미 frozen release의 local 검증과 일반 live promotion을 구분하고, 최초 control bootstrap에 live R1C 의존을 추가하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 단일 head, consumer pin, durability 및 crash 판정 경계를 기술)

[Answer]: A

### R1ND3 - 제한된 bootstrap/recovery journal의 표현

control realm이 아직 없거나 명시 복구 중일 때 사용하는 local journal을 어떤 방식으로 구성할까?

A) **append-only framed log**. canonical record에 sequence/previous digest/intent·attempt·target·plan 및 assurance를 결속하고 append+durability 확인 후 다음 단계로 간다. torn tail/중간 유실/서명·hash 불일치는 보존·격리하고 target 증거로 재조정한다. control 복원 후 sequence/digest를 멱등하게 편입한다. (권장)

B) **immutable checkpoint files**. 각 sequence를 독립 canonical file로 temp-write/durable-flush/atomic-rename하고 manifest로 연결한다. 완전히 확정된 record와 미확정 임시물을 구분하며 manifest/reference 검증 후 control DB로 멱등 편입한다. 작은 파일/manifest 관리량이 늘어난다.

공통으로 첫 effect를 열기 전 UNKNOWN checkpoint가 durable해야 한다. journal import는 metadata/증거 복원이며 저장된 명령을 자동 재실행하지 않는다. 일반 apply의 control-store 장애 fallback이나 감사 self-delete 경로로 사용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 torn write/검증/편입/권한 분리를 만족하는 journal 패턴을 기술)

[Answer]: A

### R1ND4 - Resource/deadline supervisor와 heavy lane

승인된 동시성/RSS/disk/deadline을 어떤 실행 경계에서 집행할까?

A) **one-shot RunSupervisor + 격리된 child roles**. 명시 호출이 host-wide admission을 얻고 process group/작업 디렉터리/입출력 한도와 deadline을 관리한다. tool-local 한도와 합산 RSS/disk 관측을 결합하고, 취소 후 child 및 실제 target I/O를 재조정한다. privileged executor는 R1ND6의 별도 권한 경계로 호출한다. (권장)

B) **고정 launchd one-shot role jobs + 외부 admission coordinator**. 명시 호출은 허용된 role job에 exact run/plan을 전달하고 coordinator가 host-heavy lane과 deadline/resource 상태를 관리한다. role job 자체도 남은 예산/권한을 검증한다. privileged job에 자동 KeepAlive/restart를 두지 않는다.

두 안 모두 R1C의 8개 조회/2개 health bulkhead와 dependency pool을 분리한다. host slot의 해제/프로세스 부재는 target quiescence 증거가 아니다. orphan child 또는 DB I/O가 남을 수 있으면 slot/fence를 안전하게 회수했다고 추정하지 않는다. concrete launchd/OS limit 배치는 Infrastructure에서 검증한다.

X) 기타 (아래 `[Answer]:` 뒤에 admission/child 취소/합산 자원/실제 quiescence 집행 위치를 기술)

[Answer]: A

### R1ND5 - Read path의 cache와 circuit breaker

current 권한/target/head를 유지하면서 parsing/검증 비용과 dependency 장애를 어떻게 격리할까?

A) **bounded immutable cache + fail-closed breaker**. content digest/schema/tool/policy에 결속한 immutable parsing·무결성 자료만 byte-budgeted LRU에 둔다. cache는 daemon RSS 안에서 최대 64 MiB이며 안전한 accounting/immutability를 증명하지 못하는 항목은 보관하지 않는다. dependency+operation별 최종 read 실패 3회 연속 시 10s open, half-open은 readonly probe 1개만 허용한다. (권장)

B) **stateless 검증 + timeout/bulkhead**. persistent process cache와 circuit breaker를 두지 않고 요청마다 필요한 immutable 자료를 검증한다. 동일한 8+2/총 3s budget 및 overload 거부로 의존 장애를 제한하며, 5 requests/s·p95 목표를 실제로 입증한다.

공통으로 current grant/revocation/selected head/target 사실이나 최종 eligible verdict를 오래된 cache로 대체하지 않는다. head와 record는 coherent snapshot/revision으로 결속한다. A의 breaker open은 UNKNOWN/unavailable이며 stale 권한 fallback이 아니다. 권한 거부/입력 오류를 availability 실패로 세지 않고 half-open 실패는 다시 open, 대표 readonly 성공은 closed로 전이한다. mutation을 breaker probe/retry로 실행하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 cache 대상/한도/currentness 및 dependency 장애 패턴을 기술)

[Answer]: A

### R1ND6 - Privileged 권한과 current-authority guard의 실행 경계

Keychain/TLS와 목적별 role 분리는 확정됐다. signing/target mutation 권한을 어디에 집중할까?

A) **좁은 purpose executor/helper**. 일반 supervisor·generator·scanner는 privileged secret을 받지 않고, 명시적으로 호출된 보호된 helper가 허용된 record-kind/target/plan만 서명·적용한다. helper는 현재 authority/approval/deadline와 target fence를 effect 경계에 결합하고 revoke/commit 경쟁을 같은 guard protocol로 조정한다. arbitrary bytes signing/임의 SQL·path 실행 API는 제공하지 않는다. (권장)

B) **별도 privileged role entry**. migration/publish/sign 각각의 CLI entry가 자기 OS/Keychain/DB role로 실행되고 동일한 current-authority/commit guard를 내부에 둔다. 일반 generator/scanner는 이 entry의 process/credential을 공유하지 않는다. helper IPC는 줄지만 각 privileged entry의 trusted code/공통 검증 경계를 관리해야 한다.

두 안 모두 기존 U3/운영 authority의 non-renewing projection을 사용한다. background/retry 검증이 `SessionManager.verify`의 sliding refresh를 호출해 source grant를 유지시키면 안 된다. ordinary operator와 제한된 bootstrap System 목적을 구분한다. source authority가 target commit/revocation protocol을 제공하지 못하면 별도 현재 증명 없이 mutation을 ready로 표시하지 않는다. routine key rotation은 새 verification key 배포 -> 명시 signing 전환 -> 기존 signing 종료로 설계하며 compromise는 즉시 current trust에서 철회한다.

X) 기타 (아래 `[Answer]:` 뒤에 secret custody, 현재 권한의 선형화/철회 및 bootstrap 경계를 기술)

[Answer]: A

### R1ND7 - Trusted clock window와 freshness profile

expiry를 정확히 집행하려면 시간의 신뢰/오차도 명시해야 한다. host clock-health adapter와 monotonic/boot context로 어떤 초기 window를 허용할까?

A) **짧은 clock-health window**. 보호된 clock-health 관측은 최대 30s age, 보수적으로 계산한 현재 UTC uncertainty는 최대 ±1s일 때만 시간 의존 판정에 사용한다. boot/sleep-resume/clock discontinuity 또는 신뢰 상태 상실 시 재관측 전까지 time-dependent eligibility를 보류한다. (권장)

B) **넓은 clock-health window**. 같은 방식에서 관측 age를 최대 5분, UTC uncertainty를 최대 ±5s로 둔다. 외부 동기화 관측의 일시 지연을 더 허용하지만 만료 근처 보수적 거부 범위도 커진다.

어느 안도 오차를 expiry grace로 더하지 않는다. 승인 허용은 시간 window 전체가 유효 구간 안에 있을 때만 가능하고, deadline은 가장 이른 보수적 경계를 사용한다. 단순 wall clock 두 번 읽기나 동일 host Postgres 시각을 독립된 시간 증명으로 취급하지 않는다. 실제 sync-health/불확실성 근거와 suspend 감지는 Infrastructure/인수에서 입증하며 unavailable이면 fail closed한다. 이 clock cache가 caller/key revocation cache를 허용하는 것은 아니다.

X) 기타 (아래 `[Answer]:` 뒤에 신뢰 시간의 source/uncertainty/age 및 jump/restore 처리 조건을 기술)

[Answer]: A

### R1ND8 - Critical audit의 durable 경계

현재의 일반 telemetry API와 별도로 어떤 경계에서 critical 기록의 durable receipt를 만들까?

A) **Postgres critical audit + transactional outbox**. control 변경/중요 intent와 감사 레코드를 같은 transaction에 넣고 일반 application에는 필요한 insert/read만 부여한다. 별도 relay/retention role이 U6/암호화 archive로 전달한다. target effect가 다른 저장소이면 사전 UNKNOWN과 사후 receipt로 연결한다. bootstrap audit는 R1ND3 journal에서 검증 편입한다. (권장)

B) **분리된 local append-only recorder**. 보호된 recorder 역할이 structured critical event를 검증·durable 기록하고 receipt를 반환한다. 일반 app는 수정/삭제 권한을 갖지 않는다. control/target commit과 recorder 사이에는 분산 원자성을 가정하지 않고 intent/receipt/reconcile을 사용한다. recorder가 확인되지 않으면 새 mutation을 막는다.

두 안 모두 일반 metric/trace 전송 실패와 critical 기록 불능을 구분한다. optional `append_audit` 또는 memory list append를 durable receipt로 취급하지 않는다. 90일+ 및 active/unresolved 보존, 비식별·비노출, archive 확인 후 별도 cleanup 권한을 유지한다. 이는 OBS/REM-1 내부 역할이며 별도 REM service가 아니다.

X) 기타 (아래 `[Answer]:` 뒤에 durable acknowledgement, self-delete 방지, outbox/복구/보존 패턴을 기술)

[Answer]: A

### R1ND9 - 여러 저장소의 backup cut과 restore 순서

Postgres/control/target ledger와 file bundle/journal을 어떤 consistency 경계로 묶을까?

A) **REM-1 writer-quiesced backup window**. R1R 신규 write/promotion을 잠시 막고 관련 writer의 quiescence를 확인한다. 효과 결과가 아직 확정되지 않은 항목은 UNKNOWN 이력으로 보존한다. stable head/참조 집합, DB cut, 파일/journal의 hash/coverage를 backup manifest로 묶는다. writer 정지를 증명하지 못하면 일관된 capture로 완료하지 않는다. R1C 진단은 가능한 범위에서 유지하며 capture 뒤 정상 admission을 재개한다. (권장)

B) **짧은 cut barrier + online snapshot/pin**. cut을 잡는 짧은 barrier 뒤 DB snapshot과 exact head/referenced generation을 pin하고 writer를 재개한다. 복사 중 GC가 pinned 참조를 지우지 못하게 하며 모든 저장소가 같은 logical cut 또는 검증 가능한 replay 경계를 갖는지 입증한다. coordinator/참조 수명 관리가 더 복잡하다.

어느 안도 다른 domain의 모든 업무 writer를 임의로 정지시키지 않는다. 필요한 target ledger/domain snapshot은 원 owner 계약으로 조정하고 참여하지 않는 writer/누락된 cut을 숨기지 않는다. restore는 FileVault/키 -> control/journal/참조 복원 -> 새 incarnation/current authority -> UNKNOWN 재조정 -> 명시 재개 순서를 검증한다. 원격본 회수/실제 restore와 RPO/RTO를 확인하며 off-host provider와 volume 경로는 Infrastructure에서 확정한다.

X) 기타 (아래 `[Answer]:` 뒤에 consistent cut, 미확정 effect, 참조 pin/GC 및 restore 순서를 기술)

[Answer]: A

## 5. 답변 후 구체화할 logical component 후보

아래는 내부 역할/port 후보이며 새 독립 service 목록이 아니다. 선택에 따라 책임/구현 경계를 확정한다.

| 후보 | 책임 / 결합할 패턴 | 경계 |
|---|---|---|
| EvidenceReadFacade | R1C 입력/현재 권한/총 deadline/안전한 응답 | readonly; 8+2 bulkhead |
| CurrentGateEvaluator | required slots/assurance/current facts/clock window의 pure 판정 | caller/subject/policy 결속; cached eligible 없음 |
| ControlStateRepository | Postgres plan/run/checkpoint/approval/evidence/head의 transaction/CAS | immutable record와 mutable head/lease를 구분 |
| TargetMutationExecutor | target lock/epoch/current permit 및 step effect+ledger | R1ND1/6; 각 domain-owned target capability |
| BundlePublicationCoordinator | staged -> validated/sealed -> active head 및 consumer pin | R1ND2; authoritative head 하나 |
| BootstrapJournal | 제한된 offline control bootstrap/recovery 기록 및 검증 편입 | R1ND3; 일반 outage fallback 없음 |
| RunSupervisor | host lane, child/output/RSS/disk/deadline 및 cancel/reconcile | R1ND4; orphan I/O 확인 |
| VerifiedObjectCache / DependencyReadGuard | immutable parsing cache와 bounded dependency failure | R1ND5; current authority와 분리 |
| CurrentAuthorityAndTrustPorts | U3/운영 authority, revoke/key/purpose/target guard | R1ND6; non-renewing 검사 |
| ClockHealthProvider | 보수적 UTC window, monotonic/boot/resume 신뢰 | R1ND7; uncertainty/age 및 expiry 비확대 |
| CriticalAuditWriter / ObservationAdapter | durable critical path 및 별도 best-effort telemetry/IR/COE | R1ND8; self-delete 금지 |
| BackupRestoreCoordinator | cut/coverage/pin/암호화/원격 회수/새 incarnation 재조정 | R1ND9; 다른 owner의 데이터 권위 보존 |
| SchemaBindingPipeline | offline closure, 실제 Python/TS consumer 및 fixture 검증 | TD-R1-05; generator 권한/네트워크 격리 |
| SupplyChainPipeline | frozen inventory, 도구/report/DB provenance와 exact exception | TD-R1-10; opaque artifact refs, bounded network |

그 밖에 signed-envelope의 canonical codec/purpose binding, monotonic head revision, key rotation/revocation, safe error/CLI mapping, warning/health 신호 및 cleanup 참조 계산을 명세한다. control metadata와 critical audit의 transaction, filesystem 실제 효과와 PG 결과 기록의 간격을 숨기지 않는다.

## 6. 질문-인수 및 property 연결

| 질문 | NFR / 기술 입력 | 기존 property / 실제 검증 |
|---|---|---|
| R1ND1 | NFR-R1-02/03/08/10; TD-R1-03 | PROP-R1-05~08; EV-R1-03/06 |
| R1ND2 | NFR-R1-01/02/18; TD-R1-04/05 | PROP-R1-10~12/15; EV-R1-01/04 |
| R1ND3 | NFR-R1-02/03/16/20; TD-R1-04 | PROP-R1-01/06~08; EV-R1-03/07 |
| R1ND4 | NFR-R1-04~08/19; TD-R1-06/11/17 | PROP-R1-04/07/08/16; EV-R1-02/03/09 |
| R1ND5 | NFR-R1-07~10/19; TD-R1-06/11 | PROP-R1-04/14~16; EV-R1-02/05/09 |
| R1ND6 | NFR-R1-10~13/20; TD-R1-07/08 | PROP-R1-01/07/08/14~16; EV-R1-06 |
| R1ND7 | NFR-R1-08~11/15; TD-R1-06/08 | PROP-R1-07/14~16; EV-R1-02/06/07 |
| R1ND8 | NFR-R1-14/19/20; TD-R1-11/12 | PROP-R1-01/08/16; EV-R1-06/07/09 |
| R1ND9 | NFR-R1-12/14~16/22; TD-R1-09/13 | PROP-R1-06~08/12/15; EV-R1-07/09 |

답변 분석은 head 단일 권위/consumer pin, journal/control/audit 복구, supervisor/helper 역할과 실제 quiescence, cache/clock/current 권한, backup-cut/pin/GC 간 조합을 대조한다. 증명되지 않은 보장을 성공으로 표시하는 조합은 clarification 후 진행한다.

## 7. 산출물 및 확장 적용

답변 검증 후 다음 두 파일을 생성한다.

1. `aidlc-docs/construction/rem-1-platform-integrity/nfr-design/nfr-design-patterns.md`: 선택한 패턴, 단계/선형화/실패·취소·복구 의미, NFR/EV/property trace, key/clock/authority/audit 및 per-rule 확장 준수.
2. `aidlc-docs/construction/rem-1-platform-integrity/nfr-design/logical-components.md`: 책임/port/input/output/state/권한, source/sync 의존, budget 및 composition/실행 역할·Infrastructure handoff.

Security Full과 custom single-Mac Resiliency를 유지한다. SECURITY-01/03/05~15 및 RESILIENCY-01~07/09~15의 적용 패턴을 대조하며, 신규 external intermediary/HTML 부재에 따른 SECURITY-02/04와 승인된 RESILIENCY-08 예외는 사유를 기록한다. RESILIENCY-09는 bounded local capacity 대체다.

PBT 상세 규칙의 stage table에는 NFR Design 실행 검증이 없으므로 PBT-01~10은 이 단계 실행 기준 N/A다. Full 요구, 선정된 Hypothesis/fast-check와 PROP-R1-01~16을 유지하고 각 패턴의 race/crash/clock/rollback 반례를 Code 계획/EV 인수에 연결한다. NFR Design 완료 검토에서 per-rule 근거를 다시 기록한다.

## 8. 실행 체크리스트

- [x] 사용자 `Continue to next stage`를 R1NFRR1=A로 기록하고 NFR 두 산출물/계획/state를 승인 상태로 갱신했다.
- [x] NFR Design 상세 규칙, 승인 NFR/TD/FD 및 관련 migration/generator/session/pool/OBS source를 확인했다.
- [x] 다섯 필수 질문 범주를 모두 평가하고 R1ND1~9 및 14개 내부 component 후보/인수 추적성을 작성했다.
- [x] 질문/빈 답변/A/B/Other 각 9개, 다섯 필수 범주, 14개 내부 후보 및 9개 인수 trace를 확인했다. 승인 FD/NFR의 46개 ID/range 참조, 기존 NFR 답변 14개=A, Prettier debug-check와 tracked/new-file whitespace 검사가 통과했다.
- [x] 사용자 `Use A for R1ND1-R1ND9`를 아홉 질문 모두 A로 기록하고 head/lock/authority/audit/clock/backup 조합을 검토했다. 미답변/혼합/모순 없음.
- [x] `nfr-design-patterns.md`에 PAT-R1-01~12, 단일 권위/commit·복구 경계, VAL-R1-01~18, 24개 NFR coverage 및 40개 확장 적용을 작성했다.
- [x] `logical-components.md`에 LC-R1-01~17, port/입출력/credential/transaction 경계, source·동기 DAG, failure containment 및 Infrastructure proof obligations를 작성했다. 후보 책임의 cache/guard, critical audit/일반 관측을 분리하고 목적별 signing helper를 명시했다.
- [x] 적용 확장 40개 규칙, effect/권한/복구/budget/24개 NFR coverage 및 17-node/56-edge DAG를 검증했다. 현 설계의 미해결 blocking finding 없음.
- [x] 두 산출물/plan/state/audit 및 R1NDR1 완료 리뷰를 준비했다. ID/참조/선택 trace, Markdown 및 tracked/new-file whitespace 검사가 통과했다.
- [x] 사용자 `Continue to the next stage`를 R1NDR1=A로 기록해 두 NFR Design 산출물을 승인했다 (2026-09-20).
- [x] 승인 후 **REM-1 Infrastructure Design**의 입력 분석/계획을 시작했다.

## 답변 방법

R1ND1~R1ND9 및 §10의 R1NDR1은 모두 A로 확정됐다. 후속 물리 배치 결정은 REM-1 Infrastructure Design 계획에서 다룬다.

## 9. 답변 분석 - 2026-09-20

**사용자 원문**: `Use A for R1ND1-R1ND9`
**기록 시각**: 2026-09-20T13:14:58Z

| 선택 | 확정 패턴 |
|---|---|
| R1ND1=A | 전용 physical connection의 session advisory lock + durable epoch; step별 target effect/ledger transaction |
| R1ND2=A | filesystem authoritative BindingHead + 검증된 immutable generation pin; control DB는 receipt/index |
| R1ND3=A | append-only framed bootstrap journal + sequence/previous digest/검증 편입 |
| R1ND4=A | one-shot RunSupervisor + 격리 child/helper, host admission/resource/deadline 및 orphan 재조정 |
| R1ND5=A | 최대 64 MiB immutable LRU; terminal read 실패 3회 -> 10s open -> readonly half-open probe 1개 |
| R1ND6=A | 좁은 purpose executor/helper + non-renewing current authority/commit guard, 목적별 key 분리 |
| R1ND7=A | clock-health age 30s, 현재 UTC uncertainty 최대 ±1s, boot/resume/jump 후 재관측 |
| R1ND8=A | Postgres critical audit + transactional outbox, bootstrap journal 편입, 별도 relay/retention 권한 |
| R1ND9=A | REM-1 writer-quiesced backup cut + stable 참조/hash/coverage와 명시 restore/reconcile |

교차 확인:

- filesystem BindingHead와 control DB의 per-gate EvidenceHead는 서로 다른 대상의 권위다. DB receipt를 competing binding head로 쓰거나 두 저장소의 원자 commit을 가정하지 않는다.
- session lock은 step commit 뒤에도 전용 connection에 유지한다. host-heavy slot, target exclusion, 현재 권한은 별도 증거이며 lease/PID/timeout만으로 서로를 대신하지 않는다.
- cache 64 MiB는 기존 daemon 512 MiB 안에 포함된다. cached parsing/서명 수학 결과가 current grant/key trust/head/eligible 결과를 재사용하는 경로가 되어서는 안 된다.
- ±1s clock window는 만료 grace가 아니다. window 전체가 유효 구간에 들어가야 하며 clock-health의 30s age는 권한/철회 cache를 허용하지 않는다.
- control 변경/audit/outbox는 하나의 Postgres transaction에 묶을 수 있지만 target DB/filesystem의 실제 효과와는 journal/receipt/reconciliation으로 연결한다. 실제 commit 사실과 유효한 권한·전체 검증 완료도 구분한다.
- backup은 writer quiescence를 확인한 뒤 capture한다. 결과만 미확정인 UNKNOWN 이력은 보존할 수 있지만 아직 쓰는 producer를 UNKNOWN이라는 이름으로 무시하지 않는다. 즉시 revocation/control 경로를 장시간 backup lock 뒤로 미루지 않는다.
- source authority와 각 target adapter의 실제 commit/revocation guard, durability/quiescence 및 clock-health 증명은 논리 계약과 인수 조건으로 명세한다. 제공하지 못하는 adapter는 mutation-ready가 아니다.
- 아홉 답변은 기존 single-host/수치/역할/보존/복구/별도 corpus 실행 경계와 정합적이다. 추가 정책 명확화 없이 두 NFR Design 산출물을 생성한다.

## 10. NFR Design 검증 및 완료 리뷰 - 2026-09-20

| 산출물 | 내용 |
|---|---|
| `../rem-1-platform-integrity/nfr-design/nfr-design-patterns.md` | PAT-R1-01~12, 실제 권위/선형화/내구성/권한·clock/복구 경계, VAL-R1-01~18, 24개 NFR 및 40개 확장 연결 |
| `../rem-1-platform-integrity/nfr-design/logical-components.md` | LC-R1-01~17, port/입출력/역할/credential/transaction, source·동기 DAG 및 Infrastructure proof obligations |

### 검증 결과

- pattern/component/validation 정의 **12/17/18개**가 유일하고 연속이다. 두 산출물/plan의 ID 및 약식/range 참조를 승인 NFR/TD/EV/FD/PROP까지 대조했고 미정의 참조가 없다.
- 두 산출물의 R1ND1~9=A trace는 각각 9행이며, NFR-R1-01~24가 전부 pattern과 실제 EV 인수에 연결된다.
- 선언된 component DAG **17 nodes / 56 edges**는 비순환이다. R1C facade에서 target mutation/publisher/journal/supervisor/tool/signing helper로 가는 의존 경로가 없다. shared C0 handle/native adapter와 의도된 async receipt/outbox feedback을 상위 service 역호출과 구분했다.
- 단일 FS BindingHead와 control EvidenceHead, pre-effect UNKNOWN/audit와 실제 target receipt, host slot과 I/O quiescence, non-renewing authority/현재 trust, 단일 generation pin/GC 및 backup cutoff를 대조했다.
- 64 MiB cache가 512 MiB 안에 포함되고 breaker 3회/10s/probe 1개, clock age 30s/±1s와 기존 NFR deadline/retention/RPO/RTO/PBT profile이 정합적이다. clock uncertainty를 expiry grace로 사용하지 않는다.
- source에서 확인한 sliding `SessionManager.verify`/optional audit hook을 새 current-authority/durable receipt로 간주하지 않는다. native guard·OS/FS/clock 구현을 실제로 입증할 수 없는 adapter는 mutation-ready가 아니며 해당 proof obligation을 handoff에 명시했다.
- Prettier `--debug-check`, tracked state/audit 및 새 산출물/plan의 whitespace 검사가 통과했다. 텍스트/표로 표현해 새 Mermaid/ASCII diagram은 없다. state는 기존 과거 FR-27 formatter 문제를 고려해 추가 내용의 parsing/whitespace로 검증한다.
- 이는 NFR Design 산출물 검증이다. VAL/EV의 실제 concurrency/crash/current-authority/restore 및 성능 검증은 Code/Build에서 수행한다.

### 확장 준수 요약

per-rule 근거는 `nfr-design-patterns.md` §5에 있다.

- **Security**: SECURITY-01/03/05~15는 설계 수준 Compliant(13개). SECURITY-02는 신규 외부 intermediary 없음, SECURITY-04는 신규 HTML/UI 없음으로 N/A.
- **Resiliency**: RESILIENCY-01~07/10~15 Compliant(13개), RESILIENCY-09는 local bounded-capacity replacement, RESILIENCY-08은 승인된 single-Mac 예외로 N/A.
- **PBT**: PBT-01~10은 NFR Design 단계 실행 검증 N/A. Full framework/profile, PROP-R1-01~16 및 VAL/EV의 Code/Build 검증 요구를 유지한다.

### R1NDR1 - NFR Design 산출물 승인

두 산출물의 선택 패턴/컴포넌트, 권한·내구성·실패/복구·의존 경계 및 인수 추적성을 승인하고 **REM-1 Infrastructure Design**으로 진행할까?

A) **Continue to Next Stage** — NFR Design을 승인하고 REM-1 Infrastructure Design으로 진행한다.

B) **Request Changes** — 수정할 pattern/component/guard/복구/인수 또는 추적성을 지정한다.

X) 기타 (아래 `[Answer]:` 뒤에 리뷰 의견을 기술)

[Answer]: A

**승인 기록**: 사용자 원문 `Continue to the next stage`, 2026-09-20T14:27:39Z. 현재 완료 리뷰의 Continue to Next Stage 선택인 R1NDR1=A로 기록하고 REM-1 Infrastructure Design을 시작한다.
