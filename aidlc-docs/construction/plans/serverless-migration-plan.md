# 풀 서버리스 인프라 마이그레이션 계획 (Serverless Migration Plan)

**작성일**: 2026-08-04 · **상태**: 🔶 질문 게이트 대기 (SQ1~SQ6) · **트리거**: 사용자 지시 "현행 AWS 아키텍처 → full serverless 이행 검토" · **대상**: `ops/cdk/app.py` + `stacks/{network,search,compute,frontend,ingestion,evidence,novelty,summarization}_stack.py` (8개 스택) · **방법론**: 감사 → 목표 매핑 → 컴포넌트별 경제성 분석 → 단계화 — **"서버리스가 이기는 곳만 옮기고, 최소 과금 바닥(floor)이 있는 곳은 정직하게 거부"**가 본 계획의 원칙.

---

## §1 감사 — 현행 형상 (사실 관계, 결정 불요)

| 스택 | 리소스 | 상시 여부 | 근거 |
|---|---|---|---|
| Network | VPC 2AZ, **nat_gateways=0**, Fargate=퍼블릭 서브넷, 데이터스토어=isolated | — | `network_stack.py:20` |
| Search | OpenSearch 2.19, **m6g.large.search ×2 + 200GB gp3 ×2**, VPC isolated, k-NN 1024-dim HNSW+BM25, on_disk 4x 압축 | 상시 | `search_stack.py:36-56` |
| Compute | RDS PG16 **t4g.small Multi-AZ** 20GB (`compute_stack.py:132-146`) · Redis **t4g.micro ×2** TLS (`:181-194`) · API Fargate **1vCPU/2GB ×2, max 6** FastAPI 모듈러 모놀리스 + ALB + CloudFront (`:459-505,801-824`) · U9 정리/계정 퍼지 = **EventBridge 스케줄 ECS 태스크 2종** (`:713-740,754-776`) | 상시 | |
| Frontend | Next.js SSR Fargate **0.5vCPU/1GB ×2** + ALB + CloudFront(apex), `output:'standalone'` | 상시 | `frontend_stack.py:186-207`, `next.config.mjs:10` |
| Ingestion | 워커 3종 **scale-to-zero**: harvester(2vCPU/8GB/80GB disk + GROBID ~20GB 사이드카), docmodel-builder(0.5/1GB), userdoc-builder(2/8GB+GROBID) — SQS 깊이 스케일링 min 0 | **0** | `ingestion_stack.py:255-260,341,384,398-432,443-448` |
| Evidence/Novelty/Summarization | 워커 3종 **scale-to-zero** 0.5vCPU/1GB, SQS 가시성 각 900s/3600s/900s | **0** | `evidence_stack.py:53,106`, `novelty_stack.py:50,121`, `summarization_stack.py:102,173` |

**감사 노트 (이행 시 필수 정정)**: ① `app.py:25`는 개인 계정 `559352512800`을 겨냥하지만 `ingestion_stack.py:69-78` · `summarization_stack.py:59-68`은 **구 계정(028317349537)의 RDS 엔드포인트/SG/시크릿 ARN을 하드코딩** — 어떤 DB 이행이든 이 두 파일이 함께 깨진다(사실상 Phase 1 강제 동반 수정). ② 프런트 뷰어 인증서도 구 계정 ARN(`frontend_stack.py:75`). ③ 현행 CDK에는 dev/prod 프로파일 스위치가 **없다** — 아래 비용표의 "dev 프로파일"(t3.small.search ×1+50GB, t4g.micro single-AZ, 태스크 1개씩)은 계정 이전 후 축소 운영 기준선으로, 프로파일 컨텍스트 도입 자체가 Phase 1 산출물이다.

