# 2026-09-18 검증 결함 교정 요구사항

> **2026-09-19 공개 job 계약 승인**: §1~9는 기존 승인 요구사항이다. DSRQ4=C 및 DSRQF1=A/DSRQF2=A에 따른 사용자 흐름 변경을 §10에 추가했고 RJR1=A로 승인됐다. 명시된 이관 경로의 응답 계약은 §10이 우선한다.

## 1. 의도 분석

| 항목 | 결정 |
|---|---|
| 사용자 요청 | 이전 세션에서 확인한 오류 수정 |
| 요청 유형 | 기존 시스템의 system-wide bug/security/data/runtime remediation |
| 범위 | `project-verification-2026-09-18.md`의 F01~F13 전부 |
| 복잡도/위험 | Comprehensive / High - 사용자 격리, 데이터 무결성, 계정 파기, dependency, live data 포함 |
| live 변경 | 격리 검증 통과 후 backup/rollback을 갖춘 안전한 repair 허용 |
| 별도 승인 | full corpus rebuild는 실행 직전 별도 명시 승인 필수 |
| runtime 기준 | single Mac production: launchd + OrbStack + Cloudflare Tunnel + Ollama |
| 확장 | Security Full, PBT Full, Resiliency single-host custom profile |

본 문서는 신규 제품 기능을 추가하지 않는다. 기존 FR/NFR/SEC/RES/QT의 누락된 인수를 F01~F13에 대해 명시하고, AWS 기반 런타임 가정을 현재 production에 맞게 대체한다. 기존 ID와 충돌할 때 `requirements.md`의 2026-09-18 개정 조항과 본 문서가 우선한다.

## 2. Single-Mac Production 기준선

- 공개 경로: Cloudflare edge/tunnel -> Next.js BFF(`127.0.0.1:3000`) -> FastAPI(`127.0.0.1:8000`).
- data plane: OrbStack의 Postgres, Redis, OpenSearch, MinIO, ElasticMQ. 모든 host port는 loopback 전용이다.
- inference: local Ollama `bge-m3` embedding 및 `qwen3:8b` generation.
- process: launchd가 API, web, ingestion/summarization/evidence/novelty worker, purge, backup, heartbeat, tunnel을 관리한다.
- availability: 한 host/디스크/로그인 세션의 단일 장애 도메인을 수용하며 multi-zone과 자동 failover를 요구하지 않는다.
- recovery: 일일 off-host backup과 재설치/restore runbook을 사용한다. owner-private object data도 backup 대상이다.
- capacity: 수평 확장 대신 bounded worker concurrency, queue backpressure, disk/model saturation gate를 사용한다.
- security: single-host 예외는 owner authorization, secret handling, dependency hygiene, encryption, audit/alerting을 면제하지 않는다.

## 3. F01-F13 교정 인수

