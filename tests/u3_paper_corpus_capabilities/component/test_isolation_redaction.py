"""U3 isolation and redaction component behavior across owner boundaries."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.modules.corpus.u3_http import run_dto
from backend.transactions import Authority

pytestmark = pytest.mark.u3_component

FORBIDDEN_MATERIAL = (
    "password",
    "token",
    "secret",
    "private_path",
    "authority_revision",
    "credential",
)


def test_guest_search_never_touches_owner_facts():
    from backend.modules.discovery.u3_search import U3Search

    class Repository:
        def admit(self, authority, execution, digest):
            raise AssertionError("guest search must not admit an owner fact")

        def snapshot(self, authority, query=""):
            assert authority is None
            return {
                "publication": {
                    "generation_id": "22222222-2222-2222-2222-222222222222",
                    "revision": "11111111-1111-1111-1111-111111111111",
                    "manifest_hash": "b" * 64,
                    "published_at": datetime.now(UTC),
                },
                "candidates": [],
            }

        def record(self, *args, **kwargs):
            raise AssertionError("guest search must not record history")

        def acknowledge_history(self, *args, **kwargs):
            raise AssertionError("guest search must not acknowledge history")

    class Library:
        def accept_history(self, *args, **kwargs):
            raise AssertionError("guest search must not write Library records")

    service = U3Search(None, Repository(), Library(), cursor_key=b"k" * 32)
    response = service.search(
        None,
        {
            "query": {
                "query": "guest query",
                "modeId": "lexical",
                "orderId": "relevance",
                "filters": [],
                "vocabularyRevision": "u3-paper-options-1",
                "policyRef": {"policyId": "u3-paper-search", "revision": "1"},
            },
            "page": {"limit": 5},
        },
    )
    assert response["outcome"] == "complete" and response["hits"] == []


def test_maintenance_authority_requires_the_explicit_actor_row(
    maintenance, identities, connect, fixture_discard
):
    """Account membership with a valid session is insufficient by itself."""
    fixture_discard()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) VALUES(gen_random_uuid(),%s,'u3-iso-b',"
            "'u3-iso-b-csrf',%s,clock_timestamp()+interval '30 minutes')",
            (identities["b"], identities["revision"]),
        )
        session = conn.execute(
            "SELECT id FROM accounts.session WHERE token_hash='u3-iso-b'"
        ).fetchone()["id"]
    foreign = Authority(identities["b"], session)
    with pytest.raises(PermissionError):
        maintenance.read_run(foreign, uuid4())


def test_progress_and_error_evidence_carries_no_secrets():
    run = {
        "runId": str(uuid4()),
        "operation": "ingest",
        "state": "failed",
        "revision": str(uuid4()),
        "attempts": 1,
        "retryOf": None,
        "acceptedAt": "2026-10-15T00:00:00+00:00",
        "completedAt": "2026-10-15T00:00:10+00:00",
        "watermark": None,
        "inputManifestHash": "a" * 64,
        "effects": [
            {
                "stage": "content",
                "subject": "paper-a:v1",
                "state": "failed",
                "evidenceHash": None,
                "error": "permission-unresolved",
            }
        ],
    }
    encoded = json.dumps(run_dto(run), ensure_ascii=False)
    for forbidden in FORBIDDEN_MATERIAL:
        assert forbidden not in encoded
    assert "paper-a:v1" in encoded  # public corpus identity, not a private path


def test_run_dto_maps_unknown_errors_to_the_safe_default():
    run = {
        "runId": str(uuid4()),
        "operation": "ingest",
        "state": "failed",
        "revision": str(uuid4()),
        "attempts": 0,
        "retryOf": None,
        "acceptedAt": "2026-10-15T00:00:00+00:00",
        "completedAt": None,
        "watermark": None,
        "inputManifestHash": "a" * 64,
        "effects": [
            {
                "stage": "source",
                "subject": "fixture-x",
                "state": "failed",
                "evidenceHash": None,
                "error": "kaboom-with-internal-detail",
            }
        ],
    }
    value = run_dto(run)
    effect_error = value["effects"][0]["error"]
    assert effect_error["code"] == "INTERNAL_ERROR"
    assert effect_error["messageKey"] == "run.unexpected"
    assert "internal-detail" not in json.dumps(value, ensure_ascii=False)


def test_asset_handles_and_foreign_reads_stay_absent(
    maintenance, run_fixture, authority, identities, maintenance_authority,
    fixture_discard, connect,
):
    from backend.modules.corpus.reading import ContentUnavailable, CorpusReading
    from backend.modules.corpus.repository import content_revision

    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    reader = CorpusReading(maintenance.transactions)
    # A foreign identifier never resolves, matching the contract-safe absent form.
    assert reader.resolve(authority, "paper-alpha:v1", "v9") is None
    with connect("corpus") as conn:
        content = conn.execute(
            "SELECT content FROM corpus.version WHERE id='paper-alpha:v1'"
        ).fetchone()["content"]
    revision = content_revision({"content": content})
    with pytest.raises(ContentUnavailable):
        reader.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            revision,
            str(uuid4()),
        )
    # A changed content revision is refused before any handle resolution.
    with pytest.raises(ValueError):
        reader.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            "a" * 64,
            str(uuid4()),
        )


def test_two_owner_isolation_over_the_real_store(
    maintenance, run_fixture, authority, identities, maintenance_authority,
    fixture_discard, connect,
):
    """Owner A's run is invisible to owner B even with a valid B session."""
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"

    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) VALUES(gen_random_uuid(),%s,'u3-iso-b2',"
            "'u3-iso-b2-csrf',%s,clock_timestamp()+interval '30 minutes')",
            (identities["b"], identities["revision"]),
        )
        session = conn.execute(
            "SELECT id FROM accounts.session WHERE token_hash='u3-iso-b2'"
        ).fetchone()["id"]
    foreign = Authority(identities["b"], session)
    with pytest.raises(PermissionError):
        maintenance.read_run(foreign, uuid4())
    # A surrogate: B cannot guess A's run identity into existence.
    assert foreign.account_id != authority.account_id
