# REM-1 구현 체크포인트 — 2026-09-25

**상태: Code Generation Part 2 진행 중. G1/전체 REM-1 완료 아님.**

입력 승인: 사용자 `R1CGR1: A`. 기준 HEAD `32a424d1`. 격리 worktree `rem1-20260924`에서 구현·검증했고 소스 변경을 주 checkout으로 적용했다. 기존 미커밋 AI-DLC 문서 변경을 보존했다. commit/push, 운영 데이터 repair, 서비스 재시작, FileVault 설정, Colima 전환은 수행하지 않았다.

## 구현 및 검증된 부분

### F08 — migration registry와 legacy 진실성

- `backend/migrations/registry.py`: domain owner + local ID의 명시적 registry. evidence, glossary, mypage 및 ingestion을 포함한다. 선언/디스크 불일치와 symlink/path 이탈을 거부한다.
- `backend/migrations/__init__.py`: 조회는 readonly transaction이며 ledger를 만들지 않는다. basename만 남은 legacy 이력은 `NEEDS_RECONCILIATION`; 명시적인 domain postcondition 검증과 authority를 거친 baseline은 `ADOPTED_BASELINE`으로 보존한다.
- 적용 경로는 현재 authority provider를 명시적으로 요구하며, DB 단위 advisory lock과 step 효과+ledger transaction을 사용한다. transaction 탈출/외부 효과 가능 SQL은 ATOMIC_STEP 경로에서 거부한다.
- `backend/app.py`와 CLI는 같은 registry를 사용한다. **startup은 검증 전용**이다. 기존 운영 DB에는 v2 원장 채택/현재 권한 연결이 필요하므로 이 소스를 그대로 운영 재시작하는 것은 아직 준비되지 않았다.
- disposable Postgres에서 fresh/legacy/adoption/동시 writer 거부/실패 rollback/멱등을 확인했다. 실제 evidence POST와 glossary GET도 새 schema 위에서 성공했다. 적용 테스트의 권한은 **test-only authority**이며 production 권한 증명이 아니다.

### F13 — offline generation과 실제 소비 타입

- `frontend/scripts/gen-types.mjs`: 일곱 shared DTO schema의 absolute local `$ref`를 하나의 local graph로 해소한다. 실패 시 non-zero, 단일 generated TS 모듈을 완성 후 atomic rename한다.
- `frontend/types/wire/dtos.ts`가 실제 wire 정의다. 기존 `types/generated/`는 generated type 별칭 및 명시적 summary/library view refinement를 사용한다. description-only JSON Schema 필드를 잘못 object로 좁히거나 `title` 속성을 제거하지 않는 회귀를 추가했다.
- `shared/python/tools/generate.py`: 13개 schema reference를 local staged 경로로 해소하고 미해소 reference를 실행 전에 거부한다. immutable `_binding_generations/<digest>` 및 단일 `_binding_head.json`을 사용한다.
- `_binding_loader.py`는 manifest/file digest, 정확한 Python file 집합 및 generation symlink를 확인하고 process의 `_generated.__path__`를 한 generation에 고정한다. 미등록 Python module의 추가를 거부하는 회귀를 검증했다. 기존 legacy generated 소스는 자동 삭제하지 않는다.
- Python/TS drift 검사, 기존 DTO 테스트, 프론트 TypeScript/빌드 및 non-editable shared wheel import를 확인했다. 모든 hand-authored API wire consumer에 대한 별도 inventory/visibility 증명은 아직 남아 있다.

### F06 — dependency baseline

- Python project lock 6개 및 신규 REM-1 lock을 갱신했다. 예: cryptography 50.0.1, anyio 4.15.1, Pillow 12.3.0, pydantic-settings 2.15.0, soupsieve 2.10.
- Next.js/eslint-config-next 15.5.26 및 vulnerable transitive override를 적용했다.
- isolated installed backend/ingestion/ops/shared/REM-1의 pip-audit와 frontend production pnpm audit에서 **알려진 취약점 0건**. first-party editable package는 scanner의 skip으로 표시되며 source 검증/SBOM 대상으로 별도 유지한다.
- Compose image는 조회한 immutable digest로 pin했다. MinIO Docker Hub 접근 실패 후 공식 Quay의 명시 release digest를 확인했다. production 예제 비밀번호는 protected secret-file 입력으로 대체했다.
- `.github/workflows/ci.yml`: full frozen export 기반 Python audit, frontend production audit, actual type drift, Node 24.14.0, pip-audit 2.10.1, 고정 Python/fast-check seed, REM-1 lane을 추가/정렬했다.
- image/OS의 Syft/Grype 검사, 전체 SBOM·native tool provenance 및 실제 배포 artifact 일치 검증은 아직 남아 있다. 따라서 **F06 전체 인수 완료로 표시하지 않는다**.

### 신규 독립 package

`platform_integrity/`에 다음을 구현했다:

- strict immutable control model, bounded duplicate-free JSON/JCS 및 목적 결속 Ed25519 primitive;
- registry/order/legacy/effect transition/current-evidence/exception/scanner coverage의 pure rules;
- immutable generation/head, bootstrap journal, control SQL/CAS/append-only audit/outbox;
- readonly evidence 서비스/API, 별도 health capacity, request/response/deadline bounds, generation-aware breaker, immutable byte cache;
- bounded one-shot supervisor와 미확인 holder witness 보존;
- native Darwin `getpeereid`, 비대화형 custom Keychain reader, clock-window/boot-resume 검증 adapter;
- TLS transport에서 client certificate fingerprint를 주입하는 loopback R1C server entry. 실제 synthetic mTLS 서버 시험에서 올바른 인증서의 관측, 다른 인증서+위조 header의 거부, 무인증서 handshake 거부를 확인했다;
- 명시적 readonly CLI. `apply`는 실제 native current-authority 연결 전 **BLOCKED**다.

U3 `SessionManager.inspect()`는 background 관측 시 세션 TTL을 갱신하거나 만료 세션을 삭제하지 않는다. 기존 `verify()`의 sliding 동작은 유지한다. 이 메서드만으로 object 권한/현재 계정 상태/commit 원자성이 충족된 것은 아니다.

### RunIntent / control checkpoint 후속 구현 (12:42 UTC)

- `contracts/models.py`, `domain/run.py`: ordered effect의 exact definition/before/after, target incarnation, artifact/policy/recovery를 plan digest와 stable semantic key에 결속했다. submission ID·attempt·시각·새 approval instance는 logical intent를 바꾸지 않는다.
- `adapters/postgres.py`의 `PostgresRunStore`: 동일 submission key의 의미 변경 거부, semantic dedup, immutable attempt 시작 이력, readonly 조회 및 run-row lock + expected revision으로 checkpoint 경쟁을 직렬화한다. UNKNOWN/checkpoint·critical audit·outbox·run projection은 하나의 control transaction이며 COMMIT acknowledgement 후에만 receipt를 반환한다.
- `migrations/002_run_protocol.sql`: 기존 schema를 additive하게 확장하고 uint64 sequence, attempt FK/unique invocation, immutable intent/checkpoint 이력 및 truncate 거부를 정의했다. 기존의 결속 정보 없는 run/체크포인트를 자동 backfill하지 않는다. 두 control migration은 wheel에 포함된다.
- 알려지지 않은 effect, 다른 target/plan/attempt/fence의 proof, 미확인 종료, sequence gap은 blind retry를 허용하지 않는다. 확인된 abort 뒤 충돌하는 native commit 관측이 오면 UNKNOWN으로 되돌려 재조정을 요구하는 반례를 먼저 실패로 재현한 뒤 수정했다. 확인된 COMMITTED 사실은 후속 drift로 지우지 않는다.
- 확인된 effect 사실과 run의 검증 성공을 분리했다. authorization/durability proof가 없는 commit은 기록하되 SUCCEEDED로 승격하지 않는다. retry는 확인된 no-effect와 fresh attempt/new fence가 필요하고 이미 검증된 앞선 step은 반복하지 않는다.
- `tests/run_support.py`, `test_run_recovery.py`: domain-specific plan generator, independent interrupted-effect model, round-trip/semantic identity/scope/counter 경계 및 예시 회귀. PR은 200 examples와 50×50 stateful, release는 2,000 examples와 200×100 stateful profile을 사용한다.
- `tests/test_run_postgres.py`: **15개 실제 control-DB 시험**으로 ACK 유실 후 UNKNOWN, 두 writer CAS, outbox 실패의 전체 rollback, partial commit/abort/resume, attempt 재요청의 grant/start-time 비연장, history gap, readonly/non-bootstrap 및 immutable update/delete 거부를 검증했다.

**증거 경계**: 위 DB 시험은 별도 `rem1_test`/15439와 tmpfs Postgres에서 control transaction·다른 connection의 관측을 검증했다. target/authority observation은 synthetic이며 native revoke/commit, 실제 전원 장애 내구성 또는 production 권한 증명이 아니다. `CommandContext`, `EffectObservation`, `CheckpointReceipt`는 내부 계약이며 자체 인가 capability가 아니다. 실제 current-authority/native guard/command-only DB role composition은 아직 연결해야 한다. privileged `apply`는 계속 BLOCKED다.

### Current evidence / verification publication 후속 구현 (15:09 UTC)

- `contracts/models.py`, `domain/gate.py`: verification request/예약 revision/현재 선택과 immutable result를 결속했다. `PENDING` 또는 실패한 재검사를 과거 PASS로 대체하지 않는다. 같은 verification의 서로 다른 종단 결과, 다른 subject/slot의 head와 뒤로 간 revision을 거부한다.
- gate는 현재 subject·정확한 record digest·key trust/유효 구간·현재 exception의 artifact/closure/assumptions/승인/철회를 대조한다. 보호된 current provider가 없으면 checksum-only PASS는 eligible이 아니다. `SubjectSnapshot`은 artifact와 mutable target을 구분하며 target에는 identity와 relevant-state digest가 필수다. 같은 incarnation의 schema/state 변경도 STALE로 판단한다.
- 결과에는 안전한 diagnostic code, 별도 slot 참조, 선택 revision, 평가 UTC window와 입력 fingerprint를 남긴다. unselected history/입력 열거 순서는 같은 평가 결과를 바꾸지 않고 원 exception 참조는 차단 후에도 보존한다. producer의 임의 이유문/오류문을 응답에 그대로 복사하지 않는다.
- `adapters/authority.py`의 `CurrentEvidenceVerifier`는 실제 Ed25519 envelope의 kind/purpose/body와 매번 조회한 현재 key/subject/exception facts를 확인한다. key port에 exact record를 전달해 owner가 보호된 publication provenance를 확인할 수 있다. key lookup/owner 장애는 unknown, 철회 정보의 `null`은 유효 key로 coercion하지 않는다. 이 owner port들의 **production 구현/배선은 아직 별도 작업**이다.
- `application/evidence.py`는 head/record와 현재 trust를 재관측해 도중 변경 시 INCOMPLETE를 반환한다. synchronous I/O가 끝날 때까지 worker admission 8개를 보유하고 원 2.5초 내부 budget 안에서 다음 관측을 시작한다. HTTP 3초 deadline, caller grant 재확인 및 readonly 경계를 유지한다. 실제 전체 native I/O budget/부하/RSS 인수는 아직 열려 있다.
- `adapters/postgres.py`의 `PostgresEvidenceStore`는 명시적 reserve/resolve와 audit/outbox를 직접 소유한 transaction으로 commit한다. 종전 caller-owned `publish_evidence` 경로를 대체했다. 늦은 결과도 immutable history/audit에 남기며 새 head를 덮지 않는다. 재요청은 원 verification identity/revision을 재사용하고 의미 변경은 conflict다.
- `migrations/003_verification_protocol.sql`은 request/result/head의 관계와 uint64 revision, monotonic head 전이, reservation과 head의 동일-commit floor를 강제한다. 관련 trigger의 search path를 고정했다. legacy row를 보존하되 verification binding을 발명하거나 PASS로 승격하지 않는다.
- `tests/test_current_evidence.py`, `test_evidence_trust.py`, `test_evidence_postgres.py` 및 `evidence_support.py`를 추가했다. 저장된 예외 참조만으로 PASS, unsigned/checksum-only PASS, 종단 history conflict, 다른 subject head, read 중 key 철회, mutable-state 표현 누락 및 `revoked=None` 반례를 먼저 실패로 재현한 뒤 수정했다. **새 실제 PG 11건**과 기존 evidence transaction 회귀, real Ed25519 + PG→readonly-service 조합, 독립 verification-history model을 검증했다.

실제 검증은 격리 control DB와 cryptography 구현에 대한 것이다. 키/subject/권한/clock의 owner 관측은 synthetic이며 Keychain ACL, native revoke/commit guard, host 설치 또는 G1의 증명이 아니다. compatibility matrix, 전체 verification/scanner/signing pipeline과 role 제한 command function도 남아 있다.

### Offline schema catalog / generation 후속 구현 (16:28 UTC)

