# REM-1 — NFR Design Patterns

**단계**: CONSTRUCTION / NFR Design
**상태**: 작성·검증 및 R1NDR1=A 승인 완료 (2026-09-20; `../../plans/rem-1-platform-integrity-nfr-design-plan.md`).
**입력**: R1ND1~R1ND9=A, R1NFRR1=A, R1FDR1=A, DAD1=A, UGR1=A
**결정 기록**: `../../plans/rem-1-platform-integrity-nfr-design-plan.md` §9
**Companion**: `logical-components.md`, `../nfr-requirements/`, `../functional-design/`

## 1. 설계 범위와 권위

이 문서는 승인된 패턴의 실행 순서·선형화·오류·복구 계약을 정의한다. 실제 provider/OS/DB/filesystem 구현과 운영 인수는 후속 Infrastructure/Code/Build의 증거로 판정한다. R1C/R1R/OBS는 기존 REM-1 역할이며 아래 내부 컴포넌트가 별도 REM service를 추가하지 않는다.

| 대상 | 권위 | 다른 저장소/값의 의미 |
|---|---|---|
| migration 효과/적용 이력 | 해당 target Postgres의 효과+canonical ledger transaction | control Run/receipt는 조정·관측 기록 |
| active binding generation | publication scope의 filesystem BindingHead | control DB receipt/index는 projection이며 두 번째 active head가 아님 |
| 검증 gate의 current evidence | control Postgres의 EvidenceHeadSelection revision와 immutable attestation | 가장 최근 시각/과거 PASS를 임의 선택하지 않음 |
| caller 권한·키 trust/철회 | U3 또는 승인된 운영 authority의 current port | 저장된 승인/서명/mTLS identity/캐시만으로 새 권한을 만들지 않음 |
| host-heavy lane | host exclusion과 보수적인 holder/quiescence 기록 | target effect/권한을 증명하지 않으며 canonical Run 상태는 control DB에 있음 |

**실제 효과**, **그 효과의 내구성**, **권한이 유효했던 증거**, **control/audit 완료**는 서로 다른 사실이다. 실제 효과를 확인했어도 나머지 증거가 불충분하면 SUCCEEDED/eligible로 확대하지 않는다. control DB와 target/filesystem 전체의 분산 원자 commit을 가정하지 않는다.

## 2. 선택된 패턴

### PAT-R1-01 — Capability 분리와 coherent readonly 경로

**Trace**: NFR-R1-01/06/09/13/24; TD-R1-01~06; LC-R1-01~03/10/11.

- C3 composition이 C2 adapter/C1 core/C0 contract를 묶는다. core는 backend app bootstrap, 다른 REM controller 또는 live R1C를 import/역호출하지 않는다. 같은 frozen artifact의 역할별 entry/closure/credential을 분리한다.
- R1C는 입력/현재 관측 권한/총 3s budget을 검증한 뒤 control read snapshot을 연다. required slot, selected revision, attestation body와 trust/subject binding을 확인한다. raw scanner report나 임의 locator를 클라이언트 입력으로 읽지 않는다.
- Postgres head와 record는 같은 readonly snapshot에 결속한다. filesystem head/current target처럼 다른 권위의 revision은 관측 전후 대조한다. 변화/모순이면 남은 readonly retry budget 안에서 다시 읽거나 INCOMPLETE/STALE로 끝낸다. 두 저장소의 동시 snapshot이라고 주장하지 않는다.
- evaluation은 exact input/head revisions, current facts, clock window와 평가 시각을 기록한다. 응답 시점의 관측 결과이며 다음 mutation의 권한 token이 아니다. 새 effect는 PAT-R1-02의 현재 guard가 필요하다.
- R1C 자체의 관측/telemetry와 business/control mutation을 구분한다. read/check/health가 ledger 생성, head promotion, fresh scan 또는 job을 실행하지 않는다. startup/CLI/local artifact도 같은 pure validator를 사용한다.

### PAT-R1-02 — Purpose helper, 현재 권한과 commit guard

**결정**: R1ND6=A. **Trace**: NFR-R1-03/10~13/20; BR-R1-08/11/12; LC-R1-04/05/10/17.

1. helper 입력은 allowlisted action/record-kind, opaque target, exact plan/artifact/policy digest, run/attempt/effect identity다. arbitrary SQL/path/bytes-signing 요청을 받지 않는다. SQL은 등록된 검증 artifact에서만 해소한다.
2. non-renewing authority port로 actor/purpose/resource, 원 source grant의 현재 상태·만료·MFA/role 및 revocation revision을 확인한다. background/retry는 기존 `SessionManager.verify`의 sliding save를 호출하지 않는다. U3가 없는 제한된 bootstrap은 별도 현재 운영 authority의 System 목적을 사용한다.
3. expensive 준비/SQL 실행과 최종 권한 critical section을 구분한다. 최종 effect 경계에서 source authority와 resource adapter가 참여하는 **CommitGuard**를 취득한다. 이는 사전 조회 결과의 Boolean이나 보관 가능한 bearer credential이 아니다.
4. guard는 exact target/plan/effect, authority revision, target fence epoch와 보수적 deadline에 결속한다. revoke/cancel/epoch 변경과 실제 finalization이 같은 protocol로 순서화돼야 한다. 새 guard는 revocation 요청 이후 거부되고, 이미 finalizing인 작업의 결과/실제 종료가 불명확하면 quiescence 완료를 주장하지 않는다.
5. effect가 guard 경계에서 먼저 확정됐으면 그 역사적 사실을 보존하고 다음 effect는 새 권한을 확인한다. revoke/expiry/fence 변경이 먼저면 rollback/no-replace다. guard 연결 유실 또는 순서를 증명할 수 없는 결과는 UNKNOWN으로 남긴다.

