# REM-1 Platform Integrity — Infrastructure Design 계획

**단계**: CONSTRUCTION -> Infrastructure Design
**유닛**: `rem-1-platform-integrity` (REM-1)
**일자**: 2026-09-20
**상태**: R1IF1~R1IF10 답변 수령·기록 완료; Infrastructure 산출물 생성·검증 진행
**입력 승인**: R1NDR1=A, R1ND1~9=A, R1NFRR1=A, R1FDR1=A, DAD1=A, UGR1=A
**추가 제약**: C-14 — 사용자 `The infrastructure should be zero-cost and everything should be served from this mac mini.`

이 계획은 application serving을 **이 Mac mini에 한정**하고 유료 infrastructure/서비스/license/계량 과금 및 새 장비 구매를 전제로 하지 않는다. 기존 장비/회선은 제공된 자원으로 사용한다. 실제 무료 사용 자격과 기존 backup 자원은 확인해야 하므로 **R1IF1/2에 임의 권장 답변을 넣지 않는다**. R1IF3~10의 A는 물리 배치 제안이며 답변 전 적용하지 않는다.

## 1. 승인 입력과 비용 경계

- `../rem-1-platform-integrity/functional-design/`: E-R1/FL-R1/BR-R1/PROP-R1의 business/권한/assurance 계약.
- `../rem-1-platform-integrity/nfr-requirements/`: NFR-R1-01~24, TD-R1-01~17, EV-R1-01~09와 선택된 수치/stack/복구 profile.
- `../rem-1-platform-integrity/nfr-design/`: PAT-R1-01~12, LC-R1-01~17, VAL-R1-01~18 및 실제 capability proof obligations.
- master `requirements.md`의 C-4/5/13 및 새 C-14, NFR-C1/RES-2/5/10/12를 함께 적용한다.

| 영역 | 비용 0원 / local serving 기준 |
|---|---|
| application/API/worker/inference | Mac mini의 native launchd/Python/Node/Ollama. 원격 VM/serverless/managed application hosting을 추가하지 않음 |
| serving data/queue/evidence | Mac mini의 local Postgres/Redis/OpenSearch/S3-compatible object store/ElasticMQ 및 REM 파일 realm. 원격 managed DB/object serving으로 이동하지 않음 |
| release/tooling | 공개 OSS/기존 무상 사용권과 검증된 immutable artifacts. paid registry, Docker Desktop 유료 전제, Apple Developer Program 가입을 필수로 만들지 않음 |
| ingress/공개 자료 | 기존 무료 Cloudflare Tunnel은 Mac-origin의 전달 경계로 재사용하고 package/advisory/time source는 outbound 검증 입력으로 취급. application 실행 위치를 외부로 옮기지 않음 |
| 관측 | 실제 metrics/log/audit/status는 local. host-down 부재 감지는 무료 외부 dead-man 또는 이미 소유한 독립 observer를 R1IF9에서 확인 |
| backup | passive encrypted off-host copy에 사용할 **이미 소유한 무상 자원**을 R1IF2에서 확인. 같은 internal disk의 다른 폴더/VM/MinIO를 off-host로 부르지 않음 |
| 과금/한도 | trial 종료, free-tier 초과, paid notification/CI/license의 자동 전환을 금지. 0원 조건을 입증하지 못하면 해당 외부 기능을 준비 완료로 표시하지 않음 |

backup 자원 부재는 RES-2/10/12가 자동 면제됐다는 뜻이 아니다. off-host 요구와 strict local-only 해석이 충돌하면 별도 요구사항 명확화를 먼저 수행한다. 새로운 유료 cloud backup을 기본 대안으로 제안하지 않는다.

## 2. 현재 근거와 확인되지 않은 사실

아래 source 경로는 workspace root 기준이며 실제 secret/account 설정의 확인을 뜻하지 않는다.

