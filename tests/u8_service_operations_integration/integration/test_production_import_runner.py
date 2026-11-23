"""The migration gate and the import's port on the production stand-in (U8 plan Step
52(g); L1-13).

The module's fixture is a production stand-in (`host_flows.production_stand_in`) and, in
the realm's instance, a synthetic v1 import database named by `PRODUCTION_DATABASES`'
import pattern, which holds v1's schema and accounts, so an import reaches an owner run.
Its `PUBLIC` CONNECT is revoked; CONNECT, and SELECT on its tables, go to the realm's
operator stand-in `docsuri_operator` alone. Both are dropped afterwards.

Nothing here passes `connect=` or records transactions (L1-35): `production_import`
opens the import database at the stand-in's own port (Step 51(e)) and runs its owners
under the migration tool's gate of 4 (Step 51(c)); the production environment tool's
owner work runs under the maintenance gate of 2.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import types
from uuid import uuid4

import pytest
from psycopg import sql

from backend.local_profile import verifier_key_path
from backend.modules.discovery.u8_search import StandinEmbeddings
from backend.transactions import Busy, OwnerTransactions
from docsuri_ops import production_tool
from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES
from docsuri_ops.production_wiring import production_import
from tests.u8_service_operations_integration import host_flows, v1_flows
from tests.u8_service_operations_integration import recovery_flows as rf

NOW = dt.datetime(2026, 11, 1, 10, 0, tzinfo=dt.UTC)
OPERATOR = "docsuri_operator"
GIB = 1024**3
# Free space well above every floor, for the tests that do not test the disk guard.
ROOM = 100 * GIB


@contextlib.contextmanager
def granted_v1(realm):
    """A synthetic v1 loaded into an import database of its own, and only then granted:
    `create` drops and recreates the database as the realm's superuser, so a grant made
    before it would be lost. No `PUBLIC` CONNECT; CONNECT, and SELECT on its tables, for
    the operator stand-in alone."""
    v1 = v1_flows.SyntheticV1(realm, name=PRODUCTION_DATABASES.new("import")).create()
    try:
        name = sql.Identifier(v1.name)
        with rf.admin(realm) as conn:
            conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(name))
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                name, sql.Identifier(OPERATOR)))
        with rf.admin(realm, v1.name) as conn:
            conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(OPERATOR)))
        yield v1
    finally:
        v1.drop()


@pytest.fixture(scope="module")
def env(realm):
    with host_flows.production_stand_in(realm) as standin, granted_v1(realm) as v1:
        yield types.SimpleNamespace(standin=standin, v1=v1)


def v1_payload(v1) -> tuple[bytes, dict]:
    """The synthetic v1's index documents, document models and listing, packed as the
    snapshot packs them (Step 68(c)): every key under `doc-model/` a member, and the
    bucket's listing as the reserved member."""
    import json

    from backend.modules.operations.migration.v1_source import LISTING_MEMBER, encode_listing
    from docsuri_ops.backup_agent.archives import pack

    index = pack({"documents.jsonl": b"".join(
        json.dumps(item, sort_keys=True).encode() + b"\n" for item in v1.index_documents())})
    stored = {**v1.objects(), **v1.bucket_extras()}
    members = {key: body for key, body in stored.items() if key.startswith("doc-model/")}
    objects = pack({**members, LISTING_MEMBER: encode_listing(v1.listing())})
    return index + objects, {"index": len(index), "objects": len(objects)}


def import_header(realm, standin, v1, sizes: dict, **extra) -> dict:
    return {"login": {"password": rf.credentials(realm, "standin-credentials.json")["roles"][
        "operator"]}, "runId": str(uuid4()), "importDatabase": v1.name,
        "targetDatabase": standin.database, "decisions": [], "final": False, "required": [],
        "archives": sizes, **extra}