| Resource adapter | 요구되는 finalization 보호 | 부족한 증거 |
|---|---|---|
| Postgres target | 마지막 current-authority/fence/deadline 검증이 target commit protocol에 결합되고 revoker가 같은 guard에 참여. step 효과+ledger는 같은 transaction | 독립 RPC에서 한 번 읽은 권한, control DB의 비동기 mirror, client-side 시각 확인만으로 COMMIT 보장 |
| filesystem publication | 유일한 publisher가 publication exclusion과 current-authority guard를 유지한 atomic head 전환. revoke/cancel은 같은 보호 경계로 조정 | 파일 lock만 획득하거나 오래된 signed approval만 확인한 rename |
| signature issuance | record-kind/purpose별 현재 발행 권한, 검증된 payload/provenance 및 current signing key를 결속 | caller가 준 hash/임의 bytes를 무조건 서명 |

이 계약은 authority owner의 동기 revoke/fence 참여와 native boundary 증거가 필요하다. 제공하지 못하는 adapter는 mutation capability가 unavailable이며 lookup-then-write나 오래된 lease로 대체하지 않는다. SQL lock은 권한 자체가 아니고 mTLS는 caller 권한 자체가 아니다.

실제 commit이 확인돼도 권한/시간/내구성 증거가 유실됐으면 effect fact와 verification failure를 함께 보존한다. 기존 효과를 반복하거나 나중의 승인으로 과거 권한을 소급하지 않는다. 결과 관측/기록에는 현재의 observe/reconcile 목적 권한을 사용하고 expired mutation 승인을 재사용하지 않는다.

### PAT-R1-03 — Session exclusion과 step별 migration transaction

**결정**: R1ND1=A. **Trace**: NFR-R1-02/03/08; FL-R1-01~03/07; LC-R1-03/04/06/10~12.

1. 전체 registry/plan/source digest/capability와 alias/겹치는 namespace를 먼저 검증한다. 명시 physical target exclusion key를 사용하며 basename이나 임의 caller key로 lock 범위를 만들지 않는다.
2. helper는 전용 physical psycopg connection으로 target-scoped session advisory lock을 최대 5s 안에 획득한다. attempt 동안 connection을 반환/교체/transaction-pool 하지 않는다. step commit은 session lock을 해제하지 않는다.
3. lock 아래 target incarnation/current ledger를 재관측하고 durable fence epoch와 실행 holder를 결속한다. source/fence/epoch의 변화를 무시해 pending 목록을 계속 실행하지 않는다.
4. 각 step 전에 control transaction으로 intent/UNKNOWN checkpoint/critical audit/outbox를 durable 기록한다. 제한된 control bootstrap에서는 PAT-R1-05 journal을 사용한다. 이 기록이 확인되기 전 target effect를 시작하지 않는다.
5. target transaction에서 검증한 immutable SQL bytes, prerequisite 및 precondition을 사용한다. 허용 schema/search path/role을 제한하고 metadata 값은 parameter binding한다. ATOMIC_STEP은 transaction 탈출/비원자 외부 효과/무단 role 전환을 허용하지 않는다. 이 조건을 입증할 수 없는 script는 별도 non-atomic 계획으로 분리하고 실행하지 않는다.
6. postcondition을 확인하고 PAT-R1-02의 finalization guard와 PAT-R1-08 deadline 아래 effect+canonical ledger를 함께 commit한다. 첫 실패 시 해당 transaction을 rollback하고 이후 step을 시작하지 않는다. 앞선 verified step은 유지한다.
7. 실제 target commit 후 control 결과/감사 기록을 확정한다. target 응답 또는 control 기록이 유실되면 그 간격을 UNKNOWN으로 보존한다. 다음 attempt는 exact target/identity/content/epoch의 ledger와 실제 종료/상태를 확인한 뒤에만 재개한다.

connection/PID/lease의 부재만으로 rollback을 추정하지 않는다. target server/session witness, exclusive lock 및 postcondition/ledger를 대조한다. PID 재사용과 다른 target의 같은 migration 이름을 구분한다. 실제 적용 증거가 없는 legacy adoption을 VERIFIED_EXECUTION으로 승격하지 않는다.

### PAT-R1-04 — Sealed generation, filesystem head와 consumer pin

**결정**: R1ND2=A. **Trace**: NFR-R1-01/05/18; BR-R1-13~16; LC-R1-05/07/10/13/15/17.