| 근거 | 관찰 / 영향 |
|---|---|
| `ops/server/install.sh:7-17,59-107` | 현재 모든 역할은 GUI 사용자 LaunchAgent 및 동일 HOME/repo wrapper를 사용. REM-1의 실제 role/UID/key 분리를 그대로 충족한다고 볼 수 없음 |
| `ops/server/run.sh:23-42` | 환경 파일 전체 export, repo PYTHONPATH 및 mutable virtualenv/Node 경로. frozen release launcher와 최소 환경으로 교정해야 함 |
| `backend/docker-compose.yml` | local data plane/loopback ports, Postgres `docsuri` DB, 현재 version/latest image 및 예제 credential/TLS 미강제 설정. 신규 R1 role/TLS와 공유 변경 순서가 필요 |
| `ops/local/backup-db.sh`, `ops/server/README.md` | Postgres dump/list 후 local+iCloud copy, 30일 prune 및 기존 runbook의 MinIO off-host gap. iCloud 실제 plan/잔여 quota/원격 회수 가능성을 확인한 것은 아님 |
| `ops/server/heartbeat.sh` | local/API/public-BFF probe 후 외부 dead-man ping. ping URL은 secret capability이며 보호된 별도 설정으로 공급해야 함 |
| `.github/workflows/ci.yml` | 기존 hosted workflow가 있음. local CI 선택 시 기존 자동 trigger/required checks와 비용 조건을 함께 정합화해야 하며, 무료 quota 또는 계정 billing 상태를 확인했다고 가정하지 않음 |
| 기존 NFR 관측 (2026-09-19) | RAM 24 GiB/CPU 14, data volume 97%·약 15.5 GiB free, FileVault Off. 설치/백업/전환 전 현재 값 재검증 필요 |
| 이번 read-only 환경 확인 | macOS 26.6.2, arm64, Xcode developer directory 확인. root provisioning/native bridge의 실행 검증을 마친 것은 아님 |
| `lsof -nP -iTCP:8101 -sTCP:LISTEN` | 이번 사용자 관측에서 listener 없음. 8101은 제안 포트이며 설치 시 다시 충돌/접근성을 검증 |
| shared infrastructure 문서 조회 | `aidlc-docs/construction/shared-infrastructure.md` 없음. 선택 후 shared resource/owner/변경 영향 문서를 생성해야 함 |

### 공식 자료 확인 (2026-09-20)

