# REM-1 Platform Integrity — NFR Requirements 계획

**단계**: CONSTRUCTION -> NFR Requirements
**유닛**: `rem-1-platform-integrity` (REM-1)
**일자**: 2026-09-19
**상태**: 두 NFR 산출물 작성·검증 및 R1NFRR1=A 승인 완료 (2026-09-19)
**입력 승인**: R1FDR1=A, R1FD1~6=A, UGR1=A, DAD1=A, WPR2=A

이 단계는 승인된 기능 모델에 측정 가능한 품질 목표와 기술 스택을 연결한다. R1NFR1~13은 사용자 답변으로 모두 A가 선택됐다. 선택된 값은 생성할 NFR 산출물의 입력이며 현재 production의 달성 보장이 아니다. 파일 경로는 별도 표시가 없으면 workspace root 기준이다.

## 1. 입력과 현재 근거

- 승인된 Functional Design: `aidlc-docs/construction/rem-1-platform-integrity/functional-design/`의 세 문서. E-R1-01~24, FL-R1-01~08, BR-R1-01~22, PROP-R1-01~16을 계승한다.
- 상위 요구사항: `aidlc-docs/inception/requirements/requirements.md`의 NFR-S1/C1/A1/R1/R4/O1/M1, SEC-1~15, RES-1~12, QT-4/12, C-4/5/13.
- 인수/경계: `verification-remediation-2026-09-18.md`의 F06/F08/F13 및 RJ-AC12, `unit-of-work.md`의 REM-1 High/local G1, DAD1의 R1C/R1R/OBS 및 CompatibilityManifest.

| 근거 | 이번 세션에서 확인한 사실 | NFR 영향 |
|---|---|---|
| `backend/pyproject.toml`, `shared/python/pyproject.toml`, `ops/pyproject.toml` | Python 최소 3.11, FastAPI/Pydantic v2/psycopg 3, uv project/lock; backend는 package=false와 editable path sources | 최소 지원 버전과 실제 interpreter를 구분하고 REM-1 독립 wheel/lock/release 경계를 정의해야 함 |
| `backend/.venv/bin/python --version` | Python 3.13.7 | 현재 interpreter 관측. 해당 patch의 보안 적격성 판정은 아님 |
| `ops/server/run.sh:23-42` | backend 환경 파일을 광범위하게 export하고 repo PYTHONPATH 사용; Node 기본 경로 v24.14.0 | role별 최소 환경/credential, immutable package 및 고정 interpreter 필요 |
| `frontend/package.json`, `.github/workflows/ci.yml:152-174` | pnpm 9.15.9, TypeScript, json-schema-to-typescript, Vitest/fast-check; CI Node 20 | build/production toolchain family 정렬 및 exact patch/tool pin 필요 |
| `shared/python/tools/generate.py`, `frontend/scripts/gen-types.mjs` | Pydantic v2 emitter의 target Python 3.11; TS 5개 subset/raw dump; 전체 shared schema는 13개 | 생성 언어 target과 runner interpreter를 분리. 실제 consumer/모든 local ref 검증은 승인된 F13 요구 |
| `.github/workflows/ci.yml:209-236`, `backend/docker-compose.yml` | audit가 pyproject를 재해석; image에 version tag 및 latest 사용 | frozen 실제 closure와 이미지 digest/도구/DB revision을 검증하는 SCA/SBOM 계약 필요 |
| `ops/server/README.md`, `ops/local/backup-db.sh` | 일반 로그 3 generations, Postgres dump/list 확인 후 local+iCloud copy 및 30일 prune | 90일+ 감사와 별도 보존/권한 필요. local copy나 archive listing만으로 off-host 복구 입증 불가 |
| `ops/server/heartbeat.sh` | 직접 bounded probe, 외부 healthchecks.io heartbeat; 새 job을 만들지 않음 | 기존 외부 dead-man/경보/COE를 계승하고 role별 deep readiness 연결 |
| `sysctl -n hw.memsize hw.physicalcpu hw.logicalcpu` | 메모리 25,769,803,776 bytes = 24 GiB, CPU physical/logical 14/14 | Ollama/OrbStack/기존 service와 공유하므로 REM-1 자체 예산 필요 |
| `df -k .` | data volume Capacity 97%, Available 16,302,140 KiB(약 15.5 GiB) | 현재 여유가 작음. staging/backup/새 artifact의 peak를 포함한 admission gate 필요 |
| `fdesetup status` | FileVault is Off | SEC-1 충족 수단과 cold-boot unlock 절차를 명시해야 함. 다른 암호화 수단의 실제 적용은 이 관측으로 입증되지 않음 |

위 host 값은 2026-09-19의 read-only 관측이다. runbook의 과거 disk/backup 수치와 현재 측정치를 혼동하지 않는다. `.env`/secret 값 및 사용자 private 데이터는 근거 수집에 사용하지 않았다.

## 2. 재선택하지 않는 승인 제약

