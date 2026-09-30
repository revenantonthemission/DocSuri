# REM-2 Private Content — Domain Entities

**단계**: CONSTRUCTION / REM-2 Functional Design Generation Part 2  
**일자**: 2026-09-30  
**기반**: FD-Q1~8 승인 (전수 A), NFR-Q1~13/ND-Q1~10/ID-Q1~8/CG-Q1~5 승인 대기 중

---

## 1. PrivateUserDoc

사용자 업로드 문서(PDF/Markdown/TXT)로, public corpus와 완전히 격리된 owner-scoped 엔티티.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `docId` | `Ref` | UUID v7, `userdoc:{owner}:{docId}` key prefix | 고유 식별자, owner 포함으로 격리 보장 |
| `owner` | `Ref` | 계정 UID, `_docsuri_r1t_*` 역할 아님 | 문서 소유자, non-owner에게 존재 은폐 |
| `sourceFormat` | `Enum` | `PDF`, `MARKDOWN`, `TEXT` | 업로드 원본 형식 |
| `sourceBytes` | `Bytes` | ≤ 50 MiB (configurable) | 원본 바이트, 저장 후 파싱용 |
| `docModel` | `DocModel` | `DocModel` 스키마 준수 | 파싱된 구조화 문서 (Section/Block/표/수식/그림 AssetRef) |
| `version` | `U64` | monotonic 증가 | 업데이트 시 증가, cache key에 포함 |
| `createdAt` | `U64` | 마이크로초 UTC | 생성 시각 |
| `updatedAt` | `U64` | 마이크로초 UTC | 마지막 수정 시각 |
| `status` | `Enum` | `PENDING`, `READY`, `FAILED` | 파싱/저장 상태 |

**불변식**:
- `docId`는 `userdoc:{owner}:{uuid}` 형식을 강제한다.
- `owner`는 인증된 호출자의 UID와 일치해야 한다(작성/읽기 모두).
- `docModel`은 `DocModel` 스키마 검증을 통과한 것만 저장한다.
- `sourceBytes`는 저장 후 파싱 완료되면 선택적으로 삭제 가능(정책: 보관/삭제).

---

## 2. TranslationCacheEntry

번역 결과를 캐싱하는 엔티티. **canonical source identity**에 결속돼 client-provided source 오염을 방지한다.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `cacheKey` | `Ref` | `translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}` | 정규화된 키, client source 무시 |
| `canonicalPaperId` | `Ref` | `arxiv:{id}` \| `semantic:{id}` \| `openalex:{id}` \| `userdoc:{owner}:{docId}` | `CanonicalPaperRegistry`가 확정한 정체성 |
| `version` | `U64` | 논문/문서 버전 | 내용 변경 시 cache 무효화 |
| `sourceTier` | `Enum` | `ARXIV_HTML`, `SEMANTIC_SCHOLAR_PDF`, `OPENALEX_PDF`, `USER_UPLOAD` | 출처 계층, 품질 순위 내림차순 |
| `targetLang` | `Ref` | ISO 639-1 (예: `ko`) | 목표 언어 |
| `personaHash` | `Ref` | SHA256(persona config) | persona config 변경 시 별도 엔트리 |
| `assetId` | `Ref` | `asset:{sha256(content)[:32]}` | 번역 결과 자산 참조 |
| `completedAt` | `U64` | 마이크로초 UTC | 생성/갱신 시각 |
| `hitCount` | `U64` | ≥ 0 | 캐시 히트 카운트, LRU 용 |

**불변식**:
- `cacheKey` 구성 요소 모두 server-verified 값만 사용한다. client 제공 `source` 파라미터는 **무시**한다.
- `canonicalPaperId`는 `CanonicalPaperRegistry.resolve(paperId, version)`로만 확정된다.
- 동일 `cacheKey` 재작성은 최신 결과로 원자적 치환(멱등).

---

## 3. ContentJob

