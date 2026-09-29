"""The provisioner is root-only, fixed-path and bound to installed clock state."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "provision_receipts.py"
RELEASE = "r1-clock-20260927"
D = "sha256:" + "a" * 64


def load_provisioner():
    spec = importlib.util.spec_from_file_location("rem1_provision_receipts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60,
        check=False, input="")


def test_provisioning_requires_root(tmp_path):
    """An unprivileged caller gets a refusal, never a partial realm."""
    module = load_provisioner()
    with pytest.raises(PermissionError, match="root on macOS"):
        module.provision("test", RELEASE, "receipt-key-1", Path(sys.executable), 86400,
                         "a" * 32, ())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("arguments, expected", [
    (["--days", "8"], "receipt duration"),
    (["--days", "0"], "receipt duration"),
    (["--issuer", "/nonexistent/interpreter"], "issuer interpreter"),
    (["--capability", "nts_clock", "--capability", "nts_clock"], "duplicate capability"),
    (["--capability", "keychain_roles"], "not bindable to installed state"),
    (["--capability", "restore_receipt"], "not bindable to installed state"),
])
def test_invalid_arguments_are_refused_before_anything_is_prompted(tmp_path, arguments, expected):
    """No password prompt, no directory, no key: arguments are checked first."""
    result = run("--profile", "test", "--release", RELEASE, "--key-id", "receipt-key-1",
                 "--issuer", sys.executable, *arguments)
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["state"] == "BLOCKED"
    assert payload["stage"] == "arguments"
    assert expected in payload["detail"]
    assert not list(tmp_path.iterdir())


def test_read_regular_refuses_links_writable_files_and_oversize(tmp_path):
    module = load_provisioner()
    regular = tmp_path / "regular.json"
    regular.write_bytes(b"{}")
    assert module.read_regular(regular, 1024) == b"{}"
    regular.chmod(0o666)
    with pytest.raises(ValueError, match="unsafe artifact file"):
        module.read_regular(regular, 1024)
    regular.chmod(0o644)
    link = tmp_path / "link.json"
    link.symlink_to(regular)
    with pytest.raises(OSError):
        module.read_regular(link, 1024)
    with pytest.raises(ValueError, match="unsafe artifact file"):
        module.read_regular(regular, 1)


def test_installed_clock_refuses_a_different_release(tmp_path, monkeypatch):
    """The NTS artifact comes from installed state, so a mismatched manifest is refused."""
    module = load_provisioner()
    from docsuri_platform_integrity.contracts.codec import canonical
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE / "config").mkdir(parents=True)
    (root / "releases" / RELEASE / "runtime").mkdir()
    interpreter = root / "releases" / RELEASE / "runtime" / "python3.13"
    interpreter.write_bytes(b"#!/bin/false\n")
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True, exist_ok=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    chrony = root / "releases" / RELEASE / "config" / "chrony.conf"
    chrony.write_bytes(b"# chrony\n")
    from docsuri_platform_integrity.contracts.codec import digest

    manifest = launchd.LaunchManifest(
        profile="test", release=RELEASE, python=str(interpreter),
        entries=(launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608,
                                     mode="observer",
                                     argv=(str(chronyd), "-x", "-U", "-d",
                                           "-f", str(chrony))),),
        artifacts=((str(chrony), digest(chrony.read_bytes())),
                   (str(interpreter), digest(interpreter.read_bytes()))))
    (root / "deployment.json").write_bytes(canonical(manifest.model_dump(mode="json")))
    (root / "deployment.json").chmod(0o444)
    monkeypatch.setattr(module, "REALMS", {"test": root})
    monkeypatch.setattr(launchd, "REALMS", {"test": root})
    # The launch-manifest shape is the clock installer's own contract; these tests are about
    # what installed_clock derives from it.
    monkeypatch.setattr(module, "validate_manifest", lambda manifest: None)
    clock = module.installed_clock("test", RELEASE, owner=os.getuid())
    assert clock.config_digest == digest(chrony.read_bytes())
    assert clock.writer_uid == 608
    with pytest.raises(ValueError, match="different profile or release"):
        module.installed_clock("test", "r1-clock-other", owner=os.getuid())
    with pytest.raises(PermissionError, match="not root-owned"):
        module.installed_clock("test", RELEASE)


def test_installed_clock_refuses_configuration_that_drifted(tmp_path, monkeypatch):
    module = load_provisioner()
    from docsuri_platform_integrity.contracts.codec import canonical, digest
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE / "config").mkdir(parents=True)
    (root / "releases" / RELEASE / "runtime").mkdir()
    interpreter = root / "releases" / RELEASE / "runtime" / "python3.13"
    interpreter.write_bytes(b"#!/bin/false\n")
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True, exist_ok=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    chrony = root / "releases" / RELEASE / "config" / "chrony.conf"
    chrony.write_bytes(b"# chrony\n")
    manifest = launchd.LaunchManifest(
        profile="test", release=RELEASE, python=str(interpreter),
        entries=(launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608,
                                     mode="observer",
                                     argv=(str(chronyd), "-x", "-U", "-d",
                                           "-f", str(chrony))),),
        artifacts=((str(chrony), digest(b"different bytes")),
                   (str(interpreter), digest(interpreter.read_bytes()))))
    (root / "deployment.json").write_bytes(canonical(manifest.model_dump(mode="json")))
    (root / "deployment.json").chmod(0o444)
    monkeypatch.setattr(module, "REALMS", {"test": root})
    monkeypatch.setattr(launchd, "REALMS", {"test": root})
    # The launch-manifest shape is the clock installer's own contract; these tests are about
    # what installed_clock derives from it.
    monkeypatch.setattr(module, "validate_manifest", lambda manifest: None)
    with pytest.raises(ValueError, match="does not match its manifest"):
        module.installed_clock("test", RELEASE, owner=os.getuid())


def test_ensure_directory_refuses_another_owners_path(tmp_path):
    module = load_provisioner()
    path = tmp_path / "sign"
    path.mkdir()
    os.chown(path, 0, 0) if os.geteuid() == 0 else None
    if os.geteuid() == 0:
        with pytest.raises(PermissionError, match="another owner"):
            module.ensure_directory(path, uid=os.getuid() + 1, gid=os.getgid(), mode=0o700)
    else:
        module.ensure_directory(path, uid=os.getuid(), gid=os.getgid(), mode=0o700)
        assert stat.S_IMODE(path.lstat().st_mode) == 0o700
    regular = tmp_path / "file"
    regular.write_bytes(b"")
    with pytest.raises(PermissionError, match="another owner"):
        module.ensure_directory(regular, uid=os.getuid(), gid=os.getgid(), mode=0o700)


# -- the pinned config is the one chronyd is actually launched with -------


def _manifest(entries, artifacts, release=RELEASE, root=None):
    from docsuri_platform_integrity.contracts.codec import digest
    from docsuri_platform_integrity.deployment import launchd

    interpreter = root / "releases" / release / "runtime" / "python3.13"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_bytes(b"#!/bin/false\n")
    manifest = launchd.LaunchManifest(
        profile="test", release=release, python=str(interpreter),
        entries=tuple(entries), artifacts=tuple(artifacts) + (
            (str(interpreter), digest(interpreter.read_bytes())),))
    return manifest, interpreter


def test_the_pinned_config_follows_the_deployment_layout(tmp_path, monkeypatch):
    """A deployment that keeps chrony.conf at the release root must be accepted.

    The old check assumed releases/<release>/config/chrony.conf and so rejected a healthy,
    self-consistent clock simply because it stored the file one directory higher.
    """
    module = load_provisioner()
    from docsuri_platform_integrity.contracts.codec import canonical
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    chrony = root / "releases" / RELEASE / "chrony.conf"   # flat, no config/ subdir
    chrony.write_bytes(b"# chrony\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608, mode="observer",
                             argv=(str(chronyd), "-x", "-U", "-d", "-f", str(chrony)))],
        [(str(chrony), __import__("docsuri_platform_integrity.contracts.codec",
                                  fromlist=["digest"]).digest(chrony.read_bytes()))],
        root=root)
    (root / "deployment.json").write_bytes(canonical(manifest.model_dump(mode="json")))
    (root / "deployment.json").chmod(0o444)
    monkeypatch.setattr(module, "REALMS", {"test": root})
    monkeypatch.setattr(launchd, "REALMS", {"test": root})
    monkeypatch.setattr(module, "validate_manifest", lambda manifest: None)

    clock = module.installed_clock("test", RELEASE, owner=os.getuid())
    assert clock.config_digest == __import__(
        "docsuri_platform_integrity.contracts.codec", fromlist=["digest"]
    ).digest(chrony.read_bytes())


def test_chronyd_launched_with_a_config_outside_the_frozen_artifacts_is_refused(
        tmp_path, monkeypatch):
    from docsuri_platform_integrity.contracts.codec import canonical
    """A `-f` target the manifest does not pin must not be signed for."""
    module = load_provisioner()
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    unpinned = root / "releases" / RELEASE / "config" / "chrony.conf"
    unpinned.parent.mkdir(parents=True)
    unpinned.write_bytes(b"# attacker chosen\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608, mode="observer",
                             argv=(str(chronyd), "-f", str(unpinned), "-d"))],
        [], root=root)
    assert module.clock_config_argument(manifest) == str(unpinned)
    (root / "deployment.json").write_bytes(canonical(manifest.model_dump(mode="json")))
    (root / "deployment.json").chmod(0o444)
    monkeypatch.setattr(module, "REALMS", {"test": root})
    monkeypatch.setattr(launchd, "REALMS", {"test": root})
    monkeypatch.setattr(module, "validate_manifest", lambda m: None)
    with pytest.raises(ValueError, match="not uniquely pinned"):
        module.installed_clock("test", RELEASE, owner=os.getuid())


def test_chronyd_launched_with_a_config_that_is_not_chrony_conf_is_refused(tmp_path):
    """The `-f` target must actually be the chrony config, not an arbitrary pinned file."""
    module = load_provisioner()
    from docsuri_platform_integrity.contracts.codec import digest
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    decoy = root / "releases" / RELEASE / "innocent.conf"
    decoy.write_bytes(b"# not the clock config\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608, mode="observer",
                             argv=(str(chronyd), "-f", str(decoy), "-d"))],
        [(str(decoy), digest(decoy.read_bytes()))], root=root)
    with pytest.raises(ValueError, match="not launched with the expected configuration"):
        module.clock_config_argument(manifest)


def test_two_chronyd_entries_are_refused_as_ambiguous(tmp_path):
    """More than one clock config in force is not a uniquely pinned clock."""
    module = load_provisioner()
    from docsuri_platform_integrity.contracts.codec import digest
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    first = root / "releases" / RELEASE / "a" / "chrony.conf"
    second = root / "releases" / RELEASE / "b" / "chrony.conf"
    for path in (first, second):
        path.parent.mkdir(parents=True)
        path.write_bytes(b"# chrony\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name=f"clock-{n}", role="clock", uid=608, gid=608, mode="observer",
                             argv=(str(chronyd), "-f", str(cfg)))
         for n, cfg in (("a", first), ("b", second))],
        [(str(first), digest(first.read_bytes())), (str(second), digest(second.read_bytes()))],
        root=root)
    with pytest.raises(ValueError, match="not uniquely pinned"):
        module.clock_config_argument(manifest)


def test_chronyd_without_a_config_flag_is_refused(tmp_path):
    """A chronyd with no `-f` has no configuration we could pin."""
    module = load_provisioner()
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    chronyd = root / "releases" / RELEASE / "native" / "chronyd"
    chronyd.parent.mkdir(parents=True)
    chronyd.write_bytes(b"#!/bin/false\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name="nts-observer", role="clock", uid=608, gid=608, mode="observer",
                             argv=(str(chronyd), "-x", "-U", "-d"))],
        [], root=root)
    with pytest.raises(ValueError, match="not uniquely pinned"):
        module.clock_config_argument(manifest)


def test_an_entry_named_chronyd_in_a_later_position_does_not_count(tmp_path):
    """Only argv[0] is the executable; a `-f` value that merely ends in chronyd is not one."""
    module = load_provisioner()
    from docsuri_platform_integrity.deployment import launchd

    root = tmp_path / "realm"
    (root / "releases" / RELEASE).mkdir(parents=True)
    python = root / "releases" / RELEASE / "runtime" / "python3.13"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"#!/bin/false\n")
    chrony = root / "releases" / RELEASE / "chrony.conf"
    chrony.write_bytes(b"# chrony\n")
    manifest, _ = _manifest(
        [launchd.LaunchEntry(name="clock-sample", role="clock", uid=608, gid=608, mode="periodic",
                             argv=(str(python), "-m", "docsuri_platform_integrity.host",
                                   "clock", "--config", str(chrony)))],
        [], root=root)
    with pytest.raises(ValueError, match="not uniquely pinned"):
        module.clock_config_argument(manifest)