| Finding | 기존 요구사항 | 필수 인수 기준 |
|---|---|---|
| F01 private userdoc 읽기 | FR-18/38, SEC-8 | public corpus DocModel route는 `userdoc:`를 거부한다. private document 전용 read는 authenticated owner를 검증하며 non-owner에게 존재 여부를 노출하지 않는다. source selection과 derived artifact read도 같은 경계를 사용한다. |
| F02 공유 번역 cache 오염 | FR-5/13, QT-5, SEC-13 | 공유 artifact source는 server-verified metadata/DocModel만 사용한다. cache key는 canonical source identity/content version에 결속한다. client-provided source가 다른 사용자 또는 canonical paper 결과를 결정하지 못한다. |
| F03 fixture corpus/범위 | FR-2/5/6, QT-1/9, SEC-9 | production index에 test fixture fingerprint가 0개다. paper ID/title/author/source URL을 원출처와 검증한다. 최근 AI/ML 1년 범위 완성도를 측정하고 미충족이면 readiness/운영 상태에 명시한다. full rebuild는 별도 실행 승인 전 금지한다. |
| F04 owner purge 누락 | FR-28/38, SEC-8 | 중앙 purge registry가 모든 owner-scoped SQL table과 private object prefix를 포함한다. 실제 DB/object integration에서 대상 owner 데이터는 0, 다른 owner 데이터는 불변이다. 재실행은 멱등이다. |
| F05 generation timeout | FR-12/13, NFR-P2/R2, RESILIENCY-10 | browser, BFF, API, model, worker 시간 예산이 정렬된다. 동기 예산을 넘는 정상 생성은 job/pending/poll로 전환되고 유효한 12초 이상 응답이 임의 10초 504로 잘리지 않는다. 실제 hang은 bounded timeout으로 종료한다. |
| F06 dependency 취약점 | SEC-10 | production dependency audit에서 known critical/high finding이 0이거나 source-unreachable 예외가 근거·만료일과 함께 승인된다. patched lockfile, pinned container image, SBOM과 CI audit gate를 제공한다. |
| F07 private asset serving | FR-17/18, SEC-8/9 | browser asset URL은 authenticated same-origin endpoint다. backend가 owner/license/object authorization을 적용하고 MinIO 내부 endpoint/key를 노출하지 않는다. CSP가 해당 same-origin 렌더를 허용한다. |
| F08 migration registry 누락 | FR-14/36, NFR-M1, RESILIENCY-04 | startup과 CLI가 한 ordered migration registry를 사용한다. 빈 Postgres에서 모든 mounted module table을 생성하고 evidence 및 glossary 실제 요청이 성공한다. migration은 원장/멱등/실패 rollback을 갖는다. |
| F09 digest link/unsubscribe | FR-47, SEC-5/8 | token unsubscribe route는 명시적 public endpoint이며 token 자체를 검증한다. email paper link는 실제 `/paper/{id}` route를 사용한다. valid/invalid/expired token과 익명 접근을 테스트한다. |
| F10 client rate-limit identity | SEC-2/11 | Cloudflare/BFF 신뢰 경계에서 검증한 client identity만 FastAPI에 전달한다. 임의 client header spoofing은 거부하고 서로 다른 client는 독립 bucket, 같은 client는 동일 bucket을 사용한다. |
| F11 empty degradation loss | FR-11, NFR-R1/R2, SEC-15 | 결과가 0개여도 known degradation mode와 provenance를 보존한다. frontend가 normal no-match와 lexical/model failure를 구분한다. |
| F12 out-of-scope no-match | FR-5/11, QT-1 | 검증된 corpus와 in-scope/out-of-scope 평가셋으로 relevance floor를 정한다. 명백한 범위 밖 질의는 paper list가 아니라 abstain/no-match를 반환한다. false-abstain/false-pass 결과를 기록한다. |
| F13 frontend type guard fail-open | NFR-M1, SEC-13 | 모든 local schema `$ref`를 network 없이 해소한다. 대상 schema 하나라도 생성 실패하면 non-zero exit다. generated/curated type drift 검사는 실제 build-consumed contract를 모두 포함한다. |

## 4. 횡단 품질 요구사항

- 각 finding은 먼저 실패하는 영구 regression으로 재현한 뒤 수정한다.
- F01/F02/F04/F10은 example regression과 domain generator 기반 authorization/integrity property test를 함께 둔다.
- schema/DTO, cache identity, purge registry, migration ordering, state transition에는 PBT-01~10 중 적용 가능한 속성을 문서화하고 Full mode로 집행한다.
- Hypothesis/fast-check shrinking을 유지하고 CI seed를 출력하거나 고정한다.
- 격리된 Postgres/Redis/OpenSearch/MinIO/ElasticMQ를 사용한 integration test와 current browser BFF route test를 포함한다.
- live repair 전 백업 성공, restore 가능성, rollback command, 변경 대상 count를 기록한다.
- live repair 후 health뿐 아니라 owner isolation, corpus fixture count, email route, asset route, migration ledger와 search no-match를 확인한다.

## 5. 실행 경계

- 허용: source/test/dependency/lock/container pin 변경, migration 추가, repair/dry-run tooling, backup 후 안전한 configuration/data cleanup.
- 금지: 별도 승인 없는 full corpus rebuild, backup 없는 destructive data mutation, unrelated feature 추가, secret 출력 또는 실제 사용자 private content probe.
- fixture 제거는 source fingerprint와 dry-run count를 먼저 제시하고 backup 후 실행한다.
- corpus 범위 복구가 full rebuild를 요구하면 예상 paper/chunk count, disk peak, wall time, rollback generation을 제시하고 별도 승인을 기다린다.

## 6. 확장 준수 기준

### Security Full

SECURITY-01~15를 모두 적용한다. F01/F04는 SECURITY-08, F02/F13은 SECURITY-13, F03은 SECURITY-09, F06은 SECURITY-10, F10은 SECURITY-11, F11은 SECURITY-15의 차단 finding이다. 구현 완료는 해당 차단 finding과 기존 audit의 관련 증거가 해소될 때만 선언한다.

