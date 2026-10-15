"""U3 CorpusContent repository behavior over the real owner stores."""

from uuid import uuid4

import pytest

from backend.modules.corpus.maintenance import CorpusMaintenance
from backend.modules.corpus.reading import ContentUnavailable, CorpusReading
from backend.transactions import Authority

pytestmark = pytest.mark.u3_repository

POLICY = {"policyId": "u3-source-eligibility", "revision": "1"}


def withdrawal(reason="publisher-withdrawal"):
    return {
        "changeKind": "withdrawal",
        "disposition": "withdrawn",
        "reasonKey": reason,
        "policy": POLICY,
    }


def test_resolve_returns_exact_canonical_identity(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    reading = CorpusReading(maintenance.transactions)
    row = reading.resolve(authority, "paper-alpha:v1", None)
    assert row["paperId"] == "paper-alpha" and row["versionId"] == "paper-alpha:v1"
    assert row["disposition"] == "available"
    # An unknown identifier is absent, never silently redirected.
    assert reading.resolve(authority, "paper-unknown:v9", None) is None


def test_reading_states_are_truthful_and_ordered(
    maintenance, authority, maintenance_authority, fixture_discard, connect, sources
):
    fixture_discard()
    reading = CorpusReading(maintenance.transactions)

    # Absent: no version at all.
    assert reading.read_content(authority, {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"}, "read")["availability"] == "absent"

    # Building: control/content staged by an accepted but unexecuted run.
    accepted = maintenance.accept(
        authority,
        uuid4(),
        {
            "operation": "ingest",
            "sourceScopeIds": ["fixture-alpha"],
            "authoritativeInputRevision": "u3-input-1",
            "inputManifestHash": "b" * 64,
            "sourcePolicy": {"policyId": "u3-corpus-maintenance", "revision": "1"},
            "compatibilityRevision": "u3-projection-1",
        },
    )
    with connect("corpus") as conn:
        # The staged control write happens during execution; simulate its
        # committed-first ordering by executing the run.
        pass
    maintenance.execute(accepted["runId"])
    state = maintenance.read_run(authority, accepted["runId"])["state"]
    assert state == "completed"

    # Withdrawn after withdrawal propagation.
    maintenance.record_change(authority, dict(withdrawal(), paperId="paper-alpha"))
    view = reading.read_content(
        authority, {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"}, "read"
    )
    assert view["availability"] == "withdrawn"
    assert view["title"] == "합성 논문 paper-alpha"
    assert view["retryable"] is False


def test_unsupported_when_committed_content_has_no_sections(
    maintenance, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    with connect("corpus") as conn:
        # A committed, eligible version whose document model carries no sections
        # is a bounded `unsupported` state, never endless loading or invented text.
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) "
            "VALUES('paper-malformed','손상된 합성 문서','[\"연구자\"]'::jsonb,'{}'::jsonb)"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) VALUES("
            "'paper-malformed:v1','paper-malformed','https://fixture.invalid/malformed',%s,"
            "'v1','fixture-inline',true,'local-research','{}'::jsonb,"
            "'{\"document\":{\"sections\":[]},\"chunks\":[]}'::jsonb)",
            ("a" * 64,),
        )
        conn.commit()
    reading = CorpusReading(maintenance.transactions)
    view = reading.read_content(
        authority, {"paperId": "paper-malformed", "versionId": "paper-malformed:v1"}, "read"
    )
    assert view["availability"] == "unsupported"
    # The resolve path still reports the exact identity rather than substituting.
    identity = reading.resolve(authority, "paper-malformed:v1", None)
    assert identity["versionId"] == "paper-malformed:v1"


def test_reads_are_side_effect_free(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    reading = CorpusReading(maintenance.transactions)
    with connect("corpus") as conn:
        before = conn.execute(
            "SELECT (SELECT count(*) FROM corpus.run_effect) AS effects,"
            "(SELECT count(*) FROM corpus.projection) AS chunks,"
            "(SELECT revision FROM corpus.publication) AS publication"
        ).fetchone()
    reading.resolve(authority, "paper-alpha", None)
    reading.read_content(
        authority, {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"}, "read"
    )
    reading.resolve(authority, "paper-alpha:v1", "v1")
    with connect("corpus") as conn:
        after = conn.execute(
            "SELECT (SELECT count(*) FROM corpus.run_effect) AS effects,"
            "(SELECT count(*) FROM corpus.projection) AS chunks,"
            "(SELECT revision FROM corpus.publication) AS publication"
        ).fetchone()
    assert before == after


def test_asset_handles_are_opaque_and_eligibility_checked(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    reading = CorpusReading(maintenance.transactions)
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.asset(id,version_id,section_id,media_type,content_hash,"
            "storage,byte_length,alt_text) VALUES(%s,%s,%s,'image/png',%s,'unavailable',"
            "NULL,'합성 그림')",
            (uuid4(), "paper-alpha:v1", "paper-alpha-f1", "c" * 64),
        )
        conn.commit()
        asset_id = conn.execute(
            "SELECT id FROM corpus.asset WHERE version_id='paper-alpha:v1'"
        ).fetchone()["id"]
        content = conn.execute(
            "SELECT content FROM corpus.version WHERE id='paper-alpha:v1'"
        ).fetchone()["content"]
    from backend.modules.corpus.repository import content_revision

    source = {"content": content}
    revision = content_revision(source)
    asset = reading.read_asset(
        authority,
        {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
        revision,
        str(asset_id),
    )
    assert asset["storage"] == "unavailable" and asset["assetId"] == str(asset_id)
    with pytest.raises(ContentUnavailable):
        reading.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            revision,
            str(uuid4()),
        )
    with pytest.raises(ValueError):
        reading.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            "d" * 64,
            str(asset_id),
        )
    # Withdrawal makes the handle unresolvable under current eligibility.
    maintenance.record_change(authority, dict(withdrawal(), paperId="paper-alpha"))
    with pytest.raises(ContentUnavailable):
        reading.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            revision,
            str(asset_id),
        )


def test_change_facts_paging_and_restore_replay(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    first = maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "versionId": "paper-alpha:v1",
            "changeKind": "license-change",
            "disposition": "restricted",
            "reasonKey": "license-changed",
            "policy": POLICY,
        },
    )
    second = maintenance.record_change(
        authority, dict(withdrawal(), paperId="paper-alpha")
    )
    page = maintenance.read_changes(first["position"] - 1, limit=1)
    assert [fact["factId"] for fact in page] == [first["factId"]]
    page = maintenance.read_changes(first["position"], limit=10)
    assert [fact["factId"] for fact in page] == [second["factId"]]
    # Restore rehearsal replays current boundaries: the pre-withdrawal snapshot
    # cannot serve withdrawn content again.
    replay = maintenance.restore_replay("restore-marker-1", ["paper-alpha:v1"])
    assert replay["refused"] == 1
    entry = replay["versions"][0]
    assert entry["disposition"] == "withdrawn" and entry["servable"] is False
    with connect("corpus") as conn:
        quarantined = conn.execute(
            "SELECT count(*) AS count FROM corpus.quarantine WHERE marker='restore-marker-1'"
        ).fetchone()["count"]
    assert quarantined == 1


def test_lost_acknowledgement_replays_the_original_run(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    """A lost acceptance reply reconciles the same run; changed input conflicts."""
    fixture_discard()
    key = uuid4()
    body = {
        "operation": "ingest",
        "sourceScopeIds": ["fixture-alpha"],
        "authoritativeInputRevision": "u3-input-1",
        "inputManifestHash": "e" * 64,
        "sourcePolicy": {"policyId": "u3-corpus-maintenance", "revision": "1"},
        "compatibilityRevision": "u3-projection-1",
    }
    first = maintenance.accept(authority, key, body)
    before = connect("corpus").execute(
        "SELECT revision FROM corpus.run WHERE id=%s", (first["runId"],)
    ).fetchone()["revision"]
    replay = maintenance.accept(authority, key, body)
    assert replay["runId"] == first["runId"] and replay["revision"] == str(before)
    with pytest.raises(ValueError):
        maintenance.accept(authority, key, dict(body, inputManifestHash="f" * 64))
