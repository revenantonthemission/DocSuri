# REM-1 — NFR Requirements

**단계**: CONSTRUCTION / NFR Requirements
**상태**: 작성·검증 및 R1NFRR1=A 승인 완료 (2026-09-19; `../../plans/rem-1-platform-integrity-nfr-requirements-plan.md`).
**입력**: R1NFR1~R1NFR13=A, R1FDR1=A, UGR1=A, DAD1=A, WPR2=A
**선택 기록**: `../../plans/rem-1-platform-integrity-nfr-requirements-plan.md` §9 (2026-09-19)
**Companion**: `tech-stack-decisions.md`, `../functional-design/`의 E-R1/FL-R1/BR-R1/PROP-R1 정의

## 1. 적용 범위와 판정 수준

REM-1은 **High** 중요도의 platform 기반이다. R1C는 read-only evidence/compatibility daemon, R1R은 명시적 검증/privileged runner, OBS는 각 service가 구현하는 공통 관측 규약이다. R1C 중단은 운영 조회를 저하시키고 R1R/검증 실패는 관련 build/deploy를 차단한다. 정상 사용자 data-plane에 R1C의 실시간 RPC를 새 선결조건으로 추가하지 않는다.

이 문서는 선택된 품질 목표/제약/인수 방법을 확정한다. 목표 달성은 후속 구현 및 격리 검증 증거로 판정한다. 기존 U1~U16의 domain authority, single-Mac best-effort, local G1과 전체 release의 G2~G5 구분을 계승한다. 가용성 백분율 SLA 또는 자동 host failover는 없다.

2026-09-19 계획 단계의 read-only 관측은 24 GiB RAM, CPU physical/logical 14/14, data volume 97%·약 15.5 GiB free, FileVault Off였다. 이는 수치 선정의 근거이며 현재 host가 아래 NFR을 충족한다는 증거가 아니다. 적용 시 free space/암호화/credential/backup 상태를 다시 검증한다.

## 2. 요구사항 catalogue

아래 ID가 REM-1의 NFR 기준이다. 수치의 단일 정의는 §3~5, 인수 증거는 §6, 기술 선택은 companion 문서에 둔다.

