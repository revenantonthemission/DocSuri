"""Owned U3 PostgreSQL fixtures. Recovery tests never reseed the environment."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import stat
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.local_profile import LocalProfile
from backend.modules.corpus.maintenance import CorpusMaintenance
from backend.modules.discovery.citations import CitationExplorer, FixtureCitationProvider
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.u3_search import U3Search
from backend.modules.library.repository.guarded import GuardedLibraryRepository
from backend.modules.library.u3_dispositions import SavedReferenceDispositions
from backend.transactions import Authority, OwnerTransactions
from fixtures import MemorySources, request_body, source_record


@pytest.fixture(scope="session")
def realm():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U3_ENVIRONMENT_FILE"]))
    assert profile.database_name == "docsuri_u3" and profile.realm == "corpus-maintenance"
    credentials = json.loads((profile.root / "owner-credentials.json").read_text())
    assert credentials["runId"] == profile.run_id
    return profile, credentials


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment(realm):
    descriptor = os.open(
        realm[0].root / "fixture-run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        metadata = os.fstat(descriptor)
        assert stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid()
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


@pytest.fixture
def connect(realm):
    profile, credentials = realm
    opened = []

    def connection(owner, *, autocommit=False):
        conn = psycopg.connect(
            host="127.0.0.1",
            port=profile.database_port,
            dbname=profile.database_name,
            user=f"docsuri_{owner}",
            password=credentials["roles"][owner],
            connect_timeout=3,
            row_factory=dict_row,
            autocommit=autocommit,
        )
        assert (
            conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()[
                "run_id"
            ]
            == profile.run_id
        )
        if not autocommit:
            conn.commit()
        opened.append(conn)
        return conn

    yield connection
    for conn in opened:
        conn.close()


@pytest.fixture
def admin(realm):
    """Superuser-side fixture provisioning; never used for behavior assertions."""
    profile = realm[0]
    credentials = json.loads((profile.root / "migration-credentials.json").read_text())
    opened = []
    connection = psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=credentials["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    )
    opened.append(connection)

    def provision(statement: str, params=()):
        with connection.transaction():
            connection.execute(statement, params)

    yield provision
    for conn in opened:
        conn.close()


@pytest.fixture
def identities(connect, realm):
    run = realm[0].run_id
    a, b, session, revision = [
        uuid5(NAMESPACE_URL, run + item)
        for item in ("owner-a", "owner-b", "session-a", "authority-a")
    ]
    with connect("accounts") as conn:
        for account, label in ((a, "a"), (b, "b")):
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
                "authority_revision,display_name) "
                "VALUES(%s,%s,'database-fixture-not-a-login-hash',true,true,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET verified=true,active=true,"
                "authority_revision=excluded.authority_revision",
                (account, f"u3-{label}@fixture.invalid", revision, label),
            )
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) "
                "VALUES(%s,'local-research',true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (account,),
            )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) "
            "VALUES(%s,%s,'u3-db-session','u3-db-csrf',%s,clock_timestamp()+interval '30 minutes') "
            "ON CONFLICT(id) DO UPDATE SET revoked=false,expires_at=excluded.expires_at,"
            "authority_revision=excluded.authority_revision",
            (session, a, revision),
        )
    return {"a": a, "b": b, "session": session, "revision": revision}


@pytest.fixture
def authority(identities):
    return Authority(identities["a"], identities["session"])


@pytest.fixture
def transactions(realm):
    transactions = OwnerTransactions(realm[0])
    yield transactions
    transactions.close()


@pytest.fixture
def maintenance_authority(admin, identities):
    """Explicit corpus-maintenance authority for fixture owner A only."""
    admin(
        "INSERT INTO corpus.maintenance_actor(account_id) VALUES(%s) "
        "ON CONFLICT(account_id) DO NOTHING",
        (identities["a"],),
    )
    return identities["a"]


@pytest.fixture
def sources():
    return MemorySources(
        {
            "fixture-alpha": source_record("fixture-alpha", paper_id="paper-alpha"),
            "fixture-beta": source_record(
                "fixture-beta", paper_id="paper-beta", version_label="v2"
            ),
        }
    )


@pytest.fixture
def maintenance(transactions, sources, realm):
    """Real CorpusMaintenance owner service over the owned realm."""
    from backend.artifacts import PrivateArtifacts

    files = PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152)
    return CorpusMaintenance(transactions, files, sources)


@pytest.fixture
def run_fixture(maintenance, authority, maintenance_authority, realm):
    """Accept + execute + verify one corpus run for the named fixture sources."""

    def run(scope: list[str], *, operation: str = "ingest"):
        from uuid import uuid4

        body = request_body(operation, scope)
        accepted = maintenance.accept(authority, uuid4(), body)
        maintenance.execute(accepted["runId"])
        return maintenance.read_run(authority, accepted["runId"])

    return run


@pytest.fixture
def search_service(transactions, realm, identities):
    """U3 search over the real discovery owner with the owned cursor key."""
    cursor_key = bytes.fromhex(
        json.loads((realm[0].root / "corpus-keys.json").read_text())["cursor"]
    )
    repository = GuardedDiscoveryRepository(transactions)
    library = GuardedLibraryRepository(transactions)
    return U3Search(transactions, repository, library, cursor_key=cursor_key)


@pytest.fixture
def citations(transactions):
    def build(records: dict, *, freshness: str = "fresh", fail: bool = False):
        return CitationExplorer(
            transactions, FixtureCitationProvider(records, freshness=freshness, fail=fail)
        )

    return build


@pytest.fixture
def dispositions(transactions):
    return SavedReferenceDispositions(transactions)


DISCARDED_OWNER_TABLES = (
    "accounts",
    "assistance",
    "corpus",
    "discovery",
    "library",
    "operations",
    "personalization",
    "usage",
)

CORPUS_RUN_TABLES = (
    "corpus.run_effect",
    "corpus.run",
    "corpus.change_fact",
    "corpus.projection_batch",
    "corpus.generation",
    "corpus.quarantine",
    "corpus.asset",
)


@pytest.fixture
def fixture_discard(realm):
    """Admin-side discard of exactly this case's run-scoped fixture rows.

    Behavior verification always runs through the runtime owner roles; this
    teardown only removes synthetic rows a case created so repeated runs cannot
    exceed the finite experiment footprint. A restart/interruption test keeps
    its rows: it must not be paired with this fixture.
    """
    registered = False

    def register() -> None:
        nonlocal registered
        registered = True

    yield register
    if not registered:
        return
    profile = realm[0]
    credentials = json.loads((profile.root / "migration-credentials.json").read_text())
    conn = psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=credentials["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    )
    try:
        conn.execute("SET session_replication_role = replica")
        conn.execute("DELETE FROM library.disposition_cursor")
        conn.execute("INSERT INTO library.disposition_cursor VALUES (true, 0)")
        conn.execute("UPDATE library.saved_paper SET disposition='active',"
                     "disposition_revision=NULL,disposition_position=NULL")
        for table in reversed(CORPUS_RUN_TABLES):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE corpus.change_sequence SET fact_position=0")
        conn.execute("DELETE FROM corpus.maintenance_actor")
        conn.execute("DELETE FROM discovery.citation_snapshot")
        conn.execute("DELETE FROM discovery.provider_budget")
        conn.execute("DELETE FROM discovery.execution")
        conn.execute("DELETE FROM assistance.event")
        conn.execute("DELETE FROM assistance.result")
        conn.execute("DELETE FROM assistance.job")
        conn.execute("DELETE FROM assistance.admission")
        conn.execute("DELETE FROM assistance.glossary")
        conn.execute("DELETE FROM corpus.projection")
        conn.execute("DELETE FROM corpus.version")
        conn.execute("DELETE FROM corpus.paper")
        conn.execute("DELETE FROM accounts.session")
        conn.execute("DELETE FROM accounts.consent")
        conn.execute("DELETE FROM accounts.account")
        conn.execute("SET session_replication_role = origin")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def bounded_case():
    """Hard per-case deadline includes fixture setup and teardown, not diagnostics."""

    def expired(signum, frame):
        raise TimeoutError("U3 case exceeded the finite 60 second execution limit")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
