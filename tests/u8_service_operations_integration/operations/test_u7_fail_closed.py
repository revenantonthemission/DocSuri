"""Production and the composed realm fail closed without U8's PlatformControl parts (U8
plan Step 44; the person's decisions of 2026-10-25, "Move U8's code out of U7" and "Its
own package's name").

On the composed realm's platform store: U7's child, as built, refuses A6's effects; the
operator needs both of U7's seams; without U8's package PlatformControl is missing and
ServiceOperations unavailable; with it, production's readers build over their login
store. U8's adapter keeps U7's faults and framing, and the operator tool, run as its own
process, keeps every command's own refusal.
"""

from __future__ import annotations

import inspect
import io
import json
import runpy
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_ops.platform_control import RUNTIME_ROLE, executor, native_adapter
from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.u8_platform import adapter, u8_protocols
from docsuri_ops.u8_platform.drivers import input_hash, write_input
from docsuri_ops.u8_platform.u8_protocols import BOUNDED_CHILD, readers
from tests.u8_service_operations_integration import platform_flows as pf

ROOT = Path(__file__).resolve().parents[3]
TOKEN = uuid.uuid4().hex[:16]  # sixteen hex digits, generated per run (L1-36)


def key(name: str) -> str:
    return f"u7-fail-closed-{name}-{uuid.uuid4().hex}-{pf.RUN}"


# --- U7's child and U7's seams ----------------------------------------------------------------


