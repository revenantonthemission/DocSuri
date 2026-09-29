# REM-1 — Infrastructure Design

**단계**: CONSTRUCTION / Infrastructure Design
**유닛**: REM-1 Platform Integrity (`rem-1-platform-integrity`)
**상태**: 작성·검증 완료 (2026-09-22; `../../plans/rem-1-platform-integrity-infrastructure-design-plan.md`)
**선택**: R1IF1=B, R1IF2=A, R1IF3=A, R1IF4=A, R1IF5=A, R1IF6=A, R1IF7=A, R1IF8=A, R1IF9=A, R1IF10=A
**Companion**: `deployment-architecture.md`, `../../shared-infrastructure.md`
**입력**: 승인 FD/NFR/PAT/LC와 C-14(무비용·Mac mini serving) 및 C-5 제한 개정(R1IF1=B)

## 1. 범위와 권위

이 문서는 승인된 논리 컴포넌트(LC-R1-01~17)와 패턴(PAT-R1-01~12)을 이 Mac mini의 실제 리소스에 매핑한다. 숫자/권한/보존/UNKNOWN 보장을 낮추는 물리 배치를 만들지 않는다. application serving은 이 Mac mini에 한정하고 유료 인프라/서비스/license를 전제하지 않는다.

| 영역                             | mac mini 실제 배치                                                                                                         | 근거 문구                           |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| application/API/worker/inference | native launchd/Python/Node/Ollama(기존), REM-1 신규 role만 추가                                                            | C-14, NFR-R1-01                     |
| data plane                       | local 컨테이너 data plane을 **Colima + Docker Engine**로 재호스팅(R1IF1=B). Postgres/Redis/OpenSearch/MinIO/ElasticMQ 유지 | 공식 OrbStack Free 자격 미확정 회피 |
| control/evidence                 | local Postgres `r1_control`/`r1_audit` schema(R1IF4=A) + `/Library/Application Support/DocSuri/rem-1/` filesystem realm    | NFR-R1-02/04/05                     |
| ingress                          | 기존 무료 Cloudflare Tunnel -> Mac BFF. R1C는 private loopback 8101                                                        | NFR-R1-13, PAT-R1-01                |
| backup                           | operator가 이미 보유한 이동식 드라이브(R1IF2=A). 실제 별칭/용량/일일 회수 시간은 설치 시 기록하는 operator fact            | PAT-R1-10, NFR-R1-15/16             |

실제 후보 리소스의 존재/권한/자격은 이 문서만으로 증명되지 않는다. 설치·전환·검증은 Code Generation 이후 EV-R1-01~09의 증거로 판정한다.

## 2. 선택 결정과 결과

| 답변     | 채택 배치                                                                                                                                                                   |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1IF1=B  | Colima/Lima + Docker Engine/CLI로 전환. 기존 OrbStack VM volume(Postgres/OpenSearch)은 export/검증/복구 확인 후에만 정리한다. MinIO는 host bind mount로 VM 디스크 안에 없다 |
| R1IF2=A  | 이동식 드라이브 APFS 암호화 볼륨에 quiesced capture + detached archive. 별칭/용량/일일 회수 시간은 설치 operator fact로 기록하고 사전에 실제 값으로 기입하지 않는다         |
| R1IF3=A  | R1C reader만 LaunchDaemon keepalive. supervisor/helper는 root-owned launcher가 allowlisted 고정 entry를 전용 service UID로 one-shot 실행                                    |
| R1IF4=A  | 기존 `docsuri` DB에 `r1_control`/`r1_audit` schema. NOLOGIN 소유자, command function, `hostssl`+클라이언트 identity mapping+`verify-full`                                   |
| R1IF5=A  | R1C native TLS/mTLS `127.0.0.1:8101`, helper-local IPC는 보호된 UDS의 kernel peer/목적 grant                                                                                |
| R1IF6=A  | 목적별 custom keychain 파일 + operator boot unlock. TLS/DB runtime 재료는 Keychain 원천의 단명 0700/0600 파일                                                               |
| R1IF7=A  | Mac-native chrony NTS observer(`-x`)를 별도 UID로 실행하고 보호된 health 자료를 R1C adapter에 공급                                                                          |
| R1IF8=A  | 제한 role의 one-shot relay가 60s 간격으로 durable outbox를 bounded batch 전달                                                                                               |
| R1IF9=A  | Healthchecks Hobbyist 유지(무료 한도). 최소한의 redacted 상태만 외부 전송                                                                                                   |
| R1IF10=A | operator-triggered local rehearsal + 고정 revision의 local schedule. 별도 test UID/root/CA/DB 포트·namespace와 synthetic data                                               |

