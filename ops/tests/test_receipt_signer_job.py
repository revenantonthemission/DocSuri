"""The sign-role launchd job establishes exactly one kernel group, and refuses everything else."""

import importlib.util
import os
import plistlib
import stat
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "receipt_signer_job.py"
D = "sha256:" + "b" * 64


def load_job():
    spec = importlib.util.spec_from_file_location("rem1_receipt_signer_job", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def job_mod():
    return load_job()


def credential(mod, uid=604, euid=604, gid=604, egid=604, groups=(604,)):
    return mod.Credential(uid, euid, gid, egid, tuple(groups))


def test_check_role_boundary_accepts_the_exact_sign_identity(job_mod):
    # The success case the whole job exists to produce: one uid, one gid, one group.
    job_mod.check_role_boundary(604, 604, credential(job_mod))


def test_check_role_boundary_rejects_extra_kernel_groups(job_mod):
    # This is the real-world failure: a Darwin account always carries directory groups.
    with pytest.raises(job_mod.SignerUnavailable) as error:
        job_mod.check_role_boundary(604, 604, credential(job_mod, groups=(604, 12, 80)))
    assert "extra kernel groups [12, 80]" in str(error.value)


def test_check_role_boundary_rejects_a_directory_group_alone(job_mod):
    with pytest.raises(job_mod.SignerUnavailable, match=r"extra kernel groups \[12\]"):
        job_mod.check_role_boundary(604, 604, credential(job_mod, groups=(12,)))


def test_check_role_boundary_rejects_escalated_credentials(job_mod):
    with pytest.raises(job_mod.SignerUnavailable, match="role identity not established"):
        job_mod.check_role_boundary(604, 604, credential(job_mod, euid=0))


def test_check_role_boundary_rejects_the_wrong_role(job_mod):
    # A job that landed in a different role entirely must not be able to sign; comparing the
    # credential against the expected role rather than against itself is what catches this.
    with pytest.raises(job_mod.SignerUnavailable, match="role identity not established"):
        job_mod.check_role_boundary(604, 604, credential(
            job_mod, uid=608, euid=608, gid=608, egid=608, groups=(608,)))


def test_check_role_boundary_rejects_a_mismatched_gid(job_mod):
    with pytest.raises(job_mod.SignerUnavailable, match="role identity not established"):
        job_mod.check_role_boundary(604, 604, credential(job_mod, gid=80, egid=80, groups=(80,)))


def test_credential_records_every_kernel_field(job_mod):
    # Nothing here is caller-supplied: uid, euid, gid, egid and the group set all come from the
    # kernel, which is why a root-owned header cannot widen them.
    observed = job_mod.Credential(1, 1, 2, 2, (2, 3))
    assert observed.uid == observed.euid and observed.gid == observed.egid
    assert observed.groups == (2, 3)


def test_drop_to_role_refuses_when_not_already_the_role(job_mod):
    # Unprivileged the syscalls are skipped and the verification must still fail closed rather
    # than letting the caller's own account proceed to sign.
    if os.geteuid() == 0:
        pytest.skip("root would actually transition")
    with pytest.raises(job_mod.SignerUnavailable):
        job_mod.drop_to_role(604, 604)


def test_job_argv_sanitises_the_environment_and_honours_pythonpath(job_mod):
    argv = job_mod.job_argv(
        interpreter=Path("/clock/python3.13"), bootstrap=Path("/realm/signer/bootstrap.py"),
        library=Path("/realm/signer/lib"), state=Path("/realm/signer/job_mod.json"),
        arguments=["--release", "r1t-clock-20260927", "--scope", "nts_clock"],
    )
    # `env -i` must come first, or the launchd environment survives into the signing process.
    assert argv[0:2] == ["/usr/bin/env", "-i"]
    assert f"PYTHONPATH={Path('/realm/signer/lib')}" in argv
    assert argv[argv.index("--state") + 1] == "/realm/signer/job_mod.json"
    # Fixed trailing arguments, with no shell anywhere in the chain.
    assert argv[-4:] == ["--release", "r1t-clock-20260927", "--scope", "nts_clock"]
    assert all("|" not in item and ";" not in item for item in argv)
    # `-I` is deliberately absent: it would imply -E and silently discard PYTHONPATH, which is
    # the failure mode that would let the stale bundled library be imported instead.
    assert "-I" not in argv
    assert "-B" in argv


def test_job_argv_never_uses_a_shell(job_mod):
    argv = job_mod.job_argv(
        interpreter=Path("/clock/python3.13"), bootstrap=Path("/s/bootstrap.py"),
        library=Path("/s/lib"), state=Path("/s/job_mod.json"), arguments=[])
    assert argv.count("/usr/bin/env") == 1
    assert not any(item.endswith(("-sh", "bash", "zsh")) for item in argv)


def test_signer_job_plist_uses_the_root_bootstrap_pattern(job_mod):
    plist = plistlib.loads(job_mod.signer_job_plist(
        label="org.docsuri.test.receipt-sign", argv=["/usr/bin/env", "-i", "true"],
        working_directory=Path("/realm/signer/results"),
        stdout=Path("/realm/signer/results/job_mod.out"),
        stderr=Path("/realm/signer/results/job_mod.err"),
    ))
    # Runs as root only to clear groups, and must not ask launchd to build a group list.
    assert plist["UserName"] == "root"
    assert plist["GroupName"] == "wheel"
    assert plist["InitGroups"] is False
    assert plist["Umask"] == 0o077
    # One-shot: it issues a single receipt and must not come back on its own.
    assert plist["RunAtLoad"] is False
    assert "KeepAlive" not in plist
    assert plist["ExitTimeOut"] == 30
    assert plist["HardResourceLimits"]["Core"] == 0


def test_signer_job_plist_writes_results_into_the_sign_realm(job_mod):
    plist = plistlib.loads(job_mod.signer_job_plist(
        label="org.docsuri.test.receipt-sign", argv=["/usr/bin/env", "-i", "true"],
        working_directory=Path("/realm/signer/results"),
        stdout=Path("/realm/signer/results/job_mod.out"),
        stderr=Path("/realm/signer/results/job_mod.err"),
    ))
    for key in ("WorkingDirectory", "StandardOutPath", "StandardErrorPath"):
        assert plist[key].startswith("/realm/signer/results")


def test_signer_job_plist_omits_stdin_when_no_password_source_is_bound(job_mod):
    plist = plistlib.loads(job_mod.signer_job_plist(
        label="org.docsuri.test.receipt-sign", argv=["/usr/bin/env", "-i", "true"],
        working_directory=Path("/realm/signer/results"),
        stdout=Path("/realm/signer/results/job.out"), stderr=Path("/realm/signer/results/job.err"),
    ))
    # An attended job must not inherit whatever stdin it happened to be given.
    assert "StandardInPath" not in plist


def test_signer_job_plist_wires_the_password_source_to_stdin(job_mod):
    plist = plistlib.loads(job_mod.signer_job_plist(
        label="org.docsuri.test.receipt-sign", argv=["/usr/bin/env", "-i", "true"],
        working_directory=Path("/realm/signer/results"),
        stdout=Path("/realm/signer/results/job.out"), stderr=Path("/realm/signer/results/job.err"),
        stdin=Path("/root/.docsuri/keychain.pw"),
    ))
    assert plist["StandardInPath"] == "/root/.docsuri/keychain.pw"


def test_job_argv_adds_the_stdin_flag_only_for_unattended_jobs(job_mod):
    common = dict(interpreter=Path("/clock/python3.13"), bootstrap=Path("/s/bootstrap.py"),
                  library=Path("/s/lib"), state=Path("/s/job.json"), arguments=["--days", "1"])
    attended = job_mod.job_argv(**common)
    unattended = job_mod.job_argv(**common, unattended=True)
    # The issuer only reads stdin when told to, so the flag has to follow the install decision.
    assert "--keychain-password-stdin" not in attended
    assert unattended.count("--keychain-password-stdin") == 1
    assert unattended[-1] == "--keychain-password-stdin"


def _password_file(tmp_path, body="correct-horse-battery\n"):
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o700)
    path = directory / "keychain.pw"
    path.write_text(body)
    path.chmod(0o400)
    return path


