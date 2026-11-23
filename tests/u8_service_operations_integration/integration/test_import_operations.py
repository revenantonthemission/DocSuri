"""The owners' import operations on the realm (U8 plan Step 32; A4, BR8.1–BR8.8, BR8.13,
BR8.14).

The synthetic v1 (`v1_flows.SyntheticV1`) is read through v1's own tables, and every
record is written by its owner's import operation into a rehearsal database of the
test's own (with the composed realm's schema), never `docsuri_u8`: AccountAccess's
`importAccount` and `importIdentityLink`, Personalization's `importSettings`,
CorpusContent's `importPaper` and Library's `importSavedPaper`, under the decisions
Workflow 10 proposes, each recorded as your decision would record it.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.modules.accounts.repository.imports import NO_PASSWORD
from backend.modules.discovery.u8_search import VECTOR_POLICY, StandinEmbeddings
from backend.modules.operations.ledger_records import MISFIT_REASONS
from backend.modules.operations.migration.identities import link_source_id, target_id
from backend.modules.operations.migration.misfits import (
    MAPPING_RULES,
    PROPOSALS,
    Decision,
    Decisions,
)
from backend.modules.operations.migration.phases import ImportRun
from backend.modules.operations.migration.v1_source import V1Source
from backend.transactions import OwnerTransactions
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.migration.realm import RealmDatabases, owners_for
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration import v1_flows as vf
from tests.u8_service_operations_integration.conftest import Clock

pytestmark = pytest.mark.usefixtures("own_address")


def proposed() -> Decisions:
    return Decisions({pair: Decision(decision, MAPPING_RULES.get(pair) if decision == "map"
                                     else None) for pair, decision in PROPOSALS.items()})


@pytest.fixture(scope="module")
def migrated(realm):
    v1 = vf.SyntheticV1(realm).create()
    databases = RealmDatabases.for_realm(realm.root)
    rehearsal = REALM_DATABASES.new("rehearsal")
    databases.create_rehearsal(rehearsal)
    owners, close = owners_for(realm)(rehearsal)
    clock = Clock()
    try:
        with v1.connect() as conn:
            source = V1Source(conn, index_documents=v1.index_documents(), objects=v1.objects())
            tallies = ImportRun(source, owners, proposed(), clock=clock).run()
            again = ImportRun(source, owners, proposed(), clock=clock).run()
        yield {"v1": v1, "rehearsal": rehearsal, "tallies": tallies, "again": again,
               "profile": dataclasses.replace(realm, database_name=rehearsal),
               "owners": owners, "clock": clock}
    finally:
        close()
        rf.drop_database(realm, rehearsal)
        v1.drop()


def reasons(tallies) -> set[str]:
    return {reason for tally in tallies.values() for _, _, reason in tally.misfits}


def owner_rows(migrated, owner: str, query: str, params=()) -> list:
    transactions = OwnerTransactions(migrated["profile"])
    try:
        return transactions.run(owner, lambda conn: conn.execute(query, params).fetchall())
    finally:
        transactions.close()


def test_each_misfit_reason_is_produced_by_a_record_of_the_synthetic_v1(migrated):
    # No synthetic record makes CorpusContent's three refusals happen by themselves: they
    # are shown by `test_a_time_refused_paper_is_a_misfit_and_the_rest_import` and
    # `test_a_paper_whose_versions_differ_in_title_is_a_misfit_and_the_run_carries_on`
    # (Step 69(h)), and by the repository part's tests of `PaperImport`.
    assert reasons(migrated["tallies"]) == set(MISFIT_REASONS) - {
        "refused-by-database-time-limits", "paper-metadata-changed", "version-content-changed"}
    kinds = {kind for tally in migrated["tallies"].values() for kind, _, _ in tally.misfits}
    assert {"account", "identity-link", "preferences", "paper", "paper-content",
            "paper-embedding", "paper-figure", "saved-paper", "followed-topic"} <= kinds
    accounts = migrated["tallies"]["account"]
    ids = migrated["v1"].ids
    misfit = {(source, reason) for _, source, reason in accounts.misfits}
    for name, reason in (("orcid-only", "no-email"), ("pending", "unverified-in-v1"),
                         ("deactivated", "closed-in-v1"), ("deleting", "closed-in-v1"),
                         ("case-a", "email-case-conflict"), ("case-b", "email-case-conflict"),
                         ("locked", "locked-in-v1")):
        assert (ids[name], reason) in misfit, (name, reason)
    links = {(source, reason) for _, source, reason in migrated["tallies"][
        "identity-link"].misfits}
    assert (link_source_id("google", "google-active-pending"), "unconfirmed-link") in links
    assert (link_source_id("google", "google-provider-2"), "duplicate-provider-link") in links
    assert (link_source_id("google", "google-pending-account"),
            "dependency-not-migrated") in links


def test_a_carried_argon2id_hash_signs_in_and_a_provider_only_account_has_no_password(
    migrated,
):
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService

    v1 = migrated["v1"]
    transactions = OwnerTransactions(migrated["profile"])
    try:
        entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY,
                                            clock=migrated["clock"])
        signed = entry.login(v1.email("active"), vf.V1_PASSWORD, flow_binding="migrated")
        assert signed.public["state"] == "consent_pending"
        with pytest.raises(PermissionError):
            entry.login(v1.email("provider"), vf.V1_PASSWORD, flow_binding="migrated")
    finally:
        transactions.close()
    [row] = owner_rows(migrated, "accounts", "SELECT password_hash,reset_required,"
                       "display_name FROM accounts.account WHERE id=%s",
                       (target_id("account", v1.ids["provider"]),))
    assert row["password_hash"] == NO_PASSWORD and row["reset_required"] is False
    [legacy] = owner_rows(migrated, "accounts", "SELECT password_hash,reset_required,role "
                          "FROM accounts.account WHERE id=%s",
                          (target_id("account", v1.ids["legacy"]),))
    assert legacy["reset_required"] is True and legacy["password_hash"] == NO_PASSWORD
    assert legacy["role"] == "administrator"
    [orcid] = owner_rows(migrated, "accounts", "SELECT display_name FROM accounts.account "
                         "WHERE id=%s", (target_id("account", v1.ids["orcid"]),))
    assert orcid["display_name"] == "Ada Synthetic"


def test_closed_accounts_are_never_active(migrated):
    v1 = migrated["v1"]
    closed = [target_id("account", v1.ids[name]) for name in ("deactivated", "deleting",
                                                              "pending")]
    assert owner_rows(migrated, "accounts", "SELECT id FROM accounts.account WHERE "
                      "id = ANY(%s)", (closed,)) == []
    [locked] = owner_rows(migrated, "accounts", "SELECT active,reset_required FROM "
                          "accounts.account WHERE id=%s",
                          (target_id("account", v1.ids["locked"]),))
    assert locked["reset_required"] is True


def test_a_paper_matched_by_its_canonical_identity_is_linked_not_duplicated(migrated):
    papers = owner_rows(migrated, "corpus", "SELECT id FROM corpus.paper ORDER BY id")
    versions = owner_rows(migrated, "corpus", "SELECT id,paper_id FROM corpus.version "
                          "ORDER BY id")
    assert [row["id"] for row in papers] == ["arxiv:2101.00001", "arxiv:2101.00006"]
    assert [(row["id"], row["paper_id"]) for row in versions] == [
        ("arxiv:2101.00001@v1", "arxiv:2101.00001"), ("arxiv:2101.00001@v2", "arxiv:2101.00001"),
        ("arxiv:2101.00006@v1", "arxiv:2101.00006")]
    saved = owner_rows(migrated, "library", "SELECT account_id,paper_id,version_id FROM "
                       "library.saved_paper ORDER BY account_id")
    owner = target_id("account", migrated["v1"].ids["active"])
    mine = [row for row in saved if row["account_id"] == owner]
    assert [(row["paper_id"], row["version_id"]) for row in mine] == [
        ("arxiv:2101.00001", "arxiv:2101.00001@v2")]
    assert migrated["tallies"]["saved-paper"].mapped == 1


def test_every_imported_chunk_has_a_vector_from_the_pinned_embedder(migrated):
    rows = owner_rows(migrated, "corpus", "SELECT version_id,text_content,embedding,"
                      "vector_policy,embedding_vector IS NOT NULL AS indexed FROM "
                      "corpus.projection ORDER BY version_id,ordinal")
    # Three for each imported version: 2101.00001's two and 2101.00006's one.
    assert len(rows) == 9
    embedder = StandinEmbeddings()
    for row in rows:
        assert row["vector_policy"] == VECTOR_POLICY and row["indexed"]
        assert row["embedding"] == pytest.approx(embedder.embed_query(row["text_content"]))
    # v1's vectors were offered but never reused: each version's embeddings are mapped;
    # 2101.00006's index document carries no vector.
    assert migrated["tallies"]["paper-embedding"].mapped == 2


def test_a_second_pass_over_the_same_snapshot_imports_and_updates_nothing(migrated):
    again = migrated["again"]
    assert sum(tally.imported + tally.updated for tally in again.values()) == 0
    first = migrated["tallies"]
    assert {kind: tally.unchanged for kind, tally in again.items()} == {
        kind: tally.imported + tally.unchanged for kind, tally in first.items()}
    assert first["account"].imported == 5


# --- a paper only v1's index names (U8 plan Steps 68(f), 69(f); L1-57) ------------------------


def test_a_paper_that_only_v1s_index_names_is_imported_with_its_saved_paper(migrated):
    v1 = migrated["v1"]
    pairs = [("2101.00001", 1), ("2101.00001", 2), ("2101.00002", 1), ("2101.00003", 1),
             ("2101.00004", 1), ("2101.00006", 1)]
    with v1.connect() as conn:
        source = V1Source(conn, index_documents=v1.index_documents(), objects=v1.objects())
        papers = source.papers()
        assert [(paper.paper_id, paper.version) for paper in papers] == pairs
        by_pair = {(paper.paper_id, paper.version): paper for paper in papers}
        for pair, paper in by_pair.items():
            if pair == ("2101.00006", 1):
                continue
            assert paper.doc_model_ref == (
                f"s3://docsuri-synthetic/doc-model/{pair[0]}/v{pair[1]}.json")
            assert paper.status == "ACTIVE"
        index_only = by_pair[("2101.00006", 1)]
        assert index_only.doc_model_ref == "doc-model/2101.00006/v1.json"
        assert index_only.status == "index-only"
        assert source.document("doc-model/2101.00006/v1.json") == vf.document("2101.00006", 1)
        assert {pair: paper.figures for pair, paper in by_pair.items()} == {
            pair: int(pair in {("2101.00001", 1), ("2101.00006", 1)}) for pair in pairs}
        # What names no paper: a second chunk, a private document, no version, version 0.
        extra = [{**v1.index_documents()[-1], "chunkId": "2101.00006:1:1"},
                 {"paperId": "userdoc:11111111-1111-4111-8111-111111111111", "version": 1},
                 {"paperId": "2101.00007"}, {"paperId": "2101.00008", "version": 0}]
        more = V1Source(conn, index_documents=v1.index_documents() + extra,
                        objects=v1.objects())
        assert [(paper.paper_id, paper.version) for paper in more.papers()] == pairs
    named = [item for tally in migrated["tallies"].values() for item in tally.misfits
             if item[1] == "2101.00006:v1"]
    assert named == [("paper-figure", "2101.00006:v1", "no-v2-home")]
    orcid = target_id("account", v1.ids["orcid"])
    saved = owner_rows(migrated, "library", "SELECT paper_id,version_id FROM "
                       "library.saved_paper WHERE account_id=%s", (orcid,))
    assert {(row["paper_id"], row["version_id"]) for row in saved} == {
        ("arxiv:2101.00001", "arxiv:2101.00001@v2"), ("arxiv:2101.00006", "arxiv:2101.00006@v1")}
    assert not [item for item in migrated["tallies"]["saved-paper"].misfits
                if item[1] == f"saved-6-{v1.ids['active']}"]


# --- CorpusContent's refusals as misfits (U8 plan Steps 68(h), 69(h); L1-75) -------------------


@pytest.fixture
def rehearsal(realm):
    """A rehearsal database of the test's own, with its owners, over the realm."""
    databases = RealmDatabases.for_realm(realm.root)
    name = REALM_DATABASES.new("rehearsal")
    databases.create_rehearsal(name)
    owners, close = owners_for(realm)(name)
    try:
        yield {"name": name, "owners": owners,
               "profile": dataclasses.replace(realm, database_name=name)}
    finally:
        close()
        rf.drop_database(realm, name)