- `shared/schema-catalog.json`: 13개 source file의 canonical ID/path/visibility, Python의 internal generation roots 13개 및 TypeScript의 public roots 7개를 명시했다. `python/`은 구현·빌드·시험 경로라는 제외 사유를 기록했다. 미등록/누락 schema, 경로 이탈/symlink 및 consumer-root 분류 누락은 실패다.
- `shared/python/src/docsuri_schema/`: generated DTO를 import하지 않는 독립 namespace로 local resource/fragment graph를 구현했다. `shared/python/tools/generate.py`와 REM-1 tool-role의 `domain/bindings.py`가 같은 Python 구현을 소비한다. `platform_integrity`의 `tools` extra에만 first-party `docsuri-shared==0.1.0`을 추가하고 lock을 갱신했다. third-party 버전 변경은 없다.
- `shared/schema-catalog.mjs`: Node 쪽의 같은 offline profile을 구현했다. 양쪽은 `shared/schema-conformance.json`의 **20개 공통 사례**로 대조한다. nested `$id`/anchor, legal recursion, JSON pointer의 slash/tilde/UTF-8 escape, boolean schema, duplicate/unknown/unsupported 및 visibility 경계를 다룬다.
- schema keyword는 schema 위치에서만 해석한다. `default`/`examples`/`const` 등의 literal `$id`/`$ref`와 같은 이름의 일반 property를 훼손하지 않는다. 값/문서/카탈로그/그래프에 유한한 한도를 적용하고 외부 reference를 fetch하지 않는다. 지원하지 않는 dialect/dynamic-reference profile은 non-success다.
- TypeScript emitter의 하위 ref-parser도 literal 객체를 따라가던 문제를 재현했다. external/file/HTTP 해소를 모두 끄고 schema-position grammar로 dereference를 제한했으며 percent-encoded `$defs` 경로를 보정했다. 일반 local root/fragment target을 생성 alias로 연결하고 이름 collision을 거부한다.
- Python staging은 manifest의 전체 Python profile을 검사한 뒤 local file/pointer로만 변환한다. literal percent를 포함하는 definition 이름을 다시 URI-escape한다. 기존 Python 생성물 drift는 없고 TypeScript 생성물은 catalog fingerprint banner만 변경됐다.
- single-target 실패가 기존 published head/wire를 보존하는 시험, actual generator→TypeScript/Next build, catalog inventory 거부와 shared conformance/property를 확인했다. CLI `check-schemas`는 기본적으로 manifest를 요구한다. 별도 개발/시험용 `--flat`은 제한된 local-reference scope로만 보고한다.
- 기존 shared test fixture를 유지하면서 PR 200/release 2,000-example Hypothesis profile을 추가했고 shared CI의 uv 명령을 `--frozen`으로 고정했다. fresh/no-cache non-editable wheel에서 `docsuri_schema`가 `docsuri_shared`를 bootstrap import하지 않는 것과 REM-1의 schema validator 및 기존 DTO import를 검증했다.

**남은 consumer 의무**: 위 manifest는 schema inventory와 **generator entry roots**를 닫는다. 모든 hand-authored API wire/import와 view adapter의 실제 소비 목록, helper-owned privileged seal/activation, reader/backup/GC 및 전체 F13/G1 인수를 완료한 것으로 확대하지 않는다. 해당 Step 3/8/7 항목은 열려 있다.

### Actual consumers / domain / operator harness 후속 구현 (2026-09-25)

- `frontend/scripts/inventory-consumers.mjs`와 `shared/python/tools/inventory_consumers.py`가 실제 import/alias/model/cast 및 source digest를 조사한다. snapshot은 `shared/{typescript-consumers,python-consumers}.json`이며 CI가 drift를 차단한다. TypeScript는 **185 imports, 11 declarations, 64 body casts, 17 adapters, 44 source fingerprints**; Python은 **217 imports, 97 local model candidates, 97 source fingerprints**다. Python local model은 내부 모델을 포함하는 검토 후보이며 모두 HTTP wire라고 단정하지 않는다.
- `shared/view-adapters.json`은 발견한 17개 mapper를 명시하고 fixture/schema 또는 view-only 분류를 연결한다. 새 adapter 미등록, missing/duplicate policy, generated lineage 없는 production body cast와 Python generated import 재정의를 거부한다. 임시 checkout의 alias 해소, source-field 변경 및 shadowing을 regression으로 확인했다.
- `shared/dtos/extended.schema.json`의 기존 frontend wire 57개를 generated alias로 연결했다. catalog는 현재 14 resources/Python roots 14/TS roots 8이다. 새 immutable Python generation은 `aa0015fc61158f5a29e79505ec4c2bae691992cbb91e948e5d4a4ac5c926069c`다. 이 승격은 기존 frontend 선언 추출에 기반하며 전체 backend-owner 응답/요청 parity·negative fixture 완료의 증명이 아니다.
- `domain/{registry,compatibility,observation,supply_chain}.py`: legacy assurance/prerequisite/capability, exact runtime release, liveness/readiness/subject 분리와 allowlisted observation, scanner scope/occurrence/freshness 평가를 추가했다. 서로 충돌하거나 선언 밖의 scan에서도 모든 finding을 보존한다. exact duplicate observation은 멱등이고 High/Critical은 BLOCKED, unknown/coverage 결손은 INCOMPLETE다. 예외는 `authorized is True`와 `revoked is False`를 요구한다.
- `adapters/operator_authority.py`/migration 004 및 backend finalization seam: 실제 같은 target DB connection에서 현재 operator grant와 epoch를 재확인하고 COMMIT 직전 SHARE lock으로 source revoker와 직렬화한다. 아홉 PG 시험이 revoke/finalizer 순서, stale fence/clock 거부 및 apply/adopt purpose 분리를 확인한다. read/mutation guard의 bool/float/음수/역전 clock과 unknown revoke도 차단했다. test clock 및 owner DB role은 synthetic이며 command-only role/native source 또는 durable UNKNOWN-to-dispatch 연결을 대신하지 않는다.
- `ops/platform-integrity/provision_test_realm.py`: default PLAN_ONLY, 로컬 Darwin root만 `--apply`, role별 UID/GID/directory 준비. 기존 계정 속성·중복 ID·supplementary privilege 거부의 여섯 시험이 통과했다. 실제 privileged 실행은 없으며 [operator-handoff.md](operator-handoff.md)에 검토 hash/로컬 실행·volume 입력을 기록했다.
- `test_recovery_acceptance.py`: 실제 control/audit pg_dump/pg_restore 및 new-incarnation old-PASS 무효화가 통과했다. 동일 disposable container의 별도 DB 시험으로, encrypted/off-host recovery나 RTO/RPO 인수는 아니다.
- `load_acceptance.py`: 정확한 test origin만 허용하고 mTLS credential을 보낸 redirect를 따라가지 않는다. scheduled arrival부터 queue latency를 계산하며 in-flight 10개로 한정하고 실패/INCOMPLETE 응답을 success에 포함하지 않는다. harness regression 여덟 건이 통과했다. native 600초 성능/overload/RSS 실행은 아직 없다.

### SBOM 및 차단 finding (2026-09-25)

- `fetch_tools.py`는 공식 Darwin arm64 Syft **1.52.0**, Grype **0.119.0** archive/binary digest를 확인한다. `scan_sbom.py`는 output/deadline/RSS/disk를 제한하고 report/descriptor/hash를 보존한다. unknown severity, invalid DB/filtered coverage, ignored findings를 clean으로 승격하지 않는 열 개 regression을 확인했다.
- 보존 위치의 공통 prefix: `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/`.
- `rem1-sbom-validation-20260925-r2`: 135 components/0 matches, `rem1-sbom-reader-20260925`: 67/0, `rem1-sbom-runner-20260925`: 64/0. role 환경은 frozen non-editable 설치였으나 이후 first-party 소스 변경이 있어 최종 artifact binding/rescan이 필요하다. host time은 `host-unverified`이며 zero matches만으로 G1을 통과하지 않는다.
- `rem1-sbom-postgres-20260925`: pinned `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`, **7,384 components, 323 matches, 96 High + 2 Critical, ignored 0**. blocking match fix state는 **fixed 24 / not-fixed 12 / wont-fix 62**다. Go stdlib 1.24.6, libxml2 및 Debian packages가 포함된다. 원 finding을 suppress하거나 unreachable 예외로 승인하지 않았다.
- PostgreSQL SBOM SHA256: `f6aa5ad458bb2d22b4ab4981484f1ff687d7ec67d500eabc7cb38440ec767ef1`; Grype report SHA256: `c2997da07d99885c82ddf6e3199bfa285f1fb533debb218e78cd5fc7e8661c72`.
- 원 report와 summary는 당시 관측으로 보존한다. 후속 classifier의 `summarize_findings.py`는 `unapproved_high_or_critical_findings`를 명시한다. 나머지 image/native/interpreter/build-tool/최종 role coverage는 열려 있으며 `sbom-targets.json`은 검사 대상 선언이지 완료 증거가 아니다.

### Operator native 준비 및 검사기 보정 (2026-09-26)

- operator가 원 준비 artifact(`94d73055dc46ea97db04275e3c99a81a054f1efdc3ba9989f9ed826fe511bbb5`)의 root 전용 복사본으로 `--apply`를 실행했다. 실제 OS 조회로 `_docsuri_r1t_` 역할 UID/GID 600~608, non-login 속성, realm root 0711·role directory 0700·preparation receipt 0600을 확인했다. agent의 realm listing은 EACCES이고 sudo 비대화형 root 실행은 인증 필요로 거부됐다.
- 준비 볼륨의 같은 UUID에서 `Encryption=true`, `GlobalPermissionsEnabled=true`, mounted/unlocked/writable을 확인했다. volume 소유권 적용은 완료됐다. 외장 volume의 FileVault Yes와 host 내부 디스크의 `fdesetup` Off는 별도 관측이다.
- 실제 `dscl`의 `dsAttrTypeNative:IsHidden`을 기존 검사기가 해석하지 못하는 회귀와 상충 namespace를 놓치는 회귀를 수정했다. directory membership의 everyone/localaccounts/_lpoperator를 기록하고 actual process group 격리는 별도 의무로 남긴다. 초기화 `--apply`의 엄격한 group 거부는 유지한다.
- `provision_test_realm.py --check`는 읽기 전용으로 실제 9개 계정/디렉터리를 대조해 `METADATA_VERIFIED`, `ready=false`를 반환했다. 새 `--probe`는 root-owned protected staging에서만 신규 synthetic fixture/9개 UID worker를 실행한다. supplementary group 제거, native libSystem `getgroups`, 자기 read/write·교차 role/ambient group 읽기·쓰기 거부, bounded input/5초 deadline/디스크 여유/결과 보존을 검증하도록 구현했다. modern macOS의 Python `os.getgroups`는 directory access list이므로 kernel group 검증에 사용하지 않는다.
- focused native suite **16 passed**(이전 6개에 10개 추가), Ruff 및 system Python 3.9의 worker 구문/실제 kernel query 확인 통과. 테스트 group seam은 synthetic이며 root UID별 `--probe` 자체는 operator 실행 대기다. FIFO는 nonblocking open/regular-file 확인으로 거부하고 missing file을 permission denial로 계산하지 않는다. unprivileged probe와 mutable checkout의 privileged probe도 거부한다.
- 첫 source hash `90aa58859bdfcd922f9aa2fe9a8a49a93a9e87b07be0a769b125585976ebac7f`의 실제 operator probe는 9개 TimeoutExpired로 BLOCKED였다. 원 `role-probe-su4773zc`를 보존했다. 정확한 정지 지점은 당시 report에 phase가 없어 미확정이다.
- 격리 worktree에서 검증한 script/test 두 파일을 main에 통합했다. `rem1-20260926-native.patch`와 전체 `rem1-20260926.patch`를 보존했다. 이번 변경은 ops 도구/test에 한정되므로 기존 Python wheel을 새로 빌드한 것으로 기록하지 않는다.

### Native probe timeout 진단 보강 (2026-09-26 후속)

- `/usr/bin/python3` 및 resolved framework bin이 실제 Python image로 재실행하는 launcher임을 native proc_pidpath/otool/nm으로 확인했다. 원 timeout의 정확한 원인을 단정하지 않고, 현재 실행 image를 직접 선택하고 단계 관측을 추가했다.
- 새 진단판은 allowlisted worker phase와 PID/elapsed/return code/cleanup을 보존한다. 원 stderr는 root 전용 파일에 최대 64 KiB를 남긴다. timeout 시 소유 process group을 종료하고 parent/pipe quiescence를 보고하며 이후 역할은 NOT_RUN으로 남긴다.
- `--probe --role reader`는 단일 역할만 실행하고 통과해도 PARTIAL/completeRoleCoverage=false다. 실제 역할 결과 없이 전체 native 인수를 승격하지 않는다.
- focused suite **22 passed**, Ruff/system Python 3.9 parsing, native image 직접 실행의 일반 UID startup/EOF smoke, source patch 역적용 check가 통과했다. 실제 subprocess timeout/pipe-holding descendant 정리 회귀를 포함한다. privileged 역할의 성공은 operator 재실행이 필요하다.
- 현재 hash `2e310b60c37e0398f18c9c4351398d49cf4857d5c46c2addc744126be00e4e23`; source/test 두 파일을 통합하고 전체 `rem1-20260926-diagnostics.patch` 및 incremental `rem1-20260926-probe-diagnostics.patch`를 보존했다. [native-probe-debug.md](native-probe-debug.md)에 capture/가설/contained recovery/검증 한계를, [operator-handoff.md](operator-handoff.md) §4에 새 r2 staging/단일 reader 명령을 기록했다.
- 후속 operator의 실제 reader 실행은 **0.052초에 PARTIAL_ROLE_FILE_ISOLATION_VERIFIED**로 완료됐다. UID/GID/groups 600/600/[600], own read/write, 교차 read/write 거부 각 8개와 ambient-group read 거부 3개, 마지막 stage complete/returncode=0/parentReaped=true를 확인했다. root `role-probe-e_0w5ja7`와 interpreter hash `07470fa2e1aec690aa62061af6e0f65fe9bf3169a74a16384592fb1ff1cb320f`를 기록했다. script/interpreter의 현재 로컬 hash가 일치한다. 다음 handoff는 동일 r2의 전체 9-role probe이며, reader 통과를 전체 권한/G1이나 과거 timeout의 단독 근인 확정으로 확대하지 않는다.
- 동일 r2의 전체 operator 실행도 **ROLE_FILE_ISOLATION_VERIFIED / completeRoleCoverage=true**로 완료됐다. root `role-probe-236g0xrp`, 9개 UID/GID 600~608, role별 유일한 primary kernel group과 own read/write를 확인했다. 각 8개 교차 read/write 및 3개 group read 거부로 합계 **72/72/27**이며, 전 worker는 **0.044~0.051초**, complete/exit 0/no timeout/reaped다. script/interpreter의 현재 SHA256과 대조했다. synthetic-file scope 완료를 plan에 체크했으며 `ready=false`와 installed launcher/Keychain/NTS/DB/backup/G1의 남은 의무는 유지한다.