@pytest.mark.skipif(os.geteuid() != 0, reason="requires root for ownership checks")
def test_verify_password_source_accepts_a_root_only_file(job_mod, tmp_path):
    path = _password_file(tmp_path)
    recorded = job_mod.verify_password_source(path, expected_owner=os.geteuid())
    assert recorded == job_mod.digest(path.read_bytes())


@pytest.mark.skipif(os.geteuid() != 0, reason="requires root for ownership checks")
def test_verify_password_source_rejects_a_world_readable_file(job_mod, tmp_path):
    path = _password_file(tmp_path)
    path.chmod(0o444)
    with pytest.raises(job_mod.SignerUnavailable, match="not be group- or world-accessible"):
        job_mod.verify_password_source(path)


@pytest.mark.skipif(os.geteuid() != 0, reason="requires root for ownership checks")
def test_verify_password_source_rejects_a_group_readable_file(job_mod, tmp_path):
    path = _password_file(tmp_path)
    path.chmod(0o440)
    with pytest.raises(job_mod.SignerUnavailable, match="not be group- or world-accessible"):
        job_mod.verify_password_source(path)


@pytest.mark.skipif(os.geteuid() != 0, reason="requires root for ownership checks")
def test_verify_password_source_rejects_a_world_writable_directory(job_mod, tmp_path):
    # A 0400 file inside a writable directory can be replaced by an attacker's symlink.
    path = _password_file(tmp_path)
    path.parent.chmod(0o777)
    with pytest.raises(job_mod.SignerUnavailable, match="directory is group- or world-writable"):
        job_mod.verify_password_source(path)


