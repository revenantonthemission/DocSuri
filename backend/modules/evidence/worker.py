"""Evidence Formation Agent — SQS polling worker (BR-EV-6 비동기 잡 경로).

AgentWorker는 SQS에서 메시지를 소비하여 동일한 EvidenceAgentOrchestrator 파이프라인을
실행하고 결과를 RDS evidence_turns에 기록한다.

SQS 메시지 페이로드:
  {
    "ownerId": "<uuid>",
    "sessionId": "<uuid>",
    "turnId": "<uuid>",
    "jobId": "<uuid>",
    "topic": "...",
    "scope": "auto" | "explicit" | "mixed",
    "paperIds": ["..."],
    "attachments": ["attachment-handle", "..."]
  }
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable, Iterable
from typing import Any

from docsuri_shared._generated.dtos.evidence_schema import EvidenceRequest, EvidenceScope

from .models import AgentRunContext, EvidenceTurn, TurnErrorResult, TurnPendingResult
from .orchestrator import EvidenceAgentOrchestrator
from .repository import EvidenceRepository
from .sessions.jobs import RESEARCH_JOB_SURFACE, parse_research_job_payload
from .streaming import _metric

# U16 BR-SB7 spend attribution — strictly best-effort: if the plans module is unavailable
# the null context keeps this worker byte-for-byte equivalent to the pre-U16 behavior.
try:
    from backend.modules.plans.rollup import spend_attribution
except Exception:  # noqa: BLE001 — observation-only wiring must never break the worker
    from contextlib import nullcontext as spend_attribution  # type: ignore[assignment]

log = logging.getLogger('docsuri.evidence.worker')


class InvalidWorkerPayload(ValueError):
    pass


class JobProcessingFailed(RuntimeError):
    pass


class _Message:
    def __init__(self, body: dict[str, Any], receipt_handle: str | None = None) -> None:
        self.body = body
        self.receipt_handle = receipt_handle


def _decode_payload(body: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    return json.loads(body) if isinstance(body, str) else body


def parse_sqs_payload(body: str | bytes | dict[str, Any]) -> dict[str, Any]:
    payload = _decode_payload(body)
    owner_id = payload.get('ownerId') or payload.get('owner_id')
    turn_id = payload.get('turnId') or payload.get('turn_id')
    topic = payload.get('topic')
    if not owner_id or not turn_id or not topic:
        raise InvalidWorkerPayload('ownerId, turnId, topic are required')
    raw_attachments = payload.get('attachments') or []
    if not isinstance(raw_attachments, list):
        raise InvalidWorkerPayload('attachments must be a list')
    attachments: list[str] = []
    for item in raw_attachments:
        if not isinstance(item, str) or not item:
            raise InvalidWorkerPayload('attachments must contain string handles')
        attachments.append(item)
    raw_attachment_docs = payload.get('attachmentDocs') or []
    if not isinstance(raw_attachment_docs, list):
        raise InvalidWorkerPayload('attachmentDocs must be a list')
    attachment_docs = [
        item for item in raw_attachment_docs if isinstance(item, dict)
    ]
    return {
        'owner_id': str(owner_id),
        'session_id': str(payload.get('sessionId') or payload.get('session_id', '')),
        'turn_id': str(turn_id),
        'job_id': str(payload.get('jobId') or payload.get('job_id', '')),
        'topic': str(topic),
        'scope': payload.get('scope', 'auto'),
        'paper_ids': list(payload.get('paperIds') or payload.get('paper_ids') or []),
        'attachments': attachments,
        'attachment_docs': attachment_docs,
    }


def parse_received_messages(
    raw_messages: list[dict[str, Any]],
    *,
    on_poison: Callable[[dict[str, Any]], None],
) -> list[_Message]:
    """SQS receive_message() 원본 응답 → 파싱된 메시지 목록.

    poison message(파싱 불가한 Body) 하나가 예외를 밖으로 전파해 같은 배치의 정상
    메시지까지 unacked로 남기고 crash loop을 유발하던 문제를 방지한다(PR #338 리뷰
    Blocking #3). 실패한 메시지는 즉시 ``on_poison``으로 넘겨 삭제하고, 나머지는 정상
    처리한다.
    """
    messages: list[_Message] = []
    for msg in raw_messages:
        try:
            body = json.loads(msg['Body'])
        except (json.JSONDecodeError, TypeError):
            log.exception(
                'evidence worker: dropping poison message (invalid JSON body), receiptHandle=%s',
                msg.get('ReceiptHandle'),
            )
            on_poison(msg)
            continue
        messages.append(_Message(body, msg.get('ReceiptHandle')))
    return messages


def process_sqs_payload(
    repo: EvidenceRepository,
    body: str | bytes | dict[str, Any],
    *,
    orchestrator: EvidenceAgentOrchestrator,
    user_docmodel: Any = None,
    research_repo_factory: Callable[[], Any] | None = None,
) -> None:
    payload = _decode_payload(body)
    # serverless Phase 2/NFR-P6 — research(agent chat) 긴 분석 턴은 같은 큐를 공유하되
    # `surface` 필드로 라우팅한다(sessions/jobs.py 계약).
    if payload.get('surface') == RESEARCH_JOB_SURFACE:
        if research_repo_factory is None:
            raise InvalidWorkerPayload(
                'research surface job received but research repo is not wired'
            )
        try:
            fields = parse_research_job_payload(payload)
        except ValueError as exc:
            raise InvalidWorkerPayload(str(exc)) from exc
        process_research_job(
            research_repo_factory,
            orchestrator=orchestrator,
            user_docmodel=user_docmodel,
            **fields,
        )
        return
    fields = parse_sqs_payload(payload)
    process_job(repo, orchestrator=orchestrator, user_docmodel=user_docmodel, **fields)


def process_job(
    repo: EvidenceRepository,
    *,
    orchestrator: EvidenceAgentOrchestrator,
    owner_id: str,
    session_id: str,
    turn_id: str,
    job_id: str,
    topic: str,
    scope: str = 'auto',
    paper_ids: list[str] | None = None,
    attachments: list[str] | None = None,
    attachment_docs: list[dict[str, Any]] | None = None,
    user_docmodel: Any = None,
) -> None:
    # 세션 조회 (INV-EV-1: 소유권 확인)
    try:
        session = repo.get_session(owner_id, session_id)
    except KeyError:
        log.warning('evidence job %s: session %s not found or wrong owner', job_id, session_id)
        # turn을 pending으로 방치하면 GET /jobs/{job_id}가 영원히 pending을 반환한다
        # (PR #338 리뷰 Medium #12) — 세션이 소프트 삭제됐거나 소유자가 안 맞아도
        # turn 자체는 여전히 owner_id로 조회·갱신 가능하니 terminal로 전이시킨다.
        try:
            repo.update_turn_result(
                owner_id, turn_id, TurnErrorResult(error_code='session_unavailable')
            )
        except KeyError:
            log.warning(
                'evidence job %s: turn %s also unavailable, nothing to terminate',
                job_id, turn_id,
            )
        return

    # turn 조회 — 이미 완료 상태면 스킵
    turns = repo.list_turns(owner_id, session_id)
    turn: EvidenceTurn | None = next((t for t in turns if t.turn_id == turn_id), None)
    if turn is None:
        log.warning('evidence job %s: turn %s not found', job_id, turn_id)
        return

    # idempotency guard (PR #338 리뷰 Blocking #4): SQS at-least-once 특성상 동일 job이
    # visibility_timeout 초과 등으로 중복 배달될 수 있다. turn이 이미 pending을 벗어나
    # terminal 상태(성공/기권/에러)면 재실행하지 않고 스킵 — orchestrator 이중 실행과
    # update_turn_result의 결과 clobber를 함께 방지한다.
    if not isinstance(turn.result, TurnPendingResult):
        log.info(
            'evidence job %s: turn %s already resolved, skipping duplicate delivery',
            job_id, turn_id,
        )
        return

    request = EvidenceRequest(
        topic=topic,
        scope=(
            EvidenceScope(scope)
            if scope in EvidenceScope.__members__.values()
            else EvidenceScope.auto
        ),
        paperIds=paper_ids or [],
        attachments=attachments or [],
    )
    ctx = AgentRunContext(
        session=session,
        current_turn=turn,
        owner_id=owner_id,
        request_id=job_id,
        budget_signal={},
        attachment_docs=_attachment_inputs(
            owner_id=owner_id,
            scope_id=job_id,
            attachment_docs=attachment_docs or [],
            user_docmodel=user_docmodel,
        ),
    )

    try:
        # U16 BR-SB7: 이 턴의 Bedrock 지출을 소유자에게 귀속(관측 전용 일일 롤업). ops의
        # UsageEvent에는 사용자 문맥이 없어, owner_id가 스코프에 있는 유일한 지점인 여기서
        # contextvar로 흘려보낸다 — 롤업 실패는 record 측에서 삼켜져 턴에 영향이 없다.
        with spend_attribution(owner_id):
            result = orchestrator.run(ctx, request)
    except Exception as exc:
        log.exception('evidence job %s: orchestrator failed', job_id)
        # 검색/LLM 실패는 orchestrator.run() 내부에서 이미 abstain으로 잡아낸다 — 여기까지
        # 올라오는 건 분류되지 않은 예상 밖 실패다. 그런데도 항상 'llm_unavailable'로
        # 못박아 놓으면 원인이 LLM이 아닌 경우에도 사용자에게 오도된 코드가 노출된다
        # (PR #338 리뷰 Medium #11). SEC-9상 원본 예외 메시지는 노출 불가하므로, 비기술
        # 범용 코드로 정직하게 표현한다.
        result = TurnErrorResult(error_code='internal_error')
        repo.update_turn_result(owner_id, turn_id, result)
        repo.commit()
        raise JobProcessingFailed(str(exc)) from exc

    repo.update_turn_result(owner_id, turn_id, result)


def _research_job_awaiting(job: Any, messages: list[Any], user_message_id: str) -> bool:
    """멱등 가드 — 잡이 여전히 이 유저 메시지의 답변을 기다리는 상태인지.

    API는 enqueue 전에 유저 메시지+ACTIVE 전이를 커밋하므로(sessions/service.py),
    (a) 잡이 ACTIVE가 아니거나 (b) 페이로드의 유저 메시지가 마지막 메시지가 아니면
    이미 처리된 중복 배달이다(SQS at-least-once).
    """
    from .sessions.models import ResearchJobState

    if job.state != ResearchJobState.ACTIVE:
        return False
    last = messages[-1] if messages else None
    return last is not None and last.messageId == user_message_id


def process_research_job(
    research_repo_factory: Callable[[], Any],
    *,
    orchestrator: EvidenceAgentOrchestrator,
    owner_id: str,
    job_id: str,
    user_message_id: str,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
    prior_topics: tuple[str, ...] = (),
    prior_paper_ids: tuple[str, ...] = (),
    user_docmodel: Any = None,
) -> None:
    """serverless Phase 2/NFR-P6 — 긴 분석(첨부 동반) research 턴의 워커 실행.

    동기 경로(sessions/service.add_message)와 동일한 결과 계약으로 assistant
    메시지·첨부 안내·COMPLETED 전이를 기록한다. 잡/메시지가 안 보이면 커밋-후-enqueue
    순서상 삭제(US-EV8)뿐이므로 멱등 스킵(ack)한다.
    """
    from .sessions.models import ChatRole, ResearchChatMessage
    from .sessions.service import (
        _attachment_notice,
        _format_turn_result,
        _resolved_paper_ids,
        run_research_turn_sync,
    )

    repo = research_repo_factory()
    try:
        try:
            job = repo.get_job(owner_id, job_id)
            messages = repo.list_messages(owner_id, job_id)
        except KeyError:
            log.warning('research job %s: not found or wrong owner; skipping', job_id)
            return
        if not _research_job_awaiting(job, messages, user_message_id):
            log.info(
                'research job %s: message %s already handled; skipping duplicate delivery',
                job_id, user_message_id,
            )
            return

        attachment_inputs = _attachment_inputs(
            owner_id=owner_id,
            scope_id=job_id,
            attachment_docs=list(attachments or []),
            user_docmodel=user_docmodel,
        )
        try:
            # U16 BR-SB7 — 턴의 Bedrock 지출 귀속(evidence 턴 경로와 동일 컨텍스트).
            with spend_attribution(owner_id):
                result = run_research_turn_sync(
                    orchestrator,
                    owner_id=owner_id,
                    topic=content,
                    prior_topics=tuple(prior_topics),
                    attachment_inputs=attachment_inputs,
                    prior_paper_ids=tuple(prior_paper_ids),
                )
        except Exception as exc:
            log.exception('research job %s: orchestrator failed', job_id)
            # 잡을 ACTIVE로 방치하면 FE가 영원히 폴링한다 — 동기 경로의 오류 계약
            # ([error] evidence_unavailable, SEC-9 내부 상세 비노출)로 종결한다.
            repo.add_message(
                ResearchChatMessage(
                    jobId=job_id,
                    ownerId=owner_id,
                    role=ChatRole.ASSISTANT,
                    content=_format_turn_result(None),
                    attachments=[],
                )
            )
            repo.mark_completed(owner_id, job_id)
            repo.commit()
            raise JobProcessingFailed(str(exc)) from exc

        repo.add_message(
            ResearchChatMessage(
                jobId=job_id,
                ownerId=owner_id,
                role=ChatRole.ASSISTANT,
                content=_format_turn_result(result),
                attachments=[],
                resolvedPaperIds=list(_resolved_paper_ids(result)),
            )
        )
        # US-EV4(#268) 2차 — 본문 없이 도착한 첨부는 비기술 문구로 별도 안내(동기 경로 동일).
        notice = _attachment_notice(attachment_inputs)
        if notice:
            repo.add_message(
                ResearchChatMessage(
                    jobId=job_id,
                    ownerId=owner_id,
                    role=ChatRole.ASSISTANT,
                    content=notice,
                    attachments=[],
                )
            )
        repo.mark_completed(owner_id, job_id)
        repo.commit()
    except JobProcessingFailed:
        raise
    except Exception:
        rollback = getattr(repo, 'rollback', None)
        if rollback is not None:
            rollback()
        raise
    finally:
        close = getattr(repo, 'close', None)
        if close is not None:
            close()


def run_worker(
    *,
    repo_factory: Callable[[], EvidenceRepository],
    orchestrator: EvidenceAgentOrchestrator,
    receive: Callable[[], Iterable[_Message]],
    ack: Callable[[_Message], None],
    should_stop: Callable[[], bool],
    user_docmodel: Any = None,
    drain_dlq: Callable[[], None] | None = None,
    research_repo_factory: Callable[[], Any] | None = None,
) -> None:
    while not should_stop():
        if drain_dlq is not None:
            drain_dlq()  # BR-EV-12 — DLQ로 빠진 잡의 turn을 pending에 방치하지 않는다
        for message in receive():
            repo = repo_factory()
            try:
                process_sqs_payload(
                    repo,
                    message.body,
                    orchestrator=orchestrator,
                    user_docmodel=user_docmodel,
                    research_repo_factory=research_repo_factory,
                )
                commit = getattr(repo, 'commit', None)
                if commit is not None:
                    commit()
            except JobProcessingFailed:
                commit = getattr(repo, 'commit', None)
                if commit is not None:
                    commit()
                log.exception('evidence job failed; committed error state')
            except InvalidWorkerPayload:
                # poison payload: 구조가 잘못된 메시지는 재배달해도 영원히 실패한다 —
                # on_poison의 JSON-decode 처리와 동일하게 즉시 ack(삭제)로 종결한다.
                log.exception(
                    'evidence worker: dropping poison message (invalid payload shape)'
                )
            except Exception:  # noqa: BLE001 — leave unacked for retry/DLQ
                rollback = getattr(repo, 'rollback', None)
                if rollback is not None:
                    rollback()
                log.exception('evidence job failed; leaving message for redelivery')
                continue
            finally:
                close = getattr(repo, 'close', None)
                if close is not None:
                    close()
            ack(message)
            if should_stop():
                break


def drain_dlq_once(
    sqs: Any,
    dlq_url: str,
    repo_factory: Callable[[], EvidenceRepository],
    *,
    observability: Any = None,
    research_repo_factory: Callable[[], Any] | None = None,
) -> None:
    """BR-EV-12 — max_receive_count 소진으로 DLQ에 빠진 잡을 terminal로 전이.

    evidence 턴은 TurnErrorResult(job_failed)를, research 턴(serverless Phase 2)은
    오류 assistant 메시지+COMPLETED 전이를 기록하고 메시지를 삭제한다. 이미 해소된
    잡은 멱등 스킵 후 ack. malformed 메시지는 기록 없이 삭제+로그. RDS 기록 실패
    시에만 메시지를 남겨 다음 폴링에서 재시도한다(infra-design §DLQ).
    """
    resp = sqs.receive_message(QueueUrl=dlq_url, MaxNumberOfMessages=10, WaitTimeSeconds=0)
    for msg in resp.get('Messages', []):
        if not _terminalize_dead_letter(
            msg, repo_factory, research_repo_factory, observability
        ):
            continue  # 기록 실패 — 메시지를 남겨 다음 폴링에서 재시도
        receipt = msg.get('ReceiptHandle')
        if receipt:
            sqs.delete_message(QueueUrl=dlq_url, ReceiptHandle=receipt)


def _terminalize_dead_letter(
    msg: dict[str, Any],
    repo_factory: Callable[[], EvidenceRepository],
    research_repo_factory: Callable[[], Any] | None,
    observability: Any,
) -> bool:
    """DLQ 메시지 1건을 terminal로 전이. False = 기록 실패(메시지 유지)."""
    try:
        payload = _decode_payload(msg.get('Body') or '')
    except Exception:  # noqa: BLE001 — malformed DLQ 메시지는 삭제+로그로 종결
        log.exception(
            'evidence DLQ: dropping malformed message, receiptHandle=%s',
            msg.get('ReceiptHandle'),
        )
        return True
    if payload.get('surface') == RESEARCH_JOB_SURFACE:
        try:
            fields = parse_research_job_payload(payload)
        except ValueError:
            log.exception('evidence DLQ: dropping malformed research message')
            return True
        if research_repo_factory is None:
            log.warning(
                'evidence DLQ: research message but research repo not wired; dropping'
            )
            return True
        try:
            _record_dead_lettered_research_job(research_repo_factory, fields)
        except Exception:  # noqa: BLE001 — 기록 실패는 메시지를 남겨 재시도
            log.exception(
                'evidence DLQ: failed to record job_failed for research job %s; keeping message',
                fields['job_id'],
            )
            return False
        _metric(
            observability,
            'evidence.job.dead_lettered',
            1.0,
            {'errorCode': 'job_failed', 'surface': RESEARCH_JOB_SURFACE},
        )
        return True
    try:
        fields = parse_sqs_payload(payload)
    except Exception:  # noqa: BLE001 — malformed DLQ 메시지는 삭제+로그로 종결
        log.exception(
            'evidence DLQ: dropping malformed message, receiptHandle=%s',
            msg.get('ReceiptHandle'),
        )
        return True
    try:
        _record_dead_lettered_turn(repo_factory, fields)
    except Exception:  # noqa: BLE001 — 기록 실패는 메시지를 남겨 재시도
        log.exception(
            'evidence DLQ: failed to record job_failed for turn %s; keeping message',
            fields['turn_id'],
        )
        return False
    _metric(
        observability,
        'evidence.job.dead_lettered',
        1.0,
        {'errorCode': 'job_failed'},
    )
    return True


def _record_dead_lettered_research_job(
    research_repo_factory: Callable[[], Any],
    fields: dict[str, Any],
) -> None:
    """research 턴 DLQ 종결 — 오류 assistant 메시지 + COMPLETED (동기 오류 계약)."""
    from .sessions.models import ChatRole, ResearchChatMessage
    from .sessions.service import _format_turn_result

    repo = research_repo_factory()
    try:
        try:
            job = repo.get_job(fields['owner_id'], fields['job_id'])
            messages = repo.list_messages(fields['owner_id'], fields['job_id'])
        except KeyError:
            log.warning(
                'evidence DLQ: research job %s unavailable; acking anyway',
                fields['job_id'],
            )
            return
        if not _research_job_awaiting(job, messages, fields['user_message_id']):
            return  # 이미 해소 — 멱등 ack
        repo.add_message(
            ResearchChatMessage(
                jobId=fields['job_id'],
                ownerId=fields['owner_id'],
                role=ChatRole.ASSISTANT,
                content=_format_turn_result(None),
                attachments=[],
            )
        )
        repo.mark_completed(fields['owner_id'], fields['job_id'])
        commit = getattr(repo, 'commit', None)
        if commit is not None:
            commit()
    finally:
        close = getattr(repo, 'close', None)
        if close is not None:
            close()


def _record_dead_lettered_turn(
    repo_factory: Callable[[], EvidenceRepository],
    fields: dict[str, Any],
) -> None:
    repo = repo_factory()
    try:
        try:
            repo.update_turn_result(
                fields['owner_id'],
                fields['turn_id'],
                TurnErrorResult(error_code='job_failed'),
            )
        except KeyError:
            # turn이 없거나 소유자가 다른 잔재 메시지 — 기록할 곳이 없으니 그대로 ack.
            log.warning(
                'evidence DLQ: turn %s unavailable; acking anyway', fields['turn_id']
            )
        commit = getattr(repo, 'commit', None)
        if commit is not None:
            commit()
    finally:
        close = getattr(repo, 'close', None)
        if close is not None:
            close()


_shutdown = threading.Event()


def _on_signal(signum, _frame) -> None:
    log.info('received %s; draining then exiting', signal.Signals(signum).name)
    _shutdown.set()


def main(argv: list[str] | None = None) -> int:
    del argv
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    queue_url = os.getenv('DOCSURI_EVIDENCE_JOB_QUEUE_URL')
    if not queue_url:
        log.error('DOCSURI_EVIDENCE_JOB_QUEUE_URL not set; nothing to consume')
        return 1

    from backend.config import Settings
    from backend.db import make_engine, make_session_factory

    from .real_wiring import build_evidence_orchestrator
    from .repository import SqlEvidenceRepository
    from .settings import EvidenceSettings

    ev_settings = EvidenceSettings.from_env()
    if not ev_settings.evidence_enabled:
        log.error('DOCSURI_DOCMODEL_BUCKET not set; evidence real path not configured')
        return 1

    # NFR-C1: 워커 프로세스별 cost guard (novelty/summarization 워커와 동일 패턴).
    # ponytail: 프로세스별 근사 카운터 — 공유 예산 권위가 생기면 교체.
    from docsuri_ops.cost_guard import CostGuardCircuitBreaker

    bundle = build_evidence_orchestrator(ev_settings, cost_guard=CostGuardCircuitBreaker())
    orchestrator = bundle.orchestrator

    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    def repo_factory() -> EvidenceRepository:
        return SqlEvidenceRepository(session_factory())

    # serverless Phase 2/NFR-P6 — research(agent chat) 긴 분석 턴도 이 워커가 처리한다.
    from .sessions.repository import SqlResearchRepository

    def research_repo_factory() -> Any:
        return SqlResearchRepository(session_factory())

    import boto3

    sqs = boto3.client(
        'sqs',
        region_name=ev_settings.region_name or 'ap-northeast-2',
    )

    def receive() -> list[_Message]:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,
        )
        return parse_received_messages(
            resp.get('Messages', []),
            on_poison=lambda msg: sqs.delete_message(
                QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle']
            ),
        )

    def ack(message: _Message) -> None:
        if message.receipt_handle:
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message.receipt_handle)

    # BR-EV-12: DLQ URL이 배선된 경우에만 소비한다(로컬·테스트 무영향).
    dlq_url = os.getenv('EVIDENCE_DLQ_URL')
    observability = _build_worker_observability() if dlq_url else None

    def drain_dlq() -> None:
        drain_dlq_once(
            sqs,
            dlq_url,
            repo_factory,
            observability=observability,
            research_repo_factory=research_repo_factory,
        )

    log.info('evidence agent worker started; polling queue')
    run_worker(
        repo_factory=repo_factory,
        orchestrator=orchestrator,
        receive=receive,
        ack=ack,
        should_stop=_shutdown.is_set,
        user_docmodel=_build_user_docmodel(),
        drain_dlq=drain_dlq if dlq_url else None,
        research_repo_factory=research_repo_factory,
    )
    log.info('evidence agent worker shut down gracefully')
    return 0


def _build_worker_observability() -> Any:
    """novelty worker의 _build_worker_ops와 동일 관례 — 관측 배선 실패는 워커를 막지 않는다."""
    try:
        from backend.app import _build_observability
    except ImportError:
        return None
    observability, _telemetry_store = _build_observability()
    return observability


def _attachment_inputs(
    *,
    owner_id: str,
    scope_id: str,
    attachment_docs: list[dict[str, Any]],
    user_docmodel: Any,
):
    from .attachments import attachment_inputs_from_dicts

    return attachment_inputs_from_dicts(
        owner_id=owner_id,
        scope_id=scope_id,
        attachments=attachment_docs,
        user_docmodel=user_docmodel,
    )


def _build_user_docmodel():
    from backend.modules.user_docmodel import build_default_user_docmodel_coordinator

    return build_default_user_docmodel_coordinator()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