### Native runtime 배선 + 실제 DB mTLS 인수 (2026-09-26)

- `deployment/launchd.py`, `host.py`, `adapters/{credentials,postgres_tls,nts,read_authority}.py`, `migrations/005_reader_access.sql`과 그 test를 구현해 **main에 통합**했다. 통합 전후로 worktree와 main의 `platform_integrity` 트리가 바이트 동일함을 확인했다.
- launcher는 immutable manifest allowlist, role-scoped plist(`InitGroups=false`, `Umask=0o077`, `/usr/bin/env -i` 최소 환경), `python -I -m` 고정 entry, frozen artifact digest 검증, `setgroups([])`→gid→uid 순 privilege drop과 실행 직전 uid/gid/supplementary group 재검증을 수행한다. clock observer는 고정 non-adjusting `chronyd -x -d -f`만 허용한다.
- `host.py`는 설정에 credential byte를 받지 않고 Keychain handle만 받는다. reader profile port는 test 15439/production 5432로만 허용하고, role 불일치·clock publisher 소유권·관측 실패는 모두 fail closed다.
- **실제 PostgreSQL mTLS 인수**를 추가했다. loopback TLS, `cert clientname=CN` 기반 `session_user=r1_tls_probe` 로그인, read-only transaction 강제, **wrong-CA 거부**까지 실제证书 경로로 확인했다. 잘못된 CA 거부이므로 denial이 우연히 통과하지 않는지 오류 메시지에 `certificate`가 포함되는지까지 확인했다.
- 이 테스트를 통과시키기 위해 실패 원인을 세 가지 실제로 규명했다: (1) fixture가 열린 psycopg 컨텍스트 안에서 `docker restart`를 호출해 이후 문장이 `AdminShutdown`으로 죽음, (2) `/var/lib/postgresql/data`가 `HostConfig.Tmpfs` 256M tmpfs라 restart마다 클러스터가 재초기화되어 `ALTER SYSTEM SET ssl=on`이 소실, (3) `hostssl ... cert` 규칙이 image 전역 `scram-sha-256` 뒤에 있어 first-match에서 password 요구(`fe_sendauth: no password supplied`). `pg_ctl restart`는 postmaster가 PID 1이라 container를 종료시키므로 채택하지 않았다.
- teardown 후 `ssl=off`, `pg_hba.conf`의 probe 규칙 0건, `postgresql.auto.conf` 초기화까지 확인해 검증이 격리 container를 오염시키지 않음을 확인했다. 이 인수는 격리 CA/루프백 전용이며 운영 TLS 인수 증거로 대체하지 않는다.
- 신규 모듈은 실제 실행 경로 위주로 테스트를 보강해 statement coverage를 launchd 54%→**92%**, host 58%→**99%**, nts 67%→**93%**, read_authority 75%→**100%**로 올렸다. 전체는 82%로 하락했다가 **89%**로 회복했고(9월 25일 기준선 88% 상회), main 재검증 기준 **280 passed**, Ruff 통과다.
- 테스트는 unprivileged 실행을 위해 root 소유권 기대값만 대체하며, regular file/mode/hardlink/size/digest/identity/argv 검증은 전부 실제 코드로 수행한다. 실제 launchd `install`/`bootout`, 실제 Keychain ACL, live chrony NTS daemon은 여기 포함되지 않으며 operator 측 인수 대상이다.

## 실행 결과

아래는 레인별 최신 기록이다. 9월 25일에는 REM-1/shared/frontend 및 backend migration subset을 실행했다. 다른 레인의 이전 전체 결과를 새 실행으로 계산하지 않는다.

| 레인 | 결과 |
|---|---|
| backend 전체 (disposable PG 지정) | **463 passed, 1 skipped** |
| root accounts/library | **187 passed** |
| shared | **115 passed**, Python generation/consumer drift 검사 통과 (9월 25일) |
| shared release-profile catalog/generation subset | **39 passed**, seed 20260924 / 2,000-example profile |
| ingestion | **317 passed, 1 skipped** |
| discovery (all extras) | **124 passed, 3 skipped** |
| summarization (all extras) | **298 passed, 3 skipped** |
| ops | **53 passed** |
| 신규 REM-1 (PG/container 지정) | **190 passed**, statement coverage **88%** (9월 25일) |
| 신규 REM-1 native runtime + 실제 mTLS (PG/container 지정) | **280 passed**, statement coverage **89%** (9월 26일, main에서 재검증; 신규 모듈 launchd 92% / host 99% / nts 93% / postgres_tls 94% / read_authority 100% / credentials 86%) |
| Native preparation/probe focused | **22 passed** (9월 26일; 전체 REM-1/PG suite의 새 실행으로 계산하지 않음) |
| PostgreSQL 실제 mTLS 단일 인수 | **1 passed** — 루프백 TLS, cert 기반 `session_user=r1_tls_probe`, read-only transaction 강제, wrong-CA 거부(오류가 certificate 관련인지 확인) (9월 26일; 위 280에 포함) |
| backend migration subset | **12 passed** (9월 25일; 기존 전체 합계에 중복 가산하지 않음) |
| REM-1 새 domain release subset | **23 passed**, seed 20260925 / 2,000-example profile |
| REM-1 release-profile evidence/run/property subset | **48 passed**, seed 20260924 (위 고유 합계에 중복 가산하지 않음) |
| frontend UI/helper | **340 passed** (9월 25일) |
| frontend generator/inventory | **32 passed**, 공통 conformance 20 및 consumer regression 3 포함 |
| frontend WebKit (별도 3109) | **3 passed** |
| TypeScript / Next.js 15.5.26 production build | 통과 |
| 기존/신규 Python Ruff 레인 | 통과 (root test policy를 기존 E4/E7/E9/F로 명시해 Ruff 0.16 default 확대와 분리) |
| non-editable wheel | 9월 25일 두 wheel 재빌드·fresh/no-cache 환경에서 operator authority, inventory evaluator, extended DTO 및 migration 004 import 확인 |
| source patch | `git diff --check`, 주 checkout 적용 전/후 Git patch 검증 통과 |

9월 24일 누적 고유 Python 기준선은 **1,681 passed**였다. 9월 25일 결과는 위 레인별로 기록하며 새 subset/release 반복을 그 합계에 다시 더하지 않는다. skip은 실제 external citation, OpenSearch, Bedrock/S3 및 별도 asset integration gate이며 통과로 계산하지 않는다. REM-1의 mTLS 서버는 별도 subprocess라 parent coverage의 server.py 수치에는 반영되지 않는다. Keychain 성공/실패 ACL, 실제 clock collector, native guard의 critical-path 완전 coverage는 미완료다.

Wheel 검증에서 같은 `0.1.0` 파일 경로를 재사용하는 `uv run --isolated --with ...`가 이전 cached 환경을 사용해 신규 `adapters` import가 실패했다. `--refresh-package`만으로 해결되지 않았고 `--no-cache`로 fresh non-editable 설치 후 신규 module과 packaged migration 003 검사가 통과했다. cached 실패 실행은 합격 증거로 계산하지 않는다.

## 남은 구현과 물리 인수

단순한 테스트 환경 문제가 아니라 **남은 구현/통합 작업**도 있으므로 17-step 전체를 완료 처리하지 않는다:

1. 검증된 operator-source transaction adapter를 실제 target incarnation/fence 및 control UNKNOWN checkpoint/dispatcher와 end-to-end 결합. protected command-only DB role과 native source/clock 관측 검증을 포함한다. 현재 기본 mutation provider는 거부한다.
2. 실제 chrony NTS collector의 authenticated source/clock bound/boot-resume 자료와 role-specific Keychain/CA/TLS provider의 production composition.
3. 역할별 installer/launchd/helper/서명/append-only relay/retention 및 승인된 drive backup/실제 restore 전체 구현·검증. 현재 host 산출물은 preflight/rehearsal과 제한된 test-realm UID 준비 artifact다.
4. PROP-R1/VAL-R1 전체 trace, generation-publication 모델/소비 wire의 backend-owner parity·visibility 및 새 pure model의 production composition. PostgreSQL image blocker 해소와 남은 image/OS/native/final-artifact SBOM·scanner 증명.
5. 실제 5 req/s ×10분 latency/RSS/overload, crash/orphan/COMMIT-loss/backup/restore 전수 인수 및 G1 판정.

### 확인된 preflight 중지 조건

- 명령: `python3 ops/platform-integrity/preflight.py --root . --estimated-peak-bytes 1073741824`.
- 관측 free bytes: **11,862,491,136**; 필요한 reserve/peak: **12,884,901,888**.
- 결과: `ready=false`, `disk_reserve`, `removable_drive_unverified`, `filevault_unverified`, native commit guard/NTS clock/Keychain roles/TLS roles/restore receipt 누락.
- Docker 현재 context는 **colima**였다. 이번 작업에서 전환한 것은 아니며 데이터/volume 전환과 rollback이 검증됐다고 주장하지 않는다.
- 이 preflight의 evidence 입력은 아직 검증된 receipt provider에 연결되지 않아 파일에 true를 적는 것만으로 readiness가 올라가지 않는다.

### Backup volume 관측 갱신 (2026-09-26)

- R1OP2의 mount alias `DocSuri_Backup`을 `/Volumes/DocSuri_Backup`에서 확인했다. UUID `BB384D60-46AF-4A06-B6F7-95710B3B7A3C`, USB APFS encrypted/mounted/unlocked/writable이며 SSD01과 같은 container의 별도 volume이다. 공유 여유는 `1,537,204,109,312` bytes다.
- R1OP3=A로 매일 **03:00 Asia/Seoul(UTC+9) 백업 시작·volume 상시 연결**을 확정했다(2026-09-26). scheduler 설치/활성화는 아직 미완료다. 후속 operator 실행 및 재관측으로 volume 소유권 적용 enabled를 확인했으며 host FileVault는 Off다. 다음 로컬 검증은 [operator-handoff.md](operator-handoff.md) §4의 role access probe다.
- 새 drive를 지정한 readonly preflight는 1 GiB 추가 peak 가정에서 `ready=false`다. local free `12,882,644,992` bytes가 필요 `12,884,901,888` bytes에 못 미치며 native capability/restore 증거도 없다. 실제 backup/restore 또는 전체 G1 인수는 아직 미완료다.

## 확장 규칙 상태

- **Security**: 입력/구조화 wire/의존성/readonly/기본 거부/mTLS 부정 사례는 위 시험으로 부분 확인. 실제 저장 암호화·role/Keychain·현재 mutation 인가·signed publication·90일 audit/backup 및 image audit는 미입증이므로 SECURITY-01/06/08/10/13/14 관련 전체 인수는 열려 있다. 신규 외부 intermediary/HTML은 없어 REM-1의 SECURITY-02/04는 N/A.
- **Resiliency**: bounded read/runner, atomic head/PG step, 미확정 증거 보존은 로컬 시험. RTO/RPO, native finalization, orphan/backup/restore·실제 관측은 미완료. RESILIENCY-08의 승인 single-host 예외와 09의 bounded-capacity 대체를 유지한다.
- **PBT Full**: 예시/seeded round-trip/stateful/oracle/boundary 검증을 추가했으나 모든 PROP/VAL의 실제 provider coverage 완료를 주장하지 않는다. 적용 transport-only 부분은 실제 통합 시험으로 구분한다.

## 재실행 경로