## 3. 실제 roots, ports, sockets

| 자원                 | 실경로/값                                                                         | 소유/경계                            |
| -------------------- | --------------------------------------------------------------------------------- | ------------------------------------ |
| release root         | `/Library/Application Support/DocSuri/rem-1/releases/<releaseId>/`                | root-managed, runtime role read-only |
| toolchain            | `.../toolchains/<digest>/`                                                        | root-managed, digest-addressed       |
| generations          | `.../generations/<generationId>/`                                                 | bundle helper UID 소유               |
| staging              | `.../staging/<runId>/`                                                            | tool UID 소유                        |
| canonical state      | `.../state/`(e.g. `binding-head`, generated material)                             | publisher/허용 helper만 write        |
| bootstrap journal    | `.../journal/`                                                                    | 별도 journal UID append-only         |
| audit export/archive | `.../audit-export/`                                                               | audit/relay role                     |
| keys                 | `.../keys/<purpose>.keychain-db`                                                  | root-managed custom keychains        |
| ephemeral IPC        | `/var/run/docsuri/rem1/`(UDS)                                                     | kernel peer grant로 검증             |
| 일반 로그            | `/Library/Logs/DocSuri/rem-1/`                                                    | role별, 14일 rotation                |
| test profile         | `/Library/Application Support/DocSuri/rem-1-test/` + 별도 포트/DB role/CA         | production 기본값 상속 금지          |
| R1C endpoint         | `127.0.0.1:8101`(TLS)                                                             | 최초 설치 시 포트 충돌/접근 재검증   |
| 발신 허용            | chrony NTS source, advisory 스캐너 정책 범위, relay archive 경로. 그 외 발신 없음 | generator offline, scanner scoped    |

durable witness는 `/var/run`(재부팅 소실)에만 두지 않고 canonical 권위(Postgres/immutable file)로 보존한다.

## 4. OS service identity와 credential 경계

numeric UID는 설치 도구가 사용 여부를 검사해 할당한다. GUI 사용자 HOME/환경을 role에 복제하지 않는다. 동일 binary 공유와 실제 권한 공유를 구분한다.

| OS/DB role                            | 주입 컴포넌트           | 보유 권한                                              | 보유하지 않음                                 |
| ------------------------------------- | ----------------------- | ------------------------------------------------------ | --------------------------------------------- |
| `_docsuri_r1_reader`                  | LC-R1-01/08/09          | control/evidence readonly, 자기 TLS identity, safe OBS | target write/head 변경/signing key            |
| `_docsuri_r1_runner`                  | LC-R1-07                | host lane claim, child 관측, bounded dispatch          | target/signing ambient credential             |
| `_docsuri_r1_tool`                    | LC-R1-15/16             | staging read/write, allowed tool 실행                  | active head/sealed bytes/Keychain private key |
| `_docsuri_r1_bundle`                  | LC-R1-05                | helper-owned seal, expected-head 전환                  | unvalidated tool 실행                         |
| `_docsuri_r1_sign`                    | LC-R1-17                | 목적별 Ed25519 발행(Keychain private)                  | arbitrary bytes 서명                          |
| `_docsuri_r1_audit`                   | LC-R1-12                | audit insert/outbox enqueue                            | audit UPDATE/DELETE/DDL                       |
| `_docsuri_r1_journal`                 | LC-R1-06                | journal append/flush                                   | 과거 frame 수정                               |
| `_docsuri_r1_backup`                  | LC-R1-14                | quiesced capture/restore/verified pin 해제             | 무제한 mutation, old grant 활성화             |
| `r1_control_owner` (NOLOGIN)          | LC-R1-03                | `r1_control` schema owner/DDL                          | 실제 app login                                |
| `r1_control_writer`                   | coordinator/허용 helper | 검증된 transition/proof만 기록                         | raw unrestricted CRUD                         |
| `r1_control_reader`                   | R1C read                | read snapshot                                          | write                                         |
| `r1_target_helper_<name>`             | LC-R1-04                | 해당 target의 등록 SQL/ledger 함수만                   | 임의 DSN/SQL/namespace                        |
| `r1_audit_appender`/`r1_audit_reader` | LC-R1-12                | append/read                                            | modify/delete                                 |
| `r1_relay`                            | LC-R1-12 relay          | delivery cursor/selected outbox read                   | audit 수정                                    |

