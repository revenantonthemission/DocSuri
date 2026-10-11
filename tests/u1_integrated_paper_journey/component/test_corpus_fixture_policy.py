"""Finite checked bibliographic input and embedding batch formation."""

import json

import pytest

from scripts.publish_docsuri_u1_papers import METADATA, batches, checked_metadata

pytestmark = pytest.mark.u1_component


def test_checked_bibliography_binds_both_actual_public_paper_identities():
    papers = checked_metadata(METADATA.read_bytes())
    assert [p["publishedOn"] for p in papers] == ["2017-06-12", "2020-05-22"]
    assert [len(p["authors"]) for p in papers] == [8, 12]


def test_changed_bibliographic_scope_or_source_is_rejected():
    for field, value in (("paper", "other"), ("metadataSource", "https://untrusted.invalid")):
        metadata = json.loads(METADATA.read_bytes())
        metadata["papers"][0][field] = value
        with pytest.raises(ValueError):
            checked_metadata(json.dumps(metadata).encode())


def test_invalid_date_or_missing_authors_is_rejected():
    for field, value in (("publishedOn", "unknown"), ("authors", [])):
        metadata = json.loads(METADATA.read_bytes())
        metadata["papers"][0][field] = value
        with pytest.raises(ValueError):
            checked_metadata(json.dumps(metadata).encode())


def test_embedding_batch_preserves_every_character_and_limits_cardinality():
    chunks = [{"text": f"Diagnostic {i}"} for i in range(17)]
    grouped = list(batches(chunks))
    assert [len(group) for group in grouped] == [8, 8, 1]
    assert [text for group in grouped for text in group] == [c["text"] for c in chunks]


def test_embedding_batch_accounts_for_json_escape_bytes():
    chunks = [{"text": "수학" * 600} for _ in range(2)]
    grouped = list(batches(chunks))
    assert len(grouped) == 2
    assert grouped[0][0] == chunks[0]["text"]
    for text in ("", "x" * 8193, "수학" * 1100):
        with pytest.raises(ValueError):
            list(batches([{"text": text}]))