def proposed_records() -> list[dict]:
    from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS

    return [{"kind": kind, "reasonKey": reason, "decision": decision,
             **({"mappingRule": MAPPING_RULES[(kind, reason)]} if decision == "map" else {})}
            for (kind, reason), decision in PROPOSALS.items()]


def hold(gate) -> int:
    taken = 0
    while gate.acquire(blocking=False):
        taken += 1
    return taken


def release(gate, taken: int) -> None:
    for _ in range(taken):
        gate.release()


def accounts(standin) -> int:
    with rf.admin(standin.realm, standin.database) as conn:
        return conn.execute("SELECT count(*) FROM accounts.account").fetchone()[0]


def test_the_migration_import_runs_under_the_migration_gate(realm, env):
    standin = env.standin
    profile = standin.profile
    migration = OwnerTransactions(profile, process="migration")
    maintenance = OwnerTransactions(profile, process="maintenance")
    try:
        taken = hold(migration._gate)
        try:
            assert taken == 4
            assert not migration._gate.acquire(blocking=False)
            before = accounts(standin)
            header = {
                "login": {"password": rf.credentials(realm, "standin-credentials.json")[
                    "roles"]["operator"]},
                "runId": str(uuid4()), "importDatabase": env.v1.name,
                "targetDatabase": standin.database, "decisions": [], "final": False,
                "required": [], "archives": {"index": 0, "objects": 0}, "toWrite": 0,
            }
            # Nothing is passed as `connect=`: the import database is opened at the
            # stand-in's port, and the first owner work, the first boundary's reading of
            # what the target holds (Step 68(b)), meets the held gate.
            with pytest.raises(Busy, match="process connection allocation exhausted"):
                production_import("import", header, b"", profile=profile,
                                  embedder=StandinEmbeddings(), clock=lambda: NOW,
                                  free_bytes=lambda: ROOM)
            assert accounts(standin) == before
        finally:
            release(migration._gate, taken)

        taken = hold(maintenance._gate)
        try:
            assert taken == 2
            context = types.SimpleNamespace(profile=lambda: profile, clock=lambda: NOW)
            key = verifier_key_path(profile)
            assert not (key.exists() or key.is_symlink())
            with pytest.raises(Busy, match="process connection allocation exhausted"):
                production_tool.replace_verifier_key(context, {
                    "expectedKeyRevision": "absent", "reasonKey": "verifier-key-rotation"})
            assert not (key.exists() or key.is_symlink())
            assert not list(key.parent.glob(".verifier-key-*"))
            corpus, close = production_tool._production_corpus(profile)
            try:
                assert corpus is not None
                assert close.__self__._process == "maintenance"
                assert close.__self__._gate is maintenance._gate
            finally:
                close()
        finally:
            release(maintenance._gate, taken)
    finally:
        migration.close()
        maintenance.close()


# Step 55(e): the import program's own embedder sends sixteen chunks a request.

PAPER = "2101.09040"


@contextlib.contextmanager
def import_database(realm):
    """This test's own import database in the realm's instance: v1's schema from
    `v1_flows.v1_migrations()` and one v1 paper version, granted as the module fixture's
    is (no `PUBLIC` CONNECT; CONNECT and SELECT for the operator stand-in alone)."""
    name = PRODUCTION_DATABASES.new("import")
    ident = sql.Identifier(name)
    rf.drop_database(realm, name)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(ident))
    try:
        with rf.admin(realm, name) as conn:
            for path in v1_flows.v1_migrations():
                conn.execute(path.read_text(), prepare=False)
            conn.execute(
                "INSERT INTO paper_version_state(paper_id,version,doc_model_ref,status) "
                "VALUES(%s,1,%s,'ACTIVE')",
                (PAPER, f"s3://docsuri-synthetic/doc-model/{PAPER}/v1.json"))
            conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(OPERATOR)))
        with rf.admin(realm) as conn:
            conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(ident))
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                ident, sql.Identifier(OPERATOR)))
        yield name
    finally:
        rf.drop_database(realm, name)


