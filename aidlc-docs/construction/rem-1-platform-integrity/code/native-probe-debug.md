# REM-1 native probe — failure capture 및 contained recovery

## Failure capture

- 작업: 실제 UID/GID로 synthetic 파일 격리를 확인하는 REM-1 native probe.
- 원 검증판: `90aa58859bdfcd922f9aa2fe9a8a49a93a9e87b07be0a769b125585976ebac7f`.
- 사용자 실행: 2026-09-26 12:21:05 로컬 terminal에서 protected `verify.py --probe`.
- 결과: 역할 9개 모두 5초 `TimeoutExpired`, `BLOCKED`/`ready=false`.
- 원 artifact: `/Library/Application Support/DocSuri/rem-1-test/role-probe-su4773zc`; 보존.
- 마지막 성공: account/directory metadata 확인. 실제 worker의 마지막 phase는 원 report에 없어 미확정이다.
- 환경: main `develop`/`32a424d1`, source patch 일치 확인, root operator 실행과 agent의 비대화형 sudo 거부를 구분한다.

## Diagnosis — 확인한 사실과 가설

1. `ps`의 600~608 UID 조회에서 남은 Python worker는 관측되지 않았다. 해당 시각 시작한 launchd 소유 distnoted/lsd/trustd/secd/containermanagerd가 보였다. 이 목록만으로 timeout 원인을 단정하거나 OS agent를 정리하지 않는다.
2. `/usr/bin/python3`의 `sys.executable`과 그 realpath도 실제 실행 image와 다르다. `proc_pidpath`는 `/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python`을 반환했다. `nm`에서 framework bin의 `_Py_Initialize`/`_posix_spawn` launcher와 actual image의 `_Py_BytesMain`을 구분했다.
3. agent UID의 같은 최소 환경/EOF handshake는 약 0.093초에 worker의 예상 identity 거부까지 도달했다. 이는 일반 pipe 전달 동작의 증거이며 UID 600의 정상 동작 증명은 아니다.
4. **가설**: 제한된 UID의 launcher/bootstrap 또는 후속 native/file I/O에서 지연됐다. 기존 stderr/phase가 없으므로 정지 지점 및 정확한 근인은 아직 확정할 수 없다. timeout 값을 늘려 결과를 통과시키지 않는다.

## Contained recovery

- 실제 parent process image를 Darwin `proc_pidpath`로 관측하고 해당 interpreter를 직접 실행한다. 선택된 path와 SHA256을 report에 기록하며 lookup 실패에 launcher fallback을 두지 않는다.
- `worker_entered` → imports/input/identity/kernel-groups → own-file/open/read/write/fsync → cross-role/group checks의 고정 stage marker를 추가했다. 일반 응답에는 allowlist 밖의 stderr를 반영하지 않는다.
- timeout의 partial progress를 보존하고 새 session의 소유 process group을 종료한다. parent reap/pipe quiescence가 불분명하면 그대로 미확인 상태를 보고한다. 추가 role은 첫 timeout 이후 실행하지 않는다.
- `--role reader`로 한 역할만 재실행한다. subset 통과는 PARTIAL이며 전체 9-role coverage로 확대하지 않는다. 새 fixture와 root 전용 bounded stderr/report를 보존한다.
- 변경 scope는 `ops/platform-integrity/provision_test_realm.py`와 관련 tests다. 기존 서비스/계정/volume 설정을 바꾸는 recovery는 실행하지 않았다.

## Verification / introspection result

- system Python 3.9 worker parsing: PASS.
- Ruff: PASS.
- focused native tests: **22 passed**. 실제 subprocess EOF 전달, timeout progress, process-group 정리, pipe 보유 자손 종료 및 marker 이전 timeout 구분을 포함한다. 테스트의 UID switch seam은 unprivileged로 대체하므로 production role 인수는 아니다.
- 관측한 interpreter image를 직접 실행한 일반 UID smoke에서 `worker_entered`부터 `identity_check`까지 확인했고 예상 `process_identity` 거부로 종료했다.
- 진단판 SHA256: `2e310b60c37e0398f18c9c4351398d49cf4857d5c46c2addc744126be00e4e23`.
- **결과 갱신: recovery verified / 9-role synthetic-file scope 완료.** 단일 reader 0.052초 통과 뒤 동일 r2 전체 실행이 ROLE_FILE_ISOLATION_VERIFIED/completeRoleCoverage=true로 완료됐다. 9개 UID의 자기 read/write, 교차 read/write 각각 72회 거부 및 directory group read 27회 거부를 확인했다. 원 9개 timeout의 단독 근인은 과거 phase가 없어 소급 확정하지 않는다. 전체 결과는 [operator-handoff.md §4](operator-handoff.md#4-전체-9-role-파일-격리-확인--완료)에 기록했다. installed launcher/Keychain/NTS/DB/backup/G1 범위는 여전히 별도다.
- 반복 비용 억제: 전체 9개 반복 대신 단일 역할/5초 경계로 제한하고 관측 결과로 다음 조치를 결정한다. 예방 회귀는 launcher image 선택, phase 기록, EOF 및 cleanup tests로 유지한다.

### 실제 reader 결과 보존 (2026-09-26 수신)

- scope: synthetic-file-access-only; state: PARTIAL_ROLE_FILE_ISOLATION_VERIFIED.
- probe root: `/Library/Application Support/DocSuri/rem-1-test/role-probe-e_0w5ja7`.
- interpreter SHA256: `07470fa2e1aec690aa62061af6e0f65fe9bf3169a74a16384592fb1ff1cb320f` (현재 로컬 executable과 일치).
- 15개 stage가 worker_entered부터 complete까지 관측됐다. stderr 318 bytes, truncation=false; cleanup=not_needed.
- 이 단일 실행의 `completeRoleCoverage=false` 및 `ready=false`를 보존한다. 후속 전체 결과는 다음 절에 기록한다.

### 전체 9-role 결과 보존 (2026-09-26T04:03:22Z 수신 기록)

- state ROLE_FILE_ISOLATION_VERIFIED, completeRoleCoverage=true, scope synthetic-file-access-only.
- probe root `/Library/Application Support/DocSuri/rem-1-test/role-probe-236g0xrp`.
- reader/runner/tool/bundle/sign/audit/journal/backup/clock 전부 VERIFIED. 각 UID=GID이고 kernel group은 해당 GID 하나다(600~608).
- role별 worker 0.044~0.051초, returncode=0, timedOut=false, lastStage=complete, parentReaped=true, cleanup=not_needed.
- role별 교차 읽기/쓰기 거부 각 8회, group 파일 읽기 거부 3회; 합계 72/72/27. source/interpreter hash는 현재 파일과 대조했다.
- 이 증거로 현재 r2의 해당 실행 범위 recovery를 확인했다. code/timeout 변경 없이 전체로 확대했고 `ready=false`와 나머지 G1 조건을 보존한다.