- `platform_integrity`: `uv sync --frozen --all-extras --python 3.13`; `uv run --frozen --all-extras pytest` 및 `ruff check .`.
- PostgreSQL integration은 별도 `rem1_test` DB, loopback 15439, test-only credential로만 실행하도록 guard한다. 운영 DSN을 주입하지 않는다.
- frontend: `pnpm install --frozen-lockfile`; `pnpm run check:types`; `pnpm run test:contracts`; `pnpm test`; `pnpm exec tsc --noEmit`; `pnpm build`. 브라우저는 `playwright.rem1.config.ts`의 3109 별도 서버를 쓴다.
- shared: `uv run --frozen python tools/generate.py --check` 및 `uv run --frozen pytest`.
- shared release catalog/generation: `R1_TEST_PROFILE=release uv run --frozen pytest tests/test_schema_catalog.py tests/test_offline_generation.py --hypothesis-seed=20260924`.
- REM-1 declared catalog: `uv run --frozen --all-extras python -m docsuri_platform_integrity.cli check-schemas ../shared` (`platform_integrity/` 기준). manifest 없는 임시 입력은 명시 `--flat`을 사용하며 실제 inventory 증거로 취급하지 않는다.
- 이번 REM-1 전체: `REM1_TEST_PG_DSN=postgresql://rem1_test:isolated-test-only@127.0.0.1:15439/rem1_test uv run --frozen --all-extras pytest --hypothesis-seed=20260924 --cov=docsuri_platform_integrity --cov-report=term-missing`; 이어서 `uv run --frozen --all-extras ruff check .`. DSN은 작업 전용 synthetic fixture다.
- release profile: `R1_TEST_PROFILE=release uv run --frozen --all-extras pytest tests/test_current_evidence.py tests/test_properties.py tests/test_run_recovery.py --hypothesis-seed=20260924`.
- fresh wheel smoke: `uv build --wheel --out-dir dist` 후 별도 임시 작업 경로에서 `uv run --no-cache --isolated --no-project --python 3.13 --with <absolute-wheel-path> python -I ...`로 `CurrentEvidenceVerifier`, `reserve_selection` 및 `migrations/003_verification_protocol.sql`을 확인했다. 이 smoke는 packaging/import 검사이며 전체 production closure/SBOM 인수를 대신하지 않는다.
- native binding/permission 설치 없이 새 control adapter를 public route에 노출하지 않는다. test-only observation으로 생산 권한을 구성하지 않는다.
- native runtime focused: `REM1_TEST_PG_DSN=postgresql://rem1_test:isolated-test-only@127.0.0.1:15439/rem1_test REM1_TEST_CONTAINER=rem1-test-pg-20260924 uv run --frozen --all-extras pytest tests/test_launch_policy.py tests/test_runtime_credentials.py tests/test_postgres_tls.py tests/test_nts_clock.py tests/test_host_configuration.py tests/test_reader_roles_postgres.py tests/test_postgres_mtls.py` (49 tests).
- 실제 mTLS 테스트는 검증 전용 container가 **영속 volume**을 사용해야 한다. `docker run -d --name rem1-test-pg-20260924 -e POSTGRES_USER=rem1_test -e POSTGRES_PASSWORD=isolated-test-only -e POSTGRES_DB=rem1_test -p 127.0.0.1:15439:5432 -v rem1-pgdata-20260926:/var/lib/postgresql/data postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`. `/var/lib/postgresql/data`를 tmpfs로 두면 `docker restart`마다 클러스터가 재초기화되어 `ALTER SYSTEM` 설정이 소실된다. image entrypoint는 시작마다 `pg_hba.conf`를 다시 쓰므로 test는 **restart 후** HBA를 복사하고 reload한다.
- 9월 25일 source delta를 별도 baseline index에서 생성한 incremental Git patch로 통합하고 최종 authority 교정은 apply_patch로 반영했다(총 69파일). 전체 `rem1-20260925.patch`와 9월 24일 patch/worktree를 보존했으며 사용자 문서는 source patch에 포함하지 않았다.
- 최종 wheel SHA256: REM-1 `7b24ca3fe017568eee32f463992d56d3a894a38ad169e7b3066cb2fa5580ba86`, shared `4383676eb69ca47190d2ad68b05d3290b43bf99a055593f465ae38b8c4b4eb49`. 이 두 wheel의 fresh import는 packaging 검증이며 앞선 role SBOM을 새 artifact 인수로 소급하지 않는다.
- 최종 source patch 역적용 check와 whitespace 검사가 통과했다. 작업 전용 PG 컨테이너는 2026-09-25T06:40:50Z에 중지·자동 제거했다. 새 plan/summary/operator handoff/audit는 Markdown debug-check 통과; 기존 state 파일 전체의 FR-27 강조문 Prettier idempotence 오류는 HEAD에서도 재현되며 이번 추가 section의 오류가 아니다.
- runtime/production 변경은 현재 준비되지 않았으며 별도 설치·복원 증거와 maintenance window가 필요하다. REM-2/3/4의 F01/F02/F03/F04/F05/F07/F09/F10/F11/F12는 아직 이 체크포인트에서 구현 완료되지 않았다.

### PostgreSQL runtime image 후보 재작성 (2026-09-26)

- operator 승인("digest 교체")에 따라 pinning된 `postgres@sha256:a3b7f434…`(7,384 components / 323 findings / **98 blocking**)을 재평가했다. 같은 16.15의 새 trixie build는 74 blocking으로 줄지만 잔여 74건이 전부 `wont-fix`/`not-fixed` OS 계층이라 tag 이동으로는 0이 될 수 없다.
- 98건의 정밀 분해: **24건이 `/usr/local/bin/gosu` 단일 바이너리의 go1.24.6 stdlib**, 74건이 Debian trixie OS 계층(libxml2, util-linux, gnupg, libacl, glibc, libperl 등)이다. gosu 24건은 **모든 upstream tag에 동일하게 존재**해 tag 이동으로 제거되지 않는다.
- Alpine variants는 OS 계층을 1건까지 줄였다: `postgres:16.15-alpine3.24`은 870 components / 50 findings / 25 blocking(gosu 24 + zlib 1). 동일 PostgreSQL 16.15.
- 따라서 `ops/platform-integrity/images/postgres-alpine-nosu.Dockerfile`로 **gosu를 제거하고 비특권 postgres uid로 실행하는 derived image**을 만들었다. gosu는 root→postgres降格에만 존재하므로 uid 0이 아닐 때 entrypoint가 이미 그 분기를 건너뛴다. 결과는 **865 components / 4 findings / 1 blocking**이다.
- 잔여 1건은 alpine `zlib 1.3.2-r0` `CVE-2026-85091`(High, fix state 없음)이다. alpine base 갱신 또는 기한부 예외가 필요하며, 이 상태로 G1을 통과로 기록하지 않는다.
- build는 `SOURCE_DATE_EPOCH` 고정 + `--provenance=false` 없이는 config digest가 매번 달라 compose에 pin할 수 없다. 이를 Dockerfile에 기록했고 재현 가능한 image config digest는 `sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`다(두 번 build해 동일함을 확인).
- **검증**: 이 정확한 digest의 image로 실제 mTLS test와 전체 suite를 돌려 **280 passed / statement coverage 89% / Ruff 통과**를 확인했다. teardown 후 `ssl=off`, `postgresql.auto.conf` 88 bytes, HBA probe 규칙 0건. `sbom-targets.json`에 superseded image와 근거를 함께 기록했다.
- 비root 전환의 운영 영향: PGDATA volume은 첫 start 전에 postgres uid 소유로 준비되어야 한다(`docker run --user 0 … chown 70:70`). 이 절차는 Dockerfile 주석에 있다.
- **아직 하지 않은 것**: 운영 compose digest 교체는 operator maintenance window에서 실행해야 한다. 여기서는 task-owned test container만 교체했다.

## Signed capability receipt verifier — preflight readiness (2026-09-26T13:36:10Z)

### 해결한 결함
`preflight()`가 evidence 키가 있어도 항상 `<capability>_requires_receipt_verification`를 추가해 `ready=true`가 구조적으로 불가능했다. 이제 `platform_integrity/src/docsuri_platform_integrity/deployment/receipt.py`의 실제 서명 검증으로 대체했다.

### Receipt 계약 (`deployment/receipt.py`, 신규)
- `Capability` StrEnum 5종: `native_commit_guard`, `nts_clock`, `keychain_roles`, `tls_roles`, `restore_receipt`.
- `Receipt`: capability / host(`IOPlatformUUID`) / release / `ValidityWindow` / artifact·evidence `Digest`. strict immutable `Value` 기반, extra 금지.
- `TrustKey`: manifest가 신뢰하는 키. `revoked`, 자체 validity, canonical unpadded base64url 공개키.
- `verify_capability()`는 결론과 **사유를 항상 함께** 반환한다. 순서: `malformed` → `untrusted_key` → `revoked_key` → `key_not_valid_at_observation` → `signature_invalid` → `payload_invalid` → `capability_mismatch` → `host_mismatch` → `release_mismatch` → `window_too_long` > 7일 → `outside_validity`. 미해결은 proven이 아니다.
- `host_identity()`는 하드웨어 `IOPlatformUUID`를 쓴다. 재부팅·이름변경·재설치에도 유지된다.
- `MAX_WINDOW_US` = 7일. 영구 "verified" 플래그를 acceptance로 인정하지 않는다.

### preflight wiring (`ops/platform-integrity/preflight.py`)
- `--evidence`는 `{release, trustKeys: [파일명], receipts: {capability: envelope}}`를 받는다.
- **trust는 evidence와 분리**된다. `preflight(trust=...)`는 별도 인자로만 주어지고, 신뢰 키는 evidence 파일과 같은 디렉터리로 resolve된 경로만 허용한다(`candidate.parent != base`면 거부). evidence가 호스트 어디서든 키를 끌어올 수 없다.
- `ready`는 이제 도달 가능하다. 실제 CLI로 5개 capability 전부 검증 receipt를 넣으면 `{"ready": true, "reasons": [], "provenCapabilities": [5종]}`와 exit 0을 확인했다(임시 self-signed 키, throwaway이며 acceptance 근거로 쓰지 않고 즉시 삭제).

### 구현 중 발견·교정한 결함 3건
1. **`model_validate(dict)`는 enum 문자열을 거부한다.** `Value`가 `strict=True`라 `Capability` 필드가 JSON round-trip 후 `is_instance_of` 실패했다. 저장소 관례대로 `Receipt.model_validate_json(canonical(payload))`로 변경했다. 부수 효과로 비-canonical 인코딩도 거부된다.
2. **`bytes` 필드는 JSON 직렬화가 안 된다.** `TrustKey.public_key: bytes`는 `model_dump_json()`에서 `PydanticSerializationError`가 났다(키를 디스크에 못 씀). canonical base64url `str`(43자 regex)로 바꾸고 `trust_key()` 생성 helper를 추가했다.
3. **`ValidityWindow.contains`는 `upper < valid_until`을 요구한다.** `valid_until == now`인 receipt는 `outside_validity`로 거부된다. 테스트 기본 창을 `[now-1d, now+1d]`로 잡았다.

### `ops` package 변경
- `docsuri-platform-integrity==0.1.0`을 dependency로 추가하고 `[tool.uv.sources]`에 path source를 등록했다.
- `requires-python`을 `>=3.11` → `>=3.13`으로 올렸다. 새 dependency가 3.13 이상이므로 그대로 두면 만족 불가능한 요구가 된다. 로컬 interpreter는 3.13.7이다.
- lock 추가분: `docsuri-platform-integrity`, `cryptography`, `cffi`, `pycparser`, `rfc8785`(기존 `psutil` 외).

### 검증 결과
- `platform_integrity`: **308 passed, 0 skipped**, statement coverage **89%**, Ruff 통과. `receipt.py` 95%, `postgres_tls.py` 94%. 실제 loopback mTLS test가 derived image 위에서 **실제로 실행**됨(`REM1_TEST_PG_DSN` + `REM1_TEST_CONTAINER` 필요 — 둘 다 없으면 조용히 skip된다).
- `ops`: **68 passed** (기존 53 + 신규 preflight receipt 15), Ruff 통과.
- 신규 테스트 `ops/tests/test_preflight_receipts.py` 15건: verified/other-host/other-release/untrusted-key/revoked-key/expired/30-day-window/boolean-evidence/trust-key 경로 이탈/non-object evidence/non-canonical JSON/`evidence`와 `trust` 분리.
- 6개 파일을 preserved WT에 byte-identical로 동기화했고 `platform_integrity` 트리 전체 parity를 재확인했다.

### 남은 코드 gap (이번 변경으로 해소되지 않음)
- Receipt를 **발급**하는 installer가 없다. `issue()`만 있고, 실제 native capability를 검증해 서명하는 경로가 구현되지 않았다.
- launchd installer/manifest, purpose Keychain, live chrony NTS, backup/archive 명령과 scheduler, native commit guard는 여전히 미구현이다.
- 따라서 `ready=true`는 **도달 가능**해졌지만 실제 production acceptance 증거는 아직 없다. G1 미통과.

## Readonly capability probes + receipt issuer (2026-09-26T14:05:00Z)

### 구조
`deployment/receipt.py`(verifier)와 짝을 이루는 `deployment/capability.py`(probe)를 추가하고, `ops/platform-integrity/issue_receipt.py`를 issuer로 추가했다. Verifier가 "receipt를 믿어도 되는가"를, probe가 "실제로 성립하는가"를, issuer가 "증명된 경우에만 서명한다"를 각각 담당한다.

### Probe 5종 (`deployment/capability.py`, 신규, statement 97%)
전부 **readonly**이고 절대 raise하지 않는다. crash한 probe는 통과한 probe와 구분되어야 하므로, 불가하면 `proven=False` + 사유를 반환한다.
- `probe_keychain_roles` — 선언된 모든 purpose key가 noninteractive로 읽히고 실제 TLS bundle인지 확인. **공개 인증서만 fingerprint**하고 private key는 hash/log/반환하지 않는다(receipt가 private-key 검증 oracle가 되지 않도록).
- `probe_tls_roles` — scoped role이 실제로 mTLS로 로그인하고 비특권인지 확인.
- `probe_nts_clock` — `ProtectedClock`로 보호된 frame을 실제 reader와 동일 조건으로 검증.
- `probe_native_commit_guard` — **계획 밖 effect가 거부되는지**로 증명한다. `guard()`는 frozen-plan 소속 검사를 DB I/O보다 먼저 하므로 identity 하나로 거부 확인이 되고, 실제 commit은 없다. 즉 provisioned이면 거부하고 stub이면 애초에 guard를 만들 수 없다.
- `probe_restore_receipt` — 최근·암호화·검증되었는지, host/release 결합, 그리고 **source와 다른 incarnation으로 복원**되었는지(같은 incarnation 복원은 증거가 아니다).
- `ProbeSet.run()`은 capability마다 실제 관찰 1회로 판정하고, 설정 없으면 `<capability>_not_configured`로 "미설치"와 "설치됐지만 고장"을 구분한다.
- `receipt_from()`은 proven이 아니면 `PermissionError`, 7일 초과 창이면 `ValueError`로 거부한다.

