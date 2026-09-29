"""Validate existing native identities without changing system accounts in tests."""

import os
import plistlib
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops/platform-integrity/provision_test_realm.py"
NAME = "_docsuri_r1t_reader"


@pytest.mark.parametrize("attribute,value", [
    ("UserShell", "/bin/zsh"), ("PrimaryGroupID", "20"), ("NFSHomeDirectory", "/Users/operator"),
    ("IsHidden", "0"),
])
def test_existing_identity_with_unexpected_attributes_is_rejected(monkeypatch, attribute, value):
    module = runpy.run_path(str(SCRIPT))
    validate = module["validate_existing_identity"]
    attributes = {"UniqueID": ["700"], "PrimaryGroupID": ["700"],
                  "UserShell": ["/usr/bin/false"], "NFSHomeDirectory": ["/var/empty"],
                  "IsHidden": ["1"]}
    attributes[attribute] = [value]
    monkeypatch.setitem(validate.__globals__, "command",
                        lambda *args: plistlib.dumps(attributes).decode())
    with pytest.raises(RuntimeError):
        validate(NAME, 700, {NAME: "700"}, {NAME: "700"})


def test_aliased_native_uid_is_not_adopted():
    validate = runpy.run_path(str(SCRIPT))["validate_existing_identity"]
    with pytest.raises(RuntimeError):
        validate(NAME, 700, {NAME: "700", "unrelated": "700"}, {NAME: "700"})


def test_matching_identity_requires_no_supplementary_privileges(monkeypatch):
    validate = runpy.run_path(str(SCRIPT))["validate_existing_identity"]
    attributes = {"UniqueID": ["700"], "PrimaryGroupID": ["700"],
                  "UserShell": ["/usr/bin/false"], "NFSHomeDirectory": ["/var/empty"],
                  "IsHidden": ["1"]}
    memberships = "700"

    def command(*args):
        if args[0] == "/usr/bin/id":
            return memberships
        return plistlib.dumps(attributes).decode()

    monkeypatch.setitem(validate.__globals__, "command", command)
    validate(NAME, 700, {NAME: "700"}, {NAME: "700"})
    memberships = "700 80"
    with pytest.raises(RuntimeError):
        validate(NAME, 700, {NAME: "700"}, {NAME: "700"})


def test_real_macos_native_hidden_attribute_is_supported(monkeypatch):
    validate = runpy.run_path(str(SCRIPT))["validate_existing_identity"]
    attributes = {"dsAttrTypeStandard:UniqueID": ["700"],
                  "dsAttrTypeStandard:PrimaryGroupID": ["700"],
                  "dsAttrTypeStandard:UserShell": ["/usr/bin/false"],
                  "dsAttrTypeStandard:NFSHomeDirectory": ["/var/empty"],
                  "dsAttrTypeNative:IsHidden": ["1"]}
    monkeypatch.setitem(validate.__globals__, "command", lambda *args: (
        "700" if args[0] == "/usr/bin/id" else plistlib.dumps(attributes).decode()
    ))
    validate(NAME, 700, {NAME: "700"}, {NAME: "700"})


def test_conflicting_directory_attribute_namespaces_are_rejected(monkeypatch):
    validate = runpy.run_path(str(SCRIPT))["validate_existing_identity"]
    attributes = {"UniqueID": ["700"], "PrimaryGroupID": ["700"],
                  "UserShell": ["/usr/bin/false"], "NFSHomeDirectory": ["/var/empty"],
                  "IsHidden": ["1"], "dsAttrTypeNative:IsHidden": ["0"]}
    monkeypatch.setitem(validate.__globals__, "command", lambda *args: (
        "700" if args[0] == "/usr/bin/id" else plistlib.dumps(attributes).decode()
    ))
    with pytest.raises(RuntimeError):
        validate(NAME, 700, {NAME: "700"}, {NAME: "700"})


def worker():
    namespace = {"__name__": "native_probe_test"}
    exec(runpy.run_path(str(SCRIPT))["PROBE_PROGRAM"], namespace)
    return namespace["probe_access"]


def fixture_payload(tmp_path):
    own = tmp_path / "own"
    own.write_text("synthetic-fixture")
    return {"uid": os.getuid(), "gid": os.getgid(), "token": "synthetic-fixture",
            "own": str(own), "others": [], "groupFiles": []}