| ID | 요구사항 / 필수 결과 | 인수 및 실패 의미 | Trace |
|---|---|---|---|
| NFR-R1-01 | 독립 frozen release: 선택한 Python/Node family, exact dependency/tool/image pin, 비편집 wheel와 지원 consumer manifest를 사용한다. R1C/R1R의 entry·권한·설치 closure를 분리한다. | repo PYTHONPATH/editable tree 없이 boot/검증 가능. 지원 version/필수 module 누락은 unready이며 silent skip 없음 | R1NFR1; F06/F08/F13; BR-R1-03/14/17 |
| NFR-R1-02 | control metadata는 전용 Postgres schema/role에 durable 저장한다. immutable bundle/report와 control bootstrap/recovery 한정 local journal도 복구 범위에 포함한다. | 첫 effect 전에 intent/UNKNOWN 기록의 내구성 확인. 일반 control-store 장애를 local journal fallback으로 우회하지 않음 | R1NFR2; E-R1-09~13/21~23; BR-R1-11 |
| NFR-R1-03 | target effect+ledger의 step 원자성, target별 직렬화/fencing, durable checkpoint 및 authoritative 재조정을 보장한다. | crash/lost receipt/경쟁 시 중복 effect 0. 실제 종료/무효화를 모르면 UNKNOWN이며 다음 mutation 금지 | R1NFR2/5; F08/RJ-AC12; BR-R1-07~12 |
| NFR-R1-04 | 조회/health/runner를 §3.1의 동시성/RSS 범위로 격리한다. 같은 host의 여러 실행이 상한을 각각 복제할 수 없다. | 포화 시 bounded busy/보류. health가 worker queue/긴 검사 완료를 기다리지 않음 | R1NFR3; NFR-S1; BR-R1-01/21 |
| NFR-R1-05 | 새 write 전에 추가 peak 추정과 10 GiB reserve/2배 peak 조건을 검증하고 실행 중 headroom을 관측한다. | 부족/추정 불가면 새 write 보류. corpus/감사/미확정 효과 자료를 임의 삭제해 진행하지 않음 | R1NFR3; NFR-C1; BR-R1-06/11 |
| NFR-R1-06 | typed/allowlisted 입력에 §3.2의 byte/count/depth bounds를 적용한다. 원 SQL/artifact와 요청 문자열을 분리하고 safe parsing/parameter binding을 사용한다. | type/format/limit 위반은 처리 전 명시 실패. silent truncation, path escape, 원격 ref fallback 없음 | R1NFR4; SEC-5/13; BR-R1-02/13~15 |
| NFR-R1-07 | 정상 5 requests/s·10분 profile에서 warm metadata p95 ≤250ms, liveness p95 ≤100ms를 목표로 한다. cold/degraded 측정은 분리한다. | 빠른 실패만으로 정상 성능 합격을 만들지 않음. §6의 실제 부하/성공/오류/latency 원자료 필요 | R1NFR3/5; US-R4/5; BR-R1-21 |
| NFR-R1-08 | §4의 nested deadline과 bounded read-only retry를 적용한다. mutation 자동 retry, 무한 wait 및 취소 후 무근거 no-effect 판정은 금지한다. | timeout/cancel은 safe reason과 알려진 effect assurance를 반환. in-flight effect가 불명확하면 재조정 | R1NFR5; RES-9; BR-R1-08/11/12 |
| NFR-R1-09 | build/release별 및 사용 중 artifact의 24h supply-chain 재검사, 관측/feed freshness, current head/target 검증을 수행한다. | PENDING/실패/누락/stale를 과거 PASS로 덮지 않음. readonly 조회가 authoritative 재검사/publication을 시작하지 않음 | R1NFR6; F06; BR-R1-20 |
| NFR-R1-10 | mutation 승인 최대 30분, exact source-unreachable 예외 최대 7일. 현재 source grant/대상/목적/철회/clock를 검증한다. | grace/자동 연장/범위 확대 없음. mTLS identity나 저장된 승인만으로 현재 caller 권한을 만들지 않음 | R1NFR7; SEC-8/12; BR-R1-12/19 |
| NFR-R1-11 | exact bytes SHA-256, versioned JCS metadata, detached Ed25519 provenance와 role-scoped Keychain을 사용한다. | hash/서명 검증과 current authority를 모두 확인. 불명확 key/trust/revocation은 관련 capability 차단 | R1NFR8; SEC-6/12/13; BR-R1-02/20 |
| NFR-R1-12 | 관련 local data volume을 FileVault로 보호하고 off-host backup은 별도 암호화한다. cold boot의 preboot console unlock/login을 복구 절차에 포함한다. | 필요한 volume/key가 잠기거나 보호를 확인할 수 없으면 unavailable. 자동 로그인/SSH만으로 cold boot 복구를 보장하지 않음 | R1NFR9; SEC-1; C-4/5 |
| NFR-R1-13 | TCP는 TLS 1.2+ 및 peer certificate 검증, service hop은 mTLS+현재 caller 권한을 사용한다. R1C/store listener는 private/loopback이며 외부 routing은 기존 BFF/gateway 경계다. | plaintext/TLS verification bypass/default credential로 성공 처리하지 않음. 공개 generic platform mutation route 없음 | R1NFR8; SEC-1/6/7/8/9 |
| NFR-R1-14 | §5.1의 90일/14일/7일 보존과 active/unresolved 참조 보호, 검증된 암호화 archive를 적용한다. | 보존 만료와 freshness를 구분. GC로 dedup/migration/unknown 증거를 잃거나 archive 미확인 원본을 삭제하지 않음 | R1NFR10; SEC-14; BR-R1-09~11/20 |
| NFR-R1-15 | RPO ≤24h, 사고 인지부터 검증된 REM-1 복구까지 RTO ≤4h, 정상 host/dependency 조건의 daemon restart-to-ready ≤60s를 목표로 한다. | 실제 사람/host/key 준비 시간을 포함해 보고. daemon 재시작과 privileged run 재개를 구분 | R1NFR9/11; RES-2/10; BR-R1-11/22 |
| NFR-R1-16 | control DB, target ledger, immutable bundles/evidence, bootstrap journal 및 trust/key 복구 재료의 encrypted off-host backup/restore coverage를 입증한다. | local iCloud copy/목록 조회만으로 원격 복구 합격 불가. 새 incarnation/current 권한 및 미완료 run 재조정 필요 | R1NFR2/11; RES-10/12; RJ-AC12 |
| NFR-R1-17 | pip-audit/pnpm audit/Syft/Grype 및 CycloneDX를 실제 frozen production/tool closure에 결속한다. required coverage, trusted source·지원/사용 상태를 검증한다. | unapproved known critical/high 0. 오류/미지원/누락을 clean으로 만들거나 first-party provenance를 제거하지 않음 | R1NFR12; F06; BR-R1-17~19 |
| NFR-R1-18 | 모든 선언된 local schema/ref/consumer의 generated wire 및 명시 view adapter를 offline 검증하고 complete candidate만 활성화한다. | 같은 frozen 입력의 output byte/set 동치, 실제 Python/TS build 소비, 실패 non-success/부분 bundle 비노출 | R1NFR1/4; F13; BR-R1-13~16 |
| NFR-R1-19 | structured/redacted logs, role별 metrics/trace, 직접 shallow/deep health와 기존 외부 heartbeat/경보/COE를 연결한다. | liveness, dependency readiness, subject gate 및 phase/종단 완료를 구분. 알려지지 않은 의존성을 healthy로 표시하지 않음 | US-R4/5; NFR-O1; BR-R1-21/22 |
| NFR-R1-20 | critical audit는 actor/시각/목적/대상/before-after fingerprint/outcome을 추가 전용 경로에 남긴다. 일반 application role의 자기 감사 수정/삭제를 금지한다. | critical 기록 불능은 새 mutation 차단. 일반 metrics 실패는 기존 committed effect의 사실을 바꾸지 않음 | R1NFR10; SEC-3/13/14/15; BR-R1-21 |
| NFR-R1-21 | Python pytest+Hypothesis, TypeScript Vitest+fast-check 및 §6.2 profile을 사용한다. shrinking/seed/반례 회귀와 domain generator를 유지한다. | PROP-R1-01~16의 applicable 구현을 example+PBT로 매핑. CI 실패를 재시도 성공으로 숨기지 않음 | R1NFR13; QT-4/12; PBT-09 |
| NFR-R1-22 | 실제 격리 Postgres/filesystem/consumer/scanner 실패·중단·경쟁 시험과 월간/복구 경로 변경 시 restore drill을 수행한다. | model/mock 통과만으로 I/O 원자성/복구를 합격시키지 않음. production namespace/credential로 시험하지 않음 | R1NFR13; F06/F08/F13/RJ-AC12 |
| NFR-R1-23 | CLI human summary/versioned machine output, safe non-success, 명시적 action/help, GitHub review/git-flow 및 domain/shared owner review를 유지한다. | 무인자 default apply, secret/내부 경로 노출, 오류를 success exit로 감추는 경로 없음 | NFR-M1; RES-3/11; BR-R1-01/21 |
| NFR-R1-24 | artifact/target/policy/검증 scope와 local G1/전체 release 인수를 구분하고 각 다음 stage의 검증 책임을 추적한다. | REM-2/3/4가 필요한 US-R4/5/RJ-AC12를 REM-1 local 결과만으로 종결하지 않음 | WPR2/UGR1; BR-R1-22 |

