"""The owners' A4 imports and parity reads (Step 8; BR8.2, BR8.3, BR8.10, NFR4.4).

Every record is written through its owner's repository as that owner's login, and
removed again afterwards as the same owner, so the persistent realm keeps its bounds.
"""

from __future__ import annotations

import datetime as dt
import random
import secrets
from datetime import date
from uuid import uuid4

import psycopg
import pytest

from backend.import_parity import parity_digest, stored_digest
from backend.modules.accounts.repository.imports import AccountImports, account_fields
from backend.modules.corpus.limits import PRODUCTION_LIMITS
from backend.modules.corpus.repository import IMPORT_MAX_CHUNKS, CorpusImports
from backend.modules.library.repository.imports import SavedPaperImports, saved_fields
from backend.modules.personalization.import_repository import SettingsImports, settings_fields

CREATED = dt.datetime(2024, 3, 1, 9, 30, tzinfo=dt.UTC)


@pytest.fixture
def created(connect):
    """What a test imported, removed by each owner afterwards."""
    made = {"accounts": [], "links": [], "settings": [], "saved": [], "papers": []}
    yield made
    with connect("library") as conn:
        for account, paper in made["saved"]:
            conn.execute("DELETE FROM library.saved_paper WHERE account_id=%s AND paper_id=%s",
                         (account, paper))
    with connect("personalization") as conn:
        conn.execute("DELETE FROM personalization.settings WHERE account_id=ANY(%s)",
                     (made["settings"],))
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE id=ANY(%s)", (made["links"],))
        conn.execute("DELETE FROM accounts.account WHERE id=ANY(%s)", (made["accounts"],))
    with connect("corpus") as conn:
        for paper, version in made["papers"]:
            conn.execute("DELETE FROM corpus.projection WHERE version_id=%s", (version,))
            conn.execute("DELETE FROM corpus.version WHERE id=%s", (version,))
            conn.execute("DELETE FROM corpus.paper WHERE id=%s", (paper,))


def account_source(**changes) -> dict:
    value = {
        "email": f"imported-{secrets.token_hex(6)}@fixture.invalid",
        "email_verified": True, "role": "member", "display_name": "Imported",
        # An argon2id verifier's shape around salt and hash generated per run (L1-36).
        "password_verifier": (f"$argon2id$v=19$m=65536,t=3,p=4${secrets.token_hex(8)}"
                              f"${secrets.token_hex(16)}"),
        "reset_required": False, "created_at": CREATED,
    }
    return {**value, **changes}


def paper_source(token: str) -> tuple[dict, dict, list[dict]]:
    paper = {"id": f"key:u8-import-{token}", "title": "Synthetic imported paper",
             "authors": ["A. Author"], "publishedOn": date(2024, 1, 2), "metadata": {}}
    version = {"id": f"key:u8-import-{token}@v1", "label": "v1",
               "sourceUrl": "https://example.invalid/imported", "sourceHash": "e" * 64,
               "eligible": True, "content": {"blocks": [{"anchor": "b1", "text": "alpha"}]}}
    rng = random.Random(token)
    chunks = [{"anchor": f"b{index}", "section": "body", "text": f"chunk {index}",
               "embedding": [rng.uniform(-1, 1) for _ in range(1024)]} for index in range(3)]
    return paper, version, chunks


def import_paper(transactions, created, token, **changes):
    paper, version, chunks = paper_source(token)
    version = {**version, **changes}
    result = CorpusImports(transactions).import_paper(
        paper=paper, version=version, chunks=chunks, private_path="synthetic-import",
        provenance={"source": "v1-import"})
    if (paper["id"], version["id"]) not in created["papers"]:
        created["papers"].append((paper["id"], version["id"]))
    return result, paper, version


# 1. Each import writes as its owner, and another owner's login is refused ----------------


