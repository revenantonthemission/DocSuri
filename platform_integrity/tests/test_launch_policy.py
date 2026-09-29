"""Launch configuration is an immutable allowlist, never caller-supplied command text."""

import json
import os
import plistlib
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.deployment import launchd
from docsuri_platform_integrity.deployment.launchd import (
    MINIMAL_ENV,
    LaunchEntry,
    LaunchManifest,
    kernel_groups,
    launchd_plist,
    manifest_digest,
    validate_manifest,
)

ROOT = "/Library/Application Support/DocSuri/rem-1-test"
PYTHON = ROOT + "/toolchains/python313/bin/python3.13"
D = digest(b"frozen")


def entry(**changes):
    data = {"name": "reader", "role": "reader", "uid": 600, "gid": 600,
            "mode": "daemon", "interval": None,
            "argv": (PYTHON, "-I", "-B", "-m", "docsuri_platform_integrity.host",
                     "reader", "--config", ROOT + "/releases/r1/reader.json")}
    return LaunchEntry(**(data | changes))


def manifest(*entries):
    return LaunchManifest(profile="test", release="r1", python=PYTHON,
                          entries=entries or (entry(),),
                          artifacts=((PYTHON, D), (ROOT + "/releases/r1/reader.json", D)))


def test_reader_plist_uses_root_bootstrap_for_explicit_group_drop():
    value = manifest()
    validate_manifest(value)
    plist = plistlib.loads(launchd_plist(value, value.entries[0]))
    assert plist["UserName"] == "root"
    assert plist["GroupName"] == "wheel"
    assert plist["InitGroups"] is False
    assert plist["Umask"] == 0o077 and plist["KeepAlive"] is True
    assert plist["ProgramArguments"][:2] == ["/usr/bin/env", "-i"]
    assert plist["ProgramArguments"][5:9] == [PYTHON, "-I", "-B", "-m"]
    assert (value.entries[0].uid, value.entries[0].gid) == (600, 600)
    assert "RunAtLoad" in plist and "StartInterval" not in plist


def test_helpers_are_one_shot_and_never_auto_resumed():
    item = entry(name="tool", role="tool", uid=602, gid=602, mode="oneshot")
    value = manifest(item)
    result = plistlib.loads(launchd_plist(value, item))
    assert result["KeepAlive"] is False and result["RunAtLoad"] is False
    assert "StartInterval" not in result


@pytest.mark.parametrize("changes", [
    {"uid": 0}, {"gid": 0}, {"uid": True},
    {"role": "root"}, {"role": "tool", "mode": "daemon"},
    {"argv": ("/bin/sh", "-c", "id")},
    {"argv": (PYTHON, "-c", "print('arbitrary')")},
    {"argv": (PYTHON, "-I", "-B", "-m", "outside.module")},
    # Bytecode writes into the frozen closure invalidate the pinned artifact digests and leave
    # execute() unable to start, so -B is mandatory rather than merely accepted.
    {"argv": (PYTHON, "-I", "-m", "docsuri_platform_integrity.host", "reader",
              "--config", ROOT + "/releases/r1/chrony.conf")},
])
def test_invalid_or_unbounded_launches_are_rejected(changes):
    with pytest.raises(ValueError):
        validate_manifest(manifest(entry(**changes)))


def test_cross_realm_config_and_duplicate_artifact_cannot_be_published():
    item = entry(argv=(PYTHON, "-I", "-B", "-m", "docsuri_platform_integrity.host", "reader",
                       "--config", "/Library/Application Support/DocSuri/rem-1/reader.json"))
    with pytest.raises(ValueError):
        validate_manifest(manifest(item))
    value = manifest()
    with pytest.raises(ValueError):
        validate_manifest(value.model_copy(update={"artifacts": value.artifacts * 2}))


def test_configured_periodic_tasks_have_bounded_explicit_interval():
    item = entry(name="clock-sample", role="clock", uid=608, gid=608,
                 mode="periodic", interval=5)
    value = manifest(item)
    result = plistlib.loads(launchd_plist(value, item))
    assert result["StartInterval"] == 5 and result["KeepAlive"] is False
    assert result["RunAtLoad"] is False


