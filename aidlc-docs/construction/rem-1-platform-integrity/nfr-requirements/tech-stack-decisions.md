# REM-1 — Technology Stack Decisions

**단계**: CONSTRUCTION / NFR Requirements
**상태**: 작성·검증 및 R1NFRR1=A 승인 완료 (2026-09-19; `../../plans/rem-1-platform-integrity-nfr-requirements-plan.md`).
**입력**: R1NFR1~R1NFR13=A, R1FDR1=A, DAD1=A, UGR1=A
**Companion**: `nfr-requirements.md`의 NFR-R1-01~24 및 EV-R1-01~09

## 1. 선택 수준과 기준

기술 family/표준/책임은 본 문서가, 수치/유효성/실패/검증 기준은 `nfr-requirements.md`가 정의한다. exact package patch/tool/image/report-schema version은 승인된 family 안에서 실제 freeze 및 F06/consumer 검증을 거쳐 release manifest/lock에 기록한다. `latest`, 동적 resolver 또는 현재 checkout을 고정 버전 증거로 취급하지 않는다.

기존 source의 재사용은 독립 artifact의 범위를 넓히는 근거가 아니다. C3 composition -> C2 adapters/C1 core/C0 contracts의 DAD1 의존 방향을 유지한다. core가 기존 backend app bootstrap/다른 REM controller를 import해 자동 mutation 또는 live service 순환을 만들지 않는다.

## 2. 결정 catalogue