## 3. Capacity와 입력 envelope

### 3.1 역할별 admission 및 자원

| 표면 | 선택된 기준 | 인수 조건 |
|---|---|---|
| R1C metadata/evidence 조회 | 동시 8개 | 프로세스 수 증가로 상한이 곱해지지 않으며 초과는 bounded 거부/보류 |
| R1C health | 별도 동시 2개 | 긴 runner/업무 조회 pool과 분리된 admission 및 dependency 예산 |
| 정상 조회 부하 | 5 requests/s, 10분 | §6의 정해진 dataset/mix와 정상/오류 수 및 latency 기록 |
| R1R heavy lane | host 전체 1개 | generator/scanner/privileged mutation을 동시에 별도 full-budget lane으로 시작하지 않음; target fence도 적용 |
| R1C RSS | 512 MiB | daemon의 실제 peak를 측정 |
| R1R RSS | runner+그 자식 process 합계 2 GiB | subprocess를 합계에서 빼지 않음. 공유 datastore 자원은 별도 관측/입력 제한으로 보호 |
| write disk reserve | 10 GiB | 아래 peak 사전 조건과 실행 중 headroom 확인 |

새 write의 사전 조건은 `free >= 10 GiB + 2 × estimated additional peak`다. peak는 동시에 남는 staging/new bundle/임시 결과/local backup delta를 합산하며 이미 차지하는 old bundle은 현재 free에 반영한다. REM-1 작업 사이에서 같은 여유를 중복 예약하지 않도록 조정하고 각 새 write 경계에서 재검증한다. 다른 host workload의 disk 증가도 관측하며 최초 검사가 이후 전체 host의 여유를 예약한 것처럼 보장하지 않는다. estimate가 없거나 불확실하면 실행 가능하다고 추정하지 않는다.

read-only 진단/health를 유지하고 disk pressure를 경보한다. headroom/RSS를 초과하면 새 단계 시작을 막고 진행 중 작업은 안전한 중지·재조정으로 전환한다. resource 제한을 맞추기 위해 active/unresolved 증거를 삭제하거나 불명확 I/O의 fence를 해제하지 않는다. 수치 상한을 실제로 집행·관측하는 Mac/launchd 수단은 NFR/Infrastructure Design에서 입증한다.