| 자료 | 설계에 사용한 사실 |
|---|---|
| [OrbStack pricing](https://orbstack.dev/pricing) | Free는 personal/non-commercial, business/commercial은 유료. 현재 프로젝트의 해당 자격을 추정하지 않음 |
| [Colima](https://github.com/abiosoft/colima) | MIT, Apple Silicon/macOS 및 Docker runtime 지원. 다른 runtime의 volume을 자동으로 공유/이관한다고 가정하지 않음 |
| [Apple launchd guide](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) | system daemon/user agent, 역할 사용자/소켓/명시 one-shot 및 dependency 준비의 구분. 실제 현재 OS에서 동작 확인 필요 |
| [PostgreSQL SSL](https://www.postgresql.org/docs/16/ssl-tcp.html) | SSL 활성화만으로 plaintext가 금지되지 않음. hostssl/client certificate/verify-full 및 role mapping 필요 |
| [chrony 지원 시스템](https://chrony-project.org/) / [chronyd -x](https://chrony-project.org/doc/4.6/chronyd.html) | macOS 지원 및 system clock를 조정하지 않고 offset/frequency를 추적하는 observer mode. version/native 기능은 pin·검증해야 함 |
| [Cloudflare NTS](https://developers.cloudflare.com/time-services/nts/) | TLS 기반 key exchange와 authenticated NTP, `time.cloudflare.com` 지원. 단순 wall clock 또는 unauthenticated NTP를 신뢰 window의 근거로 대체하지 않음 |
| [Healthchecks pricing](https://healthchecks.io/pricing/) | Hobbyist $0/20 jobs/100 ping-log entries. 이 provider history가 local 90일 critical audit를 대신하지 않음 |

## 3. 재사용할 물리 기준과 후보 배치

### 3.1 Local roots / profiles

- 제안 root는 `/Library/Application Support/DocSuri/rem-1/`다. `releases/<releaseId>/`, digest-addressed `toolchains/`, `generations/`, `staging/<runId>/`, `state/`, `journal/`, `audit-export/`를 분리한다. FileVault가 보호하는 같은 local APFS filesystem에서 atomic head replacement/durability를 검증한다.
- release/toolchain은 root-managed, runtime role에는 readonly다. generation의 publisher owner와 tool staging writer를 분리하고 sealed files의 늦은 descriptor write도 검증한다. 비편집 wheel/고정 Python/Node/도구 digest를 사용하며 developer HOME의 interpreter나 repo checkout을 release 근거로 쓰지 않는다.
- helper socket 등 ephemeral IPC는 `/var/run/docsuri/rem1/`에 둔다. **durable busy/journal witness는 재부팅 때 사라지는 run 디렉터리에만 두지 않는다.** canonical Run/evidence/audit는 승인된 Postgres realm/immutable 파일 권위를 따른다.
- 일반 로그는 local `/Library/Logs/DocSuri/rem-1/`, critical 원장은 별도 Postgres append-only realm과 검증된 archive다. 3-generation 일반 로그 rotation으로 90일 감사를 대체하지 않는다.
- test profile은 `rem-1-test` root, 별도 OS/DB role/CA/Keychain/socket namespace와 synthetic data를 사용한다. 생산 `.env`, Docker socket, volume, credential을 test 기본값으로 상속하지 않는다.
- 모든 새 capture/VM/image/tool staging은 기존 `free >= 10 GiB + 2 × additional peak` 및 RSS/admission 조건을 확인한다. root/UID/port는 설계 값이며 이번 단계에서 생성/설치하지 않는다.
- observer/proxy/launcher/relay를 별도 process로 만들더라도 해당 role 및 전체 host 예산에서 빼지 않는다. 작은 보조 process마다 새로운 full-size budget을 추가한 것으로 계산하지 않는다.

### 3.2 Logical-to-physical mapping 후보

| LC | 실제 후보 | 결정 / 인수 |
|---|---|---|
| LC-R1-01 | dedicated reader UID의 native R1C, loopback TLS `127.0.0.1:8101` | R1IF3/5/6, 8+2/512 MiB/3s |
| LC-R1-02 | frozen Python pure evaluator | runtime signature/policy/schema 동치, target 비변경 |
| LC-R1-03 | local Postgres control schema/제한 role/command functions | R1IF4, transaction/CAS/read snapshot |
| LC-R1-04 | target별 제한 DB role와 dedicated session helper | R1IF3/4/6, actual lock/guard/revoke/ledger 인수 |
| LC-R1-05 | publisher UID의 helper-owned APFS generation/head | R1IF3/6, same-filesystem atomic replace/flush/pin |
| LC-R1-06 | 보호된 local append-only journal/witness | R1IF3/6, torn-write/권한/복구 인수 |
| LC-R1-07 | one-shot supervisor와 protected host slot/process witness | R1IF3/10, child/RSS/disk/cancel/quiescence |
| LC-R1-08/09 | reader의 bounded LRU/breaker와 전용 readonly pool | 64 MiB 포함 512 MiB, 3-failure/10s/single probe |
| LC-R1-10 | U3/운영 owner의 non-renewing source와 native target guard | R1IF4/6, source-role를 REM-1이 임의 복제하지 않음 |
| LC-R1-11 | local chrony NTS observer + protected ClockHealth adapter | R1IF7, 30s/±1s와 boot/resume proof |
| LC-R1-12 | Postgres critical audit/outbox + local bounded relay | R1IF4/8, app self-delete 거부 |
| LC-R1-13 | local U6 JSON/metrics/status + 선택된 무료 dead-man | R1IF9, 민감정보/paid 알림 배제 |
| LC-R1-14 | local encrypted capture + 실제 보유 off-host target | R1IF2, consistency cut/회수/restore |
| LC-R1-15/16 | 별도 tool UID의 pinned generator/SCA subprocess | offline resolver와 scanner egress 분리, Docker socket ambient 권한 없음 |
| LC-R1-17 | 목적별 Keychain/signing helper와 current guard | R1IF3/6, arbitrary sign API 없음 |

## 4. 필수 질문 범주 평가

| 범주 | 적용 근거 / 질문 |
|---|---|
| Deployment Environment | serving host는 Mac mini로 확정. 무료 runtime 자격, root/운영 및 격리 검증은 R1IF1/3/10 |
| Compute Infrastructure | native roles, child/helper의 실제 UID/진입점 및 local clock observer는 R1IF3/7 |
| Storage Infrastructure | 실제 backup 자원, Postgres realm/APFS/Keychain 및 보존은 R1IF2/3/4/6 |
| Messaging Infrastructure | 승인된 Postgres outbox의 물리 drain/wakeup은 R1IF8. R1C에 새 broker 의존을 추가하지 않음 |
| Networking Infrastructure | loopback endpoint/인증서/UDS 및 source-bound service identity는 R1IF5/6 |
| Monitoring Infrastructure | local 관측, 시간 신뢰와 독립 host-down 감지는 R1IF7/9 |
| Shared Infrastructure | container runtime/Postgres/ingress/clock/backup/관측을 기존 service와 조율하는 R1IF1/4/8/9/10 |

일곱 범주는 모두 평가한다. 이미 확정된 single-host/stack/pattern/수치/보안·복구 조건은 아래 선택에서도 유지한다.

## 5. Infrastructure 질문

### R1IF1 - 현재 container runtime의 무상 사용 자격

공식 안내상 OrbStack Free는 personal/non-commercial이다. 이 프로젝트의 실제 사용 상황에 맞는 경로를 선택한다. 이 사실은 AI가 대신 확정할 수 없다.

A) **OrbStack Free 유지 자격이 있다.** 현재 사용이 personal/non-commercial에 해당하고 paid/trial 기능을 전제로 하지 않음을 확인한다. C-5의 기존 runtime을 유지한다.

B) **개인/비상업 무료 자격을 확정할 수 없거나 무조건 무상 OSS 경로를 원한다.** Colima/Lima + Docker Engine/CLI로 같은 Mac mini의 data plane을 전환하는 설계를 선택한다. 이 선택은 C-5의 container manager 부분을 수정하며, 실제 volume backup/restore/rollback과 space 검증 후 수동 전환한다. 원 volume을 바로 삭제하거나 두 VM의 중복 저장 공간을 가정하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 사용 목적/이미 확보된 무상 사용권 또는 local runtime 경로를 기술)

[Answer]: B

### R1IF2 - 추가 비용 없이 이미 사용할 수 있는 off-host backup 자원

RPO ≤24h와 실제 restore를 유지하려면 Mac 내부 disk와 분리된 copy가 필요하다. 이미 소유한 자원만 선택하고 resource 별칭·가용 용량·일일 연결/회수 가능 시간을 함께 기록한다. credential/복구 secret을 답변에 넣을 필요는 없다.

A) **이미 소유한 removable drive가 있다.** encrypted backup을 기록/검증하고 분리 보관할 수 있다. 같은 Mac에 계속 물려 있는 폴더만으로 off-host 완료를 선언하지 않고 분리/회수·restore 증거와 일일 운용 절차를 명세한다.

B) **이미 소유한 별도 장비/NAS/무상 저장 자원이 있다.** application은 계속 Mac mini에서만 serve하고 별도 자원은 encrypted backup copy만 보관한다. 새 요금이 없으며 exact 원격본 회수와 필요한 용량/retention을 입증할 수 있는 자원을 기술한다.

C) **확인된 무상 off-host 자원이 아직 없다.** local encrypted capture와 restore tooling은 설계하되 off-host/RPO 인수는 미충족으로 남긴다. 기존 복구 요구를 변경할지 또는 실제 자원을 제공할지는 별도 명확화하며 현재 선택만으로 요구를 면제하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 실제 사용 가능한 무상 backup 경로·용량·회수 방법을 기술)

