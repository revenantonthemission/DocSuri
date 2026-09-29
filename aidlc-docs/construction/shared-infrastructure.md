# Shared Infrastructure — 공유 리소스·소유자·변경 영향 (REM-1 Infrastructure)

**단계**: CONSTRUCTION / Infrastructure Design 공유 산출물
**생성**: 2026-09-22, REM-1 Infrastructure 계획(§7)에 따라 신규 생성
**역할**: 현 single-Mac 런타임의 공유 리소스에 대한 **canonical owner**, 최소 권한, 변경 선행/영향, 각 REM의 검증 책임을 조율하는 계약 문서. 기존 유닛(U1~U16) 산출물의 실제 소유권을 대치하지 않는다.

## 1. 원칙

1. 공유 리소스는 단일 canonical owner가 있고, 소비자는 owner가 문서화한 계약만 쓴다.
2. 공유 변경은 6단계로만 진행한다: additive 준비 -> 격리 검증 -> 검증된 backup/rollback -> 수동 제한 전환 -> 실제 health/인수. 새 REM-1 writer와 legacy privileged writer를 같은 scope에 동시 활성화하지 않는다.
3. C-14: 추가 비용 0원. application serving은 계속 Mac mini이며 paid/managed로 이동하지 않는다.
4. 역할 이름/문서 나눔이 실제 UID/DB role/파일 owner 분리를 대신할 수 없다.

## 2. 리소스 인벤토리

| 리소스                        | canonical owner                                     | REM-1 사용                                        | 최소 권한 경계                                                    | 현재 확인된 전환 대상                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| container runtime(data plane) | 운영(현재 OrbStack compose 정의)                    | 소비(의존), 재호스팅 주도                         | data plane은 loopback 한정                                        | **R1IF1=B: Colima/Lima로 전환**, 미검증 VM 볼륨 삭제 금지 |
| Postgres `docsuri` cluster/DB | U3/운영(백엔드 startup migration)                   | `r1_control`/`r1_audit` schema(R1IF4=A)           | NOLOGIN role, `hostssl`+client cert+verify-full, command function | TLS/role 강제 전환은 owner와 단계 검증                    |
| Redis                         | U3(세션), U7(캐시)                                  | 없음(직접 소비 없음)                              | loopback, fail-closed                                             | —                                                         |
| OpenSearch 코퍼스             | U1 writer 소유, U2 reader                           | evidence 소비                                     | reader/별칭 readonly                                              | Colima 재호스팅 시 snapshot 복원 검증                     |
| MinIO(S3 호환)                | U1(전문/자산/모델), U2/U7/U11/U12 소비              | backup/스토어 소비는 기존 경로                    | loopback, private bucket                                          | host bind mount 유지                                      |
| ElasticMQ(SQS 호환)           | 배포/워커 공통                                      | 관측/health만                                     | loopback                                                          | 무볼륨 재구성 가능; 전환 전 drain 확인                    |
| 클라우드플레어 터널/ingress   | 운영                                                | R1C는 공개하지 않음                               | R1 mutation/공개 경로 없음                                        | 유지                                                      |
| time source                   | `_docsuri_r1_clock`(R1IF7=A)                        | clock health 공급                                 | NTS outbound only                                                 | chrony observer 신설                                      |
| monitoring(Healthchecks)      | 운영 heartbeat 스크립트                             | redacted 상태 공유                                | capability URL 보호                                               | Hobbyist 한도 확인                                        |
| off-host backup               | 운영 backup 스크립트 + **이동식 드라이브(R1IF2=A)** | REM-1 backup set                                  | 별도 암호화 archive                                               | drive 별칭/용량은 실행 시 operator fact                   |
| `backend/docker-compose.yml`  | 운영/app 배포                                       | 정의 변경에 owner 검토 필요                       | pinned digest, secret 분리                                        | 이미지 pin/예제 자격 교정                                 |
| 백엔드 `.env`/비밀            | U3/운영(존재)                                       | REM-1은 `.env`를 소비하지 않고 목적 keychain 사용 | `.env` 롤백/공유 금지                                             | —                                                         |

## 3. 변경 선행/영향 규칙

- target 도메인(PG ledger), 코퍼스(OpenSearch), 사용자 세션(Redis), 작업 큐(ElasticMQ)의 스키마/데이터 소유 변경은 각 owner의 승인된 변경 절차를 따른다. REM-1은 이들에 대해 read-only 또는 등록된 helper 계약만 쓴다.
- 같은 리소스를 바꾸는 두 변경은 직렬화한다. REM-1 설치 중 기존 owner의 스키마 전환(예: U8, U13 등)과 충돌하면 6단계 절차에 따라 선행 순서를 정한다.
- 검증 gate(REM-1 G1)가 shared resource를 필요로 할 때는 리소스가 실제 준비된 순간 기준으로 판정하고, 없는 조건을 boolean 설정으로 통과시키지 않는다.

## 4. REM-1 배포 시 숨기지 않을 Shared drift

| 관측                                              | 소유 논의                                                       | REM-1에서 열어둘 것                            |
| ------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------- |
| OrbStack Free 자격 미확정                         | 컨테이너 전환은 R1IF1=B로 확정; C-5 container manager 부분 개정 | 전환/롤백 절차와 P1 검증                       |
| compose 이미지 `latest`/예제 비밀값               | shared image/pin rule로 상향                                    | 원 구성 소유자 일정으로 조정하고 확인          |
| Postgres 보안                                     | `hostssl`+인증서로 강제하되 백엔드 연결 영향 확인 필요          | shared를 덮어쓰지 않고 compat 계획             |
| existing startup migration/CLI migrator 목록 차이 | REM-3 또는 background 계열에서 소유                             | REM-1은 local bootstrap 증거 개념에만 영향     |
| 재색인 등 무거운 파이프라인                       | U1 소유의 corpus/파이프라인은 as-is 유지                        | REM-1은 해당 여부를 owner 대신 확정하지 않는다 |

## 5. REM 간 검증 책임

| REM                               | 공유 리소스 관련 검증 책임                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| REM-1(본 unit)                    | Colima 재호스팅 검증, shared-infra 변경 순서/롤백, UID/CA/TLS/clock/backup 설치 절차 |
| REM-2(private content·generation) | private 문서/생성 격리와 성능·시간 예산을 소유 도메인 계약으로 검증                  |
| REM-3(lifecycle·edge 신뢰)        | 계정/에지 신뢰와 큐·워커 재연결을 소유 도메인 계약으로 검증                          |
| REM-4(corpus·search)              | 코퍼스/검색 품질과 관련 U1/U2 소유 사항; fixture/운영 데이터 분리                    |
| 기존 U1~U16                       | 각 소유 리소스의 계약·마이그레이션과 실제 데이터 인수                                |

## 6. 완료 정의

이 문서의 항목이 완료됐다는 것은 각 전환 단계의 backup/검증/health 인수가 해당 owner와 함께 기록된 경우만이다. 비용 0원·off-host 자원·무료 서비스 한도가 확인된 사실로 공표되지 않으면 준비 완료로 표시하지 않는다.
