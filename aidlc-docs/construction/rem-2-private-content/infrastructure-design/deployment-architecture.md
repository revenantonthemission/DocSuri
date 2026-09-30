# REM-2 Private Content — Deployment Architecture

**단계**: CONSTRUCTION / REM-2 Infrastructure Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: `infrastructure-design.md` 승인 (ID-Q1~8 전수 A), REM-1 배포 아키텍처 계승

---

## 1. 배포 토폴로지 — Single-Mac Production (OrbStack)

### 물리/논리 구성
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Single Mac (Apple Silicon)                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Cloudflare Tunnel                                │ │
│  │                    (공개 경로: 443 → 127.0.0.1:3000)                     │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                             │
│                                 ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        BFF (Next.js :3000)                               │ │
│  │  └── FastAPI API (:8000) — internal only                                │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                             │
│        ┌────────────────────────┼────────────────────────┐                  │
│        ▼                        ▼                        ▼                   │
│  ┌───────────┐            ┌───────────┐            ┌───────────┐          │
│  │ Postgres  │            │  Redis    │            │ OpenSearch │         │
│  │  16       │            │  7.2      │            │ 2.11       │         │
│  │ OrbStack  │            │ OrbStack  │            │ OrbStack   │         │
│  └───────────┘            └───────────┘            └───────────┘          │
│                                 │                                             │
│        ┌────────────────────────┼────────────────────────┐                  │
│        ▼                        ▼                        ▼                   │
│  ┌───────────┐            ┌───────────┐            ┌───────────┐          │
│  │  MinIO    │            │ElasticMQ  │            │  Keychain │          │
│  │(127.0.0.1:│            │(127.0.0.1:│            │  (system) │          │
│  │  9000)    │            │ 9324)     │            │           │          │
│  └───────────┘            └───────────┘            └───────────┘          │
│                                 │                                             │
│        ┌────────────────────────┼────────────────────────┐                  │
│        ▼                        ▼                        ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Launchd Workers (4종, _docsuri_rem2_worker)           ││
│  │  rem-2-content-translate  │ rem-2-content-summarize                     ││
│  │ rem-2-content-novelty     │ rem-2-content-evidence                      ││
│  │ UID/GID 700~703, InitGroups=false, Umask=0o077, ProcessType=Background ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Keychain (system, _docsuri_rem2_sign)                ││
│  │  rem-2-asset-jwt  │ rem-2-queue  │ rem-2-minio                          ││
│  │ ACL: _docsuri_rem2_translate/summarize/novelty/evidence만 접근 허용     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Backup Volume                                         ││
│  │  /Volumes/DocSuri_Backup (USB APFS 암호화, 상시 연결, 03:00 KST 백업)    ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 컴포넌트별 배포 상세

### 2.1 BFF + FastAPI API (Next.js + FastAPI)

| 구성요소 | 상세 |
|---|---|
| **Next.js Frontend** | Next.js 14 App Router, `:3000` (Cloudflare Tunnel → 443) |
| **FastAPI API** | `127.0.0.1:8000` (internal only, Cloudflare 경유만) |
| **Process Manager** | launchd (User: `_docsuri_rem2_web`, Group: `_docsuri_rem2_web`) |
| **Launchd Label** | `org.docsuri.rem2.web` |
| **WorkingDirectory** | `/Library/Application Support/DocSuri/rem-2/web` |
| **Logs** | `/Library/Application Support/DocSuri/rem-2/web/logs/*.out/.err` |
| **Environment** | `PATH=/usr/bin:/bin`, `LANG=en_US.UTF-8`, `HOME=/var/empty`, `PYTHONPATH=/Library/Application Support/DocSuri/rem-2/signer/lib` |

### 2.2 Launchd Content Workers (4종)

| Worker | Label | UID/GID | WorkingDirectory | Concurrency |
|---|---|---|---|---|
| Translate | `rem-2-content-translate` | 700/700 | `/Library/Application Support/DocSuri/rem-2/workers/translate` | sem=2 |
| Summarize | `rem-2-content-summarize` | 701/700 | `/Library/Application Support/DocSuri/rem-2/workers/summarize` | sem=2 |
| Novelty | `rem-2-content-novelty` | 702/700 | `/Library/Application Support/DocSuri/rem-2/workers/novelty` | sem=1 |
| Evidence | `rem-2-content-evidence` | 703/700 | `/Library/Application Support/DocSuri/rem-2/workers/evidence` | sem=2 |