[Answer]: A

### R1IF3 - Root-managed 설치와 helper 실행 방식

release/상태 root는 §3의 local APFS 경로를 사용하고 reader/supervisor/tool/SQL/publisher/signer/audit·retention capability별 non-login UID 및 DB/file 권한을 분리한다. numeric UID는 충돌 검사로 할당한다. helper를 어떤 경로로 호출할까?

A) **LaunchDaemon reader + 제한된 one-shot launcher**. R1C만 keepalive daemon으로 두고 supervisor는 명시 실행한다. root-owned launcher/제한 sudo 정책이 allowlisted immutable helper entry를 정해진 service UID로 실행한다. arbitrary shell/환경/실행 파일을 전달하지 않고 helper가 exact request/현재 목적 권한을 검증한다. (권장)

B) **LaunchDaemon reader + launchd on-demand helper sockets**. 목적별 protected local socket의 호출로 helper가 시작되고 bounded run을 처리한다. kernel peer identity/current grant를 검증하고 crash 후 privileged action을 자동 재개하지 않는다. socket activation/check-in/빠른 종료 throttling 및 queued transport 요청의 deadline을 별도로 검증한다.

기존 GUI 사용자 하나의 HOME/환경을 모든 role에 복제하지 않는다. OrbStack/Ollama가 로그인 세션에 의존하는 현재 조건과 FileVault preboot unlock을 고려해 의존성 미준비를 bounded unready로 처리한다. daemon이 root로 모든 작업을 실행하는 구조는 선택지가 아니다.

X) 기타 (아래 `[Answer]:` 뒤에 actual UID/권한 분리를 만족하는 local supervisor/helper 경로를 기술)