### 3.2 Byte/count/depth limits

KiB/MiB/GiB는 각각 2의 10/20/30제곱 bytes다. byte 한도는 decoded JSON/실제 output bytes에 적용하며 압축 크기만으로 우회하지 않는다. 각 한도와 resource/time 한도를 **모두** 만족해야 한다.

| 대상 | 최대값 | 범위 |
|---|---|---|
| HTTP 입력 | 256 KiB | 파라미터/형식 검증과 별개로 framework 입구에서 bounded 수신 |
| evidence 응답/page | 1 MiB, 100항목 | 완전한 summary/ref 또는 명시 pagination; raw report를 조용히 자르지 않음 |
| manifest/schema 단일 자료 | 16 MiB | CLI/offline 입력에도 적용 |
| schema catalog 합계 | 64 MiB | 전 선언 local resource 집합 |
| schema resource | 1,000개 | 발견/선언/참조 closure의 중복·누락도 검증 |
| ref edge | 20,000개 | 실제 logical graph 기준 |
| migration spec | 2,000개 | registry 전체 validation과 scoped plan의 완전성 유지 |
| JSON nesting | 64 | 문서 nesting; 지원되는 recursive ref cycle의 금지로 바꾸지 않음 |
| generated bundle | 256 MiB, 10,000 files | complete output set 및 path/collision 검증 |
| inventory occurrence | 100,000개 | 다른 artifact/occurrence를 package 이름만으로 합치지 않음 |
| raw scanner report | 64 MiB | bounded file/stream 처리, API는 안전한 summary/ref |

초과는 validation/resource failure로 보고하고 PASS/완료 output으로 일부만 공개하지 않는다. 현재 schema 개수에 맞춰 target subset을 hard-code하지 않으며 새 선언 target도 같은 coverage/한도를 따른다.

## 4. 시간, freshness 및 권한

### 4.1 Deadline profile

| 작업 | 선택된 cap/목표 | 의미 |
|---|---|---|
| warm metadata 조회 | p95 ≤250ms | §6 정상 profile 목표 |
| warm liveness | p95 ≤100ms | 생존 응답 목표, 실제 dependency/subject gate와 별도 |
| observation/deep readiness | 총 3s | TLS/인가/현재 관측/응답을 포함한 상위 deadline |
| DB/authority connection | 1s | 남은 상위 deadline이 더 짧으면 그 경계 적용 |
| DB/authority 개별 read | 2s | 직렬 호출 합계가 총 deadline을 늘리지 않음 |
| read-only 외부 network | connect 5s/read 30s, 최대 2회 추가 retry | 최초 요청 포함 최대 3회; retry/backoff도 상위 budget 안 |
| code generation action | 10분 | complete target 생성/검증 action cap |
| scanner action | 15분 | tool/필수 feed/보고서 확인을 포함한 action cap |
| migration lock 대기 | 5s | 획득 못하면 해당 시도 중지; 유효 lease를 추정하지 않음 |
| migration step | 최대 5분 | 현재 승인/fence/attempt deadline보다 길 수 없음 |
| migration attempt | 최대 30분 | 시작 기준; paused logical RunIntent의 전체 수명이 아님 |

`effectiveDeadline`은 action/attempt deadline, 현재 approval/source grant/fence의 유효 끝 중 가장 이른 값이다. 승인 30분은 **발급** 기준이며 attempt를 늦게 시작하거나 새 process를 띄워도 다시 30분이 생기지 않는다. 충분한 안전한 실행/abort 조건을 확보하지 못하면 새 effect를 열지 않는다. 각 도구 cap은 합쳐서 하나의 무조건적 완료 보장이 아니다.

DB/authority 실패를 무한 재시도로 가리지 않는다. read-only retry도 중첩 계층에서 곱해지지 않게 추적한다. mutation/activation 실패는 자동 반복하지 않고 FD의 COMMITTED/NO_EFFECT_CONFIRMED/UNKNOWN 증거로 재조정한다. timeout/SIGTERM 이후 외부 I/O의 종료를 증명하지 못하면 UNKNOWN을 유지한다.

### 4.2 Evidence 및 approval validity

