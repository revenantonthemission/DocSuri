"""Private (``userdoc:``) document namespace contract — REM-2 F01 (SECURITY-08).

A private document is a user-uploaded PDF. It is never part of the public arXiv corpus: it is
identified by the reserved ``userdoc:{uuid}`` paper-id namespace and stored under a **separate,
IAM-isolatable** object prefix that is keyed by owner (ID-Q1).

Why this is a contract and not an inline check:

  * the public corpus prefix must never hold — or surface — a private document, so a corpus read
    can refuse a private id outright (defense in depth behind the HTTP boundary);
  * a private read is owner-scoped *by construction*: the owner's own key is the only key ever
    probed, so a non-owner's request resolves in its own (empty) prefix and cannot distinguish
    "exists but not yours" from "does not exist" (no existence oracle);
  * the writer and the reader must agree on the key, and they live in different deployables
    (``ingestion`` writes, the backend reads), so the derivation lives here.

Key layout (mirrored by both sides — see ``ingestion/.../adapters/aws.py::S3DocModelStore`` and
``backend/modules/summarization/.../adapters/s3_docmodel.py::S3DocModelReader``)::

    private/userdoc/{ownerSegment}/{docId}/v{version}.json

``ownerSegment`` is sanitized (``[^A-Za-z0-9._-]+`` → ``-``) and the ``docId`` must parse as a
UUID, so neither segment can escape the prefix — the key derivation is traversal-safe by
construction rather than by filtering at each call site.
"""

from __future__ import annotations

import re
from uuid import UUID

__all__ = [
    "CORPUS_DOCMODEL_PREFIX",
    "PRIVATE_DOCMODEL_PREFIX",
    "PRIVATE_PAPER_ID_PREFIX",
    "is_private_paper_id",
    "owner_segment",
    "private_doc_id",
    "private_docmodel_key",
    "private_docmodel_prefix",
]

#: Reserved paper-id namespace for user-uploaded documents.
PRIVATE_PAPER_ID_PREFIX = "userdoc:"
#: Object prefix for the public arXiv corpus doc-models.
CORPUS_DOCMODEL_PREFIX = "doc-model"
#: Object prefix for private (owner-scoped) doc-models. Deliberately NOT under
#: ``CORPUS_DOCMODEL_PREFIX`` — the disjointness is what makes IAM isolation possible.
PRIVATE_DOCMODEL_PREFIX = "private/userdoc"

_UNSAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_OWNER_SEGMENT = 128


def is_private_paper_id(paper_id: str) -> bool:
    """True when ``paper_id`` is in the reserved private ``userdoc:`` namespace.

    The test is the reserved prefix only — deliberately no UUID parse here, so a malformed
    ``userdoc:`` value is still classified as private and refused at the boundary rather than
    falling through to a corpus lookup.
    """
    return bool(paper_id) and str(paper_id).startswith(PRIVATE_PAPER_ID_PREFIX)


def private_doc_id(paper_id: str) -> str | None:
    """The ``docId`` segment of a ``userdoc:{uuid}`` paper id, or ``None`` if it is not a
    well-formed private id.

    Parses the segment as a UUID and returns its canonical form, so the value is safe to place in
    an object key. A malformed value yields ``None`` (→ refused) instead of being sanitized —
    refusing is the correct outcome for an identity we cannot verify.
    """
    if not is_private_paper_id(paper_id):
        return None
    raw = str(paper_id)[len(PRIVATE_PAPER_ID_PREFIX) :].strip()
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError):
        return None


def owner_segment(owner_id: str) -> str:
    """Path-safe owner segment for a private key.

    Raises ``ValueError`` when the owner is empty, sanitizes to nothing, or is a bare dot segment
    — an unverifiable owner must fail closed rather than collapse into a shared segment, and a
    ``.``/``..`` segment would let one owner's key address another's prefix.

    ``.`` is legal inside a longer id (it is in the safe charset, e.g. ``acct.1``); only a segment
    made *entirely* of dots is refused.
    """
    raw = str(owner_id or "").strip()
    segment = _UNSAFE_SEGMENT.sub("-", raw).strip("-")[:_MAX_OWNER_SEGMENT]
    if not segment:
        raise ValueError("private document owner is required")
    if set(segment) == {"."}:
        raise ValueError("private document owner must not be a dot segment")
    return segment


def private_docmodel_prefix(*, owner_id: str, doc_id: str) -> str:
    """The owner-scoped object-key prefix covering every cached version of one private document.

    Trailing ``/`` included, so it is directly usable as a S3 ``Prefix`` for invalidation.
    """
    segment = owner_segment(owner_id)
    try:
        canonical_doc_id = str(UUID(str(doc_id).strip()))
    except (ValueError, AttributeError) as exc:
        raise ValueError("private document id is not a UUID") from exc
    return f"{PRIVATE_DOCMODEL_PREFIX}/{segment}/{canonical_doc_id}/"


def private_docmodel_key(*, owner_id: str, doc_id: str, version: int) -> str:
    """The owner-scoped object key for a private doc-model.

    Raises ``ValueError`` for an unverifiable owner or a ``doc_id`` that is not a UUID.
    """
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("private document version must be a positive int")
    return f"{private_docmodel_prefix(owner_id=owner_id, doc_id=doc_id)}v{version}.json"