### Resiliency Custom

- `RESILIENCY-08`의 multi-zone/multi-region fault isolation은 single-Mac production 결정으로 명시 면제한다.
- `RESILIENCY-09`의 horizontal auto-scaling은 N/A이며 bounded concurrency/backpressure/capacity monitoring으로 적용한다.
- backup/restore, health depth, monitoring, dependency timeout, rollback, incident correction과 failure testing은 계속 차단성이다.

### PBT Full

PBT-01~10을 모두 차단성으로 적용한다. 단, 속성이 존재하지 않는 UI rendering이나 external I/O glue는 N/A 근거를 남기고 example/integration test로 검증한다.

## 7. Open Questions

없음. full corpus rebuild는 요구사항 미확정이 아니라 별도의 실행 승인 게이트다.

## 8. 추적성

| 결정 | 출처 |
|---|---|
| F01~F13 전부 | remediation 질문 Q1=A |
| safe live repair + full rebuild 별도 승인 | remediation 질문 Q2=C |
| single-Mac production 전면 재기준 | remediation 질문 Q3=B, clarification=A |
| Security Full | remediation 질문 Q4=A |
| Resiliency custom single-host profile | remediation 질문 Q5=A + clarification=A |
| PBT Full | remediation 질문 Q6=A |

## 9. Requirements Stage 확장 준수 요약

이 표는 요구사항 산출물의 규칙 반영 여부다. 현재 runtime 결함의 해소 여부는 Code Generation과 Build and Test에서 다시 판정한다.

### Security

| 규칙 | 상태 | Requirements 근거 |
|---|---|---|
| SECURITY-01 | Compliant | SEC-1 유지; local disk/backup/storage TLS 교정 대상 명시 |
| SECURITY-02 | Compliant | SEC-2를 Cloudflare/BFF access logging과 client identity로 재기준 |
| SECURITY-03 | Compliant | SEC-3, NFR-O1 구조화 로그 요구 |
| SECURITY-04 | Compliant | SEC-4 보안 header/CSP 유지 |
| SECURITY-05 | Compliant | SEC-5와 F09/F13 입력·계약 검증 |
| SECURITY-06 | Compliant | SEC-6을 Mac account/files/container/provider 권한으로 재기준 |
| SECURITY-07 | Compliant | SEC-7 loopback data plane + outbound-only tunnel |
| SECURITY-08 | Compliant | F01/F04 owner authorization·파기 인수 |
| SECURITY-09 | Compliant | F03/F07 production hardening 인수 |
| SECURITY-10 | Compliant | F06 lock/audit/SBOM/image pin 인수 |
| SECURITY-11 | Compliant | F10 trusted client rate-limit identity 인수 |
| SECURITY-12 | Compliant | 기존 SEC-12 유지; 본 교정의 직접 변경 없음 |
| SECURITY-13 | Compliant | F02/F13 source/cache/contract integrity 인수 |
| SECURITY-14 | Compliant | 기존 SEC-14 유지; local retention/alerting 구현 검증 대상 |
| SECURITY-15 | Compliant | F11 fail-safe degradation provenance 인수 |

### Resiliency

| 규칙 | 상태 | Requirements 근거 |
|---|---|---|
| RESILIENCY-01 | Compliant | RES-1과 single-host dependency baseline |
| RESILIENCY-02 | Compliant | RES-2 local backup/restore RPO/RTO |
| RESILIENCY-03 | Compliant | 기존 GitHub review + git-flow 변경 관리 유지 |
| RESILIENCY-04 | Compliant | RES-4 in-place deploy + artifact/schema rollback |
| RESILIENCY-05 | Compliant | RES-5 local logs/metrics/heartbeat |
| RESILIENCY-06 | Compliant | RES-6 deep readiness와 synthetic probe |
| RESILIENCY-07 | Compliant | RES-7 backup/disk/queue/model 경보 |
| RESILIENCY-08 | N/A | 사용자 승인 single-Mac production fault-isolation 예외 |
| RESILIENCY-09 | Compliant | horizontal scaling N/A; bounded concurrency/backpressure 적용 |
| RESILIENCY-10 | Compliant | F05 timeout alignment와 RES-9 dependency isolation |
| RESILIENCY-11 | Compliant | RES-10 local backup-and-restore 전략 |
| RESILIENCY-12 | Compliant | RES-2에 Postgres/private MinIO off-host backup 포함 |
| RESILIENCY-13 | Compliant | RES-10 reinstall/restore/traffic-resume runbook 요구 |
| RESILIENCY-14 | Compliant | RES-12 restore/failure/rollback 정기 검증 |
| RESILIENCY-15 | Compliant | 기존 RES-11 COE + 본 F01~F13 교정 cycle |