def snapshot_payload() -> tuple[bytes, dict]:
    """The snapshot's two archives: one index document holding a v1 vector (so the
    embedding's provenance is unproven) and the paper's document model of 40 paragraph
    blocks, one chunk each."""
    import json

    from docsuri_ops.backup_agent.archives import pack

    document = {"chunkId": f"{PAPER}:1:0", "paperId": PAPER, "version": 1,
                "title": f"Synthetic paper {PAPER}", "authors": ["A. Synthetic"],
                "arxivId": PAPER, "vector": [0.1] * 4,
                "arxivUrl": f"https://arxiv.org/abs/{PAPER}v1"}
    index = pack({"documents.jsonl": (json.dumps(document) + "\n").encode()})
    objects = pack({f"doc-model/{PAPER}/v1.json": json.dumps(
        v1_flows.document(PAPER, 1, blocks=40)).encode()})
    return index + objects, {"index": len(index), "objects": len(objects)}


def test_the_import_programs_embedder_sends_sixteen_chunks_a_request(realm, monkeypatch):
    from backend.modules.summarization import model_runtime

    model = host_flows.ModelStandIn()
    # For this test only: the runtime's one network builder answers in process
    # (`httpx.MockTransport`), so no socket opens; `SharedModelRuntime` builds its
    # transport at call time.
    monkeypatch.setattr(model_runtime, "network_transport", model.factory)
    payload, sizes = snapshot_payload()
    with host_flows.production_stand_in(realm) as standin, import_database(realm) as name:
        header = {
            "login": {"password": rf.credentials(realm, "standin-credentials.json")[
                "roles"]["operator"]},
            "runId": str(uuid4()), "importDatabase": name,
            "targetDatabase": standin.database, "final": False, "required": [],
            "decisions": [{"kind": "paper-embedding",
                           "reasonKey": "embedding-provenance-unproven",
                           "decision": "map", "mappingRule": "re-embed-pinned-model"}],
            "archives": sizes, "toWrite": 0,
        }
        # No embedder is given: the program builds `LocalEmbeddings(SharedModelRuntime(),
        # keep_alive=-1, query_seconds=2.0, batch=16)` itself.
        result = production_import("import", header, payload, profile=standin.profile,
                                   clock=lambda: NOW, free_bytes=lambda: ROOM)
        with rf.admin(realm, standin.database) as conn:
            chunks = conn.execute(
                "SELECT count(*) AS n, count(embedding) AS embedded FROM corpus.projection "
                "WHERE version_id=%s", (f"arxiv:{PAPER}@v1",)).fetchone()
    assert result["changed"] >= 1
    assert tuple(chunks) == (40, 40)
    embeds = model.calls("/api/embed")
    assert [len(item["input"]) for item in embeds] == [16, 16, 8]
    assert [item["keep_alive"] for item in embeds] == [-1, -1, -1]
    # The pinned digests are read from `/api/tags` before the model requests.
    assert any(request.url.path == "/api/tags" for request in model.requests)


# --- the import program's boundaries (U8 plan Steps 68(b), 69(b); S3) --------------------------


def imported_versions(standin) -> int:
    with rf.admin(standin.realm, standin.database) as conn:
        return conn.execute("SELECT count(*) FROM corpus.version WHERE id LIKE "
                            "'arxiv:2101.%'").fetchone()[0]