def test_an_a6_effect_through_u7s_child_settles_failed_and_not_applied(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    calls = []

    def u7_child(**request):
        calls.append(request.pop("adapter_module"))
        return executor.run_effect(**request)

    receipt = journey.operator(run_effect=u7_child).execute(
        "platform.tunnel.route", "tunnel", {"origin": "v1-web"}, key=key("route"))
    assert calls == [BOUNDED_CHILD]
    assert receipt["outcome"] == "failed" and receipt["effectRefs"] == []
    assert receipt["refusal"] == "unsupported effect kind"
    assert journey.tunnel() is None


def without(function, name: str):
    """`function`'s signature without one keyword parameter, as a build without U8's
    seam would have it."""
    parameters = [p for p in inspect.signature(function).parameters.values() if p.name != name]

    def stand_in(*args, **kwargs):
        return function(*args, **kwargs)

    stand_in.__signature__ = inspect.Signature(parameters)
    return stand_in


@pytest.mark.parametrize(("module", "attribute", "seam"), [
    (executor, "run_effect", "adapter_module"),
    (native_adapter, "main", "effect"),
])
def test_the_operator_refuses_to_build_without_either_seam(tmp_path, realm, monkeypatch,
                                                           module, attribute, seam):
    journey = pf.journey(tmp_path, realm)
    store = journey.profile.store(RUNTIME_ROLE, journey.profile.realm_password("runtime"))
    touched = []
    monkeypatch.setattr(store, "record_evidence", lambda **kw: touched.append(kw))
    monkeypatch.setattr(module, attribute, without(getattr(module, attribute), seam))
    with pytest.raises(ControlError) as refused:
        u8_protocols.Operator(journey.profile, store, actor="operator",
                              authorities={"routine": str(uuid.uuid4())}, facts=pf.facts)
    assert refused.value.code == "POLICY_UNRESOLVED"
    assert seam in str(refused.value)
    assert touched == []


def test_the_operator_starts_u8s_adapter(tmp_path, realm, monkeypatch):
    journey = pf.journey(tmp_path, realm)
    started = []

    class Child:
        returncode = 0

        def communicate(self, payload=None, timeout=None):
            return json.dumps({"status": "not-applied", "effectRefs": [],
                               "error": {"kind": "internal", "message": "stand-in"}}).encode(), b""

    def popen(argv, **options):
        started.append(list(argv))
        return Child()

    monkeypatch.setattr(executor.subprocess, "Popen", popen)
    receipt = journey.operator().execute("platform.tunnel.route", "tunnel", {"origin": "v1-web"},
                                         key=key("started"))
    assert started == [[sys.executable, "-m", "docsuri_ops.u8_platform.adapter"]]
    assert receipt["outcome"] == "failed"


# --- without U8's package, and with it ----------------------------------------------------------


def test_without_u8s_package_platform_control_is_missing(realm, monkeypatch):
    from backend.u8_host import build_platform_control, compose

    monkeypatch.setitem(sys.modules, "docsuri_ops.u8_platform.u8_protocols", None)
    with pytest.raises(ModuleNotFoundError) as caught:
        build_platform_control(SimpleNamespace(profile=realm, arrangement=None))
    assert caught.value.name == "docsuri_ops.u8_platform.u8_protocols"
    composition = compose(realm)
    try:
        reasons = {name: item.reason for name, item in composition.activations.items()}
        assert reasons["platform-control"] == "missing"
        assert reasons["service-operations"] == "dependency-unavailable"
        assert composition.readiness()["ready"] is False
    finally:
        composition.close()


def test_with_it_productions_readers_build_over_their_login_store(tmp_path):
    from docsuri_ops.u8_platform.platform_profile import READER_FILE, U8PlatformProfile

    folder = tmp_path / "profile"
    folder.mkdir(mode=0o700)
    reader_file = folder / READER_FILE
    reader_file.write_text(json.dumps({"authorityId": str(uuid.uuid4()), "actor": "service",
                                       "password": uuid.uuid4().hex}))  # per run (L1-36)
    reader_file.chmod(0o600)
    bound = readers(U8PlatformProfile.production(control=tmp_path / "control"), root=folder)
    assert bound is not None and len(bound) == 3
    stores = {id(part.store) for part in bound}
    assert len(stores) == 1
    store = bound[0].store
    assert store.role == "docsuri_platform_reader"
    assert store.target.dbname == "docsuri_v2_platform" and store.target.port == 15432
    # The login store's next class is U8's SCRAM store class, and the one after it U7's
    # `Store` (plan Step 163(b), NFR3.3): exactly these two, in this order.
    from docsuri_ops.platform_control.store import Store
    from docsuri_ops.u8_platform.platform_profile import _scram_store_class

    assert type(store).__mro__[1] is _scram_store_class()
    assert type(store).__mro__[1].__module__ == "docsuri_ops.u8_platform.platform_profile"
    assert type(store).__mro__[2] is Store
    assert Store.__module__ == "docsuri_ops.platform_control.store"
    via_host = u8_protocols.readers_for(SimpleNamespace(is_production=True, root=str(folder)),
                                        control=tmp_path / "control")
    assert via_host is not None and via_host[0].store.role == "docsuri_platform_reader"


# --- U8's adapter, in process -------------------------------------------------------------------


def u7_request(root: Path, kind: str = "file-write") -> dict:
    return {"operationId": "op-1", "operationName": "platform.file.write", "targetId": "t-1",
            "token": TOKEN, "effectKind": kind, "inputHash": "a" * 64, "targetRoot": str(root)}


def test_u8s_adapter_hands_u7s_kinds_to_u7s_child(tmp_path, monkeypatch):
    applied = adapter.apply_effect(u7_request(tmp_path))
    assert applied["status"] == "applied"
    assert (tmp_path / applied["effectRefs"][0]).is_file()
    seen = []
    monkeypatch.setattr(native_adapter, "apply_effect",
                        lambda request, *, injected_fault=None: seen.append(injected_fault) or {
                            "status": "applied", "effectRefs": [], "error": None})
    adapter.apply_effect(u7_request(tmp_path, "file-probe"), injected_fault="disk")
    assert seen == ["disk"]


def test_u8s_adapter_keeps_u7s_faults_and_target_checks(tmp_path, monkeypatch):
    request = {**u7_request(tmp_path, "tunnel-route"), "targetId": "tunnel"}
    with pytest.raises(ValueError, match="unknown injected fault"):
        adapter.apply_effect(request, injected_fault="flood")
    assert adapter.apply_effect(request, injected_fault="permission")["status"] == "not-applied"
    assert adapter.apply_effect(request, injected_fault="disk")["status"] == "unknown"
    assert adapter.apply_effect(request, injected_fault="connectivity")["status"] == "unknown"
    slept = []
    monkeypatch.setattr(adapter.time, "sleep", slept.append)
    hung = adapter.apply_effect(request, injected_fault="hang")
    assert hung == {"status": "unknown", "effectRefs": [],
                    "error": {"kind": "internal", "message": "injected hang"}}
    assert slept == [adapter.HANG_SECONDS]
    escaped = adapter.apply_effect({**request, "targetId": "../tunnel"})
    assert escaped == {"status": "not-applied", "effectRefs": [],
                       "error": {"kind": "internal", "message": "target not reachable"}}
    assert adapter.apply_effect({k: v for k, v in request.items() if k != "token"})[
        "status"] == "not-applied"
    assert list(tmp_path.iterdir()) == []


def test_u8s_adapter_reaches_the_driver(tmp_path, realm, monkeypatch):
    journey = pf.journey(tmp_path, realm)
    inputs = {"origin": "maintenance"}
    write_input(journey.profile.effects_root / "tunnel", TOKEN, inputs)
    result = adapter.apply_effect({
        "operationId": str(uuid.uuid4()), "operationName": "platform.tunnel.route",
        "targetId": "tunnel", "token": TOKEN, "effectKind": "tunnel-route",
        "inputHash": input_hash(inputs), "targetRoot": str(journey.profile.effects_root)})
    assert result["status"] == "applied", result
    assert journey.tunnel()["origin"] == "maintenance"


def test_u8s_adapter_main_reads_one_request_and_writes_one_settlement(tmp_path, monkeypatch):
    stdin = io.TextIOWrapper(io.BytesIO(json.dumps(u7_request(tmp_path)).encode()))
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    assert adapter.main() == 0
    assert json.loads(stdout.getvalue())["status"] == "applied"


def test_the_package_and_the_adapter_run_as_main(tmp_path, monkeypatch):
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(
        json.dumps(u7_request(tmp_path)).encode())))
    monkeypatch.setattr(sys, "stdout", stdout)
    # As `-m` runs it: a module not yet imported, so runpy runs it afresh.
    monkeypatch.delitem(sys.modules, "docsuri_ops.u8_platform.adapter", raising=False)
    with pytest.raises(SystemExit) as ended:
        runpy.run_module("docsuri_ops.u8_platform.adapter", run_name="__main__")
    assert ended.value.code == 0 and json.loads(stdout.getvalue())["status"] == "applied"
    monkeypatch.setattr(sys, "argv", ["docsuri_ops.u8_platform", "elsewhere"])
    with pytest.raises(SystemExit) as refused:
        runpy.run_module("docsuri_ops.u8_platform", run_name="__main__")
    assert refused.value.code == 2


