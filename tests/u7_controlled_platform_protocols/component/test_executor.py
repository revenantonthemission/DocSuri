from __future__ import annotations

import json
from pathlib import Path

import pytest

from docsuri_ops.platform_control import executor, native_adapter

pytestmark = pytest.mark.u7_component

TOKEN = "0123456789abcdef"


def write_request(root: Path, token: str = TOKEN, target: str = "t-1") -> dict:
    return {
        "operationId": "op-1",
        "operationName": "platform.file.write",
        "targetId": target,
        "token": token,
        "effectKind": "file-write",
        "inputHash": "a" * 64,
        "targetRoot": str(root),
    }


def test_file_write_applies_and_leaves_a_real_effect(tmp_path):
    result = native_adapter.apply_effect(write_request(tmp_path))
    assert result["status"] == "applied"
    reference = result["effectRefs"][0]
    written = tmp_path / reference
    assert written.is_file()
    assert json.loads(written.read_text())["targetId"] == "t-1"


def test_file_write_is_the_only_signal_never_the_exit_status(tmp_path):
    outcome = executor.run_effect(
        target_root=tmp_path,
        operation_id="op-1",
        operation_name="platform.file.write",
        target_id="t-1",
        token=TOKEN,
        effect_kind="file-write",
        input_hash="a" * 64,
        deadline_seconds=20,
    )
    assert outcome.status == "applied"
    assert outcome.as_receipt_fields() == ("completed", "applied", outcome.effect_refs)
    assert (tmp_path / outcome.effect_refs[0]).is_file()


@pytest.mark.parametrize(
    "fault,status,outcome",
    [
        ("permission", "not-applied", "failed"),
        ("disk", "unknown", "unknown"),
        ("connectivity", "unknown", "unknown"),
    ],
)
def test_injected_failures_never_settle_completed(tmp_path, fault, status, outcome):
    result = executor.run_effect(
        target_root=tmp_path,
        operation_id="op-x",
        operation_name="platform.file.write",
        target_id="t-1",
        token=TOKEN,
        effect_kind="file-write",
        input_hash="a" * 64,
        deadline_seconds=20,
        injected_fault=fault,
    )
    assert result.status == status
    assert result.as_receipt_fields()[0] == outcome
    assert result.as_receipt_fields()[0] != "completed"


def test_deadline_kills_a_hanging_effect_and_settles_unknown(tmp_path):
    result = executor.run_effect(
        target_root=tmp_path,
        operation_id="op-hang",
        operation_name="platform.file.write",
        target_id="t-1",
        token=TOKEN,
        effect_kind="file-write",
        input_hash="a" * 64,
        deadline_seconds=1,
        injected_fault="hang",
    )
    assert result.status == "unknown"
    assert result.reason == "deadline exceeded"
    assert result.as_receipt_fields()[0] == "unknown"


def test_target_traversal_is_refused_with_no_effect(tmp_path):
    result = native_adapter.apply_effect(write_request(tmp_path, target="../escape"))
    assert result["status"] == "not-applied"
    assert not (tmp_path.parent / "escape").exists()


def test_bad_token_is_refused_with_no_effect(tmp_path):
    result = native_adapter.apply_effect(write_request(tmp_path, token="not-a-token"))
    assert result["status"] == "not-applied"
    assert result["effectRefs"] == []


def test_probe_is_read_only_and_creates_no_effect_file(tmp_path):
    request = write_request(tmp_path)
    request["effectKind"] = "file-probe"
    (tmp_path / "t-1").mkdir()
    result = native_adapter.apply_effect(request)
    assert result["status"] == "applied"
    assert list((tmp_path / "t-1").glob("effect-*.json")) == []


def test_executor_unavailable_host_settles_unknown(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no fork")

    monkeypatch.setattr(executor.subprocess, "Popen", boom)
    result = executor.run_effect(
        target_root=tmp_path,
        operation_id="op",
        operation_name="platform.file.write",
        target_id="t-1",
        token=TOKEN,
        effect_kind="file-write",
        input_hash="a" * 64,
        deadline_seconds=5,
    )
    assert result.status == "unknown"