launcher는 `sudoers`의 고정 allowlisted 경로/인자로 전용 UID를 변경해 한정된 helper entry를 실행한다. arbitrary shell/임의 실행 파일/환경 전체 전달은 금지다. Keychain은 `security` CLI가 아닌 목적별 keychain 파일과 role ACL로 접근한다.

## 5. Postgres control realm

- target ledger는 기존 도메인 소유 DB/schema에 유지하고, REM-1 control/audit는 같은 cluster의 `r1_control`/`r1_audit` schema다(R1IF4=A). cross-DB 원자성을 주장하지 않는다.
- `r1_target_helper_<name>`은 `search_path`/권한이 제한된 command function만 실행하며 metadata 값은 parameter binding한다. ATOMIC_STEP 허용 등급은 FD/BR-R1-08에 따라 선별한다.
- TLS: `hostssl` 규칙과 role별 client certificate(내부 CA 발급)를 `pg_hba`에 명시하고 모든 연결은 `sslmode=verify-full`이다. plaintext/local trust 접속은 제거한다.
- 기존 application/migration runner 연결 변경은 shared-infrastructure.md의 소유자 조율 절차를 따른다. 현재 파일 권한/SSL 기본값을 "이미 준비됨"으로 간주하지 않는다.
- bootstrap은 제한된 운영 authority의 System 목적을 사용하며 U3가 없는 상황에서 brand-new mutation을 여는 fallback이 아니다.

## 6. TLS/네트워크 경계

- R1C는 `127.0.0.1:8101`에서 TLS 1.2+와 클라이언트 mTLS+현재 caller/object 권한 검사를 수행한다. 내부 CA는 `/Library/Application Support/DocSuri/rem-1/keys/ca/`에 issuer를 별도 보관하고 application role key와 분리한다.
- SAN/role mapping은 OS DB role과 서로 다른 목적으로 명시한다. 인증서 검증 해제/plaintext fallback/임의 proxy target은 금지다.
- helper-local IPC는 `chmod`가 아니라 kernel peer credential(`getsockopt(SO_PEERCRED)` 등)과 보호된 UDS 경로로 검증한다.
- 발신 정책: 시간(NTS 123)은 clock observer 전용, 스캐너는 allowlisted advisory/source host 전용, relay는 archive 검증 경로 전용. 그 외 tool/생성기는 offline이다. application을 외부로 호스팅하지 않고 R1 mutation endpoint를 공개하지 않는다.

## 7. Keychain/내부 CA와 cold boot

- 목적별 custom keychain(`keys/<purpose>.keychain-db`)을 root가 관리하고 role ACL로 접근을 제한한다. FileVault/login 이후 operator가 제한된 unlock/credential provider로 필요한 key만 준비한다.
- TLS/DB library가 PEM 재료를 요구할 때는 Keychain을 원천으로 0700 directory/0600 파일에 최소 수명으로 materialize하고 role 종료 시 정리한다. 이를 plaintext `.env` fallback으로 사용하지 않는다.
- record 서명은 Ed25519/JCS(PAT-R1-12), TLS identity/CA는 별도 목적이다. locked/missing/denied 상태는 실제 capability unavailable다.

## 8. Clock

- 별도 `_docsuri_r1_clock` UID로 고정·검증한 macOS chrony 빌드를 `-x` observer mode로 실행한다. system clock를 조정하지 않고 `time.cloudflare.com` NTS의 offset/frequency/상태를 관측한다.
- protected socket/자료로 age·uncertainty·drift·boot/resume context를 R1C의 ClockHealthProvider에 공급한다. age 30s/±1s를 증명할 수 없으면 fail closed다.

## 9. Backup 및 복구

- 대상: Postgres control/target ledger snapshot, immutable generations/evidence, journal, key 복구 재료. consistent cut과 detached verification manifest를 함께 기록한다.
- 매체: operator 소유 이동식 드라이브의 APFS 암호화 볼륨(R1IF2=A). 설치 시 `BACKUP_DRIVE`(별칭), 가용 용량, 일일 연결/회수 가능 시간을 operator fact로 기록한다. 이 값들은 execution preflight의 필수 입력이지 본 문서가 추정하는 값이 아니다.
- 절차: writer quiesce -> manifest 구성 -> local capture -> 암호화 archive -> drive 연결/복사 -> 성능 확인 전 detach -> 월간 isolated restore drill/coverage·hash 검증.
- FileVault: 현재 Off 관측은 NFR-R1-12 미충족 상태다. 배포 절차(deployment-architecture P0)에서 data volume 암호화를 켜고 preboot console unlock을 운영 절차에 포함한다.
- RPO 계산은 검증된 최근 cut 시각, RTO는 사고 인지부터 검증된 복구까지(운영자 unlock/host 준비 포함)다.

