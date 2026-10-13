"""Real owner transactions for canonical preparation; no normal model claim."""

from copy import deepcopy
from uuid import uuid4

import pytest
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb

from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority

pytestmark = pytest.mark.u1_repository


@pytest.fixture
def canonical_input(repositories, connect):
    r = repositories
    with connect("assistance") as conn:
        original = conn.execute(
            "SELECT revision,snapshot FROM assistance.glossary WHERE account_id=%s",
            (r["ids"]["a"],),
        ).fetchone()
        conn.execute(
            "INSERT INTO assistance.glossary(account_id,revision,snapshot) VALUES(%s,'typed-fixture-v1','[]') "
            "ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,snapshot=excluded.snapshot",
            (r["ids"]["a"],),
        )
    with connect("corpus") as conn:
        revision = conn.execute(
            "SELECT eligibility_revision FROM corpus.version WHERE id=%s", (r["ids"]["version"],)
        ).fetchone()[0]
    request = {
        "paper": {
            "paperId": r["ids"]["paper"],
            "versionId": r["ids"]["version"],
            "eligibilityRevision": str(revision),
        },
        "contentRevision": "diagnostic-codec-tested-separately",
        "contentHash": "a" * 64,
        "operation": "summary",
        "optionId": "diagnostic-selected-source",
        "optionsRevision": "diagnostic-v1",
        "glossaryRevision": "typed-fixture-v1",
        "processingPolicy": {"policyId": "local-research", "revision": "1"},
    }
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "action": "summary",
        "fixtureFamily": "repository-boundary",
        "request": request,
        "selectedSections": [],
    }
    yield payload
    with connect("assistance") as conn:
        if original:
            conn.execute(
                "UPDATE assistance.glossary SET revision=%s,snapshot=%s WHERE account_id=%s",
                (original[0], Jsonb(original[1]), r["ids"]["a"]),
            )
        else:
            conn.execute(
                "DELETE FROM assistance.glossary WHERE account_id=%s AND revision IN ('typed-fixture-v1','typed-fixture-v2')",
                (r["ids"]["a"],),
            )


def test_preparation_freezes_glossary_before_acceptance_and_replay(
    repositories, canonical_input, connect
):
    r, operation = repositories, uuid4()
    prepared = r["pa"].prepare_request(r["authority"], operation, canonical_input)
    assert prepared["intent_hash"] == intent_digest(prepared["intent"])
    assert prepared["intent"]["acceptedInput"]["glossary"]["ownerId"] == str(r["ids"]["a"])
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.glossary SET revision='typed-fixture-v2' WHERE account_id=%s",
            (r["ids"]["a"],),
        )
    assert r["pa"].replay_request(r["authority"], operation, canonical_input["request"]) == prepared
    assert r["pa"].prepare_request(r["authority"], operation, canonical_input) == prepared
    service = AssistanceAdmission(r["pa"], r["usage"])
    job = service.accept(r["authority"], operation, prepared["intent"])
    assert job["glossary_revision"] == "typed-fixture-v1"
    assert job["glossary_snapshot"] == []
    assert job["payload"] == prepared["intent"]
    replay = service.accept(r["authority"], operation, prepared["intent"])
    assert replay["accepted_at"] == job["accepted_at"]


@pytest.mark.parametrize("field", ["glossaryRevision", "eligibilityRevision"])
def test_stale_revision_creates_no_preparation(repositories, canonical_input, field, connect):
    r, operation = repositories, uuid4()
    if field == "eligibilityRevision":
        canonical_input["request"]["paper"][field] = str(uuid4())
    else:
        canonical_input["request"][field] = "stale"
    with pytest.raises(ValueError, match="revision conflict"):
        r["pa"].prepare_request(r["authority"], operation, canonical_input)
    with connect("assistance") as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM assistance.admission WHERE operation_id=%s", (operation,)
            ).fetchone()
            is None
        )


def test_changed_request_conflicts_and_current_withdrawal_precedes_replay(
    repositories, canonical_input, connect
):
    r, operation = repositories, uuid4()
    r["pa"].prepare_request(r["authority"], operation, canonical_input)
    changed = deepcopy(canonical_input)
    changed["request"]["optionId"] = "different-intent"
    with pytest.raises(ValueError, match="identity conflict"):
        r["pa"].prepare_request(r["authority"], operation, changed)
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.version SET eligible=false WHERE id=%s", (r["ids"]["version"],))
    with pytest.raises(InsufficientPrivilege):
        r["pa"].replay_request(r["authority"], operation, canonical_input["request"])


def test_valid_other_account_cannot_replay_a_preparation(repositories, canonical_input, connect):
    r, operation, session = repositories, uuid4(), uuid4()
    r["pa"].prepare_request(r["authority"], operation, canonical_input)
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '1 hour')",
            (session, r["ids"]["b"], str(session), str(uuid4()), r["ids"]["revision"]),
        )
    other = Authority(r["ids"]["b"], session)
    assert r["pa"].replay_request(other, uuid4(), canonical_input["request"]) is None
    with pytest.raises(ValueError, match="identity conflict"):
        r["pa"].replay_request(other, operation, canonical_input["request"])
    assert (
        r["pa"].replay_request(r["authority"], operation, canonical_input["request"])["account_id"]
        == r["ids"]["a"]
    )