1. REM-1은 High 중요도의 독립 versioned service다. R1C read-only daemon, R1R 명시적 build/검증/privileged runner, OBS 공통 규약을 분리한다. privileged mutation을 daemon 시작/health/자동 재시도로 실행하지 않는다.
2. startup/CLI는 동일 registry/CompatibilityManifest를 검증한다. 빈 target provisioning/adoption/apply는 별도 승인 action이며 step effect+target ledger는 원자 commit한다. UNKNOWN effect는 재조정 전 반복하지 않는다.
3. 단일 Mac/launchd/OrbStack/Cloudflare/Ollama를 계승한다. 가용성 백분율 SLA, multi-zone 및 자동 host failover는 없다. 수평 autoscale 대신 bounded capacity/backpressure를 적용한다.
4. RPO ≤24h 및 수 시간 RTO가 상위 목표다. REM-1의 persistent control/evidence/bundle도 복구 범위에 넣는다. 더 엄격한 제안은 아래 결정 후에만 채택한다.
5. SEC-1의 저장 암호화/TLS 1.2+, SEC-14의 추가 전용 감사 90일+는 단일 host에서도 필수다. loopback 또는 signed record가 encryption/현재 권한을 대체하지 않는다.
6. Operator/System은 별도 목적/target/plan/artifact 권한을 사용하고, 기존 U3/승인된 운영 authority 및 admin MFA/현재 철회 정책을 계승한다. service identity, 보관된 승인 또는 오래된 signed envelope만으로 새 caller 권한을 만들지 않는다.
7. SHA/digest는 무결성 식별값이며 credential이 아니다. metadata canonicalization은 원 SQL/schema bytes를 바꾸지 않고 signed proof도 current head/expiry/revocation 검증을 생략하지 않는다.
8. generated wire와 명시 view adapter, offline local ref closure, 전체 candidate 검증/atomic activation을 유지한다. Python consumer의 기존 최소 문법 target을 runner 버전 선택만으로 올리지 않는다.
9. known critical/high는 수정 또는 단일 exact artifact/closure의 승인된 source-unreachable 예외로만 처리한다. scanner 오류/누락/unknown은 clean이 아니다.
10. local G1과 후속 REM의 US-R4/5/RJ-AC12 최종 G4/G5는 별도다. REM-2 public-job RK나 R1C HTTP 가용성을 먼저 요구하는 bootstrap 순환은 만들지 않는다.
11. live mutation은 검증된 backup/restore/dry-run/rollback 및 현재 권한에 결속한다. full corpus rebuild/reparse/reembed/alias cutover는 별도 실행 승인이다.
12. 기존 GitHub review/git-flow, 경량 IR/COE, 직접 health/외부 heartbeat를 계승한다. 이번 unit에 새 사용자 UI는 없다. CLI는 human summary와 versioned machine-readable 결과, 명시적 실패/재조정 사유를 제공한다.

## 3. NFR 질문 범주 평가

| 범주 | 필요한 결정 / 계승 |
|---|---|
| Scalability | R1NFR3/4: 동시성·메모리·디스크 admission 및 입력/자료 크기; 수평 확장 예외 유지 |
| Performance | R1NFR5: 정상 측정 profile과 latency/timeout; 검색 NFR-P1을 platform evidence SLA로 바꾸지 않음 |
| Availability | R1NFR9/11: 암호화 unlock/cold boot와 RPO/RTO/복구 증거; single-host best-effort 유지 |
| Security | R1NFR6~10/12: freshness, 승인/예외, key/서명/TLS, at-rest encryption, 감사, SCA/SBOM |
| Tech Stack | R1NFR1/2/8/12: runtime/package, control storage/bootstrap, integrity/key profile, scanner 도구 |
| Reliability | R1NFR3/5/6/11/13: bounded failure, stale/unknown, restore/reconcile 및 장애 검증 |
| Maintainability | R1NFR1/10/12/13: frozen toolchain, cleanup/retention, artifact provenance, CI/회귀/PBT |
| Usability | 승인된 CLI/typed evidence/안전한 reason code 계승. 새 화면은 N/A; 수치 profile과 초과/재조정 안내는 R1NFR3~7/11에 연결 |

## 4. 결정 질문

### R1NFR1 - Runtime과 독립 artifact의 toolchain 기준

기존 Python/TypeScript 도구를 재사용하면서 어떤 유지보수 계열로 REM-1의 CI/release를 정렬할까? 두 안 모두 독립 REM-1 wheel/lock, 비편집 설치, immutable release root 및 daemon/runner entry 분리를 요구한다.

A) **현재 계열 정렬**. Python 3.13 + FastAPI/Pydantic v2/psycopg 3 + uv, Node 24 + pnpm 9 계열을 사용한다. 기존 JSON Schema 검증/참조 및 Python/TS emitter를 hardened adapter 뒤에서 재사용한다. scanner/codegen은 별도 runner dependency 집합이며 daemon에 전부 설치하지 않는다. exact patch/lock/tool digest는 F06 검증을 통과하는 값으로 고정한다. (권장)

B) **보수적 호환 계열**. 같은 framework/driver/emitter와 artifact 분리를 유지하되 Python 3.12 + Node 22 계열을 REM-1 기준으로 선택한다. 현재 3.13/24 환경과의 consumer/운영 호환 검증을 추가하고 해당 계열의 지원/보안 patch를 확인한다.

X) 기타 (아래 `[Answer]:` 뒤에 runtime/toolchain 계열과 독립 artifact 조건을 기술)

[Answer]: A

### R1NFR2 - Control metadata 저장소와 bootstrap 독립성

RunIntent/attempt/checkpoint/approval/evidence head의 durable 저장을 어느 기술로 제공할까? target Postgres의 migration effect+ledger transaction은 어느 안에서도 유지한다.