1. tool은 inactive 작업 공간에만 쓴다. publisher가 보유한 fresh namespace로 verified bytes를 복사/봉인하고 manifest의 전체 file set/path/digest를 대조한다. chmod만 바꾸고 기존 writable descriptor가 사라졌다고 가정하지 않는다.
2. parse/type/실제 consumer/visibility/fixture 검증은 권한 없는 validator 역할이 봉인된 exact digest를 대상으로 수행한다. privileged helper가 검증을 이유로 arbitrary generated code를 자기 credential로 실행하지 않는다.
3. files/manifest 및 필요한 directory durability를 확인하고 immutable generation을 만든다. content-addressed 경로를 다른 bytes로 덮어쓰지 않는다. 기존 generation이 있으면 일치 여부를 검증한다.
4. 사전 UNKNOWN/audit 기록 후 publication exclusion, expected head revision/hash, target incarnation 및 current CommitGuard를 검사한다. 같은 filesystem의 temporary head를 durable하게 작성하고 **하나의 BindingHead**를 atomic replace한 뒤 필요한 parent-directory durability를 확인한다. cross-device copy로 atomic replace를 대체하지 않는다.
5. head에는 scope/incarnation, activation revision, previous-head digest, generation/manifest digest, effect/permit 증거 참조가 결속된다. rollback도 새 승인과 **새 revision**으로 검증된 이전 generation을 선택한다. generation digest만 비교해 ABA를 허용하지 않는다.
6. consumer는 build/start 시 head를 한 번 검증·해소해 exact generation real path/manifest에 pin한다. 같은 import/build 도중 current link를 다시 따라가지 않는다. 새 head가 기존 process의 pin을 조용히 바꾸지 않는다.
7. control DB의 receipt/index를 actual filesystem head에 맞게 기록한다. DB 결과 기록 실패가 실제 head 전환을 되돌렸다는 뜻은 아니다. per-gate EvidenceHeadSelection은 별도 권위다.

| 실패 지점 | 처리 |
|---|---|
| candidate/검증 실패 | REJECTED, 기존 authoritative head 보존 |
| head 전환 전 실패 | old head/current effect를 확인하며 no-effect를 추정하지 않음 |
| rename 이후 durability/receipt 미확인 | UNKNOWN, 실제 head/manifest/executor quiescence로 재조정. 단순 존재를 durable 성공으로 보지 않음 |
| mixed/corrupt/unmanaged head | unready 및 복구 필요. 오래된 DB PASS를 대신 선택하지 않음 |

consumer/build/rollback/backup/미확정 effect의 참조는 GC protection이다. 읽기 pin은 미리 준비된 readonly lease/배포 manifest 등으로 보호하며 R1C 조회가 control metadata/lock file을 생성하지 않는다. GC는 참조 종료와 reader 종료를 확인하고 unknown pin을 만료 시각만으로 회수하지 않는다.

### PAT-R1-05 — Framed bootstrap journal과 검증 편입

**결정**: R1ND3=A. **Trace**: NFR-R1-02/16/20; LC-R1-03/06/10/12.

- journal은 control realm 최초 bootstrap/명시 recovery에만 사용한다. 일반 control-store 장애에서 새 business mutation을 계속하는 fallback이 아니다.
- frame은 version/길이, canonical payload, sequence/previous digest, checksum/서명 provenance를 갖는다. payload는 run/attempt/effect/target/incarnation/plan/policy/assurance를 결속하며 credential/raw private input을 넣지 않는다. length/count 한도는 parsing 전에 적용한다.
- append와 durable flush를 확인하고, 승인된 append 위치/last-acknowledged sequence/hash witness를 보호한다. UNKNOWN frame과 필요한 durability acknowledgement가 확인되기 전 effect를 열지 않는다. witness는 두 번째 event log나 effect 성공 판정이 아니다.
- partial/torn tail, gap, 중복 sequence의 다른 bytes, chain/signature/floor 불일치는 보존·격리한다. hash chain만으로 전체 tail truncation을 탐지한다고 주장하지 않는다. acknowledged floor/완전성을 증명할 수 없으면 UNKNOWN이며 target 증거와 별도 복구 판단이 필요하다.
- control 복원 후 `(journal identity, sequence, record digest)`로 멱등 편입한다. 같은 key의 다른 bytes는 충돌이다. audit/outbox와 import receipt를 같은 control transaction에 기록하고 원 provenance를 유지한다.
- import는 기존 사실/metadata 복원이지 저장된 SQL/명령의 재실행이 아니다. import/remote archive/보존·참조 검증 전 원 journal을 정리하지 않는다. append writer는 과거 frame 수정/삭제 권한을 얻지 않는다.

### PAT-R1-06 — One-shot supervisor, host slot과 orphan containment

**결정**: R1ND4=A. **Trace**: NFR-R1-04~08/19; LC-R1-07/09~13/15~17.

1. 명시 호출이 입력/현재 목적 권한/plan과 기존 RunIntent를 확인하고 host-heavy lane을 claim한다. 새로운 privileged 대기 queue를 만들지 않는다. 포화는 bounded busy/명시 재시도다.
2. host exclusion과 보호된 busy marker는 run/attempt 및 boot/process-start/group identity를 결속한다. marker는 resource 회수용 보수적 witness이며 canonical Run/effect/approval 저장소의 fallback이 아니다. lock inode를 unlink/재생성해 다른 lock을 만들지 않는다.
3. control claim과 child-launch 가능 상태를 durable하게 기록한 뒤 child/helper를 시작한다. parent가 죽어 OS lock이 풀렸어도 미정리 marker/child/target I/O를 대조하기 전 새 full-budget lane을 허용하지 않는다. pending spawn도 미실행으로 추정하지 않는다.
4. tool은 허용된 executable/input/작업 root/output 한도와 최소 환경만 받는다. generator는 offline, scanner는 정해진 network capability다. 일반 child는 DB mutation/signing secret을 받지 않는다.
5. runner와 그 child/helper의 실제 RSS 합계는 2 GiB budget으로 계측하고 daemon 512 MiB와 분리한다. tool-local 한도, output/file 크기 및 disk peak 검사를 함께 사용한다. 관측할 수 없는 process를 합계에서 빼고 성공하지 않는다.
6. `effectiveDeadline`을 child/DB/network/IPC에 전달하며 하위 retry가 새 budget을 발급하지 않는다. time/resource 위반 시 새 단계 dispatch를 막고 scoped cancel, child reap, target I/O 확인으로 진행한다. cancel이 도착했다는 사실은 rollback receipt가 아니다.
7. quiescence를 확인하면 host 자원은 회수할 수 있지만 결과가 불명확한 target mutation은 별도 UNKNOWN fence로 유지한다. ordinary daemon restart는 status/관측만 복구한다.

