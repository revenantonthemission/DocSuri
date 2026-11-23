"""U7's parts keep their built behaviour after U8's code left U7's package (U8 plan Step 44;
the person's decision of 2026-10-25, "Move U8's code out of U7").

U7's package holds its built files and two seams, each defaulting to U7's built
behaviour: `executor.run_effect`'s `adapter_module` (U7's `native_adapter`; a name
outside `docsuri_ops` is refused before a child starts) and `native_adapter.main`'s
`effect` (U7's `apply_effect`, looked up when called). Beside them, `run_effect` keeps one
name more in its child's environment, DOCKER_HOST, when it is set (L1-78). These tests
need no database.
"""

from __future__ import annotations

import io
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from docsuri_ops.platform_control import cli, enums, executor, native_adapter, profile
from docsuri_ops.platform_control.inventory import _INVENTORY_PATH, load_inventory
from docsuri_ops.u8_platform.effect_kinds import U8_EFFECT_KINDS

TOKEN = secrets.token_hex(8)  # sixteen hex digits, generated per run (L1-36)
U7_MODULES = ("authority", "cli", "enums", "errors", "evidence", "executor", "inventory",
              "native_adapter", "observations", "profile", "reconciler", "store")
MOVED_NAMES = ("U8PlatformProfile", "ReaderBinding", "PRODUCTION_LABELS", "V1_LABELS",
               "REALM_LABELS", "TUNNEL_ORIGINS", "PRODUCTION_STORE_LOGINS", "READER_FILE",
               "STORE_AMENDMENT", "U8_REALM_RUN", "U8_REALM_DATABASE", "U8_PRODUCTION_DATABASE",
               "U8_PRODUCTION_PORT", "U8_PRODUCTION_CONTROL", "U8_PRODUCTION_PROFILE",
               "U8_EFFECT_KINDS", "U7_EFFECT_KINDS", "_driver_effect", "_login_store")


class Child:
    """A stand-in bounded child that settles applied."""

    returncode = 0

    def communicate(self, payload=None, timeout=None):
        return json.dumps({"status": "applied", "effectRefs": ["t-1/x"]}).encode(), b""


def request_options(root: Path, **extra) -> dict:
    return {"target_root": root, "operation_id": "op-1", "operation_name": "platform.file.write",
            "target_id": "t-1", "token": TOKEN, "effect_kind": "file-write",
            "input_hash": "a" * 64, "deadline_seconds": 20, **extra}


