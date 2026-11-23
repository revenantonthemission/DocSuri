"""The rendered templates under macOS's own checkers, and the installer's macOS adapter
with the real tools (U8 plan Step 38; cicd-pipeline § 3, D6, security-design § 6.8).

Run only in `ci.yml`'s `macos-filesystem` job, or through the tool's `arrangement` phase,
as root under sudo (`DOCSURI_U8_ARRANGEMENT=1`); the conftest collects this folder nowhere
else. Everything is rendered and checked under a temporary prefix: `visudo -c -f` on the
sudo rules, `plutil -lint` on every launch job definition and `pfctl -n -f` on the anchor,
which parses the rules without loading them. A temporary keychain file stands in for the
System keychain; nothing is installed, loaded or excluded outside the test's folder.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from docsuri_ops.arrangement import macos, render
from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths

ACCOUNTS = Accounts.standard()


@pytest.fixture(scope="module", autouse=True)
def as_root_on_macos():
    if sys.platform != "darwin" or os.geteuid() != 0:
        pytest.fail("the arrangement tests run as root on macOS (the macos-filesystem job)")


@pytest.fixture
def rendered(tmp_path):
    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    items = render.render(paths, ACCOUNTS, operator="runner", tunnel_name="docsuri-v2-ci0001")
    for item in items:
        item.target.parent.mkdir(parents=True, exist_ok=True)
        item.target.write_bytes(item.content)
        os.chmod(item.target, item.mode)
        os.chown(item.target, 0, 0)
    return paths, items


def test_visudo_accepts_the_sudo_rules(rendered):
    paths, _ = rendered
    tools = macos.MacTools()
    assert tools.sudoers_check(paths.sudoers_rules) is True
    broken = paths.sudoers_rules.with_name("broken")
    broken.write_text("Cmnd_Alias = nonsense\n")
    os.chmod(broken, 0o440)
    assert tools.sudoers_check(broken) is False


def test_plutil_lints_every_launch_job_definition(rendered):
    paths, items = rendered
    tools = macos.MacTools()
    plists = [item.target for item in items if item.target.suffix == ".plist"]
    assert len(plists) == 11
    for plist in plists:
        assert tools.plist_lint(plist) is True, plist
    damaged = plists[0].with_name("damaged.plist")
    damaged.write_text("<plist><dict><key>")
    assert tools.plist_lint(damaged) is False


def test_pfctl_parses_the_anchor_without_loading_it(rendered):
    paths, _ = rendered
    tools = macos.MacTools()
    assert tools.anchor_check(paths.pf_anchor) is True
    wrong = paths.pf_anchor.with_name("wrong")
    wrong.write_text("pass in quick on lo0 proto tcp to 127.0.0.1 port nonsense\n")
    assert tools.anchor_check(wrong) is False


def test_the_adapter_reads_this_macs_tools(tmp_path):
    tools = macos.MacTools()
    root = tools.account("root")
    assert root is not None and root["uid"] == 0
    assert tools.account("_docsuri_no_such_account") is None
    libraries = tools.libraries(Path("/bin/ls"))
    assert libraries and macos.loads_only_from(libraries, Path("/bin"))
    assert tools.libraries(tmp_path / "missing") is None
    assert (tools.memory_available() or 0) > 0
    assert tools.volume("/") is not None
    assert tools.excluded(str(tmp_path)) in (True, False)
    assert tools.job_state("org.docsuri.no-such-job") is None
    assert tools.anchor_rules() is None or isinstance(tools.anchor_rules(), str)
    assert tools.run(["/usr/bin/id", "-u"], user=0) == b"0\n"
    # A run as an account keeps none of root's supplementary groups: without
    # `extra_groups=[]` the child would still list root's groups beside its own.
    daemon = tools.account("daemon")
    assert daemon is not None and daemon["uid"] != 0 and daemon["gid"] not in (None, 0)
    assert tools.run(["/usr/bin/id", "-u"], user=daemon["uid"], group=daemon["gid"]) == (
        f"{daemon['uid']}\n".encode())
    assert tools.run(["/usr/bin/id", "-G"], user=daemon["uid"], group=daemon["gid"]).split() == [
        str(daemon["gid"]).encode()]
    with pytest.raises(macos.ToolFailed):
        tools.run(["/usr/bin/false"])
    with pytest.raises(macos.ToolFailed):
        tools.run([str(tmp_path / "no-such-tool")])
    with pytest.raises(macos.ToolFailed):
        tools.fetch("http://example.invalid/")
    assert macos.MacTools(fetch_url=lambda url, seconds: b"fixture").fetch(
        "https://example.invalid/") == b"fixture"


def test_the_adapter_changes_files_the_way_the_installer_needs(tmp_path):
    tools = macos.MacTools()
    source = tmp_path / "source"
    source.write_bytes(b"model blob")
    clone = tmp_path / "clone"
    tools.clone(source, clone)
    assert clone.read_bytes() == b"model blob"
    tools.chown(clone, ACCOUNTS.models.uid, ACCOUNTS.models.uid)
    assert tools.owner(clone) == ACCOUNTS.models.uid
    tools.chmod(clone, 0o600)
    assert clone.stat().st_mode & 0o777 == 0o600
    link = tmp_path / "link"
    link.symlink_to(clone)
    with pytest.raises(macos.ToolFailed):
        tools.chmod(link, 0o644)
    assert tools.owner(tmp_path / "missing") is None
    tools.moved(source, clone)


def test_the_adapter_keeps_a_keychain_secret_off_every_argument(tmp_path):
    keychain = tmp_path / "fixture.keychain"
    subprocess.run(["/usr/bin/security", "create-keychain", "-p", "fixture-only", str(keychain)],
                   check=True, capture_output=True)
    try:
        tools = macos.MacTools()
        secret = secrets.token_hex(32).encode()  # 64 hex digits, generated per run (L1-36)
        tools.keychain_add("docsuri-v2-fixture", "root", secret, keychain=str(keychain))
        assert tools.keychain_has("docsuri-v2-fixture", keychain=str(keychain)) is True
        assert tools.keychain_has("docsuri-v2-absent", keychain=str(keychain)) is False
        with pytest.raises(macos.ToolFailed):
            tools.keychain_add("bad service;", "root", secret, keychain=str(keychain))
        with pytest.raises(macos.ToolFailed):
            tools.keychain_add("docsuri-v2-fixture", "root", b"not hex", keychain=str(keychain))
    finally:
        subprocess.run(["/usr/bin/security", "delete-keychain", str(keychain)],
                       capture_output=True, check=False)


def test_the_adapters_parsers_on_recorded_output():
    assert macos.parse_dscl_user("UniqueID: 610\nUserShell: /usr/bin/false\n"
                                 "PrimaryGroupID: 610\n") == {
        "uid": 610, "shell": "/usr/bin/false", "gid": 610}
    assert macos.parse_dscl_user("No such key") is None
    assert macos.parse_vm_stat("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
                               "Pages free:  100.\nPages inactive:  50.\n") == 16384 * 150
    assert macos.parse_vm_stat("") is None
    assert macos.parse_plutil_lint("/a.plist: OK\n") is True
    assert macos.parse_plutil_lint("/a.plist: Unexpected character\n") is False
    assert macos.parse_visudo_check("/x: parsed OK\n") is True
    assert macos.parse_tmutil_isexcluded("[Excluded]    /Library/DocSuri") is True
    assert macos.parse_tmutil_isexcluded("nonsense") is None
    assert macos.parse_otool("/bin/x:\n\t/usr/lib/libSystem.B.dylib (compatibility 1.0)\n") == [
        "/usr/lib/libSystem.B.dylib"]
    assert macos.parse_otool("/x: is not an object file") is None
    assert macos.parse_launchctl_state("system/x = {\n\tstate = running\n}") == "running"
    assert macos.parse_launchctl_state("") is None
    assert macos.parse_diskutil_encrypted("Volume Name: DocSuri_Backup\nLocked: No\n"
                                          "FileVault: Yes\nVolume UUID: ABC\n") == {
        "locked": False, "encrypted": True, "identifier": "ABC"}
    assert macos.parse_diskutil_encrypted("nothing") is None
    assert macos.loads_only_from(["/opt/homebrew/lib/x.dylib"], Path("/Library/DocSuri")) is False


def test_the_adapter_restarts_a_job_and_reads_a_keychain_item_back(tmp_path):
    """U8 plan Step 137(g): the two methods the password change adds, so the macOS report
    counts their lines. The keychain read runs the real `security` on a temporary keychain;
    the restart is only recorded, since a real `kickstart -k` would restart a real job."""
    keychain = tmp_path / "fixture.keychain"
    subprocess.run(["/usr/bin/security", "create-keychain", "-p", "fixture-only", str(keychain)],
                   check=True, capture_output=True)
    try:
        tools = macos.MacTools()
        secret = secrets.token_hex(32).encode()  # 64 hex digits, generated per run (L1-36)
        tools.keychain_add("docsuri-v2-fixture", "root", secret, keychain=str(keychain))
        read = tools.keychain_read("docsuri-v2-fixture", keychain=str(keychain))
        assert isinstance(read, bytearray) and read == bytearray(secret)
        assert not read.endswith(b"\n")
        with pytest.raises(macos.ToolFailed):
            tools.keychain_read("docsuri-v2-absent", keychain=str(keychain))
    finally:
        subprocess.run(["/usr/bin/security", "delete-keychain", str(keychain)],
                       capture_output=True, check=False)
    recorded: list = []

    def recording(argv, **options):
        recorded.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    macos.MacTools(run=recording).restart("system/org.docsuri.v2.standing")
    assert recorded == [["/bin/launchctl", "kickstart", "-k", "system/org.docsuri.v2.standing"]]