A) **전용 Postgres logical realm + immutable file bundles**. 기존 cluster 안의 별도 schema/role로 control metadata를 transaction 처리하고 immutable report/binding은 별도 보호된 content-addressed filesystem에 둔다. control realm 최초 bootstrap/복구에 한해 사전 기록된 독립 durable local journal을 사용하고 이후 exact receipt로 편입한다. 이 journal은 일반 mutation의 DB 장애 우회 수단이 아니다. (권장)

B) **전용 embedded SQLite + immutable file bundles**. host-local control DB를 사용해 target Postgres와의 bootstrap 의존을 줄인다. durable sync/단일 writer/read-only reader 및 backup 일관성을 검증하며 SQLite와 target ledger 사이 불확정은 승인된 reconciliation으로 해결한다. 공유 network filesystem은 사용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 durable control state, target ledger, initial bootstrap과 read-only access 경계를 기술)

[Answer]: A

### R1NFR3 - 동시성, 메모리 및 디스크 admission profile

24 GiB host에서 어떤 REM-1 기본 capacity를 적용할까? 아래는 예약된 실측 성능이 아니라 격리 시험으로 확인할 상한/목표다. 초과는 busy/보류로 보고하고 자동 privileged queue를 만들지 않는다.

A) **보수적 단일 heavy lane**. R1C 업무 조회 동시 8개와 별도 health 2개, 정상 부하 5 requests/s를 기준으로 한다. R1R heavy 작업은 host 전체 1개이며 target mutation도 직렬화한다. RSS budget은 daemon 512 MiB, runner+자식 합계 2 GiB다. 새 write 작업은 예상 추가 peak와 안전 여유를 반영해 완료 후 최소 10 GiB free를 유지할 때만 시작한다. (권장)

B) **확장된 local profile**. R1C 조회 16개/health 2개, 10 requests/s; R1R heavy lane 2개 중 mutation은 최대 1개다. daemon 1 GiB, runner+자식 전체 4 GiB, 완료 후 최소 20 GiB free를 요구한다. 현재 관측 여유로는 disk 조건을 충족하지 않는다.

공통 disk 사전 조건은 `free >= reserve + 2 × estimated additional peak`이며 staging/새 bundle/local backup delta를 포함한다. estimate 불명확 또는 budget 초과면 새 write를 보류한다. read-only 진단/health는 유지하고 corpus/감사 자료를 임의 삭제하지 않는다. 수치 초과 때 process 취소/자원 정리도 UNKNOWN effect/fence 보장을 유지해야 한다.

X) 기타 (아래 `[Answer]:` 뒤에 concurrency/RSS/디스크 여유와 측정 부하를 기술)

[Answer]: A

### R1NFR4 - 입력/검증 자료의 유한 크기

허용된 자료도 메모리/디스크를 고갈시키지 않도록 어떤 초기 validation envelope를 둘까? 한도는 조용한 truncation이 아닌 명시적 rejection이고 legitimate recursive ref는 JSON 문서 nesting과 구분한다.

A) **초기 bounded envelope**. HTTP 입력 256 KiB, evidence 응답/page 1 MiB·최대 100항목, manifest/schema 단일 16 MiB·catalog 총 64 MiB, schema resource 1,000개/ref edge 20,000개, migration spec 2,000개, JSON nesting 64, generated bundle 256 MiB·10,000 files, inventory occurrence 100,000개, raw scanner report 64 MiB로 제한한다. 큰 raw 결과는 bounded file 처리하고 API에는 안전한 summary/ref를 제공한다. (권장)

B) **큰 offline artifact envelope**. HTTP 입력/page 한도는 A와 동일하게 유지하고 CLI/offline schema·manifest·bundle·inventory/report 한도와 resource/edge/file 수만 A의 2배, JSON nesting은 128로 둔다. R1NFR3의 메모리/디스크 gate는 그대로 우선한다.

X) 기타 (아래 `[Answer]:` 뒤에 필요한 자료 규모와 입력/응답/파일별 한도를 기술)

[Answer]: A

### R1NFR5 - Latency와 bounded 실행 시간

정상 부하/실패 상황의 시간 예산을 어떻게 잡을까? 총 deadline은 내부 retry보다 우선하며 metadata 조회가 scanner/generator/migration을 시작하지 않는다.

A) **짧은 관측 + 일반 maintenance 예산**. 선택한 정상 부하를 10분 적용할 때 warm metadata 조회 p95 ≤250ms, liveness p95 ≤100ms를 목표로 한다. 관측/ready 총 deadline 3s, DB/authority connect 1s·개별 read 2s다. read-only network는 connect 5s/read 30s·최대 2회 retry이며 상위 deadline을 넘지 않는다. codegen 10분, scanner 15분, migration lock 대기 5s·step 최대 5분·attempt 최대 30분을 기본 cap으로 한다. (권장)

B) **긴 유지보수 허용 profile**. warm metadata p95 ≤500ms, liveness p95 ≤200ms, 관측/ready 총 5s, DB/authority connect 2s·read 3s를 사용한다. read-only network retry는 A와 같다. codegen 20분, scanner 30분, migration lock 대기 15s·step 15분·attempt 90분을 cap으로 한다.

어느 안도 처리 완료를 timeout까지 보장하지 않는다. cold start는 별도 측정하고 start/readiness 목표는 R1NFR11과 연결한다. live effect의 유효 deadline은 현재 승인/fence/attempt 예산 중 가장 이른 경계다. mutation의 blind retry나 비원자 작업을 일반 SQL loop에 넣는 예외는 허용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 관측/도구/migration 시간 예산과 부하 가정을 기술)

[Answer]: A