요약/번역/novelty/evidence 생성 작업을 나타내는 잡 엔티티. 공개 job 계약(RJ-AC01~12)을 따른다.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `jobId` | `Ref` | UUID v7, `job:{uuid}` | 고유 식별자 |
| `taskType` | `Enum` | `TRANSLATE`, `SUMMARIZE`, `NOVELTY`, `EVIDENCE` | 작업 유형 |
| `owner` | `Ref` | 계정 UID | 잡 소유자, 모든 단계에서 재검증 |
| `input` | `JobInput` | task type별 스키마 | 입력 데이터 (canonical paper ref, persona 등) |
| `idempotencyKey` | `Ref` | `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}` | 멱등성 보장, 동일 키 재제출 시 기존 job 반환 |
| `state` | `Enum` | `SUBMITTED`, `ACCEPTED`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `ABSTAINED` | 상태 기계 전이만 허용 |
| `attempt` | `U64` | 1부터 시작, redelivery 시 증가 | 멱등성 키와 함께 중복 차단 |
| `assetId` | `Ref` | `asset:{sha256(content)[:32]}` | 완료 시 결과 자산 참조 (`COMPLETED` 시만) |
| `abstainReason` | `String` | `ABSTAINED` 시만 필수 | 근거 없음/초극단 거절 사유 |
| `error` | `JobError` | `FAILED` 시만 필수 | `{errorType, message, retryable, retryAfterSeconds?}` |
| `createdAt` | `U64` | 마이크로초 UTC | 접수 시각 |
| `acceptedAt` | `U64` | 마이크로초 UTC | durable 접수 확인 시각 (RJ-AC01) |
| `startedAt` | `U64` | 마이크로초 UTC | 실행 시작 시각 |
| `completedAt` | `U64` | 마이크로초 UTC | 종료 시각 |
| `authzToken` | `Ref` | 1분 TTL 캐시 토큰 | 권한 재검증용 (NFR-Q7) |

**상태 전이 (불변)**:
```
SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED | FAILED | ABSTAINED
```
- 역전환 불가. `SUBMITTED`에서 검증 실패 시 즉시 `FAILED`.
- `ABSTAINED`는 근거 없음(FR-5) 또는 초극단 입력 거절 시 정상 terminal 상태.

---

## 4. Asset

생성된 결과물(번역본, 요약본, novelty 결과, evidence 결과)을 저장하는 엔티티.

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `assetId` | `Ref` | `asset:{sha256(content)[:32]}` | 내용 해시 기반, 내용 변경 시 새 asset |
| `content` | `Bytes` | 번역본/요약본/JSON 등 | 실제 결과 바이트 |
| `contentType` | `String` | `application/json`, `text/markdown` 등 | MIME 타입 |
| `owner` | `Ref` | 계정 UID | 자산 소유자 |
| `license` | `Enum` | `ARXIV`, `SEMANTIC_SCHOLAR`, `OPENALEX`, `USER_UPLOAD`, `GENERATED` | 라이선스/출처 |
| `objectRef` | `Ref` | MinIO object path | `assets/{assetId}` 또는 `private/userdoc/{owner}/{docId}/assets/{assetId}` |
| `createdAt` | `U64` | 마이크로초 UTC | 생성 시각 |
| `sizeBytes` | `U64` | 바이트 크기 | 전송/저장 용량 |

**불변식**:
- `assetId`는 내용 해시로부터 결정론적으로 유도된다(내용 변경 = 새 asset).
- `owner`는 생성 job의 `owner`와 일치한다.
- `license`는 source material의 라이선스를 계승한다(`GENERATED`는 파생물).

---

## 5. JobEvent

잡 상태 변경 시 발행되는 이벤트. SSE로 푸시되며 재연결 시 replay된다(RJ-AC04).

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `eventId` | `Ref` | UUID v7 | 이벤트 고유 ID |
| `jobId` | `Ref` | 대상 잡 ID | 대상 잡 |
| `state` | `Enum` | 잡의 새 상태 | `ACCEPTED`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `ABSTAINED` |
| `timestamp` | `U64` | 마이크로초 UTC | 발생 시각 |
| `payload` | `Json` | 선택적 상세 | `assetId`, `abstainReason`, `error` 등 |

**불변식**:
- 이벤트는 상태 전이 시점에 **단 한 번** 발행된다.
- `Last-Event-ID` 기반 replay 시 누락 없이 재전달된다(RJ-AC04).

---

## 6. AuthorizationToken

잡 파이프라인 각 단계에서 재사용되는 단기 권한 토큰(NFR-Q7).

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `token` | `Ref` | HS256 서명, 1분 TTL | `AuthorizationService`가 발급 |
| `caller` | `Ref` | 계정 UID | 호출자 |
| `jobId` | `Ref` | 대상 잡 ID | 권한 대상 |
| `actions` | `List<Enum>` | `SUBMIT`, `ENQUEUE`, `EXECUTE`, `STATUS`, `EVENT`, `ASSET` | 허용 액션 집합 |
| `expiresAt` | `U64` | 마이크로초 UTC | 만료 시각 (발급 + 1분) |