### Property-Based Testing

| 규칙 | 상태 | Requirements 근거 |
|---|---|---|
| PBT-01 | Compliant | QT-4와 횡단 품질에서 속성 식별 요구 |
| PBT-02 | Compliant | DTO/schema/cache identity roundtrip 요구 |
| PBT-03 | Compliant | authorization, purge, corpus, degradation invariant 요구 |
| PBT-04 | Compliant | purge/retry/migration idempotency 요구 |
| PBT-05 | Compliant | corpus source metadata 및 migration oracle 요구 |
| PBT-06 | Compliant | job/migration/state sequence 검증 요구 |
| PBT-07 | Compliant | domain generator 요구 |
| PBT-08 | Compliant | shrinking + fixed/logged CI seed 요구 |
| PBT-09 | Compliant | Python Hypothesis + TypeScript fast-check 유지 |
| PBT-10 | Compliant | 모든 finding에 example regression 병행 요구 |

## 10. 2026-09-19 REM 공개 job 계약 개정

**상태**: Requirements 승인 완료 - `requirement-review-questions-remediation-public-jobs-2026-09-19.md` RJR1=A (2026-09-19)
**요구사항 ID**: FR-52, NFR-R4, QT-12, C-13 (`requirements.md`에 승인본 등재)

### 10.1 의도와 입력 검증

- 사용자 결정 `DSRQF1: A, DSRQF2: A`는 DSRQ4=C를 유지하고 공개 job API 및 frontend의 접수/대기/완료/실패 처리를 포함한다.
- 네 REM services, host-native launchd 배포, 기존 domain의 business/schema authority, 물리 store 공유와 단일 writer, delegated identity, gateway 경유 versioned route 전환은 앞선 결정이다.
- 범위는 Multiple Components / High / Comprehensive다. 신규 사업 기능을 추가하는 대신 기존 기능의 호출·대기·결과 수신 방식을 바꾼다.
- 기존 reverse-engineering `code-baseline-2026-06.md`의 domain/DTO inventory와 2026-09-18 검증 보고서, `ops/server/README.md`의 single-Mac 기준을 사용했다. 구 AWS 배포 기록은 현재 runtime 권위로 사용하지 않는다.
- 기능/사용자 시나리오/비기능/사업 목표/통합 경계/품질 요구를 기존 FR 및 두 명확화 답변과 대조했다. 추가 제품 결정을 요구하는 미해결 질문은 없으며, endpoint/schema/수치/상태기계 상세는 각 후속 설계 단계의 산출물이다.
- Security Full, Resiliency custom single-Mac, PBT Full은 `aidlc-state.md`의 활성 결정을 계승한다.

### 10.2 적용 경계

| 영역 | 공개 job 계약의 범위 | 보존할 도메인 인수 |
|---|---|---|
| REM-2 content/generation | REM으로 이관되는 요약/번역 생성·재조회, DocModel read, owner context 내 private read, asset 준비/metadata 요청 및 명시적 status 조회 | F01 public/private namespace, F02 canonical source/cache, F05 bounded generation, F07 owner/license/object 확인 |
| REM-3 lifecycle/digest | REM으로 이관되는 기존 lifecycle 업무 호출과 status, token-authorized unsubscribe 업무 처리. purge 실행/운영 조회는 기존 operator 권한 경계 안 | FR-28 비활성화/세션 무효화와 유예 파기, F04 전체 owner purge, F09 익명 token 검증과 즉시 발송 차단 |
| REM-3 edge trust | ingress identity 검증/rate-limit은 접수 이전 직접 집행. policy/version 관리만 service 책임으로 설계 | F10 trusted identity; queue outage로 인증/인가/rate-limit을 우회하지 않음 |
| REM-4 corpus/search | audit/calibration/repair는 operator/background 작업. U2/U5의 검색 응답·degraded-empty·relevance 집행은 기존 사용자 경계에 유지 | F03 corpus 진실성, F11 degradation, F12 no-match; 일반 검색에 신규 job 단계 추가를 자동 승인하지 않음 |
| REM-1 platform | evidence/readiness는 read-only 직접 관측, mutation은 기존 결정의 명시적 CLI/one-shot operation | F06 dependency, F08 registry, F13 binding; 일반 사용자 job API에 관리 작업 노출 금지 |
| 공통 전달/관측 | 접수 확인, event/subscription/재연결, 완료 결과/asset bytes, health/readiness는 새 업무 job 없는 직접 경로 | caller authorization, bounded I/O, queue 장애의 명시적 관측 |

