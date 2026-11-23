"""The two thin macOS adapters over this Mac's real tools (U8 plan Step 103(b);
`.coveragerc.u8-macos`).

Run only in `ci.yml`'s `macos-filesystem` job, or through the tool's `arrangement` phase on
this Mac, as root under sudo (`DOCSURI_U8_ARRANGEMENT=1`); the conftest collects this
folder nowhere else.

- `isolation_macos.MacTools` runs `dscl`, `otool`, `lsof`, `diskutil`, `tmutil`, `pfctl`
  and `launchctl` for real. `diskutil info` writes a missing volume's `Could not find
  disk` line to standard error with exit 1 (measured in Step 74(d)), which `volume` reads.
  A `run` that raises, an exit outside a method's accepted codes, and recorded output for
  each parser's refusal branch show every method's refusal.
- `standing.macos` goes through the real `/usr/bin/sudo -n -u nobody` to `/bin/sh` probe
  programs in a fresh root-owned 0755 folder under `/private/tmp` (outside pytest's 0700
  tmp root, never under `/Library/DocSuri`), removed afterwards.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from docsuri_ops import isolation_macos
from docsuri_ops.isolation_macos import MacTools
from docsuri_ops.standing import macos as standing

MISSING_VOLUME = "/Volumes/u8-review-no-such-volume"
MARKER = "DOCSURI_U8_PROBE_MARKER"
LEDGER_BYTES = 100_000
NOBODY = "nobody"

PROBE = f"""#!/bin/sh
case "$1" in
  echo)
    input=$(/bin/cat)
    echo "a noise line before the result"
    printf '{{"ok": true, "input": %s, "user": "%s", "marker": "%s"}}\\n' \\
      "$input" "$(/usr/bin/id -un)" "${{{MARKER}-absent}}"
    ;;
  refuse)
    /bin/cat >/dev/null
    echo '{{"ok": false, "reason": "probe-refused"}}'
    exit 1
    ;;
  exit-three)
    /bin/cat >/dev/null
    echo '{{"ok": true}}'
    exit 3
    ;;
  silent)
    /bin/cat >/dev/null
    ;;
  silent-five)
    /bin/cat >/dev/null
    exit 5
    ;;
