"""Research 턴 비동기 잡 페이로드 — serverless Phase 2/NFR-P6 (BR-EV-6 확장).

긴 분석(첨부 PDF 동반) research 턴은 U11 evidence-agent-job-queue를 공유해
비동기 잡+폴링으로 처리한다. 큐 메시지는 ``surface`` 필드로 U11 canonical 턴
페이로드와 구분한다 — 워커(worker.py)가 이 모듈로 파싱하고, API(service.py)가
이 모듈로 직렬화해 양쪽이 한 벌의 계약을 쓴다.
"""

from __future__ import annotations

from typing import Any

RESEARCH_JOB_SURFACE = 'research'

# SQS 메시지 256KB 상한 방어 — 멀티턴 맥락은 최근 질문만 싣는다. 각 topic은
# evidence 계약 상한(EvidenceRequest.topic 2000자)으로 잘라 orchestrator 입력과
# 정합을 맞춘다.
_PRIOR_TOPICS_MAX = 8
_PRIOR_TOPIC_CHARS_MAX = 2000


def is_async_eligible(dto: Any, sqs_enqueue: Any) -> bool:
    """NFR-P6 분기 — 첨부 PDF 동반 턴은 '긴 분석'(DocModel 로드+추출)으로 보고
    비동기 잡+폴링으로 처리한다. 짧은 질의는 동기 SSE 스트리밍 우선(US-EV2)."""
    return sqs_enqueue is not None and bool(getattr(dto, 'attachments', None))


def build_research_job_payload(
    *,
    owner_id: str,
    job_id: str,
    user_message_id: str,
    content: str,
    attachments: list[dict[str, Any]],
    prior_topics: tuple[str, ...] = (),
    prior_paper_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        'surface': RESEARCH_JOB_SURFACE,
        'ownerId': owner_id,
        'researchJobId': job_id,
        'userMessageId': user_message_id,
        'content': content,
        'attachments': [dict(item) for item in attachments],
        'priorTopics': [
            topic[:_PRIOR_TOPIC_CHARS_MAX]
            for topic in prior_topics[-_PRIOR_TOPICS_MAX:]
        ],
        'priorPaperIds': list(prior_paper_ids),
    }


def parse_research_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """워커 입력 검증 — 필수 필드 누락/형상 오류는 ValueError(poison 처리 대상)."""
    owner_id = payload.get('ownerId')
    job_id = payload.get('researchJobId')
    user_message_id = payload.get('userMessageId')
    content = payload.get('content')
    if not owner_id or not job_id or not user_message_id or not content:
        raise ValueError('ownerId, researchJobId, userMessageId, content are required')
    attachments = payload.get('attachments') or []
    if not isinstance(attachments, list) or not all(
        isinstance(item, dict) for item in attachments
    ):
        raise ValueError('attachments must be a list of dicts')
    prior_topics = payload.get('priorTopics') or []
    if not isinstance(prior_topics, list) or not all(
        isinstance(item, str) for item in prior_topics
    ):
        raise ValueError('priorTopics must be a list of strings')
    prior_paper_ids = payload.get('priorPaperIds') or []
    if not isinstance(prior_paper_ids, list) or not all(
        isinstance(item, str) for item in prior_paper_ids
    ):
        raise ValueError('priorPaperIds must be a list of strings')
    return {
        'owner_id': str(owner_id),
        'job_id': str(job_id),
        'user_message_id': str(user_message_id),
        'content': str(content),
        'attachments': [dict(item) for item in attachments],
        'prior_topics': tuple(prior_topics),
        'prior_paper_ids': tuple(prior_paper_ids),
    }
