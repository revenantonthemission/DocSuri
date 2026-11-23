"""CorpusContent's production limits (U8 plan Step 24; performance-design § 11, P9, BR8.7).

Synthetic realms keep 20,000 elements, a depth of 128, 2 MiB of source and 256 chunks,
and refuse a block over 8 KB. The production profile and the composed realm take 250,000
elements, a depth of 256, 16 MiB and 200 chunks (lowered from 2,000 by your decision of
2026-11-08, L1-74, and measured again by your answer of 2026-11-09, L1-81), and split a
block over 8 KB at sentence boundaries into pieces that keep its anchor. A source beyond the
limits is refused with the migration's misfit reason `exceeds-v2-limit`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.modules.corpus import maintenance
from backend.modules.corpus.limits import (
    BLOCK_BYTES,
    PRODUCTION_LIMITS,
    SYNTHETIC_LIMITS,
    CorpusLimitExceeded,
    for_profile,
    split_block,
)
from backend.modules.corpus.source_parser import parse_source

DATE = datetime(2026, 10, 22, tzinfo=UTC)
PARAGRAPH = '<p class="ltx_p">Diagnostic.</p>'


def parse(body: str, limits):
    return parse_source(body.encode(), paper="u8-limits", version=1, title="Limits",
                        fetched_at=DATE, limits=limits)


# 1. Each limit, synthetic and production ------------------------------------------------------


@pytest.mark.parametrize(("body", "synthetic_refuses"), [
    ("<div>" * 129 + PARAGRAPH, True),  # depth 129
    ("<br>" * 20_001 + PARAGRAPH, True),  # 20,001 elements
    (PARAGRAPH * 257, True),  # 257 chunks
    ("<p>" + "x" * 2_097_153 + "</p>", True),  # past 2 MiB of source
], ids=["depth", "elements", "chunks", "bytes"])
def test_each_synthetic_limit_refuses_what_production_accepts(body, synthetic_refuses):
    with pytest.raises(CorpusLimitExceeded) as refused:
        parse(body, SYNTHETIC_LIMITS)
    assert refused.value.reason == "exceeds-v2-limit"
    assert isinstance(refused.value, ValueError)  # earlier realms' callers see ValueError
    if body.startswith("<p>x"):
        return  # one 2 MiB block: production accepts the bytes and splits it (test 2)
    if body == PARAGRAPH * 257:
        # 257 chunks: production's limit is now 200, below the synthetic 256 (L1-81), so
        # production refuses this too. test_each_production_limit_refuses_past_its_value
        # and test_a_paper_beyond_the_chunk_limit_is_refused_with_its_misfit_reason show
        # production's limit at 200.
        return
    _, chunks = parse(body, PRODUCTION_LIMITS)
    assert chunks


@pytest.mark.parametrize("body", [
    "<div>" * 257 + PARAGRAPH,  # depth 257
    "<br>" * 250_001 + PARAGRAPH,  # 250,001 elements
    PARAGRAPH * 201,  # 201 chunks
], ids=["depth", "elements", "chunks"])
def test_each_production_limit_refuses_past_its_value(body):
    with pytest.raises(CorpusLimitExceeded) as refused:
        parse(body, PRODUCTION_LIMITS)
    assert refused.value.reason == "exceeds-v2-limit"


def test_the_source_byte_limits_are_two_and_sixteen_mib():
    assert (SYNTHETIC_LIMITS.max_source_bytes, PRODUCTION_LIMITS.max_source_bytes) == (
        2 * 1024 * 1024, 16 * 1024 * 1024)
    with pytest.raises(CorpusLimitExceeded):
        parse_source(b"<p>" + b"x" * (16 * 1024 * 1024) + b"</p>", paper="u8-limits",
                     version=1, title="Limits", fetched_at=DATE, limits=PRODUCTION_LIMITS)


def test_the_profile_selects_the_limits():
    assert for_profile(SimpleNamespace(is_production=True, realm="production")) is (
        PRODUCTION_LIMITS)
    assert for_profile(SimpleNamespace(is_production=False, realm="service-operations")) is (
        PRODUCTION_LIMITS)
    for realm in ("approved-export", "paper-corpus", "account-controls"):
        assert for_profile(SimpleNamespace(is_production=False, realm=realm)) is (
            SYNTHETIC_LIMITS)


# 2. A split block's pieces keep the anchor, and citations lead to the block -------------------


def test_a_large_block_splits_at_sentences_into_pieces_that_keep_its_anchor():
    sentences = [f"Sentence {index} reports a measured result in detail. " * 12
                 for index in range(48)]
    text = " ".join(item.strip() for item in sentences)
    assert len(text.encode()) > 3 * BLOCK_BYTES
    model, chunks = parse(f'<section class="ltx_section"><h2>Results</h2>'
                          f'<p class="ltx_p">{text}</p></section>', PRODUCTION_LIMITS)
    assert len(chunks) >= 4 and all(len(c["text"].encode()) <= BLOCK_BYTES for c in chunks)
    assert [c["piece"] for c in chunks] == list(range(1, len(chunks) + 1))
    assert {c["anchor"] for c in chunks} == {"s1.p1"}
    assert all(c["text"].rstrip().endswith(".") for c in chunks)  # sentence boundaries
    assert " ".join(c["text"] for c in chunks).split() == text.split()
    # A citation of any piece is the block's own anchor in the document model.
    blocks = {block["id"] for section in model["sections"] for block in section["blocks"]}
    assert chunks[-1]["anchor"] in blocks
    with pytest.raises(CorpusLimitExceeded, match="chunking policy") as refused:
        parse(f'<p class="ltx_p">{text}</p>', SYNTHETIC_LIMITS)
    assert refused.value.limit == "block"  # the block refusal names itself (Step 68(i))


def test_a_sentence_longer_than_a_piece_is_cut_within_the_bound():
    pieces = split_block("가" * 9000 + ". Short end.")
    assert all(len(piece.encode()) <= BLOCK_BYTES for piece in pieces)
    assert "".join(pieces).replace(" ", "") == ("가" * 9000 + ".Shortend.")


# 3. A paper beyond the production limits is refused with its misfit reason -----------------


def record(chunks: int) -> dict:
    return {
        "paperId": "u8-limits-paper", "versionLabel": "v1", "title": "Limits",
        "authors": ["Synthetic Author"], "sourceUrl": "https://example.invalid/p",
        "identity": {"system": "synthetic", "recordId": "1"},
        "content": {"document": {}, "chunks": [{
            "anchor": f"a{index}", "section": "body", "text": f"text {index}",
            "textHash": hashlib.sha256(f"text {index}".encode()).hexdigest(),
        } for index in range(chunks)]},
    }


def test_a_paper_beyond_the_chunk_limit_is_refused_with_its_misfit_reason():
    assert maintenance._normalize_source(record(200), PRODUCTION_LIMITS)["versionId"]
    with pytest.raises(CorpusLimitExceeded) as refused:
        maintenance._normalize_source(record(201), PRODUCTION_LIMITS)
    assert refused.value.reason == "exceeds-v2-limit"
    with pytest.raises(CorpusLimitExceeded):
        maintenance._normalize_source(record(257), SYNTHETIC_LIMITS)
    assert maintenance._normalize_source(record(256))["versionId"]  # the built default


# 4. Production's corpus: imports only, the pinned embedder, the real executor (Step 31) ----


def test_the_production_corpus_composes_imports_the_pinned_embedder_and_the_real_executor(
    tmp_path, transactions,
):
    """A stub production profile under a temporary root (the start checks' allowed
    double): the composition connects to nothing, fetches no source and calls no model."""
    import os
    import secrets

    from backend.modules.corpus.maintenance import SourceUnavailable
    from backend.modules.discovery.citations import ProviderUnavailable
    from backend.modules.discovery.local_embedding import LocalEmbeddings
    from backend.modules.summarization.model_runtime import ProductionAssistanceExecutor
    from backend.u8_outward import (
        EMBEDDING_BATCH,
        NoCitationProvider,
        production_corpus,
        readiness_recorded,
    )

    root = tmp_path / "profile"
    (root / "corpus-files").mkdir(parents=True, mode=0o700)
    # The search cursor key in its own folder (U8 plan Step 73(f), L1-4): the composition
    # reads it there and never creates it.
    (root / "cursor-key").mkdir(mode=0o700)
    key = root / "cursor-key" / "search-cursor.key"
    descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(secrets.token_bytes(32))
    profile = SimpleNamespace(is_production=True, root=root, realm="production")
    parts = production_corpus(SimpleNamespace(profile=profile, transactions=transactions),
                              runtime=SimpleNamespace(verify=lambda model: None))
    embedder = parts["embedder"]
    assert isinstance(embedder, LocalEmbeddings)
    assert (embedder.keep_alive, embedder.query_seconds, embedder.batch) == (-1, 2.0,
                                                                            EMBEDDING_BATCH)
    assert parts["maintenance"].limits is PRODUCTION_LIMITS
    with pytest.raises(SourceUnavailable):
        parts["maintenance"].sources.read("any-source")
    with pytest.raises(ProviderUnavailable):
        NoCitationProvider().read("v", "outbound", max_nodes=1, max_depth=1, max_requests=1)
    assert isinstance(parts["dispatch"].executor, ProductionAssistanceExecutor)
    # The real executor waits for the reviewed real-model evidence (BR7.7).
    ready = readiness_recorded(profile)
    assert ready() is False
    (root / "evidence").mkdir(mode=0o700)
    marker = root / "evidence" / "model-readiness.json"
    marker.write_text("{}")
    marker.chmod(0o600)
    assert ready() is False  # an empty marker is not the reviewed evidence (BR7.7)
    import datetime as dt
    import json

    from docsuri_ops.local_models import MODEL_PINS

    marker.write_text(json.dumps({"models": MODEL_PINS, "purposes": {"assistance": "a" * 64},
                                  "recordedAt": dt.datetime.now(dt.UTC).isoformat()}))
    assert ready() is True
    with pytest.raises(Exception, match="synthetic profile"):
        production_corpus(SimpleNamespace(profile=SimpleNamespace(is_production=False),
                                          transactions=transactions))
    # A missing key refuses the composition, and nothing creates one.
    key.unlink()
    with pytest.raises(ValueError):
        production_corpus(SimpleNamespace(profile=profile, transactions=transactions),
                          runtime=SimpleNamespace(verify=lambda model: None))
    assert not key.exists() and not (root / "search-cursor.key").exists()


# 5. Each production limit accepts its value (Step 55(a), with (f)'s N = 200) -------------------

SIXTEEN_MIB = 16 * 1024 * 1024


def sixteen_mib_source(total: int = SIXTEEN_MIB) -> bytes:
    """The paragraph, then a `<script>` of ASCII padding the parser drops, `total` bytes."""
    head, tail = PARAGRAPH + "<script>", "</script>"
    return (head + "x" * (total - len((head + tail).encode())) + tail).encode()


def at_limit_sources() -> dict[str, bytes]:
    """The three measured at-limit cases: 250,000 elements (the paragraph's own start tag
    counts), depth 256, and exactly 16 MiB of source."""
    return {
        "elements-250000": ("<br>" * 249_999 + PARAGRAPH).encode(),
        "depth-256": ("<div>" * 255 + PARAGRAPH).encode(),
        "bytes-16mib": sixteen_mib_source(),
    }


def peak_resident_bytes() -> int:
    import resource
    import sys

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # Linux reports KiB


def assert_the_paragraphs_chunk(model: dict, chunks: list[dict]) -> None:
    assert [chunk["text"] for chunk in chunks] == ["Diagnostic."]
    blocks = {block["id"] for section in model["sections"] for block in section["blocks"]}
    assert chunks[0]["anchor"] in blocks


def test_each_production_limit_accepts_its_value():
    import time
    import warnings

    # The literals, with the chunk limit at N = 200 (L1-74, L1-81).
    assert (PRODUCTION_LIMITS.max_elements, PRODUCTION_LIMITS.max_depth,
            PRODUCTION_LIMITS.max_source_bytes, PRODUCTION_LIMITS.max_chunks,
            PRODUCTION_LIMITS.split_large_blocks) == (250_000, 256, 16_777_216, 200, True)
    assert (SYNTHETIC_LIMITS.max_elements, SYNTHETIC_LIMITS.max_depth,
            SYNTHETIC_LIMITS.max_source_bytes, SYNTHETIC_LIMITS.max_chunks,
            SYNTHETIC_LIMITS.split_large_blocks) == (20_000, 128, 2_097_152, 256, False)
    assert BLOCK_BYTES == 8_192

    # Measured first: each at-limit source goes through BeautifulSoup with lxml twice.
    # Their figures are reported before any assertion on them, so a dropped paragraph
    # still leaves its time and memory in the phase log.
    figures, parsed = {}, {}
    for name, raw in at_limit_sources().items():
        assert name != "bytes-16mib" or len(raw) == SIXTEEN_MIB
        started = time.perf_counter()
        try:
            parsed[name] = parse_source(raw, paper="u8-limits", version=1, title="Limits",
                                        fetched_at=DATE, limits=PRODUCTION_LIMITS)
            outcome = [chunk["text"] for chunk in parsed[name][1]]
        except ValueError as error:  # a dropped paragraph leaves no usable content
            parsed[name], outcome = error, f"{type(error).__name__}: {error}"
        figures[name] = {"seconds": round(time.perf_counter() - started, 3),
                         "peakResidentBytes": peak_resident_bytes(), "chunkTexts": outcome}
    warnings.warn(f"Step 55(a) at-limit figures: {figures}", UserWarning, stacklevel=1)
    for name, value in parsed.items():
        assert not isinstance(value, Exception), (name, value)
        assert_the_paragraphs_chunk(*value)

    # N paragraphs, N = 200 (Step 55(f)), each its own chunk.
    model, chunks = parse(PARAGRAPH * 200, PRODUCTION_LIMITS)
    assert [chunk["text"] for chunk in chunks] == ["Diagnostic."] * 200
    blocks = {block["id"] for section in model["sections"] for block in section["blocks"]}
    assert {chunk["anchor"] for chunk in chunks} <= blocks

    # One past each value is refused with the migration's misfit reason (16 MiB + 1 byte,
    # 250,001 elements, depth 257).
    for raw in (sixteen_mib_source(SIXTEEN_MIB + 1),
                ("<br>" * 250_000 + PARAGRAPH).encode(),
                ("<div>" * 256 + PARAGRAPH).encode()):
        with pytest.raises(CorpusLimitExceeded) as refused:
            parse_source(raw, paper="u8-limits", version=1, title="Limits", fetched_at=DATE,
                         limits=PRODUCTION_LIMITS)
        assert refused.value.reason == "exceeds-v2-limit"


# 6. The parsed text's bound is 16 MiB, in the import and in maintenance (Step 55(b)) ------


class FirstTransaction(Exception):
    """The sentinel the raise-only stand-in raises at the first owner transaction."""


class RaiseOnlyTransactions:
    """L1-35's allowed kind: it raises before any connection and answers no statement."""

    def __init__(self):
        self.calls = 0

    def run(self, *args, **kwargs):
        self.calls += 1
        raise FirstTransaction("the first owner transaction")


