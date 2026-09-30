# REM-2 Private Content — Infrastructure Design 계획

**단계**: CONSTRUCTION / REM-2 Infrastructure Design (Part 1: Planning)  
**일자**: 2026-09-30  
**입력**: 
- REM-2 Functional Design (FD-Q1~8)
- REM-2 NFR Requirements (NFR-Q1~13)
- REM-2 NFR Design (ND-Q1~10)
- REM-1 Infrastructure: launchd installer, OrbStack(Postgres/Redis/OpenSearch/MinIO/ElasticMQ), launchd clock jobs, receipt signer, keychain, backup/restore, load acceptance
- `verification-remediation-2026-09-18.md` §2 Single-Mac Production 기준
- `requirements.md` C-13, C-14, SEC-6/7/12, RES-2/11/12

**목표**: REM-2 Private Content의 인프라 배치·배포·운영 설계를 확정하고, 8개 결정 질문(REM-2-ID-Q1~8)에 대한 답변을 수집해 Part 2 Generation 게이트를 연다.

---

## 상속된 비협상 결정

- **Single-Mac production**: OrbStack으로 Postgres/Redis/OpenSearch/MinIO/ElasticMQ 실행. host port loopback 전용. Cloudflare Tunnel로 공개 경로.
- **Launchd**가 API, web, ingestion, summarization, evidence, novelty worker, purge, backup, heartbeat, tunnel 관리.
- **Backup**: 일일 03:00 Asia/Seoul, `/Volumes/DocSuri_Backup`(USB APFS 암호화 volume, 상시 연결). RPO 24h / RTO 수 시간.
- **REM-1 계약 동결**: `shared/dtos`, `shared/ports`, `shared/vector-spec` 공급.
- **Security Full, PBT Full, Resiliency custom**(`RESILIENCY-08` 면제) 계승.

---

## 분해 질문 (Decomposition Questions)

### REM-2-ID-Q1 — Private userdoc 저장: MinIO namespace 분리

F01 private userdoc은 public corpus와 격리돼야 한다. MinIO bucket/prefix를 어떻게 분리할까?

A) **동일 bucket, 별도 prefix + IAM policy(권장)** — bucket `docsuri-private` 또는 `docsuri` 동일 버킷 내 `private/userdoc/{owner}/{docId}/` prefix. MinIO IAM policy로 `userdoc:*` 경로는 owner 계정만 접근 가능. public corpus(`corpus/`)와 버킷/프리픽스로 완전 격리. 버킷 분리 불필요.

B) 별도 버킷 `docsuri-userdoc` — 격리 명확 but MinIO 버킷 수 증가, 백업/정책 중복.

C) 기타

[Answer]: AA) **동일 bucket, 별도 prefix + IAM policy(권장)** — bucket `docsuri-private` 또는 `docsuri` 동일 버킷 내 `private/userdoc/{owner}/{docId}/` prefix. MinIO IAM policy로 `userdoc:*` 경로는 owner 계정만 접근 가능. public corpus(`corpus/`)와 버킷/프리픽스로 완전 격리. 버킷 분리 불필요.

---

### REM-2-ID-Q2 — Asset serving: MinIO internal endpoint + presigned URL

F07/NFR-Q4: asset는 MinIO에 저장, `GET /api/assets/{assetId}?token`이 presigned URL 생성 후 redirect. MinIO는 **internal network만 허용**, 외부 직접 접근 차단.

A) **MinIO internal host port(OrbStack) + BFF만 접근(권장)** — OrbStack의 MinIO container port(`9000`)를 host loopback(`127.0.0.1:9000`)로만 노출. BFF(`127.0.0.1:8000`)만 접근 허용. Cloudflare Tunnel 경로에는 asset endpoint 미노출(별도 same-origin BFF 경로만). `mc` CLI는 host에서 `mc alias set local http://127.0.0.1:9000`로 관리.

B) MinIO를 Cloudflare Tunnel로도 노출 — 외부 직접 접근 가능해짐, 보안 약화.

C) 기타

[Answer]: AA) **MinIO internal host port(OrbStack) + BFF만 접근(권장)** — OrbStack의 MinIO container port(`9000`)를 host loopback(`127.0.0.1:9000`)로만 노출. BFF(`127.0.0.1:8000`)만 접근 허용. Cloudflare Tunnel 경로에는 asset endpoint 미노출(별도 same-origin BFF 경로만). `mc` CLI는 host에서 `mc alias set local http://127.0.0.1:9000`로 관리.

---

### REM-2-ID-Q3 — Job queue: ElasticMQ on OrbStack + DLQ

RJ-AC01~12 job 계약은 ElasticMQ로 구현. `submitted → accepted → queued → running → completed/failed/abstated` 전이를 큐 메시지로 구현. worker crash/재전달 시 멱등성(ND-Q8) 보장. DLQ로 영구 실패 격리.