R1C는 조회 8개와 health 2개의 별도 admission/dependency budget을 사용한다. 기존 backend의 10+20 pool을 그대로 가져와 상한을 우회하지 않는다. cache 64 MiB는 daemon budget에 포함되며 별도 증설분이 아니다. 실제 OS/job supervision/신호 권한과 고아 process 확인 수단은 Infrastructure에서 검증한다.

### PAT-R1-07 — Immutable LRU와 generation-aware circuit breaker

**결정**: R1ND5=A. **Trace**: NFR-R1-07~10/19; LC-R1-01/02/08/09.

- cache key는 exact content digest, schema/parser/tool/policy 및 필요한 visibility scope다. 서명의 수학적 검증을 재사용할 때는 algorithm/profile과 실제 public-key fingerprint도 key에 포함한다. 값은 immutable parsing/무결성 자료뿐이다. current grant/key trust/revocation, selected head, current target 및 최종 eligible verdict는 캐시하지 않는다.
- byte-budgeted LRU는 **최대 64 MiB**이며 parsed object/참조의 보수적 resident accounting을 포함한다. accounting 또는 immutability를 입증하지 못한 항목은 저장하지 않는다. raw JSON bytes만 세고 객체 overhead를 숨기지 않는다.
- hit도 현재 actor 권한/subject/head/키 trust를 확인한 뒤 사용한다. immutable 보장이 사라지거나 현재 binding이 달라지면 해당 reuse를 거부한다. 필요 readonly 재검증이 불가능하면 stale 내용으로 응답 권한을 만들지 않는다.

| Breaker 상태 | 전이 / 허용 동작 |
|---|---|
| CLOSED | dependency+operation별 최종 availability 실패 3회 연속이면 OPEN. 성공은 현재 generation의 연속 실패를 reset |
| OPEN | monotonic 10s 동안 즉시 UNKNOWN/unavailable. 과거 권한/결과를 fallback하지 않음 |
| HALF_OPEN | cooldown 뒤 원자적으로 probe ticket 1개만 발급. 대표 readonly 성공은 CLOSED, 실패는 다시 OPEN |

counter/ticket에는 breaker generation을 둔다. 이전 CLOSED 요청의 늦은 성공이 OPEN을 닫거나 오래된 probe가 새 상태를 덮지 못한다. logical read의 허용 retry가 모두 끝난 최종 결과를 한 번만 센다. caller denial/input 오류는 availability 실패 횟수에서 제외한다. probe 취소/실패도 ticket을 회수하고 bounded 상태로 돌아가며 mutation/새 scan을 probe로 사용하지 않는다.

### PAT-R1-08 — Trusted UTC window와 보수적 deadline

**결정**: R1ND7=A. **Trace**: NFR-R1-08~11/15; LC-R1-02/07/10/11.

- ClockHealthProvider는 protected source evidence, UTC lower/upper bound, 관측 monotonic 값, boot/resume identity와 drift/불확실성 근거를 제공한다. 단순 wall clock 또는 같은 host의 Postgres 시각을 두 번째 독립 증명으로 사용하지 않는다.
- 현재 window는 표본에서 경과한 continuous-monotonic 시간과 검증된 drift bound로 전진시킨다. clock-health age는 **30s 미만**, 현재 uncertainty는 **최대 ±1s**여야 한다. 범위/age/신뢰 근거를 계산할 수 없으면 UNKNOWN이다.
- boot/sleep-resume/discontinuity 또는 건강도 상실은 기존 context를 무효화한다. suspend를 포함하는 elapsed-time 수단 또는 확실한 resume invalidation이 필요하다. 새 신뢰 표본 전에는 time-dependent eligibility/새 mutation을 허용하지 않는다.
- `[L, U]` 전체가 validity 안에 있어야 한다: `validFrom <= L` 그리고 `U < validUntil`. 오차를 만료 grace로 더하지 않는다. `now == validUntil`은 유효하지 않다.
- deadline은 action/attempt의 원 monotonic cap과, `validUntil - U` 등 남은 approval/source-grant/fence 예산의 최솟값이다. refresh 후 clock-health가 좋아져도 이미 잡은 더 이른 attempt deadline을 자동 연장하지 않는다.
- helper는 실제 finalization 전에 fresh clock context를 확인한다. 실행 중 clock가 불명확해지면 새 dispatch를 중지하고 진행 중 I/O를 취소/재조정한다. 실제 효과가 있었으면 사실은 기록하되 확인되지 않은 권한·시간 증거까지 성공으로 표시하지 않는다.

clock의 실패를 기록하는 진단은 그 clock가 trusted였다는 주장이 아니다. 로그는 boot/monotonic 및 time-quality를 함께 남길 수 있지만 untrusted 시각을 승인/현재 증거의 유효성으로 소비하지 않는다.

### PAT-R1-09 — Transactional critical audit와 outbox

**결정**: R1ND8=A. **Trace**: NFR-R1-14/19/20; LC-R1-03/06/12/13.