- build/release마다 exact artifact/closure를 검사하고 사용 중 artifact는 **24시간마다** authoritative verify-only 검사를 수행한다. 최대 advisory 관측 age는 **24시간**이며 만료 경계에서 current eligible로 사용하지 않는다.
- local scanner DB는 검증된 source/update 시각·revision/digest를 기록한다. online advisory API는 trusted query/응답 snapshot과 조회 시각/제공된 provenance를 기록한다. 제공되지 않는 전역 DB revision을 발명하지 않는다. source-kind별 필수 freshness/coverage는 고정 policy로 검증하며, 오래된 DB를 새 scan 시각으로 재날짜화하지 않는다.
- 스케줄 지연/도구 오류/새 revision PENDING은 current INCOMPLETE/STALE 등의 근거다. 이전 PASS로 fallback하지 않는다. 이 주기는 dependency 업데이트 또는 privileged apply 스케줄이 아니다.
- registry/binding proof는 exact input/toolchain/template/policy가 같을 때 재사용할 수 있으나 current head/target incarnation/권한/필수 capability는 매 평가에서 확인한다. immutable proof와 현재 사실을 분리한다.
- mutation ApprovalBinding은 발급부터 **최대 30분**, source-unreachable exception은 발급부터 **최대 7일**이다. `[validFrom, validUntil)`이며 `now == validUntil`은 만료다. source grant가 먼저 만료/철회되면 더 짧은 범위를 따른다.
- current clock/revocation을 신뢰할 수 없거나 exact subject/closure/plan/policy가 달라지면 거부한다. grace/묵시적 재사용/자동 갱신은 없다. 기록 보존 기간은 이러한 실행 권한을 연장하지 않는다.

## 5. 보존, 암호화 및 복구

### 5.1 Retention profile

| 분류 | 최소 보존 / 정리 조건 |
|---|---|
| critical audit, attestation, raw verification report | 최소 90일; 필요한 active/unresolved 참조가 있으면 연장 |
| 일반 structured log/metrics | 14일; critical 감사와 별도 경로/분류 |
| 참조 없는 실패 candidate | 7일; 실제 참조/미확정 effect가 없음을 확인한 뒤 정리 |
| active/rollback-needed bundle, 유효 승인/예외, unresolved run | age만으로 정리하지 않고 참조 종료/복구 가능성을 확인 |
| current target의 migration/dedup 증거 | 해당 target/효과/재전달을 안전하게 판정할 수 있는 동안 유지; history 삭제로 재실행을 허용하지 않음 |

오래된 자료는 검증 가능한 암호화 archive로 이동해 local 사용량을 제한할 수 있다. 원격본의 무결성/회수 가능성/필수 참조를 확인하기 전 local 원본을 삭제하지 않는다. cleanup은 별도 제한된 권한으로 집행하고 일반 application role은 자기 critical 감사 이력을 수정/삭제할 수 없다. credential/PII/private 본문을 일반 로그나 오류에 보존하지 않는다.

### 5.2 Encryption / restart / DR

- FileVault가 관련 data volume을 보호하고 backup은 off-host로 이동하기 전 별도로 암호화돼야 한다. TLS 1.2+ 및 인증서 검증은 loopback에서도 유지한다. plaintext fallback 또는 certificate 검증 해제는 허용하지 않는다.
- cold boot 후 preboot console unlock/login과 Keychain/volume 접근 확인을 운영 절차에 포함한다. FileVault와 기존 무인 자동 로그인 또는 전원 복구 직후 SSH-only unlock이 함께 성립한다고 가정하지 않는다.
- **RPO ≤24h**: 마지막으로 검증된 off-host 복구 집합의 실제 snapshot/cut 시각으로 data-loss window를 계산한다. copy/re-upload 시각으로 오래된 backup의 나이를 초기화하지 않는다.
- **RTO ≤4h**: 사고 인지부터 REM-1의 현재 권한/target/evidence를 검증하고 운영 복구를 완료할 때까지다. 사람 응답, 교체 host 조달, unlock/key 복구 및 실제 중단 시간을 포함해 기록한다. 준비된 drill 환경의 준비 시간을 실제 장애에서 0으로 가정하지 않는다.
- **daemon restart-to-ready ≤60s**: 정상 host/dependency가 준비되고 명시적 daemon 시작/재시작이 이뤄진 조건의 목표다. 전체 cold-boot RTO와 다르며 R1R privileged mutation 자동 재개를 뜻하지 않는다.
- backup manifest는 control DB, 관련 target ledger, immutable bundles/evidence, bootstrap journal 및 trust/key 복구 재료의 coverage/cut/hash를 연결한다. 여러 저장소가 자동으로 같은 시점이라고 가정하지 않고 일관된 참조와 재조정 가능성을 검증한다.
- 원격본 회수와 격리된 실제 restore/boot/current evaluation을 확인해야 한다. `pg_restore --list`, local iCloud 폴더 존재 또는 upload 요청 성공만으로 완료하지 않는다.
- restore된 새 incarnation은 새 current target이다. 과거 승인/lease/RunIntent를 그대로 실행하지 않고 historical proof와 현재 postcondition을 대조해 승인된 재조정/후속 plan을 만든다.