### R1NFR6 - Evidence freshness와 재검사 주기

동일 artifact라도 새 advisory를 발견할 수 있다. 어떤 freshness 목표로 authoritative read-only 검증을 수행할까?

A) **release마다 + 일일 재검사**. build/release마다 exact closure를 검사하고 사용 중 artifact의 supply-chain 증거를 24시간마다 재검사한다. 허용되는 advisory 관측 max age도 24시간이다. registry/binding의 immutable 결과는 exact input/toolchain/policy가 같은 동안 재사용할 수 있으나 현재 target/head/authority는 판정 때 확인한다. (권장)

B) **release마다 + 6시간 재검사**. 동일 원칙에서 사용 중 artifact의 supply-chain 재검사 주기와 max age를 6시간으로 줄인다. 추가 runner/외부 feed 사용량도 R1NFR3/5 예산에 포함한다.

재검사는 명시적으로 설정한 verify-only System role/CI/운영 실행이다. dependency 업데이트/apply를 자동 수행하지 않는다. 관측 freshness와 사용 advisory feed/DB의 검증된 freshness를 함께 확인하고 새 실행 시각으로 오래된 DB의 age를 초기화하지 않는다. PENDING/오류는 과거 PASS로 덮지 않으며 cache/freshness 기간이 caller grant를 연장하지 않는다. registry/target 변경, 예외 철회·만료 또는 integrity 불일치는 age가 남아 있어도 무효다.

X) 기타 (아래 `[Answer]:` 뒤에 gate별 freshness/재검사 정책을 기술)

[Answer]: A

### R1NFR7 - Mutation 승인과 source-unreachable 예외의 최대 유효 기간

권한/예외의 scope 규칙은 확정됐다. 초기 만료 상한을 어떻게 설정할까?

A) **일반 운영 창**. mutation ApprovalBinding은 발급 후 최대 30분, source-unreachable 예외는 최대 7일이다. 각 step/activation의 실제 실행 deadline은 남은 승인·fence 시간 이내로 제한한다. 만료는 grace 없이 적용하고 장기 작업은 별도 명시 승인 또는 중지/재개를 사용한다. (권장)

B) **짧은 운영 창**. mutation 승인은 최대 10분, source-unreachable 예외는 최대 24시간으로 제한한다. 나머지 현재 권한/step deadline/명시 재승인 규칙은 A와 같다.

해당 상한이 U3 source grant의 만료를 늘리지는 않는다. 신뢰할 수 없는 clock, 철회 상태 미확인, exact artifact/closure/plan 불일치는 허용하지 않는다. 신뢰 clock·clock jump 감지의 구체 수단은 NFR Design에서 정의한다.

X) 기타 (아래 `[Answer]:` 뒤에 승인/예외 상한과 필요한 장기 action을 기술)

[Answer]: A

### R1NFR8 - Fingerprint, 서명 및 credential 관리 profile

어떤 표준 primitive로 immutable manifest/attestation/approval의 provenance를 검증할까? 검증된 라이브러리를 사용하고 자체 암호 알고리즘은 구현하지 않는다.

A) **SHA-256 + JCS + Ed25519**. 원 bytes는 SHA-256, metadata는 RFC 8785/JCS의 허용 domain을 명세해 fingerprint하고 detached Ed25519 서명을 사용한다. key ID/trust anchor/철회를 검증하며 signing key/credential은 role-scoped macOS Keychain에 둔다. TCP는 TLS 1.2+와 certificate 검증, service hop은 mTLS service identity 및 별도 current caller 권한을 사용한다. (권장)

B) **SHA-256 + JCS + ECDSA P-256**. 같은 metadata/권한/TLS/Keychain 조건에서 서명만 P-256으로 선택한다. P-256 기반 도구와의 상호운용을 우선하며 Python/Node 검증 및 key provider 연결을 NFR Design에서 구체화한다.

두 안 모두 R1C에 signing/mutation credential을 주지 않고 모든 backend 환경 변수를 runner로 상속하지 않는다. key access와 감사 접근을 별도 role 경계로 나누며 bootstrap에 U3가 없을 때는 승인된 운영 authority의 제한된 목적 credential을 사용한다. U3 장애를 오래된 user grant의 재사용 사유로 삼지 않는다. key rotation/보관·revocation 배선/인증 구현은 NFR/Infrastructure Design의 필수 검증 항목이다.

X) 기타 (아래 `[Answer]:` 뒤에 integrity/signature/key custody 및 현재 권한 검증 조건을 기술)

[Answer]: A

### R1NFR9 - 저장 암호화와 cold-boot 복구 방식

현재 FileVault는 Off이며 runbook은 자동 로그인을 전제로 한다. SEC-1을 충족하는 저장 보호와 재부팅 복구 모델을 어떻게 정렬할까? 이 답변은 목표 설계 선택이며 현재 host 설정 변경 실행은 아니다.

A) **FileVault + 운영자 unlock**. host data volume을 FileVault로 보호하고 off-host backup은 별도 암호화한다. cold boot 후 권한 있는 운영자의 preboot console unlock/login을 복구 절차에 포함하며 FileVault와 기존 무인 자동 로그인이 함께 성립한다고 가정하지 않는다. 전원 복구 직후 SSH만으로 unlock할 수 있다고 전제하지 않는다. 이후 launchd/OrbStack 복구를 검증한다. (권장)

