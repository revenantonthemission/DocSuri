"""Private ``userdoc:`` namespace contract — REM-2 F01 (SECURITY-08).

The key derivation is shared by two deployables (``ingestion`` writes, the backend reads), so
these tests pin the properties both sides depend on: a private id is always classified as
private, an unresolvable identity fails closed rather than sanitizing into a shared key, and the
private key space can never collide with the public corpus one.
"""

from __future__ import annotations

import pytest

from docsuri_shared.private_docs import (
    CORPUS_DOCMODEL_PREFIX,
    PRIVATE_DOCMODEL_PREFIX,
    is_private_paper_id,
    owner_segment,
    private_doc_id,
    private_docmodel_key,
    private_docmodel_prefix,
)

_DOC_ID = "11111111-1111-4111-8111-111111111111"


# --- classification ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "paper_id",
    [
        "userdoc:11111111-1111-4111-8111-111111111111",
        "userdoc:not-a-uuid",
        "userdoc:",
    ],
)
def test_private_ids_are_classified_private_even_when_malformed(paper_id: str) -> None:
    # Classification is the reserved prefix only: a malformed private value must be REFUSED at
    # the boundary, never fall through to a corpus lookup.
    assert is_private_paper_id(paper_id) is True


@pytest.mark.parametrize("paper_id", ["2401.00001", "2304.10557v2", "hep-th/9901001", "", None])
def test_corpus_ids_are_not_private(paper_id) -> None:
    assert is_private_paper_id(paper_id) is False


def test_private_doc_id_returns_the_canonical_uuid() -> None:
    assert private_doc_id(f"userdoc:{_DOC_ID.upper()}") == _DOC_ID


def test_private_doc_id_is_none_for_corpus_ids() -> None:
    assert private_doc_id("2401.00001") is None


@pytest.mark.parametrize("bad", ["userdoc:not-a-uuid", "userdoc:", f"userdoc:{_DOC_ID}../../x"])
def test_private_doc_id_is_none_for_an_unverifiable_id(bad: str) -> None:
    # Refusing is correct for an identity we cannot verify — sanitizing would be inventing one.
    assert private_doc_id(bad) is None


# --- key derivation -----------------------------------------------------------------------


def test_private_key_is_owner_scoped_and_under_the_private_prefix() -> None:
    key = private_docmodel_key(owner_id="acct-1", doc_id=_DOC_ID, version=3)
    assert key == f"{PRIVATE_DOCMODEL_PREFIX}/acct-1/{_DOC_ID}/v3.json"
    assert not key.startswith(f"{CORPUS_DOCMODEL_PREFIX}/")


def test_two_owners_never_share_a_key_for_the_same_document() -> None:
    a = private_docmodel_key(owner_id="acct-1", doc_id=_DOC_ID, version=1)
    b = private_docmodel_key(owner_id="acct-2", doc_id=_DOC_ID, version=1)
    assert a != b


def test_the_owner_segment_cannot_escape_the_prefix() -> None:
    # Traversal characters are sanitized, so an owner id can never address another owner's prefix
    # or climb out of ``private/userdoc/``.
    key = private_docmodel_key(owner_id="../../etc", doc_id=_DOC_ID, version=1)
    assert key == f"{PRIVATE_DOCMODEL_PREFIX}/..-..-etc/{_DOC_ID}/v1.json"
    assert ".." not in key.replace("..-", "")


def test_a_dot_only_owner_segment_is_refused() -> None:
    # ``.``/``..`` are in the safe charset (a longer id like ``acct.1`` is legitimate), so a
    # segment made ENTIRELY of dots is the traversal case and must fail closed.
    for bad in (".", "..", "..."):
        with pytest.raises(ValueError):
            owner_segment(bad)


def test_a_dotted_owner_id_is_still_accepted() -> None:
    assert owner_segment("acct.1") == "acct.1"


def test_prefix_covers_every_cached_version() -> None:
    prefix = private_docmodel_prefix(owner_id="acct-1", doc_id=_DOC_ID)
    assert prefix.endswith("/")
    for version in (1, 2, 7):
        assert private_docmodel_key(owner_id="acct-1", doc_id=_DOC_ID, version=version).startswith(
            prefix
        )


@pytest.mark.parametrize("bad_owner", ["", "   ", "///"])
def test_an_unverifiable_owner_fails_closed(bad_owner: str) -> None:
    with pytest.raises(ValueError):
        private_docmodel_key(owner_id=bad_owner, doc_id=_DOC_ID, version=1)


def test_owner_segment_is_bounded() -> None:
    assert len(owner_segment("a" * 500)) == 128


def test_a_non_uuid_doc_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        private_docmodel_key(owner_id="acct-1", doc_id="../../escape", version=1)


@pytest.mark.parametrize("bad_version", [0, -1, "1", 1.0, True, None])
def test_a_non_positive_int_version_fails_closed(bad_version) -> None:
    with pytest.raises(ValueError):
        private_docmodel_key(owner_id="acct-1", doc_id=_DOC_ID, version=bad_version)
