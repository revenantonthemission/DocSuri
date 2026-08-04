"""serverless Phase 2/NFR-P6 — research(agent chat) 턴 비동기 잡+폴링 (BR-EV-6 확장).

검증 대상:
- NFR-P6 분기: 첨부 동반(긴 분석) 턴만 비동기 — 유저 메시지 즉시 커밋 + SQS enqueue
  + 잡 ACTIVE(FE 스냅샷 폴링 유도). 짧은 질의는 동기 경로 불변(SSE 스트리밍 우선).
- SSE 표면에서도 비동기 적격 턴은 pending JSON을 반환한다(FE streamAgentTurn
  'json' 아웃컴 — 재전송 없음).
- 워커: surface=research 라우팅, 동기 경로와 동일한 결과 계약(assistant 메시지·첨부
  안내·COMPLETED), 멱등 가드(SQS at-least-once), 오류 종결([error]
  evidence_unavailable, SEC-9), DLQ 드레인(BR-EV-12).
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from docsuri_shared.authz import Principal, UserRole
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.modules.evidence.models import TurnSuccessResult
from backend.modules.evidence.repository import InMemoryEvidenceRepository
from backend.modules.evidence.sessions import controller
from backend.modules.evidence.sessions.jobs import (
    RESEARCH_JOB_SURFACE,
    build_research_job_payload,
    is_async_eligible,
    parse_research_job_payload,
)
from backend.modules.evidence.sessions.models import (
    ChatRole,
    ResearchChatMessage,
    ResearchJob,
    ResearchJobCreateRequest,
    ResearchJobState,
    ResearchMessageCreateRequest,
)
from backend.modules.evidence.sessions.repository import (
    InMemoryResearchRepository,
    SqlResearchRepository,
)
from backend.modules.evidence.sessions.service import ResearchService
from backend.modules.evidence.worker import (
    InvalidWorkerPayload,
    JobProcessingFailed,
    drain_dlq_once,
    process_sqs_payload,
)

# objectKey/paperId 없는 degraded 형상 — U1 canonical-only 방어(ref_from_attachment
# 서버측 uuid5 재유도)를 우회하지 않고 미해석 PDF 안내(US-EV4 2차) 경로를 검증한다.
PDF_ATTACHMENT = {
    'id': 'att-1',
    'name': 'paper.pdf',
    'kind': 'pdf',
    'sizeBytes': 1234,
}


def _principal(user_id: str | None = None) -> Principal:
    return Principal(user_id=user_id or str(uuid4()), role=UserRole.USER)


def _success_result() -> TurnSuccessResult:
    from docsuri_shared._generated.dtos.evidence_schema import (
        EvidenceCoverage,
        EvidenceItem,
        EvidenceResult,
        SourceRef,
    )

    return TurnSuccessResult(
        outcome=EvidenceResult(
            state='ok',
            claims=[
                EvidenceItem(
                    statement='근거 문장',
                    supporting=[
                        SourceRef(
                            paperId='2401.01234',
                            recordRef='rec-1',
                            anchor='s1.p1',
                            quote='supporting quote',
                        )
                    ],
                    conflicting=[],
                )
            ],
            coverage=EvidenceCoverage(paperCount=1, queryUsed='q'),
        ),
        resolved_paper_ids=('2401.01234',),
    )


class _StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def run(self, ctx, request, on_progress=None):
        self.calls.append(request)
        return _success_result()


class _ExplodingOrchestrator:
    def run(self, ctx, request, on_progress=None):
        raise RuntimeError('bedrock down: secret-arn-123')


class _EnqueueRecorder:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def __call__(self, payload: dict) -> None:
        self.payloads.append(payload)


class _FailingEnqueue:
    def __call__(self, payload: dict) -> None:
        raise RuntimeError('sqs unavailable')


# ---------------------------------------------------------------------------
# 단위: jobs.py 페이로드 계약
# ---------------------------------------------------------------------------

def test_payload_roundtrip_and_prior_topic_caps() -> None:
    # Arrange — 12개 topic(상한 8 초과) + 2000자 초과 topic
    long_topic = 'x' * 3000
    prior = tuple(f'topic-{i}' for i in range(11)) + (long_topic,)

    # Act
    payload = build_research_job_payload(
        owner_id='u',
        job_id='j',
        user_message_id='m',
        content='질문',
        attachments=[PDF_ATTACHMENT],
        prior_topics=prior,
        prior_paper_ids=('p1',),
    )
    fields = parse_research_job_payload(payload)

    # Assert — 최근 8건만, 각 2000자 이내(SQS 256KB 방어)
    assert payload['surface'] == RESEARCH_JOB_SURFACE
    assert len(payload['priorTopics']) == 8
    assert payload['priorTopics'][-1] == 'x' * 2000
    assert fields['owner_id'] == 'u'
    assert fields['attachments'] == [PDF_ATTACHMENT]
    assert fields['prior_paper_ids'] == ('p1',)


def test_parse_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError):
        parse_research_job_payload({'surface': RESEARCH_JOB_SURFACE, 'ownerId': 'u'})


def test_async_eligibility_requires_attachments_and_enqueue() -> None:
    dto_with = ResearchMessageCreateRequest(content='질문', attachments=[PDF_ATTACHMENT])
    dto_without = ResearchMessageCreateRequest(content='질문')

    assert is_async_eligible(dto_with, _EnqueueRecorder())
    assert not is_async_eligible(dto_without, _EnqueueRecorder())
    assert not is_async_eligible(dto_with, None)


# ---------------------------------------------------------------------------
# 서비스: NFR-P6 분기 — 첨부 동반 턴만 비동기
# ---------------------------------------------------------------------------

def test_async_turn_enqueues_and_keeps_job_active() -> None:
    repo = InMemoryResearchRepository()
    orchestrator = _StubOrchestrator()
    enqueue = _EnqueueRecorder()
    owner = str(uuid4())

    resp = asyncio.run(
        ResearchService(repo).create_job(
            owner,
            ResearchJobCreateRequest(content='첨부 논문 분석', attachments=[PDF_ATTACHMENT]),
            orchestrator,
            None,
            sqs_enqueue=enqueue,
        )
    )

    # 잡은 ACTIVE로 남아 FE 폴링을 유도하고, orchestrator는 요청 경로에서 돌지 않는다.
    assert resp.state == ResearchJobState.ACTIVE
    assert orchestrator.calls == []
    assert len(enqueue.payloads) == 1
    payload = enqueue.payloads[0]
    messages = repo.list_messages(owner, resp.jobId)
    assert [m.role for m in messages] == [ChatRole.USER]
    assert payload['surface'] == RESEARCH_JOB_SURFACE
    assert payload['researchJobId'] == resp.jobId
    assert payload['userMessageId'] == messages[0].messageId
    assert payload['attachments'] == [PDF_ATTACHMENT]


def test_sync_turn_without_attachments_is_unchanged() -> None:
    repo = InMemoryResearchRepository()
    orchestrator = _StubOrchestrator()
    enqueue = _EnqueueRecorder()
    owner = str(uuid4())

    resp = asyncio.run(
        ResearchService(repo).create_job(
            owner,
            ResearchJobCreateRequest(content='짧은 질의'),
            orchestrator,
            None,
            sqs_enqueue=enqueue,
        )
    )

    assert resp.state == ResearchJobState.COMPLETED
    assert len(orchestrator.calls) == 1
    assert enqueue.payloads == []


def test_attachment_turn_without_enqueue_stays_sync() -> None:
    repo = InMemoryResearchRepository()
    orchestrator = _StubOrchestrator()
    owner = str(uuid4())

    resp = asyncio.run(
        ResearchService(repo).create_job(
            owner,
            ResearchJobCreateRequest(content='첨부 분석', attachments=[PDF_ATTACHMENT]),
            orchestrator,
            None,
        )
    )

    assert resp.state == ResearchJobState.COMPLETED
    assert len(orchestrator.calls) == 1


def test_async_turn_reactivates_completed_job() -> None:
    """멀티턴 — COMPLETED 잡에 새 async 턴이 들어오면 ACTIVE로 되돌린다(mark_active)."""
    repo = InMemoryResearchRepository()
    orchestrator = _StubOrchestrator()
    enqueue = _EnqueueRecorder()
    owner = str(uuid4())

    created = asyncio.run(
        ResearchService(repo).create_job(
            owner, ResearchJobCreateRequest(content='짧은 질의'), orchestrator, None
        )
    )
    assert repo.get_job(owner, created.jobId).state == ResearchJobState.COMPLETED

    asyncio.run(
        ResearchService(repo).add_message(
            owner,
            created.jobId,
            ResearchMessageCreateRequest(content='이 논문도 분석', attachments=[PDF_ATTACHMENT]),
            orchestrator,
            None,
            sqs_enqueue=enqueue,
        )
    )

    assert repo.get_job(owner, created.jobId).state == ResearchJobState.ACTIVE
    assert len(enqueue.payloads) == 1


def test_enqueue_failure_terminalizes_job_with_error_contract() -> None:
    """enqueue 실패 시 잡을 ACTIVE로 방치하면 FE가 영원히 폴링한다 — 오류 계약 종결."""
    repo = InMemoryResearchRepository()
    owner = str(uuid4())

    with pytest.raises(RuntimeError):
        asyncio.run(
            ResearchService(repo).create_job(
                owner,
                ResearchJobCreateRequest(content='첨부 분석', attachments=[PDF_ATTACHMENT]),
                _StubOrchestrator(),
                None,
                sqs_enqueue=_FailingEnqueue(),
            )
        )

    jobs = repo.list_jobs(owner)
    assert jobs[0].state == ResearchJobState.COMPLETED
    messages = repo.list_messages(owner, jobs[0].jobId)
    assert messages[-1].content == '[error] evidence_unavailable'


def test_async_payload_carries_capped_prior_context() -> None:
    repo = InMemoryResearchRepository()
    orchestrator = _StubOrchestrator()
    enqueue = _EnqueueRecorder()
    owner = str(uuid4())

    created = asyncio.run(
        ResearchService(repo).create_job(
            owner, ResearchJobCreateRequest(content='topic-0'), orchestrator, None
        )
    )
    for i in range(1, 10):
        asyncio.run(
            ResearchService(repo).add_message(
                owner,
                created.jobId,
                ResearchMessageCreateRequest(content=f'topic-{i}'),
                orchestrator,
                None,
            )
        )

    asyncio.run(
        ResearchService(repo).add_message(
            owner,
            created.jobId,
            ResearchMessageCreateRequest(content='첨부 분석', attachments=[PDF_ATTACHMENT]),
            orchestrator,
            None,
            sqs_enqueue=enqueue,
        )
    )

    # 이전 유저 질문 10개 중 최근 8개만 싣는다(SQS 256KB 방어).
    assert enqueue.payloads[0]['priorTopics'] == [f'topic-{i}' for i in range(2, 10)]


# ---------------------------------------------------------------------------
# 컨트롤러: SSE 협상 — 비동기 적격 턴은 pending JSON
# ---------------------------------------------------------------------------

def _client(
    monkeypatch,
    principal: Principal,
    repo,
    orchestrator=None,
    sqs_enqueue=None,
) -> TestClient:
    monkeypatch.setenv('RESEARCH_AGENT_ENABLED', 'true')
    app = create_app(Settings(env='test', database_url='sqlite://'))
    app.dependency_overrides[controller.get_principal] = lambda: principal
    app.dependency_overrides[controller.get_repo] = lambda: repo
    if orchestrator is not None:
        app.dependency_overrides[controller.get_evidence_orchestrator] = lambda: orchestrator
    if sqs_enqueue is not None:
        app.dependency_overrides[controller.get_sqs_enqueue] = lambda: sqs_enqueue
    return TestClient(app)


def test_sse_surface_returns_pending_json_for_async_eligible_turn(monkeypatch) -> None:
    principal = _principal()
    repo = InMemoryResearchRepository()
    enqueue = _EnqueueRecorder()
    client = _client(
        monkeypatch, principal, repo, orchestrator=_StubOrchestrator(), sqs_enqueue=enqueue
    )

    resp = client.post(
        '/api/research/jobs',
        json={'content': '첨부 논문 분석', 'attachments': [PDF_ATTACHMENT]},
        headers={'accept': 'text/event-stream'},
    )

    # 스트리밍이 아니라 JSON pending — FE streamAgentTurn은 'json' 아웃컴으로
    # 재전송 없이 그대로 사용하고 스냅샷 폴링으로 넘어간다.
    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('application/json')
    assert resp.json()['state'] == 'active'
    assert len(enqueue.payloads) == 1


def test_sse_surface_still_streams_short_turns(monkeypatch) -> None:
    principal = _principal()
    repo = InMemoryResearchRepository()
    client = _client(
        monkeypatch,
        principal,
        repo,
        orchestrator=_StubOrchestrator(),
        sqs_enqueue=_EnqueueRecorder(),
    )

    resp = client.post(
        '/api/research/jobs',
        json={'content': '짧은 질의'},
        headers={'accept': 'text/event-stream'},
    )

    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('text/event-stream')


def test_add_message_sse_surface_returns_pending_json_when_eligible(monkeypatch) -> None:
    principal = _principal()
    repo = InMemoryResearchRepository()
    enqueue = _EnqueueRecorder()
    client = _client(
        monkeypatch, principal, repo, orchestrator=_StubOrchestrator(), sqs_enqueue=enqueue
    )
    created = client.post('/api/research/jobs', json={'content': '먼저 짧은 질의'})
    job_id = created.json()['jobId']

    resp = client.post(
        f'/api/research/jobs/{job_id}/messages',
        json={'content': '첨부 분석', 'attachments': [PDF_ATTACHMENT]},
        headers={'accept': 'text/event-stream'},
    )

    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('application/json')
    assert resp.json()['role'] == 'user'  # 비동기 — 유저 메시지만 즉시 반환
    assert len(enqueue.payloads) == 1
    detail = client.get(f'/api/research/jobs/{job_id}')
    assert detail.json()['job']['state'] == 'active'


# ---------------------------------------------------------------------------
# 워커: surface=research 처리 — 결과 계약·멱등·오류 종결
# ---------------------------------------------------------------------------

def _job_with_user_message(
    repo: InMemoryResearchRepository, owner: str, content: str = '첨부 분석'
) -> tuple[str, str]:
    job = repo.create_job(ResearchJob(ownerId=owner, title='분석 세션'))
    message = repo.add_message(
        ResearchChatMessage(
            jobId=job.jobId,
            ownerId=owner,
            role=ChatRole.USER,
            content=content,
            attachments=[PDF_ATTACHMENT],
        )
    )
    return job.jobId, message.messageId


def test_worker_routes_research_surface_and_completes_job() -> None:
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job_id, message_id = _job_with_user_message(repo, owner)
    payload = build_research_job_payload(
        owner_id=owner,
        job_id=job_id,
        user_message_id=message_id,
        content='첨부 분석',
        attachments=[PDF_ATTACHMENT],
    )

    process_sqs_payload(
        InMemoryEvidenceRepository(),
        json.dumps(payload),
        orchestrator=_StubOrchestrator(),
        research_repo_factory=lambda: repo,
    )

    messages = repo.list_messages(owner, job_id)
    assistant = [m for m in messages if m.role == ChatRole.ASSISTANT]
    assert assistant, '워커가 assistant 응답을 기록해야 한다'
    assert assistant[0].resolvedPaperIds == ['2401.01234']
    assert json.loads(assistant[0].content)['state'] == 'ok'
    assert repo.get_job(owner, job_id).state == ResearchJobState.COMPLETED
    # PDF DocModel 미해석 첨부 안내(US-EV4 2차) — 동기 경로와 동일 계약.
    from backend.modules.user_docmodel import EVIDENCE_PDF_DEGRADED_NOTICE

    assert messages[-1].content == EVIDENCE_PDF_DEGRADED_NOTICE


def test_worker_skips_duplicate_delivery() -> None:
    """SQS at-least-once — 이미 종결된 잡의 재배달은 결과를 중복 기록하지 않는다."""
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job_id, message_id = _job_with_user_message(repo, owner)
    payload = json.dumps(
        build_research_job_payload(
            owner_id=owner,
            job_id=job_id,
            user_message_id=message_id,
            content='첨부 분석',
            attachments=[PDF_ATTACHMENT],
        )
    )
    orchestrator = _StubOrchestrator()

    process_sqs_payload(
        InMemoryEvidenceRepository(),
        payload,
        orchestrator=orchestrator,
        research_repo_factory=lambda: repo,
    )
    count_after_first = len(repo.list_messages(owner, job_id))
    process_sqs_payload(
        InMemoryEvidenceRepository(),
        payload,
        orchestrator=orchestrator,
        research_repo_factory=lambda: repo,
    )

    assert len(repo.list_messages(owner, job_id)) == count_after_first
    assert len(orchestrator.calls) == 1


def test_worker_skips_missing_job_without_raising() -> None:
    """커밋-후-enqueue 순서상 잡이 없으면 삭제(US-EV8)뿐 — 멱등 스킵(ack)."""
    payload = build_research_job_payload(
        owner_id=str(uuid4()),
        job_id=str(uuid4()),
        user_message_id=str(uuid4()),
        content='첨부 분석',
        attachments=[PDF_ATTACHMENT],
    )

    process_sqs_payload(
        InMemoryEvidenceRepository(),
        json.dumps(payload),
        orchestrator=_StubOrchestrator(),
        research_repo_factory=InMemoryResearchRepository,
    )  # no raise


def test_worker_orchestrator_failure_terminalizes_with_error_contract() -> None:
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job_id, message_id = _job_with_user_message(repo, owner)
    payload = build_research_job_payload(
        owner_id=owner,
        job_id=job_id,
        user_message_id=message_id,
        content='첨부 분석',
        attachments=[PDF_ATTACHMENT],
    )

    with pytest.raises(JobProcessingFailed):
        process_sqs_payload(
            InMemoryEvidenceRepository(),
            json.dumps(payload),
            orchestrator=_ExplodingOrchestrator(),
            research_repo_factory=lambda: repo,
        )

    messages = repo.list_messages(owner, job_id)
    # SEC-9 — 내부 예외 상세는 비노출, 비기술 오류 계약으로만 종결.
    assert messages[-1].content == '[error] evidence_unavailable'
    assert 'secret-arn-123' not in messages[-1].content
    assert repo.get_job(owner, job_id).state == ResearchJobState.COMPLETED


def test_worker_rejects_research_payload_without_wired_repo() -> None:
    payload = build_research_job_payload(
        owner_id='u', job_id='j', user_message_id='m', content='c', attachments=[]
    )

    with pytest.raises(InvalidWorkerPayload):
        process_sqs_payload(
            InMemoryEvidenceRepository(),
            json.dumps(payload),
            orchestrator=_StubOrchestrator(),
        )


def test_worker_rejects_non_object_json_body_as_poison() -> None:
    """배열/스칼라 JSON body는 재배달해도 영원히 실패 — poison(ack) 분류."""
    with pytest.raises(InvalidWorkerPayload):
        process_sqs_payload(
            InMemoryEvidenceRepository(),
            json.dumps(['not', 'an', 'object']),
            orchestrator=_StubOrchestrator(),
            research_repo_factory=InMemoryResearchRepository,
        )


def test_worker_rejects_malformed_research_payload() -> None:
    with pytest.raises(InvalidWorkerPayload):
        process_sqs_payload(
            InMemoryEvidenceRepository(),
            json.dumps({'surface': RESEARCH_JOB_SURFACE, 'ownerId': 'u'}),
            orchestrator=_StubOrchestrator(),
            research_repo_factory=InMemoryResearchRepository,
        )


# ---------------------------------------------------------------------------
# DLQ 드레인 (BR-EV-12) — research 잡 terminal 전이
# ---------------------------------------------------------------------------

class _FakeSqs:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages
        self.deleted: list[str] = []

    def receive_message(self, **_kwargs) -> dict:
        return {'Messages': list(self._messages)}

    def delete_message(self, QueueUrl: str, ReceiptHandle: str) -> None:  # noqa: N803
        self.deleted.append(ReceiptHandle)


class _Hub:
    def __init__(self) -> None:
        self.metrics: list[tuple[str, float, dict]] = []

    def emit_metric(self, name: str, value: float, tags: dict) -> None:
        self.metrics.append((name, value, tags))


def test_dlq_drain_terminalizes_research_job() -> None:
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job_id, message_id = _job_with_user_message(repo, owner)
    payload = build_research_job_payload(
        owner_id=owner,
        job_id=job_id,
        user_message_id=message_id,
        content='첨부 분석',
        attachments=[PDF_ATTACHMENT],
    )
    sqs = _FakeSqs([{'Body': json.dumps(payload), 'ReceiptHandle': 'rh-1'}])
    hub = _Hub()

    drain_dlq_once(
        sqs,
        'dlq-url',
        InMemoryEvidenceRepository,
        observability=hub,
        research_repo_factory=lambda: repo,
    )

    messages = repo.list_messages(owner, job_id)
    assert messages[-1].content == '[error] evidence_unavailable'
    assert repo.get_job(owner, job_id).state == ResearchJobState.COMPLETED
    assert sqs.deleted == ['rh-1']
    assert hub.metrics[0][0] == 'evidence.job.dead_lettered'
    assert hub.metrics[0][2].get('surface') == RESEARCH_JOB_SURFACE


def test_dlq_drain_skips_already_resolved_research_job() -> None:
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job_id, message_id = _job_with_user_message(repo, owner)
    repo.mark_completed(owner, job_id)
    payload = build_research_job_payload(
        owner_id=owner,
        job_id=job_id,
        user_message_id=message_id,
        content='첨부 분석',
        attachments=[PDF_ATTACHMENT],
    )
    sqs = _FakeSqs([{'Body': json.dumps(payload), 'ReceiptHandle': 'rh-2'}])

    drain_dlq_once(
        sqs,
        'dlq-url',
        InMemoryEvidenceRepository,
        research_repo_factory=lambda: repo,
    )

    # 이미 해소된 잡 — 추가 기록 없이 멱등 ack.
    assert len(repo.list_messages(owner, job_id)) == 1
    assert sqs.deleted == ['rh-2']


def test_dlq_drain_drops_non_object_body_without_crashing() -> None:
    """리뷰 발견 회귀 — 배열 JSON body가 .get() AttributeError로 드레인 루프를
    죽이면 안 된다(구 코드는 parse가 catch-all 안에 있어 드롭됐다)."""
    sqs = _FakeSqs([{'Body': json.dumps([1, 2, 3]), 'ReceiptHandle': 'rh-3'}])

    drain_dlq_once(
        sqs,
        'dlq-url',
        InMemoryEvidenceRepository,
        research_repo_factory=InMemoryResearchRepository,
    )  # no raise

    assert sqs.deleted == ['rh-3']


# ---------------------------------------------------------------------------
# 리포지토리: mark_active
# ---------------------------------------------------------------------------

def test_inmemory_repo_mark_active_roundtrip() -> None:
    repo = InMemoryResearchRepository()
    owner = str(uuid4())
    job = repo.create_job(ResearchJob(ownerId=owner, title='t'))

    repo.mark_completed(owner, job.jobId)
    repo.mark_active(owner, job.jobId)

    assert repo.get_job(owner, job.jobId).state == ResearchJobState.ACTIVE


def test_sql_repo_mark_active_roundtrip() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.modules.evidence.sessions.repository import Base

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    owner = str(uuid4())
    with Session(engine) as session:
        repo = SqlResearchRepository(session)
        job = repo.create_job(ResearchJob(ownerId=owner, title='t'))
        repo.mark_completed(owner, job.jobId)
        repo.mark_active(owner, job.jobId)

        assert repo.get_job(owner, job.jobId).state == ResearchJobState.ACTIVE