### Issuer (`ops/platform-integrity/issue_receipt.py`, 신규)
- 설정 문서는 **reference만** 담는다(keychain 경로, service/account, DB target, frame 경로, restore receipt 경로). credential·연결·키는 문서에서 읽지 않는다.
- `--probe-only`는 key를 읽지도 않고 아무것도 쓰지 않는다.
- **한 번 probe한 snapshot으로 전체 run**을 처리한다( capability마다 재-probe하지 않아 관찰이 서로 다르게 찍히지 않는다).
- **하나라도 proven이 아니면 run 전체를 거부하고 파일을 전혀 쓰지 않는다.** 부분 성공이 acceptance처럼 보이면 안 된다.
- 서명 키는 symlink 거부, root 또는 self 소유, `0o077` 마스크, nlink 1, 크기 제한을 읽기 **전에** 확인한다. receipt는 0600으로 atomic write(temp + `os.replace`)한다.
- ~~`native_commit_guard`는 ... 이 명령에서 **발급하지 않는다**(`notIssuableHere`로 명시).~~ **2026-09-26 정정:** live `OperatorAuthority`에서 **발급한다**. 아래 "Step 6 live `native_commit_guard` issuance" 절을 본다.

### 구현 중 발견·교정한 결함 2건
1. `probe_restore_receipt`가 `lower <= completed`를 요구해 **방금 끝난 복원을 부당하게 `restore_stale`로 거부**했다. 관측 창이 한 순간이므로 올바른 조건은 "미래가 아니고, 30일 이내"다.
2. `build_probe_set`가 잘못된 타입의 섹션(`"nope"`, `5`)에서 `TypeError`로 crash했다. 이제 명시적 `ValueError`로 검증해 CLI가 `probe_configuration_unusable`로 fail-closed 한다. `keychainRoles` 항목은 정확한 키 집합, 절대 경로, traversal 부재를 확인한다.

### 실제 round trip 검증 (실제 CLI 3단)
1. `--probe-only` → `restore_receipt: proven`
2. `--capability restore_receipt` 발급 → `ISSUED`
3. `preflight.py --evidence` → `provenCapabilities: ["restore_receipt"]`, capability 계열 잔여 사유 0건
모두 임시 키로 수행했고 즉시 삭제했다. **acceptance 근거가 아니다.**

### 검증 결과
- `platform_integrity`: **340 passed, 0 skipped**, statement coverage **89%**, Ruff 통과(`capability.py` 97%, `receipt.py` 95%). 실제 loopback mTLS 포함.
- `ops`: **86 passed**(기존 68 + issuer 18), Ruff 통과.
- 신규 테스트: `platform_integrity/tests/test_capability_probes.py` 32건, `ops/tests/test_issue_receipt.py` 18건.
- WT 동기화: 신규 4개 파일 + 이전 세션의 `images/postgres-alpine-nosu.Dockerfile`과 `sbom-targets.json`(main에만 있던 것)까지 byte-identical. 트리 전체 parity 재확인.

### 남은 코드 gap
- `native_commit_guard` receipt 발급 경로(Step 6 operator authority 실물 필요).
- launchd installer/manifest, purpose Keychain 실제 생성, live chrony NTS, 실제 DB mTLS role, backup/archive 명령과 scheduler.
- 5개 capability 중 실제 operator 증거는 여전히 0건이고, image 잔여 finding(`CVE-2026-85091`)도 그대로다. G1 미통과.

## launchd installer/manifest 구현 (2026-09-26)

`deployment/launchd.py`에 `install` / `uninstall`을 추가했다. 이전에는 `render`(GENERATED_NOT_INSTALLED)와
`exec`만 있어 plist를 launchd에 올리는 경로 자체가 없었다.

### 추가된 것

- `install(profile, manifest_path, replace=False)` — root·darwin·launchctl 무결성 → realm 무결성 →
  계정/uid/gid 일치 → role 작업 디렉터리 소유자 → **모든 frozen artifact digest**를 확인한 뒤에야
  plist를 `/Library/LaunchDaemons/<label>.plist`에 원자적으로 쓰고 `launchctl bootstrap system` 한다.
  마지막에 자기 상태를 재검증하고, launchd가 job을 잡지 않았으면 성공을 보고하지 않는다.
- `uninstall(profile)` — bootout 후 launchd가 여전히 잡고 있는 job이 있으면 **삭제하지 않고 실패**한다
  (실행 중 job의 plist를 지우면 stop 수단이 없는 고아가 된다). Label 불일치 plist는 foreign로 간주해 거부.
- `entry_label` / `plist_path` / `role_account` — label·파일명·계정명을 한곳에서 파생. test/production이
  경로·계정·label 전부 달라 같은 system domain에서 충돌하지 않는다.
- `is_published()` — manifest digest + plist 바이트 + `launchctl print` 3중 확인.
- `write_root_file()` — symlink 거부, root 비소유 파일 거부, 임시 파일→fsync→`os.replace`→디렉터리 fsync.

### 스스로 잡은 결함

1. **최초 구현이 `deployment.json` 존재만으로 `ALREADY_INSTALLED`를 반환했다.** plist가 사라졌거나
   launchd에서 bootout된 반쯤 해제된 상태를 '설치됨'으로 오인하는 결함이다. `is_published()` 3중 확인으로
   바꾸고, drifted 상태는 **bootout 먼저 → 고쳐 쓰기** 순서로 복구한다(고장 난 job을 고치는 동안 돌게 두지 않음).
2. **refuse-silent-replacement 가드를 리팩터링 과정에서 떨어뜨렸다.** 다른 manifest를 `--replace` 없이
   조용히 갈아끼우던 상태가 되어 되돌릴 수 없는 변경이 가능해졌다. 복구하고 테스트로 고정했다.
3. `uninstall`에 orphan 방지 검증이 없었다. 추가했다.
4. `require_root`가 launchctl를 root 소유로 검사해 비권한 테스트가 구조적으로 불가능했다. root 소유 대신
   **symlink/쓰기 가능**을 검사하는 쪽이 실제로 검증 가능한 보안 속성이므로 코드를 바꿨다.

### 순서

모든 검증 → 이전 deployment bootout → plist 쓰기 → manifest 쓰기 → bootstrap → 재검증.
쓰기 전에 하나라도 실패하면 파일은 0개다.

### 검증

- `test_launch_policy.py` 24 → 34건(신규 10). 전체 `platform_integrity` 350 passed / 0 skipped /
  statement 89% / Ruff 통과(`launchd.py` 88%).
- 비root `install`/`uninstall` → `BLOCKED` exit 2, `render` 정상, `/Library/LaunchDaemons` 무변경 확인.
  **root 실제 install은 수행하지 않았다.** 테스트의 launchctl는 recorder다.
- WT 동기화 후 34 passed, `git diff --check` 통과.

### 남음

계정 9종 생성, toolchain/artifact 배치, 실제 test-profile rehearsal, production install(maintenance window).

## Step 6 live `native_commit_guard` issuance (2026-09-26)

- `deployment/operator_plan.py` (new): `read_frozen_plan` is the only way a plan reaches the authority. It
  requires a caller-supplied digest, so a plan edited after approval cannot be re-read; it also enforces
  owner (`root`/current), no group/world write, a single hard link, no symlink, a size cap, and canonical
  re-encoding plus release agreement.
- `deployment/capability.py::probe_native_commit_guard` now proves the guard in both directions. It picks an
  identity that provably is not in the plan via `itertools.count()` (no naming scheme assumed), requires the
  exact refusal message, then requires the planned identity to be admitted. It stops at the yield without
  performing an effect, because the adapter refuses finalization after the body; the verdict comes from a
  flag set inside the body. Evidence records the sorted identity set and both observations.
- `ops/platform-integrity/issue_receipt.py`: added `GuardSession`, `build_guard_authority` and
  `guard_session`, so the five probes run against one live authority. The actor role is derived from
  `operatorDatabase.user`, the `ProtectedClock` is mandatory, the connection is `PostgresTLS` readonly
  autocommit, `approval.plan` must equal the pinned `planDigest`, and the authority and fence targets must
  match. All five capabilities are requested by default and `notIssuableHere` is gone.
- Two non-obvious behaviours that live testing forced, both now covered by regression tests:
  `MutationUnavailable` subclasses `PermissionError`, so a revoked or out-of-scope approval is a legitimate
  refusal rather than a crash; and `entered` must be inspected before the exception message, because a guard
  that admits and then raises the post-yield refusal is indistinguishable from an up-front refusal by
  exception type alone.
- `tests/test_guard_receipt.py` (new, 10 tests) is the first coverage of the guard through real SQL: it
  replays migrations `001~004`, writes a real `r1_control.authority` row, and exercises revoked approval, wrong
  operator role, a database row naming a different plan, a fence for another incarnation, an expired decision
  deadline, and a non-idle connection; it also shows the planned effect admitted, a normal signed receipt that
  the existing `verify_capability` accepts, and an empty `r1_audit.events`/`r1_control.outbox` with the
  connection left `IDLE`.
- Result: `main` 382 passed / 89% statements, Ruff clean. `ops` 98 passed, Ruff clean. Tests for `ops` run
  from `ops/`, not from `ops/platform-integrity/`, which is the CLI package.

## Step 6 target effect adapter (2026-09-26)

- `migrations/006_target_effects.sql` (new): the target plane, kept separate from `r1_control` on purpose.
  `r1_target.state` holds the exact native digest a compare-and-set moves between; `r1_target.effect_ledger`
  is an append-only row bound to run/step/attempt/fence epoch. A unique index on `(run_id, step, fence_epoch)`
  means the database refuses a repeat even if two writers somehow both reach the effect.
- `adapters/target_effect.py` (new): `PostgresTargetExecutor.apply` takes a dedicated physical autocommit
  connection, holds a session-level `pg_advisory_lock` across the whole effect, and drives the guard's own
  protocol — `guard()` → one target transaction → compare-and-set on `expected_before` → state write →
  ledger row → `before_commit()`. The finalizer's `FOR SHARE` re-read happens while the transaction still
  holds the effect, which is the mechanism that serializes a revoke against a commit.
- Failure classification is the reason the adapter exists, so it is deliberate rather than incidental.
  A rejected statement, a `MutationUnavailable` refusal and a stale precondition are all *provable*
  non-applications and propagate as themselves. Only a lost connection becomes `TargetOutcomeUnknown`,
  because there the effect may well be durable and reporting either success or failure would be a guess.
- `PostgresTargetExecutor.observe` is the only resolver and is read-only. A ledger row is durable proof
  of a commit, an unchanged target is proof of a quiet abort, and any other digest stays `UNKNOWN`,
  since an unexpected observation must never be read as a decision.
- `tests/test_target_effects.py` (new, 16 tests) exercises all four Step 6 fault cases against the
  disposable database: two concurrent target writers, a fresh fence epoch, the index refusing a forged
  repeat, revoke before the effect, a revoke landing mid-transaction, rollback after the effect write,
  no session-lock leak after rollback, a lost commit reply that leaves the effect durable while the caller
  is told UNKNOWN, a blind retry then being impossible, and the three observation outcomes.
- The mid-transaction revoke test is mutation-verified: deleting the finalizer re-check makes the effect
  commit under an already-revoked authority and the test fails. The privileged-apply hazard is pinned by a
  regression test, not merely asserted in prose.

## Step 6 append-only and scoped command roles (2026-09-26)

- `migrations/007_command_roles.sql` (new) replaces the two append-only *claims* in `001`/`006` with
  enforced guarantees, and removes the caller's ability to write tables at all.
  - `r1_target_owner`, `r1_target_operator` and `r1_target_auditor` are NOLOGIN group roles.
    `r1_target_operator` holds no INSERT/UPDATE/DELETE/TRUNCATE on any table and no rights in
    `r1_control`; its only write capability is EXECUTE on one function.
  - `r1_target.effect_ledger` and `r1_control.outbox` reject UPDATE, DELETE **and TRUNCATE**. A row-level
    trigger cannot see TRUNCATE at all, so each table also has a statement-level guard; without it the
    append-only property was silently false.
- `r1_target.apply_effect(...)` is a `SECURITY DEFINER` command: the only inputs are scalars, the
  compare-and-set target is fixed, and the row lock is taken by the function. It re-verifies the
  authority itself, because **the Python guard is defence in depth, not the enforcement boundary** — the
  scoped role can call this function without a guard in the call path, and a first version of this
  migration allowed exactly that: an effect applied under a revoked authority.
  - Refusals use explicit SQLSTATEs so the adapter classifies by code, never by matching message text:
    `R1T01` (compare-and-set lost) → `TargetStateChanged`, `R1T02` (grant not current) →
    `MutationUnavailable`. A custom ERRCODE is not one of psycopg's known classes and arrives as the
    generic database error, which is why the SQLSTATE is the discriminator.
  - Checked in the database: not revoked, purpose is `apply`, and the grant's target, namespace and
    incarnation must match the target being moved. The target must also be the live incarnation at the
    caller's fence epoch.
  - **Deliberately not checked in the database**, and this is a real boundary rather than an omission:
    the validity window is decided by the guard, because judging it in SQL would mean trusting
    `clock_timestamp()`, which is not the protected chrony/NTS clock the plan requires; and the approval's
    actor label is decided by the guard, because binding a session to that label needs the database role
    mapping that Step 10 still has to provide. Both are stated in the migration so the next reader does
    not mistake them for oversights.
- `adapters/target_effect.py` no longer computes a ledger digest or a timestamp in Python; the database
  records `applied_at` and both digests. The adapter keeps the session advisory lock, the guard protocol,
  and the `UNKNOWN` classification.
- `tests/test_target_effects.py` is now 28 tests and `adapters/target_effect.py` is at 100% statement
  coverage. Beyond the original fault cases it now pins: ledger and outbox UPDATE/DELETE/TRUNCATE
  rejection, the operator role having no write right anywhere, the auditor reading only, a cross-target
  or cross-incarnation escape being refused, a non-`apply` grant being refused, a stale target epoch being
  refused, a revoke landing *after* the guard has already read being caught by the command itself, and
  scoped read-only reconciliation.
