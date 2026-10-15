"""Identity recovery and bounded process supervision, isolated from the U2 DB."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts import prepare_docsuri_u2_browser as bootstrap

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    yield


@pytest.fixture
def run(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(bootstrap.runner, "RUN", tmp_path)
    value = {"runId": "docsuri-u2-0123456789abcdef", "expiresAt": time.time() + 3600,
        "database": "docsuri_u2", "realm": "account-controls", "fixtureAccounts": ["kept"],
        "sourceSha": "before", "locks": {"frontend/pnpm-lock.yaml": "old"}}
    path = tmp_path / "environment.json"
    bootstrap.atomic_bytes(path, bootstrap.encoded(value))
    bootstrap.atomic_bytes(tmp_path / "ownership.json", bootstrap.encoded({"runId": value["runId"],
        "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest()}))

    def check(selected):
        current = json.loads(selected.read_bytes())
        ownership = json.loads((tmp_path / "ownership.json").read_bytes())
        if ownership != {"runId": current["runId"], "manifestSha256": hashlib.sha256(selected.read_bytes()).hexdigest()}:
            raise bootstrap.runner.Refused("manifest identity mismatch")
        if current["expiresAt"] < time.time():
            raise bootstrap.runner.Refused("synthetic retention expired")
        return SimpleNamespace(root=tmp_path), current

    monkeypatch.setattr(bootstrap.runner, "manifest", check)
    monkeypatch.setattr(bootstrap.runner, "preflight", lambda: None)
    monkeypatch.setattr(bootstrap.runner, "require_resources", lambda value: None)
    return path, value


def test_identity_reconciliation_preserves_lifetime_data_and_owner_binding(run):
    path, before = run
    after = dict(before, sourceSha="after", sourceTreeSha256="tree", locks={"frontend/pnpm-lock.yaml": "new"})
    with bootstrap.exclusive():
        bootstrap.reconcile(path, before, after)
    assert bootstrap.checked(path)[1] == after
    assert after["expiresAt"] == before["expiresAt"]
    assert after["fixtureAccounts"] == ["kept"]
    assert not (path.parent / bootstrap.PENDING).exists()


@pytest.mark.parametrize("field,value", [("expiresAt", 99999999999), ("database", "docsuri_u1"),
    ("fixtureAccounts", []), ("runId", "docsuri-u2-ffffffffffffffff")])
def test_nonidentity_changes_cannot_be_reconciled(run, field, value):
    path, before = run
    with pytest.raises(bootstrap.runner.Refused, match="cannot change"):
        bootstrap.reconcile(path, before, dict(before, **{field: value}))
    assert json.loads(path.read_bytes()) == before


def interrupt_identity(run, monkeypatch):
    path, before = run
    atomic = bootstrap.atomic_bytes

    def failed_owner(target, payload):
        if target.name == "ownership.json":
            raise OSError("injected owner write interruption")
        return atomic(target, payload)

    with monkeypatch.context() as patch:
        patch.setattr(bootstrap, "atomic_bytes", failed_owner)
        with pytest.raises(OSError, match="interruption"):
            bootstrap.reconcile(path, before, dict(before, sourceSha="after"))


def test_interrupted_pair_is_fail_closed_and_explicit_recovery_rolls_back(run, monkeypatch):
    path, before = run
    interrupt_identity(run, monkeypatch)
    with pytest.raises(bootstrap.runner.Refused, match="recover"):
        bootstrap.checked(path)
    assert bootstrap.recover(path)["prepareRequired"] is True
    assert bootstrap.checked(path)[1] == before


@pytest.mark.parametrize("field", ["after", "ownershipAfter", "runId"])
def test_tampered_recovery_retains_quarantine(run, monkeypatch, field):
    path, _ = run
    interrupt_identity(run, monkeypatch)
    pending_path = path.parent / bootstrap.PENDING
    pending = json.loads(pending_path.read_bytes())
    if field == "after":
        changed = json.loads(pending[field])
        changed["expiresAt"] += 86400
        pending[field] = bootstrap.encoded(changed).decode()
    elif field == "ownershipAfter":
        pending[field] = json.dumps({"runId": pending["runId"], "manifestSha256": "0" * 64})
    else:
        pending[field] = "foreign"
    bootstrap.atomic_bytes(pending_path, bootstrap.encoded(pending))
    with pytest.raises(bootstrap.runner.Refused):
        bootstrap.recover(path)
    assert pending_path.exists()


def test_recovery_cannot_extend_expired_lifetime(run, monkeypatch):
    path, before = run
    interrupt_identity(run, monkeypatch)
    monkeypatch.setattr(bootstrap.time, "time", lambda: before["expiresAt"] + 1)
    with pytest.raises(bootstrap.runner.Refused, match="expired"):
        bootstrap.recover(path)
    assert (path.parent / bootstrap.PENDING).exists()


def test_existing_exclusive_lock_rejects_another_run(run):
    with bootstrap.exclusive():
        with pytest.raises(BlockingIOError):
            with bootstrap.exclusive():
                pytest.fail("concurrent fixture owner admitted")


def test_atomic_private_output_refuses_symlinks_and_oversize(run, tmp_path):
    (tmp_path / "alias").symlink_to(tmp_path / "environment.json")
    for target, payload in ((tmp_path / "alias", b"no"), (tmp_path / "large", b"x" * 65537)):
        with pytest.raises(bootstrap.runner.Refused):
            bootstrap.atomic_bytes(target, payload)


def test_owned_short_process_exits_and_records_finite_diagnostics(tmp_path):
    result = bootstrap.bounded_process([sys.executable, "-c", "print('structural fixture')"],
        tmp_path / "browser-fixture.log", seconds=4)
    assert result["exitCode"] == 0 and result["processStopped"]
    assert result["logBytes"] > 0 and result["peakRssBytes"] < bootstrap.MAX_RSS
    assert (tmp_path / "browser-fixture.log").stat().st_mode & 0o777 == 0o600


def test_nonzero_exit_is_not_a_success(tmp_path):
    with pytest.raises(bootstrap.runner.Refused, match="failed"):
        bootstrap.bounded_process([sys.executable, "-c", "raise SystemExit(9)"],
            tmp_path / "browser-failure.log", seconds=3)


def test_supervised_evidence_inherits_private_umask(tmp_path):
    artifact = tmp_path / "synthetic-evidence.xml"
    code = f"from pathlib import Path; Path({str(artifact)!r}).write_text('<testsuite/>')"
    previous = os.umask(0o022)
    try:
        bootstrap.bounded_process([sys.executable, "-c", code],
            tmp_path / "browser-umask.log", seconds=3)
    finally:
        os.umask(previous)
    assert artifact.stat().st_mode & 0o777 == 0o600


def test_deadline_stops_owned_server_and_does_not_replace_it(tmp_path):
    result = bootstrap.bounded_process([sys.executable, "-c", "import time; time.sleep(30)"],
        tmp_path / "browser-server.log", seconds=0.5, expect_running=True)
    assert result["reason"] == "deadline" and result["processStopped"]
    assert result["elapsedSeconds"] < 4


def test_external_sigterm_stops_supervisor_child_before_deadline(tmp_path):
    """Signal the actual wrapper PID, not an enclosing terminal/shell PID."""
    marker = tmp_path / "child.pid"
    code = (
        "import os,time; from pathlib import Path; "
        f"Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    wrapper = (
        "from pathlib import Path; from scripts.prepare_docsuri_u2_browser import bounded_process; "
        f"bounded_process({[sys.executable, '-c', code]!r}, "
        f"Path({str(tmp_path / 'browser-interrupted.log')!r}), seconds=30, expect_running=True)"
    )
    process = subprocess.Popen([sys.executable, "-c", wrapper], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    started = time.monotonic()
    try:
        while not marker.exists() and time.monotonic() - started < 5:
            time.sleep(0.02)
        assert marker.exists()
        child_pid = int(marker.read_text())
        os.kill(process.pid, signal.SIGTERM)
        assert process.wait(timeout=7) != 0
        assert time.monotonic() - started < 10
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def test_rss_overrun_is_a_failed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "process_rss", lambda *args: bootstrap.MAX_RSS + 1)
    with pytest.raises(bootstrap.runner.Refused, match="RSS"):
        bootstrap.bounded_process([sys.executable, "-c", "import time; time.sleep(30)"],
            tmp_path / "browser-memory.log", seconds=1)


def test_logs_are_capped_across_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "MAX_LOG", 1000)
    log = tmp_path / "browser-existing.log"
    log.write_bytes(b"x" * 900)
    log.chmod(0o600)
    with pytest.raises(bootstrap.runner.Refused, match="16 MiB"):
        bootstrap.bounded_process([sys.executable, "-c", "print('x'*300)"],
            tmp_path / "browser-overflow.log", seconds=2)
    assert sum(path.stat().st_size for path in tmp_path.glob("browser-*.log")) <= 1000


def test_prepare_verifies_frozen_offline_tool_and_updates_only_identity(run, tmp_path, monkeypatch):
    path, before = run
    store = tmp_path / "store"
    store.mkdir()
    calls = []
    monkeypatch.setattr(bootstrap, "bounded_process", lambda args, log: calls.append(args) or {"exitCode": 0})
    monkeypatch.setattr(bootstrap.runner, "LOCKS", ("frontend/pnpm-lock.yaml",))
    monkeypatch.setattr(bootstrap.runner, "digest", lambda path: "new")
    monkeypatch.setattr(bootstrap.runner, "source_identity", lambda: {"sha256": "tree"})
    monkeypatch.setattr(bootstrap.runner, "require", lambda args, **kwargs: SimpleNamespace(stdout="9.15.9" if "--version" in args else "head"))
    result = bootstrap.prepare(path, store)
    assert result["state"] == "dependencies-reconciled"
    assert all(flag in calls[0] for flag in ("pnpm@9.15.9", "--frozen-lockfile", "--offline", "--ignore-scripts"))
    assert calls[0][-1] == str(store)
    assert bootstrap.checked(path)[1]["expiresAt"] == before["expiresAt"]


def test_python_lock_drift_is_not_certified_by_node_install(run, tmp_path, monkeypatch):
    path, _ = run
    monkeypatch.setattr(bootstrap.runner, "LOCKS", ("backend/uv.lock",))
    monkeypatch.setattr(bootstrap.runner, "digest", lambda path: "new")
    with pytest.raises(bootstrap.runner.Refused, match="Python dependency"):
        bootstrap.prepare(path, tmp_path)


def test_serve_refuses_unreconciled_dependencies(run, monkeypatch):
    path, _ = run
    monkeypatch.setattr(bootstrap.runner, "LOCKS", ("frontend/pnpm-lock.yaml",))
    monkeypatch.setattr(bootstrap.runner, "digest", lambda path: "new")
    with pytest.raises(bootstrap.runner.Refused, match="prepare"):
        bootstrap.serve(path, 300)


def test_process_bounds_cannot_be_disabled(tmp_path):
    for seconds in (0, 301):
        with pytest.raises(bootstrap.runner.Refused, match="finite"):
            bootstrap.bounded_process([sys.executable, "-c", "pass"], tmp_path / "not-created", seconds=seconds)
    assert not (tmp_path / "not-created").exists()


def test_process_table_deadline_and_nonzero_command_fail_closed(monkeypatch):
    with pytest.raises(bootstrap.runner.Refused, match="deadline"):
        bootstrap.process_rss(os.getpid(), time.monotonic() - 1)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "ps")))
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap.process_rss(os.getpid(), time.monotonic() + 1)