B) **DocSuri 전용 encrypted volume**. FileVault 대신 DocSuri datastore/control/bundle/audit/temp와 관련 민감 파일을 별도의 encrypted APFS volume에 배치하고 off-host backup을 암호화한다. mount/key-release와 role 권한, 기존 volume의 데이터 이관/잔여분 및 cold-boot unlock 절차를 명시 검증한다. 평문 key를 자동 로그인 스크립트에 두어 보호를 우회하지 않는다.

어느 안도 TLS/권한/감사를 면제하지 않는다. 필요한 volume/key가 잠겨 있으면 안전한 unavailable이며 데이터 migration/apply를 시작하지 않는다. 실제 변경·재부팅 window와 credential/volume 배치는 Infrastructure/실행 단계에서 정한다.

X) 기타 (아래 `[Answer]:` 뒤에 모든 관련 저장소/backup의 암호화 수단과 boot/unlock 절차를 기술)

[Answer]: A

### R1NFR10 - 감사/증거/일반 로그 보존

작은 disk 여유와 SEC-14의 90일+ 감사를 함께 만족시키기 위해 어떤 보존 profile을 사용할까?

A) **90일 감사 + 짧은 일반 로그**. critical audit/attestation/raw verification report는 최소 90일, 일반 structured log/metrics는 14일, 참조 없는 실패 candidate는 7일 보존한다. active/rollback-needed bundle, 유효 승인/예외, unresolved run 및 현재 target의 migration/dedup 증거는 참조가 끝날 때까지 더 오래 보존한다. 오래된 자료는 검증된 암호화 archive로 옮겨 local 사용량을 제한한다. (권장)

B) **장기 감사 profile**. critical audit/attestation/report 365일, 일반 로그/metrics 30일, 참조 없는 실패 candidate 14일로 늘린다. active/unresolved 참조와 archive 조건은 A와 같다.

일반 application role은 자기 critical audit를 삭제/수정할 수 없다. retention cleanup은 별도 권한과 검증된 정책으로만 수행하며 archive 확인 전 local 원본을 지우지 않는다. 기존 3-generation 일반 log rotation을 critical 감사 보존의 근거로 사용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 최소 감사 기간 이상인 보존/아카이브 정책을 기술)

[Answer]: A

### R1NFR11 - REM-1 복구 목표와 backup 인수

single-host best-effort를 유지하면서 platform control/evidence/bundle의 복구 목표를 어느 수준으로 구체화할까?

A) **상위 목표 구체화**. 암호화된 일일 off-host backup으로 RPO ≤24h, 사고 인지부터 검증된 REM-1 복구까지 RTO ≤4h를 목표로 한다. 정상 host/dependency가 준비된 상태의 daemon 재시작은 60s 이내 readiness를 목표로 하되 privileged run은 자동 재개하지 않는다. (권장)

B) **더 짧은 복구 창**. off-host backup을 최소 4시간마다 수행해 RPO ≤4h, REM-1 RTO ≤2h, 정상 host/dependency 조건의 daemon 재시작 30s를 목표로 한다. 더 높은 backup/운영 용량이 필요하다.

두 안 모두 사람이 필요한 unlock/복구, 교체 host 조달과 실제 중단 시간을 함께 기록한다. 예정 drill에서는 복구 host/backup/key를 준비하되 그 준비 시간이 실제 장애에서 0이라고 주장하지 않는다. control metadata, target ledger, immutable bundles/evidence, trust/key 복구 재료의 coverage/hash 및 원격본 회수/실제 restore를 확인한다. iCloud 폴더 local copy 또는 `pg_restore --list` 성공만으로 RPO/restore를 통과시키지 않는다. restore incarnation/권한/UNKNOWN run은 재검증하며 과거 승인을 새 target에 재사용하지 않는다. 실제 off-host 전송/검증 배선은 Infrastructure 단계에서 확정한다.

X) 기타 (아래 `[Answer]:` 뒤에 RPO/RTO, daemon 복구 조건과 backup 인수 목표를 기술)

[Answer]: A

### R1NFR12 - Frozen inventory, scanner 및 SBOM 도구

F06의 실제 production closure와 image/toolchain 검증을 어떤 조합으로 구현할까? report schema/feed revision과 모든 required coverage를 검증하며 실행 실패/누락을 clean으로 바꾸지 않는다.

A) **ecosystem 도구 + image inventory**. Python은 frozen lock export 및 실제 설치 inventory와 결속한 pip-audit, Node는 frozen pnpm closure/audit JSON을 사용한다. image/OS 및 통합 inventory에는 Syft/Grype를 사용하고 versioned CycloneDX SBOM을 만든다. 각 도구/DB revision과 원 report를 exact artifact에 결속한다. (권장)

B) **통합 scanner 중심**. Trivy를 frozen filesystem/lock/image 및 CycloneDX SBOM의 주요 scanner로 사용한다. required ecosystem/OS/first-party provenance의 coverage와 actual installed inventory 동치를 확인하고, 미지원 범위가 있으면 명시적 별도 검사기로 보완한다.

공통으로 runtime/CI dependencies와 도구/base image를 exact version 또는 digest로 고정한다. first-party source를 삭제해 깨끗한 보고서를 만들지 않으며 unused/abandoned/trust source 검사와 source-unreachable 예외 심사는 별도 보존한다. advisory 검사에 필요한 allowlisted network와 schema resolver의 완전한 offline 조건은 구분한다.

X) 기타 (아래 `[Answer]:` 뒤에 scanner/inventory/SBOM 도구 및 필수 coverage를 기술)