@pytest.mark.skipif(os.geteuid() != 0, reason="requires root for ownership checks")
def test_verify_password_source_rejects_a_directory(job_mod, tmp_path):
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o700)
    with pytest.raises(job_mod.SignerUnavailable, match="not a regular file"):
        job_mod.verify_password_source(directory)


def test_verify_password_source_rejects_a_symlink(job_mod, tmp_path):
    path = _password_file(tmp_path)
    link = tmp_path / "secrets" / "link.pw"
    link.symlink_to(path)
    with pytest.raises(job_mod.SignerUnavailable, match="not a regular file"):
        job_mod.verify_password_source(link)


def test_verify_password_source_rejects_a_short_password(job_mod, tmp_path):
    path = _password_file(tmp_path, body="short\n")
    with pytest.raises(job_mod.SignerUnavailable, match="not a single 12..1024 byte line"):
        job_mod.verify_password_source(path, expected_owner=os.geteuid())


def test_verify_password_source_rejects_a_missing_trailing_newline(job_mod, tmp_path):
    path = _password_file(tmp_path, body="correct-horse-battery")
    with pytest.raises(job_mod.SignerUnavailable, match="must end with a newline"):
        job_mod.verify_password_source(path, expected_owner=os.geteuid())


def test_verify_password_source_rejects_an_oversized_file(job_mod, tmp_path):
    path = _password_file(tmp_path, body="x" * 2000 + "\n")
    with pytest.raises(job_mod.SignerUnavailable, match="not a single 12..1024 byte line"):
        job_mod.verify_password_source(path, expected_owner=os.geteuid())


def test_install_library_records_every_file_and_freezes_the_tree(job_mod, tmp_path):
    source = tmp_path / "source" / "docsuri_platform_integrity"
    (source / "adapters").mkdir(parents=True)
    (source / "__init__.py").write_bytes(b"stale\n")
    (source / "adapters" / "receipt_signer.py").write_bytes(b"CURRENT = True\n")
    destination = tmp_path / "lib"

    recorded = job_mod.install_library(source.parent, destination, owner=os.geteuid())

    assert stat.S_IMODE(destination.lstat().st_mode) == 0o555
    assert set(recorded) == {"docsuri_platform_integrity/__init__.py",
                             "docsuri_platform_integrity/adapters/receipt_signer.py"}
    assert all(value.startswith("sha256:") for value in recorded.values())
    # Immutable, and not writable by the group that would otherwise tamper with what signs.
    for path in [destination, *destination.rglob("*")]:
        assert stat.S_IMODE(path.lstat().st_mode) == 0o555