def test_the_import_program_stops_at_a_low_disk_boundary(realm, env, monkeypatch):
    standin, v1 = env.standin, env.v1
    payload, sizes = v1_payload(v1)
    closed: list[int] = []
    original_close = OwnerTransactions.close

    def counted_close(self):
        closed.append(1)
        return original_close(self)

    monkeypatch.setattr(OwnerTransactions, "close", counted_close)
    to_write = 1 * GIB

    def run(reader):
        # Workflow 10's proposals as your decisions, so the accounts phase imports.
        header = import_header(realm, standin, v1, sizes, toWrite=to_write,
                               decisions=proposed_records())
        return production_import("import", header, payload, profile=standin.profile,
                                 embedder=StandinEmbeddings(), clock=lambda: NOW,
                                 **({"free_bytes": reader} if reader else {}))

    # The room rule at a phase start, with `held` read as the program reads it: the
    # program's own `held` (both logins, each measuring its own database) is read once at
    # each phase boundary, before the check reads the free space, and that same figure is
    # the one the check then uses. A test that read the sizes earlier would race any growth
    # of either database (autovacuum forks, analyze) in between.
    from docsuri_ops.migration import disk_guard

    measured: list[int] = []
    original_boundary = disk_guard.DiskGuard.boundary

    def measuring_boundary(self, *, to_write, held):
        check = original_boundary(self, to_write=to_write, held=lambda: measured[-1])

        def measured_check(kind: str) -> None:
            if kind == "phase":
                measured.append(int(held()))
            check(kind)

        return measured_check

    monkeypatch.setattr(disk_guard.DiskGuard, "boundary", measuring_boundary)

    def at_boundary() -> int:
        return 20 * GIB + max(0, to_write - measured[-1])

    calls: list[int] = []
    before = accounts(standin)

    def low():
        calls.append(1)
        return at_boundary()

    def both_sizes() -> int:
        # Step 68(b)'s `held`: the import database and the target, each measured whole.
        with rf.admin(realm, standin.database) as conn:
            return conn.execute("SELECT pg_database_size(%s) + pg_database_size(%s)",
                                (v1.name, standin.database)).fetchone()[0]

    held_before = both_sizes()
    assert run(low) == {"interrupted": "internal-disk-low"}
    held_after = both_sizes()
    assert len(calls) == 1 and len(measured) == 1 and closed == [1]
    assert accounts(standin) == before
    # The figure the room rule subtracts is both databases' sizes: nothing writes between
    # the two readings, so the databases can only grow, and the program's own reading lies
    # between them. A `held` that leaves either database out, or answers 0, fails here.
    assert held_before <= measured[0] <= held_after

    # One byte above the boundary passes the first phase start: the accounts phase runs,
    # and the next phase start meets the critical floor, before any paper.
    calls.clear()
    measured.clear()

    def above():
        calls.append(1)
        return at_boundary() + 1 if len(calls) == 1 else 10 * GIB - 1

    assert run(above) == {"interrupted": "internal-disk-critical"}
    assert len(calls) == 2 and closed == [1, 1]
    assert accounts(standin) > before and imported_versions(standin) == 0

    # Room until the papers phase has begun, then below the 10 GiB floor at the first paper.
    calls.clear()

    def critical():
        calls.append(1)
        return ROOM if len(calls) <= 5 else 10 * GIB - 1

    assert run(critical) == {"interrupted": "internal-disk-critical"}
    # One reading per phase start (accounts, usage, links, preferences, papers) and one at
    # the first paper.
    assert len(calls) == 6 and closed == [1, 1, 1]
    assert accounts(standin) > before and imported_versions(standin) == 0

    # No reader injected: the default reads f_bavail × f_frsize (8,192,000,000 bytes, below
    # the floor), not f_bfree × f_frsize (12,288,000,000 bytes, above it).
    import os

    monkeypatch.setattr(os, "statvfs", lambda path: types.SimpleNamespace(
        f_frsize=4096, f_bavail=2_000_000, f_bfree=3_000_000, f_blocks=4_000_000))
    assert run(None) == {"interrupted": "internal-disk-critical"}
    assert closed == [1, 1, 1, 1]


# --- a paper the database's time limits refuse (U8 plan Steps 68(h)-(i), 69(h)-(i); L1-75, L1-79)