**공통 설정**:
- `UserName`: `_docsuri_rem2_worker` (각 worker별 UID 700~703, 공통 GID 700)
- `GroupName`: `_docsuri_rem2_worker`
- `InitGroups`: `false`
- `Umask`: `0o077`
- `ProcessType`: `Background`
- `ThrottleInterval`: `5`
- `ExitTimeOut`: `30`
- `RunAtLoad`: `false`
- `StandardOutPath/StandardErrorPath`: `{working_dir}/logs/*.out/.err`

### 2.3 OrbStack Containers

| Service | Image | Port (Host) | Volume | 비고 |
|---|---|---|---|---|
| Postgres | `postgres:16` | `127.0.0.1:5432` | `rem1-pgdata-rem2` (named) | `ssl=on`, mTLS |
| Redis | `redis:7.2` | `127.0.0.1:6379` | `rem2-redis` (named) | - |
| OpenSearch | `opensearchproject/opensearch:2.11` | `127.0.0.1:9200` | `rem2-opensearch` (named) | `security.disabled=false` |
| MinIO | `minio/minio:RELEASE.2024` | `127.0.0.1:9000` | `rem2-minio` (named) | `MINIO_ROOT_USER/PASSWORD` from Keychain |
| ElasticMQ | `softwaremill/elasticmq:1.3` | `127.0.0.1:9324` | `rem2-elasticmq` (named) | `elasticmq.conf`로 queue/DLQ 설정 |

**네트워크**: 모든 container는 OrbStack 내부 네트워크, host port는 **loopback만** 바인딩 (`127.0.0.1:*`)

### 2.2 Keychain (macOS Security Framework)

| Keychain | Path | Owner | ACL (접근 허용) |
|---|---|---|---|
| `rem-2-asset-jwt.keychain-db` | `/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db` | `_docsuri_rem2_sign` | `_docsuri_rem2_translate`, `_docsuri_rem2_summarize`, `_docsuri_rem2_novelty`, `_docsuri_rem2_evidence` |
| `rem-2-queue.keychain-db` | `/Library/Application Support/DocSuri/rem-2/keys/queue.keychain-db` | `_docsuri_rem2_sign` | 동일 |
| `rem-2-minio.keychain-db` | `/Library/Application Support/DocSuri/rem-2/keys/minio.keychain-db` | `_docsuri_rem2_sign` | 동일 |

**ACL 설정**: `security set-keychain-acl -a "_docsuri_rem2_translate" ...` 등으로 worker 계정만 접근 허용

### 2.3 Backup Volume

| 속성 | 값 |
|---|---|
| **Mount Point** | `/Volumes/DocSuri_Backup` |
| **Volume UUID** | `BB384D60-46AF-4A06-B6F7-95710B3B7A3C` |
| **암호화** | APFS 암호화 (FileVault 별도) |
| **연결** | 상시 연결 (USB SSD01) |
| **Schedule** | 매일 03:00 KST (UTC+9) |
| **Ownership** | `diskutil enableOwnership` 적용, `GlobalPermissionsEnabled=true` |
| **Backup Scope** | `corpus/`, `private/userdoc/`, `assets/`, `receipt-public/`, `sign/`, `clock-public/` |

---

## 3. 배포 순서 (Deployment Order)

### Phase 1: 인프라 준비 (root 필요)
```bash
# 1. OrbStack containers 시작
orbstack start postgres redis opensearch minio elasticmq

# 2. Keychain provisioning
sudo uv run --directory ops python platform-integrity/provision_rem2_keys.py --profile test

# 3. Launchd worker 계정 생성
sudo dscl . -create /Groups/_docsuri_rem2_worker PrimaryGroupID 700
sudo dscl . -create /Users/_docsuri_rem2_translate PrimaryGroupID 700 UniqueID 700 ...
# (summarize=701, novelty=702, evidence=703)

# 3. Keychain ACL 설정
security set-keychain-acl -a "_docsuri_rem2_translate" /Library/Application\ Support/DocSuri/rem-2/keys/asset-jwt.keychain-db
# ... (summarize, novelty, evidence 동일)

# 4. Launchd worker 서비스 설치
sudo uv run --directory ops python platform-integrity/provision_content_workers.py --profile test --replace
```

