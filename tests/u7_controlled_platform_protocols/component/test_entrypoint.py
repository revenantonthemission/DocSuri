"""Exercise the `python -m docsuri_ops.platform_control` entrypoint in-process.

The package entrypoint is a real code path, not an unmeasurable artefact: running
it through ``runpy`` as ``__main__`` executes it and its CLI ``main`` body, so it
is measured against the same 80% floor as every other module.
"""

from __future__ import annotations

import io
import json
import runpy

import pytest

pytestmark = pytest.mark.u7_component


class _Input:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def test_package_entrypoint_executes_and_emits_one_json_document(monkeypatch):
    out = io.StringIO()
    monkeypatch.setattr("sys.stdin", _Input(b'{"op": "status", "request": {}}'))
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.argv", ["docsuri-operator"])
    with pytest.raises(SystemExit) as exitinfo:
        runpy.run_module("docsuri_ops.platform_control", run_name="__main__")
    # no operator authority is bound to the status envelope, or the synthetic
    # environment is absent: either way the entrypoint emitted one refusal.
    assert exitinfo.value.code in (1, 2)
    document = json.loads(out.getvalue())
    assert document["ok"] is False
    assert document["error"]["code"] in {"FORBIDDEN", "DEPENDENCY_UNAVAILABLE"}


def test_package_entrypoint_rejects_a_malformed_envelope(monkeypatch):
    out = io.StringIO()
    monkeypatch.setattr("sys.stdin", _Input(b"not-json"))
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.argv", ["docsuri-operator"])
    with pytest.raises(SystemExit) as exitinfo:
        runpy.run_module("docsuri_ops.platform_control", run_name="__main__")
    assert exitinfo.value.code == 2
    assert json.loads(out.getvalue())["error"]["code"] == "INVALID_INPUT"
