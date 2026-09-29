"""The root-bootstrap repair is limited to pinned clock jobs and preserves failure barriers."""

import importlib.util
import plistlib
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity/repair_clock_groups.py"
ROOT = "/Library/Application Support/DocSuri/rem-1-test"
DIGEST = "sha256:ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26"


@pytest.fixture
def repair_tool():
    spec = importlib.util.spec_from_file_location("clock_group_repair", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def original_plist(name):
    result = {
        "Label": "org.docsuri.rem1.test." + name,
        "UserName": "_docsuri_r1t_clock", "GroupName": "_docsuri_r1t_clock",
        "InitGroups": False,
        "ProgramArguments": ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "LANG=en_US.UTF-8",
                             "HOME=/var/empty", ROOT + "/toolchains/r1t-clock-20260927/runtime/bin/"
                             "python3.13", "-I", "-m",
                             "docsuri_platform_integrity.deployment.launchd", "exec", "--profile",
                             "test", "--entry", name, "--manifest-digest", DIGEST],
        "Umask": 0o077, "WorkingDirectory": ROOT + "/clock", "KeepAlive": False,
        "RunAtLoad": name == "nts-observer", "ExitTimeOut": 5, "ThrottleInterval": 5,
        "ProcessType": "Background", "SoftResourceLimits": {"NumberOfFiles": 256, "Core": 0},
        "HardResourceLimits": {"NumberOfFiles": 256, "Core": 0},
    }
    if name == "clock-sample":
        result["StartInterval"] = 5
    return plistlib.dumps(result, sort_keys=True)


@pytest.mark.parametrize("name", ["nts-observer", "clock-sample"])
def test_repair_changes_only_bootstrap_identity_and_bytecode_flag(repair_tool, name):
    before = original_plist(name)
    assert repair_tool.sha(before) == repair_tool.PREIMAGES[name]
    after = repair_tool.repaired_plist(name, before)
    result = plistlib.loads(after)
    assert result["UserName"] == "root" and result["GroupName"] == "wheel"
    assert result["ProgramArguments"][6:10] == ["-I", "-B", "-m",
                                              "docsuri_platform_integrity.deployment.launchd"]
    result["UserName"] = result["GroupName"] = "_docsuri_r1t_clock"
    del result["ProgramArguments"][7]
    assert result == plistlib.loads(before)
    assert repair_tool.repaired_plist(name, after) == after


@pytest.mark.parametrize("change", ["executable", "environment", "partial"])
def test_repair_rejects_foreign_or_partially_modified_launches(repair_tool, change):
    value = plistlib.loads(original_plist("nts-observer"))
    if change == "executable":
        value["ProgramArguments"][5] = "/unreviewed/python"
    elif change == "environment":
        value["EnvironmentVariables"] = {"DYLD_INSERT_LIBRARIES": "/unreviewed.dylib"}
    else:
        value["UserName"] = "root"
    with pytest.raises(ValueError):
        repair_tool.repaired_plist("nts-observer", plistlib.dumps(value))


@settings(max_examples=2000, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(name=st.sampled_from(["nts-observer", "clock-sample"]),
       field=st.sampled_from(["Label", "WorkingDirectory", "ProcessType"]),
       suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=30))
def test_property_repair_cannot_retarget_a_pinned_job(repair_tool, name, field, suffix):
    value = plistlib.loads(original_plist(name))
    value[field] += suffix
    with pytest.raises(ValueError, match="unrecognized"):
        repair_tool.repaired_plist(name, plistlib.dumps(value))