### Phase 2: 애플리케이션 배포
```bash
# 1. Python packages
cd platform_integrity && uv pip install -e . --all-extras
cd ../ops && uv pip install -e . --all-extras
cd ../shared/python && uv pip install -e .

# 2. Frontend build
cd frontend && pnpm install && pnpm run build

# 3. BFF + FastAPI launchd 설치 (web 서비스)
sudo uv run --directory ops python platform-integrity/provision_web.py --profile test --replace
```

### Phase 3: 검증
```bash
# Launchd 서비스 상태 확인
sudo launchctl print system/org.docsuri.rem2.web
sudo launchctl print system/rem-2-content-translate
# ... (summarize, novelty, evidence)

# Health check
curl -k https://api.docsuri.com/healthz
curl -k https://api.docsuri.com/internal/v1/evidence/test-paper
```

---

## 3. 롤백 계획 (Rollback Plan)

| 구성요소 | 롤백 절차 |
|---|---|
| Launchd Workers | `sudo launchctl bootout system/rem-2-content-*` + plist 삭제 |
| Keychain | `sudo security delete-keychain /Library/Application Support/DocSuri/rem-2/keys/*.keychain-db` |
| MinIO | `mc rm --recursive --force local/docsuri/assets/rem2-test/`, `mc rm --recursive --force local/docsuri/private/userdoc/rem2-test/` |
| DB | Migration rollback 불필요(추가 테이블 없음). `effect_ledger`/`outbox`만 REM-2 job용 행 정리. |
| Launchd plist | `/Library/LaunchDaemons/rem-2-content-*.plist` 삭제 |
| OrbStack containers | `orbstack stop` (전체) 또는 개별 container stop |

---

## 4. 검증 체크리스트 (Deployment Verification)

| 체크 항목 | 명령 | 기대 결과 |
|---|---|---|
| Launchd web 서비스 | `sudo launchctl print system/org.docsuri.rem2.web` | `state = running` |
| Launchd workers | `sudo launchctl print system/rem-2-content-translate` 등 | `state = running` (4종 모두) |
| Keychain 접근 | `security find-generic-password -s "asset-jwt" -g` | worker 계정으로 접근 성공 |
| MinIO 연결 | `mc ls local/docsuri/assets/` | 버킷 접근 성공 |
| ElasticMQ | `curl -s http://127.0.0.1:9324/` | ElasticMQ UI 응답 |
| BFF Health | `curl -k https://api.docsuri.com/healthz` | `{"alive": true}` |
| API Health | `curl -k https://api.docsuri.com/internal/v1/evidence/test-paper` | `{"verdict": "ELIGIBLE"}` |
| SSE 연결 | `curl -N https://api.docsuri.com/jobs/{jobId}/events` | SSE 스트림 수신 |
| Asset 다운로드 | `curl -L https://api.docsuri.com/api/v1/assets/{assetId}?token=...` | 파일 다운로드 성공 |
| Backup | `ls /Volumes/DocSuri_Backup/` | 백업 디렉토리 존재 |

---

## 5. 모니터링·경보 (Operations)

| 메트릭 | 소스 | 경보 임계값 |
|---|---|---|
| `job_accepted_total` (rate) | BFF 로그 | 급증 > 10x baseline for 2m |
| `job_failed_rate` | BFF 로그 | > 5% for 5m |
| `job_queue_depth` | ElasticMQ | > 1000 for 2m |
| `job_latency_p95` | BFF 로그 | p95 > 300s for 10m |
| `asset_delivery_p95` | AssetController 로그 | p95 > 10s for 5m |
| `cache_hit_ratio` | TranslationCacheService | < 0.3 for 15m |
| `queue_redelivery_rate` | Worker 로그 | > 0.01 for 5m |
| `authz_recheck_failures` | AuthzMiddleware | > 0 즉시 |
| Disk free | `df /Volumes/DocSuri_Backup` | < 10 GiB 경보 |
| Launchd worker 상태 | `launchctl print` | 비-running 즉시 경보 |

---

## 6. 승인 기록

| 질문 | 답변 | 일자 |
|---|---|---|
| ID-Q1~8 | A (전수) | 2026-09-30 |

**다음**: Code Generation Part 2 → `construction/rem-2-private-content/code/`