def test_each_import_writes_as_its_owner_and_another_owner_is_refused(
        transactions, connect, created, authority):
    accounts = AccountImports(transactions)
    target = uuid4()
    created["accounts"].append(target)
    source = account_source()
    assert accounts.import_account(target, **source)["disposition"] == "imported"
    link = uuid4()
    created["links"].append(link)
    assert accounts.import_identity_link(
        link, account_id=target, provider="orcid", subject=f"0000-{secrets.token_hex(4)}",
        linked_at=CREATED)["disposition"] == "imported"
    created["settings"].append(target)
    assert SettingsImports(transactions).import_settings(
        target, appearance="dark", language="ko", defaults={"timeZone": "Asia/Seoul"}
    )["disposition"] == "imported"
    token = secrets.token_hex(4)
    result, paper, version = import_paper(transactions, created, token)
    assert result["disposition"] == "imported"
    created["saved"].append((authority.account_id, paper["id"]))
    assert SavedPaperImports(transactions).import_saved_paper(
        authority.account_id, paper_id=paper["id"], version_id=version["id"], saved_at=CREATED
    )["disposition"] == "imported"
    with connect("accounts") as conn:
        stored = conn.execute("SELECT email,reset_required,role FROM accounts.account "
                              "WHERE id=%s", (target,)).fetchone()
    assert stored == {"email": source["email"], "reset_required": False, "role": "member"}
    refusals = (
        ("library", "INSERT INTO accounts.account(id,email,password_hash,display_name) "
                    "VALUES(gen_random_uuid(),'x@fixture.invalid','x','x')"),
        ("accounts", "INSERT INTO personalization.settings(account_id) VALUES(gen_random_uuid())"),
        ("library",
         "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('x','x','[]','{}')"),
        ("corpus", "INSERT INTO library.saved_paper(account_id,paper_id,version_id,revision,"
                   "saved_at,disposition) VALUES(gen_random_uuid(),'x','x',gen_random_uuid(),"
                   "now(),'active')"),
    )
    for owner, statement in refusals:
        with connect(owner) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)


def test_a_provider_only_account_stores_no_usable_verifier(transactions, connect, created):
    target = uuid4()
    created["accounts"].append(target)
    result = AccountImports(transactions).import_account(
        target, **account_source(password_verifier=None))
    assert result["disposition"] == "imported"
    with connect("accounts") as conn:
        stored = conn.execute("SELECT password_hash FROM accounts.account WHERE id=%s",
                              (target,)).fetchone()["password_hash"]
    assert not stored.startswith("$argon2")


# 2. A second import of the same record is unchanged ---------------------------------------


def test_a_second_import_of_the_same_record_is_unchanged(transactions, created, authority):
    accounts, settings = AccountImports(transactions), SettingsImports(transactions)
    target, source = uuid4(), account_source()
    created["accounts"].append(target)
    first = accounts.import_account(target, **source)
    again = accounts.import_account(target, **source)
    assert again == {"disposition": "unchanged", "storedDigest": first["storedDigest"]}
    created["settings"].append(target)
    values = {"appearance": "light", "language": "ko", "defaults": {"timeZone": "UTC"}}
    settings.import_settings(target, **values)
    assert settings.import_settings(target, **values)["disposition"] == "unchanged"
    token = secrets.token_hex(4)
    import_paper(transactions, created, token)
    assert import_paper(transactions, created, token)[0]["disposition"] == "unchanged"


# 3. A changed source is updated ----------------------------------------------------------


def test_a_changed_source_is_updated_and_an_immutable_version_is_refused(
        transactions, connect, created, authority):
    accounts = AccountImports(transactions)
    target, source = uuid4(), account_source()
    created["accounts"].append(target)
    first = accounts.import_account(target, **source)
    with connect("accounts") as conn:
        before = conn.execute("SELECT authority_revision FROM accounts.account WHERE id=%s",
                              (target,)).fetchone()["authority_revision"]
    changed = accounts.import_account(target, **{**source, "email_verified": False,
                                                 "reset_required": True})
    assert changed["disposition"] == "updated"
    assert changed["storedDigest"] != first["storedDigest"]
    with connect("accounts") as conn:
        after = conn.execute("SELECT authority_revision,reset_required FROM accounts.account "
                             "WHERE id=%s", (target,)).fetchone()
    assert after["reset_required"] is True and after["authority_revision"] != before
    created["settings"].append(target)
    settings = SettingsImports(transactions)
    settings.import_settings(target, appearance="light", language="ko", defaults={})
    assert settings.import_settings(target, appearance="dark", language="ko", defaults={}
                                    )["disposition"] == "updated"
    token = secrets.token_hex(4)
    _, paper, version = import_paper(transactions, created, token)
    library = SavedPaperImports(transactions)
    created["saved"].append((authority.account_id, paper["id"]))
    library.import_saved_paper(authority.account_id, paper_id=paper["id"],
                               version_id=version["id"], saved_at=CREATED)
    assert library.import_saved_paper(
        authority.account_id, paper_id=paper["id"], version_id=version["id"],
        saved_at=CREATED + dt.timedelta(days=1))["disposition"] == "updated"
    # A written version never changes: a changed source is refused, not rewritten.
    refused = import_paper(transactions, created, token, sourceUrl="https://example.invalid/b")
    assert refused[0]["disposition"] == "refused"
    assert refused[0]["reasonKey"] == "version-content-changed"