- Every new enforcement is mutation-verified rather than asserted: removing the `revoked`, `target`,
  `namespace`, `incarnation`, `purpose` or `epoch` predicate each fails a named test, as does removing the
  scoped grant or the TRUNCATE guard. Two holes were found this way and closed — a cross-target escape
  that no test covered, and an untested `purpose` predicate.
- Two test-hygiene defects were fixed rather than worked around: `tests/test_reader_roles_postgres.py`
  applies every migration but only cleared `r1_control` and `r1_audit`, so it collided with leftovers in
  `r1_target`; and a dead `except TargetStateChanged` clause in the adapter was removed once the CAS moved
  into SQL and that exception could no longer be raised inside the guarded block.

## Step 6 durable dispatch and conservative recovery (2026-09-27)

This checkpoint supersedes the earlier claims that an unchanged state proves abort and that a ledger
row proves historical authorization. Nine new regression cases failed against the previous adapter:
an uncommitted writer was reported aborted, six changed bindings reused an unrelated ledger receipt,
a direct SQL transaction committed after revocation, and ledger existence was treated as authorization.

- `migrations/008_target_reconciliation.sql` adds full target/namespace/incarnation/plan/approval
  metadata to new ledger rows. Existing rows remain immutable and unbound; the upgrade never invents
  provenance. The old command signature is removed. New receipts use a versioned, independently
  verified canonical digest.
- The database command and adapter use the same target-scoped advisory exclusion, independent of run,
  step, attempt and incarnation. Lock waits are bounded by the existing attempt deadline. Caller-chosen
  keys that would split the target scope are rejected.
- A deferred database constraint rechecks grant revision, revocation, purpose, plan, target and epoch
  at commit, holding target-identity then authority SHARE locks through commit. Tests prove both revoke
  orderings, including direct scoped SQL calls. Weak `synchronous_commit`/`fsync` settings cannot pass
  finalization. Critical audit now also rejects TRUNCATE.
- `PostgresTargetExecutor.observe` uses the injected connection source, target exclusion and one
  repeatable-read, read-only snapshot. Busy writer, legacy/mismatched/corrupt receipt, or absence without
  a newer fence remains UNKNOWN. NO_EFFECT_CONFIRMED needs an unchanged state, no ledger, exclusive
  observation and a strictly newer native epoch that prevents delayed old dispatch; epoch rewind is
  rejected. The resulting abort receipt binds the exact effect and observed epoch.
  A post-observation WAL flush barrier is required for durability; `fsync=on` alone is not proof that
  an observed commit was flushed. Concurrent unflushed WAL conservatively withholds verified completion.
- `application/dispatch.py::RunDispatcher` connects the existing control store and target helper:
  acknowledged UNKNOWN + audit + outbox, one guarded target apply, then result reconciliation. It
  requires a current control-purpose authority port and validates the configured approval against the
  stored attempt/frozen plan. Preparation failure or acknowledgement loss never dispatches. Exceptions
  after preparation never trigger retry or automatic resume.
- A successful live guarded acknowledgement can provide authorization proof for its exact receipt.
  Explicit recovery after a lost reply records COMMITTED/PAUSED when the effect is known but historical
  authorization proof is absent; it never fabricates SUCCEEDED. Current reconcile authorization is
  checked again after observation. A later approval does not retroactively authorize the old effect.
- `tests/test_dispatch_postgres.py` covers real preparation/audit failures, lost target/result replies,
  competing dispatchers, scope denial, fresh-attempt recovery after fencing, and authority changes during
  observation. `tests/test_dispatch_properties.py` generates structured plans, failure cuts and retry
  counts to assert no effect before acknowledged preparation and no repeated effect after interruption.

Validation: **456 platform tests passed**, **98 ops tests passed**, Ruff and `git diff --check` passed.
Platform statement coverage is **90%**; both `target_effect.py` and `application/dispatch.py` are **100%**.
Hypothesis seed **20260927**, plus the new failure-cut property in the release profile (2,000-example
limit). The existing Starlette/httpx deprecation warning remains.

### Remaining Step 6 acceptance boundary

The tests use disposable PostgreSQL, synthetic protected time, and test source authority. Direct SQL
still cannot prove protected-clock validity or the session-to-approval actor mapping. The combined
guarded helper has not been accepted under the production-equivalent non-superuser login; control
purpose authorization is an injected current-source port, not a new identity service. These remain
blocking native-provider/least-privilege acceptance obligations shared with Step 10. Step 6 and G1
remain open. A ledger checksum or the new dispatcher is not a capability receipt.

### Extension compliance for this implementation checkpoint

| Rules | Status | Evidence / scope |
|---|---|---|
| SECURITY-03/05/11/13/14/15 | Compliant for this slice | Atomic audit/outbox, parameterized bounded command, exact receipt verification, append-only audit, conservative failures and connection cleanup |
| SECURITY-06/08/12 | Open for stage acceptance | Scoped SQL denial is tested; native login-to-approval mapping and current protected source/clock provisioning are still required |
| SECURITY-01/02/04/07/09/10 | N/A to this change | No storage/network/HTML/deployment/dependency configuration changes; existing deployment and supply-chain gates remain separate |
| RESILIENCY-10/13/14 | Compliant for this slice | Bounded target waits, explicit reconciliation, real commit/failure races and generated failure cuts |
| RESILIENCY-01~09/11/12/15 | N/A to this change | Existing approved topology, capacity, health, backup, rollout and incident policy are not redefined here |
| PBT-01~10 | Compliant for this slice | Existing contract/round-trip and stateful run model reused; domain-shaped plans, independent native effect counter, seeded failure cuts, shrinking and actual PG regression cases |

## Step 6 current source and authenticated login mapping (2026-09-27)

- `migrations/009_operator_role_binding.sql` introduces an immutable mapping from an approval revision
  and actor to a login name **and PostgreSQL role OID**. Role deletion/recreation does not reuse authority.
  `bind_operator_role` rejects privileged, owner-member or table-write-capable logins; identical binding
  is idempotent, while reassignment needs a new source revision. Bind/revoke and critical audit/outbox
  are atomic. Source rows are owner-reviewed inputs; this command does not issue approvals.
- `r1_control.read_operator_authority` enforces the mapping against `session_user` and owns the native
  SHARE-lock operation. The process role can read its mapped source through the function but cannot
  read/write the authority table, rebind itself, or revoke grants. Finalization uses the existing
  target-identity then source-grant lock order. Direct scoped target calls check the mapping at insert
  and again at commit, including changes made after the initial guard read.
- `adapters/operator_authority.py` consumes that scoped port, with no legacy broad-SELECT fallback.
  `adapters/command_authority.py::PostgresCommandAuthority` replaces a synthetic dispatcher callback
  with fresh, read-only source checks: separate `run`/`reconcile` grants, exact actor/plan/artifact/policy
  scope, revision, protected clock window and original deadline. Reads do not renew grants or write audit.
- `deployment/operator_helper.py::build_operator_dispatcher` assembles the target helper and current
  control-purpose source. It pins the exact planned step including both pre/postconditions, requires
  `ProtectedClock`, and derives role identities from explicit database transports. `PostgresTLS.open`
  exposes a caller-owned physical connection for this assembly, preserving verified TLS, identity
  checks, temporary credential removal and failure cleanup. Target connection sources cannot silently
  fall back to an ambient DSN.
- `tests/test_operator_roles_postgres.py` authenticates genuinely separate, temporary non-superuser
  logins rather than using SET ROLE from a superuser session. It covers guarded execution, direct-call
  denial for unmapped principals, forbidden source DML, both revocation orderings, atomic audit failure,
  role recreation, immutable revision binding, scope/purpose denial, no renewal, and protected-clock
  expiry/discontinuity/loss. The isolated owner only provisions fixtures and supplies the still-existing
  control-store coordination port. Temporary login credentials are generated in memory and roles removed.
- `tests/test_operator_authority_properties.py` generates domain-shaped frozen plans and varies every
  bound source-authority dimension; mismatches cannot authorize. Existing legacy guard/receipt tests now
  install migration 009 and explicitly identify their synthetic owner mappings.

Verification: **496 platform tests passed**, **98 ops tests passed**, Ruff and `git diff --check` pass.
Total statements **90%**; helper assembly and TLS adapter **100%**, command authority **97%**. The new
property also passes the release profile (2,000-example limit), seed **20260927**. One existing
Starlette/httpx deprecation warning remains.

### Current acceptance boundary and extension status

The approval-to-login mapping and non-superuser target guard are now implemented and exercised against
real PostgreSQL. A direct mapped SQL caller still does not prove protected-clock validity; that check
belongs to the protected helper. The test transport uses disposable database logins and the clock uses
synthetic protected frames. Live Keychain/NTS plus the production-equivalent transport/helper installation
remain physical acceptance obligations. The control checkpoint store still needs scoped command roles
and enforced checkpoint provenance at the helper boundary. Step 6/G1 remain open.

For this checkpoint, SECURITY-03/05/06/08/11/13/14/15 are compliant within the tested target/source-command
scope (exact login binding, narrow functions, audited administration and fail-closed cleanup);
SECURITY-01/07/12 physical transport/key/MFA acceptance and control-store-wide least privilege remain open.
SECURITY-02/04/09/10 are N/A to these source changes (no intermediary, HTML, deployment or dependency change).
RESILIENCY-10/13/14 are compliant for bounded source calls, conservative recovery and actual fault tests;
other resiliency rules retain their approved single-Mac/design-stage assignments. PBT-01~10 continue to
use the existing contract/state models plus the new seeded source-scope invariant and native regressions.

## Step 6 scoped coordination and prepared execution (2026-09-27)

- `010_control_commands.sql` adds the inaccessible `r1_run_owner` and command-only `r1_run_operator`.
  Registration, semantic deduplication, attempt replay, ordered preparation, reconciliation and scoped
  reads use fixed functions. Native commands validate source scope, CAS, history and predecessor proof,
  then commit metadata/audit/outbox together. Process roles cannot write control tables directly.
- `ScopedPostgresRunStore` checks current source, protected time and durability on the physical control
  connection. It releases preparation only after synchronous COMMIT acknowledgement. Each preparation
  has a one-use private secret; only its hash is stored. Readonly history, normal model serialization
  and repr cannot recover the secret. Lost preparation acknowledgement leaves UNKNOWN.
- `011_prepared_target.sql` removes unprepared apply. New effects require the exact independently
  committed checkpoint/audit/outbox, original attempt/apply revision/executor OID and secret. The
  protected adapter establishes the acknowledged durability boundary; the database checks committed
  provenance and secret possession. This does not claim the server observes client acknowledgement.
- The protected helper writes a finalization witness in the effect transaction after its current
  authority/clock guard. A deferred constraint refuses commit without the witness. Coordination cannot
  invoke the attestor, forge its row or declare completion with a boolean. Native reconciliation verifies
  the v3 ledger/witness itself. Lost target replies can resolve to verified completion when that evidence
  survives; missing or legacy authorization evidence is not retroactively manufactured.
- The witness authenticates the designated helper role and exact effect. NTS-frame authentication and
  deadline enforcement remain responsibilities of the frozen protected helper; arbitrary SQL callers
  supplying timestamps are not an authenticated clock source.
- `advance_target_epoch` supplies audited source-administrator CAS fencing with no reset/wrap. Recovery
  requires exclusion and a newer fence before confirming no effect, then a new explicit attempt.
  Multi-step execution requires native predecessor evidence, not merely a control completion flag.
- `build_scoped_operator_dispatcher` assembles separate coordination/target identities on one database
  and port. This is a co-located profile, not cross-database atomicity. Its API dispatches a frozen step;
  broader runner/host/session-lifetime assembly retains its plan-stage obligations. The older owner-backed
  adapter is a reference/bootstrap test seam, not the runtime writer. Migration 010 disables legacy apply
  while 011 is installed.
- The restricted SQL C0 codec supports ASCII field names, safe integral JSON numbers, canonical U64
  strings and bounded depth/size. Generated plans are checked against independent Python RFC8785; the
  SQL helper is not a general-purpose replacement JSON canonicalizer.

Verification: **522 platform tests passed / 90%** statements, **98 ops tests passed**, Ruff and
`git diff --check` pass. Actual non-owner tests cover two coordinators, secret secrecy/replay, forged
observations, absent finalization, lost replies, source revoke, clock/audit rollback, fence CAS and
multi-step ordering. Release-profile codec/dispatcher properties pass with seed **20260927** and a
2,000-example limit. One existing Starlette/httpx warning remains.

Real execution corrected PL/pgSQL name ambiguity, a missing private codec grant and a misplaced test
cleanup block. Global WAL insertion/flush comparison was unsuitable inside the write protocol: it can
include the observer's own row locks and unrelated hint WAL. The scoped profile uses synchronous
control/target commits and protected helper provenance, not a moving global pointer as a historical
commit receipt.

Readonly host preflight, without a supplied release/evidence bundle, reported ready=false, zero proven
capabilities and five malformed receipt reasons. FileVault, the mounted drive and the 10 GiB reserve
floor passed. Peak=0 was diagnostic, not an activation budget; no provider absence is inferred.

Step 6/G1 remain unchecked for physical owner-reviewed installation, real purpose Keychains/NTS/mTLS and
host/release-bound receipts. Normal scoped runtime and recovery now use non-superuser logins; owners only
provision test fixtures. Synthetic protected clock frames are not physical acceptance.

