"""PlatformControl's fixed programs (U8 plan Step 28; D6, NFR1.6, security-design § 15
"Fixed commands (D6)").

For each program: a word outside its closed set is refused with its reason key; a
caller-set `PYTHON*`, `DYLD_*` or `LD_*` variable is refused; its JSON result is the only
output. A stop record is root-owned (the test prefix's own account here), well formed,
cites its receipt and expires at 14 days. Every macOS tool runs through the context's
recorded runner, so nothing on this Mac is started, stopped or read.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.u8_platform import fixed
from docsuri_ops.u8_platform.fixed import FixedContext, read_stop_record, run

ROOT = Path(__file__).resolve().parents[3]
NOW = dt.datetime(2026, 10, 22, 12, 0, tzinfo=dt.UTC)
FIRST_WORD = {"docsuri-service-start": "org.docsuri.v2.host",
              "docsuri-service-stop": "org.docsuri.v2.host",
              "docsuri-tunnel-route": "v2-host", "docsuri-credential-release": "operator",
              "docsuri-profile": "mode", "docsuri-logs": "filter"}


class Tools:
    """The recorded macOS tools: each argv, and a fixed answer."""

    def __init__(self, stdout: bytes = b"", returncode: int = 0):
        self.calls: list[list[str]] = []
        self.stdout, self.returncode = stdout, returncode

    def __call__(self, argv, **options):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, self.returncode, stdout=self.stdout, stderr=b"")


@pytest.fixture
def context(tmp_path) -> FixedContext:
    paths = ArrangementPaths.under(tmp_path / "prefix")
    return FixedContext(paths=paths, run=Tools(), clock=lambda: NOW, owner_uid=os.getuid())


def call(program: str, argv: list[str], context: FixedContext, document=None, *,
         environ=None) -> tuple[int, bytes, bytes]:
    stdout, stderr = io.BytesIO(), io.BytesIO()
    payload = b"" if document is None else json.dumps(document).encode()
    status = run(program, argv, context, environ=environ or {}, stdin=io.BytesIO(payload),
                 stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def results_of(program: str, out: bytes, err: bytes) -> bytes:
    return err if program == "docsuri-credential-release" else out


def only_json(raw: bytes) -> dict:
    lines = raw.decode().splitlines()
    assert len(lines) == 1, raw
    return json.loads(lines[0])


# --- 1. a word outside its closed set ----------------------------------------------------


@pytest.mark.parametrize("program", sorted(fixed.PROGRAMS))
def test_a_word_outside_its_closed_set_is_refused_with_its_reason_key(program, context):
    for argv in ([], ["elsewhere"], [FIRST_WORD[program], "extra"], ["../" + FIRST_WORD[program]]):
        status, out, err = call(program, argv, context)
        assert status == 2
        assert only_json(results_of(program, out, err)) == {"ok": False,
                                                            "reason": "word-refused"}
    assert context.run.calls == []


# --- 2. a caller-set environment ----------------------------------------------------------


@pytest.mark.parametrize("program", sorted(fixed.PROGRAMS))
@pytest.mark.parametrize("variable", ["PYTHONPATH", "PYTHONSTARTUP", "DYLD_INSERT_LIBRARIES",
                                      "LD_PRELOAD"])
def test_a_caller_set_interpreter_variable_is_refused(program, variable, context):
    status, out, err = call(program, [FIRST_WORD[program]], context,
                            environ={variable: "/tmp/elsewhere"})
    assert status == 2
    assert only_json(results_of(program, out, err)) == {"ok": False,
                                                        "reason": "environment-refused"}
    assert context.run.calls == []


@pytest.mark.parametrize("program", sorted(fixed.PROGRAMS))
def test_each_installed_program_checks_its_environment_and_word_in_its_own_process(program):
    source = ROOT / "ops" / "bin" / program
    lines = source.read_text().splitlines()
    assert lines[0] == "#!/Library/DocSuri/release/.venv/bin/python -I"
    assert f'main_fixed("{program}")' in source.read_text()
    clean = {"PATH": "/usr/bin:/bin"}
    refused = subprocess.run([sys.executable, "-I", str(source), FIRST_WORD[program]],
                             env={**clean, "PYTHONPATH": "/tmp/elsewhere"},
                             capture_output=True, timeout=60, check=False)
    assert refused.returncode == 2
    raw = refused.stderr if program == "docsuri-credential-release" else refused.stdout
    assert json.loads(raw) == {"ok": False, "reason": "environment-refused"}
    word = subprocess.run([sys.executable, "-I", str(source), "elsewhere"], env=clean,
                          capture_output=True, timeout=60, check=False)
    raw = word.stderr if program == "docsuri-credential-release" else word.stdout
    assert word.returncode == 2 and json.loads(raw) == {"ok": False, "reason": "word-refused"}


def _first_import_after_guard(source: Path) -> str | None:
    """The module the program's first module-level import after its `--self-check`
    guard names (`import x` or `from x import …`)."""
    import ast

    tree = ast.parse(source.read_text(), filename=str(source))
    guarded = False
    for node in tree.body:
        if isinstance(node, ast.If):
            guarded = True
            continue
        if guarded and isinstance(node, ast.ImportFrom) and node.level == 0:
            return node.module
        if guarded and isinstance(node, ast.Import):
            return node.names[0].name
    return None


def test_every_installed_program_imports_the_module_its_self_check_names():
    """`--self-check` imports only `release.PROGRAM_ENTRIES[name]`, so it cannot see a
    program whose own import line names another module (U8 plan Step 44, the move out of
    U7). Each program's first import after its guard is its entry, for all of them."""
    from docsuri_ops.release import PROGRAM_ENTRIES

    programs = sorted(path.name for path in (ROOT / "ops" / "bin").iterdir()
                      if path.name.startswith("docsuri-"))
    assert programs == sorted(PROGRAM_ENTRIES)
    for name in programs:
        assert _first_import_after_guard(ROOT / "ops" / "bin" / name) == PROGRAM_ENTRIES[name], name
    for name in fixed.PROGRAMS:
        assert PROGRAM_ENTRIES[name] == "docsuri_ops.u8_platform.fixed"