- control 변경/중요 intent/checkpoint, append-only critical audit 및 전달 outbox를 같은 Postgres transaction에 기록한다. critical event ID와 payload digest는 멱등이며 같은 ID의 다른 bytes는 거부한다.
- audit owner/retention, application append/read, relay delivery-cursor 권한을 분리한다. 일반 application은 audit UPDATE/DELETE/DDL 권한을 갖지 않는다. relay의 acknowledgement는 별도 delivery state이며 원 audit를 수정하지 않는다.
- target effect는 별도 저장소일 수 있다. 사전 UNKNOWN+audit의 durable receipt, 실제 resource receipt, 사후 control 결과의 순서로 연결한다. 이 간격의 crash가 분산 rollback이나 자동 재실행을 뜻하지 않는다.
- bootstrap은 PAT-R1-05 journal로 critical 증거를 보존하고 control 복원 후 검증 편입한다. 일반 장애에 이 경로를 열지 않는다.
- relay는 bounded 명시 역할로 U6/암호화 archive에 멱등 전달하고 backlog/보존/disk를 관측한다. relay/GC/대량 archive도 선언된 resource/admission budget을 지키며 별도 무제한 heavy lane이 아니다.
- 일반 metrics/trace 실패는 이미 committed한 효과의 사실을 바꾸지 않는다. optional audit hook 또는 memory append는 critical receipt가 아니다. R1C의 telemetry 제출 권한이 control/target mutation 권한으로 확대되지 않는다.

### PAT-R1-10 — Writer-quiesced backup, 참조 보호와 restore

**결정**: R1ND9=A. **Trace**: NFR-R1-12/14~16/22; LC-R1-03/05~07/10~14.

1. 명시 BackupIntent가 REM-1 write/promotion admission을 닫고 기존 관련 writer를 종료/정지·fence한다. 현재 revoke/safety control과 가능한 readonly 진단을 긴 backup 뒤로 미루지 않는다. 경합 시 새 backup을 성공 접수한 것처럼 숨기지 않는다.
2. child/helper/target I/O quiescence를 확인한다. 결과만 미확정인 UNKNOWN 이력은 보존할 수 있지만 아직 쓰는 producer는 일관된 cut으로 인정하지 않는다. 다른 domain의 snapshot/writer는 원 owner 계약으로 조정한다.
3. stable filesystem heads/immutable 참조, control DB의 consistent snapshot, target ledger와 journal의 검증 boundary를 manifest로 묶는다. audit처럼 계속 append되는 stream은 명시 cutoff를 기록한다. backup 자체의 후속 control 기록을 무한히 자기 backup에 포함하지 않는다.
4. DB dump/cut 및 mutable 자료의 일관된 local capture를 완료하고 immutable 참조에 BackupPin을 둔다. snapshot/hash/coverage가 durable하고 GC가 필요한 참조를 보존할 때 writer admission을 재개할 수 있다. 단순 reference 목록만 작성한 것을 capture 완료로 보지 않는다.
5. 암호화된 원격본 회수/hash/coverage와 실제 isolated restore를 확인한다. inner capture manifest와 outer archive/전송 receipt를 분리해 self-hash 순환을 만들지 않는다. upload timeout은 새로운 백업 시각/성공이 아니라 전송 결과 재조정 대상이다.
6. restore는 FileVault/키 접근, control/journal/files 복원, 새 incarnation/current trust·권한 검증, UNKNOWN 재조정, 명시 재개 순서다. backup의 active key/grant/head를 현재 권한으로 자동 활성화하지 않는다. 현재 trust/철회 floor를 입증할 수 없으면 recovery quarantine을 유지한다.

RPO는 snapshot/cut 시각에서, RTO는 사고 인지부터 실제 검증된 복구까지 측정한다. operator unlock/host 준비를 포함하고 daemon 60s 조건부 목표와 구분한다. backup/transfer/restore action도 명시 finite plan budget과 현재 권한이 필요하다. 구체 저장소/전송/키 escrow/시간 배선은 Infrastructure에서 확정한다.

GC는 active release/reader/rollback/BackupPin/unknown effect/journal import/retention을 모두 확인한다. 90일 critical evidence, 14일 일반 로그, 7일 미참조 실패 candidate는 필요한 참조보다 우선하지 않는다. pin/consumer 종료가 미확인일 때 자동 만료만으로 자료를 지우지 않는다.

### PAT-R1-11 — Immutable verification pipeline과 evidence CAS

**Trace**: NFR-R1-09/17/18/21/22; TD-R1-05/10/14~16; LC-R1-03/05/07~13/15~17.

- source/canonical schema/consumer/tool/profile을 freeze하고 closed-world local registry로 모든 ref와 actual import/export를 검증한다. supported recursion을 유지하고 unsupported/누락/실패를 skip-success로 만들지 않는다.
- public/server/internal wire를 분리하고 view adapter는 positive/negative fixture로 확인한다. 봉인된 candidate에 대한 검증/producer provenance가 있어야 helper가 attestation/head를 발행한다. arbitrary claim이나 exit 0만을 서명하지 않는다.
- SCA는 실제 lock/installed occurrence/image digest/SBOM을 대조하고 online response snapshot과 local DB freshness를 구분한다. source-unreachable 예외는 exact artifact/closure/proof/current policy·승인에만 적용한다. 원 finding/unknown/coverage를 보존한다.
- authoritative verification이 admission되면 control transaction으로 해당 slot의 PENDING revision/attempt를 예약한다. 결과 immutable record, 같은 revision의 RESOLVED head 및 critical audit/outbox를 일관되게 publish한다. 이미 실패/중단된 slot을 이전 PASS로 대체하지 않는다.
- CAS에 진 이전 attempt의 결과는 history일 뿐 current head가 아니다. 단순 preview/readiness/check는 예약/발행을 수행하지 않는다. 파일 BindingHead와 이 EvidenceHead의 서로 다른 revision/binding을 검증한다.
- 사용 중 artifact의 24h 재검사, approval 30분/예외 7일, 실패/만료 시 current gate 및 Full PBT profile은 승인 NFR을 따른다. 검증 과정이 dependency 업데이트/repair를 자동 실행하지 않는다.