A) **ElasticMQ on OrbStack + 표준 queue/DLQ(권장)** — queue: `content-job-{task_type}`(translate, summarize, novelty, evidence). DLQ: `content-job-dlq`. 메시지: `{jobId, taskType, input, idempotencyKey, attempt, createdAt}`. visibility timeout 5분, maxReceiveCount 3 후 DLQ 이동. OrbStack의 ElasticMQ container(`elasticmq:1.3`) 사용, host loopback `127.0.0.1:9324`만 노출.

B) Redis Streams로 대체 — ElasticMQ 미사용 but 구현 변경 필요.

C) 기타

[Answer]: AC) ElasticMQ on Colima + 표준 queue/DLQ

---

### REM-2-ID-Q4 — Worker concurrency + backpressure

NFR-Q10/RESILIENCY-10: worker 동시성 상한과 backpressure로 model/disk saturation 방지. 각 task type(translate, summarize, novelty, evidence)별 **최대 동시 worker 수**와 **queue depth 상한**을 확정한다.

A) **Task type별 동시성 상한 + queue depth gate(권장)** — 
- translate: 동시 2, queue depth 50
- summarize: 동시 2, queue depth 50  
- novelty: 동시 1, queue depth 20
- evidence: 동시 2, queue depth 30
worker가 queue에서 메시지 수신 전 `semaphore.acquire()` → 완료 시 `release()`. queue depth가 상한 초과 시 `429 Too Many Requests`로 접수 거부(RJ-AC01). OrbStack 메모리(OrbStack 기본 8GB 할당) 내에서 동작.

B) 고정 단일 worker — 단순하지만 throughput 낮음.

C) 기타

[Answer]: AA) **Task type별 동시성 상한 + queue depth gate(권장)** — 
- translate: 동시 2, queue depth 50
- summarize: 동시 2, queue depth 50  
- novelty: 동시 1, queue depth 20
- evidence: 동시 2, queue depth 30
worker가 queue에서 메시지 수신 전 `semaphore.acquire()` → 완료 시 `release()`. queue depth가 상한 초과 시 `429 Too Many Requests`로 접수 거부(RJ-AC01). OrbStack 메모리(OrbStack 기본 8GB 할당) 내에서 동작.

---

### REM-2-ID-Q5 — Backup/restore: private userdoc + asset 포함

RES-2/11/12: 일일 03:00 backup에 private userdoc(`private/userdoc/`)와 asset(`assets/`) 포함. owner purge 시 backup에서도 해당 owner 데이터만 제거 가능해야 함. restore 시 new incarnation으로 격리 복원(ND-Q8 effect ledger와 동일 원칙).

A) **기존 backup_evidence.py collect/gc에 private path 포함(권장)** — `backup_evidence.py collect`의 `--source`에 `private/userdoc/`와 `assets/` 추가. `gc`의 `ManagedPath` 마커로 owner별 격리 복원/파기 지원. `--incarnation`으로 new incarnation 복원 검증. backup 시 owner purge 전 상태 보존, purge 후 별도 실행으로 owner 데이터만 제거.

B) 별도 backup 스크립트 — 중복 but 격리 명확.

C) 기타

[Answer]: AA) **기존 backup_evidence.py collect/gc에 private path 포함(권장)** — `backup_evidence.py collect`의 `--source`에 `private/userdoc/`와 `assets/` 추가. `gc`의 `ManagedPath` 마커로 owner별 격리 복원/파기 지원. `--incarnation`으로 new incarnation 복원 검증. backup 시 owner purge 전 상태 보존, purge 후 별도 실행으로 owner 데이터만 제거.

---

### REM-2-ID-Q6 — Launchd job 등록: content worker 서비스가능화

NFR-Q10/RESILIENCY-10: content worker(translate, summarize, novelty, evidence)를 launchd 서비스로 등록해 자동 재시작/로그 회전/리소스 제한 적용. REM-1 `launchd.py` installer 재사용.

A) **REM-1 launchd installer 재사용 + 4개 service(권장)** — `rem-2-content-translate`, `rem-2-content-summarize`, `rem-2-content-novelty`, `rem-2-content-evidence` label로 launchd plist 생성. 각 worker는 단일 task type만 처리, 동시성 상한(ID-Q4)은 worker 내부 semaphore로 제어. `WorkingDirectory`는 `/Library/Application Support/DocSuri/rem-2/workers/{type}`, 로그 `/Library/Application Support/DocSuri/rem-2/workers/{type}/logs`로 분리. `UserName`=`_docsuri_rem2_worker`, `GroupName`=`_docsuri_rem2_worker`, `InitGroups=false`, `Umask=0o077`, `ProcessType=Background`, `ThrottleInterval=5`, `ExitTimeOut=30`. `RunAtLoad=false`, 필요 시 `launchctl kickstart`로 시작.

B) 단일 launchd job이 4개 worker 모두 관리 — 단순하지만 개별 재시작/로그/리소스 제어 불가.

