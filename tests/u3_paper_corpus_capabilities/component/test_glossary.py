"""U3 glossary component behavior: normalization, virtual-empty, CAS inputs."""

import unicodedata

import pytest

from backend.modules.summarization.u3_glossary import (
    GlossaryConflict,
    GlossaryInvalid,
    GlossaryService,
    normalize_terms,
    virtual_revision,
)

pytestmark = pytest.mark.u3_component


def test_normalization_composes_unicode_and_trims_whitespace():
    normalized = normalize_terms(
        [
            {"termId": None, "source": "  e\u0301tude  ", "preferred": " 연구 ", "languageId": "ko"}
        ]
    )[0]
    assert normalized["source"] == unicodedata.normalize("NFC", "étude")
    assert normalized["preferred"] == "연구"
    assert normalized["termId"].startswith("term-")


def test_normalization_rejects_empty_control_and_oversized_terms():
    for bad in (
        [{"termId": None, "source": "   ", "preferred": "x", "languageId": "ko"}],
        [{"termId": None, "source": "a\u0000b", "preferred": "x", "languageId": "ko"}],
        [{"termId": None, "source": "a" * 65, "preferred": "x", "languageId": "ko"}],
        [{"termId": None, "source": "a", "preferred": "x", "languageId": "fr"}],
        [{"termId": None, "source": 7, "preferred": "x", "languageId": "ko"}],
    ):
        with pytest.raises(GlossaryInvalid):
            normalize_terms(bad)


def test_normalization_rejects_duplicates_after_casefold():
    with pytest.raises(GlossaryInvalid):
        normalize_terms(
            [
                {"termId": None, "source": "Attention", "preferred": "어텐션", "languageId": "ko"},
                {"termId": None, "source": "attention", "preferred": "주의", "languageId": "ko"},
            ]
        )
    with pytest.raises(GlossaryInvalid):
        normalize_terms(
            [
                {"termId": None, "source": "same", "preferred": "같음", "languageId": "ko"},
                {"termId": None, "source": "other", "preferred": "같음", "languageId": "ko"},
            ]
        )


def test_term_allocation_is_finite():
    with pytest.raises(GlossaryInvalid):
        normalize_terms(
            [
                {"termId": None, "source": f"s{index}", "preferred": f"p{index}", "languageId": "ko"}
                for index in range(65)
            ]
        )


def test_virtual_revision_token_is_policy_bound_and_sql_consistent(
    transactions, authority, fixture_discard, connect
):
    fixture_discard()
    token = virtual_revision(authority.account_id)
    assert token == f"empty:{authority.account_id}:u3-owner-glossary-v1"
    service = GlossaryService(transactions)
    view = service.read(authority)
    assert view["revision"] == token and view["terms"] == []
    # The SQL read used by canonical acceptance returns the identical token.
    with connect("assistance") as conn:
        row = conn.execute(
            "SELECT revision FROM assistance.read_glossary(%s)", (authority.account_id,)
        ).fetchone()
    assert row["revision"] == token


def test_conflicting_write_preserves_committed_terms(
    transactions, authority, fixture_discard
):
    fixture_discard()
    service = GlossaryService(transactions)
    empty = service.read(authority)
    written = service.replace(
        authority,
        {
            "expectedRevision": empty["revision"],
            "normalizationPolicy": {"policyId": "u3-owner-glossary", "revision": "1"},
            "terms": [
                {"termId": None, "source": "attention", "preferred": "어텐션", "languageId": "ko"}
            ],
        },
    )
    with pytest.raises(GlossaryConflict):
        service.replace(
            authority,
            {
                "expectedRevision": empty["revision"],
                "normalizationPolicy": {"policyId": "u3-owner-glossary", "revision": "1"},
                "terms": [],
            },
        )
    assert service.read(authority)["terms"] == written["terms"]
    with pytest.raises(ValueError):
        service.replace(
            authority,
            {
                "expectedRevision": written["revision"],
                "normalizationPolicy": {"policyId": "other", "revision": "1"},
                "terms": [],
            },
        )
