"""Grounding checks shared by research answers and novelty assessments."""

import hashlib
import json
import math
from uuid import uuid4

from docsuri_shared.workspace import wire
from pydantic import ValidationError

from .errors import ResearchError


def validate_output(output, sources):
    try:
        wire.ResearchOutput.model_validate_json(json.dumps(output), strict=True)
    except (ValidationError, TypeError, ValueError):
        raise ResearchError("DEPENDENCY_UNAVAILABLE") from None
    if len(json.dumps(output).encode()) > 32768 or len(output["evidence"]) > 32:
        raise ResearchError("DEPENDENCY_UNAVAILABLE")
    known = {
        (s["sourceKind"], s["sourceId"], s["sourceVersion"], s["location"]): s for s in sources
    }
    identifiers = set()
    for evidence in output["evidence"]:
        if evidence["evidenceId"] in identifiers:
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
        identifiers.add(evidence["evidenceId"])
        source = known.get(
            (
                evidence["sourceKind"],
                evidence["sourceId"],
                evidence["sourceVersion"],
                evidence["location"],
            )
        )
        if source is None:
            raise ResearchError("SOURCE_INELIGIBLE")
        text = source.get("text")
        if not text or evidence["readCoverage"] == "not-read":
            if evidence["stance"] != "uncertain" or evidence["quote"] is not None:
                raise ResearchError("DEPENDENCY_UNAVAILABLE")
        elif (evidence["quote"] is not None and evidence["quote"] not in text) or evidence[
            "sourceContentHash"
        ] != hashlib.sha256(text.encode()).hexdigest():
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
        if evidence["sourceUrl"] != source.get("sourceUrl"):
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
    for assessment in output.get("assessments", []):
        if not set(assessment["evidenceIds"]).issubset(identifiers):
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
        if "score" in assessment:
            if not {"scaleMinimum", "scaleMaximum"}.issubset(assessment):
                raise ResearchError("DEPENDENCY_UNAVAILABLE")
            values = [assessment[k] for k in ("score", "scaleMinimum", "scaleMaximum")]
            if not all(math.isfinite(v) for v in values) or not values[1] <= values[0] <= values[2]:
                raise ResearchError("DEPENDENCY_UNAVAILABLE")
    if output["coverage"] == "complete" and (
        not identifiers or any(e["readCoverage"] != "read" for e in output["evidence"])
    ):
        raise ResearchError("DEPENDENCY_UNAVAILABLE")
    return output


class SyntheticResearchProvider:
    """Explicitly synthetic extractive fixture, never proof of model or novelty parity."""

    def run(self, sources, *, stance="uncertain"):
        if stance not in {"supports", "contradicts", "uncertain"}:
            raise ResearchError("INVALID_ARGUMENT")
        evidence = []
        for source in sources[:8]:
            text = source.get("text")
            if not text:
                continue  # An unread link is not read evidence.
            evidence.append(
                {
                    "evidenceId": str(uuid4()),
                    "sourceKind": source["sourceKind"],
                    "sourceId": source["sourceId"],
                    "sourceVersion": source["sourceVersion"],
                    "sourceContentHash": hashlib.sha256(text.encode()).hexdigest(),
                    "location": source["location"],
                    "readCoverage": "partial",
                    "quote": text[:240],
                    "claim": "Synthetic fixture excerpt; not an independent novelty judgement.",
                    "stance": stance,
                    "sourceUrl": source.get("sourceUrl"),
                }
            )
        return validate_output(
            {
                "summary": "합성 검증 자료의 인용입니다."
                if evidence
                else "읽은 근거가 없어 판단을 보류합니다.",
                "evidence": evidence,
                "coverage": "partial" if evidence else "abstained",
                "limitations": [
                    "Synthetic extractive fixture only; incomplete source coverage; no model "
                    "or novelty readiness claim."
                ],
                "methodRevision": "u4-synthetic-extractive-1",
            },
            sources,
        )