## 10. 관측과 host-down 감지

- R1C health(별도 2슬롯)/dependency readiness/subject gate를 분리 제공한다. 로그는 redacted structured JSON(타임스탬프/레벨/역할/correlation/안전한 reason)이며 일반 로그 14일, critical audit는 Postgres + 검증 아카이브(90일+)다.
- host-down은 기존 Healthchecks Hobbyist 유지(R1IF9=A): heartbeat/backup 두 check, 최소 redacted 상태만 전송. quota/계정과 실제 알림 수신을 검증한다. provider의 ping-log entry를 90일 감사 보존으로 쓰지 않는다.

## 11. Capacity/자원 집행 지점

| 표면                       | 값/집행                        | 출처                                 |
| -------------------------- | ------------------------------ | ------------------------------------ |
| R1C metadata/health 동시성 | 8/2                            | 프로세스 수와 무관하게 admission     |
| R1C RSS                    | 512 MiB(캐시 64 MiB 포함)      | launchd SoftResourceLimits/실측 확인 |
| R1R lane                   | host 전체 1개(자식 합산 2 GiB) | launcher가 lane claim을 검사         |
| 새 write disk              | `free >= 10 GiB + 2×추가 peak` | LC-R1-07/helper 진입 시 재검증       |
| HTTP 입력/response 등      | 256 KiB/1 MiB 등 §3.2 값       | framework 입구/envelope에서 강제     |

현재 disk 실측(97%·~15.5 GiB free, 2026-09-19)은 preflight 재검증 대상이며 FileVault/Colima 전환 순서(deployment-architecture P0~P1)에서 free space를 먼저 확보한다.

## 12. LC/PAT/NFR -> 물리 매핑

| LC          | 실제 배치                                              | PAT/인수           |
| ----------- | ------------------------------------------------------ | ------------------ |
| LC-R1-01    | `_docsuri_r1_reader` LaunchDaemon, 127.0.0.1:8101 mTLS | PAT-R1-01          |
| LC-R1-02    | pure Python module(C1), daemon/tool 공유               | PAT-R1-01/07/08    |
| LC-R1-03    | `r1_control` schema + psycopg pool                     | PAT-R1-01/03/09/11 |
| LC-R1-04    | `r1_target_helper_<name>` + session lock command       | PAT-R1-02/03       |
| LC-R1-05    | `_docsuri_r1_bundle` 범위 generations/head             | PAT-R1-04/10       |
| LC-R1-06    | `_docsuri_r1_journal` append journal                   | PAT-R1-05          |
| LC-R1-07    | `_docsuri_r1_runner` one-shot launcher 경유            | PAT-R1-06          |
| LC-R1-08/09 | reader 내 bounded LRU/breaker                          | PAT-R1-07          |
| LC-R1-10    | U3/운영 권한 source port + 내부 target guard           | PAT-R1-02/12       |
| LC-R1-11    | `_docsuri_r1_clock` chrony observer                    | PAT-R1-08          |
| LC-R1-12    | `r1_audit` schema + 60s relay + archive                | PAT-R1-09/10       |
| LC-R1-13    | local OBS + Healthchecks redacted ping                 | PAT-R1-12          |
| LC-R1-14    | `_docsuri_r1_backup` + 이동식 드라이브                 | PAT-R1-10          |
| LC-R1-15/16 | `_docsuri_r1_tool`, generator offline/scanner scoped   | PAT-R1-04/11       |
| LC-R1-17    | `_docsuri_r1_sign` + 목적 keychain                     | PAT-R1-02/12       |

## 13. 검증 증거 연결(Infrastructure 층)

| EV          | 물리 검증 지점(설치/rehearsal)                                     |
| ----------- | ------------------------------------------------------------------ |
| EV-R1-01    | frozen wheel/closure가 root 관리 release에서 실제 설치·boot        |
| EV-R1-02    | R1C 8슬롯 RSS/지연/입력 한도; 초과 부정 테스트                     |
| EV-R1-03    | 격리 Postgres의 fresh/복구, 실제 evidence/glossary 요청            |
| EV-R1-04    | generation/head 활성화와 네트워크 차단/실패 시 old-or-complete-new |
| EV-R1-05    | scanner datastore의 실제 coverage/current gate                     |
| EV-R1-06    | TLS 부정 인증서/키 잠김/감사 self-delete 부정/FileVault lock       |
| EV-R1-07    | 월간 이동식 드라이브 isolate restore와 새 incarnation 판정         |
| EV-R1-08/09 | PR/release/nightly profile과 후속 REM-G4/G5 연계                   |