esac
"""
LEDGER_PROBE = f"""#!/bin/sh
/usr/bin/head -c {LEDGER_BYTES} /dev/zero
echo '{{"ok": true, "bytes": {LEDGER_BYTES}}}' >&2
"""
AGENT_PROBE = """#!/bin/sh
count=$(/usr/bin/wc -c | /usr/bin/tr -d ' ')
echo "a noise line before the result" >&2
printf '{"ok": true, "bytes": %s, "user": "%s"}\\n' "$count" "$(/usr/bin/id -un)" >&2
"""
REFUSING_AGENT_PROBE = """#!/bin/sh
/bin/cat >/dev/null
echo '{"ok": false, "reason": "probe-refused"}' >&2
exit 1
"""


@pytest.fixture(scope="module", autouse=True)
def as_root_on_macos():
    if sys.platform != "darwin" or os.geteuid() != 0:
        pytest.fail("the arrangement tests run as root on macOS (the macos-filesystem job)")


# --- the isolation adapter ---------------------------------------------------------------


def refusing_run(argv, **options):
    raise OSError("the tool could not start")


def exit_two(argv, **options):
    return subprocess.CompletedProcess(argv, 2, stdout=b"", stderr=b"")


def recorded(answers: dict[str, bytes]):
    """A `run` answering each tool, by its program path, with recorded standard output
    and exit 0."""

    def run(argv, **options):
        return subprocess.CompletedProcess(argv, 0, stdout=answers[argv[0]], stderr=b"")

    return run


def every_answer(tools: MacTools) -> dict:
    return {
        "job": tools.job("com.apple.logd"),
        "disabled": tools.disabled(),
        "filter_enabled": tools.filter_enabled(),
        "anchor_digest": tools.anchor_digest(),
        "volume": tools.volume("/"),
        "excluded": tools.excluded("/private/tmp"),
        "libraries": tools.libraries("/bin/ls"),
        "listeners": tools.listeners(15432),
        "account": tools.account("root"),
        "hba_file": tools.hba_file("/usr/bin/false", "/private/tmp", 0),
        "ident_file": tools.ident_file("/usr/bin/false", "/private/tmp", 0),
    }


def test_the_isolation_adapter_reads_this_macs_tools(tmp_path):
    tools = MacTools()
    root = tools.account("root")
    assert root is not None and root["uid"] == 0 and root["shell"].startswith("/")
    assert tools.account("u8-review-no-such-account") is None
    libraries = tools.libraries("/bin/ls")
    assert libraries is not None and "/usr/lib/libSystem.B.dylib" in libraries
    assert tools.libraries("/u8-review-no-such-program") is None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listening:
        listening.bind(("127.0.0.1", 0))
        listening.listen()
        port = listening.getsockname()[1]
        assert tools.listeners(port) == [("root", f"127.0.0.1:{port}")]
    boot = tools.volume("/")
    assert boot is not None and boot["present"] is True
    # Step 74(d): the missing volume's line comes on standard error with exit 1.
    assert tools.volume(MISSING_VOLUME) == {"present": False}
    assert isinstance(tools.excluded(str(tmp_path)), bool)
    assert isinstance(tools.filter_enabled(), bool)
    digest = tools.anchor_digest()
    assert digest is None or re.fullmatch(r"[0-9a-f]{64}", digest)
    assert tools.job("org.docsuri.u8-no-such-job") is None
    logd = tools.job("com.apple.logd")
    assert logd is not None and logd["state"] == "running" and isinstance(logd["pid"], int)
    assert isinstance(tools.disabled(), dict)

    for run in (refusing_run, exit_two):
        answers = every_answer(MacTools(run=run))
        assert answers.pop("disabled") == {}
        assert answers == dict.fromkeys(answers), run.__name__

    lsof_header = b"PROCESS PID OWNER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
    lsof_short = (b"COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                  b"python 101 root 3u IPv4\n")
    refusals = MacTools(run=recorded({
        isolation_macos.DSCL: b"UniqueID: 0\n",
        isolation_macos.DISKUTIL: b"   Mount Point:   /\n",
        isolation_macos.PFCTL: b"Debug: Urgent\n",
        isolation_macos.OTOOL: b"/etc/hosts: is not an object file\n",
        isolation_macos.LSOF: lsof_header,
    }))
    assert refusals.listeners(15432) is None
    assert refusals.account("root") is None
    assert refusals.volume("/") is None
    assert refusals.filter_enabled() is None
    assert refusals.libraries("/etc/hosts") is None
    assert MacTools(run=recorded({isolation_macos.LSOF: lsof_short})).listeners(15432) is None


# --- the standing adapter ----------------------------------------------------------------


def write_probe(folder: Path, name: str, text: str) -> None:
    path = folder / name
    path.write_text(text)
    os.chown(path, 0, 0)
    path.chmod(0o755)


@pytest.fixture
def probes():
    """A fresh root-owned 0755 folder of probe programs under `/private/tmp`; its
    `refusing` folder holds the same ledger probe beside an agent probe that refuses."""
    folder = Path(tempfile.mkdtemp(prefix="docsuri-u8-probe-", dir="/private/tmp"))
    try:
        refusing = folder / "refusing"
        refusing.mkdir()
        for each in (folder, refusing):
            os.chown(each, 0, 0)
            each.chmod(0o755)
            write_probe(each, "docsuri-probe", PROBE)
            write_probe(each, "docsuri-ledger", LEDGER_PROBE)
        write_probe(folder, "docsuri-backup-agent", AGENT_PROBE)
        write_probe(refusing, "docsuri-backup-agent", REFUSING_AGENT_PROBE)
        assert not str(folder.resolve()).startswith("/Library/DocSuri")
        yield folder
    finally:
        shutil.rmtree(folder)


def as_nobody(argv, **options):
    """The real `Popen`, with each argv's fixed account replaced by `nobody`, since
    `ledger_copy`'s accounts do not exist on a runner."""
    assert argv[:3] == [standing.SUDO, "-n", "-u"]
    return subprocess.Popen([*argv[:3], NOBODY, *argv[4:]], **options)


def test_the_standing_adapter_runs_fixed_programs_through_real_sudo(probes, monkeypatch):
    monkeypatch.setenv(MARKER, "set in the test's own environment")
    result = standing.run_fixed(NOBODY, "docsuri-probe", "echo", {"a": 1}, folder=probes)
    assert result == {"ok": True, "input": {"a": 1}, "user": NOBODY, "marker": "absent"}

    with pytest.raises(RuntimeError, match="^probe-refused$"):
        standing.run_fixed(NOBODY, "docsuri-probe", "refuse", folder=probes)
    with pytest.raises(RuntimeError, match="^program-refused$"):
        standing.run_fixed(NOBODY, "docsuri-probe", "exit-three", folder=probes)
    for word in ("silent", "silent-five"):
        with pytest.raises(ValueError, match="^no-result$"):
            standing.run_fixed(NOBODY, "docsuri-probe", word, folder=probes)
    with pytest.raises(ValueError, match="^no-result$"):
        standing.run_fixed("u8-review-no-such-account", "docsuri-probe", "echo", folder=probes)

    copied = standing.ledger_copy(popen=as_nobody, folder=probes)
    assert copied["head"] == {"ok": True, "bytes": LEDGER_BYTES}
    assert copied["agent"] == {"ok": True, "bytes": LEDGER_BYTES, "user": NOBODY}
    with pytest.raises(RuntimeError, match="^probe-refused$"):
        standing.ledger_copy(popen=as_nobody, folder=probes / "refusing")
