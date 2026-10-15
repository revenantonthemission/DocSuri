"""Synthetic-fixture assistance executor for the owned synthetic realm.

This adapter is an explicitly labelled synthetic provider: it performs bounded
extractive work over the accepted immutable payload and marks every result with
`synthetic: true` provenance. It is never reported as real model readiness, and
the real model path (``GroundedLocalAssistant``) stays gated behind its own
evidence. The label travels with the result so no consumer can present the
fixture output as a normal model result.
"""

from __future__ import annotations

import hashlib
import threading

from backend.modules.summarization.local_result import encode_result
from backend.modules.summarization.worker import ExecutionRefused, PreparedExecution

SENTENCE_LIMIT = 240
SECTION_LIMIT = 7000


class SyntheticAssistanceExecutor:
    """Deterministic, bounded extractive provider fixture (labelled synthetic)."""

    def __init__(self, *, fail_with: str | None = None):
        if fail_with is not None and fail_with not in (
            "dependency-unavailable",
            "invalid-source",
            "insufficient-result",
            "deadline-exceeded",
        ):
            raise ValueError("unsupported synthetic failure")
        self.fail_with = fail_with
        self._lock = threading.Lock()
        self._active = False
        self._finished = False

    def run(
        self, bound_input: dict, _absolute_monotonic_deadline: float
    ) -> PreparedExecution:
        with self._lock:
            self._active = True
            self._finished = False
        try:
            if self.fail_with is not None:
                raise ExecutionRefused(self.fail_with)
            input_value = bound_input.get("input") or {}
            sections = bound_input.get("sections")
            operation = input_value.get("operation")
            if (
                not isinstance(sections, list)
                or not 1 <= len(sections) <= 8
                or operation not in ("summary", "translation")
            ):
                raise ExecutionRefused("invalid-source")
            output_sections = []
            anchors = []
            total = 0
            for section in sections:
                text = section.get("text")
                heading = section.get("heading")
                anchor = section.get("anchor")
                if (
                    not isinstance(text, str)
                    or not text.strip()
                    or not isinstance(heading, str)
                    or not isinstance(anchor, str)
                ):
                    raise ExecutionRefused("invalid-source")
                total += len(text.encode())
                if total > SECTION_LIMIT:
                    raise ExecutionRefused("insufficient-result")
                prepared = _prepare_text(text, operation=operation)
                output_sections.append(
                    {
                        "sectionId": section.get("sectionId") or anchor,
                        "heading": heading,
                        "text": prepared,
                        "anchor": anchor,
                    }
                )
                anchors.append(anchor)
            if not output_sections:
                raise ExecutionRefused("insufficient-result")
            content = encode_result(
                sections=output_sections,
                citations=anchors,
                definitions=[],
            )
            coverage = {
                "coverage": "partial",
                "sections": len(output_sections),
                "synthetic": True,
            }
            provenance = {
                "provider": "synthetic-fixture",
                "methodRevision": "u3-synthetic-extractive-1",
                "synthetic": True,
                "sourceAnchors": anchors,
                "sectionHashes": [
                    hashlib.sha256(item["text"].encode()).hexdigest()
                    for item in output_sections
                ],
                "operation": operation,
            }
            return PreparedExecution(content, coverage, provenance)
        finally:
            with self._lock:
                self._active = False
                self._finished = True

    def abort_owned(self) -> None:
        """Bounded work has no asynchronous child; abort is a no-op acknowledgement."""
        return None

    def stopped(self) -> bool:
        with self._lock:
            return not self._active


def _prepare_text(text: str, *, operation: str) -> str:
    """Bounded extractive preparation; never invents content beyond the source."""
    collapsed = " ".join(text.split())
    if operation == "summary":
        prepared = collapsed[:SENTENCE_LIMIT]
    else:
        # The synthetic dictionary is deliberately empty: translation-shaped
        # output keeps the literal source text and is labelled synthetic.
        prepared = collapsed[:SENTENCE_LIMIT]
    if not prepared:
        raise ExecutionRefused("insufficient-result")
    return prepared