## 14. 확장 준수 — Infrastructure 수준

| Rule          | 상태                  | 근거                                                                                                                |
| ------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------- |
| SECURITY-01   | Compliant             | FileVault 끔 관측을 켜는 절차(P0)와 별도 암호화 archive, loopback TLS, enum 잠금 실패                               |
| SECURITY-02   | N/A                   | 신규 외부 intermediary 없음. 기존 Cloudflare tunnel 접근 로그 계승                                                  |
| SECURITY-03   | Compliant             | role별 redacted structured JSON + correlation, 안전한 reason                                                        |
| SECURITY-04   | N/A                   | 새 HTML UI 없음                                                                                                     |
| SECURITY-05   | Compliant             | §11의 byte/count/depth는 제1계층에서 강제되고 sql은 binding                                                         |
| SECURITY-06   | Compliant             | §4의 OS/DB role 분리와 최소 권한, scoped sudoers                                                                    |
| SECURITY-07   | Compliant             | loopback/private socket, 발신 allowlist, 공개 generic mutation 부재                                                 |
| SECURITY-08   | Compliant             | role/mTLS는 service identity이고 현재 caller는 원 source authority guard                                            |
| SECURITY-09   | Compliant             | 기존 compose의 예제 credential/latest 태그 등 default 자격을 shared 전환으로 제거하고 최소 closure/FileVault를 적용 |
| SECURITY-10   | Compliant             | pinned digest 이미지/도구, scanner coverage, C-14 무비용 경계                                                       |
| SECURITY-11   | Compliant             | admission/한도/오용·불확정 실패의 bounded handling                                                                  |
| SECURITY-12   | Compliant             | U3/운영 MFA 현재 권한 계승, 키 잠김 unavailable, operator unlock                                                    |
| SECURITY-13   | Compliant             | 원본/증거 무결성과 GitHub review 경계, UID/ACL 고정                                                                 |
| SECURITY-14   | Compliant             | Postgres audit/90일+, application self-delete 거부, Healthchecks+local 알람                                         |
| SECURITY-15   | Compliant             | UNKNOWN/clock/캐시/breaker의 실패 닫힘과 안전한 재개                                                                |
| RESILIENCY-01 | Compliant             | R1C/R1R/OBS 각 의존/장애 격리 경계                                                                                  |
| RESILIENCY-02 | Compliant             | RPO 24h, RTO 4h, restart 60s를 매체/라이프사이클에 매핑                                                             |
| RESILIENCY-03 | Compliant             | git-flow/PR 및 단계별 운영자 승인 유지                                                                              |
| RESILIENCY-04 | Compliant             | deployment-architecture의 단계별 cutover/rollback 생성                                                              |
| RESILIENCY-05 | Compliant             | OBS/알람 wiring                                                                                                     |
| RESILIENCY-06 | Compliant             | /health는 무의존, readiness는 의존별 검증                                                                           |
| RESILIENCY-07 | Compliant             | disk/watermark/backlog/backup/key 상태 관측 (해당 리소스의 기존 운영자와 병행)                                      |
| RESILIENCY-08 | N/A                   | 승인된 single-Mac 단일 장애 도메인 예외. 별도 VM을 두지 않지만 Colima는 로컬 runtime/재호스팅이며 DR 대상이 아님    |
| RESILIENCY-09 | Compliant replacement | §11의 bounded capacity/backpressure. 수평 autoscale N/A                                                             |
| RESILIENCY-10 | Compliant             | per-role budget/timeout/breaker/캐시의 fail-closed                                                                  |
| RESILIENCY-11 | Compliant             | Backup&Restore 전략을 이동식 드라이브로 실체화                                                                      |
| RESILIENCY-12 | Compliant             | encrypted copy/coverage/hash와 월간 실제 restore                                                                    |
| RESILIENCY-13 | Compliant             | R1IF10 rehearsal과 runbook 내 실행/검증 절차                                                                        |
| RESILIENCY-14 | Compliant             | VAL-R1 시나리오 + 격리 macOS 인수 실행                                                                              |
| RESILIENCY-15 | Compliant             | heartbeat/IR/COE와 redacted 실패 신호                                                                               |
| PBT-\*        | stage-N/A             | Infrastructure 실행 단계는 속성 구현이 없다. 승인된 framework/profile와 PROP-R1/EV-R1을 Code로 이월                 |