def run_main(monkeypatch, word: str, header: dict, payload: bytes, runner) -> tuple[int, dict]:
    """`phases.main` as the import program runs it: no caller-set interpreter variable,
    the header line and the archives on standard input, one JSON line out."""
    import io
    import json
    import os
    import sys

    from backend.modules.operations.migration import phases

    for name in list(os.environ):
        if name.startswith(("PYTHON", "DYLD_", "LD_")):
            monkeypatch.delenv(name)
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(
        json.dumps(header).encode() + b"\n" + payload)))
    monkeypatch.setattr(sys, "stdout", out)
    status = phases.main([word], run=runner)
    lines = out.getvalue().splitlines()
    assert len(lines) == 1, lines
    return status, json.loads(lines[0])


def test_the_import_program_answers_a_time_refused_paper_in_its_json_line(realm, monkeypatch):
    import functools

    import psycopg

    from backend.modules.corpus.limits import PRODUCTION_LIMITS

    with host_flows.production_stand_in(realm) as standin, granted_v1(realm) as v1:
        payload, sizes = v1_payload(v1)
        runner = functools.partial(production_import, profile=standin.profile,
                                   embedder=StandinEmbeddings(), clock=lambda: NOW,
                                   free_bytes=lambda: ROOM)
        header = import_header(realm, standin, v1, sizes, toWrite=0)
        with v1_flows.refusing("arxiv:2101.00006@v1", "sleep"):
            status, answer = run_main(monkeypatch, "import", header, payload, runner)
        assert status == 0 and answer["ok"] is True
        assert ["paper", "2101.00006:v1", "refused-by-database-time-limits"] in answer[
            "misfits"]
        paper = next(kind for kind in answer["report"]["kinds"] if kind["kind"] == "paper")
        assert {"kind": "paper", "sourceId": "2101.00006:v1",
                "reasonKey": "refused-by-database-time-limits",
                "newInFinal": False} in paper["misfits"]
        # Its corpus limit record (L1-79): the refused paper counts under no limit.
        with rf.admin(realm, standin.database) as conn:
            paths = [row[0] for row in conn.execute(
                "SELECT private_path FROM corpus.version WHERE id LIKE 'arxiv:2101.%'")]
        folder = standin.profile.root / "corpus-files"
        largest = max((folder / name).stat().st_size for name in paths)
        assert paper["limits"] == {
            "profile": "production",
            "chunks": {"limit": PRODUCTION_LIMITS.max_chunks, "checked": True, "largest": 3,
                       "refused": 1},
            "sourceBytes": {"limit": 16_777_216, "checked": True, "largest": largest,
                            "refused": 0},
            "elements": {"limit": 250_000, "checked": False, "largest": None, "refused": 0},
            "depth": {"limit": 256, "checked": False, "largest": None, "refused": 0},
        }

        # The spy removed, so the paper now fits: the idempotency word skips the paper
        # `skipPapers` names (addition 3); one that ignored it would import the paper and
        # answer `changed` 1.
        again = import_header(realm, standin, v1, sizes, skipPapers=["2101.00006:v1"])
        status, answer = run_main(monkeypatch, "idempotency", again, payload, runner)
        assert (status, answer) == (0, {"ok": True, "changed": 0})

        # A stopping error reaches the operator tool as a named reason (addition 5).
        for error, reason in ((Busy("owner connection allocation exhausted"), "busy"),
                              (psycopg.OperationalError("stand-in"), "operational-error")):
            header = import_header(realm, standin, v1, sizes, toWrite=0)
            with v1_flows.refusing("arxiv:2101.00006@v1", error):
                status, answer = run_main(monkeypatch, "import", header, payload, runner)
            assert (status, answer) == (1, {"ok": False, "reason": reason})


# --- the import runner on the real owners (U8 plan Step 90(g); L1-35) ---------------------------