def test_a_time_refused_paper_is_a_misfit_and_the_rest_import(migrated, rehearsal):
    from backend.modules.operations.migration import parity

    v1, clock = migrated["v1"], migrated["clock"]
    with v1.connect() as conn, vf.refusing("arxiv:2101.00006@v1", "sleep"):
        source = V1Source(conn, index_documents=v1.index_documents(), objects=v1.objects())
        tallies = ImportRun(source, rehearsal["owners"], proposed(), clock=clock).run()
    assert ("paper", "2101.00006:v1", "refused-by-database-time-limits") in tallies[
        "paper"].misfits
    assert tallies["paper"].skipped["refused-by-database-time-limits"] == 1
    versions = owner_rows(rehearsal, "corpus", "SELECT id FROM corpus.version ORDER BY id")
    assert [row["id"] for row in versions] == ["arxiv:2101.00001@v1", "arxiv:2101.00001@v2"]
    assert ("saved-paper", f"saved-6-{v1.ids['active']}",
            "dependency-not-migrated") in tallies["saved-paper"].misfits
    assert parity.build("time-refused", tallies, rehearsal["owners"], now=clock())[
        "reconciles"] is True


def test_a_paper_whose_versions_differ_in_title_is_a_misfit_and_the_run_carries_on(
    migrated, rehearsal, tmp_path,
):
    from backend.modules.operations.migration_records import MigrationRuns

    v1, clock = migrated["v1"], migrated["clock"]
    documents = [
        {**item, "title": "Synthetic paper 2101.00001, retitled"}
        if (item["paperId"], item["version"]) == ("2101.00001", 2) else item
        for item in v1.index_documents()]
    with v1.connect() as conn:
        source = V1Source(conn, index_documents=documents, objects=v1.objects())
        tallies = ImportRun(source, rehearsal["owners"], proposed(), clock=clock).run()
    assert ("paper", "2101.00001:v2", "paper-metadata-changed") in tallies["paper"].misfits
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        runs = MigrationRuns(ledger, clock=clock)
        run_id = _dry_run(ledger)
        runs.record_misfits(run_id, [item for tally in tallies.values()
                                     for item in tally.misfits])
        assert ledger.get("misfit-record", (run_id, "paper", "2101.00001:v2",
                                            "paper-metadata-changed")) is not None
    finally:
        ledger.close()


