"""Quarantine custody, checkpoint freshness and bounded streaming checks.

The isolated tests never connect to PostgreSQL. The separate actual rehearsal
uses the same coordinator against the owned synthetic realm under its run lock.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from docsuri_ops import u2_restore as recovery
from docsuri_ops.u2_restore_context import (
    RestoreContext,
    compute_checkpoint_digest,
    context_to_json,
    sha256_json,
)
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment(request):
    if any(item.name.startswith("test_actual_") for item in request.session.items):
        # Resolve the overridden parent session fixture. Its cached lock can be
        # shared by other DB test modules without opening a competing descriptor.
        request.getfixturevalue("exclusive_environment")
    yield


@pytest.fixture(autouse=True)
def bounded_case(request):
    """One five-minute budget for the complete real old-backup experiment."""
    import signal

    previous = signal.getsignal(signal.SIGALRM)

    def timeout(signum, frame):
        raise TimeoutError("restore verification case exceeded finite deadline")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(
        signal.ITIMER_REAL, 300 if request.node.name.startswith("test_actual_") else 30
    )
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture(autouse=True)
def reconcile_restore_fixtures(request):
    """The actual-backup rehearsal declares its two accounts disposable."""
    yield
    if not request.node.name.startswith("test_actual_"):
        return
    from backend.local_profile import private_bytes

    manifest = Path(os.environ["DOCSURI_U2_ENVIRONMENT_FILE"])
    profile = recovery.LocalProfile.load(manifest)
    secret = json.loads(private_bytes(profile.root / "migration-credentials.json"))
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=secret["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET session_replication_role = replica")
        for row in conn.execute(
            "SELECT table_schema,table_name FROM information_schema.columns "
            "WHERE column_name='account_id' AND table_schema IN "
            "('accounts','assistance','corpus','discovery','library','operations',"
            "'personalization','usage')"
        ).fetchall():
            conn.execute(
                f'DELETE FROM "{row["table_schema"]}"."{row["table_name"]}" '
                "WHERE account_id IN (SELECT id FROM accounts.account WHERE email LIKE %s)",
                ("restore-%@fixture.invalid",),
            )
        conn.execute(
            "DELETE FROM accounts.account WHERE email LIKE %s",
            ("restore-%@fixture.invalid",),
        )
        conn.execute("SET session_replication_role = origin")
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname="postgres",
        user="postgres",
        password=secret["databaseAdminPassword"],
        connect_timeout=3,
        autocommit=True,
    ) as conn:
        if conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (recovery.RESTORE_DATABASE,)
        ).fetchone():
            conn.execute(f'DROP DATABASE "{recovery.RESTORE_DATABASE}" WITH (FORCE)')


class Connection:
    def __init__(self, *rows):
        self.rows, self.statements, self.committed = list(rows), [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((str(query), params))
        return self

    def fetchone(self):
        return self.rows.pop(0)

    def commit(self):
        self.committed = True


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    coordinator = recovery.IsolatedRestore.__new__(recovery.IsolatedRestore)
    coordinator.root, coordinator.run = tmp_path, "docsuri-u2-0123456789abcdef"
    coordinator.profile = SimpleNamespace(
        root=tmp_path, run_id=coordinator.run, expires_at=time.time() + 3600
    )
    coordinator.deadline = time.monotonic() + 100
    coordinator.cleanup_deadline = coordinator.deadline + 7
    coordinator.directory = tmp_path / "restore-evidence"
    coordinator.directory.mkdir(mode=0o700)
    coordinator.source_digest = "1" * 64
    coordinator.policy_digest = "2" * 64
    coordinator.manifest_digest = "3" * 64
    monkeypatch.setattr(
        coordinator, "_connect", lambda *args, **kwargs: pytest.fail("unexpected DB access")
    )
    return coordinator


@pytest.fixture
def context(isolated):
    return RestoreContext(
        isolated.run,
        uuid4(),
        1,
        None,
        "0" * 64,
        "4" * 64,
        isolated.source_digest,
        "5" * 64,
        isolated.policy_digest,
        isolated.manifest_digest,
    )


def fragments(context):
    return [
        {
            "owner": owner,
            "version": 1,
            "runId": context.run_id,
            "checkpointId": str(context.checkpoint_id),
            "sequence": context.sequence,
            "records": [],
        }
        for owner in sorted(recovery.REQUIRED)
    ]


def test_private_keys_are_explicit_paired_and_authenticated(isolated):
    with pytest.raises(FileNotFoundError):
        isolated._key()
    isolated.provision_keys()
    key = isolated._key()
    isolated.provision_keys()
    assert isolated._key() == key and len(key) == 32
    path = isolated.directory / "checkpoint.json"
    recovery._write_new(path, isolated._authenticated({"restricted": True}))
    assert isolated._read_authenticated(path) == {"restricted": True}
    value = json.loads(path.read_bytes())
    value["payload"]["restricted"] = False
    path.write_text(json.dumps(value))
    with pytest.raises(recovery.RestoreRefused, match="authentication"):
        isolated._read_authenticated(path)


@pytest.mark.parametrize("case", ["missing", "mismatch", "foreign", "version", "mode", "link"])
def test_incomplete_or_foreign_key_custody_refuses(isolated, case):
    isolated.provision_keys()
    key = isolated.root / "restore-journal-key.json"
    second = isolated.root / "restore-key-recovery/restore-journal-key.json"
    if case == "missing":
        second.unlink()
    elif case == "mismatch":
        second.write_bytes(b"{}")
    elif case in ("foreign", "version"):
        value = json.loads(key.read_bytes())
        value["runId" if case == "foreign" else "version"] = "different"
        key.write_text(json.dumps(value))
        second.write_bytes(key.read_bytes())
    elif case == "mode":
        key.chmod(0o644)
    else:
        key.unlink()
        key.symlink_to(second)
    with pytest.raises((recovery.RestoreRefused, FileNotFoundError)):
        isolated.provision_keys()


def test_evidence_writes_are_private_exclusive_and_bounded(isolated):
    path = isolated.directory / "evidence.json"
    recovery._write_new(path, {"safe": True})
    assert path.stat().st_mode & 0o777 == 0o600
    assert recovery._file_digest(path, 1024) == (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
    )
    with pytest.raises(FileExistsError):
        recovery._write_new(path, {"overwrite": True})
    with pytest.raises(recovery.RestoreRefused):
        recovery._write_new(isolated.directory / "large", {"large": "a" * (2 * recovery.MIB)})
    with pytest.raises(recovery.RestoreRefused):
        recovery._file_digest(path, 1)
    isolated.directory.chmod(0o755)
    with pytest.raises(recovery.RestoreRefused):
        recovery._write_new(isolated.directory / "public", {})


@pytest.mark.parametrize("case", ["key", "version", "tag", "duplicate"])
def test_malformed_authentication_envelopes_are_never_authority(isolated, case):
    isolated.provision_keys()
    path = isolated.directory / "journal.json"
    value = isolated._authenticated({"restriction": 1})
    if case == "key":
        value["extra"] = True
    elif case == "version":
        value["keyVersion"] = "old"
    elif case == "tag":
        value["authentication"] = None
    recovery._write_new(path, value)
    if case == "duplicate":
        path.write_text('{"payload":{},"payload":{}}')
    with pytest.raises((ValueError, recovery.RestoreRefused)):
        isolated._read_authenticated(path)


def test_deadline_expiry_retains_bounded_cleanup_window(isolated):
    isolated.deadline = time.monotonic() - 1
    with pytest.raises(recovery.RestoreRefused, match="deadline"):
        isolated._remaining()
    assert 0 < isolated._remaining(cleanup=True) <= 10
    isolated.profile.expires_at = time.time() - 1
    assert isolated._remaining(cleanup=True) > 0
    isolated.cleanup_deadline = time.monotonic() - 1
    with pytest.raises(recovery.RestoreRefused):
        isolated._remaining(cleanup=True)


def test_fixed_database_vocabulary_precedes_credentials_or_network(isolated):
    with pytest.raises(recovery.RestoreRefused, match="vocabulary"):
        recovery.IsolatedRestore._connect(isolated, "production")


def test_current_checkpoint_requires_anchor_mac_metadata_and_complete_owners(
    isolated, context, monkeypatch
):
    isolated.provision_keys()
    monkeypatch.setattr(isolated, "_verify_checkpoint_keys", lambda record, ctx: None)
    owners = fragments(context)
    context = replace(
        context,
        checkpoint_digest=compute_checkpoint_digest(
            context, owners, required_owners=recovery.REQUIRED
        ),
    )
    current = context_to_json(context)
    monkeypatch.setattr(isolated, "_connect", lambda: Connection({"value": current}))
    monkeypatch.setattr(isolated, "_schema_digest", lambda: context.schema_digest)
    path = isolated.directory / f"checkpoint-{context.checkpoint_id}.json"
    record = {"context": current, "backupId": str(uuid4()), "fragments": owners}
    recovery._write_new(path, isolated._authenticated(record))
    assert isolated.current_checkpoint(context) == (context, record)
    with pytest.raises(recovery.RestoreRefused, match="stale"):
        isolated.current_checkpoint(replace(context, checkpoint_id=uuid4()))
    monkeypatch.setattr(isolated, "_schema_digest", lambda: "f" * 64)
    with pytest.raises(recovery.RestoreRefused, match="metadata"):
        isolated.current_checkpoint(context)
    monkeypatch.setattr(isolated, "_schema_digest", lambda: context.schema_digest)
    record["fragments"].pop()
    path.write_bytes(recovery.canonical_json_bytes(isolated._authenticated(record)))
    with pytest.raises(ValueError, match="owner"):
        isolated.current_checkpoint(context)
    monkeypatch.setattr(isolated, "_connect", lambda: Connection({"value": None}))
    with pytest.raises(recovery.RestoreRefused, match="missing"):
        isolated.current_checkpoint()


@pytest.mark.parametrize("case", ["database", "guard", "identity", "runtime"])
def test_restore_target_must_remain_owned_and_unconnectable(isolated, context, case):
    context = replace(context, schema_digest=sha256_json({"test": "hash"}))
    guard = {
        "run_id": isolated.run,
        "backup_digest": context.backup_digest,
        "quarantined": True,
        "starting_context": context_to_json(context),
    }
    identity = {"run_id": isolated.run, "schema_hashes": {"test": "hash"}}
    if case == "guard":
        guard["quarantined"] = False
    if case == "identity":
        identity["run_id"] = "foreign"
    connection = Connection(
        {"name": "docsuri_u2" if case == "database" else recovery.RESTORE_DATABASE},
        guard,
        identity,
        {"allowed": case == "runtime"},
    )
    with pytest.raises(recovery.RestoreRefused):
        isolated._guard_target(connection, context)
    assert not any("DROP" in statement for statement, _ in connection.statements)


def test_owned_guard_and_explicit_cleanup_never_name_source_for_drop(
    isolated, context, monkeypatch
):
    context = replace(context, schema_digest=sha256_json({}))
    target = Connection(
        {"name": recovery.RESTORE_DATABASE},
        {
            "run_id": isolated.run,
            "backup_digest": context.backup_digest,
            "quarantined": True,
            "starting_context": context_to_json(context),
        },
        {"run_id": isolated.run, "schema_hashes": {}},
        *[{"allowed": False}] * len(recovery.ROLES),
    )
    admin = Connection()
    selected = []

    def connect(database):
        selected.append(database)
        return admin if database == "postgres" else target

    monkeypatch.setattr(isolated, "_connect", connect)
    isolated.discard_quarantine(context)
    assert selected == [recovery.RESTORE_DATABASE, "postgres"]
    assert "docsuri_u2_restore" in admin.statements[0][0]


@pytest.mark.parametrize("case", ["live", "restore", "backup", "evidence", "free", "symlink"])
def test_resource_overrun_keeps_quarantine_without_deleting_business_state(
    isolated, monkeypatch, case
):
    rows = [{"bytes": recovery.MIB}, {"bytes": recovery.MIB}, {"bytes": recovery.MIB}]
    if case == "live":
        rows[0]["bytes"] = 512 * recovery.MIB
    elif case == "restore":
        rows[2]["bytes"] = recovery.RESTORE_LIMIT + 1
    elif case in ("backup", "evidence"):
        path = isolated.directory / ("archive.dump" if case == "backup" else "evidence.json")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.ftruncate(descriptor, 256 * recovery.MIB + 1)
        os.close(descriptor)
    elif case == "symlink":
        (isolated.directory / "foreign").symlink_to(isolated.root)
    monkeypatch.setattr(isolated, "_connect", lambda: Connection(*rows))
    monkeypatch.setattr(
        recovery.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(free=0 if case == "free" else 8 * 1024**3),
    )
    with pytest.raises(recovery.RestoreRefused):
        isolated._resources()


def test_measured_resources_include_wal_and_separate_evidence(isolated, monkeypatch):
    recovery._write_new(isolated.directory / "receipt.json", {"count": 1})
    monkeypatch.setattr(
        isolated, "_connect", lambda: Connection({"bytes": 1000}, {"bytes": 2000}, None)
    )
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda _: SimpleNamespace(free=8 * 1024**3))
    measured = isolated._resources()
    assert measured["liveBytes"] == 1000 and measured["walBytes"] == 2000
    assert measured["restoreBytes"] == 0 and measured["ownedEvidenceBytes"] > 0
    assert measured["backupBytes"] == 0 and measured["reserveBytes"] == 2496 * recovery.MIB


def test_backup_revalidates_archive_digest_and_compatibility(isolated, monkeypatch):
    isolated.provision_keys()
    monkeypatch.setattr(isolated, "_capture_account_keys", lambda: {"test": "capture"})
    monkeypatch.setattr(isolated, "_verify_account_keys", lambda ref: None)
    monkeypatch.setattr(isolated, "ensure_stopped", lambda: None)
    monkeypatch.setattr(isolated, "_resources", lambda: {})
    monkeypatch.setattr(isolated, "_schema_digest", lambda: "a" * 64)

    def stream(arguments, archive, *, restore):
        assert arguments[:4] == ["pg_dump", "-U", "postgres", "-Fc"] and not restore
        descriptor = os.open(archive, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(descriptor, b"synthetic archive fixture")
        os.close(descriptor)

    monkeypatch.setattr(isolated, "_stream", stream)
    from uuid import UUID

    backup = isolated.backup()
    value, archive = isolated._backup(UUID(backup["backupId"]))
    assert value == backup and archive.name.endswith(".dump")
    with pytest.raises(recovery.RestoreRefused, match="typed"):
        isolated._backup("arbitrary-path")
    archive.write_bytes(b"tampered")
    with pytest.raises(recovery.RestoreRefused, match="compatibility"):
        isolated._backup(UUID(backup["backupId"]))


@pytest.mark.parametrize("mode", ["dump", "restore", "fail", "deadline", "overflow"])
def test_stream_is_finite_and_closes_its_owned_process(isolated, monkeypatch, mode):
    popen = subprocess.Popen
    if mode == "deadline":
        isolated.deadline = time.monotonic() + 0.1
        code = "import time; time.sleep(10)"
    elif mode == "fail":
        code = "raise SystemExit(7)"
    elif mode == "overflow":
        monkeypatch.setattr(recovery, "BACKUP_LIMIT", 32)
        code = "import os; os.write(1,b'x'*256)"
    elif mode == "restore":
        code = "import sys; assert sys.stdin.buffer.read()==b'archive'"
    else:
        code = "import os; os.write(1,b'archive')"
    children, controls = [], []

    def start(command, **kwargs):
        assert command[:3] == ["docker", "exec", "-i"]
        child = popen([sys.executable, "-c", code], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(recovery.subprocess, "Popen", start)
    monkeypatch.setattr(isolated, "_resources", lambda: {})
    monkeypatch.setattr(isolated, "_docker", lambda args, **kwargs: controls.append((args, kwargs)))
    monkeypatch.setattr(isolated, "_connect", lambda *args, **kwargs: Connection())
    path = isolated.directory / "archive.dump"
    if mode == "restore":
        path.write_bytes(b"archive")
        path.chmod(0o600)
    if mode in ("fail", "deadline", "overflow"):
        with pytest.raises(recovery.RestoreRefused):
            isolated._stream(["pg_dump"], path, restore=False)
    else:
        isolated._stream(
            ["pg_restore" if mode == "restore" else "pg_dump"], path, restore=mode == "restore"
        )
        assert path.read_bytes() == b"archive"
    assert children[0].poll() is not None
    assert controls and all(record[1]["cleanup"] for record in controls)


def test_constructor_refuses_foreign_or_unbounded_profile_before_container_work(
    tmp_path, monkeypatch
):
    tmp_path.chmod(0o700)
    run = "docsuri-u2-0123456789abcdef"
    profile = SimpleNamespace(
        root=tmp_path,
        run_id=run,
        realm="account-controls",
        database_name="docsuri_u2",
        expires_at=time.time() + 60,
    )
    monkeypatch.setattr(recovery.LocalProfile, "load", lambda _: profile)
    path = tmp_path / "environment.json"
    recovery._write_new(
        path, {"container": run, "volume": run + "-pgdata", "databaseImage": recovery.IMAGE}
    )
    verified = []
    monkeypatch.setattr(
        recovery.IsolatedRestore, "_verify_container", lambda self: verified.append(self.run)
    )
    args = {"source_digest": "1" * 64, "policy_digest": "2" * 64, "manifest_digest": "3" * 64}
    instance = recovery.IsolatedRestore(path, **args)
    assert verified == [run] and instance.directory.is_dir()
    with pytest.raises(recovery.RestoreRefused, match="deadline"):
        recovery.IsolatedRestore(path, **args, seconds=301)
    profile.realm = "journey"
    with pytest.raises(recovery.RestoreRefused, match="explicit"):
        recovery.IsolatedRestore(path, **args)
    profile.realm = "account-controls"
    path.write_text("{}")
    with pytest.raises(recovery.RestoreRefused, match="container"):
        recovery.IsolatedRestore(path, **args)


def test_container_identity_and_hard_memory_cap_are_verified(isolated, monkeypatch):
    record = {
        "Config": {"Labels": {"dev.docsuri.u2.run": isolated.run}, "Image": recovery.IMAGE},
        "State": {"Status": "running"},
        "HostConfig": {"Memory": 1024**3},
    }
    volume = {"Labels": {"dev.docsuri.u2.run": isolated.run}}
    monkeypatch.setattr(
        isolated,
        "_docker",
        lambda args: json.dumps([volume if args[0] == "volume" else record]).encode(),
    )
    isolated._verify_container()
    record["HostConfig"]["Memory"] = 0
    with pytest.raises(recovery.RestoreRefused, match="bounded"):
        isolated._verify_container()
    record["HostConfig"]["Memory"] = 1024**3
    volume["Labels"] = {}
    with pytest.raises(recovery.RestoreRefused, match="ownership"):
        isolated._verify_container()


def test_capture_fsyncs_authenticated_complete_checkpoint_before_anchor_cas(
    isolated, context, monkeypatch
):
    isolated.provision_keys()
    monkeypatch.setattr(isolated, "ensure_stopped", lambda: None)
    backup_id = uuid4()
    monkeypatch.setattr(isolated, "_backup", lambda _: ({"sha256": context.backup_digest}, None))
    monkeypatch.setattr(isolated, "_schema_digest", lambda: context.schema_digest)
    monkeypatch.setattr(
        recovery, "OwnerTransactions", lambda *args, **kwargs: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr(isolated, "_exports", lambda tx, ctx: fragments(ctx))

    class Anchor(Connection):
        def execute(self, query, params=None):
            if "advance" in query:
                expected = params[0].obj
                path = isolated.directory / f"checkpoint-{expected['checkpointId']}.json"
                assert isolated._read_authenticated(path)["context"] == expected
                self.rows = [{"value": expected}]
            return self

    monkeypatch.setattr(isolated, "_connect", lambda: Anchor({"value": None}))
    checkpoint = isolated.capture_checkpoint(backup_id)
    assert checkpoint.sequence == 1 and checkpoint.checkpoint_digest != "0" * 64
    monkeypatch.setattr(
        isolated, "_connect", lambda: Anchor({"value": context_to_json(checkpoint)})
    )
    later = isolated.capture_checkpoint(backup_id)
    assert later.sequence == 2 and later.previous_digest == checkpoint.checkpoint_digest


def test_restore_uses_distinct_quarantine_and_requires_explicit_cleanup(
    isolated, context, monkeypatch
):
    monkeypatch.setattr(isolated, "ensure_stopped", lambda: None)
    backup_id = uuid4()
    monkeypatch.setattr(
        isolated, "current_checkpoint", lambda _: (context, {"backupId": str(backup_id)})
    )
    monkeypatch.setattr(
        isolated,
        "_backup",
        lambda _: ({"sha256": context.backup_digest}, isolated.directory / "fixture.dump"),
    )
    admin, target = Connection(None), Connection()
    monkeypatch.setattr(isolated, "_connect", lambda name: admin if name == "postgres" else target)
    checked = []
    monkeypatch.setattr(isolated, "_guard_target", lambda conn, ctx: checked.append(ctx))
    monkeypatch.setattr(isolated, "_resources", lambda: {"restoreBytes": 10})

    def stream(args, archive, *, restore):
        assert restore and args[-1] == recovery.RESTORE_DATABASE
        assert "--single-transaction" in args

    monkeypatch.setattr(isolated, "_stream", stream)
    result = isolated.restore(context)
    assert result["state"] == "restored-quarantined" and checked == [context]
    assert not any("DROP" in statement for statement, _ in admin.statements)
    assert any("starting_context" in statement for statement, _ in target.statements)
    admin.rows = [{"exists": 1}]
    with pytest.raises(recovery.RestoreRefused, match="already exists"):
        isolated.restore(context)


def test_reconcile_requires_unchanged_current_fragments_and_all_owner_receipts(
    isolated, context, monkeypatch
):
    from backend.control_restore import (
        AccountsRestore,
        AssistanceRestore,
        DiscoveryRestore,
        UsageRestore,
    )
    from backend.modules.library import restore as library
    from backend.modules.personalization import restore as personalization

    owners = fragments(context)
    context = replace(
        context,
        checkpoint_digest=compute_checkpoint_digest(
            context, owners, required_owners=recovery.REQUIRED
        ),
    )
    monkeypatch.setattr(isolated, "ensure_stopped", lambda: None)
    monkeypatch.setattr(isolated, "current_checkpoint", lambda _: (context, {"fragments": owners}))
    monkeypatch.setattr(isolated, "_exports", lambda *args: owners)
    monkeypatch.setattr(
        recovery, "OwnerTransactions", lambda *args, **kwargs: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr(isolated, "_resources", lambda: {})
    reconciled = []

    def owner_receipt(tx, fragment, ctx):
        reconciled.append(fragment["owner"])
        return {
            "owner": fragment["owner"],
            "disposition": "reconciled",
            "checkpointId": str(ctx.checkpoint_id),
            "sequence": ctx.sequence,
            "fragmentDigest": recovery.fragment_digest(ctx, fragment),
            "evidenceRef": str(uuid4()),
        }

    for hook in (
        AccountsRestore,
        AssistanceRestore,
        DiscoveryRestore,
        UsageRestore,
        library,
        personalization,
    ):
        monkeypatch.setattr(hook, "reconcile_restore", owner_receipt)
    result = isolated.reconcile(context)
    assert result["activated"] is False and set(reconciled) == recovery.REQUIRED
    assert result["state"] == "reconciled-quarantined"
    monkeypatch.setattr(
        library, "reconcile_restore", lambda *args: {"owner": "Library", "disposition": "partial"}
    )
    with pytest.raises(recovery.RestoreRefused, match="evidence"):
        isolated.reconcile(context)
    owners[0]["records"].append({"newRestriction": True})
    with pytest.raises(recovery.RestoreRefused, match="changed"):
        isolated.reconcile(context)


@pytest.fixture
def account_custody(isolated, monkeypatch):
    import base64
    import hmac

    from backend.modules.accounts import control_keys

    real_type = control_keys.ControlKeyring
    verifier = b"v" * 32
    legacy = hmac.new(verifier, b"encryption\0u2-controls-v1", hashlib.sha256).digest()
    new_version = "u2-" + "a" * 32
    record = {
        "runId": isolated.run,
        "generation": 2,
        "active": new_version,
        "keys": {
            "u2-v1": base64.b64encode(legacy).decode(),
            new_version: base64.b64encode(b"n" * 32).decode(),
        },
    }
    for name, value in (
        ("account-verifier.key", verifier),
        ("account-control-keyring.initialized", isolated.run.encode()),
        ("account-control-keyring.json", json.dumps(record).encode()),
    ):
        path = isolated.root / name
        path.write_bytes(value)
        path.chmod(0o600)

    def test_owned_ring(root, run_id, key):
        assert root == isolated.root and run_id == isolated.run and key == legacy
        instance = real_type.__new__(real_type)
        instance.root, instance.run_id, instance.legacy_key = root, run_id, key
        instance.read()
        return instance

    monkeypatch.setattr(control_keys, "ControlKeyring", test_owned_ring)
    return record


def test_backup_specific_key_bundle_is_validated_without_rotation_or_repair(
    isolated, context, account_custody
):
    isolated.provision_keys()
    reference = isolated._capture_account_keys()
    isolated._verify_account_keys(reference)
    assert reference["generation"] == 2 and reference["runId"] == isolated.run
    before = (isolated.root / "account-control-keyring.json").read_bytes()
    assert isolated._capture_account_keys() == reference
    backup_id = uuid4()
    recovery._write_new(
        isolated.directory / f"backup-{backup_id}.json",
        isolated._authenticated(
            {"runId": isolated.run, "sha256": context.backup_digest, "accountKeyCustody": reference}
        ),
    )
    isolated._verify_checkpoint_keys({"backupId": str(backup_id)}, context)
    with pytest.raises(recovery.RestoreRefused, match="another backup"):
        isolated._verify_checkpoint_keys(
            {"backupId": str(backup_id)}, replace(context, backup_digest="a" * 64)
        )
    assert (isolated.root / "account-control-keyring.json").read_bytes() == before


@pytest.mark.parametrize(
    "case", ["bundle", "tamper", "marker", "both-live", "reference", "retained-key"]
)
def test_missing_or_changed_backup_account_keys_keep_restore_quarantined(
    isolated, account_custody, case
):
    from backend.modules.accounts.control_policy import PolicyUnavailable

    reference = isolated._capture_account_keys()
    bundle = isolated.root / "account-key-recovery" / (reference["digest"] + ".json")
    if case == "bundle":
        bundle.unlink()
    elif case == "tamper":
        bundle.write_bytes(b"{}")
    elif case == "marker":
        (isolated.root / "account-control-keyring.initialized").unlink()
    elif case == "both-live":
        (isolated.root / "account-control-keyring.initialized").unlink()
        (isolated.root / "account-control-keyring.json").unlink()
    elif case == "reference":
        reference["generation"] = 0
    else:
        account_custody["keys"].pop("u2-v1")
        (isolated.root / "account-control-keyring.json").write_text(json.dumps(account_custody))
    with pytest.raises((recovery.RestoreRefused, PolicyUnavailable, FileNotFoundError)):
        isolated._verify_account_keys(reference)


def test_actual_old_backup_reconciles_newer_restrictions_and_replay_preserves_work():
    """Real PostgreSQL backup/restore; two disposable accounts, never existing users."""
    from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
    from backend.modules.plans.control_service import ControlUsageService
    from backend.modules.plans.guarded_repository import GuardedUsageRepository
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.transactions import Authority, OwnerTransactions
    from scripts import verify_docsuri_u2 as runner

    manifest = Path(os.environ["DOCSURI_U2_ENVIRONMENT_FILE"])
    profile = recovery.LocalProfile.load(manifest)
    coordinator = recovery.IsolatedRestore(
        manifest,
        source_digest=runner.source_identity()["sha256"],
        policy_digest=sha256_json(asdict(SYNTHETIC_POLICY)),
        manifest_digest=sha256_json(
            {"revision": "u2-owners-v1", "owners": sorted(recovery.REQUIRED)}
        ),
    )
    coordinator.ensure_stopped()
    coordinator.provision_keys()
    kept, erased, old_session, authority_revision, operation, old_event = [
        uuid4() for _ in range(6)
    ]
    consent_revision = uuid4()
    with coordinator._connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"] <= 18
        for account in (kept, erased):
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
                "VALUES(%s,%s,'synthetic-restore-fixture-not-login-hash',true,true,%s,'restore-fixture')",
                (account, f"restore-{account}@fixture.invalid", authority_revision),
            )
            for purpose in ("local-research", "personalization"):
                conn.execute(
                    "INSERT INTO accounts.consent(account_id,purpose,granted,revision) VALUES(%s,%s,true,%s)",
                    (account, purpose, consent_revision),
                )
            conn.execute("INSERT INTO personalization.settings(account_id) VALUES(%s)", (account,))
            conn.execute(
                "INSERT INTO personalization.behavior(account_id,id,purpose_revision,fact) VALUES(%s,%s,%s,'{}')",
                (account, uuid4(), consent_revision),
            )
            conn.execute(
                'INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,\'{"q":"synthetic-private"}\')',
                (account, uuid4()),
            )
            conn.execute(
                "INSERT INTO assistance.glossary(account_id,revision,snapshot) VALUES(%s,'fixture','{}')",
                (account,),
            )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,%s,'fixture',%s,clock_timestamp()+interval '15 minutes')",
            (old_session, kept, str(old_session), authority_revision),
        )
        conn.execute("INSERT INTO library.history_boundary(account_id) VALUES(%s)", (kept,))
        conn.execute(
            "INSERT INTO library.history(account_id,execution_id,query,captured_generation,completed_at,admission_sequence) "
            "VALUES(%s,%s,'{}',0,clock_timestamp(),1)",
            (kept, old_event),
        )
        conn.execute(
            "INSERT INTO discovery.owner_admission(account_id,sequence) VALUES(%s,1)", (kept,)
        )
        for account in (kept, erased):
            event = old_event if account == kept else uuid4()
            conn.execute(
                "INSERT INTO discovery.execution(id,account_id,query,query_hash,captured_generation,results,relay_state) "
                "VALUES(%s,%s,'{}',%s,0,'[]','pending')",
                (event, account, "a" * 64),
            )
            conn.execute(
                "INSERT INTO discovery.admission(execution_id,account_id,sequence,authority_revision,query_hash) "
                "VALUES(%s,%s,1,%s,%s)",
                (event, account, authority_revision, "a" * 64),
            )
        period = "u2-period:" + str(
            conn.execute(
                "SELECT floor(extract(epoch FROM clock_timestamp())/900)::bigint AS p"
            ).fetchone()["p"]
        )
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy,period_id) VALUES(%s,3,'u2-synthetic-v1',%s)",
            (kept, period),
        )
        admission = conn.execute(
            "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,disposition,period_id,policy_ref) "
            "VALUES(%s,%s,%s,'{}','open',%s,%s) RETURNING *",
            (operation, kept, "b" * 64, period, Jsonb(SYNTHETIC_POLICY.reference)),
        ).fetchone()
    authority = Authority(kept, old_session)
    tx = OwnerTransactions(profile, process="maintenance")
    try:
        reservation = ControlUsageService(tx, SYNTHETIC_POLICY).reserve(authority, admission)
    finally:
        tx.close()
    backup = coordinator.backup()
    tx = OwnerTransactions(profile, process="maintenance")
    try:
        assistance = GuardedAssistanceRepository(tx, None)
        assistance.reject_open(authority, operation)
        proof = assistance.rejected_admission_proof(authority, operation)
        GuardedUsageRepository(tx).reject_operation(proof)
    finally:
        tx.close()
    permitted_source = uuid4()
    with coordinator._connect() as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (old_session,))
        conn.execute(
            "UPDATE accounts.consent SET granted=false,revision=gen_random_uuid(),effective_at=clock_timestamp() WHERE account_id=%s AND purpose='local-research'",
            (kept,),
        )
        conn.execute(
            "UPDATE library.history_boundary SET generation=1,revision=gen_random_uuid(),eligible_after=clock_timestamp(),admission_cutoff=1 WHERE account_id=%s",
            (kept,),
        )
        conn.execute("DELETE FROM library.history WHERE account_id=%s", (kept,))
        conn.execute(
            "UPDATE personalization.settings SET input_boundary=1,revision=gen_random_uuid() WHERE account_id=%s",
            (kept,),
        )
        conn.execute("DELETE FROM personalization.behavior WHERE account_id=%s", (kept,))
        conn.execute(
            "INSERT INTO personalization.behavior(account_id,id,purpose_revision,fact,input_boundary) VALUES(%s,%s,%s,'{}',1)",
            (kept, permitted_source, consent_revision),
        )
        conn.execute(
            "UPDATE accounts.account SET lifecycle_state='erased',active=false,lifecycle_revision=gen_random_uuid() WHERE id=%s",
            (erased,),
        )
        conn.execute(
            "INSERT INTO accounts.current_restriction(account_id,generation,lifecycle_revision,disposition,consent) "
            "SELECT id,1,lifecycle_revision,'erased','{}' FROM accounts.account WHERE id=%s",
            (erased,),
        )
        conn.execute("DELETE FROM library.saved_query WHERE account_id=%s", (erased,))
        conn.execute("DELETE FROM personalization.behavior WHERE account_id=%s", (erased,))
        conn.execute("DELETE FROM personalization.settings WHERE account_id=%s", (erased,))
        conn.execute("DELETE FROM assistance.glossary WHERE account_id=%s", (erased,))
        conn.execute("DELETE FROM discovery.execution WHERE account_id=%s", (erased,))
        conn.execute("DELETE FROM discovery.admission WHERE account_id=%s", (erased,))
    from uuid import UUID

    previous = coordinator.capture_checkpoint(UUID(backup["backupId"]))
    context = coordinator.capture_checkpoint(UUID(backup["backupId"]))
    with pytest.raises(recovery.RestoreRefused, match="stale"):
        coordinator.current_checkpoint(previous)
    restored = coordinator.restore(context)
    assert restored["state"] == "restored-quarantined"
    # An older dump really contained the prohibited rows; it was not replaced
    # by a fresh full DB copy or a pre-suppressed synthetic export.
    with coordinator._connect(recovery.RESTORE_DATABASE) as conn:
        assert conn.execute(
            "SELECT NOT revoked AS old FROM accounts.session WHERE id=%s", (old_session,)
        ).fetchone()["old"]
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM assistance.glossary WHERE account_id=%s", (erased,)
            ).fetchone()["n"]
            == 1
        )
    result = coordinator.reconcile(context)
    assert result["state"] == "reconciled-quarantined" and result["activated"] is False
    with coordinator._connect(recovery.RESTORE_DATABASE) as conn:
        assert conn.execute(
            "SELECT revoked FROM accounts.session WHERE id=%s", (old_session,)
        ).fetchone()["revoked"]
        assert not conn.execute(
            "SELECT granted FROM accounts.consent WHERE account_id=%s AND purpose='local-research'",
            (kept,),
        ).fetchone()["granted"]
        for table in ("library.history", "personalization.behavior"):
            assert (
                conn.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE account_id=%s", (kept,)
                ).fetchone()["n"]
                == 0
            )
        for table in (
            "library.saved_query",
            "personalization.settings",
            "assistance.glossary",
            "discovery.execution",
            "discovery.admission",
        ):
            assert (
                conn.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE account_id=%s", (erased,)
                ).fetchone()["n"]
                == 0
            )
        assert (
            conn.execute(
                "SELECT relay_state FROM discovery.execution WHERE id=%s", (old_event,)
            ).fetchone()["relay_state"]
            == "suppressed"
        )
        row = conn.execute(
            "SELECT disposition,period_id,quantity FROM usage.reservation WHERE id=%s",
            (reservation["id"],),
        ).fetchone()
        assert row == {"disposition": "released", "period_id": period, "quantity": 1}
        assert (
            conn.execute(
                "SELECT disposition FROM assistance.admission WHERE operation_id=%s",
                (operation,),
            ).fetchone()["disposition"]
            == "rejected"
        )
        fresh_session, fresh_work = uuid4(), uuid4()
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) VALUES(%s,%s,%s,'fixture',%s,clock_timestamp()+interval '15 minutes')",
            (fresh_session, kept, str(fresh_session), authority_revision),
        )
        conn.execute(
            "INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,'{}')",
            (kept, fresh_work),
        )
        conn.execute(
            "INSERT INTO personalization.behavior(account_id,id,purpose_revision,fact,input_boundary) VALUES(%s,%s,%s,'{}',1)",
            (kept, fresh_work, consent_revision),
        )
    # Exact receipt replay must not repeat destructive cleanup on permitted
    # work produced within the still-quarantined verification environment.
    repeated = coordinator.reconcile(context)
    assert repeated["owners"] == result["owners"]
    with coordinator._connect(recovery.RESTORE_DATABASE) as conn:
        assert not conn.execute(
            "SELECT revoked FROM accounts.session WHERE id=%s", (fresh_session,)
        ).fetchone()["revoked"]
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM library.saved_query WHERE id=%s", (fresh_work,)
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE id=%s", (fresh_work,)
            ).fetchone()["n"]
            == 1
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE assistance.admission SET disposition='accepted',reservation_id=%s WHERE operation_id=%s",
                (reservation["id"], operation),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT accounts.guard_session(%s,%s,'account-control')", (kept, old_session)
            )
        conn.rollback()
    with coordinator._connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE id=%s",
                (permitted_source,),
            ).fetchone()["n"]
            == 1
        )
    journal = coordinator.directory / f"checkpoint-{context.checkpoint_id}.json"
    saved = journal.read_bytes()
    tampered = json.loads(saved)
    tampered["payload"]["context"]["sequence"] = context.sequence + 1
    journal.write_bytes(recovery.canonical_json_bytes(tampered))
    try:
        with pytest.raises(recovery.RestoreRefused, match="authentication"):
            coordinator.reconcile(context)
    finally:
        journal.write_bytes(saved)
    key = coordinator.root / "restore-key-recovery/restore-journal-key.json"
    absent = key.with_suffix(".missing")
    key.rename(absent)
    try:
        with pytest.raises(FileNotFoundError):
            coordinator.reconcile(context)
    finally:
        absent.rename(key)
    recovery._write_new(
        coordinator.directory / f"rehearsal-{context.checkpoint_id}.json",
        {
            "runId": coordinator.run,
            "backupBytes": backup["bytes"],
            "result": result,
            "olderProhibitedRowsObserved": True,
            "exactReplayPreservedNewWork": True,
            "originalSourcePreserved": True,
            "hostLossRecovery": False,
        },
    )
    coordinator.discard_quarantine(context)