def dataset_misfits(v1) -> list[list[str]]:
    """The `v1_flows` dataset's misfits under Workflow 10's proposals, read off the
    dataset's own table (`v1_flows`' docstring): each `[kind, sourceId, reason]`."""
    from backend.modules.operations.migration.identities import link_source_id
    from backend.modules.operations.migration.v1_source import upload_source_id

    ids = v1.ids
    owner = ids["active"]
    with rf.admin(v1.realm, v1.name) as conn:
        glossary = [str(row[0]) for row in conn.execute(
            "SELECT id::text FROM user_glossary ORDER BY 1")]
    upload = next(key for key in v1.bucket_extras() if key.startswith("uploads/"))
    found = [
        # accounts: the five imported each carry the mapped display name, and `locked` its
        # mapped reset; the rest are refused or conflicting.
        *[["account", ids[name], "required-field-without-source"]
          for name in ("active", "orcid", "provider", "locked", "legacy")],
        ["account", ids["locked"], "locked-in-v1"],
        ["account", ids["orcid-only"], "no-email"],
        ["account", ids["pending"], "unverified-in-v1"],
        ["account", ids["deactivated"], "closed-in-v1"],
        ["account", ids["deleting"], "closed-in-v1"],
        ["account", ids["case-a"], "email-case-conflict"],
        ["account", ids["case-b"], "email-case-conflict"],
        # identity links
        ["identity-link", link_source_id("google", "google-provider-2"),
         "duplicate-provider-link"],
        ["identity-link", link_source_id("google", "google-active-pending"),
         "unconfirmed-link"],
        ["identity-link", link_source_id("google", "google-pending-account"),
         "dependency-not-migrated"],
        ["identity-link", link_source_id("orcid", "0000-0002-0000-0002"),
         "dependency-not-migrated"],
        # preferences
        ["preferences", f"{owner}:interest-weights", "no-v2-home"],
        ["preferences", ids["pending"], "dependency-not-migrated"],
        # papers, their figures, content and embeddings
        ["paper-figure", "2101.00001:v1", "no-v2-home"],
        ["paper-embedding", "2101.00001:v1", "embedding-provenance-unproven"],
        ["paper-embedding", "2101.00001:v2", "embedding-provenance-unproven"],
        ["paper", "2101.00002:v1", "exceeds-v2-limit"],
        ["paper", "2101.00003:v1", "ineligible-in-v2"],
        ["paper-content", "2101.00004:v1", "content-shape-unconvertible"],
        ["paper-figure", "2101.00006:v1", "no-v2-home"],
        # saved papers
        ["saved-paper", f"saved-2-{owner}", "duplicate-by-version"],
        ["saved-paper", f"saved-3-{owner}", "dependency-not-migrated"],
        ["saved-paper", f"saved-4-{owner}", "dependency-not-migrated"],
        # what Q13 did not name
        ["followed-topic", f"topic-{owner}", "not-in-scope"],
        ["digest-settings", owner, "not-in-scope"],
        *[["glossary", source, "not-in-scope"] for source in glossary],
        ["saved-search", f"search-{owner}", "not-in-scope"],
        ["search-history", f"history-{owner}", "not-in-scope"],
        ["behavior-event", f"event-{owner}", "not-in-scope"],
        ["private-upload", upload_source_id(upload), "not-in-scope"],
    ]
    return sorted(found)


def migration_backends(standin) -> int:
    """The backends of the migration process's owner logins on the stand-in's target."""
    with rf.admin(standin.realm) as conn:
        return conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND application_name "
            "LIKE %s AND usename LIKE 'docsuri\\_%%'",
            (standin.database, f"docsuri-{standin.profile.realm}-migration-%")).fetchone()[0]


def no_migration_backends(standin) -> bool:
    """Polled for up to 5 s: a closed client's backend leaves `pg_stat_activity` only once
    the server has seen the disconnect."""
    import time

    deadline = time.monotonic() + 5.0
    while migration_backends(standin):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