@pytest.fixture
def prepared(repair_tool, tmp_path, monkeypatch):
    entries = []
    for name in repair_tool.PREIMAGES:
        path = tmp_path / (name + ".plist")
        before = original_plist(name)
        path.write_bytes(before)
        entries.append(("org.docsuri.rem1.test." + name, path, before,
                        repair_tool.repaired_plist(name, before)))
    (tmp_path / "clock-public").mkdir()
    (tmp_path / "clock-public/current.json").write_bytes(b"old sample")
    monkeypatch.setattr(repair_tool, "ROOT", tmp_path)
    monkeypatch.setattr(repair_tool, "prepare", lambda *args: entries)
    monkeypatch.setattr(repair_tool, "require_operator", lambda: None)
    monkeypatch.setattr(repair_tool, "protected_path", lambda path: None)
    return entries


def test_plan_only_never_changes_launch_state(repair_tool, prepared, tmp_path, monkeypatch):
    monkeypatch.setattr(repair_tool, "launchctl", lambda *a, **k: pytest.fail("plan launched"))
    result = repair_tool.repair(tmp_path, tmp_path / "provisioner")
    assert result["state"] == "PLAN_ONLY" and result["accepted"] is False
    assert (tmp_path / "clock-public/current.json").exists()
    assert all(path.read_bytes() == before for _, path, before, _ in prepared)


def test_repair_stops_both_jobs_before_writes_and_bootstraps_after(repair_tool, prepared,
                                                                tmp_path, monkeypatch):
    events = []
    original_replace = repair_tool.replace_plist

    def replace(path, before, after):
        events.append("write")
        original_replace(path, before, after)

    monkeypatch.setattr(repair_tool, "replace_plist", replace)
    monkeypatch.setattr(repair_tool, "launchctl", lambda *a, **k: events.append(a[0]))
    assert repair_tool.repair(tmp_path, tmp_path / "provisioner", apply=True)["state"] == \
        "REPAIRED_NOT_ACCEPTED"
    assert events == ["bootout", "bootout", "write", "write", "bootstrap", "bootstrap",
                      "print", "print"]
    assert not (tmp_path / "clock-public/current.json").exists()
    assert all(path.read_bytes() == after for _, path, _, after in prepared)


def test_preflight_failure_has_no_launch_or_file_effects(
    repair_tool, prepared, tmp_path, monkeypatch,
):
    def reject(*args):
        raise ValueError("unverified candidate")

    monkeypatch.setattr(repair_tool, "prepare", reject)
    monkeypatch.setattr(repair_tool, "launchctl", lambda *a, **k: pytest.fail("preflight launched"))
    with pytest.raises(ValueError, match="unverified"):
        repair_tool.repair(tmp_path, tmp_path / "provisioner", apply=True)
    assert all(path.read_bytes() == before for _, path, before, _ in prepared)


@pytest.mark.parametrize("failed_job", ["nts-observer", "clock-sample"])
@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_bootstrap_failure_stops_all_jobs_even_without_an_acknowledgement(
    repair_tool, prepared, tmp_path, monkeypatch, failed_job, failure,
):
    calls = []

    def launchctl(*args, **kwargs):
        calls.append(args)
        if args[0] == "bootstrap" and args[-1].endswith(failed_job + ".plist"):
            raise failure("bootstrap unavailable")

    monkeypatch.setattr(repair_tool, "launchctl", launchctl)
    with pytest.raises(failure, match="bootstrap unavailable"):
        repair_tool.repair(tmp_path, tmp_path / "provisioner", apply=True)
    assert calls[-2:] == [("bootout", "system/org.docsuri.rem1.test.nts-observer"),
                         ("bootout", "system/org.docsuri.rem1.test.clock-sample")]


def test_unprivileged_apply_is_refused_before_preflight(repair_tool, tmp_path, monkeypatch):
    monkeypatch.setattr(repair_tool.os, "geteuid", lambda: 501)
    monkeypatch.setattr(repair_tool, "prepare", lambda *a: pytest.fail("unprivileged preflight"))
    with pytest.raises(PermissionError, match="root execution"):
        repair_tool.repair(tmp_path, tmp_path / "provisioner", apply=True)


def test_repair_operator_script_parses_on_system_python_39():
    import ast

    ast.parse(SCRIPT.read_text(), feature_version=(3, 9))