def test_protected_manifest_reader_rejects_writable_and_symlinked_files(tmp_path):
    from docsuri_platform_integrity.deployment.launchd import protected_bytes

    file = tmp_path / "entry.json"
    file.write_bytes(b"{}")
    file.chmod(0o600)
    assert protected_bytes(file, owner=os.getuid()) == b"{}"
    file.chmod(0o666)
    with pytest.raises(PermissionError):
        protected_bytes(file, owner=os.getuid())
    link = tmp_path / "link.json"
    link.symlink_to(file)
    with pytest.raises((OSError, PermissionError)):
        protected_bytes(link, owner=os.getuid())


def test_full_runtime_manifest_has_an_explicit_sufficient_size_limit(tmp_path, monkeypatch):
    # A real clock closure has thousands of files; the generic 256 KiB config limit was too small.
    value = manifest()
    artifacts = value.artifacts + tuple(
        (ROOT + f"/toolchains/python313/lib/python3.13/module-{index}.py", D)
        for index in range(2500)
    )
    value = value.model_copy(update={"artifacts": artifacts})
    data = canonical(value.model_dump(mode="json"))
    assert 262_144 < len(data) < launchd.MANIFEST_MAX_BYTES
    path = tmp_path / "deployment.json"
    path.write_bytes(data)
    path.chmod(0o400)
    monkeypatch.setattr(launchd, "protected_chain", lambda path: None)
    monkeypatch.setattr(launchd.protected_bytes, "__kwdefaults__",
                        {"owner": os.getuid(), "limit": 262_144})
    assert launchd.read_manifest(path) == value


def test_manifest_paths_must_be_canonical():
    value = manifest()
    with pytest.raises(ValueError):
        validate_manifest(value.model_copy(update={"artifacts": ((ROOT + "/../bad", D),)}))
    assert Path(PYTHON).is_absolute()


def test_native_observer_uses_python_guard_then_fixed_non_adjusting_daemon():
    daemon = ROOT + "/toolchains/chrony/sbin/chronyd"
    config = ROOT + "/releases/r1/chrony.conf"
    observer = entry(name="nts-observer", role="clock", uid=608, gid=608,
                     mode="observer", argv=(daemon, "-x", "-U", "-d", "-f", config))
    value = manifest(observer).model_copy(update={"artifacts": ((PYTHON, D), (daemon, D),
                                                                (config, D))})
    result = plistlib.loads(launchd_plist(value, observer))
    assert result["ProgramArguments"][5] == PYTHON
    assert result["KeepAlive"] is False and result["RunAtLoad"] is True



def test_manifest_rejects_ambiguous_or_unbound_launch_authorization():
    with pytest.raises(ValueError, match="duplicate launch entry"):
        validate_manifest(manifest(entry(), entry()))
    value = manifest()
    with pytest.raises(ValueError, match="interpreter digest missing"):
        validate_manifest(value.model_copy(update={"artifacts": (value.artifacts[1],)}))
    with pytest.raises(ValueError, match="role identity changed"):
        validate_manifest(manifest(entry(), entry(name="reader-b", mode="oneshot",
                                                   uid=610, gid=610)))
    with pytest.raises(ValueError, match="share an identity"):
        validate_manifest(manifest(entry(), entry(name="runner", role="runner", uid=600, gid=601)))
    with pytest.raises(ValueError, match="periodic entry requires explicit interval"):
        validate_manifest(manifest(entry(interval=5)))
    with pytest.raises(ValueError, match="periodic entry requires explicit interval"):
        validate_manifest(manifest(entry(mode="periodic", interval=None)))


def test_manifest_rejects_observer_and_argument_authority_gaps():
    daemon = ROOT + "/toolchains/chrony/sbin/chronyd"
    config = ROOT + "/releases/r1/chrony.conf"
    artifacts = ((PYTHON, D), (daemon, D), (config, D))
    for argv in (
        (daemon, "-x", "-U", "-d", "-f"),                            # too few arguments
        (daemon, "-x", "-U", "-d", "-f", ROOT + "/releases/r1/absent.conf"),
        (daemon, "-U", "-d", "-f", config),                           # adjustment not disabled
        (PYTHON, "-I", "-B", "-m"),                                     # too few arguments
        (PYTHON, "-I", "-B", "-m", "docsuri_platform_integrity.host"),   # too few arguments
    ):
        item = entry(name="nts-observer", role="clock", uid=608, gid=608,
                     mode="observer", argv=argv)
        with pytest.raises(ValueError):
            validate_manifest(LaunchManifest(profile="test", release="r1", python=PYTHON,
                                             entries=(item,), artifacts=artifacts))
    item = entry(name="reader-observer", role="reader", uid=600, gid=600, mode="observer",
                 argv=(daemon, "-x", "-U", "-d", "-f", config))
    with pytest.raises(ValueError):
        validate_manifest(LaunchManifest(profile="test", release="r1", python=PYTHON,
                                         entries=(item,), artifacts=artifacts))


