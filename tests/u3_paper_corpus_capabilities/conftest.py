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
from backend.modules.library.u3_dispositions import SavedReferenceDispositions
from backend.modules.library.u3_history import U3HistoryConsumer
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
def authority(identities, connect):
    """Service-level authority for owner A; renewed after any mounted login.

    A mounted browser login revokes earlier sessions; service-layer fixtures
    revalidate their own session row so both transports can coexist in one
    case without weakening the single-session rule for the browser.
    """
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET revoked=false,"
            "expires_at=clock_timestamp()+interval '30 minutes',"
            "authority_revision=%s WHERE id=%s",
            (identities["revision"], identities["session"]),
        )
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
            "fixture-gamma": source_record(
                "fixture-gamma",
                paper_id="paper-gamma",
                paragraphs=[
                    "감마 문서의 첫 문단입니다.",
                    "감마 문서의 두 번째 문단입니다.",
                    "감마 문서의 세 번째 문단입니다.",
                ],
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
    library = U3HistoryConsumer(transactions)
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


@pytest.fixture
def assistance(transactions, realm):
    """PaperAssistance owner services over the real store (shared by layers)."""
    from backend.artifacts import PrivateArtifacts
    from backend.modules.plans.guarded_repository import GuardedUsageRepository
    from backend.modules.summarization.admission import AssistanceAdmission
    from backend.modules.summarization.execution import ExecutionClaims
    from backend.modules.summarization.guarded_repository import (
        GuardedAssistanceRepository,
    )

    files = PrivateArtifacts(realm[0].root / "assistance-files")
    repository = GuardedAssistanceRepository(transactions, files)
    usage = GuardedUsageRepository(transactions)
    return {
        "repository": repository,
        "usage": usage,
        "admission": AssistanceAdmission(repository, usage),
        "claims": ExecutionClaims(repository),
        "files": files,
    }


@pytest.fixture
def accepted_job(
    assistance, maintenance, run_fixture, authority, maintenance_authority,
    fixture_discard,
):
    """One real accepted job through the canonical browser submission path."""
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    from backend.modules.corpus.repository import CorpusRepository
    from backend.modules.summarization.requests import AssistanceRequests
    from backend.modules.summarization.u3_catalog import catalog_for
    from backend.modules.summarization.u3_glossary import virtual_revision

    admission = assistance["admission"]
    corpus = CorpusRepository(maintenance.transactions, files=None)
    service = AssistanceRequests(
        admission,
        corpus,
        lambda source: catalog_for(source, provider_ready=True),
    )

    def create(*, key=None):
        from uuid import uuid4

        assistance["usage"].ensure_entitlement(authority)
        source = corpus.read("paper-alpha:v1")
        catalog = catalog_for(source, provider_ready=True)
        option = catalog.options()["options"][0]
        request = {
            "paper": catalog.paper,
            "contentRevision": catalog.content_revision,
            "contentHash": source["source_hash"],
            "operation": option["operation"],
            "optionId": option["optionId"],
            "optionsRevision": catalog.revision,
            "glossaryRevision": virtual_revision(authority.account_id),
            "processingPolicy": {"policyId": "local-research", "revision": "1"},
        }
        job = service.submit(authority, key or uuid4(), request)
        return job, catalog, source

    return create


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
        conn.execute("DELETE FROM library.history")
        conn.execute("DELETE FROM library.history_boundary")
        conn.execute("DELETE FROM library.saved_paper")
        conn.execute("DELETE FROM library.saved_query")
        for table in reversed(CORPUS_RUN_TABLES):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE corpus.change_sequence SET fact_position=0")
        conn.execute("DELETE FROM corpus.maintenance_actor")
        conn.execute("DELETE FROM discovery.citation_snapshot")
        conn.execute("DELETE FROM discovery.provider_budget")
        conn.execute("DELETE FROM discovery.admission")
        conn.execute("DELETE FROM discovery.owner_admission")
        conn.execute("DELETE FROM discovery.execution")
        conn.execute("DELETE FROM assistance.receipt")
        conn.execute("DELETE FROM assistance.event")
        conn.execute("DELETE FROM assistance.result")
        conn.execute("DELETE FROM assistance.job")
        conn.execute("DELETE FROM assistance.admission")
        conn.execute("DELETE FROM assistance.glossary")
        conn.execute("DELETE FROM usage.reservation")
        conn.execute("DELETE FROM usage.entitlement")
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


PASSWORD = "U3Fixture!28-A"
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}


def _await_admission(client, *, seconds: float = 20.0):
    """Bounded wait for the first capacity observation; routes fail closed."""
    import time as _time

    deadline = _time.monotonic() + seconds
    while True:
        probe = client.get("/health/ready")
        if probe.status_code == 200:
            return
        if _time.monotonic() >= deadline:
            raise AssertionError(f"U3 host never admitted requests: {probe.text}")
        _time.sleep(0.05)


@pytest.fixture
def mounted(realm):
    """The real mounted U3 host over the actual owner stores (integration layer)."""
    from fastapi.testclient import TestClient

    from backend.u3_host import assemble_u3

    app = assemble_u3(realm[0])
    with TestClient(app, base_url="https://127.0.0.1:18059") as client:
        _await_admission(client)
        yield client


@pytest.fixture
def anonymous(mounted):
    """Guest transport context bound to the anonymous entry flow CSRF."""
    bootstrap = mounted.get("/api/v2/session")
    mounted.headers.update(
        {
            "Origin": "https://127.0.0.1:18059",
            "X-CSRF-Token": bootstrap.json()["csrfToken"],
        }
    )
    return mounted


@pytest.fixture
def browser(mounted, identities, connect, maintenance_authority):
    """Signed-in owner A over the real cookie/CSRF transport."""
    from uuid import uuid4

    entry = mounted.app.state.entry
    encoded = entry._hash_password(PASSWORD)
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.entry_budget")
        conn.execute(
            "UPDATE accounts.account SET password_hash=%s,email=%s,verified=true,"
            "active=true WHERE id=%s",
            (encoded, "u3-a@fixture.example.com", identities["a"]),
        )
    origin = "https://127.0.0.1:18059"
    bootstrap = mounted.get("/api/v2/session")
    assert bootstrap.status_code == 200, bootstrap.text
    mounted.headers.update(
        {"Origin": origin, "X-CSRF-Token": bootstrap.json()["csrfToken"]}
    )
    response = mounted.post(
        "/api/v2/c02/access-login",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "email": "u3-a@fixture.example.com",
            "password": PASSWORD,
            "policyRef": ENTRY_POLICY,
        },
    )
    assert response.status_code == 200, response.text
    mounted.headers["X-CSRF-Token"] = mounted.get("/api/v2/session").json()["csrfToken"]
    yield mounted
    mounted.cookies.clear()


