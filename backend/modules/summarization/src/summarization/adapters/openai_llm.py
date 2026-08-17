"""OpenAICompatLlmGateway — local LLM adapter (OpenAI-compatible ``/chat/completions``).

``bedrock_llm``과 동일한 ``LlmGatewayPort`` 계약: 같은 메서드 시그니처·반환 타입, 실패 시
``LlmUnavailable``(재시도 1회 후) — 오케스트레이터는 어느 어댑터가 배선됐는지 모른다.
Bedrock 경로의 **forced tool call** 대신, 같은 스키마(SSOT: ``prompts.templates``의
``SUMMARY_TOOL``/``TRANSLATE_TOOL``)를 시스템 프롬프트 계약으로 싣고
``response_format={"type": "json_object"}``로 JSON-only 출력을 강제한다(같은 구조화-출력
의도). 파싱 후 형상 가드는 ``bedrock_llm._to_summary_draft``를 그대로 재사용한다.

OpenAI 호환 서버라면 어디든 붙는다(Ollama ``/v1``, rapid-mlx 등 — zero code change 스왑).
qwen3 계열이 응답 앞머리에 붙이는 ``<think>...</think>`` 블록은 JSON 파싱 전에 제거한다
(남기면 다운스트림 JSON 파싱이 통째로 깨진다). boto3/AWS 의존 없음 — 모듈 pyproject에
HTTP 클라이언트 의존성이 없으므로 stdlib ``urllib``만 사용한다.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from collections.abc import Sequence

from ..domain.models import (
    Glossary,
    RefinedSource,
    SummaryDraft,
    SummaryRequest,
    TranslationSegment,
    TranslationSegmentsResult,
)
from ..ports.ports import LlmUnavailable
from ..prompts import (
    SUMMARY_TOOL,
    TRANSLATE_TOOL,
    build_summary_prompt,
    build_translate_segments_prompt,
)
from .bedrock_llm import LocalCircuitBreaker, _to_summary_draft

log = logging.getLogger("docsuri.summarization.openai_compat")

# 로컬 8B 추론은 느리다: 비스트리밍이라 전체 생성이 끝날 때까지 응답이 없다. connect는
# 로컬이라 사실상 즉시(3s면 충분), read는 긴 논문 요약/번역의 전체 생성 시간을 커버해야
# 한다. urllib의 timeout은 connect+read 공용 단일 값이므로 큰 쪽(read)으로 건다 —
# 로컬 서버 connect 실패는 어차피 ECONNREFUSED로 즉시 떨어진다.
_CONNECT_TIMEOUT = 3.0
_READ_TIMEOUT = 300.0

# 선행 <think> 블록만 벗긴다. 닫는 태그가 없으면(생각 중 잘림) 답이 시작되지 않은
# 것이므로 그대로 두고 JSON 파싱 실패 → 재시도/abstain 경로를 탄다.
_THINK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)


def _strip_think(text: str) -> str:
    """qwen3의 선행 ``<think>...</think>`` 블록 제거 — JSON 파싱 전에 반드시 벗긴다."""
    return _THINK_RE.sub("", text, count=1)


def _schema_contract(tool: dict) -> str:
    """Bedrock forced tool의 ``input_schema``를 프롬프트 출력 계약으로 변환.

    스키마 SSOT는 ``prompts.templates``(SUMMARY_TOOL/TRANSLATE_TOOL) 그대로 — 여기서
    필드를 재기술하지 않는다(bedrock_llm과 같은 원칙).
    """
    schema = json.dumps(tool["input_schema"], ensure_ascii=False)
    return (
        "\n\n출력 계약: 아래 JSON Schema를 만족하는 JSON 객체 **하나만** 반환한다."
        " 산문·마크다운 코드펜스·설명 금지.\n"
        f"<output_schema>{schema}</output_schema>"
    )


class OpenAICompatLlmGateway:
    """``LlmGatewayPort`` — OpenAI 호환 로컬 서버용 실 어댑터 (bedrock_llm의 형제)."""

    def __init__(
        self,
        *,
        model: str,
        api_base: str,
        max_retries: int = 1,
        read_timeout: float = _READ_TIMEOUT,
    ) -> None:
        # S310 방어: http(s) 외 스킴(file: 등)으로 urlopen 되는 일이 없도록 조립 시점에 차단.
        if not api_base.startswith(("http://", "https://")):
            raise ValueError(f"api_base must be http(s), got: {api_base!r}")
        self._model = model
        self._api_base = api_base.rstrip("/")
        self._max_retries = max_retries
        self._read_timeout = read_timeout
        self._cb = LocalCircuitBreaker()

    # --- public ports (bedrock_llm과 동일 시그니처) ------------------------------
    def summarize(
        self, refined: RefinedSource, request: SummaryRequest, glossary: Glossary
    ) -> SummaryDraft:
        system, user = build_summary_prompt(refined, request, glossary)
        # 8192 캡 근거는 bedrock_llm.summarize 주석과 동일 — 한국어 출력 + anchor span이
        # 긴 논문에서 기본 캡을 넘어 mid-JSON 잘림 → abstain 되는 것을 막는다.
        payload = self._invoke_json(system, user, SUMMARY_TOOL, max_tokens=8192)
        return _to_summary_draft(payload)

    def translate_segments(
        self,
        segments: Sequence[TranslationSegment],
        request: SummaryRequest,
        glossary: Glossary,
    ) -> TranslationSegmentsResult:
        system, user = build_translate_segments_prompt(segments, request, glossary)
        payload = self._invoke_json(
            system, user, TRANSLATE_TOOL, max_tokens=8192, graceful_truncation=True
        )
        raw = payload.get("translations", {})
        translations = {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        return TranslationSegmentsResult(
            translations=translations,
            kept_terms=tuple(str(t) for t in payload.get("keptTerms", [])),
            truncated=bool(payload.get("_truncated", False)),
        )

    # --- local LLM plumbing ------------------------------------------------------
    def _invoke_json(
        self,
        system: str,
        user: str,
        tool: dict,
        *,
        max_tokens: int = 2000,
        graceful_truncation: bool = False,
    ) -> dict:
        if not self._cb.allow_request():
            raise LlmUnavailable("local LLM circuit breaker is OPEN")

        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system + _schema_contract(tool)},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "max_tokens": max_tokens,
            # Bedrock 경로가 forced tool(구조화 JSON 출력 모드)이므로 여기서도 JSON 모드.
            "response_format": {"type": "json_object"},
        }
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                time.sleep(2 ** attempt * 0.5)
            try:
                text, truncated = self._chat(body)
                try:
                    payload = json.loads(text)
                    if not isinstance(payload, dict):
                        raise ValueError("model output is not a JSON object")
                except (ValueError, json.JSONDecodeError):
                    # bedrock_llm._invoke_json과 동일한 graceful-truncation 계약:
                    # 출력 캡 잘림(finish_reason=length)으로 mid-JSON이 된 응답은,
                    # 재분할 가능한 호출자(translate)에는 truncation 신호로 수렴시키고
                    # 완결 응답의 파싱 실패만 진짜 오류로 재시도/abstain 한다.
                    if not (graceful_truncation and truncated):
                        raise
                    self._cb.record_success()  # 호출 자체는 성공 — 배치가 과대했을 뿐
                    return {"_truncated": True}
                payload["_truncated"] = truncated
                self._cb.record_success()
                return payload
            except Exception as exc:  # noqa: BLE001 — 전송/파싱 오류 모두 재시도/abstain
                last_exc = exc
        self._cb.record_failure()
        # bedrock_llm과 동일: 삼켜진 근본 원인을 로그로 노출해 진단 가능하게 한다.
        log.warning(
            "local LLM generation failed after %d attempt(s): %s: %s",
            self._max_retries + 1,
            type(last_exc).__name__ if last_exc else "None",
            last_exc,
        )
        raise LlmUnavailable("local LLM generation failed") from last_exc

    def _chat(self, body: dict) -> tuple[str, bool]:
        """POST ``{api_base}/chat/completions`` (비스트리밍) → (content, truncated).

        ``choices``가 비어 있으면 서버는 살아 있으나 생성이 없는 일시 장애로 간주한다
        (재시도 → abstain). ``finish_reason == "length"``는 출력 캡 잘림 신호로,
        Bedrock 경로의 ``stop_reason == "max_tokens"``에 대응한다.
        """
        request = urllib.request.Request(  # noqa: S310 — __init__에서 http(s) 스킴 강제
            f"{self._api_base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._read_timeout) as response:  # noqa: S310 — 상동
            parsed = json.loads(response.read().decode("utf-8"))
        choices = parsed.get("choices") or []
        if not choices:
            raise LlmUnavailable("chat/completions returned no choices")
        first = choices[0] or {}
        content = (first.get("message") or {}).get("content") or ""
        truncated = first.get("finish_reason") == "length"
        return _strip_think(content).strip(), truncated