def test_artifact_paths_reject_traversal_other_releases_and_control_characters():
    value = manifest()
    for name in (ROOT + "/releases/r2/reader.json", ROOT + "/roles/reader.json",
                 ROOT + "/releases/r1/../../etc/passwd", ROOT + "/releases/r1/a\nb"):
        with pytest.raises(ValueError):
            validate_manifest(value.model_copy(update={"artifacts": ((PYTHON, D), (name, D))}))


def test_kernel_group_observation_is_available_on_this_host():
    assert isinstance(kernel_groups(), tuple)


@pytest.fixture
def frozen_realm(tmp_path, monkeypatch):
    """Materialize a protected realm and simulate the already-dropped process.

    Only root-ownership expectations are substituted for the unprivileged suite; the
    regular-file, mode, hardlink, size, digest, identity and argv checks all run for real.
    """
    uid, gid = os.getuid(), os.getgid()
    realm = tmp_path / "rem-1-test"
    (realm / "reader").mkdir(parents=True)
    python = realm / "toolchains/python313/bin/python3.13"
    config = realm / "releases/r1/reader.json"
    for path in (python, config):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"frozen artifact")
    python.chmod(0o555)
    config.chmod(0o400)
    value = LaunchManifest(profile="test", release="r1", python=str(python),
                           entries=(entry(uid=uid, gid=gid,
                                          argv=(str(python), "-I", "-B", "-m",
                                                "docsuri_platform_integrity.host", "reader",
                                                "--config", str(config))),),
                           artifacts=((str(python), digest(python.read_bytes())),
                                      (str(config), digest(config.read_bytes()))))
    deployment = realm / "deployment.json"
    deployment.write_bytes(canonical(value.model_dump(mode="json")))
    deployment.chmod(0o400)

    shim = SimpleNamespace(**{name: getattr(os, name)
                              for name in dir(os) if not name.startswith("_")})
    for name in ("getuid", "geteuid"):
        setattr(shim, name, lambda: uid)
    for name in ("getgid", "getegid"):
        setattr(shim, name, lambda: gid)
    monkeypatch.setattr(launchd, "os", shim)
    monkeypatch.setattr(launchd, "REALMS", {"test": realm, "production": realm})
    monkeypatch.setattr(launchd.protected_bytes, "__kwdefaults__", {"owner": uid, "limit": 262_144})
    monkeypatch.setattr(launchd, "protected_chain", lambda path: None)
    monkeypatch.setattr(launchd, "kernel_groups", lambda: (gid,))
    monkeypatch.setattr(launchd.pwd, "getpwnam",
                        lambda name: SimpleNamespace(pw_uid=uid, pw_gid=gid))
    monkeypatch.setattr(launchd.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=gid))
    umask, previous = os.umask(0o077), os.getcwd()
    os.chdir(realm)
    yield launchd, value, deployment, shim
    os.chdir(previous)
    os.umask(umask)


def test_execute_verifies_digest_identity_and_groups_before_execve(frozen_realm):
    launchd, value, _, shim = frozen_realm
    executed = {}
    shim.execve = lambda path, argv, env: executed.update(path=path, argv=argv, env=env)
    launchd.execute("test", "reader", manifest_digest(value))
    assert executed["path"] == value.python
    assert executed["argv"] == list(value.entries[0].argv)
    assert executed["env"] == MINIMAL_ENV
    assert os.umask(0o022) == 0o077


@pytest.fixture
def root_bootstrap(frozen_realm, monkeypatch):
    module, value, deployment, shim = frozen_realm
    state = {"uid": 0, "euid": 0, "gid": 0, "egid": 0, "groups": [0, 12, 61, 100]}
    calls = []
    for field in ("uid", "euid", "gid", "egid"):
        setattr(shim, "get" + field, lambda field=field: state[field])

    def clear(groups):
        calls.append("setgroups")
        state["groups"] = list(groups)

    def setgid(gid):
        calls.append("setgid")
        state.update(gid=gid, egid=gid)

    def setuid(uid):
        calls.append("setuid")
        state.update(uid=uid, euid=uid)

    def execve(path, argv, env):
        calls.append("execve")
        target = value.entries[0]
        assert (state["uid"], state["euid"], state["gid"], state["egid"]) == (
            target.uid, target.uid, target.gid, target.gid,
        )
        assert state["groups"] == []

    shim.setgroups, shim.setgid, shim.setuid, shim.execve = clear, setgid, setuid, execve
    monkeypatch.setattr(module, "kernel_groups", lambda: tuple(state["groups"] + [state["gid"]]))
    return module, value, deployment, shim, state, calls