**이미 서버리스인 것**: SQS·EventBridge·S3·SES·CloudWatch·CloudFront — 그리고 **scale-to-zero Fargate 워커 6종**. desired_count=0 + SQS 스케일링은 유휴 $0, 사용량 과금이며 지속 실행 구간의 vCPU 단가는 Lambda보다 오히려 싸다(Fargate 0.5vCPU/1GB ≈ $0.028/hr vs Lambda 1GB 상시환산 ≈ $0.060/hr). **이 6종을 Lambda로 옮겨서 얻는 비용 이득은 ≈ $0**이고, 남는 차이는 웨이크업 지연(Fargate 태스크 기동 30~60s vs Lambda 콜드 1~3s)뿐이다.

## §2 목표 매핑 — "full serverless"의 실제 의미

| 분류 | 대상 | 판단 |
|---|---|---|
| ✅ 서버리스가 이김 (유휴 지배적) | API Fargate ×2($83/mo)+ALB, 프런트 Fargate ×2($41)+ALB, RDS Multi-AZ, 스케줄 ECS 태스크 2종 | 이행 |
| ⚪ 이미 서버리스 가격 | 워커 6종, SQS/EventBridge/S3/SES | 형태만 선택 (이행 무의미) |
| ❌ 최소 과금 바닥이 역효과 | **OpenSearch Serverless**(최소 ~2 OCU ≈ $350+/mo vs dev 노드 $33), **ElastiCache Serverless**(≈$0.084/hr ≈ $61/mo vs t4g.micro $15) | 거부, 대안 검토 |

## §3 컴포넌트별 분석

### §3.1 API — Fargate → Lambda (Mangum/LWA) 또는 App Runner

- **패키징**: `output` 컨테이너 그대로 **LWA(Lambda Web Adapter)** 권장 — Mangum 재작성 없이 uvicorn 기동. 단 모놀리스 임포트 그래프(11개 모듈 마운트, `backend/wiring.py`)로 콜드 스타트 **3~8s** 예상. 완화: provisioned concurrency 1 (≈$3.5/mo, 1GB) 또는 SnapStart(Python 지원 확인 필요).
- **기동 부작용**: 앱이 시작 시 자체 마이그레이션 실행(`compute_stack.py:199-200`) — Lambda에선 콜드마다 마이그레이션 체크가 돈다. **분리된 마이그레이션 스텝으로 이관 필수**.
- **⚠ VPC 이그레스 함정 (본 절 최대 리스크)**: OpenSearch·RDS·Redis가 isolated 서브넷이라 API Lambda는 **VPC 내부 필수** → NAT 없는 현 설계(`network_stack.py:20`)에서 VPC Lambda는 **인터넷/Bedrock/SES/arXiv 접근 불가**. 해법 = NAT GW(서울 $0.059/hr ≈ **$43/mo**+데이터) 또는 인터페이스 엔드포인트 다발(Bedrock·SES·SQS·CW logs/metrics·Secrets ≈ 6개 × $9/mo ≈ $55) — **API Lambda 절감분($83+ALB $22 → $3)의 절반을 도로 낸다**. S3/DynamoDB는 게이트웨이 엔드포인트 무료.
- **SSE/스트리밍**: evidence 스트리밍(`backend/modules/evidence/streaming.py`)은 Lambda **Function URL response streaming**(20MB/15min 한도)으로 가능 — API GW는 스트리밍 불가이므로 **Function URL + CloudFront(OAC + 기존 X-Origin-Verify 대체)** 구성. 실효 제약은 Lambda가 아니라 이미 존재하는 상류 타임아웃: CloudFront read_timeout 60s(`compute_stack.py:806-815`), BFF SSE 프록시 15s·evidence 홉 90s(`frontend/app/bff/[...path]/route.ts:20-24`). NFR-P6("짧은 질의 스트리밍 우선, 긴 분석은 비동기 잡+폴링", `requirements.md:119`)의 폴링 전환은 코드 주석에도 "근본 해결"로 명시돼 있어(`frontend_stack.py:301-304`) Lambda 이행과 독립적으로 정답이다. 15min/20MB는 60s 엣지 타임아웃보다 훨씬 크므로 **비구속**.
- **대안 App Runner**: 컨테이너 무수정 + 자체 퍼블릭 이그레스(NAT 불요) + VPC 커넥터로 데이터스토어 접근. 유휴 시 메모리 과금만(2GB ≈ $10/mo) — Lambda보다 비싸지만 NAT $43이 필요 없어 **총액은 비슷**하고 리스크가 낮다. SQ2/SQ6에서 결정.

