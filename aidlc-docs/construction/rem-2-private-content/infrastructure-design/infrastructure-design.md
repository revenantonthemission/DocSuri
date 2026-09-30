# REM-2 Private Content — Infrastructure Design

**단계**: CONSTRUCTION / REM-2 Infrastructure Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: 
- NFR Design: `nfr-design/` 승인 (ND-Q1~10 전수 A)
- Infrastructure Design Questions: ID-Q1~8 전수 A 승인
- REM-1 인프라: launchd, OrbStack(Postgres/Redis/OpenSearch/MinIO/ElasticMQ), clock, receipt signer, keychain, backup/restore, load acceptance
- `verification-remediation-2026-09-18.md` §2 Single-Mac Production 기준

---

## 1. Private UserDoc Storage — MinIO Namespace 분리 (ID-Q1 A)

### 설계
- **동일 bucket `docsuri`, 별도 prefix + IAM policy**
  - Public corpus: `corpus/` prefix
  - Private userdoc: `private/userdoc/{owner}/{docId}/` prefix
  - Assets: `assets/{assetId}` prefix (공유)
- **격리 메커니즘**: MinIO IAM policy로 `private/userdoc/*` 경로는 해당 owner 계정만 접근 가능
- **이유**: 버킷 분리 불필요, 백업/정책 중복 방지, 동일 bucket 내 prefix로 완전 격리

