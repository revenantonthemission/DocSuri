import hashlib
from uuid import uuid4

import pytest

from backend.modules.research.attachments import ResearchAttachments
from backend.modules.research.errors import ResearchError


@pytest.fixture
def attachment(transactions, authority):
    repo = ResearchAttachments(transactions)
    context = repo.create_context(authority, "research")["id"]
    row = repo.begin(authority, context, "text/plain", 4, hashlib.sha256(b"text").hexdigest(), {})
    return repo, context, row


def test_upload_handle_and_hash_bind_bytes(attachment, authority):
    repo, context, row = attachment
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.store_bytes(authority, context, row["id"], uuid4(), b"text")
    with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
        repo.store_bytes(authority, context, row["id"], row["write_handle"], b"evil")
    assert repo.read(authority, context, row["id"])["content"] is None


def test_extraction_disposition_is_idempotent(attachment, authority):
    repo, context, row = attachment
    repo.store_bytes(authority, context, row["id"], row["write_handle"], b"text")
    assert repo.finish(authority, context, row["id"], "extracted", "text")["revision"] == 2
    assert repo.finish(authority, context, row["id"], "failed", None)["disposition"] == "extracted"


def test_finish_requires_bytes(attachment, authority):
    repo, context, row = attachment
    with pytest.raises(ResearchError, match="CONFLICT"):
        repo.finish(authority, context, row["id"], "extracted", "invented")


def test_cross_context_refuses_private_asset(attachment, authority):
    repo, _, row = attachment
    context = repo.create_context(authority, "research")["id"]
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.read(authority, context, row["id"])


def test_upload_limits_and_media_allowlist(attachment, authority):
    repo, context, _ = attachment
    for media, size in [("image/png", 4), ("text/plain", 2097153), ("text/plain", 0)]:
        with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
            repo.begin(authority, context, media, size, "0" * 64, {})


def test_expired_upload_refused(attachment, authority):
    repo, context, row = attachment
    repo.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.attachment SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (row["id"],),
        ),
    )
    with pytest.raises(ResearchError, match="CONFLICT"):
        repo.store_bytes(authority, context, row["id"], row["write_handle"], b"text")