def test_every_program_in_ops_bin_is_executable_and_writable_only_by_its_owner():
    """The sudoers rules, the launch jobs and the runbooks run each program directly
    (`sudo -k /Library/DocSuri/release/ops/bin/docsuri-release`), and a release is cloned
    from git, which records the mode: each file is executable by its owner and writable
    by neither group nor others."""
    import stat

    programs = sorted((ROOT / "ops" / "bin").iterdir())
    assert len(programs) == 17
    for program in programs:
        info = program.lstat()
        assert stat.S_ISREG(info.st_mode), program.name
        mode = stat.S_IMODE(info.st_mode)
        assert mode & stat.S_IXUSR, f"{program.name} is not executable ({mode:o})"
        assert not mode & (stat.S_IWGRP | stat.S_IWOTH), f"{program.name} is {mode:o}"


def test_a_program_whose_import_differs_from_its_entry_is_found(tmp_path):
    planted = tmp_path / "docsuri-logs"
    planted.write_text('import sys\n\nif sys.argv[1:] == ["--self-check"]:\n    pass\n\n'
                       "from docsuri_ops.backup_agent.cli import main_fixed\n")
    assert _first_import_after_guard(planted) == "docsuri_ops.backup_agent.cli"
    assert _first_import_after_guard(planted) != "docsuri_ops.u8_platform.fixed"
    unguarded = tmp_path / "docsuri-profile"
    unguarded.write_text("from docsuri_ops.u8_platform.fixed import main_fixed\n")
    assert _first_import_after_guard(unguarded) is None


# --- 3. the JSON result is the only output ------------------------------------------------


def test_bounded_input_outside_its_form_is_refused_with_one_result(context):
    for payload, reason in ((b"{" + b" " * (17 * 1024) + b"}", "input-too-large"),
                            (b"not json", "input-not-json"), (b"[1]", "input-not-an-object")):
        stdout, stderr = io.BytesIO(), io.BytesIO()
        status = run("docsuri-service-stop", ["org.docsuri.v2.host"], context, environ={},
                     stdin=io.BytesIO(payload), stdout=stdout, stderr=stderr)
        assert status == 1 and only_json(stdout.getvalue())["reason"] == reason
        assert stderr.getvalue() == b""
    status, out, _ = call("docsuri-service-stop", ["org.docsuri.v2.host"], context,
                          {"receiptId": "not-a-receipt"})
    assert only_json(out) == {"ok": False, "reason": "receipt-required"}