@pytest.fixture
def started(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def popen(argv, **options):
        calls.append(list(argv))
        return Child()

    monkeypatch.setattr(executor.subprocess, "Popen", popen)
    return calls


@pytest.fixture
def started_with_environment(monkeypatch) -> list[tuple[list[str], dict]]:
    """Each bounded child's argv and the `env` it is handed; each settles applied."""
    calls: list[tuple[list[str], dict]] = []

    def popen(argv, **options):
        calls.append((list(argv), dict(options["env"])))
        return Child()

    monkeypatch.setattr(executor.subprocess, "Popen", popen)
    return calls


@pytest.mark.parametrize("module", [None, "docsuri_ops.u8_platform.adapter"])
def test_the_executor_hands_its_child_docker_host_only_when_it_is_set(
        tmp_path, monkeypatch, started_with_environment, module):
    socket = f"unix://{tmp_path}/docker-{secrets.token_hex(4)}.sock"
    for name in ("DATABASE_URL", "OPENAI_API_KEY", "DOCKER_CONFIG"):
        monkeypatch.setenv(name, f"planted-{secrets.token_hex(8)}")
    built = {name: os.environ[name] for name in ("PATH", "LANG", "LC_ALL", "TMPDIR")
             if name in os.environ}
    options = {} if module is None else {"adapter_module": module}
    expected_module = module or "docsuri_ops.platform_control.native_adapter"

    monkeypatch.setenv("DOCKER_HOST", socket)
    assert executor.run_effect(**request_options(tmp_path, **options)).status == "applied"
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    assert executor.run_effect(**request_options(tmp_path, **options)).status == "applied"

    (set_argv, set_env), (unset_argv, unset_env) = started_with_environment
    assert set_argv == unset_argv == [sys.executable, "-m", expected_module]
    assert set_env == {**built, "DOCKER_HOST": socket}
    assert unset_env == built
    assert executor.run_effect(**request_options(
        tmp_path, adapter_module="os")).status == "not-applied"
    assert len(started_with_environment) == 2


def test_the_executor_starts_u7s_native_adapter_by_default(tmp_path, started):
    outcome = executor.run_effect(**request_options(tmp_path))
    assert outcome.status == "applied"
    assert started == [[sys.executable, "-m", "docsuri_ops.platform_control.native_adapter"]]
    assert executor.NATIVE_ADAPTER == "docsuri_ops.platform_control.native_adapter"


def test_a_named_docsuri_ops_module_is_the_child(tmp_path, started):
    executor.run_effect(
        **request_options(tmp_path, adapter_module="docsuri_ops.u8_platform.adapter")
    )
    assert started == [[sys.executable, "-m", "docsuri_ops.u8_platform.adapter"]]


@pytest.mark.parametrize("name", ["os", "-c", "docsuri_ops", "docsuri_ops.", "docsuri_ops..x",
                                  "docsuri_opsx.adapter", "docsuri_ops.Adapter",
                                  "docsuri_ops.adapter; rm", "", None])
def test_any_other_child_is_refused_before_one_starts(tmp_path, started, name):
    outcome = executor.run_effect(**request_options(tmp_path, adapter_module=name))
    assert outcome.status == "not-applied"
    assert outcome.error == {"kind": "internal", "message": "bounded child outside docsuri_ops"}
    assert outcome.as_receipt_fields() == ("failed", "not-applied", [])
    assert started == []


def run_main(monkeypatch, request: dict, **options) -> tuple[int, dict]:
    stdin = io.TextIOWrapper(io.BytesIO(json.dumps(request).encode()))
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    status = native_adapter.main(**options)
    return status, json.loads(stdout.getvalue())


def test_main_runs_u7s_apply_effect_looked_up_when_called(monkeypatch):
    seen = []

    def planted(request, *, injected_fault=None):
        seen.append((request["effectKind"], injected_fault))
        return {"status": "applied", "effectRefs": ["planted"], "error": None}

    monkeypatch.setattr(native_adapter, "apply_effect", planted)
    status, result = run_main(monkeypatch, {"effectKind": "file-probe", "injectedFault": "disk"})
    assert status == 0 and result["effectRefs"] == ["planted"]
    assert seen == [("file-probe", "disk")]


def test_main_runs_the_effect_a_caller_passes(monkeypatch):
    def own(request, *, injected_fault=None):
        return {"status": "not-applied", "effectRefs": [], "error": {"kind": "internal",
                                                                     "message": "own"}}

    status, result = run_main(monkeypatch, {"effectKind": "x"}, effect=own)
    assert status == 0 and result["error"]["message"] == "own"


@pytest.mark.parametrize("kind", U8_EFFECT_KINDS)
def test_u7s_child_refuses_each_of_a6s_kinds_and_writes_nothing(tmp_path, kind):
    root = tmp_path / "effects"
    root.mkdir()
    result = native_adapter.apply_effect({
        "operationId": "op-1", "operationName": "platform.x", "targetId": "tunnel",
        "token": TOKEN, "effectKind": kind, "inputHash": "a" * 64, "targetRoot": str(root)})
    assert result == {"status": "not-applied", "effectRefs": [],
                      "error": {"kind": "internal", "message": "unsupported effect kind"}}
    assert list(root.iterdir()) == []
    # The lone ledger copy's kind is A6's twelfth (L1-5, Step 64(c)); U7's child refuses it too.
    assert len(U8_EFFECT_KINDS) == 12 and "ledger-copy" in U8_EFFECT_KINDS


def test_the_inventory_rules_are_u7s(tmp_path):
    assert enums.EFFECT_KINDS == ("file-write", "file-probe", "credential-presence")
    assert native_adapter.EFFECT_KINDS == enums.EFFECT_KINDS
    assert len(load_inventory().protocols) == 8
    raw = json.loads(_INVENTORY_PATH.read_text())
    raw["protocols"][0] = {**raw["protocols"][0], "effectKind": "tunnel-route"}
    planted = tmp_path / "inventory.json"
    planted.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="invalid effect kind"):
        load_inventory(planted)


@pytest.mark.parametrize("command", ["recovery", "cutover", "migration", "inventory"])
def test_u7s_envelope_refuses_u8s_commands(command):
    with pytest.raises(SystemExit) as refused:
        cli.main([command, "status"])
    assert refused.value.code == 2


def test_importing_every_u7_module_loads_nothing_of_u8_or_the_backend():
    imports = "; ".join(f"import docsuri_ops.platform_control.{name}" for name in U7_MODULES)
    program = (f"import sys; import docsuri_ops.platform_control.__main__; {imports}; "
               "print('\\n'.join(sorted(sys.modules)))")
    done = subprocess.run([sys.executable, "-I", "-c", program], capture_output=True,
                          timeout=60, check=True)
    loaded = done.stdout.decode().splitlines()
    assert "docsuri_ops.platform_control.store" in loaded
    others = [name for name in loaded if name.startswith("docsuri_ops.")
              and not name.startswith("docsuri_ops.platform_control")]
    assert others == []
    assert not [name for name in loaded if name == "backend" or name.startswith("backend.")]


def test_u7s_profile_holds_none_of_the_moved_names():
    for name in MOVED_NAMES:
        assert not hasattr(profile, name), name
        assert not hasattr(profile.PlatformProfile, name), name
        assert not hasattr(enums, name), name
        assert not hasattr(native_adapter, name), name