def test_root_bootstrap_clears_groups_before_dropping_and_executing(root_bootstrap):
    module, value, _, _, _, calls = root_bootstrap
    module.execute("test", "reader", manifest_digest(value))
    assert calls == ["setgroups", "setgid", "setuid", "execve"]


@pytest.mark.parametrize("failed", ["setgroups", "setgid", "setuid"])
def test_privilege_drop_failure_never_executes_target(root_bootstrap, failed):
    module, value, _, shim, _, calls = root_bootstrap

    def refusal(*args):
        calls.append(failed)
        raise PermissionError("injected credential-drop failure")

    setattr(shim, failed, refusal)
    with pytest.raises(PermissionError, match="credential-drop failure"):
        module.execute("test", "reader", manifest_digest(value))
    assert calls == ["setgroups", "setgid", "setuid"][:
        ["setgroups", "setgid", "setuid"].index(failed) + 1
    ]


def test_root_bootstrap_refuses_residual_supplementary_groups(root_bootstrap):
    module, value, _, shim, _, calls = root_bootstrap
    shim.setgroups = lambda groups: calls.append("setgroups")  # Failed to clear kernel credentials.
    with pytest.raises(PermissionError, match="role boundary"):
        module.execute("test", "reader", manifest_digest(value))
    assert calls == ["setgroups", "setgid", "setuid"]


def test_root_bootstrap_verifies_artifacts_before_any_credential_change(root_bootstrap):
    module, value, _, _, _, calls = root_bootstrap
    artifact = Path(value.python)
    artifact.chmod(0o644)
    artifact.write_bytes(b"changed")
    with pytest.raises(PermissionError, match="artifact verification"):
        module.execute("test", "reader", manifest_digest(value))
    assert calls == []


def test_execute_refuses_changed_manifest_unknown_entry_and_installed_identity(frozen_realm,
                                                                               monkeypatch):
    launchd_module, value, _, shim = frozen_realm
    shim.execve = lambda *args: pytest.fail("must not execve")
    with pytest.raises(PermissionError, match="deployment manifest changed"):
        launchd_module.execute("test", "reader", digest(b"other"))
    with pytest.raises(PermissionError, match="unknown launch entry"):
        launchd_module.execute("test", "absent", manifest_digest(value))
    monkeypatch.setattr(launchd_module.pwd, "getpwnam",
                        lambda name: SimpleNamespace(pw_uid=os.getuid() + 1, pw_gid=os.getgid()))
    with pytest.raises(PermissionError, match="installed identity differs"):
        launchd_module.execute("test", "reader", manifest_digest(value))


def test_execute_refuses_unfrozen_artifact_writable_manifest_and_extra_group(frozen_realm,
                                                                              monkeypatch):
    launchd_module, value, deployment, shim = frozen_realm
    shim.execve = lambda *args: pytest.fail("must not execve")
    frozen = launchd_module.artifact_path(value, value.entries[0].argv[0])
    frozen.chmod(0o644)
    frozen.write_bytes(b"tampered")
    frozen.chmod(0o555)
    with pytest.raises(PermissionError, match="frozen artifact verification failed"):
        launchd_module.execute("test", "reader", manifest_digest(value))

    deployment.chmod(0o666)
    with pytest.raises(PermissionError, match="unprotected runtime artifact"):
        launchd_module.execute("test", "reader", manifest_digest(value))
    deployment.chmod(0o400)
    frozen.chmod(0o644)
    frozen.write_bytes(b"frozen artifact")
    frozen.chmod(0o555)

    monkeypatch.setattr(launchd_module, "kernel_groups", lambda: (os.getgid(), 12, 61))
    with pytest.raises(PermissionError, match="role boundary"):
        launchd_module.execute("test", "reader", manifest_digest(value))