# --- the operator tool as its own process ---------------------------------------------------------


def tool(*argv: str, stdin: bytes = b"{}", isolated: bool = False) -> subprocess.CompletedProcess:
    """The operator tool as its own process: `-I` as production runs it, or as the
    composed realm runs it, from the repository's root."""
    flags = ["-I"] if isolated else []
    return subprocess.run([sys.executable, *flags, "-m", "docsuri_ops.u8_platform", *argv],
                          input=stdin, capture_output=True, timeout=120, check=False,
                          env={"PATH": "/usr/bin:/bin"}, cwd=ROOT)


def test_the_operator_tool_refuses_a_fifth_word():
    for argv in ((), ("platform",), ("shell", "ls")):
        for isolated in (True, False):
            refused = tool(*argv, isolated=isolated)
            assert refused.returncode == 2
            assert b"usage: python -I -m docsuri_ops.u8_platform" in refused.stderr
            assert refused.stdout == b""


def test_u7s_envelope_refuses_u8s_commands_as_its_own_process():
    # `availability` joins the commands U7's envelope refuses (U8 plan Step 73(e)). It is
    # given a word valid for availability itself, so only U7's own parser refusing it (and
    # not availability's usage, were the envelope ever to route it) passes.
    from docsuri_ops.u8_platform import availability_words

    for command, words in (("recovery", ["status"]), ("cutover", ["status"]),
                           ("migration", ["status"]), ("inventory", ["status"]),
                           ("service", ["status"]), ("availability", ["report", "--production"])):
        refused = subprocess.run(
            [sys.executable, "-I", "-m", "docsuri_ops.platform_control", command, *words],
            input=b"{}", capture_output=True, timeout=60, check=False,
            env={"PATH": "/usr/bin:/bin"})
        assert refused.returncode == 2, command
        assert b"unrecognized arguments" in refused.stderr, (command, refused.stderr[-400:])
        assert availability_words.USAGE.encode() not in refused.stderr, command


def test_each_command_reaches_its_own_refusal(tmp_path):
    """Run with no environment, as their in-process tests record: `cutover status` with
    a list for input is INVALID_INPUT and `migration dry-run` or `inventory take` with no
    realm or production named is POLICY_UNRESOLVED, each exit code 1 with one JSON
    result; `recovery` refuses a word outside its closed set through its own parser."""
    missing = str(tmp_path / "none" / "environment.json")
    cutover = tool("cutover", "status", "--environment-file", missing, stdin=b"[]")
    assert cutover.returncode == 1, cutover.stderr[-400:]
    assert json.loads(cutover.stdout)["error"]["code"] == "INVALID_INPUT"
    for command, word in (("migration", "dry-run"), ("inventory", "take")):
        done = tool(command, word)
        assert done.returncode == 1, (command, done.stderr[-400:])
        assert json.loads(done.stdout)["code"] == "POLICY_UNRESOLVED", command
    recovery = tool("recovery", "shell", "--environment-file", missing)
    assert recovery.returncode == 2
    assert b"docsuri-ops recovery" in recovery.stderr  # its own parser's `prog` label
    for done in (cutover, recovery):
        assert b"usage: python -I -m docsuri_ops.u8_platform" not in done.stderr