여기서 **공개 job API**는 BFF/gateway를 통해 client가 소비하는 계약을 뜻하며, 인증 없는 공용 endpoint를 뜻하지 않는다. endpoint별 method/path/version과 producer/consumer 매핑은 Application Design에서 이 범위에 맞게 확정한다. 업무 권한·수명주기가 확장되는 별도 기능은 추가하지 않는다.

### 10.3 FR-52 기능 인수

| ID | 검증 가능한 인수 기준 | Trace |
|---|---|---|
| RJ-AC01 | 허용된 요청의 operation과 발행 의도가 durable하게 저장된 후에만 job 접수 확인을 반환한다. 접수 확인은 업무 성공과 구분하며, durable 접수 실패를 accepted/pending으로 표현하지 않는다. | FR-52, NFR-R4, F05 |
| RJ-AC02 | 이관된 업무 read와 명시적 status 요청은 job으로 처리한다. status job의 결과는 대상 job과 관측 시점을 식별하는 완료 결과로 전달하며, 이를 읽기 위한 status job을 재귀 생성하지 않는다. | DSRQ4=C, DSRQF2=A |
| RJ-AC03 | frontend는 요청 중/접수됨/대기/처리/완료/실패와 도메인의 abstain/degraded/no-match를 구분한다. 접수 확인만으로 결과를 성공 표시하지 않고 terminal failure를 무기한 pending으로 숨기지 않는다. 기존 화면에서 비기술적 메시지와 적절한 재시도를 제공한다. | FR-11/52, NFR-R1, F11 |
| RJ-AC04 | event/subscription과 재연결은 원 job의 알려진 결과/진행을 인가된 caller에게 전달하며 새 업무 job을 만들지 않는다. 중복/역순 event는 terminal 상태를 되돌리지 않는다. 접속이 끊긴 동안의 완료를 재연결 시 알 수 있고, 보존 기간을 넘긴 결과는 명시적 만료/재요청 상태로 처리한다. | NFR-R4, QT-12, DSRQF2=A |
| RJ-AC05 | job 제출·실행·명시적 조회·구독/재연결·완료 결과 전달 모두 현재 caller/object 권한을 검증한다. job ID만으로 접근을 허용하지 않는다. non-owner와 존재하지 않는 private job/resource는 구분 가능한 정보를 노출하지 않는다. queue 대기가 만료/철회된 권한을 연장하지 않는다. | F01, SEC-8/12/15, DSRQ5=A |
| RJ-AC06 | 동일 논리 제출의 재시도와 queue redelivery는 중복 업무 효과를 만들지 않는다. canonical 공개 artifact를 재사용하더라도 다른 caller의 job metadata/권한을 공유하지 않는다. 명시적 새 read/status 요청과 이전 제출의 재시도는 구분한다. | F02/F04/F05, NFR-R4, QT-12 |
| RJ-AC07 | cache-backed read도 job 계약을 따른다. 기존 canonical source/version에 맞는 결과를 재사용하고 cache hit 때문에 model을 다시 실행하지 않는다. client 제공 본문으로 공유 결과나 job identity를 오염시킬 수 없다. | F02/F05, FR-12/13, NFR-P2 |
| RJ-AC08 | 준비된 DocModel/결과는 인가된 직접 전달 경로로, 준비된 자산 bytes는 인증된 same-origin URL로 제공한다. 전달 요청은 새 업무 job을 만들지 않으며 현재 owner/license/object 권한을 다시 검사한다. 내부 MinIO URL/key 및 private namespace를 노출하지 않는다. | F01/F07, FR-17/18 |
| RJ-AC09 | 계정 삭제 시 owner-scoped job 입력/결과/event/구독 권한도 purge 대상에 포함한다. 대기/실행 중 작업이 삭제 후 private 산출물을 다시 만들거나 전달하지 못해야 하며 다른 owner의 작업은 불변이다. 보존할 운영 감사 증거는 private payload와 재식별 가능한 owner 참조를 제거한 정책을 따른다. | F04, FR-28/38, SEC-8/14 |
| RJ-AC10 | anonymous unsubscribe는 해당 token을 검증하는 명시적 public 경로를 유지한다. job 관측 권한은 그 해지 요청의 일반화된 결과에만 한정하고 다른 job/계정 정보로 확장하지 않는다. valid 요청의 durable 수락 시점부터 추가 발송을 차단하며 후속 처리 지연이 차단을 해제하지 않는다. invalid/expired token은 거부하고 완료와 접수를 구분한다. | F09, FR-47/48, SEC-5/8 |
| RJ-AC11 | rate-limit/인가 선행 집행, FR-28의 즉시 계정 비활성화와 세션 무효화는 queue 처리 대기로 지연시키지 않는다. 후속 purge 등 비동기 작업의 접수는 원래의 수명주기 보호를 만족해야 한다. | F04/F10, FR-28, C-13 |
| RJ-AC12 | queue 중단/유실, worker 재시작, 부분 배포, subscription 단절을 주입해 accepted 작업의 복구 또는 명시적 terminal failure, 인가된 결과 재전달, 중복 효과 부재를 검증한다. health/readiness와 REM-1 evidence는 새 job 없이 응답하며 deep readiness는 실제 의존 장애를 반영한다. | NFR-R4, RES-6/9/12, QT-12 |

