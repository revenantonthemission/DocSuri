# REM-1 native 설치 및 복구 인수 — operator 입력

2026-09-25 readonly 관측: 현재 사용자는 UID 501이며 `sudo -n true`는 로컬 인증을 요구한다. FileVault는 Off다. `/Volumes/SSD01`은 기존 데이터가 있는 USB APFS volume이고 암호화되지 않았다. 이 관측은 설치 완료 또는 backup 대상 선택의 증명이 아니다.

코드/격리 인수는 독립적으로 진행한다. 아래 답변은 privileged test realm과 실제 encrypted backup/recovery 인수를 진행할 때 필요하다. 비밀번호·recovery key는 이 문서나 채팅에 기록하지 않는다.

## Question R1OP1
검토된 REM-1 설치 산출물이 준비되면 native test/서비스 UID, protected roots/Keychain/launcher 설치에 필요한 로컬 관리자 실행과 FileVault 준비를 어떻게 진행할 것인가?

A) Operator가 로컬에서 관리자 인증·검토된 설치 절차·FileVault 및 복구 key 보관을 수행하고 결과를 제공한다.

B) Host-level 준비를 보류하고 해당 native/G1 인수는 blocked로 유지한다.

X) Other (구체적인 허용 경계/절차를 `[Answer]:` 뒤에 기록한다).

[Answer]: A — Operator-assisted setup (2026-09-25).

## Question R1OP2
실제 backup/restore 인수에 사용할 이미 보유한 encrypted APFS 이동식 volume과 일일 접근 시간을 지정한다. 기존 volume의 포맷/삭제 또는 자동 암호화는 수행하지 않는다.

A) Operator가 SSD01 장치에 준비한 encrypted APFS volume을 사용한다. 아래에 mount alias와 일일 연결/회수 시간을 적는다.

B) 다른 이미 암호화된 보유 volume을 사용한다. 아래에 mount alias와 일일 연결/회수 시간을 적는다.

X) Other (대상/접근 계획을 `[Answer]:` 뒤에 기록한다).

[Answer]: A — Prepare SSD01 volume (2026-09-25). 사용자 제공(2026-09-26): mount alias `DocSuri_Backup`, 일일 연결/회수 시간 `03:00`. 실제 mount path `/Volumes/DocSuri_Backup`의 APFS 암호화·마운트를 확인했다. R1OP3=A로 매일 03:00 한국시간 백업 시작·볼륨 상시 연결을 확정했다.

### 확인한 볼륨 정보 (2026-09-26T02:15:16Z 이후 readonly 관측)

- Volume UUID: `BB384D60-46AF-4A06-B6F7-95710B3B7A3C`.
- 장치 `disk5s2`, APFS container `disk5`, USB physical store `disk4s2`. 기존 SSD01(`disk5s1`)과 같은 container의 별도 volume이다. device 번호는 재연결 때 달라질 수 있다.
- `/Volumes/DocSuri_Backup`에 mounted, `Encryption=true`, `Locked=false`, `WritableVolume=true`.
- container 공유 여유: `1,537,204,109,312` bytes(약 1.54 TB). 별도 예약 용량이나 실제 backup peak의 검증값은 아니다.
- 후속 operator 실행 및 2026-09-26T02:46:30Z 이후 readonly 재관측에서 `GlobalPermissionsEnabled=true`를 확인했다. backup volume 소유권 적용은 완료됐고, 로컬 host의 FileVault는 별도로 Off다.

## Question R1OP3
제공한 `03:00`의 시간대와 의미를 확정한다. 실제 백업 중 volume이 연결되는 구간을 알아야 일정을 정할 수 있다.

A) 한국시간(Asia/Seoul, UTC+9) 매일 03:00에 백업을 시작한다. 볼륨은 상시 연결되어 있다.

B) 한국시간(Asia/Seoul, UTC+9) 매일 03:00에 볼륨을 연결하고, 백업·검증 완료를 확인한 뒤 회수한다.

C) 한국시간(Asia/Seoul, UTC+9) 매일 03:00에 볼륨을 회수한다. 답변에 연결 시작 시각도 적는다.

X) Other (시간대, 백업 시작/연결/회수 시점 및 접근 가능한 구간을 `[Answer]:` 뒤에 적는다).

[Answer]: A — 매일 03:00 Asia/Seoul(UTC+9)에 백업 시작, 볼륨 상시 연결. 사용자 `R1OP3: A` (2026-09-26T02:36:28Z). 백업 일정의 operator fact를 확정했으며 실제 scheduler 설치/활성화는 아직 미완료다.

## Operator 실행 결과 (2026-09-26)

- R1OP1: 원 준비 artifact hash `94d73055dc46ea97db04275e3c99a81a054f1efdc3ba9989f9ed826fe511bbb5`의 보호된 복사본으로 `--apply` 실행 완료. 역할별 UID/GID 600~608과 0700 디렉터리를 OS 조회로 대조했다. 상태는 `PREPARED_NOT_ACCEPTED`다.
- R1OP2: 같은 backup volume UUID의 encryption/mount/ownership enabled를 실제 확인했다.
- 첫 `--probe`는 9개 TimeoutExpired로 BLOCKED였으며, r2 단일 reader 통과 뒤 동일 r2 전체 실행도 **ROLE_FILE_ISOLATION_VERIFIED/completeRoleCoverage=true**로 완료됐다. UID/GID 600~608 모두 자기 파일 read/write와 교차 read/write 각 8개·group 파일 read 3개 거부를 통과했다. 결과는 [operator handoff §4](../rem-1-platform-integrity/code/operator-handoff.md#4-전체-9-role-파일-격리-확인--완료)에 기록했다. 이후 installed launcher/NTS/Keychain/DB/backup 인수는 별도 작업이다.
