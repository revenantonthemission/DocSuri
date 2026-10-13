"""Canonical worker payloads from immutable acceptance and CorpusContent.

Legacy diagnostic intents deliberately fail this codec. Missing accepted fields
cannot be reconstructed from mutable current preferences or option catalogs.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from backend.modules.corpus.repository import CorpusRepository, content_revision
from backend.modules.summarization.execution import ExecutionClaims
from docsuri_shared.workspace import execution as wire


def selected_sections(source: dict, selection: list[dict]) -> list[dict]:
    chunks = source["content"]["chunks"]
    if not 1 <= len(chunks) <= 256 or not 1 <= len(selection) <= 8:
        raise ValueError("source selection exceeds finite allocation")
    by_anchor = {chunk["anchor"]: chunk for chunk in chunks}
    if len(by_anchor) != len(chunks):
        raise ValueError("ambiguous source anchor")
    seen = set()
    sections = []
    for item in selection:
        base = {"anchor", "heading", "textHash"}
        if set(item) not in (base, base | {"start", "end", "selectedHash"}):
            raise ValueError("invalid accepted selection descriptor")
        anchor = item["anchor"]
        if anchor in seen or anchor not in by_anchor:
            raise ValueError("missing or repeated selected source")
        seen.add(anchor)
        chunk = by_anchor[anchor]
        actual_hash = hashlib.sha256(chunk["text"].encode()).hexdigest()
        if (
            item["heading"] != chunk["section"]
            or item["textHash"] != actual_hash
            or chunk["textHash"] != actual_hash
        ):
            raise ValueError("accepted section identity changed")
        text = chunk["text"]
        section_id = anchor
        if "start" in item:
            # Offsets are Unicode code-point indices in the immutable original
            # text; selectedHash always hashes the selected UTF-8 bytes.
            start, end = item["start"], item["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise ValueError("selected source span is outside its original text")
            text = text[start:end]
            if hashlib.sha256(text.encode()).hexdigest() != item["selectedHash"]:
                raise ValueError("selected span byte binding changed")
            section_id = f"{anchor}:{start}:{end}"
        sections.append(
            {
                "sectionId": section_id,
                "heading": chunk["section"],
                "text": text,
                "anchor": anchor,
            }
        )
    if sum(len(section["text"].encode()) for section in sections) > 7000:
        raise ValueError("selected source exceeds context allocation")
    return sections


def encode_payload(bound: dict, source: dict) -> dict:
    accepted = wire.AssistanceAcceptedInput.model_validate(
        bound["payload"]["acceptedInput"]
    ).model_dump(mode="json")
    if accepted["paper"] != {
        "paperId": source["paper_id"],
        "versionId": source["id"],
        "eligibilityRevision": str(source["eligibility_revision"]),
    }:
        raise ValueError("accepted paper/version/eligibility binding changed")
    if (
        source["id"] != bound["versionId"]
        or source["source_hash"] != bound["sourceHash"]
        or accepted["contentHash"] != bound["sourceHash"]
        or accepted["contentRevision"] != content_revision(source)
    ):
        raise ValueError("accepted source content binding changed")
    glossary = accepted["glossary"]
    if (
        glossary["ownerId"] != str(bound["accountId"])
        or glossary["revision"] != bound["glossaryRevision"]
        or accepted["glossaryRevision"] != bound["glossaryRevision"]
        or glossary["terms"] != bound["glossarySnapshot"]
    ):
        raise ValueError("accepted glossary snapshot binding changed")
    return wire.AssistanceExecutionPayload.model_validate(
        {
            "binding": bound["binding"],
            "acceptedAt": bound["acceptedAt"].isoformat(),
            "input": accepted,
            "sections": selected_sections(source, bound["payload"]["selectedSections"]),
            "usageRecordId": str(bound["reservationId"]),
        }
    ).model_dump(mode="json")


class ExecutionPayloads:
    def __init__(self, claims: ExecutionClaims, corpus: CorpusRepository):
        self.claims = claims
        self.corpus = corpus

    def read(self, claim: dict, *, trusted_worker: UUID) -> dict:
        if UUID(claim["workerId"]) != UUID(str(trusted_worker)):
            raise PermissionError("execution claim does not belong to authenticated worker")
        bound = self.claims.read_input(claim)
        source = self.corpus.read(bound["versionId"])
        payload = encode_payload(bound, source)
        # Corpus reads are outside the PA transaction. Recheck current authority
        # and execution after assembling bytes; no model work occurs in a guard.
        current = self.claims.read_input(claim)
        if current["binding"] != bound["binding"] or current["payload"] != bound["payload"]:
            raise ValueError("immutable acceptance changed during payload assembly")
        return payload