[Answer]: A

### R1IF4 - Postgres control/audit realm의 실제 배치

기존 local Postgres cluster와 target ledger transaction을 유지하면서 control metadata를 어디에 둘까?

A) **기존 `docsuri` DB의 별도 `r1_control`/`r1_audit` schema**. NOLOGIN owner와 runtime reader/coordinator/helper/audit/relay 역할을 분리하고 원 domain의 source authority/guard는 그 owner의 namespace/port에 둔다. audit 및 protected 상태는 raw unrestricted CRUD 대신 제한된 command/권한으로 다룬다. (권장)

B) **같은 cluster의 전용 `docsuri_platform` DB**. control/audit schema를 별도 DB로 분리한다. target ledger 및 원 owner의 authority guard는 기존 target DB에 유지하고 cross-DB commit을 원자적이라고 주장하지 않는다. 여러 DB의 backup/cut/role/복구를 추가로 검증한다.

두 안 모두 현재 공유 credential/SSL 선택만으로 준비 완료라 하지 않는다. role-scoped TLS 접속, `hostssl`/client identity mapping 및 client `verify-full`을 검증한다. source guard는 U3/운영 authority의 현재 epoch/철회와 native commit에 연결하며 sliding session verify나 async cache로 대체하지 않는다. legacy startup/CLI와 DB owner 권한 전환도 R1 구현/검증에 포함한다.

X) 기타 (아래 `[Answer]:` 뒤에 DB/schema/owner/guard/backup 경계를 기술)

[Answer]: A

### R1IF5 - R1C의 private endpoint와 TLS 경계

외부 공개 경로는 기존 무료 tunnel -> Mac BFF이고 R1C는 private serving이다. 제안 포트 8101의 TLS를 어디에서 종료할까?

A) **R1C native TLS/mTLS**. `127.0.0.1:8101`에서 고정 internal evidence/health resource를 제공하고 별도 현재 caller/object 권한을 검사한다. helper-local IPC는 보호된 pipe/UDS의 kernel peer와 목적 grant로 검증한다. 모든 TCP 연결의 TLS/peer 검증은 유지한다. (권장)

B) **같은 Mac의 local TLS proxy + R1C UDS**. loopback 8101의 OSS proxy가 client certificate를 검증하고 보호된 UDS로만 R1C에 연결한다. proxy identity/인증 정보 전달을 위조할 수 없도록 peer/고정 protocol을 검증하며 proxy와 reader의 resource 합계를 기존 budget에 포함한다.

application을 외부에 호스팅하거나 R1 mutation endpoint를 공개하지 않는다. 내부 CA/신뢰 파일/SAN/role mapping을 명시하고 plaintext fallback, 임의 proxy target 또는 인증서 검증 해제를 금지한다. 기존 gateway/store의 TLS 변경은 shared owner와 단계적으로 검증한다.

X) 기타 (아래 `[Answer]:` 뒤에 loopback endpoint/TLS/client identity 및 helper-local transport 경계를 기술)

[Answer]: A

### R1IF6 - Keychain/내부 CA와 cold-boot key 준비

유료 certificate/KMS 없이 Keychain/목적별 key 분리를 실제로 구성할 방법을 선택한다.

A) **purpose-specific custom keychains + operator boot unlock**. root-managed local keychain files와 role별 접근을 만들고 operator의 FileVault/login 이후 제한된 unlock/credential provider로 필요한 key만 준비한다. local CA의 issuer key는 application role과 분리하고 native bridge의 동작을 검증한다. (권장)

B) **System Keychain + 좁은 code/role ACL**. 목적별 item을 System Keychain에 두고 검증된 helper identity/코드 요구사항/OS role로 접근을 제한한다. generic interpreter 전체를 trusted app으로 허용하지 않으며 ACL 갱신/새 release/재부팅 시 non-interactive access를 검증한다. paid Developer ID 가입을 전제로 하지 않는다.

두 안 모두 record 서명은 승인된 Ed25519/JCS이고 TLS identity/CA key는 별도 목적이다. PEM 파일만 받는 TLS/DB library에는 Keychain을 원천으로 하는 짧은 수명의 role-private runtime materialization을 명시한다(0700 directory/0600 file, FileVault volume, 최소 수명/회전/정리). 이것은 plaintext 환경 파일 fallback이 아니며 secret을 argv/로그/source에 넣지 않는다. locked/denied 상태에서는 실제 capability가 unavailable이다.