def test_a_clashing_email_and_a_second_provider_link_are_refused(transactions, created):
    accounts = AccountImports(transactions)
    first, second = uuid4(), uuid4()
    created["accounts"].extend([first, second])
    source = account_source()
    accounts.import_account(first, **source)
    clash = accounts.import_account(second, **{**source})
    assert clash["disposition"] == "refused" and clash["reasonKey"] == "email-taken"
    links = [uuid4(), uuid4()]
    created["links"].extend(links)
    accounts.import_identity_link(links[0], account_id=first, provider="google",
                                  subject="g-" + secrets.token_hex(4), linked_at=CREATED)
    duplicate = accounts.import_identity_link(
        links[1], account_id=first, provider="google", subject="g-" + secrets.token_hex(4),
        linked_at=CREATED)
    assert duplicate["reasonKey"] == "duplicate-provider-link"
    orphan = accounts.import_identity_link(
        uuid4(), account_id=uuid4(), provider="orcid", subject="o-" + secrets.token_hex(4),
        linked_at=CREATED)
    assert orphan["reasonKey"] == "dependency-not-migrated"


def test_a_saved_paper_whose_paper_was_not_imported_is_refused(transactions, authority):
    result = SavedPaperImports(transactions).import_saved_paper(
        authority.account_id, paper_id="key:never-imported", version_id="key:never-imported@v1",
        saved_at=CREATED)
    assert result["disposition"] == "refused"
    assert result["reasonKey"] == "dependency-not-migrated"


def test_the_import_bound_is_the_chunk_limit(transactions, connect):
    """One value bounds both the conversion and the write (L1-74, Step 50(h)): the
    import refuses N + 1 chunks before any write. `convert()` refuses an oversized paper
    first, so no other test reaches this bound."""
    assert IMPORT_MAX_CHUNKS == PRODUCTION_LIMITS.max_chunks == 200
    token = secrets.token_hex(4)
    paper, version, _ = paper_source(token)
    chunks = [{"anchor": f"b{index}", "section": "body", "text": f"chunk {index}"}
              for index in range(201)]
    with pytest.raises(ValueError, match="^projection allocation exceeded$"):
        CorpusImports(transactions).import_paper(
            paper=paper, version=version, chunks=chunks, private_path="synthetic-import",
            provenance={"source": "v1-import"})
    with connect("corpus") as conn:
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM corpus.paper WHERE id=%s) AS papers,"
            "(SELECT count(*) FROM corpus.version WHERE id=%s) AS versions,"
            "(SELECT count(*) FROM corpus.projection WHERE version_id=%s) AS chunks",
            (paper["id"], version["id"], version["id"])).fetchone()
    assert counts == {"papers": 0, "versions": 0, "chunks": 0}


# 4. Parity digests are equal across source order -----------------------------------------


def test_parity_digests_are_equal_across_source_order(transactions, created, clock):
    accounts, settings = AccountImports(transactions), SettingsImports(transactions)
    sources = [(uuid4(), account_source(display_name=f"Imported {index}")) for index in range(4)]
    created["accounts"].extend(target for target, _ in sources)
    created["settings"].extend(target for target, _ in sources)
    shuffled = list(sources)
    random.Random(7).shuffle(shuffled)
    for target, source in shuffled:
        accounts.import_account(target, **source)
        settings.import_settings(target, appearance="system", language="ko",
                                 defaults={"display": target.hex[:4]})
    # The source side, computed in the opposite order, matches the owners' reads.
    expected_accounts = parity_digest(
        stored_digest(account_fields(**source)) for _, source in reversed(sources))
    expected_settings = parity_digest(
        stored_digest(settings_fields(account_id=target, appearance="system", language="ko",
                                      defaults={"display": target.hex[:4]}))
        for target, _ in reversed(sources))
    ids = [target for target, _ in sources]
    read_accounts = accounts.parity("account", now=clock(), target_ids=reversed(ids))
    assert read_accounts["digest"] == expected_accounts and read_accounts["count"] == 4
    assert settings.parity(now=clock(), account_ids=ids)["digest"] == expected_settings
    assert accounts.parity("account", now=clock(), target_ids=ids) == read_accounts


