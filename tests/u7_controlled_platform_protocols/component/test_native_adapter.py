from __future__ import annotations

import errno
import io
import json
import os
from pathlib import Path

import pytest

from docsuri_ops.platform_control import native_adapter

pytestmark = pytest.mark.u7_component

TOKEN = "0123456789abcdef"


def request(root: Path, *, kind="file-write", target="t-1", token=TOKEN, **extra) -> dict:
    payload = {
        "operationId": "op-1",
        "operationName": "platform.file.write",
        "targetId": target,
        "token": token,
        "effectKind": kind,
        "inputHash": "a" * 64,
        "targetRoot": str(root),
    }
    payload.update(extra)
    return payload


class _Input:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def run_main(monkeypatch, data: bytes) -> tuple[int, str]:
    out = io.StringIO()
    monkeypatch.setattr(native_adapter.sys, "stdin", _Input(data))
    monkeypatch.setattr(native_adapter.sys, "stdout", out)
    code = native_adapter.main([])
    return code, out.getvalue()


# --- resolved path and input safety ----------------------------------------


@pytest.mark.parametrize(
    "target,token",
    [("bad/target", TOKEN), ("t-1", "not-a-token"), ("../escape", TOKEN)],
)
def test_invalid_target_or_token_never_touches_the_filesystem(tmp_path, target, token):
    result = native_adapter.apply_effect(request(tmp_path, target=target, token=token))
    assert result["status"] == "not-applied"
    assert result["effectRefs"] == []


def test_unknown_effect_kind_is_refused(tmp_path):
    result = native_adapter.apply_effect(request(tmp_path, kind="shell"))
    assert result["status"] == "not-applied"
    assert result["error"]["kind"] == "internal"


def test_unknown_injected_fault_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        native_adapter.apply_effect(request(tmp_path), injected_fault="nonsense")


# --- file-write -------------------------------------------------------------


def test_file_write_creates_the_target_directory_and_effect(tmp_path):
    result = native_adapter.apply_effect(request(tmp_path, target="fresh"))
    assert result["status"] == "applied"
    assert (tmp_path / result["effectRefs"][0]).is_file()


def test_file_write_into_an_unwritable_location_is_not_applied(tmp_path, monkeypatch):
    def denied(self, *args, **kwargs):
        raise OSError(errno.EACCES, "denied")

    monkeypatch.setattr(native_adapter.Path, "mkdir", denied)
    result = native_adapter.apply_effect(request(tmp_path))
    assert result["status"] == "not-applied"
    assert result["error"]["kind"] == "permission"


def test_file_write_disk_exhaustion_is_unknown_not_completed(tmp_path, monkeypatch):
    def no_space(*args, **kwargs):
        raise OSError(errno.ENOSPC, "no space")

    monkeypatch.setattr(native_adapter.os, "write", no_space)
    result = native_adapter.apply_effect(request(tmp_path))
    assert result["status"] == "unknown"
    assert result["status"] != "applied"
    assert result["error"]["kind"] == "disk"


# --- file-probe (read-only) -------------------------------------------------


def test_probe_does_not_create_the_target_directory(tmp_path):
    result = native_adapter.apply_effect(request(tmp_path, kind="file-probe", target="absent"))
    assert result["status"] == "not-applied"
    assert not (tmp_path / "absent").exists()


def test_probe_observes_an_existing_directory_without_writing(tmp_path):
    (tmp_path / "present").mkdir()
    result = native_adapter.apply_effect(request(tmp_path, kind="file-probe", target="present"))
    assert result["status"] == "applied"
    assert result["observations"]["entries"] == 0
    assert list((tmp_path / "present").iterdir()) == []


def test_probe_permission_failure_is_not_applied(tmp_path, monkeypatch):
    (tmp_path / "present").mkdir()

    def denied(*args, **kwargs):
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(native_adapter.os, "scandir", denied)
    result = native_adapter.apply_effect(request(tmp_path, kind="file-probe", target="present"))
    assert result["status"] == "not-applied"
    assert result["error"]["kind"] == "permission"


# --- credential-presence (real native semantics) ---------------------------


def test_credential_presence_requires_an_owner_only_non_empty_file(tmp_path):
    target = tmp_path / "creds"
    target.mkdir()
    credential = target / "credential"
    credential.write_text("secret-material")
    os.chmod(credential, 0o600)
    applied = native_adapter.apply_effect(
        request(tmp_path, kind="credential-presence", target="creds")
    )
    assert applied["status"] == "applied"
    assert applied["observations"] == {"credentialPresent": True, "mode": "0o600"}
    # weakened permissions are refused
    os.chmod(credential, 0o644)
    weakened = native_adapter.apply_effect(
        request(tmp_path, kind="credential-presence", target="creds")
    )
    assert weakened["status"] == "not-applied"
    assert weakened["error"]["kind"] == "permission"


def test_credential_presence_absent_or_empty_is_not_applied(tmp_path):
    target = tmp_path / "creds"
    target.mkdir()
    absent = native_adapter.apply_effect(
        request(tmp_path, kind="credential-presence", target="creds")
    )
    assert absent["status"] == "not-applied"
    (target / "credential").write_text("")
    os.chmod(target / "credential", 0o600)
    empty = native_adapter.apply_effect(
        request(tmp_path, kind="credential-presence", target="creds")
    )
    assert empty["status"] == "not-applied"
    assert empty["error"]["kind"] == "internal"


# --- injected faults and error classification ------------------------------


@pytest.mark.parametrize(
    "fault,status",
    [("permission", "not-applied"), ("disk", "unknown"), ("connectivity", "unknown")],
)
def test_injected_faults_are_reported_truthfully(tmp_path, fault, status):
    result = native_adapter.apply_effect(request(tmp_path), injected_fault=fault)
    assert result["status"] == status


@pytest.mark.parametrize(
    "errno_value,kind",
    [
        (errno.EACCES, "permission"),
        (errno.EROFS, "permission"),
        (errno.ENOSPC, "disk"),
        (errno.ECONNREFUSED, "connectivity"),
        (errno.EINVAL, "internal"),
    ],
)
def test_oserror_classification(errno_value, kind):
    assert native_adapter._classify_oserror(OSError(errno_value, "x")) == kind


# --- the child-process entrypoint -------------------------------------------


def test_main_emits_one_typed_record_for_a_valid_request(tmp_path, monkeypatch):
    code, out = run_main(monkeypatch, json.dumps(request(tmp_path)).encode())
    assert code == 0
    assert json.loads(out)["status"] == "applied"


def test_main_rejects_an_oversized_request(monkeypatch):
    code, out = run_main(monkeypatch, b"x" * (native_adapter.MAX_REQUEST_BYTES + 2))
    assert code == 2
    assert out == ""


def test_main_rejects_invalid_json(monkeypatch):
    code, _out = run_main(monkeypatch, b"not-json")
    assert code == 2


def test_main_reports_a_malformed_request_as_not_applied(tmp_path, monkeypatch):
    broken = request(tmp_path)
    del broken["token"]
    code, out = run_main(monkeypatch, json.dumps(broken).encode())
    assert code == 0
    assert json.loads(out)["status"] == "not-applied"


def test_main_routes_an_injected_fault(tmp_path, monkeypatch):
    payload = request(tmp_path)
    payload["injectedFault"] = "disk"
    code, out = run_main(monkeypatch, json.dumps(payload).encode())
    assert code == 0
    assert json.loads(out)["status"] == "unknown"