**불변식**:
- 토큰은 1분 TTL 후 자동 만료, 재발급 필요.
- `AuthzCache`(1분 TTL)로 DB round-trip 최소화(NFR-Q7).

---

## 7. RateLimitBucket

Client identity별 토큰 버킷(NFR-Q10).

| 속성 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `identity` | `Ref` | `user:{uid}` \| `ip:{hash}` | 인증된 사용자 또는 익명 IP 해시 |
| `taskType` | `Enum` | `TRANSLATE`, `SUMMARIZE`, `NOVELTY`, `EVIDENCE` | 작업 유형별 별도 버킷 |
| `tokens` | `U64` | 현재 토큰 수 | 리필 알고리즘에 따라 변동 |
| `maxTokens` | `U64` | 버킷 용량 | task type별 설정 |
| `refillRate` | `U64` | 초당 리필량 | 지속 가능한 처리율 |
| `lastRefill` | `U64` | 마이크로초 UTC | 마지막 리필 시각 |

**불변식**:
- 인증된 사용자: `user:{uid}`, 익명: `ip:{sha256(ip)[:16]}`.
- 동일 identity는 동일 버킷 공유, spoofing 불가(NFR-Q10).

---

## 8. TimeoutProfile

Task type별 동기/비동기 임계값 및 레이어별 timeout 역산표(NFR-Q11, CG-Q4).

| Task Type | 동기 임계값(문자 수) | 모델 p95(초) | Worker timeout(초) | API timeout(초) | BFF timeout(초) | Browser timeout(초) |
|---|---|---|---|---|---|---|
| `TRANSLATE` | 12,000 chars | 6s | 8s | 10s | 12s | 15s |
| `SUMMARIZE` | 8,000 chars | 6s | 8s | 10s | 12s | 15s |
| `NOVELTY` | 16,000 chars | 10s | 14s | 18s | 22s | 30s |
| `EVIDENCE` | 20,000 chars | 12s | 16s | 20s | 24s | 30s |

**불변식**:
- 동기 경로: 브라우저 timeout 내 완료 보장(임계값 이하 입력).
- 비동기 경로: 임계값 초과 입력 → job 접수(202) → SSE/폴링으로 완료 대기.
- 각 레이어 timeout = 하위 레이어 timeout + 여유(2~4초).

---

## 9. CanonicalPaperRegistry

`paperId` + `version` → `canonical_paper_id` + `source_tier` 정규화 서비스(FD-Q2, ND-Q1).

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `resolve(paperId, version)` | `(paperId: Ref, version: U64) -> (canonicalId: Ref, sourceTier: Enum)` | canonical identity 확정. `arxiv:{id}`, `semantic:{id}`, `openalex:{id}`, `userdoc:{owner}:{docId}` 중 하나로 정규화. |
| `getSourceTier(canonicalId)` | `(canonicalId: Ref) -> Enum` | source tier 반환 (`ARXIV_HTML` > `SEMANTIC_SCHOLAR_PDF` > `OPENALEX_PDF` > `USER_UPLOAD` 순위). |

**불변식**:
- 동일 `paperId`+`version`은 항상 동일 `canonicalId` 반환(결정론적).
- `sourceTier`는 품질 순위로 고정, client 제공 source 무시(FD-Q2).

---

## 10. IdempotencyKeyGenerator

ContentJob 멱등성 키 생성기(ND-Q6).

```python
def generate_idempotency_key(
    canonical_paper_id: str,
    task_type: TaskType,
    input_data: bytes,
    params: JobParams
) -> str:
    input_hash = sha256(input_data).hexdigest()[:16]
    params_hash = sha256(canonical_json(params)).hexdigest()[:16]
    return f"content:{canonical_paper_id}:{task_type.value}:{input_hash}:{params_hash}"
```

**불변식**:
- 동일 `(canonical_paper_id, task_type, input_hash, params_hash)` → 동일 키.
- `params`는 persona, target_lang 등 실행 파라미터를 포함.
- 키로 기존 job 조회 → 존재 시 기존 `jobId` 반환(RJ-AC06).