X) 기타 (아래 `[Answer]:` 뒤에 Keychain/내부 CA custody, 역할별 접근과 boot/unlock 경로를 기술)

[Answer]: A

### R1IF7 - 비용 없는 trusted clock provider

30s age/±1s window를 실제 source/오차 근거로 입증할 observer를 어디에 둘까?

A) **Mac-native chrony NTS observer**. 검증·고정한 macOS build를 `-x` observer mode로 실행해 system clock를 조정하지 않고 authenticated time source의 offset/frequency/상태를 관측한다. protected adapter가 source age/불확실성/drift와 host continuous time/boot-resume을 결속해 readonly clock context를 제공한다. (권장)

B) **같은 Mac의 isolated Linux-container observer**. local VM 안에서 clock-control capability 없이 chrony NTS observer를 실행한다. host bridge가 VM와 host 시간을 같다고 가정하지 않고 관측/전달 지연을 포함한 window를 검증한다. 추가 process/VM resource 및 socket 권한을 명세한다.

무료 `time.cloudflare.com` 같은 명시된 NTS source를 사용하고 source/CA/도구 pin·outbound 제한을 적용한다. typical accuracy나 network-time enabled flag만으로 ±1s를 선언하지 않는다. authenticated source/current uncertainty/age 또는 resume 증명이 없으면 fail closed다. 초기 TLS 시간 검증을 우회하는 옵션을 production 기본값으로 두지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 실제로 입증 가능한 무상 local clock observer/source와 window 근거를 기술)

[Answer]: A

### R1IF8 - Postgres audit outbox의 local 전달 구동

critical 원장은 Postgres이며 새 broker는 필요하지 않다. U6/archive로 전달하는 bounded relay를 어떻게 깨울까?

A) **명시 local timer/poll relay**. 전용 role의 one-shot relay가 60s 간격으로 durable outbox를 확인하고 한정 batch를 전달한다. heavy lane/budget이 없으면 pending/lag를 관측하고 기존 원장은 유지한다. (권장)

B) **LISTEN/NOTIFY wakeup + 주기 재조정**. 같은 local Postgres의 notification을 빠른 wake hint로 사용하고 60s reconciliation scan으로 누락/재시작을 복구한다. notification은 진실원천이나 durable receipt가 아니며 listener/relay의 권한/자원도 분리한다.

일반 telemetry와 critical durability를 혼동하지 않는다. audit row는 immutable, delivery cursor는 별도이며 application self-delete를 금지한다. R1C/health에 ElasticMQ/queue 또는 relay 가용성을 필수 호출로 추가하지 않는다. 기존 다른 REM의 queue는 계속 같은 Mac의 별도 권한 realm이다.

X) 기타 (아래 `[Answer]:` 뒤에 zero-cost/local outbox drain/wakeup/복구 방식을 기술)

[Answer]: A

### R1IF9 - Local 관측과 독립 host-down 감지

metrics/log/audit 및 DocSuri status는 Mac에서 제공한다. host 자체가 꺼졌을 때의 감지는 어느 무상 보조 경계를 사용할까?

A) **기존 Healthchecks Hobbyist 유지**. 현재 두 heartbeat/backup check를 무료 한도 안에서 사용하고 최소한의 redacted 상태만 전송한다. local 데이터/대시보드를 외부로 이전하지 않고 paid notification/업그레이드를 사용하지 않는다. quota/계정 상태와 실제 알림 수신을 확인한다. (권장)

B) **이미 소유한 독립 observer 사용**. 추가 비용 없는 별도 장비/네트워크 관측에서 host absence를 탐지한다. 장비/관측 경로와 실제 알림 방법을 기술한다. 동일 Mac의 자기 ping만으로 host-down 탐지를 완료했다고 하지 않는다.

무료 provider의 100 ping-log entries를 90일 critical 감사 보존으로 취급하지 않는다. ping capability/알림 credential은 보호된 source에서 제공하며 로그에 노출하지 않는다. 독립 observer가 없으면 해당 감지 인수는 미충족으로 남긴다.

X) 기타 (아래 `[Answer]:` 뒤에 local serving과 비용 0원을 만족하는 관측/host-down 경계를 기술)

[Answer]: A

### R1IF10 - 이 Mac에서의 격리 검증과 CI 실행

추가 compute 구매/paid CI 없이 실제 macOS/PG/filesystem/권한 인수를 어떻게 실행할까?