| ID | 선택 / 근거 | 필수 인수 / 관련 NFR |
|---|---|---|
| TD-R1-01 | **Python 3.13, FastAPI, Pydantic v2, uv, 독립 wheel**. 기존 stack과 검증 도구를 재사용하되 REM-1 자체 package/lock/entry를 둔다. wheel build는 기존 shared/ops의 Hatchling 관례에 맞춘다. | daemon/core/runner closure 분리, frozen 비편집 설치, repo PYTHONPATH 없이 실행; NFR-R1-01/23 |
| TD-R1-02 | **Node 24, pnpm 9, 기존 TypeScript toolchain**. Node는 TS generation/검증 도구의 runtime이며 R1C의 Python runtime과 분리한다. CI Node 20과 선언된 production Node 24 차이를 정렬한다. | exact interpreter/packageManager/lock digest, 실제 consumer compile/build; NFR-R1-01/18 |
| TD-R1-03 | **Postgres logical realm + psycopg 3**. 기존 cluster 안에 control schema/role을 분리하고 명시 transaction을 사용한다. target migration ledger는 target의 step effect와 같은 transaction이다. | reader/publisher/maintenance 권한, durable commit, 동시 실행/중단/reconcile 인수; NFR-R1-02/03 |
| TD-R1-04 | **보호된 local content-addressed filesystem + 한정 bootstrap journal**. immutable bundle/report 및 control realm 최초 bootstrap/복구의 사전 durable 기록을 제공한다. | fsync/atomic publication/복구 의미는 NFR Design에서 증명. 일반 control DB outage의 write fallback 없음; NFR-R1-02/05/16/18 |
| TD-R1-05 | **JSON Schema local registry, jsonschema/referencing, datamodel-code-generator, json-schema-to-typescript**. 현재 도구를 offline/complete-validation adapter 뒤에서 재사용한다. | declared roots/exports, root-less definitions, recursion, unsupported/실패 전파 및 실제 Python/TS 소비; NFR-R1-06/18 |
| TD-R1-06 | **versioned typed PolicySnapshot/CompatibilityManifest**. Pydantic/schema로 유효 설정을 검증하고 fingerprint를 artifact/plan/evaluation에 결속한다. | 임의 환경 변수로 보안/한도를 무효화하지 않음. effective config와 허용 override 추적; NFR-R1-01/04~10/24 |
| TD-R1-07 | **SHA-256 + RFC 8785/JCS + detached Ed25519**. exact source bytes와 metadata canonicalization을 구분하고 검증된 crypto/library를 사용한다. | version/purpose/subject/policy binding, Python/Node 동일 vectors와 부정 사례; NFR-R1-11 |
| TD-R1-08 | **role-scoped macOS Keychain, TLS 1.2+, mTLS + current caller authority**. transport identity와 approval/evidence-signing 및 mutation 권한을 분리한다. | role key 접근·회전/철회·인증서 검증, U3/운영 authority의 현재 목적 권한, secret-free logs; NFR-R1-10/11/13/20 |
| TD-R1-09 | **FileVault + cold-boot operator unlock**. local data volume을 보호하고 preboot console unlock/login 뒤 launchd/OrbStack/Keychain 준비를 확인한다. | 기존 자동 로그인 가정의 운영 정합화, locked-volume/key 실패, 조건부 restart와 전체 RTO 분리; NFR-R1-12/15 |
| TD-R1-10 | **pip-audit, pnpm audit JSON, Syft/Grype, versioned CycloneDX**. ecosystem 및 image/OS inventory를 실제 frozen closure/provenance로 묶는다. | supported coverage, 원 report/DB provenance, exact 예외, unapproved critical/high 0; NFR-R1-09/17 |
| TD-R1-11 | **U6 OBS 계약, structured JSON logging, 기존 metrics/trace/healthchecks.io 연계**. 새 독립 REM 관측 service를 만들지 않고 각 role의 local 계측을 연결한다. | timestamp/level/correlation, 안전한 reason/phase, 직접 deep health, 경보/COE·bounded label; NFR-R1-19/20/24 |
| TD-R1-12 | **정책 기반 보존 + 별도 감사/cleanup 권한 + verified encrypted archive**. 보존은 NFR profile을 따르고 active/unresolved 참조를 보호한다. | 일반 role의 audit 수정/삭제 거부, archive 검증/회수 후 정리, dedup/history 보존; NFR-R1-14/20 |
| TD-R1-13 | **기존 backup-and-restore 전략 확장**. Postgres/control/files/journal/trust 복구를 하나의 검증 가능한 backup manifest로 연결한다. off-host 전송 구현은 Infrastructure에서 확정한다. | 원격본 회수/actual restore, 새 incarnation/권한/unknown run 검증, 월간 drill; NFR-R1-15/16/22 |
| TD-R1-14 | **pytest + Hypothesis**. Python의 domain generator/round-trip/invariant/oracle/idempotence/stateful 테스트를 기존 환경과 통합한다. | shrinking/seed, FD property 매핑 및 새 REM-1 dev dependency/CI 배치; NFR-R1-21, PBT-09 |
| TD-R1-15 | **Vitest + fast-check**. TypeScript/Node의 실제 consumer/export/view adapter/generator-control 성질을 검증한다. | runtime/generated binding 테스트와 example 병행, scheduler/commands 및 seed/path 보존; NFR-R1-18/21, PBT-09 |
| TD-R1-16 | **GitHub Actions의 frozen PR/release/nightly 검증 + 격리 macOS arm64 인수**. 기존 GitHub review/git-flow를 계승한다. | NFR의 profile/trigger, Linux pure 결과와 Mac I/O/배포 증거 구분, protected production target; NFR-R1-21~24 |
| TD-R1-17 | **명시 CLI action + human summary/versioned JSON**. Python 표준 argparse와 기존 entry 관례로 check/plan/verify/apply/reconcile의 권한·효과를 구분한다. | default apply 없음, effect uncertainty/denial/blocked/stale의 non-success 구분, 안전한 도움말/진단; NFR-R1-08/23 |

## 3. 독립 release와 consumer 호환