### 10.4 비기능 및 기존 계약과의 조정

1. **F05/FR-13 응답 모델**: 이관된 versioned route의 repeat-request polling은 durable job + queued 명시적 status query + event/subscription 전달로 대체한다. 정상 UI 추적은 원 job의 event를 소비하며 status 조회 job을 자동으로 연쇄 생성하지 않는다. 미전환 route의 기존 pending/poll 계약은 호환 기간 동안 보존한다.
2. **성능 측정**: 접수 latency, queue 대기, 실행 latency, 결과 전달 latency와 사용자 종단 완료 시간을 구분한다. NFR-P1의 검색 목표를 job 접수 시간으로 대체하지 않는다. NFR-P2의 cache hit는 빠른 cache-backed job 완료/전달로 다루며, 첫 생성의 관측은 event와 검증된 결과 수신으로 제공한다. 새 요구사항은 token-by-token 생성 스트리밍을 보장하지 않는다.
3. **Timeout/capacity**: 접수/실행/status/event/asset 전달은 각기 bounded I/O와 실패 상태를 갖는다. 상태 조회·event 구독의 폭증이 모델 작업과 health를 고갈시키지 않도록 상한과 backpressure를 적용한다. 구체 시간/동시성/retention 수치는 per-service NFR Requirements/Design에서 확정하고 부하/장애 시험으로 검증한다.
4. **Durability/retention**: durable operation/outbox가 accepted 작업의 진실원천이며 ElasticMQ는 전달 수단이다. 재시작 후 미완료 작업을 재조정하고 terminal 결과/전달 이력을 정책 기간 동안 복구할 수 있어야 한다. operation/event/result/manifest 데이터는 기존 RES-2의 암호화 backup/restore 대상에 포함하고 owner purge와 보존 종료를 검증한다.
5. **Compatibility/cutover**: DSRQ6=A의 gateway 경유 versioned route와 수동 전환을 사용한다. 신구 client/service 조합 및 진행 중 job을 처리할 수 있어야 하며 rollback이 job을 유실하거나 중복 실행하지 않아야 한다. 호환되지 않는 버전은 명시적 실패/보류로 처리한다. 인증·무결성 경로의 자동 fail-open 및 이중 업무 쓰기는 허용하지 않는다.
6. **관측성**: request/job/event correlation과 다중 service trace를 유지한다. 접수/실행/terminal/권한 거부/구독 실패 지표 및 queue/backlog/디스크/model saturation을 기존 RES-5/7/11 경보·COE 경로에 연결한다. 로그에 토큰, private 본문, 내부 저장 key를 기록하지 않는다.
7. **모바일 UX**: 기존 NFR-U1/U2/X1을 따라 대기/완료/실패/재연결을 가독성 있는 상태로 표현한다. event 단절을 업무 실패로 오인하지 않고, 권한/결과 만료 시 계속 기다리는 대신 재인증 또는 재요청 가능 여부를 안내한다.
8. **범위 유지**: 일반 검색, 로그인/OIDC, 라이브러리 및 전체 agent API를 일괄 job화하지 않는다. 기존 product/domain이 business rule/schema를 소유하고 REM이 운영 조정을 담당한다. full rebuild/reparse/reembed/alias cutover는 별도 승인 경계다.