### MinIO Policy (예시)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::*:user/_docsuri_rem2_worker"},
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::docsuri/private/userdoc/${aws:userid}/*"
    },
    {
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::docsuri/private/userdoc/*",
      "Condition": {"StringNotEquals": {"aws:userid": "${aws:userid}"}}
    }
  ]
}
```

---

## 2. Asset Serving — MinIO Internal + Presigned URL (ID-Q2 A, ID-Q7 A)

### 아키텍처
```
Client → BFF (FastAPI) → AssetService.authorize() → MinIO presigned GET (1분 TTL) → 307 Redirect → Client → MinIO (127.0.0.1:9000) 직접 다운로드
```

### 구성
- **MinIO**: OrbStack container, `127.0.0.1:9000` **internal only** 바인딩
- **External 접근**: Cloudflare Tunnel 경로에 asset endpoint 미노출 (BFF same-origin 경로만)
- **mc CLI 관리**: host에서 `mc alias set local http://127.0.0.1:9000`로 관리
- **Presigned URL**: 1분 TTL, `response-content-disposition: inline`, JWT 토큰으로 인증

### 네트워크 격리
- MinIO container port 9000 → host loopback `127.0.0.1:9000`만 노출
- BFF(`127.0.0.1:8000`)만 접근 허용
- Cloudflare Tunnel 경로에는 asset endpoint 미노출

---

## 3. Job Queue — ElasticMQ on OrbStack (ID-Q3 A)

### Queue Topology
| Queue | 용도 | 설정 |
|---|---|---|
| `content-job-translate` | 번역 job | visibility timeout 5분, maxReceiveCount 3 |
| `content-job-summarize` | 요약 job | visibility timeout 5분, maxReceiveCount 3 |
| `content-job-novelty` | novelty job | visibility timeout 5분, maxReceiveCount 3 |
| `content-job-evidence` | evidence job | visibility timeout 5분, maxReceiveCount 3 |
| `content-job-dlq` | Dead Letter | maxReceiveCount 3 초과 시 이동 |

### 메시지 스키마
```json
{
  "jobId": "uuid",
  "taskType": "TRANSLATE|SUMMARIZE|NOVELTY|EVIDENCE",
  "input": {...},
  "idempotencyKey": "content:...",
  "attempt": 1,
  "createdAt": "2026-09-30T23:59:59.123456Z"
}
```

### 운영
- ElasticMQ: OrbStack container `elasticmq:1.3`, host loopback `127.0.0.1:9324`만 노출
- Visibility timeout 5분, maxReceiveCount 3 후 DLQ 이동
- 메시지 지속성: ElasticMQ persistence 활성화 (broker 재시작 시 메시지 보존)

---

## 4. Worker Concurrency + Backpressure (ID-Q4 A)

### Task Type별 동시성 상한
| Worker | Task Type | 동시성 상한 (semaphore) | Queue Depth 상한 | 비고 |
|---|---|---|---|---|
| TranslateWorker | TRANSLATE | 2 | 50 | Cache hit 시 즉시 completed |
| SummarizeWorker | SUMMARIZE | 2 | 50 | Map-reduce for 긴 본문 |
| NoveltyWorker | NOVELTY | 1 | 20 | Evidence agent 결과 소비 |
| EvidenceWorker | EVIDENCE | 2 | 30 | Evidence formation |

### 구현
- 각 worker 프로세스: 단일 `asyncio.Queue` + `asyncio.Semaphore`로 동시성 제어
- Queue depth 상한 초과 시 `429 Too Many Requests`로 접수 거부 (RJ-AC01)
- OrbStack 메모리(기본 8GB 할당) 내에서 동작
- Worker crash 시 `semaphore.release()`는 `finally` 블록에서 보장

---

## 5. Backup/Restore — Private Path 포함 (ID-Q5 A)

### Backup Scope 확대
```bash
# 기존 backup_evidence.py collect에 추가
--source private/userdoc/
--source assets/
```

### Owner별 격리 복원/파기
- `ManagedPath` 마커로 owner별 격리 복원/파기 지원
- `--incarnation`으로 new incarnation 복원 검증
- Owner purge 시 backup에서도 해당 owner 데이터만 제거 가능 (별도 gc 실행)

### 검증
- `backup_evidence.py collect`로 private userdoc + asset 백업 검증
- `gc --apply --approve-critical`로 owner별 격리 파기 검증
- Restore 시 new incarnation으로 격리 복원 (ND-Q8 effect ledger 원칙과 동일)

---

## 6. Launchd Worker 서비스 등록 (ID-Q6 A)

### 4종 Launchd Service
| Label | Worker | WorkingDirectory |
|---|---|---|
| `rem-2-content-translate` | TranslateWorker | `/Library/Application Support/DocSuri/rem-2/workers/translate` |
| `rem-2-content-summarize` | SummarizeWorker | `/Library/Application Support/DocSuri/rem-2/workers/summarize` |
| `rem-2-content-novelty` | NoveltyWorker | `/Library/Application Support/DocSuri/rem-2/workers/novelty` |
| `rem-2-content-evidence` | EvidenceWorker | `/Library/Application Support/DocSuri/rem-2/workers/evidence` |

### Plist 공통 설정
```xml
<key>Label</key><string>rem-2-content-translate</string>
<key>UserName</key><string>_docsuri_rem2_worker</string>
<key>GroupName</key><string>_docsuri_rem2_worker</string>
<key>InitGroups</key><false/>
<key>Umask</key><integer>127</integer>  <!-- 0o077 -->
<key>WorkingDirectory</key><string>/Library/Application Support/DocSuri/rem-2/workers/translate</string>
<key>ProcessType</key><string>Background</string>
<key>ThrottleInterval</key><integer>5</integer>
<key>ExitTimeOut</key><integer>30</integer>
<key>RunAtLoad</key><false/>
<key>StandardOutPath</key><string>/Library/Application Support/DocSuri/rem-2/workers/translate/logs/translate.out</string>
<key>StandardErrorPath</key><string>/Library/Application Support/DocSuri/rem-2/workers/translate/logs/translate.err</string>
```

### 계정 생성 (root 필요)
```bash
# 그룹/계정 생성 (UID/GID 700~703 할당)
dscl . -create /Groups/_docsuri_rem2_worker PrimaryGroupID 700
dscl . -create /Users/_docsuri_rem2_translate PrimaryGroupID 700 UniqueID 700 UserShell /usr/bin/false NFSHomeDirectory /var/empty
dscl . -create /Users/_docsuri_rem2_summarize PrimaryGroupID 700 UniqueID 701 UserShell /usr/bin/false NFSHomeDirectory /var/empty
dscl . -create /Users/_docsuri_rem2_novelty PrimaryGroupID 700 UniqueID 702 UserShell /usr/bin/false NFSHomeDirectory /var/empty
dscl . -create /Users/_docsuri_rem2_evidence PrimaryGroupID 700 UniqueID 703 UserShell /usr/bin/false NFSHomeDirectory /var/empty
```

### 설치/제거 (root 필요)
```bash
# 설치
sudo uv run --directory ops python platform-integrity/provision_content_workers.py --profile test --replace

# 제거
sudo launchctl bootout system/rem-2-content-translate
sudo launchctl bootout system/rem-2-content-summarize
sudo launchctl bootout system/rem-2-content-novelty
sudo launchctl bootout system/rem-2-content-evidence
```

---

## 7. CSP / Asset Endpoint — Same-Origin + MinIO Presigned (ID-Q7 A)

### CSP 헤더
```
Content-Security-Policy: img-src 'self' http://127.0.0.1:9000; script-src 'self'; connect-src 'self' wss://api.docsuri.com
```

### Asset Endpoint Flow
```
GET /api/v1/assets/{assetId}?token={jwt}
  → AssetService.authorize(caller, assetId, VIEW)
  → MinIO presigned GET (1분 TTL, inline disposition) 생성
  → 307 Redirect to presigned URL
  → 브라우저가 MinIO(127.0.0.1:9000)에서 직접 다운로드
```

### CSP 세부사항
- `img-src 'self' http://127.0.0.1:9000` — MinIO internal endpoint만 허용
- `script-src 'self'` — 인라인 스크립트 금지
- `connect-src 'self' wss://api.docsuri.com` — SSE/WebSocket만 허용
- MinIO는 **internal only** (`127.0.0.1:9000`), 외부 직접 접근 차단

---

## 8. Secret/Key 관리 — Keychain Pattern (ID-Q8 A)

### Keychain Secret Mapping
| Secret | Keychain Path | Service | Account | Owner | 용도 |
|---|---|---|---|---|---|
| Asset JWT Secret | `/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db` | `docsuri.rem2.asset` | `asset-jwt` | `_docsuri_rem2_sign` | Asset presigned JWT 서명 |
| ElasticMQ Creds | `/Library/Application Support/DocSuri/rem-2/keys/queue.keychain-db` | `docsuri.rem2.queue` | `elasticmq` | `_docsuri_rem2_sign` | ElasticMQ 인증 |
| MinIO Keys | `/Library/Application Support/DocSuri/rem-2/keys/minio.keychain-db` | `docsuri.rem2.minio` | `minio` | `_docsuri_rem2_sign` | MinIO access/secret key |

### Provisioning (root 필요)
```bash
sudo uv run --directory ops python platform-integrity/provision_rem2_keys.py --profile test
```
- `provision_receipts.py` 패턴으로 root provisioner가 keychain 생성·비밀번호 입력·ACL 설정
- 런타임은 `KEYCHAIN_PASSWORD_STDIN`으로 stdin에서 비밀번호 읽어 unlock → 사용 후 lock

### Keychain ACL
```bash
# 각 keychain에 worker 계정만 접근 허용
security set-keychain-acl -a "_docsuri_rem2_translate" "/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db"
security set-keychain-acl -a "_docsuri_rem2_summarize" "/Library/Application Support/DocSuri/rem-2/keys/asset-jwt.keychain-db"
# ... (4개 worker 계정 모두 추가)
```

---

## 9. 네트워크 토폴로지 (Single-Mac Production)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Single Mac (OrbStack)                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Cloudflare Tunnel                                │ │
│  │                    (공개 경로: 443 → 127.0.0.1:3000)                     │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                             │
│                                 ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        BFF (FastAPI :8000)                               │ │
│  │  RateLimitMw → JobAuthzMw → ContentJobService → AssetController        │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                             │
│        ┌────────────────────────┼────────────────────────┐                  │
│        ▼                        ▼                        ▼                   │
│  ┌───────────┐            ┌───────────┐            ┌───────────┐          │
│  │ Postgres  │            │  Redis    │            │ OpenSearch │         │
│  │ (OrbStack)│            │ (OrbStack)│            │ (OrbStack) │          │
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
│  │                    Launchd Workers (4종)                                 ││
│  │  rem-2-content-translate  │ rem-2-content-summarize                     ││
│  │  rem-2-content-novelty    │ rem-2-content-evidence                      ││
│  │  User: _docsuri_rem2_worker, InitGroups=false, Umask=0o077             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Keychain (system)                                     ││
│  │  rem-2-asset-jwt  │ rem-2-queue  │ rem-2-minio                          ││
│  │  Owner: _docsuri_rem2_sign, ACL: worker 계정만 접근 허용                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Backup Volume                                         ││
│  │  /Volumes/DocSuri_Backup (USB APFS 암호화, 상시 연결, 03:00 KST 백업)    ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. 승인 기록

| 질문 | 답변 | 일자 |
|---|---|---|
| ID-Q1~8 | A (전수) | 2026-09-30 |

**다음**: Code Generation Part 2 → `construction/rem-2-private-content/code/`