- 동일한 source version에서 core/contracts, read-only daemon 및 필요한 runner/tool closure를 추적한다. **독립 artifact**는 dependency와 실행 bytes가 동결됐다는 의미다. 서로 다른 역할이 backend의 전체 virtualenv/환경 파일 또는 mutable repo root를 공유한다는 의미가 아니다.
- Python 3.13은 REM-1 interpreter 선택이다. 공유 Python binding의 기존 **target syntax 3.11** 및 실제 consumer 지원 조합은 별도 manifest로 유지한다. interpreter 선택만으로 consumer 최저 버전을 올리거나 지원되지 않는 문법을 생성하지 않는다.
- Node 24/pnpm 9의 exact patch와 TypeScript/emitter/formatter/version, 선택된 Python wheel과 generator/formatter version도 provenance에 포함한다. timestamp/환경 경로가 output bytes를 바꾸는 경우 재현성 실패다.
- generation/check/scan 도구는 runner 쪽의 필요한 closure에 둔다. daemon은 runtime validation/관측/TLS/DB read에 필요한 최소 dependency만 설치한다. first-party wheel/source provenance는 SBOM에서 보존한다.
- compatible artifact/schema/operation/writer 조합과 actual imports/build를 검사한다. startup은 검증만 하고 missing schema/module을 적용하거나 silent skip하지 않는다. promotion/rollback은 별도 승인과 검증된 complete generation의 경계를 따른다.
- CI/실제 배포 artifact에서 검증한 lock/installed inventory가 동일한지 확인한다. universal lock에 기록된 다른 OS/extra용 dependency와 현재 role에 실제 설치된 occurrence를 구분하되 required build/tool scope를 검사에서 지우지 않는다.
- pipeline 정의 편집권한을 최소화하고 기존 GitHub review 및 deployment approver의 승인 경계로 code 작성과 배포 승인을 분리한다. 검증/승인 후 artifact 또는 effective policy를 바꾸면 새 digest와 검토가 필요하며 기존 receipt를 그대로 재사용하지 않는다.

## 4. Durable state / bootstrap / publication 경계

| 표면 | 저장/권한 계약 | 복구 시 판정 |
|---|---|---|
| canonical migration effect/ledger | domain-owned target Postgres transaction; 검증된 immutable script와 동일 effect proof | matching ledger/실제 postcondition으로 재조정; control 결과와 다른 transaction인 경우를 인정 |
| RunIntent/attempt/checkpoint/approval/head | REM-1 전용 Postgres schema/role; reader와 publisher/maintenance 분리 | durable NOT_STARTED/UNKNOWN 및 append-only 결과로 중복 effect를 방지 |
| schema/generated/report artifact | immutable content-addressed files와 검증된 complete head | partial/mixed/unknown head는 unready; old-or-complete-new 및 consumer pin 요구 |
| control bootstrap/recovery journal | 전용 제한된 local durable journal, exact intent/target/plan/권한과 receipt | control realm 복원 후 검증된 증거로 편입. 일반 mutation에서 control-store 오류를 우회하지 않음 |
| critical audit | append-only 또는 tamper-evident 경로와 application self-delete 불가 권한 | 복원/보존/키 provenance를 확인하며 조용한 history 교체를 허용하지 않음 |

Postgres transaction과 local file/control journal 전체에 분산 원자 commit이 있다고 가정하지 않는다. target commit 뒤 control 기록/응답이 유실되면 FD의 UNKNOWN/reconciliation을 적용한다. filesystem rename만 존재한다는 사실도 여러 consumer의 complete-generation 관측/내구성을 자동 입증하지 않는다.

bootstrap은 live R1C 또는 REM-2 public-job RK를 요구하지 않는다. U3가 아직 없거나 복구 중인 제한된 bootstrap에는 현재 검증된 운영 authority의 목적 한정 credential을 사용하며 expired user grant를 재사용하지 않는다. key/권한/durability가 준비되지 않으면 mutation도 준비되지 않은 것이다.

## 5. Schema, metadata 및 cryptographic domain

### 5.1 Offline generation

- jsonschema/referencing의 local registry와 승인된 SchemaCatalog/ConsumerManifest로 선언 scope를 검증한다. schema resolver의 network 접근은 허용하지 않는다. advisory scan의 allowlisted network와는 별개 capability다.
- Python과 TS emitter 모두 public/server/internal export closure, required root-less definitions/recursive refs, 실제 wire 소비를 검사한다. emitter가 해당 기능을 지원하지 못하면 실패이며 curated/raw dump fallback은 없다.
- hand-written view/domain model은 generated wire input에 대한 명시 adapter/positive·negative fixture로 검증한다. generated wire 대신 이름만 바꾼 수작업 DTO를 사용할 수 없다.
- reference mapping/shape 변환/호환에 영향이 있는 emitter 교체는 원 domain/shared owner review와 F13 인수를 다시 거친다. library reuse는 현재의 skip-success/remove-copy publication 동작을 승인한다는 뜻이 아니다.