### PAT-R1-12 — Canonical control envelope, key lifecycle와 안전한 관측

**Trace**: NFR-R1-06/10~13/19/23/24; LC-R1-01/02/10~13/17.

| Control codec | 명세 |
|---|---|
| identity/reference | versioned schema가 정한 opaque string. source/domain ID를 임의 case-fold/coerce하지 않음 |
| monotonic epoch/sequence 및 UTC instant | 새 REM-1 signed control contract는 lossless canonical decimal string을 사용. instant 단위는 UTC Unix microseconds로 구분하며 JSON Number/JS Date의 반올림으로 비교하지 않음 |
| bounded count/duration | schema에 unit/range를 명시한 safe integer. NaN/Infinity, 중복 key, 잘못된 Unicode, 선언되지 않은 type은 거부 |
| fingerprint | algorithm/policy version과 exact bytes SHA-256 또는 선언된 JCS metadata digest를 구분 |
| signed envelope | domain/record-kind/schema-version/key-purpose/key-id/subject/scope/policy/payload-digest 및 해당 kind의 validity/provenance를 JCS로 결속해 Ed25519 서명. signature field 자체는 signed bytes에서 제외 |

이 codec은 새 REM-1 control envelope에 적용한다. epoch/sequence/UTC-microsecond field는 uint64 범위의 base-10 string이며 `0` 외 leading zero, 부호, 지수 표현을 허용하지 않는다. bounded JSON integer는 정확한 safe-integer 범위와 field별 한도를 지킨다. SHA-256 digest는 algorithm-tagged lowercase hex, Ed25519 signature는 decoded 64 bytes의 unpadded base64url로 정의한다. 기존 product wire/ID를 일괄 변환하지 않는다. counter는 wrap/reuse하지 않으며 schema/test vectors로 검증한다. raw SQL/schema/source bytes는 canonical metadata처럼 정규화하지 않는다.

routine rotation은 새 key ID/public verification material 배포·호환 확인 -> current signing 전환 -> old signing 종료 순서다. 다른 key material에 기존 key ID를 재사용하지 않는다. retired key의 역사적 검증과 current 발행 권한을 구분한다. historical acceptance는 보호된 record/head/receipt provenance로 확인하며 서명자가 주장한 과거 시각만으로 backdated proof를 신뢰하지 않는다. compromise/revocation은 current trust를 차단하고 관련 evidence를 재검토한다.

shallow liveness, dependency readiness, subject gate는 별도다. 일반화 reason/role/correlation/phase latency를 U6에 연결하고 private payload/token/DSN/내부 경로를 일반 응답/로그에 넣지 않는다. gate verdict는 BLOCKED -> INCOMPLETE -> STALE -> ELIGIBLE_WITH_EXCEPTIONS -> ELIGIBLE 순서로 표시하되 모든 reason을 보존한다. local G1을 전체 release/G4/G5 인수로 확대하지 않는다.

## 3. Pattern 검증 시나리오

아래는 Code/Build의 검증 요구다. design 문서 작성만으로 실제 I/O 보장이 통과한 것은 아니다.