## 6. 검증 및 인수 증거

### 6.1 공통 측정 원칙

1. frozen artifact/lock/tool/정책/fixture digest, hardware/OS/runtime, load mix, warm-up/cold 조건과 시작·종료 시각을 기록한다. 정상 5 requests/s·10분은 **3,000개 요청 제시**를 기준으로 요청/처리/거부/오류 수를 함께 보고한다.
2. metadata와 health의 latency를 분리하고 TLS/인가/current observation을 정상 경로에서 생략하지 않는다. 대상 record 수/응답 크기·health probe 부하는 측정 manifest에 명시한다. 정상 valid-input/healthy-dependency profile의 예상치 못한 실패/유실/timeout은 성능 합격으로 처리하지 않는다.
3. cold start, 한 heavy runner와의 자원 경쟁, overload 및 dependency 장애를 별도 scenario로 측정한다. 모든 경우에 bounded failure/readiness/비변경 보장은 유지하며 바깥 조건의 결과를 정상 p95로 섞어 숨기지 않는다.
4. byte/count/depth 한도의 정확한 경계와 초과, active/unresolved GC, missing/expired/새 head/late PASS, clock/revocation 실패를 포함한다. 최대 개별 input이 모든 다른 자원 한도에서도 반드시 성공한다는 뜻은 아니다.
5. live production 데이터/credential을 시험 입력으로 사용하지 않는다. 각 시험은 격리 namespace·역할·자원 budget과 복구 가능한 fixtures에서 수행한다.

### 6.2 PBT / CI profile

| 실행 | pure property당 examples | stateful property당 sequences | sequence당 최대 commands |
|---|---:|---:|---:|
| PR | 200 | 50 | 50 |
| release/nightly | 2,000 | 200 | 100 |

Python은 pytest+Hypothesis, TypeScript는 Vitest+fast-check를 사용한다. 범위에 맞는 domain generator, 빈/경계/실패 sequence, 각 command 뒤 invariant/oracle 비교, 자동 shrinking과 기록/고정된 seed를 유지한다. framework의 추가 shrink/replay 실행을 생략해 표의 숫자에 억지로 맞추지 않는다. discovered minimal counterexample은 영구 example regression으로 보존한다.

현재 property catalogue는 FD의 PROP-R1-01~16이다. Code Generation 계획은 각 property/언어/실제 구현과 test step을 명시적으로 연결해야 한다. suite success만으로 실제 I/O 인수를 대신하지 않는다.

### 6.3 Acceptance evidence matrix

| Evidence | 검증 대상 | 필수 증거 / gate |
|---|---|---|
| EV-R1-01 | 독립 artifact/consumer 호환 | 비편집 설치, role별 closure, registry/operation/schema/worker 조합과 실제 Python/TS import/build; G1 및 후속 변경 |
| EV-R1-02 | capacity/성능/input | §3/4/6.1의 정상/초과/실패 수와 latency/RSS/disk 원자료. capability를 거부한 경우도 별도 기록; G1 |
| EV-R1-03 | F08 migration/bootstrap | fresh/restore 격리 Postgres의 모든 mounted module, evidence/glossary 실제 요청, legacy ambiguity, changed SQL, 두 process 경쟁/중단/ledger 원자성; G1 |
| EV-R1-04 | F13 bindings/publication | 모든 local ref/declared target, 실제 소비/visibility/adapter fixtures, network 차단, generator 실패 및 activation 중단의 old-or-complete-new 관측; G1 |
| EV-R1-05 | F06 frozen supply chain | patched lock/installed inventory/image digest/SBOM/tool·feed provenance, 각 coverage 결과, 원 finding 및 exact exception/expiry 판정; G1와 최종 artifact 재검사 |
| EV-R1-06 | 권한/암호화/감사 | 현재 권한/목적/issuer/audience/철회, TLS/certificate 부정 사례, Keychain role, FileVault/backup 보호, audit self-delete 거부 및 일반 로그 비노출 |
| EV-R1-07 | backup/restore/reconcile | 원격본 회수·coverage/hash, 실제 restore, 새 incarnation/currentness, unknown run 및 expired approval 처리; 최초 release/월간/복구 경로 변경 및 G5 |
| EV-R1-08 | Full PBT + 회귀 | PROP-R1-01~16의 applicable 구현, profile/seed/shrunk case 및 permanent counterexample 결과; PR/release/nightly |
| EV-R1-09 | US-R4/US-R5/RJ-AC12 | REM-1의 직접 health/관측/복구 증거와 후속 REM-2/3/4 실제 local/다중 process/queue/재연결/복구 결과를 연결; 최종 G4/G5 |