### 5.2 Identity와 signature

- 원 SQL/schema/file는 exact bytes SHA-256이다. metadata만 versioned RFC 8785/JCS의 허용 값 domain으로 canonicalize한다. safe I-JSON 범위 밖 값, 중복 key, 유효하지 않은 Unicode/숫자는 조용히 정규화·반올림하지 않고 거부하거나 명시 schema의 lossless 표현을 요구한다.
- 큰 integer/시각/opaque identity의 wire 표현, signed envelope의 schema/version/purpose/subject/policy 및 digest 결속은 NFR Design의 contract로 고정한다. 서로 다른 record kind의 signature를 approval로 재해석할 수 없어야 한다.
- Ed25519는 검증된 library primitive로 구현하고 custom crypto를 쓰지 않는다. Python/Node canonicalization/signature conformance 및 altered bytes/잘못된 key/목적/유효성의 negative fixtures가 필수다.
- signature가 유효해도 선택되지 않은/오래된 head, 불명확 current facts 또는 만료/철회된 authority는 eligible이 아니다. currentness/revocation 상태가 없는 offline proof는 그 자체로 현재 mutation 권한이 아니다.

### 5.3 Key/transport와 role

- R1C는 자기 TLS/mTLS endpoint identity key를 제한적으로 사용한다. **privileged approval/attestation signing key와 mutation credential은 보유하지 않는다.** TLS handshake와 업무 증거/승인 발행은 다른 목적/신뢰 경계다.
- signing, deployment/runner, reader, 감사/cleanup의 역할을 구분한다. 같은 OS UID/Keychain ACL/DB owner가 모든 권한을 실질적으로 공유한 채 role 이름만 나눈 것으로 만족시키지 않는다. 실제 UID/ACL/provider 배치는 Infrastructure에서 검증한다.
- Keychain의 locked/missing/denied 상태는 safe unavailable다. background daemon이 사용자 prompt를 무한 대기하거나 plaintext `.env`/default credential로 fallback하지 않는다. runner는 허용된 환경/secret reference만 받는다.
- mTLS는 service identity다. Operator/System의 목적, source grant, 현재 대상/epoch/철회는 별도로 확인한다. 기존 U3 admin MFA/session 보호와 승인된 운영 authority를 계승한다.
- 인증서/key rotation, 이전 public verification key의 history 보존, current trust/revocation 및 offline recovery key 절차를 NFR Design에서 명세한다. 이전 key가 서명했다는 사실만으로 현재 실행 권한을 연장하지 않는다.

## 6. Supply-chain evidence pipeline

| 표면 | 선택 도구 / 입력 | 보존할 검증 정보 |
|---|---|---|
| Python production/runner closure | pip-audit; frozen lock export와 실제 설치 inventory | version/hash/marker/extra/first-party provenance 및 검사 대상 occurrence |
| Node production/tool closure | pnpm frozen lock/실제 closure 및 audit JSON | workspace/production/build scope, package occurrence/경로, 원 advisory 결과 |
| image/OS 및 통합 inventory | Syft + Grype, image digest와 실제 대상 snapshot | OS/ecosystem coverage, component relation, scanner/DB/source revision·freshness |
| 공유 인벤토리 | versioned CycloneDX | format version, artifact/platform/role identity, component 및 dependency graph, source/report refs |

- source-kind별 report schema/coverage/freshness를 검증한다. online query snapshot에는 원 응답/hash/조회 provenance를, local DB에는 검증된 DB provenance/update 정보를 보존한다. 미제공 전역 revision을 꾸미거나 오래된 local DB를 scan 실행 시각으로 새로 만들지 않는다.
- required OS/ecosystem을 scanner가 지원하지 않는 경우 빈 결과를 clean으로 해석하지 않는다. native macOS 지원/patch 상태 등 scanner 범위 밖의 필수 항목은 운영 policy의 별도 검증 증거로 연결하며 unsupported라는 이유만으로 자동 N/A 처리하지 않는다.
- 원 finding/alias/component occurrence와 severity/unknown을 보존한다. approved exact exception은 finding을 삭제하지 않는다. 신규 artifact/closure/runtime 가정 또는 유효성 변경에는 새 검토가 필요하다.
- toolchain/DB/update 다운로드는 trusted source/TLS/integrity를 검증하고 version/digest를 기록한다. diagnostic stdout/일반 log에는 token/credential/private 입력을 출력하지 않는다.
- F06 인수는 현재 source 파일의 최소 version 선언이나 새 dependency만 보는 PR diff가 아니라 **실제 제출/배포할 frozen closure**의 증거로 판정한다.