def stored_document_bytes(document: dict) -> int:
    """The bytes `paper_import.py` stores: the validated model, sorted keys, compact
    separators, `ensure_ascii=False` (never the input dict)."""
    import json

    from backend.modules.corpus.paper_import import convert

    model = convert(document, PRODUCTION_LIMITS)["document"]
    return len(json.dumps(model, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode())


def padded_v1_document(total: int) -> dict:
    """A valid v1 document model whose `fullText`, which no chunk carries, is padded with
    ASCII until its stored model is exactly `total` bytes."""
    from tests.u8_service_operations_integration import v1_flows

    document = v1_flows.document("2101.09055", 1)
    base = stored_document_bytes(document)
    padded = {**document, "fullText": document["fullText"] + "x" * (total - base)}
    assert stored_document_bytes(padded) == total
    return padded


def maintenance_record(total: int) -> dict:
    """A provider record with one valid chunk and no `permission`, whose content's compact
    JSON (`maintenance.py`'s measure) is exactly `total` bytes."""
    import json

    text = "One valid chunk."
    chunk = {"anchor": "a0", "section": "body", "text": text,
             "textHash": hashlib.sha256(text.encode()).hexdigest()}
    content = {"document": {"padding": ""}, "chunks": [chunk]}
    base = len(json.dumps(content, separators=(",", ":")).encode())
    content["document"]["padding"] = "x" * (total - base)
    assert len(json.dumps(content, separators=(",", ":")).encode()) == total
    return {"paperId": "u8-limits-bound", "versionLabel": "v1", "title": "Limits",
            "authors": ["Synthetic Author"], "sourceUrl": "https://example.invalid/p",
            "identity": {"system": "synthetic", "recordId": "1"}, "content": content}


class OneRecord:
    def __init__(self, record: dict):
        self.record = record

    def read(self, source_id: str) -> dict:
        return self.record


def test_the_parsed_text_bound_is_sixteen_mib():
    from backend.modules.corpus.maintenance import CorpusMaintenance
    from backend.modules.corpus.paper_import import (
        PaperImport,
        PaperMeasure,
        PaperSource,
        split_identity,
    )

    def source(total: int) -> PaperSource:
        return PaperSource(
            source_key="2101.09055:v1", version="arxiv:2101.09055@v1",
            title="Synthetic paper", authors=("A. Synthetic",),
            source_url="https://arxiv.org/abs/2101.09055v1", published_on=None,
            document=padded_v1_document(total), metadata={})

    # The import's bound: at 16 MiB `_decide` reaches its first owner transaction.
    stand_in = RaiseOnlyTransactions()
    importer = PaperImport(stand_in, None, limits=PRODUCTION_LIMITS, embedder=None,
                           vector_policy=None)
    at_limit = source(SIXTEEN_MIB)
    with pytest.raises(FirstTransaction):
        importer._decide(at_limit, *split_identity(at_limit.version), re_embed=False)
    assert stand_in.calls == 1
    past = source(SIXTEEN_MIB + 1)
    stand_in = RaiseOnlyTransactions()
    importer = PaperImport(stand_in, None, limits=PRODUCTION_LIMITS, embedder=None,
                           vector_policy=None)
    decided = importer._decide(past, *split_identity(past.version), re_embed=False)
    refused = decided[0]
    assert (refused["disposition"], refused["reasonKey"]) == ("refused", "exceeds-v2-limit")
    assert decided[1] == PaperMeasure(refused_by="sourceBytes")  # Step 68(i)'s measure
    assert stand_in.calls == 0

    # Maintenance's bound: at 16 MiB the next check, the permission, refuses.
    stand_in = RaiseOnlyTransactions()
    maintenance = CorpusMaintenance(stand_in, None, OneRecord(maintenance_record(SIXTEEN_MIB)),
                                    limits=PRODUCTION_LIMITS)
    with pytest.raises(ValueError) as unresolved:
        maintenance._apply_source({}, "u8-limits-bound", retry_only=None)
    assert type(unresolved.value) is ValueError  # CorpusLimitExceeded is a ValueError too
    assert str(unresolved.value) == "source permission unresolved"
    maintenance = CorpusMaintenance(
        stand_in, None, OneRecord(maintenance_record(SIXTEEN_MIB + 1)),
        limits=PRODUCTION_LIMITS)
    with pytest.raises(CorpusLimitExceeded):
        maintenance._apply_source({}, "u8-limits-bound", retry_only=None)
    assert stand_in.calls == 0


# 7. The import's record of each corpus limit (Step 68(i), L1-79) ------------------------------


def test_the_import_records_each_limits_largest_value_and_refusals():
    from backend.modules.corpus.paper_import import LimitRecord, PaperMeasure

    empty = LimitRecord.of(PRODUCTION_LIMITS)
    assert empty.as_dict() == {
        "profile": "production",
        "chunks": {"limit": 200, "checked": True, "largest": None, "refused": 0},
        "sourceBytes": {"limit": 16_777_216, "checked": True, "largest": None, "refused": 0},
        "elements": {"limit": 250_000, "checked": False, "largest": None, "refused": 0},
        "depth": {"limit": 256, "checked": False, "largest": None, "refused": 0},
    }
    records = [empty]
    for measure in (PaperMeasure(chunks=3, source_bytes=700),
                    PaperMeasure(chunks=5, source_bytes=600), None,
                    PaperMeasure(refused_by="chunks"), PaperMeasure(refused_by="sourceBytes")):
        records.append(records[-1].add(measure))
    final = records[-1].as_dict()
    assert final["chunks"] == {"limit": 200, "checked": True, "largest": 5, "refused": 1}
    assert final["sourceBytes"] == {"limit": 16_777_216, "checked": True, "largest": 700,
                                    "refused": 1}
    assert (final["elements"], final["depth"]) == (empty.as_dict()["elements"],
                                                   empty.as_dict()["depth"])
    # Each `add` leaves the record it was called on as it was.
    assert records[0] == empty and records[1].as_dict()["chunks"]["largest"] == 3
    assert records[2].as_dict()["chunks"]["refused"] == 0 and records[3] == records[2]
    # The block refusal names itself: only under limits that refuse a block over 8 KB.
    synthetic = LimitRecord.of(SYNTHETIC_LIMITS)
    assert synthetic.as_dict()["block"] == {"limit": 8192, "checked": True, "largest": None,
                                            "refused": 0}
    assert synthetic.add(PaperMeasure(refused_by="block")).as_dict()["block"]["refused"] == 1
    assert "block" not in empty.as_dict()