실제 Postgres/filesystem/consumer 중단·경쟁 검증은 최초 release와 관련 storage/fence 변경 시 수행한다. Linux CI의 pure/contract 검증과 macOS arm64의 실제 배포/파일 원자성 검증을 구분한다. restore drill은 매월 및 복구 경로 변경 시 수행한다. 전체 trace의 최종 통합은 모든 unit 이후 Build and Test에서 확인한다.

## 7. 결정 추적성

| 결정 | NFR | 검증 증거 |
|---|---|---|
| R1NFR1=A | NFR-R1-01/18/23 | EV-R1-01/04/05 |
| R1NFR2=A | NFR-R1-02/03/16 | EV-R1-03/07 |
| R1NFR3=A | NFR-R1-04/05 | EV-R1-02 |
| R1NFR4=A | NFR-R1-06 | EV-R1-02/04 |
| R1NFR5=A | NFR-R1-07/08 | EV-R1-02/03/09 |
| R1NFR6=A | NFR-R1-09 | EV-R1-05/09 |
| R1NFR7=A | NFR-R1-10 | EV-R1-05/06/07 |
| R1NFR8=A | NFR-R1-11/13 | EV-R1-01/06 |
| R1NFR9=A | NFR-R1-12/15/16 | EV-R1-06/07 |
| R1NFR10=A | NFR-R1-14/20 | EV-R1-06/07 |
| R1NFR11=A | NFR-R1-15/16 | EV-R1-07/09 |
| R1NFR12=A | NFR-R1-17 | EV-R1-05 |
| R1NFR13=A | NFR-R1-21/22 | EV-R1-03~09 |

NFR-R1-19/23/24는 승인된 US-R4/5, NFR-O1/M1, RES-3/11, C-13 및 WPR2/UGR1의 공통 제약도 계승한다. F06/F08/F13과 RJ-AC12의 domain 기준은 Functional Design에서 변경하지 않는다.

## 8. 확장 준수 — NFR Requirements 수준

Compliant는 요구사항/선택/검증 책임이 명세됐다는 뜻이다. 물리 설정/실행 합격은 EV-R1 및 후속 stage의 증거로 판정한다. N/A는 이 unit/stage의 적용성이지 활성 확장 해제가 아니다.

