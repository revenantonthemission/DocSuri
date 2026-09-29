# REM-1 operator handoff — 2026-09-26

**상태: 준비 metadata와 전체 9-role synthetic 파일·그룹 격리 인수 완료. 실제 서비스 배선 및 G1은 미완료.**

기존 선택은 `R1OP1=A`, `R1OP2=A`다. 로컬 관리자 실행과 보유 SSD01의 encrypted APFS volume 준비를 operator가 수행한다. 암호·recovery key·private key는 채팅/문서에 기록하지 않는다.

## 1. 준비·검증 artifact

- 소스: `ops/platform-integrity/provision_test_realm.py`.
- 초기 준비에 사용한 SHA256: `94d73055dc46ea97db04275e3c99a81a054f1efdc3ba9989f9ed826fe511bbb5` (operator 실행 완료).
- 첫 role 검증판 SHA256: `90aa58859bdfcd922f9aa2fe9a8a49a93a9e87b07be0a769b125585976ebac7f` (9개 timeout 관측).
- **현재 진단판 SHA256:** `2e310b60c37e0398f18c9c4351398d49cf4857d5c46c2addc744126be00e4e23`.
- 대상은 `/Library/Application Support/DocSuri/rem-1-test`와 `_docsuri_r1t_` 접두사의 9개 non-login 역할이다.
- 기본 실행은 `PLAN_ONLY`다. `--apply`는 Darwin의 로컬 root 실행을 요구하고 UID/GID 및 역할별 디렉터리를 준비한다.
- 기존 계정의 UID/GID 중복, shell/home/hidden/primary group 불일치와 supplementary privilege는 거부한다. 부분 실패 시 자동 계정 삭제나 UID 재사용을 하지 않는다.
- 실제 준비 결과는 `preparation.json`의 `PREPARED_NOT_ACCEPTED`다. 이 파일은 권한·키·clock·내구성 증명의 대체물이 아니다.
- 현재 검증판은 `--check`(readonly metadata 관측)와 `--probe`(operator-only synthetic 파일 격리 시험)를 추가한다. macOS의 `dsAttrTypeNative:IsHidden`을 해석하고 상충 namespace 값은 거부한다.

## 2. 초기 준비 실행 결과 — 완료

2026-09-26 operator가 원 준비 artifact의 소스/보호된 복사본 SHA256 일치를 확인하고 `--apply`를 실행했다. 결과는 `PREPARED_NOT_ACCEPTED`이며 readonly OS 조회로 다음을 대조했다.

| Role | UID/GID | Directory mode |
|---|---|---|
| reader | 600 | 0700 |
| runner | 601 | 0700 |
| tool | 602 | 0700 |
| bundle | 603 | 0700 |
| sign | 604 | 0700 |
| audit | 605 | 0700 |
| journal | 606 | 0700 |
| backup | 607 | 0700 |
| clock | 608 | 0700 |

계정 이름은 `_docsuri_r1t_<role>`, shell은 `/usr/bin/false`, home은 `/var/empty`, hidden=1이다. realm root는 root 소유 0711, 준비 receipt는 root 소유 0600이다. agent 사용자의 realm directory listing은 EACCES로 거부됐다.

macOS directory membership에는 역할 GID 외 `everyone(12)`, `localaccounts(61)`, `_lpoperator(100)`이 관측된다. **계정 metadata와 실제 실행 프로세스의 group 격리는 별도 검증**이다. `--check`는 이를 숨기지 않고 `METADATA_VERIFIED`, `ready=false`, `processGroupIsolationRequired=true`로 출력한다. r2 실제 worker 9개에서는 §4와 같이 각 primary GID만 관측되고 다른 group 파일 접근이 거부됐다. 이 실행 정책을 실제 서비스 launcher에도 구현·검증해야 한다.

## 3. SSD01 및 FileVault 준비 결과

2026-09-26 operator 입력과 readonly 관측:

- alias `DocSuri_Backup`, 확인한 mount path `/Volumes/DocSuri_Backup`.
- Volume UUID `BB384D60-46AF-4A06-B6F7-95710B3B7A3C`; USB SSD01과 같은 APFS container의 별도 **암호화 volume**이다. mounted/unlocked/writable 상태를 확인했다.
- 공유 container 여유 `1,537,204,109,312` bytes(약 1.54 TB). 백업에 독점 예약된 용량은 아니므로 capture 직전 실제 peak/여유를 다시 검증한다.
- [R1OP3=A](../../plans/rem-1-platform-integrity-operator-questions.md) 확정(2026-09-26): **매일 03:00 Asia/Seoul(UTC+9)에 백업 시작**, 볼륨 **상시 연결**. scheduler 구현/설치 시 이 시간대를 명시적으로 적용한다. 현재는 operator 일정 확정 단계이며 자동 실행 job은 아직 활성화되지 않았다.

- **소유권 적용 완료:** operator가 `diskutil enableOwnership`을 실행했고 같은 UUID에서 `GlobalPermissionsEnabled=true`/Owners Enabled를 재확인했다.

그 뒤 backup 역할의 실제 권한 분리와 별도 root 디렉터리/쓰기·읽기·restore 인수를 검증한다. volume 암호화는 host 내부 디스크의 FileVault를 대신하지 않는다. host는 2026-09-26에도 Off로 관측됐다. 승인된 P0 절차에 따라 verified encrypted backup/restore와 console-unlock 준비를 확인한 뒤 FileVault를 준비한다. cold-boot/복구 시험은 별도 maintenance window와 실제 복구 증거를 필요로 한다.

관측용 명령:

```sh
/usr/bin/fdesetup status
/usr/sbin/diskutil info "/Volumes/DocSuri_Backup"
```

## 4. 전체 9-role 파일 격리 확인 — 완료

첫 실행은 모든 역할이 5초 `TimeoutExpired`였으며 원 fixture `/Library/Application Support/DocSuri/rem-1-test/role-probe-su4773zc`를 보존했다. 원 report에 실행 단계가 없어 정확한 정지 지점은 미확정이다. `/usr/bin/python3`와 resolved framework bin도 launcher이며 실제 image는 Xcode의 `Python.app/.../Python`임을 확인했다. 현재 진단판은 `proc_pidpath`로 관측한 실행 image를 직접 사용하고 phase/cleanup/범위 정보를 남긴다. 상세 근거는 [native-probe-debug.md](native-probe-debug.md)에 있다.

### 단일 reader 재실행 — 통과

- operator의 r2 `--probe --role reader` 결과는 `PARTIAL_ROLE_FILE_ISOLATION_VERIFIED`다.
- UID/GID/groups `600/600/[600]`, ownReadWrite=true, crossReadDenied=8, crossWriteDenied=8, directoryGroupReadDenied=3.
- worker는 0.052초에 `complete`까지 도달했고 returncode=0/timedOut=false/parentReaped=true다.
- 결과 root: `/Library/Application Support/DocSuri/rem-1-test/role-probe-e_0w5ja7`.
- interpreter SHA256 `07470fa2e1aec690aa62061af6e0f65fe9bf3169a74a16384592fb1ff1cb320f`를 현재 로컬 executable과 대조했다. script hash도 §1의 현재 값과 일치한다.
- reader 경로의 timeout 해소와 파일 격리를 확인했다. 원 9개 timeout의 정확한 내부 정지 지점/단독 원인은 과거 phase가 없어 소급 확정하지 않는다.

### 전체 역할 실행 — 통과

operator가 배치한 **동일한 r2 복사본**으로 아래 전체 명령을 실행했다.

```sh
sudo /usr/bin/python3 -I "/private/var/root/docsuri-rem1-verification-20260926-r2/verify.py" --probe
```

결과: **ROLE_FILE_ISOLATION_VERIFIED**, `completeRoleCoverage=true`, `ready=false`. 결과 root는 `/Library/Application Support/DocSuri/rem-1-test/role-probe-236g0xrp`다.

| Role | UID/GID/kernel groups | Worker seconds | Result |
|---|---|---|---|
| reader | 600/600/[600] | 0.051 | VERIFIED |
| runner | 601/601/[601] | 0.045 | VERIFIED |
| tool | 602/602/[602] | 0.044 | VERIFIED |
| bundle | 603/603/[603] | 0.046 | VERIFIED |
| sign | 604/604/[604] | 0.045 | VERIFIED |
| audit | 605/605/[605] | 0.045 | VERIFIED |
| journal | 606/606/[606] | 0.047 | VERIFIED |
| backup | 607/607/[607] | 0.046 | VERIFIED |
| clock | 608/608/[608] | 0.045 | VERIFIED |

모든 역할이 ownReadWrite=true, crossReadDenied=8, crossWriteDenied=8, directoryGroupReadDenied=3이다. 합계 교차 읽기 72회·쓰기 72회·group 파일 읽기 27회가 거부됐다. 모든 worker는 complete/returncode=0/timedOut=false/parentReaped=true, stderrTruncated=false로 종료됐다. Source 및 interpreter hash는 앞서 확인한 값과 일치한다.

probe 범위:

- `/Library/Application Support/DocSuri/rem-1-test/role-probe-*`의 신규 synthetic fixture만 생성한다. 생성한 fixture와 root 전용 `probe.json`은 결과 확인을 위해 보존한다.
- 실행은 reader부터 clock까지 UID/GID 600~608의 9개 worker를 순차 검증했다. supplementary groups를 비우고 최소 환경·5초/worker deadline을 적용했으며 script/staging 및 관측된 interpreter image의 소유권·쓰기 제한과 local disk reserve를 먼저 확인했다.
- 역할별 자기 파일 read/write, 다른 8역할 파일 read/write 거부, directory group 12/61/100 소유 파일 read 거부를 검사한다. 성공 기준은 역할별 8 read + 8 write + 3 group-read 거부다.
- 현대 macOS CPython의 `os.getgroups()`는 `setgroups()` 후에도 directory membership을 반환하므로, **libSystem의 native `getgroups`**로 실제 kernel credential을 관측하고 파일 접근 결과와 함께 확인한다. 참고: [Python os.getgroups macOS note](https://docs.python.org/3/library/os.html#os.getgroups).
- `worker.stages`, `worker.lastStage`, PID/return code/elapsed time, parent reap/cleanup 결과를 기록한다. worker code의 첫 marker가 없으면 `before_worker_code`, 파일 fsync에서 멈추면 `own_fsync` 등으로 구분한다. 원 stderr는 root 전용 파일에 최대 64 KiB를 보존하고 JSON에는 allowlisted phase와 메타데이터만 넣는다.
- timeout이면 해당 child process group을 종료·reap하고 추가 역할 실행을 중지한다. scoped subprocess/pipe 보유 자손 정리의 실제 회귀를 검증했다. launchd가 관리하는 OS user agent는 별도이며 임의 종료하지 않는다.
- 전체 통과 기준은 `ROLE_FILE_ISOLATION_VERIFIED`, roles 9개 모두 VERIFIED, `completeRoleCoverage=true`다. `ready=false`는 installed launcher/Keychain/NTS/DB/backup 등 전체 native/G1 인수가 남아 있다는 뜻이다.

이로써 이번 synthetic-file scope의 전체 역할 인수를 완료했다. 다음 구현은 검증한 실행 group 정책의 실제 launcher 적용, purpose Keychain/NTS observer/DB mTLS·command role 배선이다. 그 후 실제 archive/restore와 load 인수를 수행한다. 이번 probe는 production 데이터나 Keychain/DB 권한을 시험한 결과가 아니다.

## 5. 남은 acceptance 조건

- NTS clock, purpose Keychain/CA, native peer/mTLS identity, command-only DB role, current source authority 및 durable UNKNOWN-to-dispatch/finalization 연결.
- encrypted removable-drive archive와 실제 restore, 새 incarnation, RTO/RPO 및 감사 relay/retention.
- `ops/platform-integrity/load_acceptance.py`의 `127.0.0.1:18101` mTLS normal-path 5 req/s ×600초, 별도 overload, 프로세스/자식 RSS 및 실제 dependency 관측. 실패/INCOMPLETE 응답은 정상 처리량이 아니다.
- PostgreSQL image의 **96 High + 2 Critical** findings 해소, 나머지 image/native/final-artifact SBOM 범위 검증. native 준비가 끝나도 이 blocker가 남으면 G1은 통과하지 않는다.

현재 수행한 pg_dump/pg_restore는 동일 disposable container 내 control/audit 복원 시험이다. 위 물리 backup/recovery 인수와 구분한다.

## 6. Native runtime 통합과 실제 DB mTLS 인수 — 완료 (2026-09-26)

- `launchd.py`, `host.py`, credential/TLS/NTS/read-authority adapter와 `005_reader_access.sql`을 **main에 통합**했다. launchd plist/privilege-drop 정책, Keychain handle-only 구성, 고정 non-adjusting chrony 인수는 코드 수준에서 검증됐다. 실제 `launchd install/bootout`, 실제 Keychain ACL, live NTS daemon은 이 인수에 포함되지 않는다.
- **실제 PostgreSQL mTLS 인수 통과**: loopback TLS handshake, `cert clientname`으로 매핑된 `session_user=r1_tls_probe` 로그인, read-only transaction 강제, wrong-CA 거부까지 실제 인증서 경로에서 확인했다. 검증 전용 CA/role/database이며 운영 DB role 인수로 승격하지 않는다.
- 검증 전용 container는 **`rem1-test-pg-20260924`**, image `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`, **named volume `rem1-pgdata-20260926`**(PGDATA 영속화), loopback `15439`다. operator가 자체 container를 만들 때 PGDATA를 tmpfs로 두면 `ALTER SYSTEM` 설정이 재시작마다 소실되어 mTLS test가 실패한다. teardown은 원래 `pg_hba.conf`를 되돌리고 `ALTER SYSTEM RESET` 후 재시작하므로 `ssl=off`, `postgresql.auto.conf` header-only, HBA probe 규칙 0건으로 복구된다. 단, **`r1_tls_probe` role 자체는 남는다**(fixture가 존재하지 않을 때만 생성). 검증용 disposable DB이며 운영 role과 무관하지만, 이 container를 계속 재사용할 때 알아둘 사실이다.
- 아직 하지 않은 것: purpose별 실제 Keychain 생성/ACL 부여, launchd job 실제 등록·부팅 후 생존, live chrony NTS source의 authenticated/clock bound 관측, production-equivalent DB role의 `hostssl`/`verify-full` 배선, native commit guard. 이 항목이 남아 있는 동안 `ready=false`와 Step 10 미체크가 유지된다.

## 7. Preflight evidence 형식 변경 — operator 확인 필요 (2026-09-26T13:36:10Z)

`ops/platform-integrity/preflight.py`가 capability를 실제 서명 검증으로 판정하도록 바뀌었다. **evidence 파일 형식이 바뀌었으므로** 이전 boolean JSON은 더 이상 proof가 아니다.

### 새 evidence 파일
evidence 파일과 **같은 디렉터리**에 trust key 파일을 두고 함께 가리켜야 한다. evidence는 이 파일이 속한 디렉터리 밖을 가리킬 수 없다(`../`는 거부된다).

```
evidence/
  release-key-1.json      # trust key (manifest 배포본)
  evidence.json           # 아래 내용
```

`release-key-1.json`:
```json
{"key_id":"release-key-1","public_key":"<43자 base64url>","validity":{"valid_from":"<us>","valid_until":"<us>"},"revoked":false}
```

`evidence.json`:
```json
{"release":"r1-2026.09","trustKeys":["release-key-1.json"],
 "receipts":{"nts_clock":{"payload":{...},"keyId":"release-key-1","alg":"ed25519","sig":"<base64url>"}}}
```

### 실행
```
uv run python ops/platform-integrity/preflight.py --root <repo> \
  --drive /Volumes/DocSuri_Backup --estimated-peak-bytes 0 --evidence <evidence.json>
```
exit 0이면 `ready: true`, 아니면 exit 2이고 `reasons`에 **사유가 붙는다**. boolean이나 파일 존재는 proof가 아니며(`<capability>_malformed`), 서명·신뢰키·host·release·유효기간 중 무엇이 틀렸는지가 그대로 드러난다(`host_mismatch`, `untrusted_key`, `outside_validity`, `window_too_long` …).

### 현재 상태 — 아직 acceptance가 아니다
- 코드 경로상 `ready=true`가 도달 가능함을 임시 self-signed 키로 확인했고 그 키는 즉시 폐기했다. **production acceptance receipt는 아직 존재하지 않는다.**
- receipt를 **발급하는 installer가 아직 없다**(`issue()`만 존재). 실제 native capability를 검증해 서명하는 단계가 남았다.
- 5개 capability 각각의 실측 증거(launchd 설치, Keychain ACL, live NTS clock, 실제 DB mTLS role, 복원 receipt)는 operator 실행이 아직 없다.
- image 잔여 finding(`CVE-2026-85091` zlib)과 registry digest 교체는 그대로 남았다.

## 8. Receipt 발급 절차 — operator 실행 필요 (2026-09-26T14:05:00Z)

preflight는 이제 서명된 receipt만 신뢰한다. 그 receipt를 만드는 명령이 생겼다. **이 명령은 아무것도 설치·활성화·재시작하지 않는다.** readonly probe를 돌리고, 성립한 capability에만 서명한다.

### 1. probe만 먼저 확인 (권장 — key 불필요, 아무것도 안 씀)
```
uv run --directory ops python platform-integrity/issue_receipt.py \
  --config <probe.json> --release r1-2026.09 --probe-only
```
`proven: true`가 나온 capability만 서명 가능하다. `not_configured`는 현재 reference 문서에 해당 provider가
선언되지 않았다는 뜻이며 실제 미설치의 증명은 아니다. 다른 실패 사유도 configuration/access/runtime 상태를
각각 확인해야 한다.

### 2. probe 설정 문서 (reference만; secret 금지)
```json
{
  "keychainRoles": [{"keychain": "/absolute/path.rem1-reader.keychain-db",
                     "service": "docsuri.rem1", "account": "reader"}],
  "database": {"database": "rem1", "user": "r1_reader", "port": 5432},
  "databaseTls": {"keychain": "/...keychain-db", "service": "docsuri.rem1",
                  "account": "reader", "runtimeRoot": "/Library/.../reader"},
  "clock": {"frame": "/.../clock.json", "writerUid": 0, "configDigest": "sha256:..."},
  "restoreReceipt": "/.../restore.json"
}
```
없는 섹션은 그 capability를 `not_configured`로 만든다. 상대 경로와 `..`는 거부된다.

### 3. 서명 키 준비
- Ed25519 private key(PKCS8 PEM), root 또는 본인 소유, **`0600`**, symlink 아님.
- 상태를 확인할 필요 없다. 그룹/세계 읽기 가능하거나 symlink면 `signing_key_unusable`로 거부된다.

### 4. 발급
```
uv run --directory ops python platform-integrity/issue_receipt.py \
  --config <probe.json> --release r1-2026.09 \
  --key <key.pem> --key-id release-key-1 --out <receipts dir/> \
  [--capability restore_receipt] [--days 1]
```
- **하나라도 proven이 아니면 run 전체가 거부되고 파일이 하나도 생기지 않는다.** 부분 발급은 acceptance로 오인될 수 있어 의도적으로 막았다.
- receipt는 `<capability>.receipt.json`, 0600, atomic write. `--days`는 1~7.
- ~~`native_commit_guard`는 이 명령에서 발급하지 않는다(`notIssuableHere`).~~ **2026-09-26 정정:** 이제 live operator authority에서 **발급한다**. `nativeCommitGuard` reference 문서와 강제 규칙은 아래 "Step 6 `nativeCommitGuard` reference document" 절을 본다.

### 5. preflight에 연결
`preflight.py --evidence`가 받는 형식은 7절과 동일하다. 같은 디렉터리에 trust key 파일을 두고 `receipts`에 발급받은 envelope를 넣으면 된다. 본机 UUID는 `D8420CE8-FD62-5BA1-9C1F-FE4BBA7D4D77`이었다(receipt는 이 값에 결합된다).

### 6. restore.json이 아직 없다
`restore_receipt` probe가 요구하는 문서(없으면 해당 capability는 `not_configured`/`receipt_unreadable`):
```json
{"host": "<IOPlatformUUID>", "release": "r1-2026.09",
 "source":   {"target_id":"pg","namespace":"r1","incarnation":"1"},
 "restored": {"target_id":"pg","namespace":"r1","incarnation":"2"},
 "encrypted": true, "verified": true, "completed_utc_us": "<microseconds>"}
```
`restored.incarnation`은 `source`와 **달라야 한다**(같은 incarnation으로의 복원은 증거가 아니다). extra field는 거부되고, 30일보다 오래된 복원은 `restore_stale`이다.

### ⚠ 8절의 서명 절차는 폐기되었다 (2026-09-29)

8절의 `--key <key.pem>` / `--key-id` / `--out` 절차는 **더 이상 동작하지 않는다.** 세 인자 중 하나라도 주면
probe-only가 아닌 실행은 `state=BLOCKED`, `reason=protected_signing_required`로 즉시 거부되고 파일은 하나도
생기지 않는다. 이유를 제거한 것이 아니라 **사라지도록 만든 것**이다. PEM private-key 파일 경로와
"evidence와 같은 디렉터리에 trust key 파일을 두는" 방식은 이제 존재하지 않는다:

- trust는 `preflight.py`/`issue_receipt.py`가 **root 소유 0444 policy**에서만 읽는다.
- evidence 안에 `trustKeys`가 있으면 `evidence_invalid_or_contains_trust`로 거부한다.
- 서명 키는 **purpose Keychain 안에만** 있고, 전용 서명 역할 계정 외에는 ACL이 허락하지 않는다.
- 위 절의 "3. 서명 키 준비"는 **읽으면 안 되는 폐기된 지시**다. 그대로 실행하지 말 것.

**아래 8A절이 현재 유효한 유일한 절차다.**

## 8A. 보호된 receipt 발급 절차 (2026-09-29 — root 필요 단계 1개, 나머지 비권한)

세 단계로 나뉜다. FileVault가 켜져 있어야 서명이 가능하다
(`KeychainReceiptSigner`는 호스트 암호화를 요구한다. 꺼져 있으면 `host_encryption_required`).

### 단계 0 — FileVault 확인 (root)

```bash
sudo fdesetup status | grep -q "FileVault is On" || echo "BLOCKED: FileVault must be On"
```

### 단계 1 — root-side provisioner (신규, sudo)

```bash
sudo uv run --directory ops python platform-integrity/provision_receipts.py \
  --profile test --release r1-clock-20260927 \
  --key-id receipt-key-1 --issuer "$(uv run --directory ops python -c 'import sys; print(sys.executable)')" \
  --capability nts_clock --days 1
```

- keychain 비밀번호를 `getpass`로 **두 번** 입력한다(두 번째는 확인). argv·환경·파일·로그 어디에도 남지 않는다.
- NTS artifact digest는 **사용자 입력이 아니라 설치된 root 소유 `deployment.json`에서 유도**한다.
  설치된 `config/chrony.conf` 바이트가 manifest digest와 다르면 거절한다(`installed clock configuration
  does not match its manifest`).
- NTP 관측 시각이 아니라 **배포된 인증 clock**(`clock-public/current.json`, writer uid 608)에서
  trust window를 잡는다(`trustValidFrom = 지금 − 1일`).
- 지금 묶을 수 있는 capability는 `nts_clock` 하나뿐이다. 나머지는 `not bindable to installed state`로 거절한다.
- 인자가 틀리면 비밀번호를 묻기 **전에** `state=BLOCKED`, `stage=arguments`로 거절한다.
- 실패하면 `{"state":"BLOCKED","stage":...,"reason":<예외명>,"detail":...}`만 JSON으로 나간다(비밀 노출 없음).
- 성공 시 `state=PROVISIONED`와 `keyId`, `policy`, `policySha256`, `keychain`, `output`, `signerUid`,
  `clockWriterUid`, `publicKeySha256`, `capabilities`, `clockConfigDigest`, `host`, `trustedWindow`을 출력한다.
- **private key는 stdout에도 policy에도 없다.** public key만 policy에 들어간다.
- 재실행은 기존 keychain 때문에 `FileExistsError`로 거절된다(조용한 교체 금지). 회전하려면 operator가
  명시적으로 기존 policy/keychain/output을 제거한 뒤 다시 실행한다.

생성되는 소유권 (test profile 기준, production은 `rem-1`):

| 경로 | 소유자 | mode |
| --- | --- | --- |
| `…/rem-1-test/sign/` | `_docsuri_r1t_sign` | 0700 |
| `…/rem-1-test/sign/<release>--<key_id>.keychain-db` | `_docsuri_r1t_sign` | 0600 |
| `…/rem-1-test/receipt-policy/` | root | 0755 |
| `…/rem-1-test/receipt-policy/<release>.json` | root | 0444 |
| `…/rem-1-test/receipt-public/` | root | 0755 |
| `…/rem-1-test/receipt-public/<release>/` | `_docsuri_r1t_sign` | 0755 |

### 단계 2 — 발급 (비권한, signer 계정 또는 그 권한이 있는 계정)

provisioner가 남긴 Keychain은 **locked 상태**다. 그래서 issuer가 `--keychain-password-stdin`으로 한 번만
unlock하고, 서명이 끝나면 다시 lock한다(`finally`).

```bash
printf '%s\n' "$KEYCHAIN_PASSWORD" | uv run --directory ops python platform-integrity/issue_receipt.py \
  --profile test --release r1-clock-20260927 --capability nts_clock --days 1 \
  --keychain-password-stdin
```

- 비밀번호는 **stdin 한 줄**, 12..1024 바이트. argv·환경·로그에 나타나지 않는다.
- 하나의 probe라도 proven이 아니면 전체 거부, 파일 0개.
- receipt는 `receipt-public/<release>/<capability>.receipt.json`, **0444**, temp+rename 원자적 기록.
- 발급 시각도 wall clock이 아니라 인증 clock의 관측 창으로 결정된다.

### 단계 3 — preflight (비권한)

```bash
uv run --directory ops python platform-integrity/preflight.py \
  --root <repo root> --estimated-peak-bytes 0 \
  --profile test --release r1-clock-20260927 --evidence <evidence.json>
```

- trust는 policy에서만 온다. evidence는 `{release, receipts}`만 허용한다.
- `provenCapabilities: ["nts_clock"]`이 나오고 사유가 남지 않으면 그 capability는 **검증 완료**다.
  output chain(루트가 소유한 조상 3단계)·mode·link count·digest를 publication 때마다 재검사한다.

### 검증된 범위와 남은 것

- **검증됨 (코드/테스트):** 실제 macOS Keychain을 만들어 `SecKeychainItemCreateFromContent` ACL로 묶고,
  locked 상태에서는 서명이 `purpose signing key`로 거부되고, 올바른 비밀번호로 unlock 후 실제 Ed25519
  서명 → 0444 publication → **독립 policy가 그것을 `verified`로 받아들이는** 전체 경로가 end-to-end로
  증명됐다. 같은 purpose 슬롯에 다른 키를 넣으면 거부되고, 잘못된 비밀번호로는 unlock되지 않는다.
  provisioner 레이아웃은 signer가 요구하는 모든 경로 조건을 만족한다(`platform_integrity/tests/
  test_receipt_provisioning_native.py`).
- **아직 없음:** 이 호스트에는 signer Keychain·signer key·trust key·protected policy가 하나도 없고,
  서명된 `nts_clock` receipt도 없다. `capabilityReceiptIssued=false` 유지.
- **operator만 가능:** 단계 0과 단계 1은 root 권한이 필요하고 agent는 sudo를 못 쓴다.

## 13. launchd installer/manifest (신규 — root 필요, serving checkout에서 실행 금지)

`platform_integrity/src/docsuri_platform_integrity/deployment/launchd.py`에 `install` / `uninstall`을
추가했다. 이전에는 `render`(GENERATED_NOT_INSTALLED)와 `exec`만 있었고, **plist를 launchd에 올리는 경로가
없었다.** 이제 render → review → install 3단 operator 흐름이 완성되었다.

### 왜 이렇게 만들었나 (결정 3가지)

1. **install은 아무것도 쓰기 전에 전부 검증한다.** root·realm·계정·artifact digest를 먼저 확인하고, 하나라도
   안 맞으면 plist를 0개 쓴다. 부분 설치는 "설치된 것처럼 보이는" 상태를 만들므로 금지한다.
2. **`deployment.json` 존재만으로는 '설치됨'으로 믿지 않는다.** 이전 판단을 그대로 두면 plist가 somebody에게
   지워졌는데도 `ALREADY_INSTALLED`가 나오는 결함이 있었다. 지금은 (manifest digest 일치) + (plist 바이트가
   다시 계산한 결과와 정확히 일치) + (`launchctl print system/<label>`가 실제로 잡고 있음) 3개를 모두 확인한다.
   하나라도 어긋나면 **복구(repair)** 로 들어가고, drifted plist는 **먼저 bootout한 뒤** 고쳐 쓴다 —
   고장 난 job을 고치는 동안 계속 돌게 두지 않는다.
3. **`--replace` 없이는 다른 deployment로 바꿀 수 없다.** 조용한 교체는 되돌릴 수 없으므로 명시적
   `--replace`를 요구하고, 그때도 이전 deployment를 먼저 bootout한다(되돌릴 수 있는 cutover).

### 명령

```bash
# 1) render (비권한, 리뷰용)
python -m docsuri_platform_integrity.deployment.launchd render <manifest.json> /tmp/rem1-review

# 2) install (root, maintenance window 안에서만)
sudo python -m docsuri_platform_integrity.deployment.launchd install --profile test /tmp/rem1-review/deployment.json
# 다른 manifest로 교체하려면 반드시 명시적으로:
sudo python -m docsuri_platform_integrity.deployment.launchd install --profile test <new.json> --replace

# 3) uninstall (root)
sudo python -m docsuri_platform_integrity.deployment.launchd uninstall --profile test
```

`--profile`은 `test`(`/Library/Application Support/DocSuri/rem-1-test`, 계정 `_docsuri_r1t_*`) 또는
`production`(`/Library/Application Support/DocSuri/rem-1`, 계정 `_docsuri_r1_*`)이다. 두 realm은
**경로·계정·label이 전부 다르므로 같은 system domain에서 충돌하지 않는다.**
label은 `org.docsuri.rem1.<profile>.<entry>`이고, plist 파일명도 label과 같게 쓴다.

### 안전 속성 (테스트로 고정됨)

- root가 아니면 `BLOCKED`. macOS가 아니면 `BLOCKED`. `launchctl`이 symlink이거나 쓰기 가능하면 `BLOCKED`.
- **symlink를 따라 쓰지 않는다.** plist 경로가 symlink면 거부하고 대상 파일은 그대로 둔다.
- root 소유가 아닌 파일은 덮어쓰지 않는다(`refusing to replace a foreign launchd file`).
- 임시 파일 → `fsync` → `os.replace` → 부모 디렉터리 `fsync`로 원자적 쓰기, 모드는 plist 0644 / manifest 0400.
- install이 끝난 뒤 **자기 상태를 다시 검증**하고, launchd가 job을 안 잡고 있으면 성공으로 보고하지 않는다.
- uninstall은 bootout 후에도 launchd가 잡고 있는 job이 있으면 **삭제하지 않고 실패한다.** 실행 중인 job의
  plist를 지우면 그 process는 stop할 방법이 없는 고아로 남기 때문이다. foreign plist(`Label` 불일치)도 거부.
- recursive delete·glob 삭제를 쓰지 않는다. 이 realm의 파일만 지운다.

### 검증 결과

- 신규 10건으로 `test_launch_policy.py` 24 → 34건. 전체 `platform_integrity` 350 passed / 0 skipped /
  statement 89% / Ruff 통과(`launchd.py` 88%).
- **이 호스트에서 실제로 한 것**: 비root로 `install`/`uninstall` 실행 → 둘 다 `BLOCKED` + exit 2 확인,
  `render`가 plist를 정상 생성하는지 `plutil`로 확인, `/Library/LaunchDaemons`에 DocSuri plist가 없음을 확인.
  **root로 실제 install은 하지 않았고 이 호스트는 바뀌지 않았다.** 테스트의 launchctl는 recorder여서
  어떤 job도 실제로 bootstrap되지 않는다.

### 남은 operator 작업

- **root 계정 9종 생성**(`_docsuri_r1t_*`): `dscl . -create /Groups/_docsuri_r1t_<role>`, 동일 gid의 User 생성.
  `verify_identities()`가 이들을 확인하므로 없으면 install이 거부한다.
- **toolchain/artifact 배치**: `realm/toolchains/python313/...`, `realm/releases/<release>/*.json`,
  `realm/<role>/` 작업 디렉터리(role uid 소유). digest는 manifest에 그대로 맞춰야 한다.
- **isolated `rem-1-test` rehearsal**: 이 installer를 test profile로 실제 실행해 reader daemon이
  `_docsuri_r1t_reader`로 뜨는지 확인. 그 다음 제거하고 production으로 넘어간다.
- **production install은 maintenance window 안에서만.** `rem-1` realm과 `_docsuri_r1_*` 계정은 지금 없다.

## Step 6 `nativeCommitGuard` reference document (2026-09-26)

`native_commit_guard` is now issued from a live `PostgresOperatorAuthority`. It is a normal capability
receipt: same signer, same verifier, same trust and validity rules as the other four. What is new is
where its proof comes from, so the reference document has to name a real operator authority.

```jsonc
"nativeCommitGuard": {
  "plan": "/absolute/path/operator-plan.json",   // frozen, root/current-owner, no group/world write
  "planDigest": "sha256:...",                    // must equal the digest the approval already names
  "operatorDatabase": {                          // target the authority is bound to
    "host": "...", "port": 5432, "database": "...",
    "user": "docsuri_r1t_operator",              // the actor_role is derived from this user
    "namespace": "public", "incarnation": "1"
  },
  "operatorTls": {
    "service": "docsuri-r1t", "account": "docsuri_r1t_operator",
    "keychain": "/absolute/path.rem1-operator.keychain-db"
  },
  "approval": {
    "approval_id": "...", "actor": "...", "purpose": "adopt",
    "target": {...}, "plan": "sha256:...", "artifact": "sha256:...",
    "policy": "sha256:...",
    "validity": {"valid_from": "...", "valid_until": "..."},
    "authority_revision": "1"
  },
  "fence": {
    "target": {...}, "epoch": "1", "holder": "...",
    "validity": {"valid_from": "...", "valid_until": "..."}
  },
  "deadlineSeconds": 300                          // 1..300
  // "identity": "registry:adopt"                 // optional; see below
}
```

Rules the issuer enforces, all fail-closed:

- `actor_role` is derived from `operatorDatabase.user` and cannot be set by the document.
- The authenticated `ProtectedClock` is mandatory. There is no wall-clock or database-time fallback.
- `approval.plan` must equal `planDigest`, and the row in the database must agree with it.
- The authority target and the fence target must be the same.
- The authority window may not exceed 1800 seconds.
- `identity` defaults to `registry:adopt` when `approval.purpose` is `adopt` and `registry:apply`
  otherwise. If that conventional key is not in the plan, set `identity` explicitly.

If `nativeCommitGuard` is declared but cannot be composed — bad path, unreadable Keychain, clock
unavailable, connection refused — the capability reports unproven and **the whole issuance is
refused**. There is no fallback to "not issuable here"; that answer is gone, because a missing guard
is now a broken operator configuration rather than an unimplemented feature.

The proof itself is two-sided, and both sides are checked against the real adapter:

1. An identity that provably is not in the plan must be refused with exactly
   `effect is outside the frozen operator plan`.
2. The planned identity must be admitted into the guarded region, and **no effect is performed**.

### What an operator still has to do

Nothing in this section is a physical operator step yet; every proof above ran against a disposable
database. To produce real Step 6 evidence an operator must supply, in the maintenance window:

- a purpose-specific Keychain holding the operator identity's key and chain, with an ACL that only the
  operator launchd job can use;
- a dedicated `r1_...` database login with the target/source function grants and an approval-revision
  mapping provisioned through migration 009;
- a signed `r1_control.authority` row for a real approval, with a validity window at or under 1800s;
- a `r1_control.target_identity` row and matching fence for the real incarnation;
- a live chrony NTS daemon, because the `ProtectedClock` refuses to start without authenticated time.

Until those exist and the probe is run through this path against the production-equivalent database,
Step 6 stays unchecked and the count of real operator capability proofs stays at zero.

### What the database now refuses on its own (2026-09-26)

`migrations/007_command_roles.sql` limits the process's database role to `r1_target_operator`, which
cannot insert, update, delete or truncate any table. Migration 008 adds narrow target-identity SELECT
for reconciliation; it grants no process-role write rights in `r1_control`. Its effect command is
`r1_target.apply_effect(...)`, and that call re-checks the approval itself:

- an approval that is revoked, is for a different purpose, or names a different target, namespace or
  incarnation is refused (`R1T02`);
- a target that is no longer the live incarnation at the caller's fence epoch is refused (`R1T02`);
- an effect whose `expected_before` no longer matches the stored state is refused (`R1T01`);
- the effect ledger and the control outbox reject `UPDATE`, `DELETE` and `TRUNCATE`.

Current time and identity enforcement:

- **Expiry** is judged by the guard, not by the database. Doing it in SQL would mean trusting the
  database's own clock, and the plan requires the authenticated chrony/NTS clock instead. A grant that has
  expired is therefore refused on the guarded path, but a caller that bypasses the guard and calls the
  command directly would not be stopped by expiry alone. Revocation, retargeting and purpose are still
  enforced in the database.
- **Which database role may use which approval** is now enforced by migration 009 (2026-09-27), described
  below. The current approval revision/actor must match the authenticated login name and role OID.
  Production mapping provisioning is still an explicit owner action.

For mapped logins, the database refuses wrong-principal, revoked, mis-targeted, out-of-epoch and repeated
effects. Protected-clock expiry still requires the guarded helper path.

### Durable dispatch and recovery protocol (2026-09-27)

Apply migrations **001 through 011 in order** in the isolated rehearsal. Migration 011 replaces the
older command with mandatory preparation-digest and private-secret arguments. Previous ledger rows are
retained, but their missing binding data cannot be supplied retroactively as verified proof.

The protected orchestration entry is `RunDispatcher.dispatch`, with a configured target helper and
current control-purpose authorization provider. It records and acknowledges UNKNOWN/audit/outbox
before calling the target and records the result afterward. Target or control acknowledgement loss
requires an explicit `RunDispatcher.reconcile`; invoking dispatch again is not recovery.

Recovery outcomes:

- **Busy target or unmatched/legacy/corrupt receipt:** UNKNOWN, no effect replay.
- **No ledger, unchanged state:** still UNKNOWN until the native owner has fenced out the old attempt.
  A newer epoch plus exclusive read-only observation supplies an abort receipt. The observer never
  advances the epoch itself. Resumption requires a new explicit attempt and current approval/fence.
- **Exact committed receipt after lost reply:** verify the helper-owned finalization witness. The new
  prepared profile can confirm completion from that durable witness; absent historical authorization
  proof remains unverified, and another approval cannot repair that history.
- **Acknowledged live guarded commit and exact matching receipt:** verified completion can be recorded.

The SQL finalizer now serializes direct command commit with revocation and target epoch changes as well
as the Python guarded path. It also refuses weakened commit durability. This is clock-independent
database enforcement; acceptance still requires provisioned role mappings and the protected clock.
The SQL command alone remains insufficient as a fully authorized privileged endpoint.

### Current-source and database identity provisioning (2026-09-27)

Migration 009 supersedes the earlier missing session-to-approval mapping. The approval actor remains
a logical identity; its database login is provisioned explicitly and is not inferred from that label.

1. Provision a dedicated non-superuser target login with membership in `r1_target_operator`, a source
   lookup login with `r1_operator_authority_reader`, and a separate provisioning/revocation login with
   `r1_operator_grant_admin`. Grant no membership in the inaccessible owner roles and no raw table-write
   rights to either process login. Production connections use the existing explicit Keychain/mTLS port.
2. The source owner supplies reviewed approvals with exact target, plan/artifact/policy digests, actor,
   purpose, revision and a validity window at most 30 minutes. The dispatcher uses distinct `apply`,
   `run` and `reconcile` approvals. The latter two do not borrow or refresh the mutation approval.
3. As the source administrator, call `r1_control.bind_operator_role(approval_id, revision, login_name)`:
   bind `apply` to the target login and `run`/`reconcile` to the source lookup login. The function checks
   role safety, derives the actor from the current source row and records audit/outbox atomically.
   Mapping identity includes the login OID. A replaced role or changed revision requires explicit new
   provisioning; an existing revision cannot be reassigned.
4. Assemble the internal helper with `build_operator_dispatcher`, the reviewed `ExecutionPlan`, the
   selected step, current approval/fence references, `ProtectedClock`, the original absolute attempt
   deadline and explicit `PostgresTLS` transports. It pins pre/postconditions as well as definition
   digests. An unavailable/stale clock or current source denies new work.
5. Revoke through `r1_control.revoke_operator_grant(approval_id)` as the source administrator. Its update
   and audit/outbox commit together and serialize against the guard's native finalization locks.

The target/source logins work without broad authority-table SELECT/UPDATE. Migrations 010/011 add the
full scoped coordination profile below. Current tests use actual logins and synthetic protected frames;
they are not live NTS or installed purpose-Keychain acceptance receipts.

### Scoped coordination profile — current entry point (2026-09-27)

1. Install reviewed migrations through **011**. Migration 010 revokes legacy apply immediately; an
   incomplete installation must remain unavailable rather than fall back to unprepared execution.
2. Give coordination `r1_run_operator`, the target `r1_target_operator`, and the separate source
   administrator `r1_operator_grant_admin`. Use different coordination/target logins with no membership
   in each other's role, no owner role and no raw table-write grant.
3. Provision distinct `plan`, `run` and `reconcile` approvals for coordination and `apply` for the target,
   bound to the reviewed plan/target/artifact/policy/actor. Map each revision to its login/OID through the
   audited binding command.
4. Use `build_scoped_operator_dispatcher` with explicit `control_database` and `operator_database` on
   the same database/port, the protected clock and original deadline. Register/begin through its
   `ScopedPostgresRunStore`; dispatch automatically receives acknowledged preparation. The older
   owner-backed store is not this profile's runtime writer.
5. Keep the dispatch secret transient and private. Do not log/archive it or reconstruct it from history.
   Normal receipt serialization omits it. It is not standalone authority. Lost prepare acknowledgement
   means UNKNOWN and explicit recovery, not preparation replay.
6. Lost target replies require explicit reconciliation. The database derives completion from native
   ledger/helper evidence and ignores caller success claims. Apply without same-transaction helper
   finalization rolls back.
7. The source administrator may call `advance_target_epoch(target_id, namespace, expected_epoch)` to
   fence late work. CAS and audit are atomic. Reconciliation still needs exclusion and unchanged state;
   fence advancement alone is not an abort receipt. Resume requires a fresh explicit attempt.

The protected control adapter releases the secret only after synchronous COMMIT acknowledgement. The
target verifies an independently committed checkpoint, matching audit/outbox and secret hash. A database
cannot prove that an arbitrary client received a network reply: use the frozen protected adapters and
their protocol, not an arbitrary SQL endpoint.

Physical acceptance is the next gate: reviewed frozen installation, actual purpose Keychains, live NTS,
production-equivalent mTLS identities and host/release-bound receipts. The latest readonly preflight
supplied no evidence bundle and proved zero capabilities; its receipt errors do not establish provider
installation status. Peak=0 checked only the disk-reserve floor.

## 12. Test-realm clock bundle — current operator handoff (2026-09-28 local)

The operator executed the initial installation below and received `INSTALLED_NOT_ACCEPTED`. The native
probe then failed. The §13 manifest-mode correction was executed, but the observer still exits 2.
The §14 diagnostic has now identified supplementary groups `[608,12,61,100]` under UID/GID 608.
The §15 repair has been applied and the observer/publisher are functioning.
The §16 retry passed as `NATIVE_CLOCK_PROBED` with both isolated-reader access denials.
**The current checkpoint and receipt prerequisites are in §17.** Earlier sequences are execution records.

### Prepared artifact

| Item | Value |
| --- | --- |
| work | `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/r1clock-20260927` |
| release | `r1t-clock-20260927` |
| manifest SHA256 | `509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752` |
| installer SHA256 | `efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67` |
| size | 2248 files / 97,622,694 bytes |
| chrony source SHA256 | `4924c6f530105bcd5b9e9e33c48a2ae1bfd889222c8480bc41601110efc864d0` (`4.9`) |
| CPython archive SHA256 | `064afb7c2fc0bbf511d886288adf98696af5105e36c138cdf2c199c0146fcf68` (`3.13.15+20260924`) |

> ⚠ **2026-09-29: the `work` directory above was deleted (macOS reaped `/var/folders/.../T/opencode/`).**
> Recovery status:
>
> - **The installed release is intact and now durably recorded.** `deployment.json` was copied out of
>   `/Library/Application Support/DocSuri/rem-1-test` to
>   `aidlc-docs/construction/rem-1-platform-integrity/code/installed-deployment-manifest.json`
>   (root-readable 0444). Its digest is `ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26`,
>   **exactly** the value recorded above, and all **2247/2247** of its artifact digests re-verify against
>   the installed files. The launch entries are intact: `nts-observer` (clock, 608/608) and
>   `clock-sample` (periodic, 608/608). The receipt directories are still absent, confirming
>   `provision_receipts.py` has never been run.
> - **The bundle is permanently lost and is NOT reproducible. Do not attempt to rebuild it.**
>   `fetch` still works — the chrony (`4924c6f5…`) and CPython (`064afb7c…`) inputs re-download and
>   re-verify, because those two are digest-pinned. But `build`/`refresh`/`seal` were run on
>   2026-09-29 to test this and produced manifest **`290aa5e01541283976049f7d31f696bd080dab34f819a543715074cdae006b4c`**
>   (2056 files / 93,252,271 bytes) — **not** `509b5074…` (2248 files / 97,622,694 bytes). The diff
>   against the installed manifest is decisive:
>   - **196 `runtime/lib/python3.13/**/__pycache__/*.pyc` files are missing.** The original bundle shipped
>     precompiled bytecode; the rebuild ships none.
>   - **5 files are new**, including `config/deployment.json` and four receipt sources written on
>     2026-09-29 that did not exist when the bundle was frozen.
>   - **9 digests differ**: `native/chronyd` and `native/chronyc` (recompiled from source),
>     `cffi`/`docsuri_platform_integrity` `RECORD`, `direct_url.json`, `uv_cache.json`, and two edited
>     sources.
>
>   The bundle embeds this repository's own source tree plus a bytecode cache, so it is a
>   point-in-time freeze, not a derivable artifact. Rebuilding from any later tree necessarily yields a
>   different bundle. **A `bundle.json` that does not hash to `509b5074…` is not the reviewed artifact
>   and must never be installed** — `install` only checks the digest you pass it, so passing the
>   rebuild's own `290aa5e0…` would install unreviewed bytes. That rebuild was deleted.
> - **`scan-handoff/` is permanently lost.** 51 components / 8 findings / 1 High
>   (`CVE-2026-82049`) / 0 ignored survive only as prose in `aidlc-docs/audit.md`. Regenerating it needs
>   network, `fetch_tools.py` (Grype) and the derived images. Treat the scan as **not reproduced**.
>
> **Consequence for acceptance.** `probe()` begins with `verify_bundle(work, …)`, so **the native clock
> probe can no longer be re-run for this release**, and the `509b5074…` pin can never be satisfied again.
> The `NATIVE_CLOCK_PROBED` result recorded in §17 stands as the executed evidence; it cannot be
> reproduced or re-verified from a bundle now. Any future clock install requires a **fresh** build, a
> fresh review of its new pins, a new manifest digest, and a new `tarfile-remediation` proof. Do not
> re-seal against the old pins.

This supersedes manifest `98e91b42…` and the earlier interim digests. The manifest binds the exact
installer bytes as well as every bundle file. Editing either requires resealing and reviewing new pins.

### Evidence to review before installation

- The installer independently pins the PSF backport identity, preimage and postimage for
  `CVE-2026-82049`; an edited manifest cannot redefine them. Unpatched bytes and cached `tarfile` bytecode
  are rejected. Bootstrap archive extraction rejects hard links.
- `<work>/tarfile-remediation.json` binds the **current manifest** to the actual frozen-runtime regression
  for both `data` and `tar` extraction filters. Verification checks the candidate before and after the
  regression and never repairs it. The proof contains `accepted=false`.
- `<work>/scan-handoff/` retains the raw SBOM/Grype capture: 51 components, 8 findings, 1 High, 0 ignored.
  The scanner lists Python `3.14.0b1` as fixed for the CPE match; the candidate uses the PSF's separate 3.13
  backport `b8f23e307097552eaea2604383a12ab280520d0d`. The raw report remains `BLOCKED`, with remediation
  review and role/freshness acceptance pending. No exception or release approval was issued.
- Earlier unprivileged rehearsal observed authenticated NTS and **400 chronyd executable mappings**
  within the frozen bundle/system libraries. This did not measure the installed Python process or prove
  role isolation. Static Mach-O/Python closure checks were separate. Result: `NTS_OBSERVED_NOT_ACCEPTED`.
- Current system-Python plan-only verification and the sealed-runtime regression pass. Main ops has
  **137 passing tests**, including 39 clock cases and two 2,000-example properties (seed `20260928`).

### Runnable operator sequence

This initial sequence was already executed; use §13 for the reported probe failure.
It verifies the unprivileged plan, creates a fresh root-only installer copy, checks its digest, installs
the two test-realm clock jobs, and probes them. Each step runs only if the previous step succeeds.
The local sudo prompt is handled in Terminal. Keep the printed installer path and the JSON results.

```sh
WORK="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/r1clock-20260927" &&
SOURCE="/Users/revenantonthemission/Projects/DocSuri/ops/platform-integrity/provision_clock.py" &&
MANIFEST="509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752" &&
INSTALLER="efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67" &&
/usr/bin/python3 -I -B "$SOURCE" install --work "$WORK" --manifest-sha256 "$MANIFEST" &&
COPY_DIR="$(/usr/bin/sudo /usr/bin/mktemp -d /private/var/root/docsuri-clock.XXXXXXXX)" &&
COPY="$COPY_DIR/provision_clock.py" &&
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0500 "$SOURCE" "$COPY" &&
printf '%s  %s\n' "$INSTALLER" "$COPY" | /usr/bin/sudo /usr/bin/shasum -a 256 -c - &&
printf 'Protected installer: %s\n' "$COPY" &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$COPY" install --work "$WORK" --manifest-sha256 "$MANIFEST" --apply &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$COPY" probe --work "$WORK" --manifest-sha256 "$MANIFEST"
```

Expected sequence: `PLAN_ONLY` (`ready=false`), checksum `OK`, `INSTALLED_NOT_ACCEPTED`, then
`NATIVE_CLOCK_PROBED`. Probe verifies installed file hashes, publishes a fresh NTS sample under the
clock UID and reads it under the isolated reader UID, which must be unable to write the frame or access
the chrony command socket. It does not issue a capability receipt or claim reboot/expiry acceptance.
If any step returns `BLOCKED`, retain the output and stop there.

### Rollback

In the **same Terminal**, the variables above remain available. This stops only the matching reviewed
test deployment and invalidates its last sample; immutable artifacts and private state remain for
inspection. A different installed manifest is refused.

```sh
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$COPY" uninstall --work "$WORK" --manifest-sha256 "$MANIFEST"
```

In a new Terminal, restore `COPY` from the printed protected path and `WORK`/`MANIFEST` from the table.

### Remaining acceptance

Live install/probe results are prerequisites for the release-bound `nts_clock` receipt and signed
preflight verification. Boot/expiry behavior, purpose Keychains, mTLS identities, encrypted backup and
restore, the 03:00 scheduler, load acceptance and registry publication remain open. A missing or malformed
receipt is not proof that a provider is absent. Step 6/10 and G1 remain unchecked; the derived-image
`CVE-2026-85091` finding also remains unresolved.

## 13. Installed clock recovery — manifest access mode (2026-09-28)

**Executed:** the operator verified all three checksums and corrected mode to 0444. The observer's second
run still exited 2. Manifest readability is resolved; use §14 to capture the remaining cause.

### Observed failure

- Operator installation succeeded for bundle manifest `509b5074…`, deployment manifest `ac0c16bb…`,
  and the two `org.docsuri.rem1.test.*` jobs. Protected installer:
  `/private/var/root/docsuri-clock.dAZVUkTy/provision_clock.py` (SHA256 `efb6145b…`).
- Readonly `launchctl print` shows the observer exited with code 2 and the periodic sampler also exits 2.
  The public sample contains `{"status":"UNAVAILABLE"}`.
- `deployment.json` is root:wheel, mode `0400`; both launch jobs start as `_docsuri_r1t_clock` (608).
  The installed Python reproduces `PermissionError` when a non-root process opens the manifest.
  The jobs therefore fail before starting chronyd. This does not establish an NTS network/authentication
  failure.

The repository fix publishes this non-secret path/digest/role manifest as root-owned **0444**. Readability
is part of installation validation, so a same-digest manifest with an incorrect mode is repaired rather
than reported as `ALREADY_INSTALLED`. The four regressions preserve distinct owner/reader identities;
the previous fixture had allowed the test reader to act as the file owner.

### Run this recovery in a local Terminal

This checks the protected installer, installed deployment contents and original bundle manifest before
changing the one manifest's mode. It starts the failed observer, then runs the existing guarded probe.
The sampler already has a five-second launchd interval. This is a correction to the existing installation;
its bundle manifest and protected installer pins remain valid.

```sh
COPY="/private/var/root/docsuri-clock.dAZVUkTy/provision_clock.py" &&
WORK="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/r1clock-20260927" &&
MANIFEST="509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752" &&
DEPLOYMENT="/Library/Application Support/DocSuri/rem-1-test/deployment.json" &&
printf '%s  %s\n' \
  'efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67' "$COPY" \
  'ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26' "$DEPLOYMENT" \
  "$MANIFEST" "$WORK/bundle.json" | /usr/bin/sudo /usr/bin/shasum -a 256 -c - &&
/usr/bin/sudo /bin/chmod 0444 "$DEPLOYMENT" &&
/usr/bin/sudo /bin/launchctl kickstart system/org.docsuri.rem1.test.nts-observer &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$COPY" probe --work "$WORK" --manifest-sha256 "$MANIFEST"
```

Expected: three checksum `OK` lines and, after synchronization, `NATIVE_CLOCK_PROBED`. The probe allows
up to 90 seconds of collector retries. If it still reports `BLOCKED`, preserve that output and the output
of the following readonly queries:

```sh
/bin/launchctl print system/org.docsuri.rem1.test.nts-observer
/bin/launchctl print system/org.docsuri.rem1.test.clock-sample
```

Rollback remains the digest-bound `uninstall` in §12 using `COPY`, `WORK` and `MANIFEST` above.
The agent has not executed this privileged recovery. Physical clock acceptance and signed receipts remain
pending the operator's result; registration alone is not daemon health.

## 14. Capture the remaining failure in the actual launchd context (2026-09-28)

**Collected:** PID 69943 reported UID/EUID/GID/EGID 608, kernel groups `[608,12,61,100]`, and
`PermissionError: runtime role boundary not established`. The strict guard is working. Proceed to §15.

The installed interpreter can now read the manifest and verify its exact digest, account mapping and all
2247 artifacts (97,140,890 bytes). These inspector-side checks pass under UID 501; they do not establish
UID 608's kernel groups or the precise native launch failure. Both jobs still exit 2 and the frame remains
UNAVAILABLE. A new permission/privilege change would be premature.

`ops/platform-integrity/diagnose_clock_launch.sh` is a bounded diagnostic for this exact installed
release. It uses the frozen interpreter and original launcher, prints real/effective UID/GID plus native
kernel groups, captures the guard exception, and intercepts `execve` before chronyd runs. It refuses root
execution, limits the guard to 15 seconds, bounds error text, and always reports `accepted=false` and
`targetExecuted=false`. SHA256:

```text
410016041adc71e2a503848446ee3ac1a222d73571976e0bf2202ef41869ecbe
```

### Run once using two Terminals

The block creates a fresh protected diagnostic copy. `launchctl debug` overrides only the observer's
next invocation while retaining its configured service identity, working directory and resource limits.
Its stdout/stderr are directed to the current Terminal, and the diagnostic settings are cleared after
that invocation. The original plist and installed bundle are not rewritten.

**Terminal A:** configure output capture and leave this command running. With terminal stdout/stderr
attached, `launchctl debug` waits in the foreground; do not chain `kickstart` after it with `&&`.

```sh
SOURCE="/Users/revenantonthemission/Projects/DocSuri/ops/platform-integrity/diagnose_clock_launch.sh" &&
DIAG_DIR="$(/usr/bin/sudo /usr/bin/mktemp -d '/Library/Application Support/DocSuri/rem-1-test/clock-diagnostic.XXXXXXXX')" &&
DIAG="$DIAG_DIR/diagnose_clock_launch.sh" &&
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0555 "$SOURCE" "$DIAG" &&
printf '%s  %s\n' '410016041adc71e2a503848446ee3ac1a222d73571976e0bf2202ef41869ecbe' "$DIAG" | \
  /usr/bin/sudo /usr/bin/shasum -a 256 -c - &&
/usr/bin/sudo /bin/chmod 0755 "$DIAG_DIR" &&
/usr/bin/sudo /bin/launchctl debug system/org.docsuri.rem1.test.nts-observer \
  --program "$DIAG" --stdout --stderr -- "$DIAG"
```

**Terminal B:** once Terminal A prints `Service configured for next launch.`, start the observer:

```sh
/usr/bin/sudo /bin/launchctl kickstart -p system/org.docsuri.rem1.test.nts-observer
```

For the already-pending diagnostic at `clock-diagnostic.WzjHE9EL`, Terminal A is still attached; only the
Terminal B command is needed. The older chained command may continue its queued kickstart/sleep after
the diagnostic completes. Capture the diagnostic JSON from Terminal A.

Retain the JSON line with `diagnostic: "r1t-clock-launch-v1"` and any stderr. The PID is printed in
Terminal B; diagnostic output appears in Terminal A. `LAUNCH_DIAGNOSTIC_FAILED` includes the exact stage/error and kernel groups;
`LAUNCH_GUARD_PASSED_NO_EXEC` means the launcher checks passed but the target was deliberately not run.
Neither result is a clock capability receipt. The actual UID-608 result is still pending.

Verification of the helper: four regressions cover exec interception/restoration, group-error reporting,
root refusal and bounded/incomplete results; full ops **141 passed**, Ruff and shell syntax pass. An
unprivileged smoke run reports UID 501's expected role-boundary failure, which is not the native job's
diagnosis. The next correction must be based on the operator's actual launch-context report.

## 15. Repair explicit supplementary-group isolation (2026-09-28)

**Applied:** the operator received `REPAIRED_NOT_ACCEPTED`. Both repaired plist hashes match; chronyd is
running as UID/GID 608 and the publisher exits 0. The first reader clock check failed; continue with §16.

The native report proves that `InitGroups=false` did not establish the required group set. The installed
launcher already has the approved root verification/drop path: verify the manifest and every artifact,
then `setgroups([])`, `setgid(608)`, `setuid(608)`, verify native credentials, and only then execute the
clock target. The old plist started this launcher as UID 608 and skipped that branch.

The repository renderer now starts the **bootstrap** as root:wheel and adds Python `-B` alongside `-I`.
`-B` prevents root from creating unmanifested bytecode. The actual observer and collector execute only
after the unchanged strict guard verifies their non-root identity and cleared supplementary groups.
`launchctl print` will show the configured bootstrap user as root; that is not the target process UID.

### Verified repair artifact

`ops/platform-integrity/repair_clock_groups.py` is plan-only by default and bound to:

- Original bundle `509b5074…`, original provisioner `efb6145b…`, deployment `ac0c16bb…` and UID/GID 608.
- Both exact original plist preimages (`ab40d8a3…` observer, `3f059ce1…` sample).
- Fixed changes to bootstrap `UserName`, `GroupName`, and the guard's `-B` argument. A foreign or partly
  edited plist is refused; an exact already-repaired plist is recognized.
- Complete installed artifact and CA verification before any service change. Apply stops both jobs,
  invalidates the old sample, writes plists atomically, then bootstraps them. A failed or interrupted
  bootstrap attempts to stop both scoped labels, including an unacknowledged start.

Repair script SHA256: `9fc69cb3b2ec72bcd30b5eea4770b58de8e6455617ce750a9d4a6dabec3e3812`.
Expected repaired plist SHA256 values:

| Job | SHA256 |
| --- | --- |
| nts-observer | `e9eb9bc34a23bee0c77e9b3c8aec3ec04413c1f24cf6f97cf37d78d8898ca653` |
| clock-sample | `d751260ff3599fc2f71c7412c55c143e4bfb7ec885525441a7c010bfaa8e319a` |

System-Python plan-only verification of the real installation passes and produces those exact values;
the corrected renderer independently produces the same values. Platform **534 passed / 90.42%**, ops
**156 passed**, including 15 repair cases and a 2,000-example retargeting property (seed `20260928`).
These tests simulate privileged mutation/launch operations; operator apply is still required.

### Operator repair and probe

**First press Ctrl+C in Terminal A, which is still running the old `launchctl debug` capture.** This
ends the foreground capture and cancels its queued `&& kickstart` tail so it cannot race with repair.
The diagnostic report has already been captured. Then run the block below from a normal shell prompt:

```sh
SOURCE="/Users/revenantonthemission/Projects/DocSuri/ops/platform-integrity/repair_clock_groups.py" &&
WORK="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/r1clock-20260927" &&
ORIGINAL="/private/var/root/docsuri-clock.dAZVUkTy/provision_clock.py" &&
REPAIR_DIR="$(/usr/bin/sudo /usr/bin/mktemp -d /private/var/root/docsuri-clock-groups.XXXXXXXX)" &&
REPAIR="$REPAIR_DIR/repair_clock_groups.py" &&
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0500 "$SOURCE" "$REPAIR" &&
printf '%s  %s\n' '9fc69cb3b2ec72bcd30b5eea4770b58de8e6455617ce750a9d4a6dabec3e3812' "$REPAIR" | \
  /usr/bin/sudo /usr/bin/shasum -a 256 -c - &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$REPAIR" --work "$WORK" --provisioner "$ORIGINAL" &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$REPAIR" --work "$WORK" --provisioner "$ORIGINAL" --apply &&
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$ORIGINAL" probe --work "$WORK" \
  --manifest-sha256 509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752
```

Expected sequence: checksum `OK`, `PLAN_ONLY`, `REPAIRED_NOT_ACCEPTED`, then `NATIVE_CLOCK_PROBED`.
Retain all JSON output. A registered job is not yet clock health; the final probe supplies that evidence.

For this installed release, replaying the **original** `install --apply` would render the old role-start
plists again and undo the repair. Use the repair/probe sequence above. The original provisioner's
digest-bound `uninstall` remains the stop/rollback path if repair or probing fails:

```sh
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B "$ORIGINAL" uninstall --work "$WORK" \
  --manifest-sha256 509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752
```

This stops the matching test deployment and preserves immutable artifacts for inspection. The agent
has not applied the repair; signed capability acceptance and Step 6/10/G1 remain pending.

## 16. Probe the now-stable source without reapplying repair (2026-09-28)

**Passed:** the operator's retry returned `NATIVE_CLOCK_PROBED`, `CLOCK_READ_VERIFIED`, both access denials
true, and `capabilityReceiptIssued=false`. No further clock repair/retry is requested at this checkpoint.

The latest failure is at the isolated reader's `ProtectedClock` call, after the collector succeeded and
the reader identity/group assertion passed. Its failed frame was not retained, so the exact predicate
cannot be recovered. Initial synchronization uncertainty or concurrent publication is possible, not a
confirmed cause.

Current readonly observations show:

- Observer PID 87325 is chronyd with real/effective UID/GID 608; the sampler exits 0.
- Both plist hashes equal the approved repaired values. Frames are authenticated, available, owned by
  UID 608, mode 0444, single-link, and match config/boot/resume identities.
- The installed `ProtectedClock` passes five inspector-UID-501 reads across 20 seconds, with window widths
  543326, 543384, 498018, 498066 and 602966 microseconds (about ±0.25–0.30 seconds).

These checks establish a materially different, stable source state. They do not replace the UID-600
reader's file/socket isolation proof. Run **only** the existing probe once:

```sh
/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root \
  /usr/bin/python3 -I -B /private/var/root/docsuri-clock.dAZVUkTy/provision_clock.py \
  probe --work /var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/r1clock-20260927 \
  --manifest-sha256 509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752
```

Expected result is `NATIVE_CLOCK_PROBED`. Retain the JSON. If it still fails, capture the UID-600 frame/
context rejection specifically rather than applying another launcher repair. The original probe retries
the producer but performs the reader check once; no policy threshold or guard has been relaxed.

## 17. Native clock probe complete; signed receipt preparation (2026-09-28)

### Verified operator result

- `NATIVE_CLOCK_PROBED`, profile `test`, collector `OBSERVED`.
- Isolated reader `CLOCK_READ_VERIFIED`, with `clockWriteDenied=true` and `commandSocketDenied=true`.
- UTC window `[1790599834753553, 1790599834989279]` microseconds: width **235726 us**, or **±117863 us**.
- `capabilityReceiptIssued=false`: this is live native probe evidence, not a signed acceptance receipt.
- Readonly inspection still observes chronyd PID 87325 and the exact repaired plist hashes.

The native live-clock/read-isolation checkpoint is complete. Expiry/reboot acceptance and signed release
acceptance remain separate obligations; Step 6/10/G1 are not promoted to complete.

### Prepared receipt probe references

`ops/platform-integrity/clock-receipt.test.json` contains only the deployed frame path, writer UID 608
and config digest `sha256:0f0e16c09299e7d7768d1db50bde805e5598a59e535bc0cd18d86757b1990b05`.
The following readonly command was run from `ops/`:

```sh
uv run --frozen --all-extras python platform-integrity/issue_receipt.py \
  --config platform-integrity/clock-receipt.test.json \
  --release r1t-clock-20260927 --probe-only
```

Result: `PROBED`, `nts_clock: {proven: true, reason: verified}`. The other four capabilities report
`not_configured` because this reference document declares only the clock. Overall exit 2 is expected for
that incomplete set. The command read no signing key and issued no receipt. This agent-side check does
not replace the operator's already-completed isolated-reader evidence above.

### Next implementation/provisioning work

1. Complete the approved role-scoped Keychain signer and frozen issuer execution boundary. The existing
   `issue_receipt.py --key` interface reads a protected PEM file; it is the current bootstrap/test seam,
   not completed production Keychain signing assembly.
2. Bind the issuer/preflight validity checks to the authenticated clock window. `receipt_from()` and the
   standalone preflight currently default to local wall time; a valid native clock is now available to
   complete that wiring.
3. Supply an independently provisioned, release-trusted public-key entry with key ID, validity and
   revocation status. The standalone CLI currently reads evidence-named trust files; production trust
   must be anchored outside the caller's receipt/evidence rather than established by it.
4. Run a fresh live probe under the protected issuance path, issue only `nts_clock`, and verify the
   host/release-bound signature through preflight. Missing other capabilities must remain unproven.

No new signing key, trust approval or signed receipt was created during this checkpoint.

## 18. launchd signer unattended issuance — operator decision 2026-09-30

### Decision
**Keep the signer job and supply a root-owned password file.** The launchd job cannot prompt, and the
purpose Keychain has `lock-on-sleep timeout=300s`; without a password source the job always fails with
`purpose signing key unavailable: KeyUnavailable: ... security status -25293 (0xffff9d33)`. The
alternative (attended issuance only) loses automation. A root-owned password file restores unattended
issuance but accepts a persisted secret. The operator chose this tradeoff on 2026-09-30.

### What changed
`ops/platform-integrity/receipt_signer_job.py` now accepts `--keychain-password-file` on `install`:

```
sudo uv run --directory ops python platform-integrity/receipt_signer_job.py install \
  --profile test --release r1-clock-20260927-r3 \
  --library-source /path/to/platform_integrity/src \
  --keychain-password-file /absolute/path/to/keychain.pw \
  -- --capability nts_clock --days 1
```

The file must be:
- Regular file (not symlink, not directory)
- Root-owned (`uid 0`)
- Mode exactly `0400` (no group/other bits)
- Inside a root-owned, non-writable directory (parent `uid 0`, mode not group/world writable)
- Exactly one line, 12..1024 bytes, ending in newline

The installer:
1. Validates the file and records its digest in the job state (`job.json`).
2. Writes `StandardInPath` into the plist pointing at that file.
3. Appends `--keychain-password-stdin` to the job's argv (the caller cannot override it).
4. On every run, `run_bootstrap` re-verifies the file and its digest before exec; a swapped, relaxed,
   or deleted file is refused with `keychain password source changed since the job was installed`.

The password never appears in `argv`, the environment, or a process listing. Launchd opens the file
as the job's stdin; the issuer reads one line via `read_password`, unlocks the Keychain, signs,
and re-locks in a `finally` block.

### Operator steps (requires root + TTY for sudo)

1. Create the password file **outside the signer realm** (so `--replace` never deletes it):
   ```bash
   sudo mkdir -m 0700 /root/.docsuri/secrets
   printf '%s\n' "YOUR_12_TO_1024_BYTE_PASSWORD" | sudo tee /root/.docsuri/secrets/keychain.pw >/dev/null
   sudo chmod 0400 /root/.docsuri/secrets/keychain.pw
   sudo chown root:wheel /root/.docsuri/secrets/keychain.pw
   ```

2. Install the job with the password source:
   ```bash
   sudo uv run --directory ops python platform-integrity/receipt_signer_job.py install \
     --profile test --release r1-clock-20260927-r3 \
     --library-source "$(pwd)/platform_integrity/src" \
     --keychain-password-file /root/.docsuri/secrets/keychain.pw \
     -- --capability nts_clock --days 1
   ```

3. The job runs unattended (triggered by whatever start condition you wire). To test manually:
   ```bash
   sudo launchctl start system/org.docsuri.test.receipt-sign
   # tail the results
   sudo cat /Library/Application\ Support/DocSuri/rem-1-test/signer/results/job.out
   ```

4. Rotate the password without reinstalling:
   ```bash
   printf '%s\n' "NEW_PASSWORD" | sudo tee /root/.docsuri/secrets/keychain.pw >/dev/null
   # Job re-verifies the digest on next run; it will refuse if you relax the mode or change the digest.
   ```

### Security posture
- The password is a persistent secret on disk. Treat it like any other root-only credential.
- The validator enforces the strictest practical constraints (ownership, permissions, directory
  integrity, size, newline). It does not prevent a root compromise, but it raises the bar.
- The `--replace` flow does NOT delete the password file; it is operator-managed.
- If you revert to attended issuance, uninstall the job and omit `--keychain-password-file` on the
  next install. The plist will then omit `StandardInPath` and the argv will lack
  `--keychain-password-stdin`.

### Tests
`ops/tests/test_receipt_signer_job.py` gained 12 tests:
- `test_signer_job_plist_omits_stdin_when_no_password_source_is_bound`
- `test_signer_job_plist_wires_the_password_source_to_stdin`
- `test_job_argv_adds_the_stdin_flag_only_for_unattended_jobs`
- 9 `verify_password_source` tests covering ownership, permissions, directory writability, symlink
  rejection, size bounds, missing newline, and short/long passwords.
All pass; full suites remain green.

## 19. Five-capability probe map — current provisioning gaps (2026-09-30)

The probe infrastructure for all 5 capabilities is implemented and tested. A comprehensive probe config
`ops/platform-integrity/full-probe.test.json` exists and runs. Current status:

| Capability | Probe Result | Root Cause | Operator Action Required |
|---|---|---|---|
| `keychain_roles` | `purpose_key_unavailable` | Only signer keychain exists; 9 role keychains (reader, runner, tool, bundle, audit, journal, backup, clock) not created | Provision 9 role keychains with `docsuri.rem1` service, matching accounts; update probe config paths |
| `tls_roles` | `role_login_failed` | Database not running or mTLS credentials missing | Start PostgreSQL, provision mTLS certs for target roles, add keychain to probe config |
| `nts_clock` | `protected_clock_unavailable` | Frame shows `{"status":"UNAVAILABLE"}`; observer must publish fresh frame | Run clock probe with `sudo` (observer publishes frame) or verify observer job is running |
| `native_commit_guard` | `not_configured` | Probe config missing `operatorTls`, `guard_identity`, `guard_connection`, `guard_definition_digest` | Provision operator authority in DB, bind to login, add keychain and identity to probe config |
| `restore_receipt` | `trusted_clock_required` | Depends on valid `nts_clock` window | Resolve `nts_clock` first; then create `restore.json` with encrypted+verified restore into new incarnation |

None of these are code defects — every probe is implemented and the failure reasons are precise
provisioning signals. The operator must execute the provisioning steps in §8A, §12, §13, and §6 to
populate the live infrastructure each probe validates.

### Probe execution (readonly, no signing)
```bash
uv run --directory ops python platform-integrity/issue_receipt.py \
  --config platform-integrity/full-probe.test.json \
  --release r1t-clock-20260927-r3 --probe-only
```

Expected output structure (all false until provisioned):
```json
{
  "state": "PROBED",
  "host": "D8420CE8-FD62-5BA1-9C1F-FE4BBA7D4D77",
  "release": "r1t-clock-20260927-r3",
  "capabilities": {
    "keychain_roles": {"proven": false, "reason": "purpose_key_unavailable"},
    "tls_roles": {"proven": false, "reason": "role_login_failed"},
    "nts_clock": {"proven": false, "reason": "protected_clock_unavailable"},
    "native_commit_guard": {"proven": false, "reason": "not_configured"},
    "restore_receipt": {"proven": false, "reason": "trusted_clock_required"}
  }
}
```

## 20. Backup restore + load snapshots — implementation complete (2026-09-30)

### LocalRestoreTarget.restore() — now copies the archive
`ops/src/docsuri_ops/adapters/backup.py` `LocalRestoreTarget.restore(archive: Path)` now:
- Validates archive exists and target incarnation directory does not
- Creates the isolated target directory (mode 0700)
- Copies the archive file into it (preserving name)
- Returns `(True, "restored <archive> into <target>")` or failure detail

The evidence collector (`ops/src/docsuri_ops/backup_evidence.py`) now captures the archive path from `write_archive` and passes the `Path` to `restore()`, instead of the digest string.

### Distinct before/after load snapshots — concrete probe + CLI
`ops/src/docsuri_ops/load_probe.py` implements `DependencyProbe` for PostgreSQL:
```bash
# Before load test
python -m docsuri_ops.load_probe \
  --host 127.0.0.1 --port 5432 --database rem1 --user r1_reader \
  --tables runs,ledger,checkpoint,audit \
  --output dependency_state_before.json

# Run load acceptance (600s, 5 req/s, mTLS)
uv run --directory ops python platform-integrity/load_acceptance.py \
  --url https://127.0.0.1:18101 --subject <subject> \
  --ca <ca.pem> --certificate <cert.pem> --key <key.pem> \
  --output result.json --seconds 600 --rps 5 --listener-pid <pid>

# After load test
python -m docsuri_ops.load_probe \
  --host 127.0.0.1 --port 5432 --database rem1 --user r1_reader \
  --tables runs,ledger,checkpoint,audit \
  --output dependency_state_after.json

# Include in load acceptance
uv run --directory ops python platform-integrity/load_acceptance.py \
  ... --dependency-state dependency_state_after.json \
  --dependency-state-before dependency_state_before.json
```

The probe:
- Connects with mTLS (`sslmode=verify-full` by default)
- Password via stdin (never argv/env)
- Writes snapshot as JSON `{table: count, ...}` with mode 0600
- Tables are comma-separated in `--tables`

Tests: `ops/tests/test_load_probe.py` (3 tests, mocked psycopg).

## 21. CVE/SBOM/G1 Disposition — summary (2026-09-30)

Full detail in `ops/platform-integrity/cve-disposition.md`. Source of truth: `sbom-targets.json` v2.

### Actionable blocking findings: 2
| CVE | Severity | Location | Status |
|---|---|---|---|
| CVE-2026-85091 | High | Derived postgres (`docsuri/postgres-alpine-16.15-nosu`), alpine zlib 1.3.2-r0 | **NO UPSTREAM FIX** — operator must choose: time-boxed exception with compensating controls, or alpine base refresh |
| CVE-2026-82049 | High | Clock observer (Python 3.13 `tarfile`) | **MITIGATED IN BUILD** — PSF backport `b8f23e30` pinned, installer-enforced preimage/postimage pins, sealed-runtime regression passes |

### Rejected / superseded
- Legacy postgres `postgres@sha256:a3b7f...` — 74 blocking OS advisories, gosu Go stdlib 24 High/Critical. **REJECTED**; replaced by derived image without gosu.

### Unscanned this cycle (require re-scan)
redis, opensearch, minio, elasticmq — run `fetch_tools.py` + `scan_sbom.py` in maintenance window.

### G1 gate
**BLOCKED** on:
1. CVE-2026-85091 exception decision (or base refresh)
2. Remaining image re-scans
3. Docker bridge mTLS validation for derived postgres
4. pip-audit SIGABRT resolution or non-blocking documentation

### Operator actions
1. Decide CVE-2026-85091 path (exception vs refresh) and update `sbom-targets.json` `status`.
2. Re-scan 4 unscanned images: `fetch_tools.py --destination <dir>` then `scan_sbom.py --tools <dir> --output <dir> --subject <name> --source docker:<image> --profile production`.
4. Execute Docker bridge mTLS test for derived postgres.
5. Resolve/Document pip-audit SIGABRT.
6. Sign off `sbom-targets.json` status fields → G1 can be evaluated.