def test_the_import_runner_composes_the_real_owners_on_the_production_stand_in(
        realm, env, monkeypatch):
    from backend.modules.operations.migration import v1_source
    from backend.modules.operations.migration.v1_source import LISTING_MEMBER
    from backend.modules.summarization import model_runtime

    standin, v1 = env.standin, env.v1
    model = host_flows.ModelStandIn()
    # The shared model runtime answers in process, as `production_composition` patches it.
    monkeypatch.setattr(model_runtime, "network_transport", model.factory)
    handed: list[dict] = []
    real_source = v1_source.V1Source

    class SeenSource(real_source):
        """A delegating spy: records what `production_import` hands the real reader."""

        def __init__(self, conn, **parts):
            handed.append(parts)
            super().__init__(conn, **parts)

    monkeypatch.setattr(v1_source, "V1Source", SeenSource)
    payload, sizes = v1_payload(v1)
    expected = dataset_misfits(v1)
    met = {(kind, reason) for kind, _, reason in expected}
    required = sorted([list(pair) for pair in met - {("account", "email-case-conflict")}])
    header = import_header(realm, standin, v1, sizes, toWrite=0, final=True,
                           required=required, decisions=proposed_records())
    # No `connect=` and no embedder: the import database is opened through the operator
    # stand-in's login at the stand-in's port, and the program builds its own embedder.
    answer = production_import("import", header, payload, profile=standin.profile,
                               clock=lambda: NOW, free_bytes=lambda: ROOM)
    assert no_migration_backends(standin)
    # `_archives` took the reserved member out of the objects and handed it on as the
    # listing, through `split_listing`.
    (parts,) = handed
    assert parts["listing"] == v1.listing()
    assert LISTING_MEMBER not in parts["objects"]
    assert set(parts["objects"]) == {key for key in {**v1.objects(), **v1.bucket_extras()}
                                     if key.startswith("doc-model/")}
    assert sorted(answer["misfits"]) == expected
    uploads = [item for item in answer["misfits"] if item[0] == "private-upload"]
    assert len(uploads) == 1 and uploads[0][2] == "not-in-scope"
    assert not [item for item in answer["misfits"] if LISTING_MEMBER in item[1]]
    assert ["paper-figure", "2101.00006:v1", "no-v2-home"] in answer["misfits"]
    assert not [item for item in answer["misfits"] if item[1].startswith("saved-6-")]
    assert answer["newInFinal"] == [["account", "email-case-conflict"]]
    assert answer["report"]["runId"] == header["runId"]
    assert answer["report"]["newInFinal"] == ["account:email-case-conflict"]
    # The model requests went to the stand-in, in batches of at most sixteen.
    assert model.calls("/api/embed")
    assert all(len(item["input"]) <= 16 for item in model.calls("/api/embed"))

    again = import_header(realm, standin, v1, sizes, decisions=proposed_records())
    assert production_import("idempotency", again, payload, profile=standin.profile,
                             clock=lambda: NOW) == {"changed": 0}
    assert no_migration_backends(standin)


# --- the import program's circuit breaker (U8 plan Step 162(e); L4-11) --------------------------


def store_models_observation(standin, outcome: str, reason: str | None, *, age: int) -> None:
    """One stored observation of provider.models in the profile's own database, as its
    producer records it, `age` seconds before `NOW`: the clock the import is handed, and
    so the clock its state reader derives staleness with."""
    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.u8_registry import CAPABILITY_BY_ID

    producer = CAPABILITY_BY_ID["provider.models"].producer
    observations = Observations(ObservationStore(standin.transactions))
    row = observations.make("provider.models", producer, outcome, reason=reason,
                            observed_at=NOW - dt.timedelta(seconds=age))
    assert observations.record(producer, [row])["written"] == 1