[Answer]: A

### R1NFR13 - 검증 강도와 실행 주기

Hypothesis/fast-check와 Full PBT는 이미 승인됐다. 어떤 실행 profile로 16개 속성, 기존 counterexample 및 복구 인수를 검증할까?

A) **빠른 PR + 확장 release/nightly**. PR은 pure property당 200 examples와 stateful property당 50 sequences·최대 50 commands, release/nightly는 2,000 examples와 200 sequences·최대 100 commands를 기본으로 한다. shrinking/seed와 최소 반례를 보존한다. 최초 release/관련 storage·fence 변경마다 실제 격리 Postgres/filesystem/consumer 중단·경쟁 시험, 매월 및 복구 경로 변경 시 isolated restore drill을 실행한다. (권장)

B) **동일한 집중 PR/release profile**. PR/release 모두 1,000 examples와 stateful 100 sequences·최대 100 commands를 적용하고 별도 nightly job은 추가하지 않는다. 실제 integration/restore의 trigger는 A와 동일하다.

각 profile은 known failing example을 property로 대체하지 않으며 business effect를 mock 성공만으로 검증하지 않는다. Linux CI의 pure/contract 검증과 macOS arm64의 실제 배포·파일 원자성 검증을 구분한다. 모든 부하/장애/restore 검증은 격리 namespace/credential/resource budget에서 수행하고 production DB/object를 테스트 대상으로 사용하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 CI/test/restore 강도와 주기를 기술)

[Answer]: A

## 5. PBT-09 및 기술 매핑

QT-4가 framework를 이미 선정했고 현재 project dev dependency에도 존재하므로 재선택 질문을 만들지 않는다. 새로운 REM-1 package의 dev dependency/pin과 CI 배치는 Code 단계에서 이 선택을 반영한다.

| 언어 / 실행 표면 | 선정된 framework | Functional Design 연결 |
|---|---|---|
| Python pure domain/registry/run/authority/evidence 및 scanner normalization | pytest + Hypothesis | PROP-R1-01~16 중 Python 구현 성질; Python consumer/adapter 포함 |
| TypeScript/Node generated wire/consumer/export graph/view adapter 및 generator control | Vitest + fast-check | PROP-R1-01/09~12/16 중 실제 TS 구현 성질; 다른 언어의 domain 권위를 재구현하지 않음 |
| 양 언어의 계약 동치 | 동일 frozen positive/negative fixture와 reference model | local ref/visibility/identity/bytes 동치 및 실제 build 소비 |
| 실제 I/O/복구 경계 | 격리 integration/fault-injection + 예시 회귀 | Postgres effect+ledger, lock/fence, bundle/head, lost receipt; pure model만으로 실제 원자성을 주장하지 않음 |

custom domain generators, automatic shrinking, CI seed 기록/고정, 반례의 영구 회귀를 유지한다. R1NFR13은 이 선정의 해제 여부가 아니라 실행량/주기 결정이다. Code Generation 계획에서 PROP-R1-01~16과 PBT-01~10을 다시 매핑한다.

## 6. 답변 분석 시 교차 확인

- runtime/emitter target/actual consumer 호환, frozen artifact/lock 및 동일 input의 deterministic output을 대조한다.
- Postgres 또는 SQLite 선택이 initial bootstrap, readonly daemon, atomic target ledger 및 current head 조회에 순환 의존을 만들지 않는지 확인한다.
- 큰 input/긴 timeout profile도 선택한 RSS/디스크/승인 기간을 초과할 수 없다. 불가능한 조합은 임의로 수치를 늘리지 않고 명확화한다.
- freshness/retention/RPO는 다른 의미다. 오래 보존한 PASS가 현재 eligible이거나, archive가 있다는 사실이 실제 restore 성공이라는 의미는 아니다.
- encryption/Keychain/role isolation과 cold boot, U3 부재 시 제한된 bootstrap authority, 감사 self-delete 금지를 함께 검토한다.
- clock/revocation/current target을 확인하지 못하면 grace 또는 오래된 signature로 대체하지 않는다.
- 선택한 목표의 부하/관측 구간과 failure/overload 인수를 명시하고, 보장할 수 없는 host 조건을 current 합격으로 표시하지 않는다.

## 7. 산출물과 단계별 이월

답변 검증 후 다음 두 파일을 생성한다.

1. `aidlc-docs/construction/rem-1-platform-integrity/nfr-requirements/nfr-requirements.md`: measurable NFR ID, role/scope, measurement profile, failure behavior, F/BR/property/extension trace 및 acceptance evidence.
2. `aidlc-docs/construction/rem-1-platform-integrity/nfr-requirements/tech-stack-decisions.md`: runtime/package/storage/validation/crypto/SCA/observability/testing 선택, 근거, 대안 및 inherited constraints.

NFR Design은 transaction/fence/reconcile/pool/timeout/authorization/key-rotation/append-only audit/backup/clock 패턴을, Infrastructure Design은 실제 package/port/launchd UID·credential·volume·CA·off-host destination/배치와 실행 순서를 확정한다. 미정 physical 위치가 FD 안전 보장을 완화하지 않는다.

## 8. 확장 적용 및 진행 체크리스트

Security Full, Resiliency custom single-Mac, PBT Full을 유지한다. 답변 분석과 두 산출물의 작성/검증 및 R1NFRR1=A 승인을 마쳤다. 현 단계의 per-rule Compliant/N/A 근거는 `nfr-requirements.md` §8에 있다.