def test_probe_refuses_ambient_groups_before_file_access(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    probe = worker()
    monkeypatch.setitem(probe.__globals__, "process_groups", lambda: [payload["gid"] + 1000])
    with pytest.raises(PermissionError, match="effective_groups"):
        probe(payload)
    assert (tmp_path / "own").read_text() == "synthetic-fixture"


def test_probe_does_not_count_missing_files_as_access_denials(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    payload["others"] = [str(tmp_path / "missing")]
    probe = worker()
    monkeypatch.setitem(probe.__globals__, "process_groups", lambda: [])
    with pytest.raises(FileNotFoundError):
        probe(payload)


def test_probe_detects_cross_role_access_instead_of_reporting_pass(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.write_text("synthetic-other-role")
    payload["others"] = [str(foreign)]
    probe = worker()
    monkeypatch.setitem(probe.__globals__, "process_groups", lambda: [])
    with pytest.raises(PermissionError, match="cross_role_access"):
        probe(payload)


def test_probe_checks_own_roundtrip(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    probe = worker()
    monkeypatch.setitem(probe.__globals__, "process_groups", lambda: [])
    result = probe(payload)
    assert result["ownReadWrite"] is True
    assert (tmp_path / "own").read_text() == "synthetic-fixture:verified"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS group ABI")
def test_kernel_group_query_does_not_use_python_directory_membership(monkeypatch):
    def wrong_api():
        pytest.fail("os.getgroups is directory membership on modern macOS CPython")

    monkeypatch.setattr(os, "getgroups", wrong_api)
    groups = worker().__globals__["process_groups"]()
    assert isinstance(groups, list) and len(groups) <= 256
    assert all(type(value) is int for value in groups)


def test_probe_rejects_fifo_fixture_without_blocking(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    (tmp_path / "own").unlink()
    os.mkfifo(tmp_path / "own")
    probe = worker()
    monkeypatch.setitem(probe.__globals__, "process_groups", lambda: [])
    with pytest.raises(ValueError, match="fixture_not_regular"):
        probe(payload)


def test_probe_refuses_non_root_before_creating_fixtures(monkeypatch):
    probe = runpy.run_path(str(SCRIPT))["probe_roles"]
    monkeypatch.setattr(probe.__globals__["platform"], "system", lambda: "Darwin")
    monkeypatch.setattr(os, "geteuid", lambda: 501)
    with pytest.raises(PermissionError, match="operator root"):
        probe()


def test_probe_refuses_privileged_execution_from_mutable_checkout(monkeypatch):
    if os.getuid() == 0:
        pytest.skip("requires a non-root-owned checkout")
    probe = runpy.run_path(str(SCRIPT))["probe_roles"]
    monkeypatch.setattr(probe.__globals__["platform"], "system", lambda: "Darwin")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(PermissionError, match="protected script"):
        probe()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS executable image API")
def test_interpreter_selection_observes_kernel_image():
    image = runpy.run_path(str(SCRIPT))["current_interpreter"]()
    assert image.is_absolute() and image.is_file() and os.access(image, os.X_OK)


def test_progress_parser_retains_only_known_stage_codes():
    parse = runpy.run_path(str(SCRIPT))["worker_stages"]
    stderr = b"secret\nR1PROBE:worker_entered\nR1PROBE:password=secret\nR1PROBE:input_ready\n"
    assert parse(stderr) == ["worker_entered", "input_ready"]
    assert parse(None) == []


def unprivileged_launcher(monkeypatch, program):
    launch = runpy.run_path(str(SCRIPT))["run_probe_worker"]
    original = subprocess.Popen

    def popen(*args, **kwargs):
        # Exercise real pipes/deadlines/reaping without switching host identities in unit tests.
        for name in ("user", "group", "extra_groups"):
            kwargs.pop(name)
        return original(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setitem(launch.__globals__, "PROBE_PROGRAM", program)
    return launch


def test_worker_communication_closes_stdin_and_keeps_progress(monkeypatch):
    launch = unprivileged_launcher(monkeypatch, """
import json, sys
sys.stderr.write('R1PROBE:worker_entered\\n'); sys.stderr.flush()
payload = json.load(sys.stdin)
sys.stderr.write('R1PROBE:input_ready\\n'); sys.stderr.flush()
print(json.dumps(payload))
""")
    result = launch(Path(sys.executable), {"uid": os.getuid(), "gid": os.getgid()}, timeout=5)
    assert result["returncode"] == 0 and result["timedOut"] is False
    assert result["lastStage"] == "input_ready" and result["parentReaped"] is True


def test_timeout_preserves_phase_and_reaps_worker(monkeypatch):
    launch = unprivileged_launcher(monkeypatch, """
import sys, time
sys.stderr.write('R1PROBE:worker_entered\\n'); sys.stderr.flush()
time.sleep(30)
""")
    result = launch(Path(sys.executable), {"uid": os.getuid(), "gid": os.getgid()}, timeout=2)
    assert result["timedOut"] is True and result["parentReaped"] is True
    assert result["lastStage"] == "worker_entered"
    assert result["cleanup"] == "process_group_killed"


def test_timeout_reaps_pipe_holding_descendant(monkeypatch):
    launch = unprivileged_launcher(monkeypatch, """
import subprocess, sys
subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'])
sys.stderr.write('R1PROBE:worker_entered\\n'); sys.stderr.flush()
""")
    result = launch(Path(sys.executable), {"uid": os.getuid(), "gid": os.getgid()}, timeout=2)
    assert result["timedOut"] is True and result["parentReaped"] is True
    assert result["cleanup"] == "process_group_killed"


def test_missing_worker_marker_is_distinct_from_file_probe_timeout(monkeypatch):
    launch = unprivileged_launcher(monkeypatch, "import time; time.sleep(30)")
    result = launch(Path(sys.executable), {"uid": os.getuid(), "gid": os.getgid()}, timeout=1)
    assert result["timedOut"] is True and result["lastStage"] == "before_worker_code"