@pytest.mark.parametrize(("stored", "held"), [
    (("unavailable", "runtime-unreachable", 60), True),
    (("available", None, 60), False),
    (None, False),                                         # nothing observed: unknown
    (("unavailable", "runtime-unreachable", 901), False),  # older than 900 s: stale
])
def test_while_provider_models_is_observed_unavailable_the_import_stops_and_embeds_nothing(
        realm, monkeypatch, stored, held):
    """Reliability-design § 10 (lines 133-137), L4-11: the import program gives its
    runtime a reader of provider.models' stored state. While the newest observation is
    `unavailable` the run stops as `provider-held` and nothing reaches the runtime; with
    `available`, no observation, or one older than 900 s, it embeds as built."""
    import functools

    from backend.modules.summarization import model_runtime

    model = host_flows.ModelStandIn()
    # For this test only: the runtime's one network builder answers in process.
    monkeypatch.setattr(model_runtime, "network_transport", model.factory)
    payload, sizes = snapshot_payload()
    with host_flows.production_stand_in(realm) as standin, import_database(realm) as name:
        if stored is not None:
            store_models_observation(standin, stored[0], stored[1], age=stored[2])
        header = {
            "login": {"password": rf.credentials(realm, "standin-credentials.json")[
                "roles"]["operator"]},
            "runId": str(uuid4()), "importDatabase": name,
            "targetDatabase": standin.database, "final": False, "required": [],
            "decisions": [{"kind": "paper-embedding",
                           "reasonKey": "embedding-provenance-unproven",
                           "decision": "map", "mappingRule": "re-embed-pinned-model"}],
            "archives": sizes, "toWrite": 0,
        }
        # No embedder is given: the program builds its own on `SharedModelRuntime`, with
        # the reader of the stand-in profile's own database.
        runner = functools.partial(production_import, profile=standin.profile,
                                   clock=lambda: NOW, free_bytes=lambda: ROOM)
        status, answer = run_main(monkeypatch, "import", header, payload, runner)
        with rf.admin(realm, standin.database) as conn:
            chunks = conn.execute(
                "SELECT count(*) AS n, count(embedding) AS embedded FROM corpus.projection "
                "WHERE version_id=%s", (f"arxiv:{PAPER}@v1",)).fetchone()
        assert no_migration_backends(standin)
    if held:
        assert (status, answer) == (1, {"ok": False, "reason": "provider-held"})
        assert model.requests == [] and tuple(chunks) == (0, 0)
        return
    assert status == 0 and answer["ok"] is True and answer["changed"] >= 1
    assert tuple(chunks) == (40, 40)
    assert [len(item["input"]) for item in model.calls("/api/embed")] == [16, 16, 8]


# --- the import database's connection (U8 plan Step 164(e); NFR3.3, L4-12) ----------------------


def test_the_import_database_is_opened_with_scram_only(realm):
    """The import program opens the run's import database in the target profile's own
    instance as the operator tool's login, with `require_auth=scram-sha-256`. The driver's
    `connect` is a raise-only spy that refuses before any connection, so nothing is
    imported and the run's owner pools are closed again."""
    from tests.u8_service_operations_integration.operations.test_scram_sites import (
        Reached,
        demanded,
        refusing_connect,
    )

    payload, sizes = snapshot_payload()
    with host_flows.production_stand_in(realm) as standin, import_database(realm) as name:
        password = rf.credentials(realm, "standin-credentials.json")["roles"]["operator"]
        header = {"login": {"password": password}, "runId": str(uuid4()),
                  "importDatabase": name, "targetDatabase": standin.database, "final": False,
                  "required": [], "decisions": [], "archives": sizes, "toWrite": 0}
        with pytest.raises(Reached) as reached:
            production_import("import", header, payload, profile=standin.profile,
                              connect=refusing_connect, embedder=StandinEmbeddings(),
                              clock=lambda: NOW, free_bytes=lambda: ROOM)
        options = reached.value.options
        assert demanded(options) == ("127.0.0.1", standin.profile.database_port,
                                     "docsuri_operator", name, "scram-sha-256")
        assert options["password"] == password and options["connect_timeout"] == 5
        assert no_migration_backends(standin)