- SECURITY-01의 저장/TLS, SECURITY-03/14의 구조화·추가 전용 90일+ 감사, SECURITY-05/06/08/12/13/15의 입력/권한/무결성/실패, SECURITY-09/10/11의 hardening/supply-chain/capacity를 위 질문과 고정 제약에 연결한다. SECURITY-02/07은 기존 private topology/접근 로그와 Infrastructure 배선으로 추적한다. SECURITY-04는 새 HTML/UI 없음으로 N/A다.
- RESILIENCY-01~07/10~15는 기존 중요도/프로세스/목표를 계승해 해당 NFR에 구체화한다. RESILIENCY-08은 승인된 단일 장애 도메인 예외, RESILIENCY-09는 local bounded-capacity 대체다.
- PBT-09는 이번 NFR Requirements의 적용 규칙이다. §5의 선정/기존 dependency 근거를 `tech-stack-decisions.md`에 반영해야 완료다. PBT-01~08/10은 이 단계 실행 검증 N/A이며 후속 Full 검증을 유지한다.

- [x] R1FDR1=A를 기록하고 승인된 세 FD 산출물과 NFR 상세 규칙을 확인했다.
- [x] 상위 NFR/SEC/RES/QT 및 current manifests/CI/launcher/backup/heartbeat를 대조했다.
- [x] CPU/메모리/disk/FileVault를 read-only로 관측해 capacity/encryption 결정 근거를 기록했다.
- [x] 8개 질문 범주를 평가하고 13개 결정 질문 및 PBT-09 매핑을 작성했다.
- [x] 질문/빈 답변/A/B/Other 각 13개, 8개 범주, FD 정의/참조 및 승인 답변 7개=A를 확인했다. 수치/교차 제약 검토, Prettier debug-check와 tracked/new-file whitespace 검사가 통과했다.
- [x] R1NFR1~13을 모두 A로 기록하고 수치/기술/운영 경계의 정합성을 분석했다. 미답변/혼합/모순 없음.
- [x] `nfr-requirements.md`에 NFR-R1-01~24, 선택된 수치/시간/보존/복구 profile, EV-R1-01~09, 13개 결정 trace 및 확장 적용표를 작성했다.
- [x] `tech-stack-decisions.md`에 TD-R1-01~17, 독립 release/저장/crypto/role/SCA/관측/복구 경계, PBT-09의 양 언어 framework/dependency 근거와 13개 결정 trace를 작성했다.
- [x] 적용 확장 40개 규칙, 인수/측정/선택값 및 문서 정합성을 검증했다. 현 NFR 명세의 미해결 blocking finding 없음.
- [x] NFR Requirements 완료 리뷰 및 R1NFRR1 승인 질문을 준비하고 state/audit를 갱신했다.
- [x] 사용자 `Continue to next stage`를 R1NFRR1=A로 기록해 NFR Requirements 두 산출물을 승인했다 (2026-09-19).
- [x] 승인 후 **REM-1 NFR Design**의 입력 분석/계획을 시작했다.

## 답변 방법

R1NFR1~13 및 §10의 R1NFRR1은 모두 A로 확정됐다. 후속 패턴 결정은 REM-1 NFR Design 계획에서 다룬다.

## 9. 답변 분석 - 2026-09-19

**사용자 원문**: `Use A for R1NFR1–R1NFR13`
**기록 시각**: 2026-09-19T15:39:41Z

| 선택 | 확정 입력 |
|---|---|
| R1NFR1=A | Python 3.13/FastAPI/Pydantic v2/psycopg 3/uv, Node 24/pnpm 9, 독립 frozen artifact와 runner tool 분리 |
| R1NFR2=A | 전용 Postgres logical realm + immutable file bundles; control bootstrap/recovery 한정 durable local journal |
| R1NFR3=A | R1C 8 조회+2 health, 5 requests/s; R1R heavy lane 1, 512 MiB/2 GiB, reserve 10 GiB와 2배 peak 조건 |
| R1NFR4=A | 초기 bounded HTTP/page/catalog/registry/depth/bundle/inventory/report envelope |
| R1NFR5=A | warm 250ms/100ms, 관측 3s, DB 1s/2s, network 5s/30s·retry 2, codegen 10분/scanner 15분/migration 5s·5분·30분 |
| R1NFR6=A | build/release별 및 사용 중 artifact의 24h 재검사/freshness, current target/authority 별도 확인 |
| R1NFR7=A | mutation 승인 최대 30분, exact unreachable 예외 최대 7일, 만료 grace 없음 |
| R1NFR8=A | SHA-256/JCS/Ed25519, role-scoped Keychain, TLS 1.2+/mTLS와 현재 caller 권한 |
| R1NFR9=A | FileVault + 별도 encrypted backup; cold-boot preboot console unlock/login을 복구에 포함 |
| R1NFR10=A | critical audit/evidence/report 최소 90일, 일반 log/metrics 14일, 미참조 실패 candidate 7일; active/unresolved 참조 우선 |
| R1NFR11=A | RPO ≤24h, 사고 인지부터 REM-1 RTO ≤4h, host/dependency 준비 후 daemon readiness 60s 목표 |
| R1NFR12=A | pip-audit/pnpm audit + Syft/Grype + versioned CycloneDX, 실제 frozen artifact/coverage 결속 |
| R1NFR13=A | PR 200 examples/50 sequences×최대50 commands; release/nightly 2,000/200×최대100; 실제 integration과 월간/변경 시 restore |