### 10.5 시나리오 및 추적성

| 시나리오 | 인수 | 기존 story 영향 후보 |
|---|---|---|
| 캐시가 있는 요약/번역도 job으로 접수한 뒤 기존 산출물을 빠르게 수신 | RJ-AC01/03/07 | US-S1/2/5 |
| private 문서/자산 열람 중 다른 owner가 job/result 참조를 재사용 | RJ-AC05/08 | US-EV4/7, US-AG5 |
| 접속 단절 동안 완료된 작업의 결과를 재연결로 수신 | RJ-AC02/03/04 | US-S5, 영향받는 US-NV7/US-AG4 |
| 대기/실행 중 계정 삭제와 권한 만료/철회 | RJ-AC05/09/11 | US-A6, US-EV8 |
| 익명 이메일 수신 해지 및 처리 대기 중 추가 발송 시도 | RJ-AC10 | US-TN2 |
| queue outage/재전달/부분 배포에서 중복 효과와 상태 오판 방지 | RJ-AC06/12 | US-R2/4/5 |

이 표는 후속 User Stories 단계의 영향 분석 입력이다. 해당 story 개정/승인을 완료했다는 의미가 아니며, 새 story ID와 Given/When/Then은 그 단계에서 확정한다.

### 10.6 확장 준수 - Requirements 산출물 수준

§9의 기존 F01~F13 요구를 유지하면서 이번 공개 job 계약에 대한 delta를 검토했다. 아래 Compliant는 요구사항에 제약이 반영됐다는 판정이다.

| Security 규칙 | 상태 | 이번 개정의 요구사항 근거 |
|---|---|---|
| SECURITY-01 | Compliant | SEC-1 및 §10.4.4의 operation/event/result 저장·backup 암호화, TLS 요구 계승 |
| SECURITY-02 | Compliant | 공개 BFF/gateway access log와 §10.4.6 correlation 유지 |
| SECURITY-03 | Compliant | 모든 service/worker/subscription의 구조화 로그와 민감정보 제외 |
| SECURITY-04 | Compliant | SEC-4/CSP와 RJ-AC08 same-origin 결과·자산 전달 |
| SECURITY-05 | Compliant | SEC-5, 허용 업무/입력/job 참조 검증과 RJ-AC10 token 검증 |
| SECURITY-06 | Compliant | DSRQ3=A의 단일 writer, service별 store/job 권한 분리 |
| SECURITY-07 | Compliant | BFF/gateway만 공개; REM/data plane은 private listener |
| SECURITY-08 | Compliant | RJ-AC05/08/10 접수·실행·event·result 권한 및 익명 token 예외 한정 |
| SECURITY-09 | Compliant | 일반화된 상태/오류, 내부 key/endpoint 비노출, public storage 금지 계승 |
| SECURITY-10 | Compliant | F06 audit/lock/pin/SBOM에 새 job/event 의존성 포함 |
| SECURITY-11 | Compliant | RJ-AC11 접수 전 rate-limit 및 §10.4.3 status/subscription 남용 제한 |
| SECURITY-12 | Compliant | RJ-AC05 현재 session/delegated credential 만료·철회, 관리자 인증 계승 |
| SECURITY-13 | Compliant | F02/F13, RJ-AC01/06의 durable 접수·멱등성, versioned 계약·감사 |
| SECURITY-14 | Compliant | SEC-14 append-only 감사 및 §10.4.6 인가·실패 경보 |
| SECURITY-15 | Compliant | 접수/완료 구분, terminal failure, 권한 실패 closed, bounded 직접 전달 |