def test_private_uploads_are_counted_from_the_snapshots_objects(migrated, caplog):
    """U8 plan Step 90(h) (L1-20): v1's private uploads are counted from the copy's
    object listing, by an opaque id, and archive-only by proposal."""
    import json
    import logging

    from backend.modules.operations.migration import parity
    from backend.modules.operations.migration.v1_source import upload_source_id

    v1, owners, clock = migrated["v1"], migrated["owners"], migrated["clock"]
    listing = v1.listing()
    (key,) = [item["key"] for item in listing if item["key"].startswith("uploads/")]
    owner = v1.ids["active"]
    withheld = (key, "paper.pdf", "attachment-1")

    def run(entries):
        with v1.connect() as conn:
            source = V1Source(conn, index_documents=v1.index_documents(),
                              objects=v1.objects(), listing=entries)
            return ImportRun(source, owners, proposed(), clock=clock).run()

    caplog.set_level(logging.DEBUG)
    tallies = run(listing)
    uploads = [item for tally in tallies.values() for item in tally.misfits
               if item[0] == "private-upload"]
    assert uploads == [("private-upload", upload_source_id(key), "not-in-scope")]
    source_id = uploads[0][1]
    assert source_id != key and not any(part in source_id for part in (*withheld, owner))
    assert PROPOSALS[("private-upload", "not-in-scope")] == "archive-only"
    assert proposed().of("private-upload", "not-in-scope") == "archive-only"
    report = parity.build("uploads", tallies, owners, now=clock())
    entry = next(item for item in report["kinds"] if item["kind"] == "private-upload")
    assert entry["source"] == 1 and entry["excluded"] == {"archive-only": 1}
    assert entry["misfits"] == [{"kind": "private-upload", "sourceId": source_id,
                                 "reasonKey": "not-in-scope", "newInFinal": False}]
    assert owner not in json.dumps(entry)
    # Nothing names the upload's key or file, in any misfit, the report or a log line.
    texts = [json.dumps(report, sort_keys=True), *(record.getMessage()
                                                   for record in caplog.records),
             *(json.dumps(item) for tally in tallies.values() for item in tally.misfits)]
    for text in texts:
        assert not any(part in text for part in withheld), text
    for record in caplog.records:
        assert owner not in record.getMessage()

    # A listing with no upload counts none.
    without = run([item for item in listing if not item["key"].startswith("uploads/")])
    assert without["private-upload"].misfits == [] and without["private-upload"].source == 0


