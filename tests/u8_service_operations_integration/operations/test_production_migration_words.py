"""The production migration platform's v2 side, with stand-ins (U8 plan Step 32; the
person's decision of 2026-10-24, "Build it, test on test v1"; BR8.2, D4–D6).

The production environment tool's words and the import program run only as the service
account against the production profile, so here their runners are recording stand-ins:
nothing reaches sudo, the keychain or /Library/DocSuri. The v1 side runs against the
synthetic v1 in `integration/test_production_migration_platform.py`.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.modules.operations.errors import OperationsError
from docsuri_ops.migration import production
from docsuri_ops.migration.tool import MigrationTool
from docsuri_ops.production_tool import Refused


class Completed:
    def __init__(self, stdout: bytes, returncode: int = 0):
        self.stdout, self.returncode, self.stderr = stdout, returncode, b""


RELEASED = secrets.token_hex(16)  # thirty-two characters, generated per run (L1-36)


def released(login: str) -> bytearray:
    assert login == "operator"
    return bytearray(RELEASED.encode())


# --- the import program -----------------------------------------------------------------------


def test_the_importer_runs_the_program_in_person_with_the_login_in_the_header_only():
    seen = {}

    def run(argv, *, input, **options):
        seen.update(argv=argv, input=input, options=options)
        return Completed(b'{"ok": true, "misfits": [], "newInFinal": [], "report": {}, '
                         b'"changed": 0}\n')

    importer = production.ProgramImporter(release=released, run=run, account="_docsuri_v2")
    request = {"runId": "r", "importDatabase": "docsuri_v2_import_" + "a" * 12,
               "targetDatabase": "docsuri_v2_rehearsal_" + "b" * 12, "decisions": [],
               "archives": {"index": b"INDEX", "objects": b"OBJECTS!"}}
    answer = importer("import", request)
    assert answer["ok"] is True and answer["changed"] == 0
    assert seen["argv"] == ["/usr/bin/sudo", "-k", "-u", "_docsuri_v2",
                            production.IMPORT_PROGRAM, "import"]
    header, payload = seen["input"].split(b"\n", 1)
    document = json.loads(header)
    assert document["login"] == {"password": RELEASED}
    assert document["archives"] == {"index": 5, "objects": 8} and payload == b"INDEXOBJECTS!"
    assert RELEASED not in " ".join(seen["argv"])
    assert request["archives"] == {"index": b"INDEX", "objects": b"OBJECTS!"}  # unchanged


@pytest.mark.parametrize(("stdout", "code", "reason"), [
    (b'{"ok": false, "reason": "database-refused"}\n', 1, "database-refused"),
    (b"", 1, "import-answered-no-result"),
])
def test_an_import_programs_refusal_is_a_fixed_reason(stdout, code, reason):
    importer = production.ProgramImporter(release=released, account="_docsuri_v2",
                                          run=lambda argv, **o: Completed(stdout, code))
    with pytest.raises(production.ToolRefused, match=reason):
        importer("import", {"archives": {"index": b"", "objects": b""}})
    with pytest.raises(production.ToolRefused, match="word-refused"):
        importer("drop", {"archives": {"index": b"", "objects": b""}})


# --- the production environment tool's words --------------------------------------------------


def test_the_databases_go_through_the_production_environment_tool_in_person(tmp_path):
    calls = []

    def invoke(word, document, *, login=None, payload=None):
        calls.append((word, document, login, payload))
        return {"ok": True}

    databases = production.ToolDatabases(invoke, connect=None)
    databases.create_rehearsal("docsuri_v2_rehearsal_" + "a" * 12)
    databases.create_import("docsuri_v2_import_" + "b" * 12)
    spool = tmp_path / "dump"
    spool.write_bytes(b"PGDMP-dump")
    databases.restore_import("docsuri_v2_import_" + "b" * 12, spool)
    databases.prepare_production("docsuri_v2")
    assert [(word, login) for word, _, login, _ in calls] == [
        ("create-disposable", "operator"), ("create-disposable", "operator"),
        ("restore-import", "operator"), ("prepare-production", "operator")]
    restore = calls[2]
    assert restore[1]["sha256"] == hashlib.sha256(b"PGDMP-dump").hexdigest()
    assert restore[3] == b"PGDMP-dump" and all("operationId" in item[1] for item in calls)

    def refusing(word, document, **options):
        raise Refused("template-not-current")

    with pytest.raises(production.ToolRefused, match="template-not-current"):
        production.ToolDatabases(refusing, connect=None).create_rehearsal("x")


# --- the migration tool's importer seam ----------------------------------------------------------


class Runs:
    def __init__(self):
        self.ledger = SimpleNamespace(records=lambda kind: [{"kind": "account"}])
        self.recorded = []

    def required_pairs(self):
        return {("account", "no-email")}

    def record_misfits(self, run_id, misfits, *, new_in_final=frozenset()):
        self.recorded.append((run_id, misfits, new_in_final))


def tool_with(importer) -> MigrationTool:
    platform = SimpleNamespace(importer=importer, names=SimpleNamespace(production="p"))
    tool = MigrationTool.__new__(MigrationTool)
    tool.runs, tool.platform, tool.ledger = Runs(), platform, Runs().ledger
    return tool


def test_a_final_runs_request_carries_the_frozen_pairs_and_the_archives():
    seen = {}

    def importer(word, request):
        seen.update(word=word, request=request)
        return {"misfits": [["account", "a1", "no-email"]], "newInFinal": [["paper", "x"]],
                "report": {"runId": "r"}}

    tool = tool_with(importer)
    run = {"runId": "r", "kind": "final"}
    misfits, fresh, report = tool._import_through_program(
        run, "docsuri_v2_import_" + "a" * 12, {"index": b"i", "objects": b"o"}, True,
        to_write=0)
    assert misfits == [("account", "a1", "no-email")] and fresh == {("paper", "x")}
    assert report == {"runId": "r"} and seen["word"] == "import"
    request = seen["request"]
    assert request["targetDatabase"] == "p" and request["final"] is True
    assert request["required"] == [["account", "no-email"]]
    assert request["decisions"] == [{"kind": "account"}]


@pytest.mark.parametrize("answer", [{"misfits": [["only-two", "x"]], "newInFinal": [],
                                     "report": {}},
                                    {"report": {}}, {"misfits": [], "newInFinal": [],
                                                     "report": []}])
def test_an_import_answer_outside_its_form_is_refused(answer):
    tool = tool_with(lambda word, request: answer)
    with pytest.raises(OperationsError) as refused:
        tool._import_through_program({"runId": "r", "kind": "final"}, "i",
                                     {"index": b"", "objects": b""}, True, to_write=0)
    assert refused.value.current == {"reasonKey": "import-answer-refused"}


@pytest.mark.parametrize("reason", ["internal-disk-low", "internal-disk-critical"])
def test_an_interrupted_import_answer_is_an_interruption_with_its_reason(reason):
    """Step 69(b) (S3): the program stopped at a boundary; the tool interrupts the run."""
    from docsuri_ops.migration.tool import Interrupted

    seen = {}

    def importer(word, request):
        seen.update(request=request)
        return {"ok": True, "interrupted": reason}

    tool = tool_with(importer)
    with pytest.raises(Interrupted) as stopped:
        tool._import_through_program({"runId": "r", "kind": "final"}, "i",
                                     {"index": b"", "objects": b""}, True, to_write=5)
    assert stopped.value.reason == reason and seen["request"]["toWrite"] == 5
    elsewhere = tool_with(lambda word, request: {"ok": True, "interrupted": "elsewhere"})
    with pytest.raises(OperationsError) as refused:
        elsewhere._import_through_program({"runId": "r", "kind": "final"}, "i",
                                          {"index": b"", "objects": b""}, True, to_write=5)
    assert refused.value.current == {"reasonKey": "import-answer-refused"}


def test_a_time_refused_paper_is_recorded_and_the_idempotency_pass_skips_it(tmp_path, clock):
    """Step 69(h) (L1-75): the program's time-refused triple passes the tool, is recorded
    as `_import` records it, and `_verify`'s request names the paper in `skipPapers`."""
    from backend.modules.operations.ledger import utc_text
    from backend.modules.operations.migration_records import MigrationRuns
    from tests.u8_service_operations_integration import recovery_flows as rf

    triple = ["paper", "2101.00006:v1", "refused-by-database-time-limits"]
    tool = tool_with(lambda word, request: {"misfits": [triple], "newInFinal": [],
                                            "report": {"runId": "r"}})
    # `_import_through_program` reads no reason: the triple passes as it is.
    misfits, fresh, _ = tool._import_through_program(
        {"runId": "r", "kind": "final"}, "i", {"index": b"", "objects": b""}, True,
        to_write=0)
    assert misfits == [tuple(triple)]
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        runs = MigrationRuns(ledger, clock=clock)
        run = {"runId": "6d1f7a3e-0b55-4c4e-9a52-2f7f0e0c9a11", "kind": "dry",
               "target": "rehearsal", "toolCommit": "0" * 40, "decisionsDigest": "0" * 64,
               "state": "preparing", "startedAt": utc_text(clock())}
        ledger.atomic(lambda view: view.append("migration-run", run, expect_revision=0))
        for state in ("copying", "importing", "verifying"):
            runs.move(run["runId"], state, **({"targetCopyId": run["runId"],
                                                "snapshotCopyId": run["runId"]}
                                               if state == "copying" else {}))
        runs.record_misfits(run["runId"], misfits, new_in_final=fresh)
        assert ledger.get("misfit-record", (run["runId"], *triple))["newInFinal"] is False

        seen = {}

        def importer(word, request):
            seen.update(word=word, request=request)
            return {"changed": 0}

        verifier = MigrationTool.__new__(MigrationTool)
        verifier.runs, verifier.ledger = runs, ledger
        verifier.copies = SimpleNamespace(get=lambda copy_id: {
            "locations": ["database/docsuri_v2_rehearsal_" + "b" * 12]})
        verifier.platform = SimpleNamespace(
            importer=importer, snapshot=SimpleNamespace(verified_parts=lambda record: {}))
        verifier._import_database = lambda current: ("docsuri_v2_import_" + "a" * 12, {})
        verifier._archive_bytes = lambda parts: {"index": b"", "objects": b""}
        verifier._verify(runs.require(run["runId"]))
        assert seen["word"] == "idempotency"
        assert seen["request"]["skipPapers"] == ["2101.00006:v1"]
        assert runs.require(run["runId"])["state"] == "reported"
    finally:
        ledger.close()