## 7. Observability, retention 및 복구 연결

- U6 OBS의 typed context/signal을 소비하고 structured JSON은 검증된 timestamp/level/messageCode/role/correlation 및 안전한 reference/reason만 담는다. 자유형 원 exception/DSN/private 내용 복사를 피하며 metrics label은 bounded category로 제한한다.
- 접수, queue 대기, 실행, 전달, 종단 완료를 구분한다. REM-1에 없는 job phase는 N/A이며 0초 업무 완료를 만들지 않는다. 실제 후속 service의 계측/trace와 G4/G5를 연결한다.
- process liveness, dependency readiness, subject eligibility는 별도 값이다. runner/queue와 독립된 bounded health, 권한 실패/unknown effect/stale evidence/backup/disk·RSS 포화 signal을 기존 경보/healthchecks.io/IR/COE로 전달한다.
- critical audit는 일반 14일 log와 분리한다. application self-delete/변조를 막고 actor/시각/목적/target/before-after fingerprint/outcome을 보존한다. exact retention은 NFR-R1-14를 따른다.
- FileVault 및 별도 encrypted off-host backup과 operator unlock을 복구에 반영한다. archive/backup의 실제 원격본 회수, hash/coverage, restore 후 incarnation/current authority/미완료 run 검증이 필요하다. 구 iCloud local-copy 성공을 그 증거로 승격하지 않는다.
- off-host destination, 암호화 key 복구/escrow, snapshot-cut/저장소 coverage 및 cleanup 구현은 Infrastructure에서 구체화한다. 인증 정보나 unverified backup을 사용해 목표 RPO/RTO를 충족했다고 선언할 수 없다.

## 8. PBT-09 — Framework 선정 및 dependency 근거

| 언어 / 적용 표면 | 확정 선택 | 현재 project 선언 근거 | 요구 capability |
|---|---|---|---|
| Python domain/registry/run/evidence 및 tooling | pytest + Hypothesis | `backend/pyproject.toml`, `shared/python/pyproject.toml`, `ops/pyproject.toml`의 dev 그룹에 pytest/Hypothesis 선언 및 uv lock 존재 | custom strategies, automatic shrinking, seed 재현, pytest 통합, stateful/oracle |
| TypeScript/Node wire/consumer/view adapter/generator control | Vitest + fast-check | `frontend/package.json`의 devDependencies와 pnpm lock; 기존 `vitest run` runner | domain arbitraries, shrinking, seed/path 재현, command/model 검증 및 Vitest 통합 |

이는 QT-4의 기존 선정을 REM-1에 적용한 것이다. 새로운 REM-1 project/tool workspace가 생성될 때 해당 dev dependency를 직접 선언하고 frozen lock/CI에 포함해야 한다. NFR 단계는 framework 선정과 선언 근거를 확인하며 새 package가 이미 구현됐다고 주장하지 않는다.

| Property 영역 | 주 검증 표면 | Code 계획에 남길 사항 |
|---|---|---|
| PROP-R1-01~04 | serialize/registry/legacy/read-only | valid/invalid domain, 원 이력/assurance, byte/identity 및 target 비변경 |
| PROP-R1-05~08 | atomic step/retry/fence/reconcile | stateful effect/ledger model, 빈 sequence, revoke/crash/lost receipt, 실제 I/O 별도 인수 |
| PROP-R1-09~12 | local ref/consumer/generation/activation | shared positive/negative fixture, 양 언어 conformance, network 차단 및 partial publication |
| PROP-R1-13~15 | inventory/exception/current gate | 독립 normalized finding/required-slot model, expiry/old PASS/PENDING/late result |
| PROP-R1-16 | safe observation | 민감정보 sentinel, health/subject 분리, 명시 clock와 duration |

