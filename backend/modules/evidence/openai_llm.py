"""OpenAICompatEvidenceExtractor — 로컬(OpenAI 호환) LLM용 EvidenceExtractor 형제.

``extractor.EvidenceExtractor``와 동일 계약: ``extract()`` → EvidenceItem 목록, LLM 호출
불가 시 ``LlmUnavailable``(재시도 1회 후) — Orchestrator는 어느 쪽이 배선됐는지 모른다.
``extract()``와 INV-EV-3 날조 검증(``_filter_hallucinated`` 등)은 부모를 그대로 재사용하고
LLM 전송 계층(``_invoke_json``)만 교체한다.

Bedrock 스트림 대신 POST ``{api_base}/chat/completions`` (비스트리밍, OpenAI 호환 —
Ollama ``/v1``·rapid-mlx 어디든 zero code change 스왑). Bedrock 경로가 free-text JSON을
``_parse_json``의 관대한 brace 추출로 파싱하므로(구조화 출력 모드 없음), 여기서도
``response_format``을 싣지 않고 같은 파서를 재사용한다. qwen3 계열이 앞머리에 붙이는
``<think>...</think>`` 블록은 파싱 전에 제거한다. boto3/AWS 의존 없음.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from .extractor import (
    _MAX_RETRIES,
    _MAX_TOKENS,
    EvidenceExtractor,
    LlmUnavailable,
    _LocalCircuitBreaker,
    _parse_json,
)

logger = logging.getLogger(__name__)

# 로컬 8B 추론은 느리다 — 비스트리밍이라 전체 생성이 끝날 때까지 응답이 없다.
# httpx.Timeout(connect=3s, read=300s)로 배선한다(real_wiring 참조).
CONNECT_TIMEOUT_S = 3.0
READ_TIMEOUT_S = 300.0

# 선행 <think> 블록만 벗긴다. 닫는 태그가 없으면(생각 중 잘림) 답이 시작되지 않은
# 것이므로 그대로 두고 _parse_json이 {}를 돌려 abstain 경로를 탄다(기존 계약 동일).
_THINK_RE = re.compile(r'^\s*<think>.*?</think>\s*', re.DOTALL)


def _strip_think(text: str) -> str:
    """qwen3의 선행 ``<think>...</think>`` 블록 제거 — JSON 파싱 전에 반드시 벗긴다."""
    return _THINK_RE.sub('', text, count=1)


class OpenAICompatEvidenceExtractor(EvidenceExtractor):
    """extract()·INV-EV-3 필터는 부모 그대로, LLM 전송 계층만 교체."""

    def __init__(
        self,
        *,
        model: str,
        api_base: str,
        client: Any,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        # 부모 __init__은 client=None이면 boto3 클라이언트를 만들므로 호출하지 않는다
        # (로컬 경로는 AWS 의존 금지). 부모 extract()가 쓰는 속성만 직접 구성한다.
        self._model = model
        self._api_base = api_base.rstrip('/')
        self._client = client  # httpx.Client — 모듈이 이미 쓰는 HTTP 클라이언트 재사용
        self._max_retries = max_retries
        self._cb = _LocalCircuitBreaker()
        # 로컬 추론은 USD 지출이 없다 — NFR-C1 Bedrock 지출 계측은 생략(None 고정).
        self._cost_guard = None

    def _invoke_json(self, system: str, user: str) -> dict:
        if not self._cb.allow_request():
            raise LlmUnavailable('OpenAICompatEvidenceExtractor circuit breaker OPEN')

        body = {
            'model': self._model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            'stream': False,
            'max_tokens': _MAX_TOKENS,
        }
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                time.sleep(2 ** attempt * 0.5)
            try:
                text = self._chat(body)
                payload = _parse_json(text)
                self._cb.record_success()
                return payload
            except Exception as exc:  # noqa: BLE001 — 전송 실패 → 재시도/abstain
                last_exc = exc
        self._cb.record_failure()
        raise LlmUnavailable('OpenAICompatEvidenceExtractor LLM call failed') from last_exc

    def _chat(self, body: dict) -> str:
        """POST ``{api_base}/chat/completions`` → ``choices[0].message.content`` (think 제거).

        ``choices``가 비어 있으면 서버는 살아 있으나 생성이 없는 일시 장애로 간주한다
        (재시도 → LlmUnavailable → Orchestrator fail-closed, BR-EV-12).
        """
        response = self._client.post(f'{self._api_base}/chat/completions', json=body)
        response.raise_for_status()
        parsed = response.json()
        choices = parsed.get('choices') or []
        if not choices:
            raise LlmUnavailable('chat/completions returned no choices')
        content = ((choices[0] or {}).get('message') or {}).get('content') or ''
        return _strip_think(content)