# --- the environment file and the credentials --------------------------------------------------


def test_the_object_stores_credentials_are_a_private_file_of_your_own(tmp_path):
    login = {"accessKey": "a", "secretKey": secrets.token_hex(8)}  # per run (L1-36)
    good = tmp_path / "good.json"
    good.write_text(json.dumps(login))
    good.chmod(0o600)
    assert production.objects_credentials(good) == login
    loose = tmp_path / "loose.json"
    loose.write_text(json.dumps(login))
    loose.chmod(0o644)
    linked = tmp_path / "linked.json"
    linked.symlink_to(good)
    shaped = tmp_path / "shaped.json"
    shaped.write_text(json.dumps({"accessKey": "a"}))
    shaped.chmod(0o600)
    for path in (loose, linked, shaped, tmp_path / "missing.json"):
        with pytest.raises(production.SourcesRefused):
            production.objects_credentials(Path(path))


def test_the_dump_carries_the_named_address_and_its_receipt_is_checked():
    sources = production.V1Sources(
        {"host": "127.0.0.1", "port": 15510, "database": "docsuri"}, "http://127.0.0.1:19209",
        "docsuri-corpus", "http://127.0.0.1:19009", "docsuri-v1", Path("/x"))
    sent = []

    def agent(word, document, *, via):
        sent.append((word, document, via))
        return {"source": {"host": "127.0.0.1", "port": 15510, "database": "docsuri"}}

    production.named_dump(sources, agent)("dry-run-snapshot", "c", None)
    assert sent == [("snapshot", {"kind": "dry-run-snapshot", "recordId": "c", "v1Source": {
        "host": "127.0.0.1", "port": 15510, "database": "docsuri"}}, "in-person")]
    elsewhere = production.named_dump(sources, lambda word, document, via: {
        "source": {"host": "127.0.0.1", "port": 5432, "database": "docsuri"}})
    with pytest.raises(production.SnapshotRefused, match="v1-address-not-named"):
        elsewhere("dry-run-snapshot", "c", None)
    from docsuri_ops.u8_platform.drivers import DriverRefused

    def refusing(word, document, via):
        raise DriverRefused("v1-source-not-named")

    with pytest.raises(production.SnapshotRefused, match="v1-source-not-named"):
        production.named_dump(sources, refusing)("dry-run-snapshot", "c", None)