| Rule | 상태 | 근거 또는 N/A 사유 |
|---|---|---|
| SECURITY-01 | Compliant | NFR-R1-12/13/16의 FileVault, 별도 encrypted backup, TLS 1.2+ 및 negative 인수 |
| SECURITY-02 | N/A | REM-1에 외부 traffic intermediary를 새로 만들지 않음. 기존 EDGE 접근 로그 책임 계승; service 로그는 SECURITY-03 |
| SECURITY-03 | Compliant | NFR-R1-19/20의 structured/redacted timestamp/level/correlation, 기존 중앙 관측 연결 |
| SECURITY-04 | N/A | 새 HTML/UI 없음. 기존 BFF/UI header/CSP 요구 유지 |
| SECURITY-05 | Compliant | NFR-R1-06의 type/format/byte/count/depth 및 safe parsing/parameter binding |
| SECURITY-06 | Compliant | NFR-R1-01/02/10/11/20의 reader/runner/bootstrap/key/audit 권한 분리 |
| SECURITY-07 | Compliant | NFR-R1-13의 private/loopback, 기존 BFF/gateway 및 scoped outbound; 실제 배선은 Infrastructure |
| SECURITY-08 | Compliant | NFR-R1-10/13의 current object/purpose/source grant와 인증서·service identity 분리 |
| SECURITY-09 | Compliant | NFR-R1-01/13/17/23의 supported patched artifact, 최소 closure/default credential 금지/일반화 오류 |
| SECURITY-10 | Compliant | NFR-R1-17과 EV-R1-05의 frozen lock/pin/installed inventory/SBOM/coverage/예외 |
| SECURITY-11 | Compliant | NFR-R1-04~08/10의 admission/bounds/오용·불확정 실패; public rate-limit은 기존 EDGE에서 계승 |
| SECURITY-12 | Compliant | 기존 U3 admin MFA/session 보호와 NFR-R1-10/11의 current grant/Keychain/최소 credential |
| SECURITY-13 | Compliant | NFR-R1-01~03/11/18/20의 provenance/무결성/현재 head/atomicity/audit 및 변경 review |
| SECURITY-14 | Compliant | NFR-R1-14/19/20의 90일+ self-delete 불가 감사, 권한/unknown/backup/capacity 경보 |
| SECURITY-15 | Compliant | NFR-R1-03/06/08/09/23의 bounded safe failure/cleanup/currentness/명시 non-success |
| RESILIENCY-01 | Compliant | §1의 High 및 R1C/R1R/OBS의 장애 영향, local G1/후속 의존 구분 |
| RESILIENCY-02 | Compliant | NFR-R1-15의 RPO 24h/RTO 4h/조건부 60s, 승인된 single-host best-effort 계승 |
| RESILIENCY-03 | Compliant | NFR-R1-23의 기존 GitHub review/git-flow 및 domain/shared owner review |
| RESILIENCY-04 | Compliant | NFR-R1-01/03/18의 versioned 수동 전환/호환 rollback, step 및 publication 원자성 |
| RESILIENCY-05 | Compliant | NFR-R1-19의 logs/metrics/trace/phase 구분, 기존 운영 관측/heartbeat 연결 |
| RESILIENCY-06 | Compliant | NFR-R1-04/07/08/19의 독립 shallow/deep health 및 실제 의존 실패 반영 |
| RESILIENCY-07 | Compliant | NFR-R1-05/09/16/19의 disk/freshness/backup/unknown 및 포화 경보 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | NFR-R1-04/05/06의 bounded local capacity/backpressure; horizontal autoscale N/A |
| RESILIENCY-10 | Compliant | NFR-R1-04/08/19의 분리된 budget/timeout/종료·저하 의미; 패턴 배치는 다음 단계 |
| RESILIENCY-11 | Compliant | NFR-R1-15/16의 기존 backup-and-restore 전략 및 operator unlock |
| RESILIENCY-12 | Compliant | NFR-R1-12/14/16의 encrypted off-host backup/coverage/retention/실제 restore |
| RESILIENCY-13 | Compliant | NFR-R1-03/15/16의 incarnation/current 권한/unknown run 복구 및 단계별 검증 |
| RESILIENCY-14 | Compliant | NFR-R1-21/22와 EV-R1-03~09의 격리 실패/중단/경쟁/월간 restore |
| RESILIENCY-15 | Compliant | NFR-R1-19/20/23의 기존 경보/IR/COE 및 redacted 교정 증거 |
| PBT-01 | N/A - NFR Requirements | FD PROP-R1-01~16 식별 완료; Code 계획에 carry-forward |
| PBT-02 | N/A - NFR Requirements | round-trip 구현/실행은 Code/Build; NFR-R1-21에 요구 유지 |
| PBT-03 | N/A - NFR Requirements | invariant 구현/실행은 Code/Build; NFR-R1-21에 요구 유지 |
| PBT-04 | N/A - NFR Requirements | retry/멱등성 구현/실행은 Code/Build; NFR-R1-03/21에 연결 |
| PBT-05 | N/A - NFR Requirements | oracle 비교 구현은 Code; FD의 독립 reference model 계승 |
| PBT-06 | N/A - NFR Requirements | stateful 구현은 Code; §6.2의 sequence profile 확정 |
| PBT-07 | N/A - NFR Requirements | generator 구현은 Code; domain/boundary/empty 요구 유지 |
| PBT-08 | N/A - NFR Requirements | shrinking/seed/CI 실행 검증은 Code/Build; §6.2에 요구 유지 |
| PBT-09 | Compliant | pytest/Hypothesis 및 Vitest/fast-check 선정/기존 dependency와 새 package 매핑을 tech-stack-decisions.md에 기록 |
| PBT-10 | N/A - NFR Requirements | example+PBT 테스트 구현은 Code; 기존 counterexample과 §6.2 병행 요구 |

## 9. 다음 단계의 확정 항목

- **NFR Design**: Postgres/target별 transaction/fence와 journal 재조정, deadline/resource 집행, effective-currentness/clock/키 rotation·철회, mTLS와 caller 권한, immutable activation, append-only 감사/관측 및 복구 패턴.
- **Infrastructure Design**: 실제 package/port/launchd role/OS UID·Keychain·CA·volume·backup destination, FileVault/unlock와 변경 window, root/consumer 경계, local+off-host 보존/관측 배선.
- **Code Generation / Build and Test**: exact patch/tool/image/report schema pin, frozen artifact의 실제 coverage, EV-R1-01~09 및 PROP-R1-01~16 구현/검증. 물리 수단이 선택된 안전 보장을 제공하지 못하면 관련 capability를 ready로 선언하지 않는다.