def test_a_failed_tool_or_a_missing_file_is_still_one_result(context):
    receipt = str(uuid4())
    context.run = Tools(returncode=1)
    status, out, err = call("docsuri-service-stop", ["org.docsuri.v2.host"], context,
                            {"receiptId": receipt})
    assert status == 1 and only_json(out) == {"ok": False, "reason": "tool-failed"}
    status, out, err = call("docsuri-tunnel-route", ["v2-host"], context,
                            {"receiptId": receipt})
    assert status == 1 and only_json(out) == {"ok": False, "reason": "program-failed"}
    assert err == b""
    status, out, _ = call("docsuri-profile", ["mode"], context,
                          {"value": "live", "receiptId": receipt})
    assert only_json(out) == {"ok": False, "reason": "program-failed"}


# --- 4. the stop record ------------------------------------------------------------------


def test_a_stop_unloads_the_job_and_writes_a_bounded_root_owned_record(context):
    receipt = str(uuid4())
    status, out, _ = call("docsuri-service-stop", ["org.docsuri.v2.workers"], context,
                          {"receiptId": receipt})
    result = only_json(out)
    assert status == 0 and result["ok"] is True and result["state"] == "stopped"
    assert context.run.calls == [
        ["/bin/launchctl", "disable", "system/org.docsuri.v2.workers"],
        ["/bin/launchctl", "bootout", "system/org.docsuri.v2.workers"]]
    path = fixed.stop_record_path(context.paths, "org.docsuri.v2.workers")
    info = path.lstat()
    assert info.st_uid == context.owner_uid and info.st_mode & 0o777 == 0o644
    record = read_stop_record(path, owner_uid=context.owner_uid, now=NOW)
    assert record == {"label": "org.docsuri.v2.workers", "receiptId": receipt,
                      "stoppedAt": NOW.isoformat(),
                      "expiresAt": (NOW + dt.timedelta(days=14)).isoformat()}
    # Past its bound, owned by another account, or altered, it covers nothing.
    assert read_stop_record(path, owner_uid=context.owner_uid,
                            now=NOW + dt.timedelta(days=14, seconds=1)) is None
    assert read_stop_record(path, owner_uid=context.owner_uid + 1, now=NOW) is None
    altered = {**record, "expiresAt": (NOW + dt.timedelta(days=30)).isoformat()}
    path.write_text(json.dumps(altered))
    assert read_stop_record(path, owner_uid=context.owner_uid, now=NOW) is None
    path.write_text("not json")
    assert read_stop_record(path, owner_uid=context.owner_uid, now=NOW) is None


def test_a_start_loads_the_job_and_removes_the_record(context):
    receipt = str(uuid4())
    call("docsuri-service-stop", ["org.docsuri.v2.host"], context, {"receiptId": receipt})
    context.run.calls.clear()
    status, out, _ = call("docsuri-service-start", ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    assert status == 0 and only_json(out)["state"] == "running"
    assert context.run.calls == [
        ["/bin/launchctl", "enable", "system/org.docsuri.v2.host"],
        ["/bin/launchctl", "bootstrap", "system",
         "/Library/LaunchDaemons/org.docsuri.v2.host.plist"]]
    assert not fixed.stop_record_path(context.paths, "org.docsuri.v2.host").exists()


class Launchd:
    """launchctl answering by subcommand: `answers` maps a subcommand to its status."""

    def __init__(self, answers: dict[str, int]):
        self.answers, self.calls = answers, []

    def __call__(self, argv, **options):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, self.answers.get(argv[1], 0), stdout=b"",
                                           stderr=b"")