| ID | 반례/경합 | 필수 결과 / trace |
|---|---|---|
| VAL-R1-01 | 같은 target의 두 writer, 겹치는 alias | session exclusion/epoch 및 alias 검증; 중복 효과 0 — PAT-R1-03, PROP-R1-02/05~07 |
| VAL-R1-02 | 긴 SQL 중 revoke, finalization과 revoke 경쟁 | native guard의 승자를 입증; 선행 revoke면 rollback/거부, 이미 확정된 사실은 보존 — PAT-R1-02/03 |
| VAL-R1-03 | target COMMIT 후 응답/control 기록 유실 | ledger/실제 종료로 재조정, 재실행 없음; 권한 증거와 effect fact 구분 — PROP-R1-08, EV-R1-03 |
| VAL-R1-04 | parent crash, pending spawn, PID 재사용 | old child/DB I/O 종료 전 full-budget lane 회수 금지 — PAT-R1-06 |
| VAL-R1-05 | seal 후 worker의 늦은 write/privileged validation 시도 | immutable helper-owned snapshot 검증 및 최소 권한, active 데이터 변경 없음 — PAT-R1-04 |
| VAL-R1-06 | head replace 전후 crash/parent-directory flush 실패 | old 또는 complete new만 관측, 내구성 미확인은 UNKNOWN — PROP-R1-12 |
| VAL-R1-07 | multi-file import 중 head 변경/rollback | 한 generation pin 유지, 새 revision으로 ABA 방지 — PAT-R1-04 |
| VAL-R1-08 | torn journal/gap/유실 floor/중복 import | 보존·격리/metadata-only 멱등 편입, blind command replay 없음 — PAT-R1-05 |
| VAL-R1-09 | control/audit DB 실패와 일반 telemetry 실패 | 전자는 새 effect 차단, 후자는 과거 commit 사실을 바꾸지 않음 — PAT-R1-09 |
| VAL-R1-10 | key revoke/target restore/head 변경 뒤 cache hit | parsing 재사용과 current 권한/eligibility를 분리 — PAT-R1-07/12 |
| VAL-R1-11 | 3 terminal 실패, 늦은 성공, 동시 half-open | 10s open/current-generation probe 1개, 오래된 callback이 상태를 되돌리지 않음 — PAT-R1-07 |
| VAL-R1-12 | age 30s, uncertainty 초과, suspend/jump, expiry 경계 | time-dependent current 판정 보류, grace/attempt 연장 없음 — PAT-R1-08 |
| VAL-R1-13 | 임의 signing/SQL/path, 다른 purpose/plan, stale grant | helper 거부 및 안전한 audit; bg session touch 없음 — PAT-R1-02/12 |
| VAL-R1-14 | unquiesced writer 또는 missing domain cut의 backup | consistent capture 완료로 표시하지 않음 — PAT-R1-10 |
| VAL-R1-15 | active reader/backup/unknown reference와 GC 경쟁 | 필요한 generation/journal/evidence 보존 — PAT-R1-04/10 |
| VAL-R1-16 | restore 후 old approval/old active key/late helper | 새 incarnation/current trust, 명시 재조정 전 mutation 금지 — PAT-R1-02/10 |
| VAL-R1-17 | scanner 오류+빈 findings, 실패한 현재 검증 뒤 late PASS | coverage/current revision 실패 보존, clean/eligible로 승격하지 않음 — PAT-R1-11 |
| VAL-R1-18 | resource/입력 한도 초과, queue 장애, clock/audit 장애 | bounded health/current gate/non-success 및 민감정보 비노출 — PAT-R1-06~09/12 |

## 4. NFR 및 결정 coverage

| NFR | Pattern | 실제 인수 |
|---|---|---|
| NFR-R1-01 | PAT-R1-01/04/11/12 | EV-R1-01/04/05 |
| NFR-R1-02 | PAT-R1-03/05/09 | EV-R1-03/07 |
| NFR-R1-03 | PAT-R1-02~06 | EV-R1-03/06 |
| NFR-R1-04 | PAT-R1-06/07 | EV-R1-02 |
| NFR-R1-05 | PAT-R1-04/06/10 | EV-R1-02/07 |
| NFR-R1-06 | PAT-R1-01/05/11/12 | EV-R1-02/04/06 |
| NFR-R1-07 | PAT-R1-01/06/07 | EV-R1-02 |
| NFR-R1-08 | PAT-R1-02/03/06~08 | EV-R1-02/03/06 |
| NFR-R1-09 | PAT-R1-01/07/08/11 | EV-R1-05/09 |
| NFR-R1-10 | PAT-R1-02/08/12 | EV-R1-06 |
| NFR-R1-11 | PAT-R1-05/12 | EV-R1-01/06 |
| NFR-R1-12 | PAT-R1-01/10/12 | EV-R1-06/07 |
| NFR-R1-13 | PAT-R1-01/02/12 | EV-R1-06 |
| NFR-R1-14 | PAT-R1-04/05/09/10 | EV-R1-06/07 |
| NFR-R1-15 | PAT-R1-06/08/10/12 | EV-R1-07/09 |
| NFR-R1-16 | PAT-R1-05/09/10 | EV-R1-07 |
| NFR-R1-17 | PAT-R1-11 | EV-R1-05 |
| NFR-R1-18 | PAT-R1-04/11 | EV-R1-04 |
| NFR-R1-19 | PAT-R1-06~09/12 | EV-R1-02/09 |
| NFR-R1-20 | PAT-R1-05/09/12 | EV-R1-06/07 |
| NFR-R1-21 | PAT-R1-02~12 | EV-R1-08 |
| NFR-R1-22 | PAT-R1-02~12 | EV-R1-03~09 |
| NFR-R1-23 | PAT-R1-01/02/06/12 | EV-R1-01/06/09 |
| NFR-R1-24 | PAT-R1-01/11/12 | EV-R1-09 |

| 선택 | 주 Pattern | 보완 경계 |
|---|---|---|
| R1ND1=A | PAT-R1-03 | PAT-R1-02/06/08 |
| R1ND2=A | PAT-R1-04 | PAT-R1-01/02/10 |
| R1ND3=A | PAT-R1-05 | PAT-R1-09/12 |
| R1ND4=A | PAT-R1-06 | PAT-R1-02/08 |
| R1ND5=A | PAT-R1-07 | PAT-R1-01/08/12 |
| R1ND6=A | PAT-R1-02 | PAT-R1-03/04/12 |
| R1ND7=A | PAT-R1-08 | PAT-R1-02/07/12 |
| R1ND8=A | PAT-R1-09 | PAT-R1-05/10 |
| R1ND9=A | PAT-R1-10 | PAT-R1-04/05/06/09 |

PAT-R1-01/11/12는 승인된 구조·검증·계약/관측도 구체화한다. Hypothesis/fast-check, PROP-R1-01~16, PR/release-nightly profile, 최초/변경 시 실제 integration 및 월간/변경 시 restore를 유지한다.

## 5. 확장 준수 — NFR Design 수준

Compliant는 패턴/port/검증 책임의 충족이다. 실제 resource 설정과 실행 결과는 EV-R1 및 VAL-R1로 판정한다.

