"""U3 content reading component behavior: dispositions and bounded states."""

from uuid import uuid4

import pytest

from backend.modules.corpus.maintenance import CorpusMaintenance
from backend.modules.corpus.reading import ContentUnavailable, CorpusReading
from fixtures import request_body

pytestmark = pytest.mark.u3_component


@pytest.fixture
def reader(maintenance):
    return CorpusReading(maintenance.transactions)


def test_building_state_while_run_is_staged(
    transactions, authority, maintenance_authority, fixture_discard, realm, sources
):
    fixture_discard()
    reader = CorpusReading(transactions)
    # Stage the control/content rows directly (a claimed but uncommitted run).
    stored = sources.records["fixture-alpha"]
    transactions.run("corpus", lambda conn: _stage(conn, stored))
    view = reader.read_content(
        authority, {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"}, "read"
    )
    assert view["availability"] == "building"
    assert view["retryable"] is True
    assert view["title"] == stored["title"]


def _stage(conn, record):
    from psycopg.types.json import Jsonb

    import hashlib
    import json

    content = record["content"]
    content_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    conn.execute(
        "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES(%s,%s,%s,%s) "
        "ON CONFLICT(id) DO NOTHING",
        (record["paperId"], record["title"], Jsonb(record["authors"]), Jsonb({})),
    )
    conn.execute(
        "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
        "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,%s,%s,%s,"
        "'fixture-inline',false,'local-research','{}'::jsonb,'{\"document\":{\"sections\":[]},"
        "\"chunks\":[]}'::jsonb) ON CONFLICT(id) DO NOTHING",
        (
            f"{record['paperId']}:{record['versionLabel']}",
            record["paperId"],
            record["sourceUrl"],
            content_hash,
            record["versionLabel"],
        ),
    )
    return True


def test_exact_version_is_never_substituted(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, sources, reader
):
    fixture_discard()
    from fixtures import source_record

    sources.records["fixture-alpha-v2"] = source_record(
        "fixture-alpha-v2", paper_id="paper-alpha", version_label="v2"
    )
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    assert run_fixture(["fixture-alpha-v2"])["state"] == "completed"
    # Each version resolves its own anchors; v1 is not replaced by v2.
    v1 = reader.resolve(authority, "paper-alpha", "v1")
    v2 = reader.resolve(authority, "paper-alpha", "v2")
    assert v1["versionId"] != v2["versionId"]
    content = reader.read_content(
        authority, {"paperId": "paper-alpha", "versionId": v1["versionId"]}, "read"
    )
    assert content["versionLabel"] == "v1"


def test_foreign_paper_reference_is_absent(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, reader
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    view = reader.read_content(
        authority, {"paperId": "paper-other", "versionId": "paper-alpha:v1"}, "read"
    )
    assert view["availability"] == "absent"


def test_purpose_outside_vocabulary_is_refused(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, reader
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    with pytest.raises(ValueError):
        reader.read_content(
            authority, {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"}, "exfiltrate"
        )


def test_asset_handle_is_uuid_and_revision_bound(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, reader, connect
):
    from backend.modules.corpus.repository import content_revision

    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.asset(id,version_id,section_id,media_type,content_hash,"
            "storage,byte_length,alt_text) VALUES(%s,'paper-alpha:v1','paper-alpha-f1',"
            "'image/png',%s,'unavailable',NULL,'합성 그림')",
            (uuid4(), "a" * 64),
        )
        conn.commit()
        asset_id = conn.execute(
            "SELECT id FROM corpus.asset WHERE version_id='paper-alpha:v1'"
        ).fetchone()["id"]
        content = conn.execute(
            "SELECT content FROM corpus.version WHERE id='paper-alpha:v1'"
        ).fetchone()["content"]
    revision = content_revision({"content": content})
    record = reader.read_asset(
        authority,
        {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
        revision,
        str(asset_id),
    )
    assert record["storage"] == "unavailable"
    # A non-UUID handle never resolves.
    with pytest.raises(ContentUnavailable):
        reader.read_asset(
            authority,
            {"paperId": "paper-alpha", "versionId": "paper-alpha:v1"},
            revision,
            "../../etc/passwd",
        )


def test_figure_limitations_are_disclosed(
    maintenance, authority, maintenance_authority, fixture_discard, sources, reader, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts
    from fixtures import source_record

    sources.records["fixture-figure"] = source_record(
        "fixture-figure", paper_id="paper-figure", figures=1
    )
    maintenance = CorpusMaintenance(
        maintenance.transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        sources,
    )
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-figure"])
    )
    maintenance.execute(accepted["runId"])
    view = reader.read_content(
        authority, {"paperId": "paper-figure", "versionId": "paper-figure:v1"}, "read"
    )
    assert view["availability"] == "available"
    assert view["coverage"] == "partial"
    assert view["limitations"], "figure unavailability must be disclosed"
    assert view["figures"] == 1


def test_no_invented_text_when_sections_missing(
    maintenance, authority, maintenance_authority, fixture_discard, connect, reader
):
    fixture_discard()
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) "
            "VALUES('paper-empty','빈 문서','[\"연구자\"]'::jsonb,'{}'::jsonb)"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) VALUES("
            "'paper-empty:v1','paper-empty','https://fixture.invalid/empty',%s,'v1',"
            "'fixture-inline',true,'local-research','{}'::jsonb,"
            "'{\"document\":{\"sections\":[]},\"chunks\":[]}'::jsonb)",
            ("b" * 64,),
        )
        conn.commit()
    view = reader.read_content(
        authority, {"paperId": "paper-empty", "versionId": "paper-empty:v1"}, "read"
    )
    assert view["availability"] == "unsupported"
    assert "sections" not in view