A) **operator-triggered local rehearsal + 고정 revision의 local schedules**. 별도 test UID/root/CA/DB port·namespace와 synthetic data에서 PR/release/nightly profile을 실행한다. 검토된 exact revision만 실행하고 resource/target preflight 후 결과를 기존 GitHub review 흐름에 연결한다. 기존 hosted workflow trigger/required checks도 local 검증·비용 조건에 맞게 조정하며 결과 없이 gate를 통과시키지 않는다. cold-boot/FileVault/공유 DB 변경은 console 접근과 backup/rollback이 있는 명시 maintenance window에서 확인한다. (권장)

B) **격리 local self-hosted CI worker**. 같은 Mac의 dedicated test account/VM/socket/mount/network에서 trusted protected branch 작업만 받는다. production Docker socket/volume/Keychain 및 production ports/credential에 접근할 수 없음을 먼저 입증한다. fork PR/unreviewed workflow를 production 권한으로 자동 실행하지 않는다.

host fault/clock/kill 시험은 production 프로세스/시각/데이터를 직접 교란하지 않는 주입·격리 경로를 사용한다. VM 안의 Linux 통과가 native Mac Keychain/Filesystem/FileVault 인수를 대신하지 않는다. disk/메모리 또는 격리 조건이 부족하면 작업을 보류하고 유료 runner나 임의 data cleanup으로 전환하지 않는다.

X) 기타 (아래 `[Answer]:` 뒤에 실제 가능한 무상 격리 검증/운영 window/CI 경계를 기술)

[Answer]: A

## 6. 답변 분석과 shared 변경 순서

1. R1IF1의 license 자격/선택과 R1IF2의 실제 medium·용량·일일 회수 가능성을 먼저 확인한다. 불명확하면 임의 가정으로 설계를 완료하지 않는다. R1IF1=B는 C-5/runtime 참조의 제한적 개정과 검증된 export/restore/cutover 계획을 함께 기록한다.
2. root/UID/helper/Keychain/TLS/DB 역할의 실제 분리가 source/동기 DAG와 맞는지 확인한다. public/API/user grant와 OS/service identity를 구분한다.
3. PostgreSQL TLS/role/native authority guard 변경이 기존 application, migration runner, backup과 각 원 owner에 미치는 영향을 mapping한다. current authority/commit/revoke 인수 없이 G1을 통과시키지 않는다.
4. filesystem atomics는 선택된 실제 APFS volume/같은 filesystem에서 확인한다. container VM disk/host bind mount/임시 디렉터리의 차이를 숨기지 않는다. 새 runtime/volume/restore에는 incarnation/rollback 인수를 연결한다.
5. clock/key/budget/backup/runtime 준비 순환을 제거한다. observer와 제한된 bootstrap trust는 live R1C/RK 없이 준비되고, 증명되지 않은 현재 권한/clock은 ready가 아니다.
6. shared 변경은 additive 준비 -> isolated verification -> verified backup/rollback -> 수동 제한 전환 -> 실제 health/인수 순서다. 새 R1R와 legacy privileged writer를 같은 scope에 동시 활성화하지 않는다.
7. free 조건/계정/물리 capacity를 인수 증거에 남긴다. 신규 비용 또는 off-host 자원 부재가 상위 요구와 충돌하면 requirements clarification 후 진행하며, 보안/복구를 조용히 낮추지 않는다.

## 7. 질문 추적성과 산출물

| 질문 | 승인 입력 / 실제 검증 |
|---|---|
| R1IF1 | C-5/14, NFR-R1-01/05/16/17; EV-R1-01/05/07 |
| R1IF2 | C-14, NFR-R1-12/14~16; PAT-R1-10; EV-R1-07 |
| R1IF3 | NFR-R1-01/04/08/13; LC-R1-01/04~07/17; VAL-R1-04/13 |
| R1IF4 | NFR-R1-02/03/10/20; PAT-R1-02/03/09; VAL-R1-01~03/09 |
| R1IF5 | NFR-R1-07/13; PAT-R1-01/02/12; EV-R1-06 |
| R1IF6 | NFR-R1-10~13/15; PAT-R1-02/12; VAL-R1-10/13/16 |
| R1IF7 | NFR-R1-08~11; PAT-R1-08; VAL-R1-12 |
| R1IF8 | NFR-R1-19/20; PAT-R1-09; VAL-R1-09/18 |
| R1IF9 | C-14, NFR-R1-19/24; PAT-R1-12; EV-R1-09 |
| R1IF10 | C-14, NFR-R1-21/22; TD-R1-14~16; EV-R1-01~09 |