### §3.2 워커 — SQS→Lambda 매핑 (15분 상한 대조)

| 워커 | 실측/설계 상한 | Lambda 적합성 | 결론 |
|---|---|---|---|
| novelty | Bedrock 호출 2회 × read_timeout **600s**(`novelty/adapters.py:1695-1697`) + 재시도, 큐 가시성 **3600s**(`novelty_stack.py:50`) | 15min 초과 가능 | **Fargate 유지** (또는 Step Functions 분해 — 호출 1회=1스텝이면 가능하나 코드 재구조화 비용 > 이득 $0) |
| evidence | 가시성 900s(`evidence_stack.py:53`) = Lambda 상한과 동률, DLQ 자가-드레인 루프(BR-EV-12, `:88-89,137-138`)는 이벤트소스 매핑으로 재현 곤란 | 경계선 | **Fargate 유지** |
| summarization | 가시성 900s, map-reduce N+1 LLM 호출(`summarization_stack.py:102`) | 재시도 포함 초과 가능 | **Fargate 유지** (분해 시 SFn Map 후보) |
| ingestion harvester | 2vCPU/8GB/**80GB disk** + GROBID **~20GB** 이미지(`ingestion_stack.py:252-260`), 31.8k-잡 드레인 = 일 단위(`:316-319`) | 이미지 10GB·/tmp 10GB·15min 전부 초과 | **Fargate 유지** (대안 AWS Batch on Fargate — 이득 없음) |
| userdoc-builder | GROBID 사이드카 동일 | 동일 | **Fargate 유지** |
| docmodel-builder | 0.5/1GB, 가시성 300s(`:139`), GROBID-free | **적합** (arXiv 1req/3s 리미터도 잡 단위론 수분 내) | 이행 **가능**하나 §1대로 이득 ≈ $0 — 웨이크업 지연 단축이 필요할 때만 |
| U9 정리·계정 퍼지 (스케줄 ECS ×2) | 단발 수 분, 멱등(`compute_stack.py:708-776`) | **최적** | **Lambda 이행 권장** — EventBridge cron→Lambda가 자연스럽고, API 모놀리스 이미지 기동보다 가볍다 |

### §3.3 검색/벡터 — OpenSearch Serverless는 비용 함정

- 코퍼스: Cohere Embed Multilingual v3, **1024-dim cosine**(`shared/vector-spec/vector-spec.yaml`), 풀바디 멀티청크 인덱싱으로 50GB 도메인을 flood-stage까지 채워 200GB/노드로 증설한 이력(`search_stack.py:47-52`) — 벡터 수는 수십만~저수백만 청크 급.
- **AOSS**: 최소 OCU 바닥 = 표준 ~2 OCU(색인+검색) ≈ **$350+/mo**(서울, $0.24+/OCU-hr), dev/test 0.5+0.5 OCU 옵션이어도 ≈ $175/mo — **dev 노드 $33/mo의 5~10배**. 거부.
- 대안: **A) 관리형 소형 노드 유지**(t3.small.search+50GB ≈ $33 — 단 200GB로 큰 현 코퍼스는 재색인·프루닝 필요) / **B) pgvector on Aurora**(1M×1024-dim ≈ 4GB+HNSW, dev QPS엔 충분하나 **BM25 하이브리드**(`search_stack.py:3`)를 앱에서 재구현해야 함 — U2 검색 계약 재작업) / **C) S3 Vectors(2025 preview)**: 최저가지만 BM25 없음+지연 수백 ms — 하이브리드 요구와 상충 / D) 외부 SaaS(Zilliz/Pinecone free tier) — 데이터 주권·VPC 이탈. **권장 A** (SQ1).

### §3.4 RDS → Aurora Serverless v2 (0 ACU scale-to-zero)

- 이행 = 스냅샷 → Aurora PG16 복원 (+§1 감사 노트 ①의 구 계정 DSN 하드코딩 동시 수정).
- 경제성(서울 ≈ **$0.20/ACU-hr** 가정): 유휴 0 ACU + 하루 4h × 1 ACU ≈ **$24/mo** + 스토리지. 현 t4g.small Multi-AZ($64/mo) 대비 승리. **단** min 0.5 ACU 상시 = $73/mo로 **현행보다 비싸다** — scale-to-zero일 때만 이기는 구조. dev 축소안(t4g.micro single-AZ ≈ $15~18 고정, 콜드 없음)과는 사용 시간 6h/일 근방에서 교차.
- **콜드 리줌 ~15s 리스크**: `/readyz` ALB 헬스체크(`compute_stack.py:535`)와 BFF 홉 타임아웃(기본 10s·검색 30s, `route.ts:24-31`)이 첫 요청에서 깨질 수 있다 — 완화: readyz의 DB 프로브 lazy화 + BFF 재시도 1회 또는 업무시간 워머 ping. SQ3에서 수용 여부 결정.

### §3.5 Redis — 바닥 함정 + 실사용 축소

- 실사용: **① accounts 세션 저장소(Fail-Closed** — Redis 다운=로그인 전면 불가, `accounts/models.py:69`, `controller.py:107-116,280-285`) **② API 측 요약 핫캐시**(`summarization/adapters/s3_redis_store.py` — 워커는 S3-only, `summarization_stack.py:152`). 즉 필수 의존은 세션뿐.
- ElastiCache Serverless 최소 ≈ $0.084/hr ≈ **$61/mo** vs 단일 t4g.micro **$15/mo** — 거부. 대안: **A) 단일 노드 유지 $15** / **B) 세션→DynamoDB(TTL) + 핫캐시→S3-only 강등** ≈ $1~2/mo, `accounts/repository/session.py` 어댑터 교체 필요하나 API Lambda의 VPC 의존을 하나 제거(단 OpenSearch·RDS 때문에 VPC 탈출은 못 함). SQ5.

### §3.6 프런트엔드 — Next.js SSR

- `output:'standalone'` + BFF 캐치올(`app/bff/[...path]/route.ts`)이 세션 쿠키를 서버 측에서만 게이트웨이로 중계(SEC-3/12 — 토큰이 클라이언트 JS에 못 들어감) → **정적 export + BFF-less는 보안 심을 부수므로 기각**. BFF는 Node 핸들러라 OpenNext 서버 함수에 그대로 패키징된다(게이트웨이 타임아웃 상수 15s/90s/30s 유지 가능).
- **A) OpenNext/SST → Lambda(스트리밍 Function URL)+CloudFront**: 프런트 Fargate $41+ALB $22 → ≈ $5/mo. 기존 WebCdn 동작(정적 캐시, /auth/social/* 백엔드 오리진, 엣지 에러 페이지 `frontend_stack.py:353-390`)을 OpenNext 배포에 재이식해야 함. **B) Amplify Hosting**: 관리형이나 커스텀 오리진 동작(/auth/social/*)·엣지 에러 제어가 제한적. **권장 A** (SQ4).

## §4 비용표 — 서울, 월간, 가정 명시

가정: Fargate $0.04656/vCPU-hr·$0.00511/GB-hr, Lambda $0.0000167/GB-s, Aurora $0.20/ACU-hr, AOSS $0.24+/OCU-hr, NAT $43/mo, ALB ≈ $22/mo(LCU 포함), 트래픽 = 소규모 팀(월 ~10만 req, 일 4h 활성). 목록가 ±10%.

| 항목 | 현행 prod (배포 형상) | dev 프로파일 (기준선) | **serverless-max** | **hybrid-optimal (권장)** |
|---|---|---|---|---|
| 검색/벡터 | OpenSearch 2×m6g.large+400GB ≈ **$268** | t3.small+50GB **$33** | AOSS 2 OCU **$350** *(dev/test 1 OCU $175)* | 관리형 유지 **$33** |
| DB | t4g.small MAZ **$64** | t4g.micro 1AZ **$17** | Aurora Sv2 0-ACU **$25** | Aurora Sv2 **$25** |
| Redis/세션 | t4g.micro ×2 **$30** | ×1 **$15** | ElastiCache Serverless **$61** | 단일 노드 **$15** *(SQ5=B 시 $2)* |
| API | Fargate ×2 $83 + ALB $22 = **$105** | ×1 **$63** | Lambda $3 + **NAT $43** = $46 | Lambda+NAT **$46** |
| 프런트 | Fargate ×2 $41 + ALB $22 = **$63** | ×1 **$43** | OpenNext **$5** | OpenNext **$5** |
| 워커 6종 | 사용량 **~$5** | ~$5 | Lambda/SFn ~$5 | Fargate 유지 **~$5** |
| 기타 (CF·S3·SQS·SES·CW·R53) | **~$20** | ~$15 | ~$15 | ~$15 |
| **합계** | **≈ $555** | **≈ $191 (실질 $150~180대)** | **X ≈ $505** *(1-OCU 시 $330)* | **Y ≈ $144** *(SQ5=B·SQ3=C 시 ≈ $125)* |

**결론**: "전부 서버리스"는 dev 기준선보다 **2.6~3.3배 비싸다** — OpenSearch($350 vs $33)와 Redis($61 vs $15)의 최소 과금 바닥이 API/DB/프런트의 유휴 절감을 전부 삼킨다. 서버리스는 **API·DB·프런트·스케줄 태스크에서만** 이기고, 그 절감의 절반은 NAT가 회수한다. 권장 종착점은 hybrid-optimal **≈ $125~145/mo**.

## §5 단계 계획 (롤백·유닛·스택 매핑)

| Phase | 내용 | 영향 유닛 / 스택 | 롤백 |
|---|---|---|---|
| **0 준비** | dev/prod 프로파일 컨텍스트 도입, 구 계정 하드코딩 3건 정정(§1 노트), 시작 시 마이그레이션 분리 | 전 유닛 / 전 스택 | 커밋 리버트 (무중단) |
| **1 퀵윈** | ① RDS 스냅샷 → **Aurora Sv2**(min 0 ACU) ② 스케줄 ECS 2종 → **Lambda cron** ③ API → **Lambda(LWA)+Function URL+CloudFront** 카나리(NAT 신설 포함) — 기존 ALB/Fargate 병행 유지 | U2·U3·U4·U7·U8·U9·U10·U11 API 슬라이스 / Compute(분할: Db/ApiLambda), Evidence·Novelty·Summarization·Ingestion(DSN 참조 갱신) | ① 스냅샷 복원 역방향 ② EventBridge 타깃 원복 ③ CloudFront 오리진을 ALB로 즉시 스위치백 |
| **2 워커 선별** | docmodel-builder Lambda 이행은 **웨이크업 지연이 문제일 때만**(이득 $0 명시); NFR-P6 폴링 전환(evidence 턴 비동기화) — 60s 엣지 타임아웃 완화의 근본 해결 | U1·U11·U13 / Ingestion·Evidence·Frontend | SQS 컨슈머 스위치(이벤트소스 매핑 disable → Fargate desired 복원) |
| **3 검색/벡터 결정** | SQ1 확정 실행: 관리형 축소(재색인·코퍼스 프루닝) 또는 pgvector 파일럿. AOSS는 코퍼스/트래픽이 OCU 바닥을 정당화할 때만 재심 | U1·U2 / Search·Ingestion·Compute | 인덱스 alias 스왑 원복(`docsuri-corpus` alias 패턴 기존 보유) |
| **Fargate 잔류 (최종)** | harvester·userdoc(GROBID 20GB/80GB disk), novelty(600s×2+재시도), evidence(900s+DLQ 드레인), summarization(map-reduce) — **이미 유휴 $0이므로 잔류가 곧 서버리스 경제성** | U1·U7·U11·U12 | — |

## §6 질문 게이트 (SQ — 답변 후 Phase 착수)

**SQ1. 검색/벡터 전략** *(§3.3, Phase 3)*
- **A (권장)**: 관리형 OpenSearch 소형 노드 유지(t3.small+50GB, 코퍼스 프루닝/재색인 동반) — Δ 현행 prod 대비 **−$235/mo**, 하이브리드 BM25+kNN 계약 무수정.
- B: AOSS 이행 — Δ **+$317/mo**(vs dev 노드). 운영 무관리 외 이득 없음.
- C: pgvector on Aurora — Δ −$33/mo 추가 절감이나 U2 하이브리드 검색 재구현 리스크.

**SQ2. API 실행체 + SSE 경로** *(§3.1, Phase 1)*
- **A (권장)**: Lambda(LWA) + Function URL 스트리밍 + CloudFront, NFR-P6 폴링 전환을 Phase 2에 병행 — Δ **−$59/mo**(NAT 차감 후), 콜드 3~8s는 PC 1로 완화.
- B: App Runner(컨테이너 무수정, NAT 불요) — Δ −$50/mo 수준, 리스크 최소·"Lambda"는 아님.
- C: Fargate ×1 축소만 — Δ −$42/mo, 마이그레이션 리스크 0.

**SQ3. Aurora scale-to-zero 콜드 리줌(~15s) 수용** *(§3.4, Phase 1)*
- **A (권장)**: min 0 ACU + readyz lazy화 + BFF 1회 재시도 — Δ −$39/mo(vs 현행), 첫 요청 15s 수용.
- B: min 0.5 ACU 상시 — 콜드 없음이나 **$73/mo로 현행보다 비쌈**. 기각 권고.
- C: RDS t4g.micro single-AZ 잔류 — $17/mo 고정·콜드 없음. 활성 6h/일 이상이면 실질 최적.

**SQ4. 프런트 호스팅** *(§3.6, Phase 1~2)*
- **A (권장)**: OpenNext/SST → Lambda+CloudFront(기존 WebCdn 동작 재이식) — Δ **−$58/mo**, BFF 심 보존.
- B: Amplify Hosting — 관리형이나 /auth/social/* 오리진·엣지 에러 제어 제약.
- C: Fargate ×1 축소 — Δ −$20/mo.

**SQ5. Redis/세션 전략** *(§3.5, Phase 1~2)*
- **A (권장)**: 단일 t4g.micro 유지 — Δ −$15/mo, Fail-Closed 세션 경로 무수정(최소 변경).
- B: 세션→DynamoDB(TTL)+핫캐시 S3-only — Δ −$28/mo, `accounts/repository/session.py` 어댑터 교체 필요.
- C: ElastiCache Serverless — Δ **+$31/mo**. 기각 권고.

**SQ6. 이행 순서** *(§5)*
- **A (권장)**: DB 먼저(Phase 1-①) → API 컷오버가 Aurora 위에서 검증됨 → 프런트 → 워커/검색. 각 단계 독립 롤백.
- B: API 먼저 — DB 이행 시 API를 두 번 건드림.
- C: 빅뱅 — 롤백 불가 결합. 기각 권고.

**리뷰 게이트**: SQ1~SQ6 답변 대기. 승인 시 Phase 0 브랜치(`infra/serverless-phase0`)부터 착수 — 본 계획의 비용 수치는 목록가 기반 추정이므로 Phase 0에서 Cost Explorer 실측 4주치로 보정한다.