| Resiliency 규칙 | 상태 | 이번 개정의 요구사항 근거 |
|---|---|---|
| RESILIENCY-01 | Compliant | §10.2 업무/전달/운영 경계 및 서비스별 중요도 후속 설계 요구 |
| RESILIENCY-02 | Compliant | 기존 RES-2 RPO 24h/수 시간 RTO를 새 durable state에 적용 |
| RESILIENCY-03 | Compliant | 기존 GitHub review/git-flow 변경 관리 계승 |
| RESILIENCY-04 | Compliant | §10.4.5 versioned 전환/진행 중 job/DB-aware rollback 요구 |
| RESILIENCY-05 | Compliant | §10.4.6 service 간 trace, latency/error/backlog 관측 |
| RESILIENCY-06 | Compliant | RJ-AC12 queue와 독립적인 shallow/deep health 응답 |
| RESILIENCY-07 | Compliant | queue/job/result 전달 적체·disk/model saturation 경보 |
| RESILIENCY-08 | N/A | 승인된 single-Mac 단일 장애 도메인 예외 |
| RESILIENCY-09 | Compliant replacement | 수평 autoscale N/A; §10.4.3 bounded concurrency/backpressure/capacity gate |
| RESILIENCY-10 | Compliant | 업무·status·event·health 의존 격리와 bounded timeout |
| RESILIENCY-11 | Compliant | 기존 backup-and-restore 전략에 operation/result state 포함 |
| RESILIENCY-12 | Compliant | §10.4.4 암호화 backup 및 복구·보존·owner purge 검증 |
| RESILIENCY-13 | Compliant | queue/worker/artifact 복구 후 accepted job 재조정 요구 |
| RESILIENCY-14 | Compliant | RJ-AC12 queue loss/crash/reconnect/partial deploy 시험 |
| RESILIENCY-15 | Compliant | 기존 RES-11 경보/COE와 비동기 실패 증거 연계 |

| PBT 규칙 | 단계 적용 | 후속 추적 |
|---|---|---|
| PBT-01 | N/A - Requirements Analysis | Functional Design에서 QT-12의 property 분류 |
| PBT-02 | N/A - Requirements Analysis | job/event/result DTO round-trip |
| PBT-03 | N/A - Requirements Analysis | owner 격리, terminal 보존, 비재귀 전달 불변식 |
| PBT-04 | N/A - Requirements Analysis | submit retry/redelivery의 논리적 멱등성 |
| PBT-05 | N/A - Requirements Analysis | 상태/권한/compatibility reference model |
| PBT-06 | N/A - Requirements Analysis | enqueue/crash/revoke/purge/reconnect 상태 시퀀스 |
| PBT-07 | N/A - Requirements Analysis | owner/job/token/version/event domain generator |
| PBT-08 | N/A - Requirements Analysis | shrinking/seed 및 CI 재현성 |
| PBT-09 | N/A - Requirements Analysis | 기존 Hypothesis/fast-check를 NFR Requirements에서 service별 매핑 |
| PBT-10 | N/A - Requirements Analysis | F01~F13 및 RJ-AC 회귀와 property 병행 |

PBT Full은 계속 활성이다. 상세 rule의 적용 stage 표에 따라 현 단계는 실행 검증 N/A이며, QT-12가 downstream test surface를 보존한다.

### 10.7 진행 및 상세 설계 이월

- [x] 명확화 답변과 existing FR/NFR/SEC/RES/QT를 대조했다.
- [x] 공개 job 범위, 직접 전달/관측 예외, FR-52/NFR-R4/QT-12/C-13을 작성했다.
- [x] F05/polling, F07 asset, FR-28 lifecycle, FR-47 unsubscribe, NFR-P1/P2의 인수를 정합시켰다.
- [x] 활성 확장의 요구사항 수준 delta와 후속 test surface를 검토했다.
- [x] 문서 구조, ID/참조, 답변 및 whitespace를 검증했다. 신규 ID 충돌 없음, RJ-AC01~12 전수 추적, DSRQF1/2=A, RJR1 단일 승인 질문, tracked/new-file whitespace check 통과.
- [x] RJR1에서 Requirements 개정 승인을 받았다. 사용자 "Approve & continue" (2026-09-19).
- [x] User Stories RJS2=A -> Workflow Planning WPR2=A 개정/승인 후 Application Design을 재개했다 (2026-09-19).

Application Design은 route/version·component/interface·domain owner·dependency를, Functional Design은 상태 전이·멱등키·삭제 fence·재연결 결과 의미를, NFR/Infrastructure Design은 TTL/보존/timeout/용량·전송/인증 구현·backup/runtime 배치를 구체화한다. 이 이월은 필요한 제품 결정이 미답변이라는 뜻이 아니다.