def test_the_saved_paper_and_paper_parity_reads_match_their_sources(
        transactions, created, authority, clock):
    token = secrets.token_hex(4)
    _, paper, version = import_paper(transactions, created, token)
    created["saved"].append((authority.account_id, paper["id"]))
    SavedPaperImports(transactions).import_saved_paper(
        authority.account_id, paper_id=paper["id"], version_id=version["id"], saved_at=CREATED)
    corpus = CorpusImports(transactions).parity(now=clock(), version_ids=[version["id"]])
    assert corpus["count"] == 1
    assert corpus["digest"] == CorpusImports(transactions).parity(
        now=clock(), version_ids=[version["id"]])["digest"]
    saved = SavedPaperImports(transactions).parity(now=clock(),
                                                   account_ids=[authority.account_id])
    # Every test removes its saved papers, so the owner holds exactly this one.
    expected = stored_digest(saved_fields(account_id=authority.account_id, paper_id=paper["id"],
                                          version_id=version["id"], saved_at=CREATED))
    assert saved["count"] == 1 and saved["digest"] == parity_digest([expected])


# 5. CorpusContent's refusals and the corpus limit record (U8 plan Steps 69(h)-(i)) ------------


TIME_REFUSED = "refused-by-database-time-limits"


def corpus_files(realm):
    from backend.artifacts import PrivateArtifacts

    return PrivateArtifacts.for_profile(realm, "corpus-files", maximum_bytes=16_777_216)


def listed(files) -> set[str]:
    return {path.name for path in files.root.glob("*.blob")}


def measured_import(transactions, files):
    from backend.modules.corpus.paper_import import PaperImport

    return PaperImport(transactions, files, limits=PRODUCTION_LIMITS, embedder=None,
                       vector_policy=None)


def v1_paper(token: str, *, version: int = 1, title: str = "Synthetic time paper",
             document=None, blocks: int = 3):
    from backend.modules.corpus.paper_import import PaperSource
    from tests.u8_service_operations_integration import v1_flows as vf

    return PaperSource(
        source_key=f"u8-time-{token}:v{version}", version=f"key:u8-time-{token}@v{version}",
        title=title, authors=("A. Synthetic",), source_url="https://example.invalid/u8-time",
        published_on=None,
        document=document if document is not None else vf.document(f"u8-{token}", version,
                                                                   blocks=blocks),
        metadata={})


def corpus_counts(connect, paper: str, version: str) -> dict:
    with connect("corpus") as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM corpus.paper WHERE id=%s) AS papers,"
            "(SELECT count(*) FROM corpus.version WHERE id=%s) AS versions",
            (paper, version)).fetchone()


@pytest.mark.parametrize("how", ["sleep", "deadline"])
def test_a_paper_the_database_time_limits_refuse_is_refused_with_its_reason(
        realm, transactions, connect, created, how):
    """`sleep`: the database's own 3 s statement bound cancels the import
    (`test_a_paper_the_database_time_limits_refuse_is_refused_with_its_reason`); `deadline`:
    the passed transaction deadline is the same refusal
    (`test_a_passed_transaction_deadline_is_the_same_refusal`, addition 1's
    `DeadlineReached`)."""
    import time

    from backend.transactions import DeadlineConnection, DeadlineReached
    from tests.u8_service_operations_integration import v1_flows as vf

    files = corpus_files(realm)
    before = listed(files)
    token = secrets.token_hex(4)
    source = v1_paper(token)
    importer = measured_import(transactions, files)
    created["papers"].append((f"key:u8-time-{token}", source.version))
    try:
        with vf.refusing(source.version, how):
            outcome, measure = importer.import_measured(source, re_embed=False)
        assert (outcome["disposition"], outcome["reasonKey"]) == ("refused", TIME_REFUSED)
        assert measure is None
        assert corpus_counts(connect, f"key:u8-time-{token}", source.version) == {
            "papers": 0, "versions": 0}
        assert listed(files) == before  # its freshly published file erased (addition 2)
        assert importer.import_paper(source, re_embed=False)["disposition"] == "imported"
        assert importer.import_paper(source, re_embed=False)["disposition"] == "unchanged"
    finally:
        for name in sorted(listed(files) - before):
            files.erase(name)
    if how == "deadline":
        with pytest.raises(DeadlineReached, match="aggregate transaction deadline reached"):
            DeadlineConnection(None, time.monotonic() - 1.0).remaining()


