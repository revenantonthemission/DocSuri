"""Regression tests for PR2 user doc-model coordinator fixes (review of #392)."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import unquote

import pytest

from backend.modules.user_docmodel import (
    UserDocModelCoordinator,
    object_key_for_upload,
    ref_from_attachment,
    user_docmodel_ref,
)
from backend.modules.user_docmodel.coordinator import _userdoc_build_queue_url


def _ref():
    return user_docmodel_ref(
        owner_id="acct-1",
        scope_id="scope-1",
        attachment_id="att-1",
        object_key="uploads/evidence/acct-1/scope-1/att-1/doc.pdf",
        module="evidence",
    )


class _RaisingReader:
    def get_doc_model(self, paper_id, version):
        raise RuntimeError("simulated AccessDenied / throttle / parse error")

    def get_private_doc_model(self, owner_id, doc_id, version):
        raise RuntimeError("simulated AccessDenied / throttle / parse error")


class _OwnerScopedReader:
    """Reader double recording WHICH identity the readiness probe resolved (REM-2 F01 / ID-Q1)."""

    def __init__(self, doc_model=None):
        self._doc_model = doc_model
        self.corpus_reads: list[tuple[str, int]] = []
        self.private_reads: list[tuple[str, str, int]] = []

    def get_doc_model(self, paper_id, version):
        self.corpus_reads.append((paper_id, version))
        return None

    def get_private_doc_model(self, owner_id, doc_id, version):
        self.private_reads.append((owner_id, doc_id, version))
        return self._doc_model


class _CapturingS3:
    def __init__(self):
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


def test_poll_doc_model_degrades_when_reader_raises() -> None:
    # get_doc_model raises on non-miss S3 errors; readiness polling must degrade to None,
    # never propagate and 500 the async evidence/research request paths (best-effort contract).
    coord = UserDocModelCoordinator(
        bucket="b",
        s3_client=_CapturingS3(),
        doc_model_reader=_RaisingReader(),
        poll_timeout_seconds=0.0,
        poll_interval_seconds=0.01,
    )

    assert coord.poll_doc_model(_ref()) is None


def test_poll_doc_model_reads_the_private_path_with_the_ref_owner() -> None:
    # REM-2 F01 (ID-Q1): a ``userdoc:`` ref must be resolved through get_private_doc_model with the
    # ref's OWNER identity — the corpus read now refuses the private namespace, so probing it there
    # would turn every upload's readiness check into a permanent miss.
    reader = _OwnerScopedReader()
    coord = UserDocModelCoordinator(
        bucket="b",
        s3_client=_CapturingS3(),
        doc_model_reader=reader,
        poll_timeout_seconds=0.0,
        poll_interval_seconds=0.01,
    )
    ref = _ref()

    assert coord.poll_doc_model(ref) is None

    assert reader.corpus_reads == []
    assert reader.private_reads, "the private read must be attempted"
    owner_read, doc_id_read, version_read = reader.private_reads[-1]
    assert owner_read == ref.owner_id == "acct-1"
    assert doc_id_read == ref.paper_id.split(":", 1)[1]
    assert version_read == ref.version


def test_peek_doc_model_returns_the_owned_document_without_polling() -> None:
    reader = _OwnerScopedReader(doc_model=object())
    coord = UserDocModelCoordinator(
        bucket="b",
        s3_client=_CapturingS3(),
        doc_model_reader=reader,
        poll_timeout_seconds=0.0,
        poll_interval_seconds=0.01,
    )

    assert coord.peek_doc_model(_ref()) is not None
    assert len(reader.private_reads) == 1  # exactly one attempt — no sleep loop


def test_poll_doc_model_ignores_a_ref_whose_paper_id_is_not_private() -> None:
    # Fail closed: a corpus-shaped ref must not be routed into the private namespace, and the
    # corpus path stays unavailable here (the coordinator only serves private refs).
    reader = _OwnerScopedReader()
    coord = UserDocModelCoordinator(
        bucket="b",
        s3_client=_CapturingS3(),
        doc_model_reader=reader,
        poll_timeout_seconds=0.0,
        poll_interval_seconds=0.01,
    )
    corpus_ref = replace(_ref(), paper_id="2401.00001")

    assert coord.poll_doc_model(corpus_ref) is None
    assert reader.private_reads == []
    assert reader.corpus_reads == []


def test_userdoc_build_queue_url_prefers_dedicated_then_falls_back(monkeypatch) -> None:
    # GROBID Option B routing: user-PDF builds prefer the dedicated userdoc queue (its worker
    # carries the GROBID sidecar). With only the shared doc-model queue set, an un-split
    # deployment still enqueues there (backward compatible). Neither set → no queue.
    monkeypatch.delenv("DOCSURI_USERDOC_BUILD_QUEUE_URL", raising=False)
    monkeypatch.setenv("DOCSURI_DOCMODEL_BUILD_QUEUE_URL", "https://sqs/docmodel")
    assert _userdoc_build_queue_url() == "https://sqs/docmodel"

    monkeypatch.setenv("DOCSURI_USERDOC_BUILD_QUEUE_URL", "https://sqs/userdoc")
    assert _userdoc_build_queue_url() == "https://sqs/userdoc"

    monkeypatch.delenv("DOCSURI_USERDOC_BUILD_QUEUE_URL", raising=False)
    monkeypatch.delenv("DOCSURI_DOCMODEL_BUILD_QUEUE_URL", raising=False)
    assert _userdoc_build_queue_url() is None


def test_upload_pdf_metadata_is_ascii_for_unicode_filename() -> None:
    # S3 object metadata must be US-ASCII; a Korean filename must not make put_object throw.
    s3 = _CapturingS3()
    coord = UserDocModelCoordinator(bucket="b", s3_client=s3)

    coord.upload_pdf(_ref(), b"%PDF-1.4 body", file_name="논문 초안.pdf")

    file_name_meta = s3.calls[0]["Metadata"]["file-name"]
    assert file_name_meta.isascii()
    assert unquote(file_name_meta) == "논문 초안.pdf"


def test_ref_from_attachment_accepts_server_issued_evidence_object_key() -> None:
    object_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        file_name="doc.pdf",
    )
    ref = user_docmodel_ref(
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        object_key=object_key,
        module="evidence",
    )

    hydrated = ref_from_attachment(
        owner_id="acct-1",
        scope_id="request-1",
        attachment_id="att-1",
        object_key=object_key,
        module="evidence",
        paper_id=ref.paper_id,
        record_ref=ref.record_ref,
    )

    assert hydrated.object_key == object_key
    assert hydrated.paper_id == ref.paper_id
    assert hydrated.record_ref == ref.record_ref


def test_ref_from_attachment_rejects_cross_owner_evidence_object_key() -> None:
    object_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        file_name="doc.pdf",
    )
    ref = user_docmodel_ref(
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        object_key=object_key,
        module="evidence",
    )
    forged_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-2",
        scope_id="att-1",
        attachment_id="att-1",
        file_name="doc.pdf",
    )

    with pytest.raises(ValueError, match="objectKey"):
        ref_from_attachment(
            owner_id="acct-1",
            scope_id="request-1",
            attachment_id="att-1",
            object_key=forged_key,
            module="evidence",
            paper_id=ref.paper_id,
            record_ref=ref.record_ref,
        )


def test_ref_from_attachment_rejects_self_consistent_foreign_paper_id() -> None:
    # SEC regression: an authenticated attacker echoes their own valid objectKey but a foreign
    # tenant's paperId plus a recordRef crafted to match it. The old check only validated the
    # supplied fields against each other (self-referential), so this passed; the server-side
    # uuid5 recomputation must reject it before any poll or build touches the foreign namespace.
    victim = user_docmodel_ref(
        owner_id="acct-victim",
        scope_id="att-9",
        attachment_id="att-9",
        object_key=object_key_for_upload(
            module="evidence",
            owner_id="acct-victim",
            scope_id="att-9",
            attachment_id="att-9",
            file_name="doc.pdf",
        ),
        module="evidence",
    )
    own_object_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        file_name="doc.pdf",
    )

    with pytest.raises(ValueError, match="identity"):
        ref_from_attachment(
            owner_id="acct-1",
            scope_id="request-1",
            attachment_id="att-1",
            object_key=own_object_key,
            module="evidence",
            paper_id=victim.paper_id,
            record_ref=f"upload:acct-1:{victim.job_id}:att-1",
        )


def test_ref_from_attachment_accepts_novelty_manuscript_reuse() -> None:
    # Novelty mints with (owner, scope=novelty job id, attachment="manuscript"); the worker reuse
    # path passes the original job id back as scope_id — recomputation must reproduce it.
    object_key = object_key_for_upload(
        module="novelty",
        owner_id="acct-1",
        scope_id="job-1",
        attachment_id="manuscript",
        file_name="paper.pdf",
    )
    ref = user_docmodel_ref(
        owner_id="acct-1",
        scope_id="job-1",
        attachment_id="manuscript",
        object_key=object_key,
        module="novelty",
    )

    hydrated = ref_from_attachment(
        owner_id="acct-1",
        scope_id="job-1",
        attachment_id="manuscript",
        object_key=object_key,
        module="novelty",
        paper_id=ref.paper_id,
        record_ref=ref.record_ref,
    )

    assert hydrated.paper_id == ref.paper_id
    assert hydrated.record_ref == ref.record_ref


def test_ref_from_attachment_rejects_wrong_attachment_evidence_object_key() -> None:
    object_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        file_name="doc.pdf",
    )
    ref = user_docmodel_ref(
        owner_id="acct-1",
        scope_id="att-1",
        attachment_id="att-1",
        object_key=object_key,
        module="evidence",
    )
    forged_key = object_key_for_upload(
        module="evidence",
        owner_id="acct-1",
        scope_id="att-2",
        attachment_id="att-2",
        file_name="doc.pdf",
    )

    with pytest.raises(ValueError, match="objectKey"):
        ref_from_attachment(
            owner_id="acct-1",
            scope_id="request-1",
            attachment_id="att-1",
            object_key=forged_key,
            module="evidence",
            paper_id=ref.paper_id,
            record_ref=ref.record_ref,
        )