답변 분석 후 다음 문서를 생성한다.

- `aidlc-docs/construction/rem-1-platform-integrity/infrastructure-design/infrastructure-design.md`: actual roots/roles/store/CA/clock/backup/monitoring와 LC/PAT/NFR/인수 매핑.
- `aidlc-docs/construction/rem-1-platform-integrity/infrastructure-design/deployment-architecture.md`: single-Mac environment, shared dependency/boot/unlock, packaging/provision/순서/전환·rollback·복구 및 비용 경계.
- `aidlc-docs/construction/shared-infrastructure.md`: 공유 resource, canonical owner, 최소 권한, 변경 영향/선행성/각 REM 검증 책임. 현재 해당 파일은 없으므로 새 shared 문서를 만들되 기존 unit의 실제 권위를 덮어쓰지 않는다.

Security Full, custom single-Mac Resiliency, Full PBT를 유지한다. 적용 규칙은 실제 선택/배치/검증 책임과 per-rule로 대조한다. PBT의 Infrastructure 실행 적용은 stage table상 N/A이나 승인된 framework/profile/PROP/VAL/EV의 후속 검증을 유지한다. 외부 무료 보조 서비스의 사용과 실제 off-host data/감지는 C-14 및 답변을 대조한다.

## 8. 실행 체크리스트

- [x] `Continue to the next stage`를 R1NDR1=A로 기록하고 Infrastructure 상세 규칙을 로드했다.
- [x] 사용자 zero-cost/Mac-mini serving 제약을 C-14/NFR-C1/state/audit에 반영했다.
- [x] 승인 FD/NFR/PAT/LC와 local installer/launcher/compose/backup/heartbeat 및 shared 문서 부재를 확인했다.
- [x] 관련 공식 자료와 macOS/architecture/Xcode/제안 port의 read-only 근거를 확인했다.
- [x] 일곱 필수 범주와 10개 질문, LC 물리 후보/인수/비용 경계를 작성했다.
- [x] 질문/빈 답변/A/B/Other 각 10개, R1IF2의 추가 사실 선택지, R1IF3~10의 권장안 8개, 필수 범주 7개를 확인했다. LC 17개 전수 매핑/질문 trace 10행/승인 ID 참조 50개 및 C-14 유일성을 검증했고 Prettier debug-check와 tracked/new-file whitespace가 통과했다.
- [x] R1IF1~10 답변과 필요한 실제 resource 정보를 수집하고 충돌/미확정을 해소한다. (2026-09-22: R1IF1=B, R1IF2=A, R1IF3~10=A. R1IF2의 실제 drive 별칭/용량/일일 회수 시간은 설치 시 operator fact로 기록하며 사전에 미확정 사실로 표기한다. 모순·모호성 없음.)
- [x] Infrastructure 두 산출물 및 shared-infrastructure 문서를 생성한다. (2026-09-22: `rem-1-platform-integrity/infrastructure-design/infrastructure-design.md`, `deployment-architecture.md`, `construction/shared-infrastructure.md`)
- [x] 실제 배치/role/boot/TLS/clock/durability/backup/zero-cost 인수 및 확장 per-rule 정합성을 검증한다. (ID 참조/LC 17 전수 매핑/결정·인수 대조, Prettier check 통과, git diff --check 통과. Mermaid 렌더는 로컬 headless 미가용으로 파서 실패(DOMPurify 환경) — 문법은 보수적 quoted-label 형태이며 규범상 텍스트 대안을 문서에 수록함.)
- [x] Infrastructure 완료 리뷰와 별도 명시 승인을 받는다. (2026-09-24: 사용자 "continue to next stage" = R1IFR1=A.)
- [x] 승인 후 REM-1 Code Generation의 상세 계획을 작성한다. (`rem-1-platform-integrity-code-generation-plan.md`, 2026-09-24; R1CGR1 승인 대기.)

## 답변 방법

R1IF1/2는 실제 사용 자격과 이미 있는 backup 자원에 대한 답변이 필요하다. **R1IF3~10은 A를 권장**한다. 각 `[Answer]:`에 선택과 필요한 resource 설명을 기록한다. 불명확한 license/backup을 A로 가정하지 않으며, 모든 정책/필수 resource가 정합화된 뒤 세 Infrastructure 산출물을 생성한다.