C) 기타

[Answer]: AA) **REM-1 launchd installer 재사용 + 4개 service(권장)** — `rem-2-content-translate`, `rem-2-content-summarize`, `rem-2-content-novelty`, `rem-2-content-evidence` label로 launchd plist 생성. 각 worker는 단일 task type만 처리, 동시성 상한(ID-Q4)은 worker 내부 semaphore로 제어. `WorkingDirectory`는 `/Library/Application Support/DocSuri/rem-2/workers/{type}`, 로그 `/Library/Application Support/DocSuri/rem-2/workers/{type}/logs`로 분리. `UserName`=`_docsuri_rem2_worker`, `GroupName`=`_docsuri_rem2_worker`, `InitGroups=false`, `Umask=0o077`, `ProcessType=Background`, `ThrottleInterval=5`, `ExitTimeOut=30`. `RunAtLoad=false`, 필요 시 `launchctl kickstart`로 시작.

---

### REM-2-ID-Q7 — CSP/Asset endpoint: same-origin + MinIO presigned redirect

NFR-Q4/F07: `GET /api/assets/{assetId}?token` → owner/license/object 재검증 → MinIO presigned GET(1분 TTL) → `307 Redirect`. CSP `img-src 'self' https://minio.internal` 허용. MinIO는 internal만 노출(ID-Q2).

A) **BFF가 presigned URL 생성 후 307 Redirect(권장)** — FastAPI endpoint가 owner/license/object 재검증 → MinIO presigned GET URL(1분 TTL, `response-content-disposition: inline`) 생성 → `307 Redirect` with `Location: <presigned_url>`. 브라우저가 MinIO(`127.0.0.1:9000`)에서 직접 다운로드. CSP: `Content-Security-Policy: img-src 'self' http://127.0.0.1:9000; connect-src 'self' https://api.docsuri.com`. MinIO는 OrbStack internal(`127.0.0.1:9000`)만 바인딩.

B) BFF가 프록시 스트리밍 — 대역폭 소모, 구현 단순화.

C) 기타

[Answer]: AA) **BFF가 presigned URL 생성 후 307 Redirect(권장)** — FastAPI endpoint가 owner/license/object 재검증 → MinIO presigned GET URL(1분 TTL, `response-content-disposition: inline`) 생성 → `307 Redirect` with `Location: <presigned_url>`. 브라우저가 MinIO(`127.0.0.1:9000`)에서 직접 다운로드. CSP: `Content-Security-Policy: img-src 'self' http://127.0.0.1:9000; connect-src 'self' https://api.docsuri.com`. MinIO는 OrbStack internal(`127.0.0.1:9000`)만 바인딩.

---

### REM-2-ID-Q8 — Secret/Key 관리: asset JWT secret, queue creds, MinIO keys

C-13/C-14: secret은 Keychain/환경변수로만 관리, 코드/로그/아카이브에 노출 금지. REM-1 keychain pattern 재사용.

A) **Keychain + 환경변수 하이브리드(권장)** — 
- Asset JWT secret: `/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db` (service `docsuri.rem2.asset`, account `asset-jwt`), `security` CLI로 읽기.
- ElasticMQ creds: `rem-2-queue.keychain-db` (service `docsuri.rem2.queue`, account `elasticmq`).
- MinIO keys: `rem-2-minio.keychain-db` (service `docsuri.rem2.minio`, account `minio`).
- Keychain은 `_docsuri_rem2_sign` 계정 소유, ACL로 launchd worker만 접근 허용.
- `provision_receipts.py` 패턴으로 root provisioner가 keychain 생성·비밀번호 입력·ACL 설정.
- 런타임은 `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽어 unlock → 사용 후 lock.

B) 환경변수만 — 단순 but 코드/프로세스 리스트 노출 위험.

C) 기타

[Answer]: AA) **Keychain + 환경변수 하이브리드(권장)** — 
- Asset JWT secret: `/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db` (service `docsuri.rem2.asset`, account `asset-jwt`), `security` CLI로 읽기.
- ElasticMQ creds: `rem-2-queue.keychain-db` (service `docsuri.rem2.queue`, account `elasticmq`).
- MinIO keys: `rem-2-minio.keychain-db` (service `docsuri.rem2.minio`, account `minio`).
- Keychain은 `_docsuri_rem2_sign` 계정 소유, ACL로 launchd worker만 접근 허용.
- `provision_receipts.py` 패턴으로 root provisioner가 keychain 생성·비밀번호 입력·ACL 설정.
- 런타임은 `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽어 unlock → 사용 후 lock.

---

## 답변 방법

각 `[Answer]:` 뒤에 A, B 또는 X와 설명을 입력한다. 모든 권장안을 채택하려면 REM-2-ID-Q1~8에 각각 A를 기록한다. 모든 답변과 plan 승인을 받기 전에는 Part 2 Generation으로 진행하지 않는다.