Extension status for this checkpoint: SECURITY-03/05/06/08/11/13/14/15 compliant for tested commands and
provenance; deployment-wide SECURITY-01/07/12 still needs physical acceptance; SECURITY-02/04/09/10 N/A
to these source changes. RESILIENCY-10/13/14 is supported by bounded calls and actual recovery/fault tests;
other assignments remain in approved deployment/operations stages. PBT-01~10 reuse contract/state models
and add independent seeded codec parity. Private secret serialization is intentionally lossy and tested.

## Clock installer verification and executable operator handoff (2026-09-28 local)

- `ops/platform-integrity/provision_clock.py` now verifies `runtimePatch` against independent reviewed
  constants and the exact `tarfile.py` postimage. Null/incomplete/altered metadata, a rehashed unpatched
  module and cached bytecode are refused. The original verifier accepted patch claims without inspecting
  them; three failing regressions reproduced that gap before correction.
- `backport --manifest-sha256 ...` verifies the existing sealed candidate before and after the upstream
  regression. It never applies the patch or repairs a failed candidate. Its proof binds the release,
  manifest, vendor commit and module digests, and retains `accepted=false`.
- Reproduced a CA staging-swap race: a root-owned system CA was checked, but the separate short-path
  installation then reread mutable staging bytes. Installation now uses the exact checked system-CA
  snapshot. The test substitutes filesystem/launch operations; it does not exercise a root installation.
- Main ops: **137 passed**, Ruff clean. **39 clock tests** include two Hypothesis properties with
  **2,000 examples each**, seed **20260928**: metadata round-trip/tampering and a base/fixed/foreign state
  model proving read-only verification, repeat-apply idempotence and preservation of foreign bytes.
- Actual macOS system-Python plan-only install and frozen Python vendor regression pass. Current manifest:
  `509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752`; installer:
  `efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67`; **2248 files / 97,622,694 bytes**.
  Raw final-payload capture `r1clock-20260927/scan-handoff` reports 51 components, 8 findings, 1 High,
  0 ignored and `BLOCKED`. The version-based match remains visible with separate vendor-backport evidence;
  full role/freshness coverage and remediation acceptance are still pending.