Python 구현 부분은 Hypothesis로, 실제 TypeScript/Node 구현 부분은 fast-check로 검증한다. 검증을 위해 domain 권위를 다른 언어에 포크하지 않는다. 내부 구현 branch를 복제한 oracle 대신 observable ledger/effect/head/reason 의미를 사용한다.

PR/release/nightly의 정확한 examples/sequences/commands 수와 integration/restore trigger는 `nfr-requirements.md` §6.2~6.3을 따른다. seed/최소 반례와 artifact/policy/tool identity를 보존하고, flaky 실패를 자동 재시도로 지우지 않는다. 원 F06/F08/F13 counterexample과 key scenario는 영구 example regression으로 함께 유지한다.

## 9. 선택한 대안과 후속 결정 경계

| 영역 | 이번 선택 | 미선택 대안 / 이유 |
|---|---|---|
| runtime | Python 3.13/Node 24 family | 3.12/22 별도 호환 family 대신 현재 계열 정렬; exact patch 적격성은 별도 검사 |
| control store | Postgres realm + files/journal | embedded SQLite 대신 기존 cluster/명시 transaction·role을 재사용; 제한된 bootstrap journal로 초기 의존 해결 |
| integrity | SHA-256/JCS/Ed25519 | P-256 profile을 선택하지 않음; 같은 TLS/현재 권한 요구는 유지 |
| at-rest | FileVault + operator unlock | 별도 encrypted volume-only profile 대신 data volume 보호를 선택; unattended cold boot를 전제하지 않음 |
| SCA | ecosystem tools + Syft/Grype | 통합 Trivy 중심 profile 대신 원 ecosystem evidence와 image/OS inventory를 결합 |
| test cadence | 빠른 PR + 확장 release/nightly | 동일 집중 PR/release-only profile 대신 빠른 피드백과 주기적 넓은 탐색을 분리 |

NFR Design은 이 선택을 만족하는 transaction/fence/deadline/resource/currentness/crypto·credential/clock/activation/audit/DR 패턴을 결정한다. Infrastructure는 실제 role/UID/port/package root/CA/volume/off-host 배치와 운영 window를 확정한다. 이러한 물리 세부 결정이 숫자/권한/보존/UNKNOWN 보장을 낮추는 암묵적 예외가 되어서는 안 된다.

## 10. 선택 추적성 및 완료 검증 조건

| 입력 | 기술 결정 | 연계 요구사항 |
|---|---|---|
| R1NFR1=A | TD-R1-01/02/05/16/17 | NFR-R1-01/18/23 |
| R1NFR2=A | TD-R1-03/04 | NFR-R1-02/03/16 |
| R1NFR3=A | TD-R1-04/06/11 | NFR-R1-04/05 |
| R1NFR4=A | TD-R1-05/06 | NFR-R1-06 |
| R1NFR5=A | TD-R1-06/11/17 | NFR-R1-07/08 |
| R1NFR6=A | TD-R1-06/10 | NFR-R1-09 |
| R1NFR7=A | TD-R1-06/08 | NFR-R1-10 |
| R1NFR8=A | TD-R1-07/08 | NFR-R1-11/13 |
| R1NFR9=A | TD-R1-09/13 | NFR-R1-12/15/16 |
| R1NFR10=A | TD-R1-11/12 | NFR-R1-14/20 |
| R1NFR11=A | TD-R1-04/09/13 | NFR-R1-15/16 |
| R1NFR12=A | TD-R1-10 | NFR-R1-17 |
| R1NFR13=A | TD-R1-14~16 | NFR-R1-21/22 |

17개 선택은 NFR-R1-01~24 및 FD의 기능 보장을 만족해야 한다. extension per-rule 판정은 `nfr-requirements.md` §8에 모은다. PBT-09는 위 양 언어 framework/dependency 근거와 Code carry-forward를 기준으로 NFR Requirements 수준에서 Compliant다. 실제 library compatibility, key/DB/filesystem/backup/consumer 연결과 성능·실패 보장은 EV-R1-01~09로 검증한다.