def test_other_errors_still_stop_the_import(realm, transactions, connect, created,
                                            monkeypatch):
    from backend.transactions import Busy, UnknownCommit
    from tests.u8_service_operations_integration import v1_flows as vf

    files = corpus_files(realm)
    before = listed(files)
    importer = measured_import(transactions, files)
    try:
        for error in (psycopg.OperationalError("stand-in: connection lost"),
                      Busy("owner connection allocation exhausted")):
            source = v1_paper(secrets.token_hex(4))
            with vf.refusing(source.version, error), pytest.raises(type(error)):
                importer.import_paper(source, re_embed=False)
        # A failing commit after the version's write: its outcome is unknown, so its file
        # is kept for reconciliation.
        token = secrets.token_hex(4)
        source = v1_paper(token)
        created["papers"].append((f"key:u8-time-{token}", source.version))
        armed = {"insert": False}
        commit = psycopg.Connection.commit

        def seen() -> bool:
            armed["insert"] = True
            return False  # call-through: the statement itself runs

        def failing_commit(self):
            if armed["insert"]:
                armed["insert"] = False
                raise psycopg.OperationalError("stand-in: connection lost during commit")
            return commit(self)

        kept = listed(files)  # the two errors above propagated, so their files stay too
        monkeypatch.setattr(psycopg.Connection, "commit", failing_commit)
        with vf.refusing(source.version, "sleep", when=seen), pytest.raises(UnknownCommit):
            importer.import_paper(source, re_embed=False)
        monkeypatch.undo()
        assert len(listed(files) - kept) == 1
    finally:
        for name in sorted(listed(files) - before):
            files.erase(name)


def test_a_refused_new_version_of_a_changed_paper_leaves_no_file(realm, transactions,
                                                                 created):
    files = corpus_files(realm)
    before = listed(files)
    importer = measured_import(transactions, files)
    token = secrets.token_hex(4)
    first = v1_paper(token)
    second = v1_paper(token, version=2, title="Synthetic time paper, retitled")
    created["papers"].extend([(f"key:u8-time-{token}", first.version),
                              (f"key:u8-time-{token}", second.version)])
    try:
        assert importer.import_paper(first, re_embed=False)["disposition"] == "imported"
        after_first = listed(files)
        answer = importer.import_paper(second, re_embed=False)
        assert answer["reasonKey"] == "paper-metadata-changed"
        assert listed(files) == after_first  # addition 2
    finally:
        for name in sorted(listed(files) - before):
            files.erase(name)


def test_a_paper_over_one_limit_is_counted_under_that_limit(realm, transactions, connect,
                                                             created):
    from docsuri_shared.workspace import execution

    from backend.modules.corpus.paper_import import PaperMeasure

    files = corpus_files(realm)
    before = listed(files)
    importer = measured_import(transactions, files)
    token = secrets.token_hex(4)
    paper = f"key:u8-time-{token}"
    created["papers"].append((paper, f"{paper}@v1"))
    created["papers"].append((paper, f"{paper}@v2"))

    def again(source, outcome) -> None:
        assert importer.import_paper(source, re_embed=False) == outcome

    try:
        big = v1_paper(secrets.token_hex(4), blocks=PRODUCTION_LIMITS.max_chunks + 1)
        outcome, measure = importer.import_measured(big, re_embed=False)
        assert (outcome["reasonKey"], measure) == ("exceeds-v2-limit",
                                                   PaperMeasure(refused_by="chunks"))
        assert listed(files) == before
        assert corpus_counts(connect, "x", big.version)["versions"] == 0
        execution.ImportOutcome.model_validate(outcome)
        again(big, outcome)

        source = v1_paper(token)
        outcome, measure = importer.import_measured(source, re_embed=False)
        assert outcome["disposition"] == "imported"
        execution.ImportOutcome.model_validate(outcome)
        with connect("corpus") as conn:
            path = conn.execute("SELECT private_path FROM corpus.version WHERE id=%s",
                                (source.version,)).fetchone()["private_path"]
        size = (files.root / path).stat().st_size
        assert measure == PaperMeasure(chunks=3, source_bytes=size)
        unchanged, measured = importer.import_measured(source, re_embed=False)
        assert unchanged["disposition"] == "unchanged" and measured == measure
        execution.ImportOutcome.model_validate(unchanged)
        again(source, unchanged)

        from tests.u8_service_operations_integration import v1_flows as vf

        refusals = (
            (v1_paper(token, version=2, title="Another title"), "paper-metadata-changed"),
            (v1_paper(token, document=vf.document(f"u8-{token}", 1, blocks=4)),
             "version-content-changed"),
            (v1_paper(secrets.token_hex(4), title=""), "ineligible-in-v2"),
            (v1_paper(secrets.token_hex(4), document={"meta": {"paperId": "x"},
                                                     "sections": "not a tree"}),
             "content-shape-unconvertible"),
        )
        for refused, reason in refusals:
            outcome, measure = importer.import_measured(refused, re_embed=False)
            assert (outcome["disposition"], outcome["reasonKey"], measure) == (
                "refused", reason, None), reason
            execution.ImportOutcome.model_validate(outcome)
            again(refused, outcome)
    finally:
        for name in sorted(listed(files) - before):
            files.erase(name)