| Rule | 상태 | 근거 또는 N/A 사유 |
|---|---|---|
| SECURITY-01 | Compliant | FileVault/local staging, 별도 encrypted archive, TLS 검증과 locked-resource 거부를 PAT-R1-01/10/12 및 component capability에 결속 |
| SECURITY-02 | N/A | 신규 외부 intermediary 없음; 기존 EDGE 접근 로그 책임 계승 |
| SECURITY-03 | Compliant | PAT-R1-09/12의 typed/redacted audit/telemetry와 timestamp/level/correlation |
| SECURITY-04 | N/A | 새 HTML/UI 없음; 기존 BFF/CSP 요구 유지 |
| SECURITY-05 | Compliant | PAT-R1-01/03/05/11/12의 allowlist/범위/codec/path/parameter validation |
| SECURITY-06 | Compliant | PAT-R1-01/02/09의 reader/helper/tool/audit/retention 분리와 최소 credential |
| SECURITY-07 | Compliant | private/loopback/TLS 및 generator offline/scanner scoped egress를 role capability로 배정 |
| SECURITY-08 | Compliant | PAT-R1-02의 non-renewing current-authority/resource guard와 거부 경계 |
| SECURITY-09 | Compliant | frozen 최소 role closure, 안전한 오류/default apply·plaintext fallback 금지 |
| SECURITY-10 | Compliant | PAT-R1-11의 actual frozen inventory/report/coverage/예외 및 artifact/도구 pin |
| SECURITY-11 | Compliant | PAT-R1-02/06/07의 오용/경합/한도/서명 서비스 남용 방지 |
| SECURITY-12 | Compliant | 기존 U3/운영 MFA·session 정책과 Keychain/current grant, bg grant 비연장 |
| SECURITY-13 | Compliant | PAT-R1-03~05/10~12의 immutable input/linearization/provenance/canonical signature와 GitHub review 경계 |
| SECURITY-14 | Compliant | PAT-R1-09/10/12의 application self-delete 불가 감사, 90일+ 참조 보호/경보 |
| SECURITY-15 | Compliant | UNKNOWN/권한·clock·durability 실패의 중지, scoped cleanup 및 안전한 결과 |
| RESILIENCY-01 | Compliant | R1C/R1R/OBS와 native resource/authority 의존 및 장애 영향 분리 |
| RESILIENCY-02 | Compliant | 승인된 single-host 목표 및 PAT-R1-06/08/10의 조건부 restart/RPO/RTO |
| RESILIENCY-03 | Compliant | frozen plan/policy/domain owner review와 기존 GitHub review/git-flow 유지 |
| RESILIENCY-04 | Compliant | PAT-R1-03/04/10의 step checkpoint, generation pin, 새 revision의 호환 rollback |
| RESILIENCY-05 | Compliant | PAT-R1-09/12의 구조화 logs/metrics/trace 및 기존 heartbeat/IR 연결 |
| RESILIENCY-06 | Compliant | PAT-R1-01/06/07/12의 8+2 직접 health와 실제 dependency/subject 구분 |
| RESILIENCY-07 | Compliant | unknown I/O, stale proof, disk/RSS/backlog/backup/clock/key 상태의 명시 관측 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | PAT-R1-06/07의 host lane/bulkhead/자식 합산/LRU 및 backpressure |
| RESILIENCY-10 | Compliant | PAT-R1-06~08의 bounded I/O/cancel/circuit breaker/격리 및 fail-closed |
| RESILIENCY-11 | Compliant | PAT-R1-10의 backup-and-restore와 operator unlock/새 incarnation |
| RESILIENCY-12 | Compliant | consistent capture/pin/encrypted remote retrieval/실제 restore 및 보존 |
| RESILIENCY-13 | Compliant | PAT-R1-03~06/10의 actual receipt/guard/quiescence 기반 복구·명시 재개 |
| RESILIENCY-14 | Compliant | VAL-R1-01~18, 승인된 CI/실제 integration/월간 restore 및 EV trace |
| RESILIENCY-15 | Compliant | 기존 경량 IR/COE와 실패/재조정/잔여 위험의 감사/관측 연결 |
| PBT-01 | N/A - NFR Design 실행 | FD PROP-R1-01~16을 pattern/VAL 검증으로 연결; 속성 요구 유지 |
| PBT-02 | N/A - NFR Design 실행 | codec/journal/envelope round-trip은 Code의 필수 검증 |
| PBT-03 | N/A - NFR Design 실행 | fence/head/currentness 불변식은 Code에서 검증 |
| PBT-04 | N/A - NFR Design 실행 | retry/import/outbox 멱등성 요구를 보존 |
| PBT-05 | N/A - NFR Design 실행 | 독립 ledger/head/breaker/clock model을 Code 계획에 연결 |
| PBT-06 | N/A - NFR Design 실행 | revoke/crash/late result/GC/restore stateful sequence 명세 |
| PBT-07 | N/A - NFR Design 실행 | domain/경계/오류 generator는 Code 구현 대상 |
| PBT-08 | N/A - NFR Design 실행 | shrinking/seed/CI 및 최소 반례 보존을 계승 |
| PBT-09 | N/A - NFR Design 실행 | 승인된 pytest/Hypothesis 및 Vitest/fast-check 선택 유지 |
| PBT-10 | N/A - NFR Design 실행 | F06/F08/F13 예시 회귀+property+실제 I/O 인수 병행 |