def _dry_run(ledger) -> str:
    """A dry run recorded straight into a private ledger, as a start would record it."""
    from uuid import uuid4

    from backend.modules.operations.ledger import utc_text

    record = {"runId": str(uuid4()), "kind": "dry", "target": "rehearsal",
              "toolCommit": "0" * 40, "decisionsDigest": "0" * 64, "state": "preparing",
              "startedAt": utc_text(ledger.clock())}
    ledger.atomic(lambda view: view.append("migration-run", record, expect_revision=0))
    return record["runId"]


# --- the corpus limit record (U8 plan Steps 68(i), 69(i); L1-79) --------------------------------


def test_the_paper_tally_records_each_limits_largest_value_and_refusals(migrated, realm):
    from backend.modules.corpus.limits import PRODUCTION_LIMITS

    rows = owner_rows(migrated, "corpus", "SELECT private_path FROM corpus.version")
    folder = realm.root / "corpus-files"
    largest = max((folder / row["private_path"]).stat().st_size for row in rows)
    record = migrated["tallies"]["paper"].limits.as_dict()
    assert record == {
        "profile": "production",
        "chunks": {"limit": PRODUCTION_LIMITS.max_chunks, "checked": True, "largest": 3,
                   "refused": 1},
        "sourceBytes": {"limit": 16_777_216, "checked": True, "largest": largest,
                        "refused": 0},
        "elements": {"limit": 250_000, "checked": False, "largest": None, "refused": 0},
        "depth": {"limit": 256, "checked": False, "largest": None, "refused": 0},
    }
    exceeding = [item for item in migrated["tallies"]["paper"].misfits
                 if item[0] == "paper" and item[2] == "exceeds-v2-limit"]
    assert exceeding == [("paper", "2101.00002:v1", "exceeds-v2-limit")]
    assert sum(entry["refused"] for name, entry in record.items() if name != "profile") == 1
    assert migrated["again"]["paper"].limits == migrated["tallies"]["paper"].limits