@pytest.mark.parametrize("answer", [5, 37])
def test_a_start_on_a_job_already_loaded_is_done(context, answer):
    """Your decision of 2026-10-26 ("Start and stop are safe to repeat"): bootstrap's
    already-loaded answers are done, as `MacTools.bootstrap` treats them."""
    call("docsuri-service-stop", ["org.docsuri.v2.host"], context, {"receiptId": str(uuid4())})
    context.run = Launchd({"bootstrap": answer})
    status, out, _ = call("docsuri-service-start", ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    result = only_json(out)
    assert status == 0 and result["state"] == "running" and result["wasLoaded"] is True
    assert not fixed.stop_record_path(context.paths, "org.docsuri.v2.host").exists()
    assert context.run.calls[-1] == ["/bin/launchctl", "print", "system/org.docsuri.v2.host"]


@pytest.mark.parametrize(("bootstrap", "printed"), [(5, 113), (37, 113), (5, 1)])
def test_a_bootstrap_5_whose_job_is_not_loaded_fails_and_keeps_the_record(
        context, bootstrap, printed):
    """Review finding (Minor, R13): 5 is launchctl's generic input/output error (a plist
    with the wrong owner or mode answers it too). Unless `launchctl print` then shows the
    job loaded, the start fails (`tool-failed`) and its stop record stays, so the
    isolation check still counts the job as stopped by a held receipt."""
    receipt = str(uuid4())
    call("docsuri-service-stop", ["org.docsuri.v2.host"], context, {"receiptId": receipt})
    context.run = Launchd({"bootstrap": bootstrap, "print": printed})
    status, out, _ = call("docsuri-service-start", ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    assert (status, only_json(out)) == (1, {"ok": False, "reason": "tool-failed"})
    kept = read_stop_record(fixed.stop_record_path(context.paths, "org.docsuri.v2.host"),
                            owner_uid=context.owner_uid, now=NOW)
    assert kept is not None and kept["receiptId"] == receipt


def test_a_bootstrap_that_succeeds_needs_no_print(context):
    context.run = Launchd({"print": 113})
    status, out, _ = call("docsuri-service-start", ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    assert status == 0 and only_json(out)["wasLoaded"] is False
    assert [argv[1] for argv in context.run.calls] == ["enable", "bootstrap"]


@pytest.mark.parametrize("answer", [3, 113])
def test_a_stop_on_a_job_not_loaded_is_done_and_writes_its_record(context, answer):
    receipt = str(uuid4())
    context.run = Launchd({"bootout": answer})
    status, out, _ = call("docsuri-service-stop", ["org.docsuri.v2.workers"], context,
                          {"receiptId": receipt})
    result = only_json(out)
    assert status == 0 and result["renewed"] is False and result["wasLoaded"] is False
    record = read_stop_record(fixed.stop_record_path(context.paths, "org.docsuri.v2.workers"),
                              owner_uid=context.owner_uid, now=NOW)
    assert record["receiptId"] == receipt


def test_a_stop_on_a_loaded_job_with_a_record_unloads_it(context):
    """A record left while the job is loaded (a start whose unlink failed after the
    bootstrap) does not stop the bootout: the job is unloaded and the record rewritten."""
    call("docsuri-service-stop", ["org.docsuri.v2.host"], context, {"receiptId": str(uuid4())})
    context.run = Launchd({})
    receipt = str(uuid4())
    status, out, _ = call("docsuri-service-stop", ["org.docsuri.v2.host"], context,
                          {"receiptId": receipt})
    result = only_json(out)
    assert status == 0 and result["renewed"] is False and result["wasLoaded"] is True
    assert context.run.calls == [["/bin/launchctl", "disable", "system/org.docsuri.v2.host"],
                                 ["/bin/launchctl", "bootout", "system/org.docsuri.v2.host"]]
    assert result["stopRecord"]["receiptId"] == receipt


def test_a_stop_on_an_unloaded_job_with_a_record_renews_it(context):
    first = str(uuid4())
    call("docsuri-service-stop", ["org.docsuri.v2.host"], context, {"receiptId": first})
    later = NOW + dt.timedelta(days=13)
    context.clock = lambda: later
    context.run = Launchd({"bootout": 3})
    receipt = str(uuid4())
    status, out, _ = call("docsuri-service-stop", ["org.docsuri.v2.host"], context,
                          {"receiptId": receipt})
    result = only_json(out)
    assert status == 0 and result["renewed"] is True
    record = read_stop_record(fixed.stop_record_path(context.paths, "org.docsuri.v2.host"),
                              owner_uid=context.owner_uid, now=later)
    assert record["receiptId"] == receipt
    assert record["expiresAt"] == (later + dt.timedelta(days=14)).isoformat()


@pytest.mark.parametrize(("program", "subcommand"), [("docsuri-service-start", "bootstrap"),
                                                     ("docsuri-service-stop", "bootout")])
def test_any_other_launchctl_failure_is_still_a_tool_failure(context, program, subcommand):
    context.run = Launchd({subcommand: 1})
    status, out, _ = call(program, ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    assert status == 1 and only_json(out) == {"ok": False, "reason": "tool-failed"}
    context.run = Launchd({"disable" if program.endswith("stop") else "enable": 5})
    status, out, _ = call(program, ["org.docsuri.v2.host"], context,
                          {"receiptId": str(uuid4())})
    assert status == 1 and only_json(out)["reason"] == "tool-failed"


def test_v1s_agents_are_reached_in_the_operators_own_domain(context):
    status, out, _ = call("docsuri-service-stop", ["dev.docsuri.api"], context,
                          {"receiptId": str(uuid4())}, environ={"SUDO_UID": str(os.getuid())})
    assert status == 0, out
    assert context.run.calls[0] == ["/bin/launchctl", "disable",
                                    f"gui/{os.getuid()}/dev.docsuri.api"]
    status, out, _ = call("docsuri-service-stop", ["dev.docsuri.api"], context,
                          {"receiptId": str(uuid4())})
    assert only_json(out) == {"ok": False, "reason": "operator-unknown"}


# --- each program's own work ---------------------------------------------------------------


def test_tunnel_routing_makes_one_registered_configuration_active(context):
    folder = context.paths.tunnel_config
    folder.mkdir(parents=True)
    (folder / "v2-host.yml").write_text("ingress: v2-host\n")
    receipt = str(uuid4())
    status, out, _ = call("docsuri-tunnel-route", ["v2-host"], context, {"receiptId": receipt})
    assert status == 0 and only_json(out) == {"ok": True, "origin": "v2-host", "active": True}
    assert (folder / "active.yml").read_text() == "ingress: v2-host\n"
    assert json.loads((folder / "active.json").read_text()) == {"origin": "v2-host",
                                                               "receiptId": receipt}
    assert context.run.calls == [["/bin/launchctl", "kickstart", "-k",
                                  "system/org.docsuri.tunnel"]]
    os.chmod(folder / "v2-host.yml", 0o666)
    status, out, _ = call("docsuri-tunnel-route", ["v2-host"], context, {"receiptId": receipt})
    assert only_json(out) == {"ok": False, "reason": "registered-configuration-refused"}
    # NFR3.4: a configuration another account owns is refused, even at 0644.
    os.chmod(folder / "v2-host.yml", 0o644)
    other = FixedContext(paths=context.paths, run=context.run, clock=context.clock,
                         owner_uid=os.getuid() + 1)
    kept = {name: (folder / name).read_bytes() for name in ("active.yml", "active.json")}
    calls = list(context.run.calls)
    status, out, _ = call("docsuri-tunnel-route", ["v2-host"], other, {"receiptId": str(uuid4())})
    assert only_json(out) == {"ok": False, "reason": "registered-configuration-refused"}
    assert {name: (folder / name).read_bytes() for name in kept} == kept
    assert context.run.calls == calls


def operator_named(context: FixedContext, name: str) -> Path:
    """`control/platform-authorities.json` under the context's prefix, at 0644 and owned
    by the test's own user (the context's `owner_uid`), naming `name` as the operator."""
    path = context.paths.control / "platform-authorities.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"actors": {"operator": name}}))
    os.chmod(path, 0o644)
    return path


def test_credential_release_writes_the_password_to_its_pipe_and_the_result_beside_it(context):
    import pwd

    account = pwd.getpwuid(os.getuid()).pw_name
    operator_named(context, account)
    released = secrets.token_hex(16).encode() + b"\n"  # generated per run (L1-36)
    context.run = Tools(stdout=released)
    status, out, err = call("docsuri-credential-release", ["restore"], context,
                            environ={"SUDO_UID": str(os.getuid())})
    assert status == 0 and out == released
    assert only_json(err) == {"ok": True, "login": "restore", "actor": account}
    assert context.run.calls == [["/usr/bin/security", "find-generic-password", "-s",
                                  "docsuri-v2-restore", "-w",
                                  "/Library/Keychains/System.keychain"]]
    status, out, err = call("docsuri-credential-release", ["restore"], context, {"x": 1})
    assert out == b"" and only_json(err) == {"ok": False, "reason": "input-field-refused"}


def test_the_credential_release_serves_only_the_account_sudo_authenticated_as_the_installed_operator(  # noqa: E501
        context, tmp_path):
    """Step 120(a) (D4, security-design § 5.3; L2-6): the account sudo authenticated
    (`SUDO_UID`, through patched user identifiers) must be the operator the root-owned
    authority file names; every other caller is refused before the keychain is read."""
    from types import SimpleNamespace

    accounts = {501: "maintainer", 502: "other"}

    def lookup(uid: int):
        if uid not in accounts:
            raise KeyError(uid)
        return SimpleNamespace(pw_name=accounts[uid])

    context.lookup = lookup
    path = operator_named(context, "maintainer")
    released = secrets.token_hex(16).encode() + b"\n"  # generated per run (L1-36)

    def release(uid: str | None):
        context.run = Tools(stdout=released)
        environ = {} if uid is None else {"SUDO_UID": uid}
        return call("docsuri-credential-release", ["operator"], context, environ=environ)

    def refused(answer, reason: str) -> None:
        status, out, err = answer
        assert status == 1 and out == b"", (status, out)
        assert only_json(err) == {"ok": False, "reason": reason}
        assert context.run.calls == []

    refused(release("502"), "not-the-installed-operator")
    status, out, err = release("501")
    assert status == 0 and out == released and released not in err
    assert only_json(err) == {"ok": True, "login": "operator", "actor": "maintainer"}
    for uid in (None, "root", "-1", "999"):
        refused(release(uid), "in-person-actor-refused")

    os.chmod(path, 0o664)
    refused(release("501"), "authorities-file-refused")
    os.chmod(path, 0o644)
    kept = tmp_path / "kept-authorities.json"
    path.rename(kept)
    path.symlink_to(kept)
    refused(release("501"), "authorities-file-refused")
    path.unlink()
    refused(release("501"), "authorities-file-refused")
    kept.rename(path)
    assert release("501")[0] == 0
    # A file that names the operator but is padded past MAX_AUTHORITIES is refused.
    path.write_text(json.dumps({"actors": {"operator": "maintainer"},
                                "padding": "x" * fixed.MAX_AUTHORITIES}))
    refused(release("501"), "authorities-file-refused")
    operator_named(context, "maintainer")
    assert release("501")[0] == 0
    context.owner_uid = os.getuid() + 1
    refused(release("501"), "authorities-file-refused")


def test_logs_filter_reads_only_lines_carrying_the_request_identifier(context):
    folder = context.paths.profile / "logs"
    folder.mkdir(parents=True)
    request = str(uuid4())
    (folder / "host.jsonl").write_text(
        json.dumps({"requestId": request, "event": "a"}) + "\n"
        + json.dumps({"requestId": str(uuid4()), "event": "b"}) + "\n")
    before = (folder / "host.jsonl").stat().st_mtime_ns
    status, out, _ = call("docsuri-logs", ["filter"], context, {"requestId": request})
    result = only_json(out)
    assert status == 0 and result["truncated"] is False
    assert [line["file"] for line in result["lines"]] == ["logs/host.jsonl"]
    assert (folder / "host.jsonl").stat().st_mtime_ns == before
    status, out, _ = call("docsuri-logs", ["filter"], context, {"requestId": "*"})
    assert only_json(out) == {"ok": False, "reason": "request-id-refused"}


def test_logs_filter_never_reads_through_a_link_a_second_name_or_a_pipe(context, tmp_path):
    """Your answer of 2026-11-10 ("Fix both and sweep the rest"): every file below carries
    the request's identifier, so each would give its line if it were read. In the service
    account's log folder, a link to another file, a second name of another file and a FIFO
    give none, and a link in place of the scheduler's log folder gives none; only the
    folder's own regular file is read. The other files are left as they were."""
    request = str(uuid4())
    line = json.dumps({"requestId": request, "event": "x"}) + "\n"
    secret, second = tmp_path / "secret", tmp_path / "second"
    for path in (secret, second):
        path.write_text(line)
    folder = context.paths.profile / "logs"
    folder.mkdir(parents=True)
    (folder / "a-link.jsonl").symlink_to(secret)
    os.link(second, folder / "b-second-name.jsonl")
    os.mkfifo(folder / "c-fifo.jsonl")
    (folder / "d-own.jsonl").write_text(line)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "e.jsonl").write_text(line)
    context.paths.scheduler.mkdir(parents=True)
    (context.paths.scheduler / "logs").symlink_to(elsewhere)
    before = {path: path.read_bytes() for path in (secret, second, elsewhere / "e.jsonl")}
    status, out, _ = call("docsuri-logs", ["filter"], context, {"requestId": request})
    result = only_json(out)
    assert status == 0 and result["truncated"] is False
    assert [found["file"] for found in result["lines"]] == ["logs/d-own.jsonl"]
    assert {path: path.read_bytes() for path in before} == before
    assert second.stat().st_nlink == 2
    # With the second name gone, the same file read as the folder's own gives its line.
    (folder / "b-second-name.jsonl").unlink()
    os.link(second, folder / "b-own.jsonl")
    second.unlink()
    status, out, _ = call("docsuri-logs", ["filter"], context, {"requestId": request})
    assert [found["file"] for found in only_json(out)["lines"]] == [
        "logs/b-own.jsonl", "logs/d-own.jsonl"]


def test_logs_filter_skips_a_socket_in_a_log_folder(context, monkeypatch):
    """The review of the sweep (2026-11-10): a real UNIX-domain socket in the service
    account's log folder (bound by a relative name, within the socket path's length
    limit) is skipped, never read and never an error; the folder's own file still gives
    its line."""
    import socket
    import stat

    request = str(uuid4())
    folder = context.paths.profile / "logs"
    folder.mkdir(parents=True)
    (folder / "b-own.jsonl").write_text(json.dumps({"requestId": request, "event": "x"}) + "\n")
    monkeypatch.chdir(folder)
    with contextlib.closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as listener:
        listener.bind("a-socket.jsonl")
        assert stat.S_ISSOCK((folder / "a-socket.jsonl").lstat().st_mode)
        status, out, _ = call("docsuri-logs", ["filter"], context, {"requestId": request})
    result = only_json(out)
    assert status == 0 and [found["file"] for found in result["lines"]] == ["logs/b-own.jsonl"]


def test_a_profile_change_needs_the_profiles_custody_and_its_receipt(context):
    root = context.paths.profile
    root.mkdir(parents=True)
    manifest = root / "environment.json"
    manifest.write_text("{}")
    os.chmod(manifest, 0o644)
    receipt = str(uuid4())
    status, out, _ = call("docsuri-profile", ["mode"], context,
                          {"value": "live", "receiptId": receipt})
    assert only_json(out) == {"ok": False, "reason": "profile-custody"}
    os.chmod(manifest, 0o600)
    status, out, _ = call("docsuri-profile", ["mode"], context, {"value": "live"})
    assert only_json(out) == {"ok": False, "reason": "input-field-refused"}
    # An incomplete manifest fails the production profile's own checks; nothing changes.
    status, out, _ = call("docsuri-profile", ["mode"], context,
                          {"value": "live", "receiptId": receipt})
    assert only_json(out)["reason"].startswith("profile-")
    assert manifest.read_text() == "{}"


# --- The profile's database follows its mode (Step 28 gains; your decision of 2026-10-24) ----


@pytest.fixture
def profile_context():
    """A production profile of the installer's own first manifest, in the tests' marked
    folder (the loader refuses `/tmp`), under an arrangement prefix of its own."""
    from tests.u8_service_operations_integration.host_flows import (
        installer_manifest,
        production_root,
        write_private,
    )

    with production_root() as folder:
        paths = ArrangementPaths.under(folder / "prefix")
        root = paths.profile
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
        value = installer_manifest("docsuri-v2-" + "c" * 16, uuid4())
        write_private(root / "environment.json", json.dumps(value).encode())
        yield FixedContext(paths=paths, run=Tools(), clock=lambda: NOW,
                           owner_uid=os.getuid())


def loaded(context: FixedContext):
    from backend.u8_profile import ProductionProfile

    return ProductionProfile.load(context.paths.profile / "environment.json",
                                  service_uid=os.getuid())


def change(context: FixedContext, word: str, value) -> dict:
    status, out, _ = call("docsuri-profile", [word], context,
                          {"value": value, "receiptId": str(uuid4())})
    result = only_json(out)
    assert (status == 0) == result["ok"], result
    return result


def test_every_manifest_the_two_words_write_loads(profile_context):
    first = loaded(profile_context)
    rehearsal = first.rehearsal_database
    assert first.database_name == rehearsal  # the installer's first manifest loads
    assert change(profile_context, "mode", "live")["ok"]
    live = loaded(profile_context)
    assert (live.mode, live.database_name, live.rehearsal_database) == (
        "live", "docsuri_v2", rehearsal)  # the switch keeps the rehearsal database
    assert change(profile_context, "mode", "rehearsal")["ok"]
    back = loaded(profile_context)
    assert (back.mode, back.database_name) == ("rehearsal", rehearsal)
    other = "docsuri_v2_rehearsal_" + "d" * 12
    assert change(profile_context, "rehearsal-database", other)["ok"]
    assert loaded(profile_context).database_name == other  # in rehearsal it follows
    assert change(profile_context, "mode", "live")["ok"]
    assert change(profile_context, "rehearsal-database", None)["ok"]  # live: cleared
    cleared = loaded(profile_context)
    assert (cleared.database_name, cleared.rehearsal_database) == ("docsuri_v2", None)


def test_both_refusals_write_nothing(profile_context):
    manifest = profile_context.paths.profile / "environment.json"
    before = manifest.read_bytes()
    result = change(profile_context, "rehearsal-database", None)
    assert result == {"ok": False, "reason": "rehearsal-database-unset"}
    assert manifest.read_bytes() == before
    assert change(profile_context, "mode", "live")["ok"]
    assert change(profile_context, "rehearsal-database", None)["ok"]
    cleared = manifest.read_bytes()
    assert change(profile_context, "mode", "rehearsal") == {
        "ok": False, "reason": "rehearsal-database-unset"}
    assert manifest.read_bytes() == cleared
    assert not (profile_context.paths.profile / "environment.json.pending").exists()


def test_the_aborts_profile_steps_load(profile_context):
    """The abort's return to rehearsal (`cutover.tool.abort`: mode, then admission) loads,
    because the switch kept the rehearsal database."""
    assert change(profile_context, "mode", "live")["ok"]
    assert change(profile_context, "admission", "open")["ok"]
    assert change(profile_context, "mode", "rehearsal")["ok"] is False  # open + rehearsal
    assert change(profile_context, "admission", "maintainer-only")["ok"]
    assert change(profile_context, "mode", "rehearsal")["ok"]
    profile = loaded(profile_context)
    assert (profile.mode, profile.admission, profile.database_name) == (
        "rehearsal", "maintainer-only", profile.rehearsal_database)


def test_the_rollbacks_profile_steps_load_on_its_new_rehearsal_database(profile_context):
    """The rollback's return to rehearsal (`cutover.tool._serving_step`; your decision of
    2026-10-24, "Create a fresh rehearsal database"), through the production
    `docsuri-profile` word: opening cleared the rehearsal database, so mode rehearsal
    alone is refused; the rollback sets its new one first (still live, so the database
    stays `docsuri_v2`), then admission, then mode, and the manifest loads on it."""
    manifest = profile_context.paths.profile / "environment.json"
    first = loaded(profile_context).rehearsal_database
    # The switch, then opening: live, open, and the rehearsal database cleared.
    assert change(profile_context, "mode", "live")["ok"]
    assert change(profile_context, "admission", "open")["ok"]
    assert change(profile_context, "rehearsal-database", None)["ok"]
    opened = loaded(profile_context)
    assert (opened.mode, opened.database_name, opened.rehearsal_database) == (
        "live", "docsuri_v2", None)
    # Without the new database the return to rehearsal cannot load (the P3 finding).
    assert change(profile_context, "admission", "maintainer-only")["ok"]
    before = manifest.read_bytes()
    assert change(profile_context, "mode", "rehearsal") == {
        "ok": False, "reason": "rehearsal-database-unset"}
    assert manifest.read_bytes() == before
    assert change(profile_context, "admission", "open")["ok"]
    # The rollback's steps, in its order.
    fresh = "docsuri_v2_rehearsal_" + "f" * 12
    assert fresh != first
    assert change(profile_context, "rehearsal-database", fresh)["ok"]
    still_live = loaded(profile_context)
    assert (still_live.mode, still_live.database_name, still_live.rehearsal_database) == (
        "live", "docsuri_v2", fresh)
    assert change(profile_context, "admission", "maintainer-only")["ok"]
    assert change(profile_context, "mode", "rehearsal")["ok"]
    back = loaded(profile_context)
    assert (back.mode, back.admission, back.database_name, back.rehearsal_database) == (
        "rehearsal", "maintainer-only", fresh, fresh)
    # A dry run accepted after the rollback moves it onto that run's database.
    accepted = "docsuri_v2_rehearsal_" + "a" * 12
    assert change(profile_context, "rehearsal-database", accepted)["ok"]
    assert loaded(profile_context).database_name == accepted