교차 검토 결과:

- 정상 resource envelope와 byte/count 상한은 독립 제약이다. 개별 입력 한도가 남았더라도 메모리/디스크/시간 예산이 부족하면 명시적으로 거부한다. 15.5 GiB free 관측은 큰 backup/write의 실행 가능성을 입증하지 않는다.
- 30분 mutation 승인과 30분 migration attempt는 각각 issue/start 기준의 상한이다. lock 대기·준비로 소비한 시간까지 반영한 가장 이른 deadline을 사용하며 승인 기간을 새 attempt에서 다시 시작하지 않는다.
- R1C의 mTLS endpoint identity key와 privileged approval/attestation signing key는 다른 목적이다. R1C는 자기 transport 인증만 수행하며 mutation/authoritative evidence 서명 권한을 얻지 않는다.
- control realm bootstrap journal은 한정된 복구 경로이며 일반 apply의 fail-open fallback이 아니다. target effect+ledger와 control 결과 기록 사이의 불확정은 FD의 UNKNOWN/reconciliation으로 처리한다.
- 24h freshness, 7일 예외, 90일 보존과 24h RPO를 혼동하지 않는다. 오래 보존된 signature/PASS가 current eligibility를 연장하지 않는다.
- FileVault의 operator unlock은 선택된 복구 절차다. RTO에는 사람의 응답/키 접근/host 준비 시간을 포함하고 daemon의 조건부 60s 목표와 구분한다.
- 모든 답변은 명시적 A이고 상위 single-host/현재 권한/격리 검증/별도 corpus 실행 경계와 정합적이다. 추가 정책 명확화 없이 두 산출물을 생성할 수 있다.

## 10. NFR Requirements 검증 및 완료 리뷰 - 2026-09-19

| 산출물 | 내용 |
|---|---|
| `../rem-1-platform-integrity/nfr-requirements/nfr-requirements.md` | NFR-R1-01~24, 선택된 capacity/input/deadline/freshness/retention/DR profile, EV-R1-01~09 및 per-rule 확장 적용 |
| `../rem-1-platform-integrity/nfr-requirements/tech-stack-decisions.md` | TD-R1-01~17, 독립 frozen release, Postgres/files/journal, offline generation, crypto/role, SCA, OBS/backup, 양 언어 PBT |

### 검증 결과

- NFR/TD/EV 정의는 **24/17/9개**로 유일하고 연속이다. 두 산출물과 plan의 약식/range ID 참조를 FD 정의까지 대조했으며 미정의 참조가 없다.
- 두 문서의 결정 추적성은 각각 R1NFR1~13=A **13행**이며 누락/중복이 없다.
- capacity/input/deadline 표의 **29개 exact 값**과 PR/release-nightly PBT profile을 선택된 A 내용과 대조했다. freshness/승인/예외/보존/RPO/RTO는 시간 기준과 실패 의미까지 검토했다.
- PBT-09의 Python Hypothesis/pytest, TypeScript fast-check/Vitest를 명시했고 기존 세 Python dev 그룹과 frontend devDependencies의 선언을 확인했다. 새 REM-1 package/CI 배치는 Code 단계의 요구로 남겼다.
- Markdown Prettier `--debug-check`, tracked state/audit의 `git diff --check` 및 새 plan/산출물 각각의 `git diff --no-index --check -- /dev/null <file>` 검사가 통과했다. 문서는 텍스트/표이며 새 Mermaid/ASCII diagram은 없다.
- state는 기존 FD 검증에서 확인한 과거 FR-27 항목의 formatter 재출력 문제가 있으므로 추가 내용의 parsing과 tracked whitespace를 확인한다. 기존 문제를 이번 NFR 결과로 다시 분류하지 않는다.
- 이는 NFR 명세/기술 선정 검증이다. 실제 성능/암호화/원격 backup/restore/role 분리/Full PBT 구현은 EV-R1 인수 및 다음 단계로 추적한다.

### 확장 준수 요약

- **Security**: SECURITY-01/03/05~15는 NFR 수준 Compliant(13개). SECURITY-02는 신규 외부 intermediary 없음, SECURITY-04는 신규 HTML/UI 없음으로 N/A(2개).
- **Resiliency**: RESILIENCY-01~07/10~15 Compliant(13개), RESILIENCY-09는 bounded-capacity replacement Compliant, RESILIENCY-08은 승인된 single-Mac 예외로 N/A.
- **PBT**: PBT-09 Compliant. PBT-01~08/10은 NFR Requirements 단계 실행 검증 N/A이며 Full의 후속 test 요구를 유지한다.

### R1NFRR1 - NFR Requirements 산출물 승인

위 두 산출물과 13개 선택의 반영, 수치/기술/인수/PBT-09 및 후속 구현 경계를 승인하고 **REM-1 NFR Design**으로 진행할까?

A) **Continue to Next Stage** — 두 NFR 산출물을 승인하고 REM-1 NFR Design으로 진행한다.

B) **Request Changes** — 수정할 NFR/기술 선택/측정·인수 또는 추적성을 지정한다.

X) 기타 (아래 `[Answer]:` 뒤에 리뷰 의견을 기술)

[Answer]: A

**승인 기록**: 사용자 원문 `Continue to next stage`, 2026-09-19T16:59:36Z. 현재 완료 리뷰의 Continue to Next Stage 선택인 R1NFRR1=A로 기록하고 REM-1 NFR Design을 시작한다.