def test_install_library_excludes_bytecode_from_the_pinned_tree(job_mod, tmp_path):
    """A `.pyc` here is code nobody reviewed, in the one tree whose promise is reviewability."""
    source = tmp_path / "source" / "docsuri_platform_integrity"
    (source / "__pycache__").mkdir(parents=True)
    (source / "__init__.py").write_bytes(b"CURRENT = True\n")
    (source / "__pycache__" / "__init__.cpython-313.pyc").write_bytes(b"stale bytecode\n")
    (source / "orphan.pyc").write_bytes(b"stale bytecode\n")
    destination = tmp_path / "lib"

    recorded = job_mod.install_library(source.parent, destination, owner=os.geteuid())

    assert set(recorded) == {"docsuri_platform_integrity/__init__.py"}
    assert not any(".pyc" in name for name in recorded)
    assert not (destination / "docsuri_platform_integrity" / "__pycache__").exists()


def test_shadowing_is_verified_against_the_bound_interpreter(job_mod, tmp_path):
    """`PYTHONPATH` losing to bundled `site-packages` is silent; install has to ask.

    This is the regression for a real failure: `--library-source` pointing at the package directory
    instead of its parent laid the tree out one level too deep, so the shadow never shadowed, every
    digest check still passed, and the job signed with the interpreter's stale bundled copy.
    """
    library = tmp_path / "lib"
    package = library / "docsuri_platform_integrity"
    package.mkdir(parents=True)
    (package / "__init__.py").write_bytes(b"CURRENT = True\n")

    job_mod.verify_shadowing(Path(sys.executable), library)

    with pytest.raises(job_mod.SignerUnavailable, match="not what the interpreter imports"):
        job_mod.verify_shadowing(Path(sys.executable), package)