def test_render_command_writes_plists_and_reports_generated_not_installed(frozen_realm, tmp_path,
                                                                         capsys, monkeypatch):
    launchd_module, value, deployment, _ = frozen_realm
    destination = tmp_path / "out"
    monkeypatch.setattr(launchd_module.sys, "argv",
                        ["launchd", "render", str(deployment), str(destination)])
    assert launchd_module.main() == 0
    assert json.loads(capsys.readouterr().out) == {"state": "GENERATED_NOT_INSTALLED",
                                                   "manifestDigest": manifest_digest(value),
                                                   "entries": 1}
    assert sorted(path.name for path in destination.iterdir()) == ["deployment.json",
                                                         "reader.plist"]
    rendered = destination / "deployment.json"
    assert rendered.read_bytes() == canonical(value.model_dump(mode="json"))


def test_commands_fail_closed_when_output_exists_or_authority_is_wrong(frozen_realm, tmp_path,
                                                                       capsys, monkeypatch):
    launchd_module, _, deployment, _ = frozen_realm
    blocked = {"state": "BLOCKED", "reason": "native_launch_unavailable"}
    destination = tmp_path / "out"
    destination.mkdir()
    monkeypatch.setattr(launchd_module.sys, "argv",
                        ["launchd", "render", str(deployment), str(destination)])
    assert launchd_module.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert {key: report[key] for key in ("state", "reason")} == blocked
    # The envelope must name the failing call; a bare reason hides it behind a rebuild.
    assert report["errorType"] == "FileExistsError" and "out" in report["detail"]
    monkeypatch.setattr(launchd_module.sys, "argv", ["launchd", "exec", "--profile", "test",
                                                     "--entry", "reader",
                                                     "--manifest-digest", digest(b"x")])
    assert launchd_module.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert {key: report[key] for key in ("state", "reason")} == blocked
    assert report["errorType"] and report["detail"]


@pytest.fixture
def installable_realm(frozen_realm, tmp_path, monkeypatch):
    """A realm plus a root-only stand-in for the launchd system directory.

    The manifest, artifact digest, identity, mode, symlink, ordering and launchctl
    arguments all run for real. Only what an unprivileged suite cannot own is
    substituted: the root uid, chown, the root-owned /Library/LaunchDaemons parent,
    and launchctl itself. launchctl is replaced by a recorder, so no job is ever
    actually bootstrapped on this host.
    """
    launchd_module, value, deployment, shim = frozen_realm
    # frozen_realm seeds the realm deployment.json for the exec tests. An install run must
    # start from an empty realm and be driven by a separately reviewed manifest, which is
    # how the operator flow works: render, review, then install.
    assert deployment.read_bytes() == canonical(value.model_dump(mode="json"))
    staged = tmp_path / "reviewed-deployment.json"
    staged.write_bytes(canonical(value.model_dump(mode="json")))
    staged.chmod(0o400)
    (launchd_module.REALMS["test"] / "deployment.json").unlink()
    daemons = tmp_path / "LaunchDaemons"
    daemons.mkdir()
    calls = []
    monkeypatch.setattr(launchd_module, "LAUNCH_DAEMONS", daemons)
    monkeypatch.setattr(launchd_module, "LAUNCHCTL", daemons / "launchctl")
    (daemons / "launchctl").write_bytes(b"#!/bin/sh\n")
    (daemons / "launchctl").chmod(0o555)
    for name in ("getuid", "geteuid"):
        setattr(shim, name, lambda: 0)
    shim.chown = lambda path, uid, gid: None

    # An unprivileged suite cannot create root-owned files, so the two things this fake
    # installer publishes -- the plists under LaunchDaemons and the realm deployment.json
    # -- are reported as root:wheel. Only ownership is substituted, so the "never clobber a
    # file root does not own" guard and the actual mode checks still run for real.
    real_lstat = os.lstat
    published = (daemons / "org.docsuri.rem1.test.reader.plist",
                 launchd_module.REALMS["test"] / "deployment.json")

    def lstat(path, *arguments, **keywords):
        value = real_lstat(path, *arguments, **keywords)
        if Path(path) in published:
            return SimpleNamespace(st_mode=value.st_mode, st_uid=0, st_nlink=value.st_nlink,
                                   st_gid=0, st_size=value.st_size)
        return value

    shim.lstat = lstat

    loaded = set()

    def record(*arguments):
        calls.append(arguments[0])
        label = arguments[-1]
        if arguments[0] == "bootstrap":
            loaded.add(Path(label).stem)
        elif arguments[0] == "bootout":
            loaded.discard(label.split("/", 1)[-1])
        return ""

    def bootout(profile_name, labels):
        calls.append("bootout")
        for label in labels:
            loaded.discard(label)

    monkeypatch.setattr(launchd_module, "launchctl", record)
    monkeypatch.setattr(launchd_module, "is_loaded", lambda label: label in loaded)
    monkeypatch.setattr(launchd_module, "bootout", bootout)
    return launchd_module, value, staged, daemons, SimpleNamespace(calls=calls, loaded=loaded)


