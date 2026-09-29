# 전체 기능 및 요구사항 검증 계획 — 2026-09-18

## 목적과 기준

- 사용자 요청: "First, understand the project. After understanding the project, Check whether all functions are working correct and satisfies all requirements."
- 기준 커밋: `32a424d` (`develop`), 시작 시 작업 트리 clean.
- 기존 AI-DLC 구현의 Build and Test 검증을 재개한다. 승인된 요구사항과 후속 결정, 현재 코드, 실제 검사 결과를 대조한다.
- 요구사항 기준: `aidlc-docs/inception/requirements/requirements.md`, 관련 유닛의 비즈니스 규칙 및 후속 결정.
- 결과는 실제 검증 통과, 확인된 결함, 부분 검증, 환경/외부 서비스로 인한 미검증, 의도된 제외/보류를 구분한다.
- 확장: Security Full, Resiliency Full, PBT Partial. Agent Chat의 별도 Full PBT 결정도 확인한다.

## 실행 순서

- [x] 1. 공통 규칙, 확장 설정, 기존 AI-DLC 상태, Git 기준선을 확인한다.
- [x] 2. 제품 요구사항, 현재 아키텍처, 런타임 구성과 테스트 레인을 파악한다.
- [x] 3. 활성 기능 요구사항 전체를 코드와 테스트에 매핑하고 주요 통합 흐름을 검토한다.
- [x] 4. Python 테스트 레인과 계약 생성 드리프트 검사를 실행하고 실패/skip 원인을 확인한다.
- [x] 5. 프론트엔드 타입·린트·단위 테스트·프로덕션 빌드·브라우저 테스트를 실행한다.
- [x] 6. 추가 통합/인프라/성능 검사 가능성을 확인하고 재현 가능한 결함을 검증한다.
- [x] 7. 요구사항별 증거, 우선순위별 결함, 확장 규칙 평가, 미검증 항목을 보고서에 기록한다.
- [x] 8. 감사 로그와 상태를 갱신하고 최종 Git diff를 확인한다.

## 검증 원칙

- 모킹된 테스트 통과를 실서비스 동작 보장으로 해석하지 않는다.
- 과거 문서의 완료 표기를 현재 실행 증거로 대체하지 않는다.
- 요구사항 변경/보류 결정은 출처와 함께 기록한다.
- PBT 실행은 고정 seed `20260918`을 사용해 재현성을 확보한다.
- 생성 문서는 일반 Markdown으로 검증하며, 복잡한 시각화 대신 텍스트를 사용한다.

## 환경 발견 및 실행 격리

- `ops/server/README.md`에 따르면 2026-08-17 AWS 폐기 이후 현재 Mac이 운영 서버다. 로컬 Postgres/Redis/OpenSearch/MinIO/ElasticMQ 컨테이너가 실제 실행 중이다.
- 애플리케이션 빌드와 테스트는 HEAD `32a424d`의 detached worktree `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/docsuri-verification-20260918`에서 수행한다.
- Python은 현재 애플리케이션 인터프리터와 같은 3.13을 사용하고, 별도 가상환경에서 frozen lock 설치를 확인한다. 운영 `.env`는 테스트에 로드하지 않는다.
- 라이브 검증은 우선 헬스·공개 읽기 경로의 제한된 프로브로 수행하며, 브라우저 테스트는 별도 로컬 포트를 사용한다.

## 중간 실행 결과

- Python: backend 451 passed/1 skipped, shared 73 passed, ingestion 317 passed/1 skipped, discovery 124 passed/1 skipped, summarization 298 passed/3 skipped, ops 53 passed, root accounts/library 185 passed. 합계 1,501 passed/6 skipped.
- 6 skips는 provider/OpenSearch/Postgres/Bedrock 등 opt-in 통합 환경에 해당한다. shared Python 생성 드리프트 검사는 `uv run --frozen --no-sync python tools/generate.py --check`로 통과했다.
- 기존 CI Python ruff 7개 레인 전부 통과. 프론트엔드 TypeScript·ESLint·Vitest 338개·Next.js production build 통과.
- 프론트엔드 타입 생성은 library schema의 원격 `$ref` fetch에 실패해 해당 스키마를 건너뛰어도 exit 0이다. 생성/빌드 성공만으로 계약 전수 검증을 주장할 수 없다.
- 운영 헬스·14개 모듈 mount·공개 BFF health는 통과. 별도 라이브 검색 프로브에서 10초 임베딩 실패/lexical-only 및 테스트 fixture 논문 노출을 확인했으며 원인·영향을 추가 검증 중이다.
- 브라우저: 격리 포트 3109에서 WebKit 기존 E2E 3개 통과. 첫 실행의 브라우저 바이너리 누락은 임시 디렉터리 설치로 해소했다.
- 격리 Postgres 컨테이너(15439)에서 기존 asset 저장/읽기 통합 테스트 3개 추가 통과. Python 고유 통과 수는 1,504개로 증가했고, 외부 서비스 미검증은 별도 유지한다.
- 라이브 임베딩은 초기 timeout 뒤 warm 상태로 회복했다. 회복 후 한국어 질의와 무관한 음식 질의 모두 11개 결과를 반환했고, 공개 BFF 결과에도 fixture 논문들이 존재했다. 초기 지연과 현재 가용성을 구분해 보고한다.
- 합성 반례: userdoc 교차 사용자 읽기·공유 번역 캐시 오염·12초 요약 응답의 BFF 10초 504·서로 다른 클라이언트 IP 전달 누락 등 4개 추가 테스트가 요구사항 기대값에 대해 실패했다.
- 의존성 감사: frontend production tree 34건(critical 2/high 22/moderate 10), backend cryptography 1개 고유 advisory(출력 2행), ingestion 4개 패키지 30개 출력 항목(중복 advisory 포함), ops 알려진 취약점 없음. 적용 조건과 실제 공격 가능성은 별도 구분한다.
- 운영 인벤토리: OpenAPI 82 paths/101 operations, 14 mounted modules. 현재 read alias `docsuri-corpus`는 `docsuri-corpus-v3`를 가리키며 599 chunks/11 distinct paper IDs, 연도 집계에 2025/2026 논문 없음.
- 격리 PostgreSQL 컨테이너는 검증 후 정상 종료·자동 제거했다. 최종 보고서/반례 문서를 작성했고 활성 FR 47행을 확인했다.
- 감사 worktree의 변경이 직접 만든 합성 테스트/config 4개뿐임을 확인한 후 worktree를 제거했다. 최종 운영 readyz는 14 mounted/0 skipped/0 blocking이다.
- 주 checkout은 보고서/재현 기록/계획/상태/감사 로그/기존 요약 등 문서 6개 변경만 있다. 최종 판정은 **CHANGES REQUIRED**, 검증 수행은 완료다.