- [Operator handoff §12](operator-handoff.md#12-test-realm-clock-bundle--current-operator-handoff-2026-09-28-local)
  now includes exact protected-copy, checksum, install, probe and rollback commands. All three privileged
  commands carry the manifest digest. The 400 earlier executable mappings were observations of chronyd,
  not the installed Python process; the handoff corrects that distinction and the former 2251-file typo.
- Local sudo still requires operator authentication. Root install/probe, signed physical capability
  receipts and Step 6/10/G1 acceptance remain open. This checkpoint does not advance the workflow stage.

Extension assessment for this change: SECURITY-03/05/06/08/09/11/13/15 compliant for the tested CLI
boundaries; SECURITY-10 artifact verification is implemented but release-wide supply-chain acceptance
remains incomplete. SECURITY-01/02/04/07/12/14 are N/A to this installer-verification delta (no changed
storage encryption, intermediary, HTML, network policy, credential mechanism or alerting); existing
physical obligations remain. RESILIENCY-03/04/10/13/14 have explicit failure/rollback guidance and tests;
01/02/05~09/11/12/15 are N/A to this delta, with the approved single-Mac exceptions retained. PBT-02~08/10
are covered by the generated round-trip/invariant/state/oracle checks and concrete regressions;
PBT-01/09 retain the approved design/framework rather than introducing a new selection.

## Clock launch failure — contained recovery (2026-09-28)

- **Failure**: operator installation registered both jobs, but the native clock probe returned
  `native_runtime_unavailable`. Readonly launchctl output shows observer exit 2 and repeated sampler exit 2;
  the frame is UNAVAILABLE.
- **Root cause**: `deployment/launchd.py` published root-owned `deployment.json` with mode 0400 although
  launchd starts the verifier under the service UID. The frozen interpreter reproduces EACCES. The prior
  unprivileged fixture substituted the artifact owner with the reader UID and missed this boundary.
- **Code correction**: `MANIFEST_MODE=0o444` for the non-secret path/digest/role manifest, with exact mode
  checked by `is_published()`. Root ownership, digest checks and group/other write denial remain enforced.
  An incorrect mode triggers the existing bootout/republish/bootstrap repair path. Tests now model root
  UID/GID separately from the service reader and verify idempotence after repair.
- **Verification**: four new regressions failed before the fix and passed afterward; launcher suite
  **39 passed**. Full platform **528 passed / 90.33%**, ops **137 passed**, Ruff and wheel build pass.
  Existing Starlette/httpx warning remains. Test launchctl operations are simulated; these are not native
  installation acceptance results.
- **Recovery**: handoff §13 checks the original provisioner, deployed manifest and bundle digests, changes
  only the deployment manifest mode, starts the failed observer and invokes the original guarded probe.
  Original candidate `509b5074…` and protected installer `efb6145b…` are retained. The new wheel is a
  separate source-build check, not a replacement of the installed immutable release.
- **Result**: code fix verified; privileged recovery and live clock acceptance await the operator.
  One deterministic access-mode diagnosis was isolated rather than repeating NTS retries or rebuilding
  the clock closure. Future fixtures must distinguish artifact-owner access from service-reader access.

Extension delta: SECURITY-06/13/15 compliant for root-owned read-only metadata and failure handling;
RESILIENCY-04/06/13/14 supported by same-digest repair, explicit health limits and regression/recovery
instructions. No new credential, network, storage-encryption or data-transformation surface; the prior
per-rule applicability and supply-chain/physical acceptance obligations remain. Existing PBT runs retain
seed 20260928; the four new examples reproduce the concrete filesystem-permission defect.

## Remaining launch failure — bounded native-context diagnostic (2026-09-28)

- The operator completed the mode correction. The manifest is now 0444, its digest still matches, and
  the installed interpreter passes manifest/identity/all-artifact validation under the inspector UID.
  The observer still exits 2 after its second launch; the sampler also exits 2 and the frame is UNAVAILABLE.
- The first permission defect was real but not the complete cause. The next unknown is the actual
  launchd process context or later launch path. Inspector UID 501's groups cannot establish UID 608's
  credentials, and the production CLI's generic error hides the failing check.
- Added `ops/platform-integrity/diagnose_clock_launch.sh`: fixed frozen interpreter, exact test entry and
  manifest digest, root refusal, native group observation, 15-second deadline, bounded exception text,
  and an exec interception that raises before executing the target. It restores the intercepted function
  and signal handler on exit. Output is explicitly unaccepted diagnostic evidence.
- Four tests in `ops/tests/test_clock_launch_diagnostic.py` verify interception, error preservation,
  privilege refusal and result bounds. Full ops **141 passed**, Ruff/shell syntax pass. The actual
  unprivileged smoke reports the expected UID-501 role refusal; no native service-context diagnosis is
  claimed from that run.
- Handoff §14 stages a root-owned digest-checked copy and uses a one-invocation `launchctl debug` override
  on the existing observer label, preserving its identity/workdir/limits. Output goes to the operator's
  Terminal; the target is not executed. The native report is required before another permission/privilege
  correction. This avoids another blind 90-second collector retry.

Extension delta: SECURITY-06/13/15 covers protected staging, retained identity/guard checks and bounded
failure output; RESILIENCY-10/14 covers the finite diagnostic and concrete non-execution tests. There is
no new business-state transformation or acceptance mechanism; existing property and physical gates remain.

## Native supplementary-group failure — verified bootstrap repair (2026-09-28)

Actual service-context JSON identifies the cause: UID/GID 608 still has kernel groups `[608,12,61,100]`.
The strict guard correctly refuses target execution. `InitGroups=false` was not sufficient on this host.

- `launchd_plist()` now configures root:wheel for the short verifier bootstrap with `-I -B`. The
  pre-existing `execute()` path verifies all frozen bytes, clears supplementary groups, sets GID then UID,
  verifies real/effective IDs and native groups, and executes the target as its declared role. `-B`
  prevents root bytecode writes into the frozen closure. Guard policy is not relaxed.
- Six root-path cases cover success ordering, each credential syscall failure, residual groups and
  rejection of invalid artifacts before credential changes. The prior renderer assertion fails on the
  old role-start policy and passes with the corrected policy.
- `ops/platform-integrity/repair_clock_groups.py` uses the exact original provisioner snapshot to verify
  the original bundle and every installed artifact/CA. It recognizes only the two exact original or
  repaired plists and changes bootstrap identity plus `-B`. Default invocation is PLAN_ONLY. Privileged
  application requires protected root-owned script copies, stops both jobs before publication, invalidates
  the old sample, replaces plists atomically and starts both. Failed/interrupted or unacknowledged starts
  trigger cleanup of both scoped labels. Failure to confirm cleanup is reported as BLOCKED.
- Actual System-Python preflight passes. Repair postimages and the current renderer agree:
  observer `e9eb9bc3…`, sample `d751260f…`. Repair script SHA256 is
  `9fc69cb3b2ec72bcd30b5eea4770b58de8e6455617ce750a9d4a6dabec3e3812`.
- Main platform **534 passed / 90.42%**, ops **156 passed**, Ruff success. The 15 repair cases include
  mutation barriers, interruption/lost-reply cleanup, exact output scope and a 2,000-example retargeting
  property (seed `20260928`). Privileged launch effects in tests are simulated.
- Handoff §15 requires cancelling the still-attached debug Terminal before repair so its queued start
  cannot race. It retains the original bundle/provisioner pins and provides the existing uninstall path.
  Actual repair/probe and signed acceptance still await the operator.

Extension delta: SECURITY-06/13/15 uses the approved root-owned bootstrap followed by explicit verified
least-privilege execution; RESILIENCY-04/10/13/14 covers bounded commands, stop-before-publish, failed-start
cleanup and rollback. PBT-03/05/07/08/10 adds exact-scope retargeting checks alongside syscall/failure
examples. Existing release-wide supply-chain and physical acceptance obligations remain open.

### Runtime follow-up: repaired publisher, reader acceptance pending

The operator applied the repair. Readonly checks confirm both repaired plist hashes, chronyd PID 87325
at real/effective UID/GID 608 and publisher exit 0. The initial reader call failed inside ProtectedClock
after its identity/group assertion passed. The failed frame is unavailable for diagnosis; startup
uncertainty/publication race remains a hypothesis. Current authenticated frames and five installed-
ProtectedClock reads across 20 seconds pass under inspector UID 501, with about ±0.25–0.30 s uncertainty.
Handoff §16 requests one probe-only retry for actual UID-600 read/isolation evidence. No runtime code or
validation policy changes were made in this follow-up.

### Native probe success and receipt prerequisites

Operator retry returned `NATIVE_CLOCK_PROBED`: collector OBSERVED, isolated reader CLOCK_READ_VERIFIED,
frame writes denied, chrony command socket access denied. The verified window is 235726 us wide
(±117863 us). `capabilityReceiptIssued=false` is retained. Readonly process/plist checks still match the
repaired installation; live collection and reader isolation are now proven in the test realm.

Added reference-only `ops/platform-integrity/clock-receipt.test.json`. The actual issuer --probe-only
reports nts_clock verified, with four omitted capabilities not_configured (overall exit 2). This uses no
key and does not issue or approve a receipt. Next work is the protected Keychain signer/frozen issuer,
authenticated-clock validity and independently anchored release trust; the current bootstrap PEM/
wall-clock/evidence-named-key CLI is not the completed production path. Expiry/reboot and signed
acceptance remain open. No runtime changes or new unit tests were needed for this evidence/config update.

## Step 7/12/14/15 코드 구현 (2026-09-29)

**상태: 네 step의 코드 의무 완료. acceptance 박스는 전부 미체크 — 물리/operator 증명이 남는다.**

### Step 7 — generation/journal 경계

- `platform_integrity/src/docsuri_platform_integrity/domain/generation.py` (신설): durability
  receipt, 검증된 metadata import, collection 판정 같은 순수 규칙. clock·filesystem·network 없음.
- `adapters/filesystem.py`: `GenerationStore` 위에 `GenerationBoundary`(receipt·seal·head
  교체), `PinRegistry`(reader/backup pin), pin 보호 collection, `_erase_tree` 추가.
- 테스트(`tests/test_generation_boundary.py`, 28개): receipt/seal 중단, torn tail, stale head,
  늦은 writable descriptor, pin 보유 중 GC 거부, import 검증, symlink 탈출, 복구.

### Step 12 — R1R + scoped helper

- `domain/actions.py` (신설): 닫힌 `ACTIONS`, `ROLES`, `ROLE_ACTIONS`, `REQUEST_ACTION`,
  `authorize`, `resolve_request`. 임의 shell/path/SQL/sign 요청은 닫힌 어휘 밖이라 거부된다.
- `cli/__main__.py`: `check-schemas`·`verify-audit`·`capabilities`·`plan`·`apply`·`reconcile`·
  `backup` 명시 action, 선택적 `--role`, 기계가독 non-success. **기본 apply 없음** —
  `test_cli_never_applies`가 유지한다.
- `application/supervisor.py`는 one-shot 의무를 이미 전부 만족해 **변경 없음**.

### Step 14 — observability/retention/backup evidence (신설)

- `domain/retention.py`: `Correlation`(effect는 반드시 run을 명시), 단조 `advance_relay_cursor`
  (replay·regression 거부), `RetentionPolicy`(14일 ordinary / 90일 critical, 구성 시점에
  검증), `gc_decision`. **managed 집합 밖 레코드는 승인 여부와 무관하게 삭제 대상이 아니다** —
  retention을 켜도 기존 operator 로그·백업이 지워지지 않는다. critical은 승인 없이는 자동 GC 불가.
- `domain/backup.py`: `BackupEvidence`, `evaluate_backup`, `cut_is_exact`. **모든 신호의 기본값이
  미증명**이라 cut·generation만 채운 객체도 6개 reason을 모두 달고 `INCOMPLETE`가 된다.
  부분 채증 evidence가 백업 성공으로 읽힐 경로가 없다.

### Step 15 — CI

`.github/workflows/ci.yml`에 nightly + `workflow_dispatch` 트리거와 4개 lane 추가:
`rem1-closure-audit`(전체 closure, PR-diff 아님), `pbt-full`(release 2,000/200×100),
`rem1-isolated`(185 skip을 실제 실행으로 + skip 0건 가드), `macos-filesystem`(APFS 의미).
`ops/platform-integrity/validate_supply_chain.py` 신설(stdlib 전용, `ops/tests/
test_supply_chain_targets.py` 13개 테스트로 고정).

### 실행 결과

platform **485 passed** / 185 skipped (기존 격리 DB skip), ops **192 passed** (+13), 양쪽 Ruff clean.

### 남음

Step 7 격리 APFS root 및 native durability 증명 · Step 12 native role 바인딩과 실 lost-receipt
rehearsal, 물리 mTLS · Step 14 `ops/server/`·`ops/local/` seam 배선, 암호화 이동식 드라이브
archive, 새 target incarnation 격리 restore · Step 15 closure 감사 실 실행(이 sandbox에서
`uvx pip-audit`가 `ensurepip` SIGABRT로 중단되어 신규 project는 blocking이 아닌 report로 둠).

## Step 3/4/5 하네스 구현 (2026-09-29)

**상태: 코드 완료. 물리 인수(암호화 드라이브 backup/restore, 실제 mTLS 부하, CVE 처분)는 operator 몫.**

### Step 3 — backup/restore evidence

- `ops/src/docsuri_ops/backup_evidence.py` (신설): `BackupCut`(cut 시각 + writer epoch),
  `collect_backup_evidence`(포트 3개를 관측해 evidence 구성), `collect_expired_backups`(실제 삭제
  경로), `ManagedPath`(`.docsuri-rem1-managed` marker), `LocalHostLock`(연결 전 기본값 = 둘 다
  미증명). 판정은 계속 `platform_integrity.domain.backup`의 순수 규칙이 소유한다 — evidence를 모은
  쪽이 결정을 하면 누락 조건이 흡수된다.
- `ops/src/docsuri_ops/adapters/backup.py` (신설): `LocalDriveArchive`(마운트/쓰기/암호화
  보고 확인, **기존 archive는 조용히 덮어쓰지 않고 거부**), `LocalRestoreTarget`(새 incarnation만,
  기존 대상 거부), `LocalKeyLock`, `ProcessTreeSampler`(`ps` 기반, macOS 대응).
- `ops/platform-integrity/backup_evidence.py` (신설): operator CLI. `gc`는 기본 dry-run이고
  **marker가 있는 항목만** 지운다. 실측: 마운트 안 된 드라이브 → `INCOMPLETE` 5개 사유, exit 2.

### Step 4 — load/RSS/의존성 관측

- 기존 `load_acceptance.py`는 5 req/s × 600s mTLS를 이미 돌리면서
  `nativeProviderAndRssAcceptanceRequired: true`만 세우고 **아무것도 관측하지 않았다.** 필요한
  증거가 존재하지 않았던 상태다.
- `ops/src/docsuri_ops/load_observation.py` (신설): 512 MiB 상한, 64 MiB immutable LRU,
  `RssObservation`(피크 1회 초과도 실패), `verify_no_side_effects`(read/check/health가 run/ledger를
  못 건드리는지 전후 비교), `LoadVerdict`. **지연만 통과해선 승인 불가** — 자원/부작용 관측이
  없으면 INCOMPLETE.
- `load_acceptance.py`에 `--listener-pid`, `--rss-budget-mib`, `--lru-budget-mib`,
  `--dependency-state[-before]` 추가. 실행 중 listener 프로세스 트리 RSS를 샘플링한다.

### Step 5 — finding disposition / G1

- `ops/src/docsuri_ops/finding_disposition.py` (신설): `Finding`(발생 횟수 보존),
  `Acceptance`(정당화 + 승인자 + timezone-aware 만료 **없이는 거부**), `Disposition`,
  `evaluate_closure`. **accepted_risk는 severity 합계를 줄이지 않는다** — 보고서에서 나란히
  나올 뿐이다. disposition이 findings 수와 맞지 않으면 `disposition_count_mismatch`로 BLOCKED,
  맞지 않는 항목은 `unaccounted`로 이름이 노출된다. 만료된 승인은 다시 BLOCKED.

### 작성 중 발견·수정한 결함 4건 (본인이 쓴 코드 3건 포함)

1. `iter_backup_candidates`가 **디렉터리만** 열거했는데 `LocalDriveArchive`는 `*.archive`
   **파일**을 쓴다 — 우리 시스템 자신의 archive가 retention에 보이지 않았고, operator 파일은
   제외된 게 아니라 보이지 않았다. 열거는 완전하게 하고 제외는 marker 판정에서 한다
   (안 보이는 항목은 제외할 수 없다).
2. `test_an_unresolved_writer_blocks_collection`이 이름과 반대로 asserting 했고 writer 가드는
   collector에 아예 배선돼 있지 않았다. `writer_resolved`를 배선하고 테스트를 실제 동작에 맞췄다.
3. `evaluate_closure`의 `report.blockers().append(...)`는 임시 리스트를 변조해 mismatch blocker가
   **조용히 사라졌다.** 내 테스트가 더 깊은 버전을 잡았다: `by_severity()`가 disposition 기준으로
   합산해 미계상 finding이 합계를 줄이고 사라졌다 — 이 모듈이 막으려던 바로 그 실패. 이제
   severity 합계는 findings 기준이고 `dispositionedTotals`와 `unaccounted`를 함께 낸다.
4. 노화 테스트의 합성 먼 미래 microsecond 타임스탬프가 APFS에 clamp됐고, `os.utime`에 float
   초를 넘기면 그 크기에서 정밀도가 손실된다 → `ns=` 사용. `observe_resources`는 `stop`이
   keyword-only인데 `main()`이 위치 인자로 넘겨 새 테스트가 잡아냈다.

### 실행 결과

ops **275 passed** (192 → 275), platform **485 passed** / 185 skipped, 양쪽 Ruff clean.

### 실제 호스트 점검에서 발견한 어댑터 결함 (2026-09-29)

operator 지침을 쓰기 전에 실제 호스트를 확인했고, 그 과정에서 내가 쓴 Step 3 어댑터의 결함이
드러났다. `LocalDriveArchive.encrypted()`가 `cryptutil status`를 쓰는데 **macOS에 `cryptutil`은
존재하지 않는다** (`command not found`). `check=False`로 돌리고 stdout에 `encrypted`를 찾았으므로
빈 출력 → `False`, 즉 **실제로 FileVault 암호화되어 있는 드라이브를 "암호화 안 됨"으로 보고**했다.
암호화를 증명하려는 순간 operator에게 거짓 음성을 주게 되는 방향의 실패였다. `diskutil info -plist`의
볼륨 레벨 `FileVault` 키(`plistlib` 파싱)로 교체했고, rc!=0·파싱 불가·probe 예외는 모두 fail closed.
실측 `encrypted() -> True`.

**진짜 블로커는 다른 것이었고, 이제 어댑터가 그걸 정확히 말한다:**
`/Volumes/DocSuri_Backup`은 `root:wheel` 755라 operator 계정이 쓸 수 없다
(`available() -> not writable`). 해제 대상은 암호화가 아니라 쓰기 권한이고, 그 권한은 대화형
operator 계정이 아니라 `_docsuri_r1t_backup` role에 있어야 한다.

기억할 원칙: **플랫폼에 없는 capability probe와 실제로 없는 capability는 구분되지 않는다.**

### volume 소유권과 retention marker (2026-09-29, 실제 호스트 출력 기반)

- `sudo chown -R` 의 `.Spotlight-V100: Operation not permitted`은 **정상**이다. macOS가 SIP/TCC로
  보호하므로 어떤 chown도 건드리지 못한다. mountpoint 자체는 이미
  `_docsuri_r1t_backup` 700으로 적용되어 **1단계는 완료**다. `-R` 재시도 금지, SIP 해제 금지.
- 700/backup role 상태에서는 대화형 operator 계정이 써선 안 된다 — 쓰기 불가 자체가 올바른 상태다.
  `available()` 검증은 **role로 실행**한다: `sudo -u _docsuri_r1t_backup`(숫자 607도 가능.
  `#607`은 `launchctl asuser` 문법이라 `sudo -u`에서 거부된다). role은 이 checkout의 venv·코드에
  접근 가능하다(홈 ACL은 `delete`만 deny, venv/site-packages/CLI 모두 755).
- **결함 2건 수정:** ① `encrypted()`의 `cryptutil`은 macOS에 없어 암호화 드라이브를 "미암호화"로
  오보고 → `diskutil info -plist`의 `FileVault` 사용, fail closed. ② `ManagedPath.is_managed()`가
  `path/MARKER`만 검사 → **일반 파일 내부에는 marker가 존재할 수 없어 시스템이 쓴 archive 전부가
  unmanaged으로 분류**되었다. marker는 이제 '이 subtree가 우리 것'을 뜻하고 상위 디렉터리를 통해
  상속된다. GC는 우리 archive를 보존하고 marker 밖 operator 데이터는 건드리지 않는다.
- 검증: ops **287 passed** (275 → 287), platform **485** / 185 skipped, 양쪽 Ruff clean.

### provision_receipts의 chrony.conf 경로 (2026-09-29, 실제 배포 기준 확정)

호스트 배포는 `releases/r1t-clock-20260927/chrony.conf`(config/ 없음)를 쓰고Launching manifest도
그대로 가리킨다. 그런데 `installed_clock()`은 `releases/<release>/config/chrony.conf`를 하드코딩해서
**건강한 배포를 거부**했다. r2 검토본에는 `provision_receipts.py` 자체가 없으므로 이 파일은 검토
배포보다 새로워 그 가정이 실제 호스트에서 한 번도 실행된 적이 없다.

**수정:** `clock_config_argument()`가 레이아웃을 추정하지 말고 **frozen manifest의 `-f` 인자에서**
pin할 config를导출한다. 이전보다 강하다: chronyd entry 정확히 1개, `-f` 정확히 1회, 대상은 이름이
chrony.conf여야 하고, `artifact_path`의 비정규 경로/`..`/심링크/타 릴리즈/미pin 검사 유지. 즉
**pin됐지만 읽히지 않는 config도, 읽히지만 pin되지 않은 config도 통과할 수 없다.**

주의: `provision_clock.py`를 재실행하는 것은 금지. config/ 하위 디렉터리 맞추려고 하면 release
디렉터리·toolchain·launchd plist를 덮어쓰고 clock bundle을 재생성해 **검증된 구동 배포를 파괴**한다
(C-15: rebuild bundle `290aa5e0…` 재설치 금지). 배포는 정합하며 그대로 둔다.

검증: 실제 배포 기준 derived target = flat `chrony.conf`, basename ok, manifest pin ok, on-disk digest
일치. 테스트 6개 추가(ops 293), platform 485/185 skipped, Ruff clean.

## sign-role launchd job (`ops/platform-integrity/receipt_signer_job.py`)

`nts_clock` receipt 발급이 `sign_and_publish`에서 막히던 원인: `require_signer_role()`은
**네이티브** 그룹 집합(`kernel_groups()` → `getgroups(2)`)이 sign gid 외에 아무것도 없어야
한다. macOS 계정은 `everyone`·`localaccounts`·`admin` 하위 그룹을 암묵적으로 가지며,
`sudo -u`는 `initgroups(3)`로 이를 커널 자격에 주입한다. 즉 어느 셸에서도 성립 불가이며,
`admin` 그룹 추가(`711`은 이미 group traverse 허용)로도 해결되지 않는다.

**설계 근거 2가지**
- `deployment/launchd.py:178`의 `launchd_plist()`가 동일 문제를 이미 풀고 있다:
  `UserName: root` + `InitGroups: False`, 그리고 `:231`의 root bootstrap이
  `setgroups([])` → `setgid`/`setuid` → `kernel_groups()` 재검증 후 exec. 새 발상이 아니라
  저장소 내 선례를 재사용한다.
- keychain ACL은 `SecTrustedApplicationCreateFromPath(executable.resolve())`
  (`adapters/keychain_provisioning.py:111`)로 **경로 기준**이다. 해당 바이너리로 실행된
  프로세스는 모두 권한이 있으므로, 번들된 오래된 라이브러리는 ACL을 약화시키지 않는다.
  키 재-provisioning이나 키 파일 export가 불필요하다.

**동작**
- `install`(root 전용): 현재 라이브러리를 root 소유 0555 digest 기록 트리로 고정, 인터프리터
  digest와 **가리고 있는 번들 사본의 digest**를 함께 기록(매니페스트가 site-packages 항목을
  고정하지 않아 그 사본은 검증되지 않았음), 고정 argv의 1-shot plist 작성.
- `run`(launchd 호출): 그룹 제거 후 604/604 획득 → 고정 트리 재검증 → ACL 바인딩
  인터프리터를 `PYTHONPATH`로 명시하여 exec. `-I`는 의도적으로 제외(`-E`를 함의해
  `PYTHONPATH`를 조용히 버리고 오래된 import로 되돌아간다). argv에 셸 없음.

테스트 20개. ops 316 passed, platform 485/185 skipped, Ruff clean.
미해결: purpose keychain이 locked 상태면 `KeyUnavailable`. `KeychainReader`는
`SecKeychainSetUserInteractionAllowed(False)`라 비대화형이라, 잠금 해제는 운영자가
1회 수행하는 별도 단계가 필요(여기서 자동화하지 않음).