def test_install_verifies_then_bootstraps_every_frozen_entry(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    result = launchd_module.install("test", deployment)
    assert result["state"] == "INSTALLED" and result["labels"] == ["org.docsuri.rem1.test.reader"]
    assert result["manifestDigest"] == manifest_digest(value)
    assert control.calls == ["bootstrap"]
    written = daemons / "org.docsuri.rem1.test.reader.plist"
    assert written.read_bytes() == launchd_plist(value, value.entries[0])
    assert stat.S_IMODE(written.stat().st_mode) == launchd_module.PLIST_MODE
    assert (launchd_module.REALMS["test"] / "deployment.json").read_bytes() == \
        canonical(value.model_dump(mode="json"))


def test_published_manifest_is_readable_but_not_writable_by_service_roles(installable_realm):
    launchd_module, value, deployment, _, _ = installable_realm
    launchd_module.install("test", deployment)
    path = launchd_module.REALMS["test"] / "deployment.json"
    info = launchd_module.os.lstat(path)
    for item in value.entries:
        assert item.uid != info.st_uid and item.gid != info.st_gid
        # Root ownership is simulated, but these are the real on-disk mode bits. Reading as
        # the fixture's owner would hide the 0400 regression experienced by the native UID.
        assert info.st_mode & stat.S_IROTH
        assert not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    assert path.read_bytes() == canonical(value.model_dump(mode="json"))


@pytest.mark.parametrize("mode", [0o400, 0o440, 0o644])
def test_install_repairs_same_digest_manifest_access_mode(installable_realm, mode):
    launchd_module, value, deployment, _, control = installable_realm
    launchd_module.install("test", deployment)
    path = launchd_module.REALMS["test"] / "deployment.json"
    before = path.read_bytes()
    path.chmod(mode)
    control.calls.clear()
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    assert control.calls == ["bootout", "bootstrap"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert path.read_bytes() == before
    control.calls.clear()
    assert launchd_module.install("test", deployment)["state"] == "ALREADY_INSTALLED"
    assert control.calls == []


def test_install_is_idempotent_and_refuses_silent_replacement(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    control.calls.clear()
    assert launchd_module.install("test", deployment)["state"] == "ALREADY_INSTALLED"
    assert control.calls == []

    # A genuinely different deployment: same frozen artifacts, reader downgraded to
    # oneshot, so the manifest digest differs.
    other = value.model_copy(update={"entries": (value.entries[0].model_copy(
        update={"mode": "oneshot"}),)})
    changed = deployment.with_name("other.json")
    changed.write_bytes(canonical(other.model_dump(mode="json")))
    changed.chmod(0o400)
    control.calls.clear()
    with pytest.raises(PermissionError, match="already installed"):
        launchd_module.install("test", changed)
    assert control.calls == []
    # --replace boots the previous deployment out before publishing the new one.
    assert launchd_module.install("test", changed, replace=True)["state"] == "INSTALLED"
    assert control.calls == ["bootout", "bootstrap"]


def test_install_refuses_before_writing_when_anything_is_unproven(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    frozen = launchd_module.artifact_path(value, value.entries[0].argv[0])
    frozen.chmod(0o644)
    frozen.write_bytes(b"tampered")
    frozen.chmod(0o555)
    with pytest.raises(PermissionError, match="frozen artifact"):
        launchd_module.install("test", deployment)
    assert control.calls == [] and list(daemons.iterdir()) == [daemons / "launchctl"]
    assert not (launchd_module.REALMS["test"] / "deployment.json").exists()

    frozen.chmod(0o644)
    frozen.write_bytes(b"frozen artifact")
    frozen.chmod(0o555)
    monkeypatch.setattr(launchd_module.pwd, "getpwnam",
                        lambda name: SimpleNamespace(pw_uid=os.getuid() + 7,
                                                     pw_gid=os.getgid()))
    with pytest.raises(PermissionError, match="identity differs"):
        launchd_module.install("test", deployment)
    assert control.calls == [] and not (launchd_module.REALMS["test"] / "deployment.json").exists()


def test_install_requires_root_and_refuses_a_foreign_manifest(installable_realm, monkeypatch):
    launchd_module, value, deployment, _, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    monkeypatch.setattr(launchd_module.os, "getuid", lambda: os.getuid() or 501)
    with pytest.raises(PermissionError, match="requires root"):
        launchd_module.install("test", deployment)
    monkeypatch.setattr(launchd_module.os, "getuid", lambda: 0)
    monkeypatch.setattr(launchd_module.os, "geteuid", lambda: 0)
    production = deployment.with_name("production.json")
    rebased = value.model_copy(update={"profile": "production"})
    production.write_bytes(canonical(rebased.model_dump(mode="json")))
    production.chmod(0o400)
    with pytest.raises(PermissionError, match="another realm"):
        launchd_module.install("test", production)
    assert control.calls == []


def test_install_refuses_to_write_through_a_symlinked_launchd_file(installable_realm,
                                                                  monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    target = daemons / "elsewhere.plist"
    target.write_bytes(b"do not touch")
    (daemons / "org.docsuri.rem1.test.reader.plist").symlink_to(target)
    with pytest.raises(PermissionError, match="symlink"):
        launchd_module.install("test", deployment)
    assert target.read_bytes() == b"do not touch"
    assert control.calls == []


def test_uninstall_bootouts_and_removes_only_its_own_files(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    launchd_module.install("test", deployment)
    foreign = daemons / "com.example.keepme.plist"
    foreign.write_bytes(launchd_plist(value, value.entries[0]).replace(
        b"org.docsuri.rem1.test.reader", b"com.example.keepme"))
    control.calls.clear()
    result = launchd_module.uninstall("test")
    assert result == {"state": "UNINSTALLED", "labels": ["org.docsuri.rem1.test.reader"]}
    assert control.calls == ["bootout"]
    assert sorted(path.name for path in daemons.iterdir()) == ["com.example.keepme.plist",
                                                              "launchctl"]
    assert not (launchd_module.REALMS["test"] / "deployment.json").exists()


def test_uninstall_refuses_a_swapped_plist_and_leaves_it_in_place(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    launchd_module.install("test", deployment)
    target = daemons / "org.docsuri.rem1.test.reader.plist"
    target.unlink()
    target.write_bytes(launchd_plist(value, value.entries[0]).replace(
        b"org.docsuri.rem1.test.reader", b"com.example.impostor"))
    with pytest.raises(PermissionError, match="foreign launchd file"):
        launchd_module.uninstall("test")
    assert target.is_file()


def test_install_cli_reports_state_and_fails_closed_without_root(installable_realm, capsys,
                                                                 monkeypatch):
    launchd_module, value, deployment, _, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    monkeypatch.setattr(launchd_module.sys, "argv",
                        ["launchd", "install", "--profile", "test", str(deployment)])
    assert launchd_module.main() == 0
    assert json.loads(capsys.readouterr().out)["state"] == "INSTALLED"
    monkeypatch.setattr(launchd_module.os, "getuid", lambda: os.getuid() or 501)
    monkeypatch.setattr(launchd_module.os, "geteuid", lambda: os.getuid() or 501)
    monkeypatch.setattr(launchd_module.sys, "argv",
                        ["launchd", "uninstall", "--profile", "test"])
    assert launchd_module.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "BLOCKED" and report["reason"] == "native_launch_unavailable"
    assert report["errorType"] == "PermissionError"
    assert report["detail"] == "installer requires root"


def test_install_repairs_a_drifted_or_half_removed_deployment(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    plist = daemons / "org.docsuri.rem1.test.reader.plist"

    # A plist that was edited after install must not be trusted as installed. The job is
    # stopped before the correct bytes are republished, so a drifted job is never left
    # running alongside the repair.
    plist.unlink()
    plist.write_bytes(launchd_plist(value, value.entries[0]).replace(b"Umask", b"umask"))
    control.calls.clear()
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    assert plist.read_bytes() == launchd_plist(value, value.entries[0])
    assert control.calls == ["bootout", "bootstrap"]

    # A manifest still present but every job gone from launchd must be re-bootstrapped,
    # and the installer must refuse to report success if launchd will not hold the job.
    control.loaded.clear()
    control.calls.clear()
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    assert control.calls == ["bootout", "bootstrap"]

    monkeypatch.setattr(launchd_module, "is_loaded", lambda label: False)
    with pytest.raises(RuntimeError, match="did not verify"):
        launchd_module.install("test", deployment, replace=True)


def test_uninstall_refuses_to_orphan_a_job_launchd_still_holds(installable_realm, monkeypatch):
    launchd_module, value, deployment, daemons, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    launchd_module.install("test", deployment)
    plist = daemons / "org.docsuri.rem1.test.reader.plist"
    monkeypatch.setattr(launchd_module, "bootout", lambda *arguments: None)
    with pytest.raises(RuntimeError, match="still holds jobs"):
        launchd_module.uninstall("test")
    assert plist.is_file() and (launchd_module.REALMS["test"] / "deployment.json").is_file()


def test_replace_migrates_a_published_manifest_this_release_cannot_validate(
        installable_realm, monkeypatch):
    """A deployment written before a validator tightened must still be replaceable.

    The published manifest is compared and read for labels, never re-validated against today's
    rules. Validating it strictly means a release that adds a rule can never migrate the very
    deployment it is replacing, which is the one case --replace exists for.
    """
    launchd_module, value, deployment, _, control = installable_realm
    monkeypatch.setattr(launchd_module, "protected_chain", lambda path: None)
    assert launchd_module.install("test", deployment)["state"] == "INSTALLED"
    published = launchd_module.REALMS["test"] / "deployment.json"
    published.chmod(0o644)  # the fixture's fake root install left it 0444 and root-simulated
    legacy = value.model_copy(update={"entries": (value.entries[0].model_copy(
        update={"argv": tuple(a for a in value.entries[0].argv if a != "-B")}),)})
    published.write_bytes(canonical(legacy.model_dump(mode="json")))
    # The stale document is genuinely unreadable by today's validator ...
    with pytest.raises(ValueError, match="executable entry"):
        launchd_module.read_manifest(published)
    # ... yet it can still be identified, and its jobs retired.
    assert launchd_module.installed_digest("test") != launchd_module.manifest_digest(value)
    assert launchd_module.published_labels("test", published) == [
        launchd_module.entry_label("test", value.entries[0])]
    control.calls.clear()
    assert launchd_module.install("test", deployment, replace=True)["state"] == "INSTALLED"
    assert control.calls == ["bootout", "bootstrap"]


def _bootout_result(returncode, stderr):
    return SimpleNamespace(returncode=returncode, stderr=stderr, stdout="")


def test_bootout_never_calls_launchctl_for_a_label_it_does_not_hold(monkeypatch):
    """Retiring an absent job is success; launchctl is not even consulted."""
    monkeypatch.setattr(launchd, "is_loaded", lambda label: False)
    attempted = []
    monkeypatch.setattr(launchd.subprocess, "run", lambda *a, **k: attempted.append(a[0]))
    launchd.bootout("test", ["org.docsuri.rem1.test.absent"])
    assert attempted == []


def test_bootout_tolerates_a_job_that_unloads_concurrently(monkeypatch):
    """A bootout reported as failed only because the job already vanished is still success."""
    state = {"loaded": True}
    monkeypatch.setattr(launchd, "is_loaded", lambda label: state["loaded"])

    def run(*arguments, **keywords):
        state["loaded"] = False
        return _bootout_result(1, "Boot-out failed: 113: Could not find service")

    monkeypatch.setattr(launchd.subprocess, "run", run)
    launchd.bootout("test", ["org.docsuri.rem1.test.racing"])


def test_bootout_still_raises_when_the_job_survives_the_call(monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda label: True)
    monkeypatch.setattr(
        launchd.subprocess, "run",
        lambda *a, **k: _bootout_result(1, "Boot-out failed: 1: Operation not permitted"))
    with pytest.raises(RuntimeError, match="bootout failed"):
        launchd.bootout("test", ["org.docsuri.rem1.test.stuck"])


def test_cli_failure_reports_the_underlying_error(installable_realm, monkeypatch, capsys):
    """The failure envelope must name the failing call, not just a generic reason.

    An opaque reason has repeatedly hidden the real defect behind a bundle rebuild.
    """
    launchd_module, _, deployment, _, _ = installable_realm

    def refuse(*arguments, **keywords):
        raise ValueError("no such entry")

    monkeypatch.setattr(launchd_module, "install", refuse)
    monkeypatch.setattr(sys, "argv", ["launchd", "install", "--profile", "test", str(deployment)])
    assert launchd_module.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "native_launch_unavailable"
    assert report["errorType"] == "ValueError" and report["detail"] == "no such entry"