def test_install_library_refuses_to_clobber_an_existing_tree(job_mod, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "lib"
    job_mod.install_library(source, destination, owner=os.geteuid())
    with pytest.raises(FileExistsError, match="remove it explicitly"):
        job_mod.install_library(source, destination, owner=os.geteuid())


def test_verify_installed_library_accepts_an_untouched_tree(job_mod, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_bytes(b"ok\n")
    destination = tmp_path / "lib"
    recorded = job_mod.install_library(source, destination, owner=os.geteuid())
    job_mod.verify_installed_library(destination, recorded, expected_owner=os.geteuid())


def test_verify_installed_library_rejects_drift(job_mod, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_bytes(b"ok\n")
    destination = tmp_path / "lib"
    recorded = job_mod.install_library(source, destination, owner=os.geteuid())
    # The point of pinning: a swapped module would otherwise be what actually signs. The tree is
    # installed 0555, so tampering means breaking that first -- which is the second guarantee.
    os.chmod(destination, 0o755)
    (destination / "module.py").chmod(0o644)
    (destination / "module.py").write_bytes(b"ok = False\n")
    with pytest.raises(job_mod.SignerUnavailable, match="contents changed since install"):
        job_mod.verify_installed_library(destination, recorded, expected_owner=os.geteuid())


def test_verify_installed_library_rejects_an_added_file(job_mod, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_bytes(b"ok\n")
    destination = tmp_path / "lib"
    recorded = job_mod.install_library(source, destination, owner=os.geteuid())
    os.chmod(destination, 0o755)
    (destination / "injected.py").write_bytes(b"malicious = True\n")
    with pytest.raises(job_mod.SignerUnavailable, match="contents changed since install"):
        job_mod.verify_installed_library(destination, recorded, expected_owner=os.geteuid())


def test_verify_installed_library_rejects_a_writable_tree(job_mod, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_bytes(b"ok\n")
    destination = tmp_path / "lib"
    recorded = job_mod.install_library(source, destination, owner=os.geteuid())
    os.chmod(destination, 0o777)
    with pytest.raises(job_mod.SignerUnavailable, match="not a root-owned immutable directory"):
        job_mod.verify_installed_library(destination, recorded, expected_owner=os.geteuid())


def test_bundled_library_digest_records_what_is_being_shadowed(job_mod, tmp_path):
    # Runs against the real interpreter, so it only means anything on macOS.
    if sys.platform != "darwin":
        pytest.skip("macOS only")
    recorded = job_mod.bundled_library_digest(Path(sys.executable))
    digest_text, count = recorded.rsplit(":", 1)
    assert digest_text.startswith("sha256:")
    assert int(count) > 0


def test_role_identity_resolves_the_sign_role(job_mod):
    if sys.platform != "darwin":
        pytest.skip("macOS only")
    try:
        uid, gid = job_mod.role_identity("test")
    except KeyError:
        pytest.skip("test realm is not provisioned on this host")
    # uid and gid must agree: the manifest and require_signer_role both demand that pairing.
    assert uid == gid == 604


def test_role_identity_uses_the_deployment_naming_helper(job_mod):
    # A locally rebuilt prefix would drift from the one the deployment actually installed.
    assert job_mod.role_account("test", "sign") == "_docsuri_r1t_sign"
    assert job_mod.role_account("production", "sign") == "_docsuri_r1_sign"


def test_passthrough_drops_the_leading_separator(job_mod):
    # REMAINDER keeps the caller's "--", and shipping it into argv leaves a second one in the
    # launchd command line, which is how the installed job came to show "-- -- --release".
    assert job_mod.passthrough(
        ["--", "--release", "r1t-clock-20260927", "--capability", "nts_clock"]
    ) == ["--release", "r1t-clock-20260927", "--capability", "nts_clock"]


def test_passthrough_is_stable_without_a_separator(job_mod):
    assert job_mod.passthrough(["--capability", "nts_clock"]) == ["--capability", "nts_clock"]


def test_job_argv_omits_the_policy_binding_the_bootstrap_injects(job_mod):
    argv = job_mod.job_argv(
        interpreter=Path("/X/python3.13"), bootstrap=Path("/X/bootstrap.py"),
        library=Path("/X/lib"), state=Path("/X/job.json"),
        arguments=passthrough_release())
    # The job states its own profile/release at exec time, so they must not be install-time args
    # that could be pointed somewhere else.
    assert "--profile" not in argv
    assert argv.count("--release") == 0


def passthrough_release():
    return ["--capability", "nts_clock"]


def test_bootstrap_and_issuer_are_distinct_scripts(job_mod, tmp_path):
    # The bug this guards: install once recorded a single "script" path for both roles, so the
    # job exec'd *itself* with the issuer's flags. argparse then saw a top-level --release it did
    # not know, and its value landed on the subcommand as "invalid choice: <release>". The job
    # reported that as an argument error while the group boundary had in fact been established.
    source = Path(__file__).resolve().parents[1] / "platform-integrity"
    bootstrap = source / "receipt_signer_job.py"
    issuer = source / "issue_receipt.py"
    assert bootstrap != issuer
    assert issuer.name == "issue_receipt.py"
    assert "issue_receipt" not in bootstrap.read_text().split("def install(")[0]


def test_issuer_state_key_is_used_for_the_exec(job_mod):
    # `run_bootstrap` must exec the issuer recorded in the state file, never its own path.
    text = (Path(__file__).resolve().parents[1]
            / "platform-integrity" / "receipt_signer_job.py").read_text()
    body = text.split("def run_bootstrap(")[1].split("def main(")[0]
    assert 'state["script"]' not in body
    assert 'state["issuer"]' in body


def test_both_signer_script_sources_resolve_to_real_files():
    # `install` derives each source from this file's own directory. Getting that wrong aborted the
    # install mid-way, which booted the old job out and left no service registered at all -- the
    # failure looked like a launchd problem, not a missing-file problem.
    here = Path(__file__).resolve().parents[1] / "platform-integrity"
    realm = Path("/Library/Application Support/DocSuri/rem-1-test/signer")
    sources = {realm / "bootstrap.py": here / "receipt_signer_job.py",
               realm / "issue_receipt.py": here / "issue_receipt.py"}
    for destination, source in sources.items():
        assert source.is_file(), source
        # The destination is in the realm, so the two must never resolve to one file.
        assert source.resolve() != destination
    # The bootstrap source is this file itself. Resolving it under the destination's name would
    # look for a platform-integrity/bootstrap.py, which is the file that was missing.
    assert sources[realm / "bootstrap.py"] == here / "receipt_signer_job.py"
